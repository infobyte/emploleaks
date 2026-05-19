from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models import EmailOut, EmailCreate

router = APIRouter(tags=["emails"])


@router.get("/employees/{employee_id}/emails", response_model=list[EmailOut])
async def list_emails(employee_id: int):
    async with get_db() as db:
        confirmed = await db.execute_fetchall(
            "SELECT email_id, email FROM emails WHERE employee_id = ?", (employee_id,))
        potential = await db.execute_fetchall(
            "SELECT email_id, email FROM potential_emails WHERE employee_id = ?", (employee_id,))
        return [
            {"email_id": r[0], "email": r[1], "type": "confirmed"} for r in confirmed
        ] + [
            {"email_id": r[0], "email": r[1], "type": "potential"} for r in potential
        ]


@router.post("/employees/{employee_id}/emails", response_model=EmailOut, status_code=201)
async def create_email(employee_id: int, body: EmailCreate):
    async with get_db() as db:
        row = await db.execute_fetchall("SELECT employee_id FROM employees WHERE employee_id = ?", (employee_id,))
        if not row:
            raise HTTPException(404, "Employee not found")

        table = "emails" if body.type == "confirmed" else "potential_emails"
        cur = await db.execute(f"INSERT INTO {table} (email, employee_id) VALUES (?, ?)", (body.email, employee_id))
        await db.commit()
        return {"email_id": cur.lastrowid, "email": body.email, "type": body.type}


@router.patch("/emails/{email_id}")
async def update_email(email_id: int, body: EmailCreate, current_type: str = Query("confirmed")):
    async with get_db() as db:
        old_table = "emails" if current_type == "confirmed" else "potential_emails"
        row = await db.execute_fetchall(f"SELECT email_id, employee_id FROM {old_table} WHERE email_id = ?", (email_id,))
        if not row:
            raise HTTPException(404, "Email not found")

        employee_id = row[0][1]

        if body.type == current_type:
            await db.execute(f"UPDATE {old_table} SET email = ? WHERE email_id = ?", (body.email, email_id))
        else:
            new_table = "emails" if body.type == "confirmed" else "potential_emails"
            await db.execute(f"DELETE FROM {old_table} WHERE email_id = ?", (email_id,))
            await db.execute(f"INSERT INTO {new_table} (email, employee_id) VALUES (?, ?)", (body.email, employee_id))

        await db.commit()
        return {"updated": True}


@router.delete("/emails/{email_id}", status_code=204)
async def delete_email(email_id: int, type: str = Query("confirmed")):
    async with get_db() as db:
        table = "emails" if type == "confirmed" else "potential_emails"
        row = await db.execute_fetchall(f"SELECT email_id FROM {table} WHERE email_id = ?", (email_id,))
        if not row:
            raise HTTPException(404, "Email not found")

        await db.execute(f"DELETE FROM breaches WHERE email_id = ?", (email_id,))
        await db.execute(f"DELETE FROM passwords WHERE email_id = ?", (email_id,))
        await db.execute(f"DELETE FROM social_profiles WHERE email_id = ?", (email_id,))
        await db.execute(f"DELETE FROM {table} WHERE email_id = ?", (email_id,))
        await db.commit()
