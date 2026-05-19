#!/usr/bin/env python3
"""
EmploLeaks Telegram Sync — userbot daemon.

Standalone service that uses a Telethon userbot to download credential dump
files from approved Telegram groups/channels into `leaks_data/telegram/`.
Decoupled from the main EmploLeaks CLI: after files land on disk, run
`import_leaks` from inside emploleaks.py to ingest them into ClickHouse.

Usage:
    python3.13 telegram_sync.py login
    python3.13 telegram_sync.py list_groups
    python3.13 telegram_sync.py approve <chat_id> [--limit N]
    python3.13 telegram_sync.py unapprove <chat_id>
    python3.13 telegram_sync.py list_approved
    python3.13 telegram_sync.py backfill <chat_id> [--limit N]
    python3.13 telegram_sync.py run [--watch]
    python3.13 telegram_sync.py status
"""

import argparse
import asyncio
import configparser
import hashlib
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User


BASE_DIR = Path(__file__).resolve().parent
CONFIG_INI = BASE_DIR / "config" / "tokens.ini"
DB_PATH = BASE_DIR / "data" / "emploleaks.db"
LOG_FILE = BASE_DIR / "logs" / "telegram.log"

DEFAULT_EXTS = {"txt", "csv", "dat", "zip", "gz"}


def setup_logging():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    fh = RotatingFileHandler(LOG_FILE, maxBytes=10_000_000, backupCount=3)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(sh)
    logging.getLogger("telethon").setLevel(logging.WARNING)
    return logging.getLogger("telegram_sync")


log = setup_logging()


