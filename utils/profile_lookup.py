"""
Social media profile lookup using Maigret.
Searches for username existence across selected platforms.
"""

import asyncio
import logging

log = logging.getLogger(__name__)

DEFAULT_PLATFORMS = [
    'Instagram',
    'Twitter',
    'Facebook',
    'TikTok',
    'GitHub',
    'Reddit',
    'Pinterest',
    'YouTube',
    'Telegram',
    'Spotify',
]


async def _search_username(username: str, platforms: list[str] | None = None) -> list[dict]:
    """Async implementation of username search using Maigret."""
    try:
        import maigret
        from maigret.sites import MaigretDatabase
    except ImportError:
        log.error("maigret is not installed. Run: pip install maigret")
        return []

    target_platforms = platforms or DEFAULT_PLATFORMS

    try:
        import os
        pkg_dir = os.path.dirname(maigret.__file__)
        db_file = os.path.join(pkg_dir, 'resources', 'data.json')
        db = MaigretDatabase().load_from_path(db_file)
        all_sites = db.ranked_sites_dict(top=3000)

        lower_targets = [p.lower().strip() for p in target_platforms]
        sites = {k: v for k, v in all_sites.items() if k.lower() in lower_targets}

        if not sites:
            log.warning(f"No matching sites found for platforms: {target_platforms}")
            return []

        quiet_logger = logging.getLogger('maigret.quiet')
        quiet_logger.setLevel(logging.CRITICAL)

        results_dict = await maigret.search(
            username=username,
            site_dict=sites,
            logger=quiet_logger,
            timeout=10,
            no_progressbar=True,
            max_connections=10,
        )
    except Exception as e:
        log.warning(f"Maigret error for @{username}: {e}")
        return []

    results = []
    if not results_dict:
        return results

    for site_name, site_data in results_dict.items():
        if isinstance(site_data, dict):
            status_obj = site_data.get("status")
            url = site_data.get("url_user", site_data.get("url", ""))
        elif hasattr(site_data, 'status'):
            status_obj = site_data
            url = getattr(site_data, 'site_url_user', '') or site_data.get("url_user", "") if isinstance(site_data, dict) else getattr(site_data, 'site_url_user', '')
        else:
            continue

        if status_obj is None:
            continue

        is_found = False
        if hasattr(status_obj, 'is_found'):
            is_found = bool(status_obj.is_found)
        else:
            status_str = str(status_obj).lower()
            is_found = status_str in ("claimed", "available", "found", "exists")

        if not is_found:
            inner = getattr(status_obj, 'status', status_obj)
            status_str = str(inner).lower()
            is_found = status_str in ("claimed", "available", "found", "exists")

        if not is_found:
            continue

        if hasattr(status_obj, 'site_url_user') and status_obj.site_url_user:
            url = status_obj.site_url_user
        if not url:
            continue

        results.append({
            "platform": site_name,
            "url": url,
            "exists": True,
        })

    return results


def lookup_username_sync(username: str, platforms: list[str] | None = None) -> list[dict]:
    """
    Synchronous wrapper for username search across social media platforms using Maigret.
    Returns list of dicts with {platform, url, exists} for found accounts.
    """
    try:
        return asyncio.run(_search_username(username, platforms))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_search_username(username, platforms))
        finally:
            loop.close()
    except Exception as e:
        log.warning(f"Maigret sync wrapper error for @{username}: {e}")
        return []
