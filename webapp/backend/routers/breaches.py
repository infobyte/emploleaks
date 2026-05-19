from fastapi import APIRouter, Query
from database import get_db
from models import BreachOut

router = APIRouter(tags=["breaches"])


@router.get("/breaches", response_model=list[BreachOut])
async def list_breaches(company_id: int = Query(...)):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT e.name, COALESCE(em.email, pe.email) as email,
                   b.breach_name, b.breach_date
            FROM breaches b
            LEFT JOIN emails em ON b.email_id = em.email_id
            LEFT JOIN employees emp1 ON em.employee_id = emp1.employee_id AND emp1.company_id = ?
            LEFT JOIN potential_emails pe ON b.email_id = pe.email_id
            LEFT JOIN employees emp2 ON pe.employee_id = emp2.employee_id AND emp2.company_id = ?
            INNER JOIN employees e ON e.employee_id = COALESCE(emp1.employee_id, emp2.employee_id)
            WHERE emp1.employee_id IS NOT NULL OR emp2.employee_id IS NOT NULL
            ORDER BY e.name, b.breach_name
        """, (company_id, company_id))
        return [{
            "employee_name": r[0],
            "email": r[1] or "",
            "breach_name": r[2] or "",
            "breach_date": r[3],
        } for r in rows]
