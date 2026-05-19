"""
AI-powered credential leak file parser.

Detects the format of credential dump files automatically:
- Known formats (email:password, email:password:url) are parsed directly.
- Unknown formats are analyzed by an LLM which returns parsing instructions.
- Supports .zip and .gz archives (extracts and parses contents).
"""

import gzip
import json
import logging
import os
import re
import tempfile
import zipfile

import requests

log = logging.getLogger('emploleaks')

_SEPARATOR_CHARS = (':', ';', '|', '\t', ',')


def _detect_encoding(filepath):
    """Sniff the first bytes for a BOM and pick the right encoding."""
    try:
        with open(filepath, 'rb') as f:
            head = f.read(4)
    except Exception:
        return 'utf-8'
    if head.startswith(b'\xff\xfe\x00\x00') or head.startswith(b'\x00\x00\xfe\xff'):
        return 'utf-32'
    if head.startswith(b'\xff\xfe') or head.startswith(b'\xfe\xff'):
        return 'utf-16'
    if head.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    return 'utf-8'


def _open_text(filepath):
    """Open a leak file with auto-detected encoding, ignoring decode errors."""
    encoding = _detect_encoding(filepath)
    return open(filepath, 'r', encoding=encoding, errors='ignore')


def _looks_like_credential_line(line):
    """Heuristic: line has a separator AND at least one structural marker."""
    if len(line) < 5:
        return False
    if not any(s in line for s in _SEPARATOR_CHARS):
        return False
    # Reject lines that are >50% non-alphanumeric (banners, ASCII art, control chars).
    alnum = sum(1 for c in line if c.isalnum())
    return alnum * 2 >= len(line)


_AGENT_SYSTEM_PROMPT = (
    'You are a credential leak file parser agent. Your job is to propose a JSON parse '
    'schema for a credential dump file, so the caller can extract usernames, emails, '
    'and passwords cleanly.\n\n'
    'You have TWO parsing strategies. Pick the right one for the file:\n\n'
    '=== Strategy 1: "columns" — fixed-column split ===\n'
    'Use when every line has the SAME number of columns when split on the separator.\n'
    '{\n'
    '  "strategy": "columns",\n'
    '  "separator": "<the char(s) that split fields, e.g. \\":\\" or \\";\\" or \\"|\\">",\n'
    '  "fields": ["<field1>", "<field2>", ...],\n'
    '  "skip_lines": <int, header lines to skip>,\n'
    '  "notes": "<brief explanation>"\n'
    '}\n'
    'Allowed field names: "email", "username", "password", "url", "hash", "other".\n'
    'The "fields" array length MUST equal the column count after splitting. Use "other" liberally to absorb junk columns.\n\n'
    '=== Strategy 2: "rightmost_pair" — trailing credential extraction ===\n'
    'Use when lines VARY in column count (typical for stealer logs: some have URL paths, some have android package signatures with internal `:` and `@`, some have country codes, etc.) but ALL end with `<user_or_email>:<password>` as the last pair.\n'
    '{\n'
    '  "strategy": "rightmost_pair",\n'
    '  "skip_lines": <int, header lines to skip>,\n'
    '  "notes": "<brief explanation>"\n'
    '}\n'
    'The caller will, for each line: find the last `:` (password boundary), then find the previous `:` or `/` (user boundary), and yield the (user_or_email, password) pair.\n\n'
    '=== How to choose ===\n'
    '- Sample lines all look like `aaa:bbb` (consistent 2 columns) → "columns" with ["email", "password"] or ["username", "password"].\n'
    '- Sample lines all look like `aaa:bbb:ccc` (consistent 3 columns) → "columns" with 3 fields.\n'
    '- Sample lines start with URL/path/android signature and the column count varies wildly between lines → "rightmost_pair".\n'
    '- Banner lines, channel headers, emoji art, decorative underscores → increase skip_lines so they are skipped.\n\n'
    'Common formats you will see (don\'t hardcode — let the sample dictate):\n'
    '  - `email:password`                    → columns ["email","password"]\n'
    '  - `email:password:url`                → columns ["email","password","url"]\n'
    '  - `https://x@y.com:pass`              → rightmost_pair (URL prefix varies in length)\n'
    '  - `android://<sig>@<pkg>/:email:pass` → rightmost_pair (signature has internal @ and :)\n'
    '  - `IT https://url:email:pass`         → rightmost_pair (country code prefix)\n'
    '  - `domain.com/path:user:pass`         → rightmost_pair (no protocol)\n'
    '  - `192.168.x.x:port/:user:pass`       → rightmost_pair (IP+port stealer log)\n\n'
    'Respond ONLY with valid JSON, no markdown, no commentary.'
)


