from fastapi import APIRouter, HTTPException
from database import get_db
from models import CompanyOut, CompanyCreate

router = APIRouter(tags=["companies"])


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies():
    async with get_db() as db:
        rows = await db.execute_fetchall("SELECT company_id, company_name, company_logo_url FROM companies ORDER BY company_name")
        return [{"company_id": r[0], "company_name": r[1], "company_logo_url": r[2]} for r in rows]


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

        # Delete subdomains via domains
        await db.execute("DELETE FROM subdomains WHERE domain_id IN (SELECT domain_id FROM domains WHERE company_id = ?)", (company_id,))
        await db.execute("DELETE FROM domains WHERE company_id = ?", (company_id,))

        # Delete usernames and social_profiles via employees
        await db.execute("DELETE FROM usernames WHERE employee_id IN (SELECT employee_id FROM employees WHERE company_id = ?)", (company_id,))
        await db.execute("DELETE FROM social_profiles WHERE employee_id IN (SELECT employee_id FROM employees WHERE company_id = ?)", (company_id,))

        await db.execute("""
            DELETE FROM secrets_repos WHERE employee_id IN
            (SELECT employee_id FROM employees WHERE company_id = ?)
        """, (company_id,))
        for table in ['breaches', 'passwords']:
            await db.execute(f"""
                DELETE FROM {table} WHERE email_id IN (
                    SELECT email_id FROM emails WHERE employee_id IN
                    (SELECT employee_id FROM employees WHERE company_id = ?)
                )
            """, (company_id,))
        for table in ['githubs', 'twitters', 'phones', 'websites']:
            await db.execute(f"DELETE FROM {table} WHERE employee_id IN (SELECT employee_id FROM employees WHERE company_id = ?)", (company_id,))
        await db.execute("DELETE FROM emails WHERE employee_id IN (SELECT employee_id FROM employees WHERE company_id = ?)", (company_id,))
        await db.execute("DELETE FROM potential_emails WHERE employee_id IN (SELECT employee_id FROM employees WHERE company_id = ?)", (company_id,))
        await db.execute("DELETE FROM username_passwords WHERE company_id = ?", (company_id,))
        await db.execute("DELETE FROM employees WHERE company_id = ?", (company_id,))
        await db.execute("DELETE FROM companies WHERE company_id = ?", (company_id,))
        await db.commit()
