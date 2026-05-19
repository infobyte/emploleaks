from fastapi import APIRouter
from database import get_db
from models import DashboardOut, DashboardStats, Finding

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/{company_id}", response_model=DashboardOut)
async def get_dashboard(company_id: int):
    async with get_db() as db:
        emp = await db.execute_fetchall("SELECT count() as c FROM employees WHERE company_id = ? AND (excluded IS NULL OR excluded = 0)", (company_id,))
        total_emp = emp[0][0]

        emails = await db.execute_fetchall("""
            SELECT count(DISTINCT e.employee_id) as c FROM employees e
            LEFT JOIN emails em ON e.employee_id = em.employee_id
            LEFT JOIN potential_emails pe ON e.employee_id = pe.employee_id
            WHERE e.company_id = ? AND (em.email_id IS NOT NULL OR pe.email_id IS NOT NULL)
        """, (company_id,))
        total_emails = emails[0][0]

        br = await db.execute_fetchall("""
            SELECT count() as c FROM breaches b
            INNER JOIN emails em ON b.email_id = em.email_id
            INNER JOIN employees e ON em.employee_id = e.employee_id
            WHERE e.company_id = ?
        """, (company_id,))
        total_breaches = br[0][0]

        creds = await db.execute_fetchall("""
            SELECT count() as c FROM passwords p
            INNER JOIN emails em ON p.email_id = em.email_id
            INNER JOIN employees e ON em.employee_id = e.employee_id
            WHERE e.company_id = ?
        """, (company_id,))
        creds2 = await db.execute_fetchall("""
            SELECT count() as c FROM passwords p
            INNER JOIN potential_emails pe ON p.email_id = pe.email_id
            INNER JOIN employees e ON pe.employee_id = e.employee_id
            WHERE e.company_id = ?
        """, (company_id,))
        total_creds = creds[0][0] + creds2[0][0]

        ucreds = await db.execute_fetchall("SELECT count() as c FROM username_passwords WHERE company_id = ?", (company_id,))
        total_ucreds = ucreds[0][0]

        secs = await db.execute_fetchall("""
            SELECT count() as c FROM secrets_repos
            WHERE employee_id IN (SELECT employee_id FROM employees WHERE company_id = ?)
        """, (company_id,))
        total_secrets = secs[0][0]

        depts = await db.execute_fetchall("""
            SELECT DISTINCT department FROM employees
            WHERE company_id = ? AND department IS NOT NULL AND department != ''
            ORDER BY department
        """, (company_id,))
        dept_list = [r[0] for r in depts]

        findings = []
        if total_creds + total_ucreds > 0:
            findings.append(Finding(
                severity="critical",
                title=f"{total_creds + total_ucreds} leaked credentials found",
                description=f"{total_creds} matched by email, {total_ucreds} matched by username.",
            ))
        if total_secrets > 0:
            findings.append(Finding(
                severity="high",
                title=f"{total_secrets} secrets exposed in repositories",
                description="Secrets found via gitleaks scan in employee repositories.",
            ))
        if total_breaches > 0:
            unique_br = await db.execute_fetchall("""
                SELECT count(DISTINCT b.breach_name) as c FROM breaches b
                INNER JOIN emails em ON b.email_id = em.email_id
                INNER JOIN employees e ON em.employee_id = e.employee_id
                WHERE e.company_id = ?
            """, (company_id,))
            findings.append(Finding(
                severity="medium",
                title=f"{total_breaches} breach records across {unique_br[0][0]} breaches",
                description="Employee emails found in known data breaches via HIBP.",
            ))

        return DashboardOut(
            stats=DashboardStats(
                total_employees=total_emp,
                total_emails=total_emails,
                total_breaches=total_breaches,
                total_credentials=total_creds,
                total_username_credentials=total_ucreds,
                total_secrets=total_secrets,
                departments=dept_list,
            ),
            findings=findings,
        )
