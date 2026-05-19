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

KNOWN_PATTERNS = [
    {
        'name': 'email:password:url',
        'regex': r'^([^:@\s]+@[^:@\s]+):([^:]+):(.+)$',
        'fields': ['email', 'password', 'url'],
    },
    {
        'name': 'email:password',
        'regex': r'^([^:@\s]+@[^:@\s]+):(.+)$',
        'fields': ['email', 'password'],
    },
    {
        'name': 'email;password',
        'regex': r'^([^;@\s]+@[^;@\s]+);(.+)$',
        'fields': ['email', 'password'],
    },
    {
        'name': 'email|password',
        'regex': r'^([^|@\s]+@[^|@\s]+)\|(.+)$',
        'fields': ['email', 'password'],
    },
    {
        'name': 'url,email,password',
        'regex': r'^([^,]+),([^,@\s]+@[^,@\s]+),(.+)$',
        'fields': ['url', 'email', 'password'],
    },
    {
        'name': 'id:password (numeric)',
        'regex': r'^(\d{5,}):(.+)$',
        'fields': ['username', 'password'],
    },
    {
        'name': 'username:password',
        'regex': r'^([^:@\s]{3,}):(.+)$',
        'fields': ['username', 'password'],
    },
]

FORMAT_DETECTION_PROMPT = (
    'You are a data format analyst. Given sample lines from a credential leak file, '
    'identify the format and return a JSON object with:\n'
    '- "separator": the character(s) separating fields\n'
    '- "fields": ordered list of field names. Use ONLY these names: "email", "password", "url", "username", "hash", "other"\n'
    '- "skip_lines": number of header lines to skip (0 if none)\n'
    '- "notes": brief explanation of the format\n\n'
    'Respond ONLY with valid JSON, no markdown or explanation.\n\n'
    'Example response:\n'
    '{"separator": ":", "fields": ["email", "password", "url"], "skip_lines": 0, "notes": "Standard email:pass:url format"}\n\n'
    'Here are the sample lines:\n'
)


def _detect_known_format(lines):
    """Try to match lines against known patterns. Returns pattern dict or None."""
    for pattern in KNOWN_PATTERNS:
        matches = 0
        for line in lines[:20]:
            if re.match(pattern['regex'], line.strip()):
                matches += 1
        if matches >= len(lines[:20]) * 0.6:
            return pattern
    return None


def _detect_format_with_ai(lines, api_endpoint, api_key, model):
    """Use LLM to detect the format of unknown credential files."""
    sample = '\n'.join(lines[:30])
    prompt = FORMAT_DETECTION_PROMPT + sample

    url = api_endpoint.rstrip('/') + '/chat/completions'
    headers = {'Content-Type': 'application/json'}
    if api_key and api_key.lower() != 'ollama':
        headers['Authorization'] = f'Bearer {api_key}'

    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.1,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content'].strip()

        if content.startswith('```'):
            content = content.split('\n', 1)[1] if '\n' in content else content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()

        result = json.loads(content)
        if 'separator' in result and 'fields' in result:
            log.info(f"AI detected format: {result.get('notes', 'unknown')}")
            return result
        return None
    except Exception as e:
        log.error(f"AI format detection failed: {e}")
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
    Parse a credential leak file, auto-detecting its format.

    Returns an iterator of tuples:
        (mail_username, mail_domain, mail_tld, password, uri_subdomain, uri_domain, uri_tld)

    Falls back to AI detection for unknown formats.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            sample_lines = []
            for i, line in enumerate(f):
                line = line.strip()
                if line:
                    sample_lines.append(line)
                if len(sample_lines) >= 50:
                    break
    except Exception as e:
        log.error(f"Cannot read {filepath}: {e}")
        return

    if not sample_lines:
        return

    known = _detect_known_format(sample_lines)
    if known:
        log.info(f"  Format detected: {known['name']}")
        yield from _parse_with_regex(filepath, known['regex'], known['fields'])
        return

    if not api_endpoint:
        log.warning(f"  Unknown format in {os.path.basename(filepath)}, skipping (no AI configured)")
        return

    ai_result = _detect_format_with_ai(sample_lines, api_endpoint, api_key, model)
    if not ai_result:
        log.warning(f"  Could not detect format for {os.path.basename(filepath)}")
        return

    yield from _parse_with_ai_result(filepath, ai_result)


def _parse_with_regex(filepath, regex, fields):
    """Parse a file using a known regex pattern."""
    compiled = re.compile(regex)
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = compiled.match(line)
            if not m:
                continue

            groups = m.groups()
            data = dict(zip(fields, groups))
            email = data.get('email', '')
            password = data.get('password', '')
            url = data.get('url', '')
            raw_username = data.get('username', '')

            if email:
                username, domain, tld = _parse_email(email)
                if not username:
                    continue
            elif raw_username:
                username = raw_username
                domain = ''
                tld = ''
            else:
                continue

            uri_sub, uri_dom, uri_tld = _parse_url(url) if url else ('', '', '')
            yield (username, domain, tld, password, uri_sub, uri_dom, uri_tld)


def _parse_with_ai_result(filepath, ai_result):
    """Parse a file using AI-detected format instructions."""
    sep = ai_result.get('separator', ':')
    fields = ai_result.get('fields', [])
    skip = ai_result.get('skip_lines', 0)

    if 'email' not in fields and 'username' not in fields:
        log.warning("  AI format has no email/username field, skipping")
        return

    email_idx = fields.index('email') if 'email' in fields else None
    user_idx = fields.index('username') if 'username' in fields else None
    pass_idx = fields.index('password') if 'password' in fields else None
    hash_idx = fields.index('hash') if 'hash' in fields else None
    url_idx = fields.index('url') if 'url' in fields else None

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            if i < skip:
                continue
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

            uri_sub, uri_dom, uri_tld = _parse_url(url) if url else ('', '', '')
            yield (username, domain, tld, password, uri_sub, uri_dom, uri_tld)


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
