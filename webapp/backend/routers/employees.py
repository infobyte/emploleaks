import logging
import os
import sys
import configparser
from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models import EmployeeOut, EmployeeUpdate, BulkDepartment

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, PROJECT_ROOT)
from utils.ai_classifier import classify_roles

log = logging.getLogger(__name__)
router = APIRouter(tags=["employees"])


def _load_ai_config():
    config_path = os.path.join(PROJECT_ROOT, 'config', 'tokens.ini')
    cfg = configparser.ConfigParser()
    cfg.read(config_path)
    if 'ai' not in cfg:
        return None, None, None
    return (
        cfg.get('ai', 'endpoint', fallback=None),
        cfg.get('ai', 'key', fallback=None),
        cfg.get('ai', 'model', fallback=None),
    )


async def _build_employee(db, emp) -> dict:
    eid = emp["employee_id"]

    confirmed = await db.execute_fetchall("SELECT email FROM emails WHERE employee_id = ?", (eid,))
    potential = await db.execute_fetchall("SELECT email FROM potential_emails WHERE employee_id = ?", (eid,))
    phones_r = await db.execute_fetchall("SELECT phone_number FROM phones WHERE employee_id = ?", (eid,))
    websites_r = await db.execute_fetchall("SELECT website_url FROM websites WHERE employee_id = ?", (eid,))
    githubs_r = await db.execute_fetchall("SELECT github_url FROM githubs WHERE employee_id = ?", (eid,))
    twitters_r = await db.execute_fetchall("SELECT twitter_url FROM twitters WHERE employee_id = ?", (eid,))

    all_email_ids = [r[0] for r in await db.execute_fetchall(
        "SELECT email_id FROM emails WHERE employee_id = ? UNION SELECT email_id FROM potential_emails WHERE employee_id = ?",
        (eid, eid)
    )]

    has_breaches = False
    has_credentials = False
    if all_email_ids:
        placeholders = ','.join('?' * len(all_email_ids))
        br = await db.execute_fetchall(f"SELECT count() FROM breaches WHERE email_id IN ({placeholders})", all_email_ids)
        has_breaches = br[0][0] > 0
        cr = await db.execute_fetchall(f"SELECT count() FROM passwords WHERE email_id IN ({placeholders})", all_email_ids)
        has_credentials = cr[0][0] > 0

    sec = await db.execute_fetchall("SELECT count() FROM secrets_repos WHERE employee_id = ?", (eid,))
    has_secrets = sec[0][0] > 0

    socials = await db.execute_fetchall(
        "SELECT DISTINCT platform, url FROM social_profiles WHERE employee_id = ? ORDER BY platform", (eid,))

    return {
        "employee_id": eid,
        "name": emp["name"],
        "title": emp["title"],
        "profile_photo_url": emp["profile_photo_url"] if "profile_photo_url" in emp.keys() else None,
        "department": emp["department"] if "department" in emp.keys() else None,
        "excluded": emp["excluded"] if "excluded" in emp.keys() else 0,
        "confirmed_emails": [r[0] for r in confirmed],
        "potential_emails": [r[0] for r in potential],
        "phones": [r[0] for r in phones_r],
        "websites": [r[0] for r in websites_r],
        "githubs": [r[0] for r in githubs_r],
        "twitters": [r[0] for r in twitters_r],
        "social_profiles": [{"platform": r[0], "url": r[1]} for r in socials],
        "has_breaches": has_breaches,
        "has_credentials": has_credentials,
        "has_secrets": has_secrets,
    }


@router.get("/employees", response_model=list[EmployeeOut])
async def list_employees(company_id: int = Query(...)):
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM employees WHERE company_id = ? ORDER BY name",
            (company_id,),
        )
        results = []
        for r in rows:
            try:
                results.append(await _build_employee(db, r))
            except Exception as e:
                log.error(f"Error building employee {r['employee_id']}: {e}")
        return results


@router.post("/employees/classify")
async def classify_employees_endpoint(company_id: int = Query(...)):
    endpoint, key, model = _load_ai_config()
    if not all([endpoint, key, model]):
        raise HTTPException(400, "AI not configured. Set up [ai] section in config/tokens.ini or use 'set_ai' in the CLI.")

    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT employee_id, title FROM employees WHERE company_id = ? AND title IS NOT NULL AND title != ''",
            (company_id,),
        )
        if not rows:
            raise HTTPException(400, "No employees with titles found for this company.")

        titles = [r["title"] for r in rows]
        mapping = classify_roles(titles, endpoint, key, model)
        if not mapping:
            raise HTTPException(500, "AI classification failed. Check logs and AI configuration.")

        count = 0
        for row in rows:
            dept = mapping.get(row["title"], "Other")
            await db.execute(
                "UPDATE employees SET department = ? WHERE employee_id = ?",
                (dept, row["employee_id"]),
            )
            count += 1
        await db.commit()
        return {"classified": count}


@router.patch("/employees/bulk-department")
async def bulk_department(body: BulkDepartment):
    async with get_db() as db:
        placeholders = ','.join('?' * len(body.employee_ids))
        await db.execute(
            f"UPDATE employees SET department = ? WHERE employee_id IN ({placeholders})",
            [body.department] + body.employee_ids,
        )
        await db.commit()
        return {"updated": len(body.employee_ids)}


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(employee_id: int, body: EmployeeUpdate):
    async with get_db() as db:
        row = await db.execute_fetchall("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
        if not row:
            raise HTTPException(404, "Employee not found")

        updates = []
        params = []
        if body.department is not None:
            updates.append("department = ?")
            params.append(body.department)
        if body.excluded is not None:
            updates.append("excluded = ?")
            params.append(body.excluded)

        if updates:
            params.append(employee_id)
            await db.execute(f"UPDATE employees SET {', '.join(updates)} WHERE employee_id = ?", params)
            await db.commit()

        row = await db.execute_fetchall("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
        return await _build_employee(db, row[0])


@router.delete("/employees/{employee_id}", status_code=204)
async def delete_employee(employee_id: int):
    async with get_db() as db:
        row = await db.execute_fetchall("SELECT employee_id FROM employees WHERE employee_id = ?", (employee_id,))
        if not row:
            raise HTTPException(404, "Employee not found")

        await db.execute("DELETE FROM secrets_repos WHERE employee_id = ?", (employee_id,))
        for table in ['breaches', 'passwords']:
            await db.execute(f"""
                DELETE FROM {table} WHERE email_id IN (
                    SELECT email_id FROM emails WHERE employee_id = ?
                    UNION SELECT email_id FROM potential_emails WHERE employee_id = ?
                )
            """, (employee_id, employee_id))
        for table in ['emails', 'potential_emails', 'phones', 'websites', 'githubs', 'twitters']:
            await db.execute(f"DELETE FROM {table} WHERE employee_id = ?", (employee_id,))
        await db.execute("DELETE FROM employees WHERE employee_id = ?", (employee_id,))
        await db.commit()
