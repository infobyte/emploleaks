import os
import sys
from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models import SocialProfileOut

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, PROJECT_ROOT)
from utils.email_lookup import lookup_email_sync

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

        total_found = 0
        for r in rows:
            email_id, email, employee_id = r[0], r[1], r[2]
            results = lookup_email_sync(email)
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