def _call_ai_for_schema(messages, api_endpoint, api_key, model, timeout=60):
    """Send a chat completion request and parse the JSON schema response.

    Accepts two schema shapes:
      - {"strategy": "columns", "separator": ..., "fields": [...], ...}
      - {"strategy": "rightmost_pair", "skip_lines": N, ...}
    Anything else is rejected (caller treats as failed iteration).
    """
    url = api_endpoint.rstrip('/') + '/chat/completions'
    headers = {'Content-Type': 'application/json'}
    if api_key and api_key.lower() != 'ollama':
        headers['Authorization'] = f'Bearer {api_key}'
    payload = {'model': model, 'messages': messages, 'temperature': 0}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content'].strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[1] if '\n' in content else content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
        result = json.loads(content)
        if not isinstance(result, dict):
            log.warning(f"  AI returned non-dict: {content[:200]!r}")
            return None
        strategy = result.get('strategy', 'columns')
        if strategy == 'rightmost_pair':
            return result
        if strategy == 'columns':
            if 'separator' not in result or 'fields' not in result:
                log.warning(f"  AI columns schema missing separator/fields: {content[:200]!r}")
                return None
            return result
        log.warning(f"  AI returned unknown strategy {strategy!r}: {content[:200]!r}")
        return None
    except Exception as e:
        log.warning(f"  AI call failed: {e}")
        return None


def _parse_email(email):
    """Split email into (username, domain, tld). Returns None tuple on failure."""
    try:
        username, domain_full = email.split('@', 1)
        parts = domain_full.split('.')
        tld = parts[-1]
        domain = '.'.join(parts[:-1])
        return username, domain, tld
    except (ValueError, IndexError):
        return None, None, None


_GARBAGE_USER_PREFIXES = ('http', 'android', 'ftp', '//')
_GARBAGE_PASS_PREFIXES = ('http://', 'https://', 'android://', 'ftp://', '//')


def _is_clean_credential(username, password):
    """Reject obvious garbage (URL paths, oversized fields, control chars)."""
    if not username or not password:
        return False
    if len(username) > 64 or len(username) < 1:
        return False
    if len(password) > 256 or len(password) < 1:
        return False
    lower_user = username.lower()
    if lower_user.startswith(_GARBAGE_USER_PREFIXES):
        return False
    # Path-like or separator-contaminated usernames mean a bad split.
    if any(ch in username for ch in ('/', ':', '\\', ' ', '\t', '\r', '\n')):
        return False
    # Same checks on the password — a bad split often leaves URL paths or
    # extra columns in the password slot. Allow a single ':' (rare but legit
    # in some encoded passwords); reject anything else that screams URL.
    if password.lower().startswith(_GARBAGE_PASS_PREFIXES):
        return False
    if '/' in password or password.count(':') >= 2:
        return False
    if any(ch in password for ch in ('\\', ' ', '\t', '\r', '\n')):
        return False
    return True


def _parse_url(url):
    """Split URL into (subdomain, domain, tld)."""
    try:
        url = url.replace('http://', '').replace('https://', '').split('/')[0]
        parts = url.split('.')
        if len(parts) < 2:
            return '', url, ''
        tld = parts[-1]
        domain = parts[-2]
        subdomain = '.'.join(parts[:-2]) if len(parts) > 2 else ''
        return subdomain, domain, tld
    except Exception:
        return '', '', ''


