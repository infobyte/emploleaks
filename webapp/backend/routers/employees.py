from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models import EmployeeOut, EmployeeUpdate, BulkDepartment

router = APIRouter(tags=["employees"])


async def _build_employee(db, emp) -> dict:
    eid = emp["employee_id"]

    confirmed = await db.execute_fetchall("SELECT email FROM emails WHERE employee_id = ?", (eid,))
    potential = await db.execute_fetchall("SELECT email FROM potential_emails WHERE employee_id = ?", (eid,))
    phones_r = await db.execute_fetchall("SELECT phone FROM phones WHERE employee_id = ?", (eid,))
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
            results.append(await _build_employee(db, r))
        return results


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
