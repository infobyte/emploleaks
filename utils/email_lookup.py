"""
Email lookup module using Holehe.

Checks if an email address is registered on various social media platforms
and websites using the "forgot password" technique (does not alert the target).
"""

import asyncio
import logging
import httpx
from holehe.modules import *
from holehe.core import get_functions

log = logging.getLogger('emploleaks')


async def check_email(email: str) -> list[dict]:
    """
    Check if an email is registered on ~120 platforms via Holehe.

    Returns a list of dicts with keys:
        platform, exists, email_recovery, phone_recovery, url
    """
    out = []
    client = httpx.AsyncClient(timeout=15)

    try:
        modules = get_functions()
        tasks = [module(email, client, out) for module in modules]

        for batch_start in range(0, len(tasks), 10):
            batch = tasks[batch_start:batch_start + 10]
            await asyncio.gather(*batch, return_exceptions=True)
            await asyncio.sleep(0.5)
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


def lookup_email_sync(email: str) -> list[dict]:
    """Synchronous wrapper for check_email."""
    try:
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(check_email(email))
        loop.close()
        return results
    except Exception as e:
        log.error(f"Lookup failed for {email}: {e}")
        return []
