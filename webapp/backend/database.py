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
        ("passwords", "url", "TEXT"),
        ("username_passwords", "url", "TEXT"),
    ]
    for table, col, typedef in migrations:
        try:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except Exception:
            pass

    # One-time backfill: move URL-looking values from breach_context to url.
    for table in ("passwords", "username_passwords"):
        try:
            await db.execute(f"""
                UPDATE {table}
                   SET url = breach_context,
                       breach_context = 'clickhouse-leaks'
                 WHERE url IS NULL
                   AND breach_context IS NOT NULL
                   AND breach_context != 'proxynova-comb'
                   AND breach_context LIKE '%.%'
            """)
        except Exception:
            pass

    try:
        await db.execute("ALTER TABLE companies ADD COLUMN company_logo_url TEXT")
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

    await db.execute("""
        CREATE TABLE IF NOT EXISTS domains (
            domain_id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            company_id INTEGER,
            FOREIGN KEY (company_id) REFERENCES companies(company_id),
            UNIQUE(domain, company_id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS subdomains (
            subdomain_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subdomain TEXT NOT NULL,
            domain_id INTEGER,
            source TEXT,
            ip_address TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (domain_id) REFERENCES domains(domain_id),
            UNIQUE(subdomain, domain_id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS usernames (
            username_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            employee_id INTEGER,
            source TEXT DEFAULT 'manual',
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            UNIQUE(username, employee_id)
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
