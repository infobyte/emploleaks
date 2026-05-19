import os
import sys
import configparser
from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models import SocialProfileOut, UsernameOut, UsernameCreate

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, PROJECT_ROOT)
from utils.email_lookup import lookup_email_sync, DEFAULT_PLATFORMS

router = APIRouter(tags=["social"])


@router.get("/social-profiles", response_model=list[SocialProfileOut])
async def list_social_profiles(company_id: int = Query(...)):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT sp.profile_id, sp.platform, sp.url, sp.email_recovery,
                   sp.phone_recovery, sp.employee_id, e.name as employee_name,
                   em.email as source_email
            FROM social_profiles sp
            INNER JOIN employees e ON sp.employee_id = e.employee_id
            LEFT JOIN emails em ON sp.email_id = em.email_id
            WHERE e.company_id = ?
            ORDER BY e.name, sp.platform
        """, (company_id,))
        return [{
            "profile_id": r[0],
            "platform": r[1],
            "url": r[2],
            "email_recovery": r[3],
            "phone_recovery": r[4],
            "employee_id": r[5],
            "employee_name": r[6],
            "source_email": r[7],
        } for r in rows]


@router.post("/social-profiles/lookup")
async def trigger_lookup(company_id: int = Query(...)):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT em.email_id, em.email, e.employee_id, e.name
            FROM emails em
            INNER JOIN employees e ON em.employee_id = e.employee_id
            WHERE e.company_id = ?
        """, (company_id,))

        if not rows:
            raise HTTPException(400, "No confirmed emails found for this company.")

        config = configparser.RawConfigParser()
        config.read(os.path.join(PROJECT_ROOT, 'config', 'tokens.ini'))
        platforms = list(DEFAULT_PLATFORMS)
        if config.has_section('holehe') and config.has_option('holehe', 'platforms'):
            platforms = [p.strip() for p in config.get('holehe', 'platforms').split(',') if p.strip()]

        total_found = 0
        for r in rows:
            email_id, email, employee_id = r[0], r[1], r[2]
            results = lookup_email_sync(email, platforms)
            for item in results:
                if not item.get("exists"):
                    continue
                await db.execute("""
                    INSERT INTO social_profiles (platform, url, exists_flag, email_recovery, phone_recovery, email_id, employee_id)
                    VALUES (?, ?, 1, ?, ?, ?, ?)
                """, (item["platform"], item.get("url"), item.get("email_recovery"),
                      item.get("phone_recovery"), email_id, employee_id))
                total_found += 1

        await db.commit()
        return {"found": total_found, "emails_checked": len(rows)}


@router.get("/employees/{employee_id}/usernames", response_model=list[UsernameOut])
async def list_usernames(employee_id: int):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT u.username_id, u.username, u.employee_id, e.name, u.source
            FROM usernames u
            INNER JOIN employees e ON u.employee_id = e.employee_id
            WHERE u.employee_id = ?
            ORDER BY u.username
        """, (employee_id,))
        return [{
            "username_id": r[0], "username": r[1], "employee_id": r[2],
            "employee_name": r[3], "source": r[4],
        } for r in rows]


@router.post("/employees/{employee_id}/usernames", response_model=UsernameOut)
async def add_username(employee_id: int, body: UsernameCreate):
    async with get_db() as db:
        row = await db.execute_fetchall(
            "SELECT name FROM employees WHERE employee_id = ?", (employee_id,)
        )
        if not row:
            raise HTTPException(404, "Employee not found")

        try:
            cursor = await db.execute(
                "INSERT INTO usernames (username, employee_id, source) VALUES (?, ?, 'manual')",
                (body.username.strip(), employee_id)
            )
            await db.commit()
            return {
                "username_id": cursor.lastrowid,
                "username": body.username.strip(),
                "employee_id": employee_id,
                "employee_name": row[0][0],
                "source": "manual",
            }
        except Exception as e:
            if "UNIQUE" in str(e):
                raise HTTPException(409, "Username already exists for this employee")
            raise HTTPException(500, str(e))


@router.delete("/usernames/{username_id}")
async def delete_username(username_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM usernames WHERE username_id = ?", (username_id,))
        await db.commit()
        return {"ok": True}


@router.post("/social-profiles/lookup-usernames")
async def trigger_username_lookup(company_id: int = Query(...)):
    from utils.profile_lookup import _search_username

    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT u.username_id, u.username, u.employee_id, e.name
            FROM usernames u
            INNER JOIN employees e ON u.employee_id = e.employee_id
            WHERE e.company_id = ?
        """, (company_id,))

        if not rows:
            raise HTTPException(400, "No usernames found. Add usernames to employees first.")

        config = configparser.RawConfigParser()
        config.read(os.path.join(PROJECT_ROOT, 'config', 'tokens.ini'))
        platforms = None
        if config.has_section('maigret') and config.has_option('maigret', 'platforms'):
            raw = config.get('maigret', 'platforms')
            platforms = [p.strip() for p in raw.split(',') if p.strip()]

        total_found = 0
        for r in rows:
            username, employee_id = r[1], r[2]
            results = await _search_username(username, platforms)
            for item in results:
                if not item.get("exists"):
                    continue
                try:
                    await db.execute("""
                        INSERT OR IGNORE INTO social_profiles (platform, url, exists_flag, employee_id)
                        VALUES (?, ?, 1, ?)
                    """, (item["platform"], item.get("url"), employee_id))
                    total_found += 1
                except Exception:
                    pass

        await db.commit()
        return {"found": total_found, "usernames_checked": len(rows)}
