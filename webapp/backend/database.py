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

    await db.execute("""
        CREATE TABLE IF NOT EXISTS social_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            url TEXT,
            exists_flag BOOLEAN DEFAULT 1,
            email_recovery TEXT,
            phone_recovery TEXT,
            email_id INTEGER,
            employee_id INTEGER,
            FOREIGN KEY (email_id) REFERENCES emails (email_id),
            FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        )
    """)
    await db.commit()


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
