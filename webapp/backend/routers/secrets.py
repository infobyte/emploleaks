from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models import SecretOut, TriageUpdate

router = APIRouter(tags=["secrets"])


@router.get("/secrets", response_model=list[SecretOut])
async def list_secrets(company_id: int = Query(...)):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT s.secret_id, s.repo_url, s.secret_type, s.secret_value,
                   s.file_path, s.triage_status, e.name as employee_name
            FROM secrets_repos s
            INNER JOIN employees e ON s.employee_id = e.employee_id
            WHERE e.company_id = ?
            ORDER BY e.name, s.secret_type
        """, (company_id,))
        return [{
            "secret_id": r[0],
            "repo_url": r[1],
            "secret_type": r[2],
            "secret_value": r[3],
            "file_path": r[4],
            "triage_status": r[5] or "pending",
            "employee_name": r[6],
        } for r in rows]


@router.get("/employees/{employee_id}/secrets", response_model=list[SecretOut])
async def list_secrets_for_employee(employee_id: int):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT secret_id, repo_url, secret_type, secret_value, file_path, triage_status
            FROM secrets_repos
            WHERE employee_id = ?
            ORDER BY secret_type
        """, (employee_id,))
        return [{
            "secret_id": r[0],
            "repo_url": r[1],
            "secret_type": r[2],
            "secret_value": r[3],
            "file_path": r[4],
            "triage_status": r[5] or "pending",
            "employee_name": None,
        } for r in rows]


@router.patch("/secrets/{secret_id}")
async def update_secret(secret_id: int, body: TriageUpdate):
    async with get_db() as db:
        result = await db.execute("UPDATE secrets_repos SET triage_status = ? WHERE secret_id = ?", (body.triage_status, secret_id))
        if result.rowcount == 0:
            raise HTTPException(404, "Secret not found")
        await db.commit()
        return {"updated": True}