def parse_file(filepath, api_endpoint=None, api_key=None, model=None):
    """
    Parse a credential leak file. Uses an AI agent loop (with self-correction)
    to derive the parse schema for the file, then applies it.

    Returns an iterator of tuples:
        (mail_username, mail_domain, mail_tld, password, uri_subdomain, uri_domain, uri_tld)
    """
    try:
        with _open_text(filepath) as f:
            raw_lines = []
            credential_lines = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw_lines.append(line)
                if _looks_like_credential_line(line):
                    credential_lines.append(line)
                if len(credential_lines) >= 80 or len(raw_lines) >= 8000:
                    break
    except Exception as e:
        log.error(f"Cannot read {filepath}: {e}")
        return

    # Prefer the credential-looking subset (skips banners / ASCII art).
    # Fall back to raw lines so we don't break on plain-text files without separators.
    sample_lines = credential_lines if credential_lines else raw_lines[:80]
    if not sample_lines:
        return

    if not api_endpoint:
        log.warning(
            f"  Skipping {os.path.basename(filepath)}: no AI configured. "
            f"Set [ai] in tokens.ini to enable the agent parser."
        )
        return

    log.info(f"  Running AI agent parser (max 7 iterations, temp=0)...")
    yield from _parse_with_ai_agent(
        filepath, sample_lines, api_endpoint, api_key, model, max_iters=7,
    )


def _extract_rightmost_pair(line, boundary_chars=(':', '/')):
    """
    Find the trailing `<user_or_email>:<password>` pair in a line.

    Strategy: locate the LAST `:` (password boundary), then walk left to find
    the previous occurrence of any char in `boundary_chars` (user boundary).
    Whatever sits between those two delimiters is the user/email; whatever
    follows the last `:` is the password. Everything to the left of the user
    boundary is discarded (URL paths, package signatures, country codes, etc.).

    Returns (user_or_email, password) or (None, None) on failure.
    """
    last_colon = line.rfind(':')
    if last_colon <= 0 or last_colon >= len(line) - 1:
        return None, None

    password = line[last_colon + 1:]
    lhs = line[:last_colon]

    boundary_pos = -1
    for ch in boundary_chars:
        pos = lhs.rfind(ch)
        if pos > boundary_pos:
            boundary_pos = pos

    user = lhs[boundary_pos + 1:] if boundary_pos >= 0 else lhs

    if not user or not password:
        return None, None
    return user, password


def _apply_schema_to_lines(lines_iter, schema, sanitize=True):
    """
    Apply a parse schema to an iterable of lines and yield credential tuples.

    Dispatches on `schema["strategy"]`:
      - "columns" (default): fixed-column split by `separator`.
      - "rightmost_pair": extract the trailing `<user>:<password>` from each line.

    With sanitize=False, yields raw extractions (including garbage) so callers
    can score the schema. With sanitize=True (default), filters via
    `_is_clean_credential` before yielding.
    """
    strategy = schema.get('strategy', 'columns')
    skip = schema.get('skip_lines', 0) or 0

    if strategy == 'rightmost_pair':
        for i, line in enumerate(lines_iter):
            if i < skip:
                continue
            if isinstance(line, str):
                line = line.strip()
            if not line:
                continue
            raw_user, password = _extract_rightmost_pair(line)
            if not raw_user or not password:
                continue
            if '@' in raw_user:
                username, domain, tld = _parse_email(raw_user)
                if not username:
                    continue
            else:
                username, domain, tld = raw_user, '', ''
            if sanitize and not _is_clean_credential(username, password):
                continue
            yield (username, domain, tld, password, '', '', '')
        return

    # Default: columns strategy.
    sep = schema.get('separator', ':')
    fields = schema.get('fields', [])

    if 'email' not in fields and 'username' not in fields:
        return

    email_idx = fields.index('email') if 'email' in fields else None
    user_idx = fields.index('username') if 'username' in fields else None
    pass_idx = fields.index('password') if 'password' in fields else None
    hash_idx = fields.index('hash') if 'hash' in fields else None
    url_idx = fields.index('url') if 'url' in fields else None

    for i, line in enumerate(lines_iter):
        if i < skip:
            continue
        if isinstance(line, str):
            line = line.strip()
        if not line:
            continue

        parts = line.split(sep)
        if len(parts) < len(fields):
            continue

        email = parts[email_idx] if email_idx is not None else ''
        password = parts[pass_idx] if pass_idx is not None else ''
        if not password and hash_idx is not None:
            password = parts[hash_idx]
        url = parts[url_idx] if url_idx is not None else ''
        raw_user = parts[user_idx] if user_idx is not None else ''

        if email and '@' in email:
            username, domain, tld = _parse_email(email)
            if not username:
                continue
        elif raw_user:
            username = raw_user
            domain = ''
            tld = ''
        elif email:
            username = email
            domain = ''
            tld = ''
        else:
            continue

        if sanitize and not _is_clean_credential(username, password):
            continue

        uri_sub, uri_dom, uri_tld = _parse_url(url) if url else ('', '', '')
        yield (username, domain, tld, password, uri_sub, uri_dom, uri_tld)