def load_config() -> dict:
    if not CONFIG_INI.exists():
        log.error(f"Config file not found: {CONFIG_INI}")
        sys.exit(2)
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_INI)
    if not cfg.has_section("telegram"):
        log.error("Missing [telegram] section in config/tokens.ini")
        sys.exit(2)
    s = cfg["telegram"]
    try:
        api_id = int(s.get("api_id", "0"))
    except ValueError:
        api_id = 0
    api_hash = s.get("api_hash", "").strip()
    if not api_id or not api_hash:
        log.error("api_id / api_hash empty under [telegram]")
        sys.exit(2)

    session_path = Path(s.get("session", "config/telegram.session"))
    if not session_path.is_absolute():
        session_path = BASE_DIR / session_path

    download_root = Path(s.get("download_root", "leaks_data/telegram"))
    if not download_root.is_absolute():
        download_root = BASE_DIR / download_root
    download_root.mkdir(parents=True, exist_ok=True)

    exts = {
        e.strip().lower().lstrip(".")
        for e in s.get("allowed_extensions", ",".join(DEFAULT_EXTS)).split(",")
        if e.strip()
    } or set(DEFAULT_EXTS)

    return {
        "api_id": api_id,
        "api_hash": api_hash,
        "session": str(session_path),
        "download_root": download_root,
        "extensions": exts,
        "default_backfill_limit": int(s.get("default_backfill_limit", "10")),
    }


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            username TEXT,
            approved INTEGER NOT NULL DEFAULT 0,
            backfill_limit INTEGER DEFAULT 10,
            added_at TEXT,
            last_sync_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            file_name TEXT,
            file_hash TEXT UNIQUE,
            file_size INTEGER,
            local_path TEXT,
            downloaded_at TEXT,
            UNIQUE(chat_id, message_id)
        )
    """)
    conn.commit()
    return conn


def slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_\-]+", "_", text or "")
    text = text.strip("_")
    return text[:60] or "unknown"


def is_wanted_filename(name: str, extensions: set[str]) -> bool:
    if not name:
        return False
    lower = name.lower()
    return any(lower.endswith("." + e) for e in extensions)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def message_filename(message) -> str | None:
    doc = getattr(message, "document", None)
    if not doc:
        return None
    for attr in getattr(doc, "attributes", []):
        name = getattr(attr, "file_name", None)
        if name:
            return name
    return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upsert_group(conn: sqlite3.Connection, entity) -> None:
    chat_id = int(entity.id)
    title = (
        getattr(entity, "title", None)
        or getattr(entity, "first_name", None)
        or "(unknown)"
    )
    username = getattr(entity, "username", None)
    conn.execute("""
        INSERT INTO telegram_groups (chat_id, title, username, added_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            title=excluded.title,
            username=excluded.username
    """, (chat_id, title, username, now_iso()))
    conn.commit()


async def download_message_file(
    client: TelegramClient,
    message,
    cfg: dict,
    conn: sqlite3.Connection,
    chat_title: str | None = None,
) -> bool:
    """Download a single message's document if it matches filters. Returns True if new."""
    if not getattr(message, "document", None):
        return False

    fname = message_filename(message)
    if not is_wanted_filename(fname, cfg["extensions"]):
        return False

    chat_id = int(message.chat_id)
    msg_id = int(message.id)

    cur = conn.execute(
        "SELECT 1 FROM telegram_files WHERE chat_id=? AND message_id=?",
        (chat_id, msg_id),
    )
    if cur.fetchone():
        return False

    if not chat_title:
        try:
            chat = await message.get_chat()
            chat_title = getattr(chat, "title", None) or str(chat_id)
        except Exception:
            chat_title = str(chat_id)

    group_dir = cfg["download_root"] / f"{chat_id}_{slug(chat_title)}"
    group_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{msg_id}_{slug(Path(fname).stem)}{Path(fname).suffix.lower()}"
    out_path = group_dir / safe_name
    log.info(f"Downloading '{fname}' from '{chat_title}' (msg {msg_id}) -> {out_path.name}")

    try:
        await client.download_media(message, file=str(out_path))
    except Exception as e:
        log.warning(f"Download failed for msg {msg_id}: {e}")
        if out_path.exists():
            try:
                out_path.unlink()
            except Exception:
                pass
        return False

    if not out_path.exists() or out_path.stat().st_size == 0:
        log.warning(f"Empty/missing file after download: {out_path}")
        if out_path.exists():
            out_path.unlink()
        return False

    file_hash = sha256_file(out_path)
    existing = conn.execute(
        "SELECT local_path FROM telegram_files WHERE file_hash=?", (file_hash,)
    ).fetchone()
    if existing:
        log.info(f"Hash duplicate of {existing['local_path']}, removing new copy")
        try:
            out_path.unlink()
        except Exception:
            pass
        try:
            conn.execute("""
                INSERT INTO telegram_files
                    (chat_id, message_id, file_name, file_hash, file_size, local_path, downloaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (chat_id, msg_id, fname, file_hash + f":dup-{msg_id}", 0,
                  existing["local_path"], now_iso()))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        return False

    size = out_path.stat().st_size
    rel_path = str(out_path.relative_to(BASE_DIR))
    conn.execute("""
        INSERT INTO telegram_files
            (chat_id, message_id, file_name, file_hash, file_size, local_path, downloaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (chat_id, msg_id, fname, file_hash, size, rel_path, now_iso()))
    conn.commit()
    log.info(f"Saved {size:,} bytes to {rel_path}")
    return True


def build_client(cfg: dict) -> TelegramClient:
    return TelegramClient(cfg["session"], cfg["api_id"], cfg["api_hash"])


async def cmd_login(cfg: dict):
    async with build_client(cfg) as client:
        me = await client.get_me()
        log.info(f"Authenticated as @{me.username or me.first_name} (id={me.id})")


async def cmd_list_groups(cfg: dict):
    conn = get_db()
    rows = []
    async with build_client(cfg) as client:
        async for dialog in client.iter_dialogs():
            ent = dialog.entity
            if isinstance(ent, User):
                continue
            if isinstance(ent, (Channel, Chat)):
                upsert_group(conn, ent)
                rows.append((
                    int(ent.id),
                    getattr(ent, "username", None) or "-",
                    getattr(ent, "title", "?"),
                ))

    print(f"\n{'chat_id':<15} {'username':<28} title")
    print("-" * 90)
    for cid, uname, title in rows:
        print(f"{cid:<15} {uname:<28} {title}")
    print(f"\nTotal: {len(rows)} group(s)/channel(s).")
    print("Snapshot saved to telegram_groups table.")


async def cmd_list_approved(cfg: dict):
    conn = get_db()
    rows = conn.execute("""
        SELECT chat_id, title, username, backfill_limit, last_sync_at
        FROM telegram_groups WHERE approved=1
        ORDER BY title
    """).fetchall()
    if not rows:
        print("No approved groups. Use `approve <chat_id>` first.")
        return
    print(f"\n{'chat_id':<15} {'limit':<6} {'last_sync':<28} title")
    print("-" * 100)
    for r in rows:
        print(f"{r['chat_id']:<15} {r['backfill_limit']:<6} "
              f"{(r['last_sync_at'] or '-'):<28} {r['title']}")


async def cmd_approve(cfg: dict, chat_id: int, limit: int):
    conn = get_db()
    async with build_client(cfg) as client:
        try:
            ent = await client.get_entity(chat_id)
        except Exception as e:
            log.error(f"Cannot resolve chat_id {chat_id}: {e}")
            log.error("Tip: run `list_groups` first so Telethon caches the entity.")
            return
        upsert_group(conn, ent)
        conn.execute("""
            UPDATE telegram_groups SET approved=1, backfill_limit=? WHERE chat_id=?
        """, (limit, int(ent.id)))
        conn.commit()
        title = getattr(ent, "title", str(chat_id))
        log.info(f"Approved '{title}' (chat_id={int(ent.id)}, limit={limit})")
        await _backfill_entity(client, ent, limit, cfg, conn)


async def cmd_unapprove(cfg: dict, chat_id: int):
    conn = get_db()
    conn.execute("UPDATE telegram_groups SET approved=0 WHERE chat_id=?", (chat_id,))
    conn.commit()
    log.info(f"Unapproved chat_id={chat_id}")


async def _backfill_entity(
    client: TelegramClient,
    entity,
    limit: int,
    cfg: dict,
    conn: sqlite3.Connection,
) -> int:
    title = getattr(entity, "title", None) or str(entity.id)
    log.info(f"Backfilling last {limit} messages from '{title}'...")
    downloaded = 0
    async for msg in client.iter_messages(entity, limit=limit):
        if not getattr(msg, "document", None):
            continue
        if await download_message_file(client, msg, cfg, conn, chat_title=title):
            downloaded += 1
    conn.execute(
        "UPDATE telegram_groups SET last_sync_at=? WHERE chat_id=?",
        (now_iso(), int(entity.id)),
    )
    conn.commit()
    log.info(f"Backfill done for '{title}': {downloaded} new file(s)")
    return downloaded


async def cmd_backfill(cfg: dict, chat_id: int, limit: int):
    conn = get_db()
    async with build_client(cfg) as client:
        try:
            ent = await client.get_entity(chat_id)
        except Exception as e:
            log.error(f"Cannot resolve chat_id {chat_id}: {e}")
            return
        await _backfill_entity(client, ent, limit, cfg, conn)


async def cmd_status(cfg: dict):
    conn = get_db()
    approved = conn.execute(
        "SELECT COUNT(*) FROM telegram_groups WHERE approved=1"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM telegram_groups").fetchone()[0]
    files_row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(file_size),0) FROM telegram_files"
    ).fetchone()
    print(f"\nApproved groups : {approved}/{total}")
    print(f"Files downloaded: {files_row[0]} ({files_row[1] / 1e6:.1f} MB)")
    print(f"Download root   : {cfg['download_root']}")
    print(f"Session file    : {cfg['session']}")
    print(f"Extensions      : {', '.join(sorted(cfg['extensions']))}")


async def cmd_run(cfg: dict, watch: bool):
    conn = get_db()
    approved = conn.execute(
        "SELECT chat_id, backfill_limit FROM telegram_groups WHERE approved=1"
    ).fetchall()
    if not approved:
        log.warning("No approved groups. Use `approve <chat_id>` first.")
        return

    async with build_client(cfg) as client:
        entities = []
        for row in approved:
            try:
                ent = await client.get_entity(row["chat_id"])
                entities.append(ent)
            except Exception as e:
                log.warning(f"Skipping chat_id {row['chat_id']}: {e}")
                continue
            await _backfill_entity(
                client, ent, row["backfill_limit"] or cfg["default_backfill_limit"],
                cfg, conn,
            )

        if not watch:
            log.info("Backfill complete. Exiting (use --watch to stay alive).")
            return

        watch_ids = [int(e.id) for e in entities]
        log.info(f"Listening for new messages in {len(watch_ids)} approved group(s)...")

        @client.on(events.NewMessage(chats=watch_ids))
        async def on_new_message(event):
            try:
                if event.message.document:
                    await download_message_file(client, event.message, cfg, conn)
            except Exception as e:
                log.warning(f"Listener error for msg {event.message.id}: {e}")

        await client.run_until_disconnected()


def main():
    parser = argparse.ArgumentParser(
        description="EmploLeaks Telegram sync daemon (Telethon userbot).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Typical flow:\n"
            "  1) python3.13 telegram_sync.py login         (one-time, enter SMS code)\n"
            "  2) python3.13 telegram_sync.py list_groups   (find chat_ids you want)\n"
            "  3) python3.13 telegram_sync.py approve <chat_id>\n"
            "  4) python3.13 telegram_sync.py run --watch   (daemon: backfill + listen)\n"
            "  5) from inside emploleaks.py: import_leaks   (push everything to ClickHouse)\n"
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<command>")

    sub.add_parser("login", help="One-time Telegram authentication")
    sub.add_parser("list_groups",
                   help="List all chats your account is in (and snapshot to DB)")
    sub.add_parser("list_approved", help="List groups currently approved for sync")
    sub.add_parser("status", help="Show counts of approved groups and downloaded files")

    p_a = sub.add_parser("approve",
                         help="Mark a chat as approved and run an immediate backfill")
    p_a.add_argument("chat_id", type=int)
    p_a.add_argument("--limit", type=int, default=None,
                     help="Number of recent messages to scan (default: from config)")

    p_u = sub.add_parser("unapprove", help="Remove approval from a chat")
    p_u.add_argument("chat_id", type=int)

    p_b = sub.add_parser("backfill", help="Download last N files from a single group")
    p_b.add_argument("chat_id", type=int)
    p_b.add_argument("--limit", type=int, default=None,
                     help="Number of recent messages to scan (default: from config)")

    p_r = sub.add_parser(
        "run",
        help="Backfill all approved groups; optionally stay alive listening for new files",
    )
    p_r.add_argument("--watch", action="store_true",
                     help="Keep the process alive listening for NewMessage events")

    args = parser.parse_args()
    cfg = load_config()
    default_limit = cfg["default_backfill_limit"]

    try:
        if args.cmd == "login":
            asyncio.run(cmd_login(cfg))
        elif args.cmd == "list_groups":
            asyncio.run(cmd_list_groups(cfg))
        elif args.cmd == "list_approved":
            asyncio.run(cmd_list_approved(cfg))
        elif args.cmd == "status":
            asyncio.run(cmd_status(cfg))
        elif args.cmd == "approve":
            limit = args.limit if args.limit is not None else default_limit
            asyncio.run(cmd_approve(cfg, args.chat_id, limit))
        elif args.cmd == "unapprove":
            asyncio.run(cmd_unapprove(cfg, args.chat_id))
        elif args.cmd == "backfill":
            limit = args.limit if args.limit is not None else default_limit
            asyncio.run(cmd_backfill(cfg, args.chat_id, limit))
        elif args.cmd == "run":
            asyncio.run(cmd_run(cfg, args.watch))
    except KeyboardInterrupt:
        log.info("Interrupted. Bye.")


if __name__ == "__main__":
    main()
