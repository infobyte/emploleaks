from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models import CredentialOut, TriageUpdate, BulkTriage

router = APIRouter(tags=["credentials"])


@router.get("/credentials", response_model=list[CredentialOut])
async def list_credentials(company_id: int = Query(...)):
    async with get_db() as db:
        email_creds = await db.execute_fetchall("""
            SELECT p.password_id, p.password, p.breach_context, p.triage_status,
                   COALESCE(em.email, pe.email) as email,
                   COALESCE(emp1.name, emp2.name) as employee_name
            FROM passwords p
            LEFT JOIN emails em ON p.email_id = em.email_id
            LEFT JOIN employees emp1 ON em.employee_id = emp1.employee_id AND emp1.company_id = ?
            LEFT JOIN potential_emails pe ON p.email_id = pe.email_id
            LEFT JOIN employees emp2 ON pe.employee_id = emp2.employee_id AND emp2.company_id = ?
            WHERE emp1.employee_id IS NOT NULL OR emp2.employee_id IS NOT NULL
            ORDER BY employee_name, email
        """, (company_id, company_id))

        username_creds = await db.execute_fetchall("""
            SELECT password_id, username, password, breach_context, triage_status
            FROM username_passwords
            WHERE company_id = ?
            ORDER BY username
        """, (company_id,))

        results = []
        for r in email_creds:
            results.append({
                "password_id": r[0],
                "source_type": "email",
                "identifier": r[4] or "",
                "password": r[1] or "",
                "breach_context": r[2],
                "triage_status": r[3] or "pending",
                "employee_name": r[5],
            })
        for r in username_creds:
            results.append({
                "password_id": r[0],
                "source_type": "username",
                "identifier": r[1] or "",
                "password": r[2] or "",
                "breach_context": r[3],
                "triage_status": r[4] or "pending",
                "employee_name": None,
            })
        return results


@router.patch("/credentials/bulk-triage")
async def bulk_triage(body: BulkTriage):
    async with get_db() as db:
        table = "username_passwords" if body.source_type == "username" else "passwords"
        placeholders = ','.join('?' * len(body.ids))
        await db.execute(
            f"UPDATE {table} SET triage_status = ? WHERE password_id IN ({placeholders})",
            [body.triage_status] + body.ids,
        )
        await db.commit()
        return {"updated": len(body.ids)}


@router.patch("/credentials/{password_id}")
async def update_credential(password_id: int, body: TriageUpdate, source_type: str = Query("email")):
    async with get_db() as db:
        table = "username_passwords" if source_type == "username" else "passwords"
        result = await db.execute(f"UPDATE {table} SET triage_status = ? WHERE password_id = ?", (body.triage_status, password_id))
        if result.rowcount == 0:
            raise HTTPException(404, "Credential not found")
        await db.commit()
        return {"updated": True}
