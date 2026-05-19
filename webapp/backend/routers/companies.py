from fastapi import APIRouter, HTTPException
from database import get_db
from models import CompanyOut, CompanyCreate

router = APIRouter(tags=["companies"])


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies():
    async with get_db() as db:
        rows = await db.execute_fetchall("SELECT company_id, company_name FROM companies ORDER BY company_name")
        return [dict(r) for r in rows]


@router.post("/companies", response_model=CompanyOut, status_code=201)
async def create_company(body: CompanyCreate):
    async with get_db() as db:
        cur = await db.execute("INSERT INTO companies (company_name) VALUES (?)", (body.name,))
        await db.commit()
        return {"company_id": cur.lastrowid, "company_name": body.name}


@router.delete("/companies/{company_id}", status_code=204)
async def delete_company(company_id: int):
    async with get_db() as db:
        row = await db.execute_fetchall("SELECT company_id FROM companies WHERE company_id = ?", (company_id,))
        if not row:
            raise HTTPException(404, "Company not found")

        await db.execute("""
            DELETE FROM secrets_repos WHERE employee_id IN
            (SELECT employee_id FROM employees WHERE company_id = ?)
        """, (company_id,))
        for table in ['breaches', 'passwords', 'githubs', 'twitters', 'phones', 'websites']:
            await db.execute(f"""
                DELETE FROM {table} WHERE email_id IN (
                    SELECT email_id FROM emails WHERE employee_id IN
                    (SELECT employee_id FROM employees WHERE company_id = ?)
                )
            """, (company_id,))
        await db.execute("DELETE FROM emails WHERE employee_id IN (SELECT employee_id FROM employees WHERE company_id = ?)", (company_id,))
        await db.execute("DELETE FROM potential_emails WHERE employee_id IN (SELECT employee_id FROM employees WHERE company_id = ?)", (company_id,))
        await db.execute("DELETE FROM username_passwords WHERE company_id = ?", (company_id,))
        await db.execute("DELETE FROM employees WHERE company_id = ?", (company_id,))
        await db.execute("DELETE FROM companies WHERE company_id = ?", (company_id,))
        await db.commit()
