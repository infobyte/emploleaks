"""
Email lookup module using Holehe.

Checks if an email address is registered on various social media platforms
and websites using the "forgot password" technique (does not alert the target).
"""

import asyncio
import logging
import httpx
from holehe.core import import_submodules, get_functions
import holehe.modules

log = logging.getLogger('emploleaks')

DEFAULT_PLATFORMS = [
    "google", "discord", "docker", "eventbrite", "github",
    "instagram", "office365", "twitter", "spotify", "snapchat",
    "pinterest", "adobe", "amazon", "firefox", "flickr",
    "imgur", "nike", "patreon", "wordpress", "yahoo",
]

_all_modules = None
_all_funcs = None


def _load_all_functions():
    global _all_modules, _all_funcs
    if _all_funcs is None:
        _all_modules = import_submodules(holehe.modules)
        _all_funcs = get_functions(_all_modules)
    return _all_funcs


def get_available_platforms() -> list[str]:
    """Return sorted list of all available platform names."""
    funcs = _load_all_functions()
    return sorted([f.__name__ for f in funcs])


def _get_filtered_functions(platforms: list[str] | None = None):
    """Get holehe check functions, optionally filtered to specific platforms."""
    all_funcs = _load_all_functions()
    if not platforms:
        return all_funcs
    platform_set = {p.lower().strip() for p in platforms}
    return [f for f in all_funcs if f.__name__ in platform_set]


async def check_email(email: str, platforms: list[str] | None = None) -> list[dict]:
    """
    Check if an email is registered on platforms via Holehe.

    Args:
        email: Email address to check
        platforms: Optional list of platform names to check. If None, checks all.

    Returns a list of dicts with keys:
        platform, exists, email_recovery, phone_recovery, url, rate_limited
    """
    out = []
    client = httpx.AsyncClient(timeout=15)

    try:
        funcs = _get_filtered_functions(platforms)
        if not funcs:
            log.warning("No valid platforms to check.")
            return []

        log.debug(f"Checking {len(funcs)} platforms for {email}")
        tasks = [func(email, client, out) for func in funcs]

        for batch_start in range(0, len(tasks), 10):
            batch = tasks[batch_start:batch_start + 10]
            await asyncio.gather(*batch, return_exceptions=True)
            await asyncio.sleep(0.3)
    except Exception as e:
        log.error(f"Holehe error for {email}: {e}")
    finally:
        await client.aclose()

    results = []
    for item in out:
        if not item.get("exists", False) and not item.get("rateLimit", False):
            continue

        results.append({
            "platform": item.get("name", "unknown"),
            "exists": item.get("exists", False),
            "email_recovery": item.get("emailrecovery") or None,
            "phone_recovery": item.get("phoneNumber") or None,
            "url": item.get("domain") or None,
            "rate_limited": item.get("rateLimit", False),
        })

    return results


def lookup_email_sync(email: str, platforms: list[str] | None = None) -> list[dict]:
    """Synchronous wrapper for check_email."""
    try:
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(check_email(email, platforms))
        loop.close()
        return results
    except Exception as e:
        log.error(f"Lookup failed for {email}: {e}")
        return []
