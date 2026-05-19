import aiosqlite
import os
from contextlib import asynccontextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'emploleaks.db')


async def ensure_columns(db: aiosqlite.Connection):
    """Add triage/department columns if they don't exist yet."""
    migrations = [
        ("passwords", "triage_status", "TEXT DEFAULT 'pending'"),
        ("username_passwords", "triage_status", "TEXT DEFAULT 'pending'"),
        ("secrets_repos", "triage_status", "TEXT DEFAULT 'pending'"),
        ("employees", "department", "TEXT"),
        ("employees", "excluded", "INTEGER DEFAULT 0"),
    ]
    for table, col, typedef in migrations:
        try:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except Exception:
            pass
    await db.commit()


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