def _score_schema(sample_lines, schema):
    """
    Run a schema against the sample WITHOUT sanitization and score the output.

    The score is `clean_count / sample_size` — NOT `clean_count / extracted`.
    This deliberately penalizes schemas that produce few extractions (e.g. a
    column schema with too many `other` slots that only fits 1 out of 80
    sample lines). A schema must cover most of the sample AND extract clean
    rows to win.

    Returns (score, bad_examples, total_extracted).
    """
    sample_size = max(len(sample_lines), 1)
    extracted = list(_apply_schema_to_lines(sample_lines, schema, sanitize=False))
    if not extracted:
        return 0.0, [], 0

    clean_count = 0
    bad = []
    for tup in extracted:
        u, p = tup[0], tup[3]
        if _is_clean_credential(u, p):
            clean_count += 1
        elif len(bad) < 5:
            bad.append({'username': u[:80], 'password': p[:50]})

    return clean_count / sample_size, bad, len(extracted)


def _parse_with_ai_agent(filepath, sample_lines, api_endpoint, api_key, model, max_iters=7):
    """
    Agentic AI parser: propose schema -> apply to sample -> score -> if bad,
    feed the error back to the model and ask for a revised schema. Repeat up
    to `max_iters` times. Once score >= 0.8 (and >= 5 rows extracted), parse
    the full file with that schema.

    Falls back to the best-scoring schema seen ONLY if its score is >= 0.7
    (we never silently ingest low-confidence garbage).
    """
    # Send up to 50 sample lines for better format coverage (we sampled 80 upstream).
    sample_text = '\n'.join(sample_lines[:50])
    history = [
        {'role': 'system', 'content': _AGENT_SYSTEM_PROMPT},
        {'role': 'user', 'content': (
            f'Sample lines from the file (one per line):\n{sample_text}\n\n'
            'Propose a parse schema. Respond with JSON only.'
        )},
    ]

    best = None  # tuple (score, schema)

    for attempt in range(1, max_iters + 1):
        schema = _call_ai_for_schema(history, api_endpoint, api_key, model)
        if not schema:
            log.warning(f"  AI agent iter {attempt}: no usable schema returned")
            break

        score, bad, total = _score_schema(sample_lines, schema)
        strategy = schema.get('strategy', 'columns')
        if strategy == 'rightmost_pair':
            detail = f"strategy='rightmost_pair' skip={schema.get('skip_lines', 0)}"
        else:
            detail = (
                f"strategy='columns' sep={schema.get('separator')!r} "
                f"fields={schema.get('fields')} skip={schema.get('skip_lines', 0)}"
            )
        log.info(
            f"  AI agent iter {attempt}: {detail} "
            f"-> score={score:.2f} ({total}/{len(sample_lines)} rows extracted)"
        )

        if best is None or score > best[0]:
            best = (score, schema)

        if score >= 0.8 and total >= 5:
            log.info(f"  AI agent converged after {attempt} iteration(s)")
            with _open_text(filepath) as f:
                yield from _apply_schema_to_lines(f, schema, sanitize=True)
            return

        if attempt == max_iters:
            break

        # Pair each bad output with the source line that produced it so the
        # model sees both the input and what it generated. Helps it diagnose.
        bad_with_source = []
        for tup_idx, tup in enumerate(_apply_schema_to_lines(sample_lines, schema, sanitize=False)):
            u, p = tup[0], tup[3]
            if _is_clean_credential(u, p):
                continue
            if tup_idx < len(sample_lines):
                bad_with_source.append({
                    'source_line': sample_lines[tup_idx][:200],
                    'extracted_user': u[:80],
                    'extracted_pass': p[:50],
                })
            if len(bad_with_source) >= 5:
                break

        sample_size = len(sample_lines)
        coverage_pct = 100 * total / max(sample_size, 1)
        feedback = (
            f'You proposed: {json.dumps(schema)}\n\n'
            f'Applied to the {sample_size}-line sample, your schema:\n'
            f'  - extracted {total} rows ({coverage_pct:.0f}% coverage of the sample)\n'
            f'  - of those, only {score*100:.0f}% (relative to the FULL sample) were clean credentials\n\n'
            'Below are bad extractions paired with the original source line that produced them — study the misalignment carefully:\n'
            f'{json.dumps(bad_with_source if bad_with_source else bad, indent=2)}\n\n'
            'Diagnosis checklist (in order of likelihood):\n'
            '1. **If coverage is low and lines vary in structure**: your "columns" schema is too rigid for this file. Switch to `{"strategy": "rightmost_pair", "skip_lines": N}`. This handles lines where the URL/path/signature prefix has variable internal `:` separators (typical stealer logs, android packages).\n'
            '2. **Extracted user has "/" or ":" or starts with "http"/"android"**: a URL/path column was assigned to "email" or "username". Reassign that index to "other".\n'
            '3. **Extracted pass looks like an email or URL**: field order is shifted by one. Add an "other" before the credential columns, or remove an extra field.\n'
            '4. **Source line has more columns than your fields array**: add "other" entries until the count matches the actual column count of the line.\n'
            '5. **Source line begins with banner/header/emoji decoration**: increase skip_lines.\n'
            '6. **The credential pair is always the LAST `<user_or_email>:<password>` in the line** (read right to left). If you cannot get a fixed-column schema to fit, "rightmost_pair" is almost certainly the right strategy.\n\n'
            'Propose a REVISED schema. Respond with JSON only.'
        )
        history.append({'role': 'assistant', 'content': json.dumps(schema)})
        history.append({'role': 'user', 'content': feedback})

    if best and best[0] >= 0.7:
        log.warning(
            f"  AI agent did not converge after {max_iters} iters; "
            f"using best schema seen (score={best[0]:.2f}) as fallback"
        )
        with _open_text(filepath) as f:
            yield from _apply_schema_to_lines(f, best[1], sanitize=True)
    else:
        log.warning(
            f"  AI agent gave up on {os.path.basename(filepath)} "
            f"(best score: {best[0] if best else 0:.2f}, fallback threshold 0.7)"
        )


