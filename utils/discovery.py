"""
Infrastructure discovery via `assetfinder` (always) + SecurityTrails (optional).

`assetfinder` (https://github.com/tomnomnom/assetfinder) is the primary source.
It internally aggregates results from crt.sh, HackerTarget, BufferOver and
several other passive sources without rate limits we manage ourselves, so we
delegate the discovery to it instead of calling those endpoints by hand.

If a SecurityTrails API key is configured under `[discovery] securitytrails_key`
in `config/tokens.ini`, its subdomains endpoint is queried in addition and the
two result sets are merged.
"""

import logging
import os
import shutil
import socket
import subprocess

import requests

log = logging.getLogger(__name__)


_SECURITYTRAILS_URL = "https://api.securitytrails.com/v1/domain/{domain}/subdomains"
_ASSETFINDER_BIN = os.environ.get("ASSETFINDER_BIN", "assetfinder")


def _resolve_assetfinder_path() -> str | None:
    """Return the absolute path to `assetfinder` if available, else None."""
    return shutil.which(_ASSETFINDER_BIN)


def discover_assetfinder(domain: str, timeout: int = 120) -> list[str]:
    """Enumerate subdomains via the `assetfinder` Go tool. Returns a sorted list."""
    path = _resolve_assetfinder_path()
    if not path:
        log.error(
            "assetfinder binary not found. Install with: "
            "go install github.com/tomnomnom/assetfinder@latest"
        )
        return []

    try:
        proc = subprocess.run(
            [path, "-subs-only", domain],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log.warning(f"assetfinder timed out after {timeout}s for {domain}")
        return []
    except Exception as e:
        log.warning(f"assetfinder execution failed for {domain}: {e}")
        return []

    if proc.returncode != 0:
        log.warning(
            f"assetfinder exited with code {proc.returncode} for {domain}: "
            f"{proc.stderr.strip()[:200]}"
        )

    subdomains: set[str] = set()
    for line in proc.stdout.splitlines():
        name = line.strip().lower()
        if not name or name.startswith("*"):
            continue
        # Keep only subdomains of the requested domain.
        if name == domain or name.endswith("." + domain):
            subdomains.add(name)

    return sorted(subdomains)


def discover_securitytrails(domain: str, api_key: str, timeout: int = 30) -> list[str]:
    """Enumerate subdomains via the SecurityTrails API. Requires a free or paid key."""
    if not api_key:
        return []

    url = _SECURITYTRAILS_URL.format(domain=domain)
    try:
        resp = requests.get(
            url,
            headers={"APIKEY": api_key, "Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as e:
        log.warning(f"SecurityTrails request failed for {domain}: {e}")
        return []

    if resp.status_code == 401:
        log.warning("SecurityTrails: invalid API key (401)")
        return []
    if resp.status_code == 429:
        log.warning("SecurityTrails: rate limit / quota exceeded (429)")
        return []
    if not resp.ok:
        log.warning(f"SecurityTrails returned HTTP {resp.status_code} for {domain}")
        return []

    try:
        data = resp.json()
    except ValueError:
        log.warning(f"SecurityTrails returned non-JSON for {domain}")
        return []

    # API returns subdomains as labels relative to the requested domain
    # (e.g. "www", "mail.us") — we prepend `.{domain}` to get FQDNs.
    fqdns: set[str] = set()
    for sub in data.get("subdomains", []):
        sub = sub.strip().lower()
        if not sub or sub.startswith("*"):
            continue
        fqdn = f"{sub}.{domain}"
        fqdns.add(fqdn)

    return sorted(fqdns)


def resolve_dns(hostname: str) -> str | None:
    """Resolve a hostname to its first A record IP address."""
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if results:
            return results[0][4][0]
    except (socket.gaierror, OSError):
        pass
    return None


def discover_all(
    domain: str,
    securitytrails_api_key: str | None = None,
    progress_callback=None,
) -> list[dict]:
    """
    Run all configured discovery sources against a domain, deduplicate by
    subdomain, and resolve IPs for each result.

    Returns a list of dicts with keys: subdomain, ip, source.
    """
    seen: dict[str, dict] = {}

    if progress_callback:
        progress_callback(f"Running assetfinder for {domain}...")
    for sub in discover_assetfinder(domain):
        seen[sub] = {"subdomain": sub, "ip": None, "source": "assetfinder"}

    if securitytrails_api_key:
        if progress_callback:
            progress_callback(f"Querying SecurityTrails for {domain}...")
        for sub in discover_securitytrails(domain, securitytrails_api_key):
            if sub in seen:
                seen[sub]["source"] += ", securitytrails"
            else:
                seen[sub] = {"subdomain": sub, "ip": None, "source": "securitytrails"}

    if progress_callback:
        progress_callback(f"Resolving DNS for {len(seen)} subdomains...")
    for sub, data in seen.items():
        data["ip"] = resolve_dns(sub)

    return sorted(seen.values(), key=lambda x: x["subdomain"])