def iter_leak_files(directory):
    """
    Walk a directory yielding paths to parseable files.
    Automatically extracts .zip and .gz archives to temp dirs.
    """
    for root, _, files in os.walk(directory):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            lower = fname.lower()

            if lower.endswith('.zip'):
                yield from _extract_zip(fpath)
            elif lower.endswith('.gz'):
                yield from _extract_gz(fpath)
            elif lower.endswith(('.txt', '.csv', '.dat', '.tsv', '.log')):
                yield fpath


def _extract_zip(zip_path):
    """Extract a zip file to a temp directory and yield contained file paths."""
    try:
        tmp = tempfile.mkdtemp(prefix='emploleaks_zip_')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmp)
        log.info(f"  Extracted ZIP: {os.path.basename(zip_path)}")
        yield from iter_leak_files(tmp)
    except (zipfile.BadZipFile, Exception) as e:
        log.error(f"  Error extracting {zip_path}: {e}")


def _extract_gz(gz_path):
    """Decompress a .gz file to a temp file and yield the path."""
    try:
        tmp = tempfile.NamedTemporaryFile(
            prefix='emploleaks_gz_', suffix='.txt', delete=False
        )
        with gzip.open(gz_path, 'rb') as gz_in:
            tmp.write(gz_in.read())
        tmp.close()
        log.info(f"  Extracted GZ: {os.path.basename(gz_path)}")
        yield tmp.name
    except Exception as e:
        log.error(f"  Error extracting {gz_path}: {e}")
