import os
import sys
from fastapi import APIRouter, HTTPException, Query
from database import get_db
from models import DomainOut, DomainCreate, SubdomainOut

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, PROJECT_ROOT)
from utils.discovery import discover_all

router = APIRouter(tags=["discovery"])


@router.get("/domains", response_model=list[DomainOut])
async def list_domains(company_id: int = Query(...)):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT d.domain_id, d.domain,
                   (SELECT COUNT(*) FROM subdomains s WHERE s.domain_id = d.domain_id) as sub_count
            FROM domains d
            WHERE d.company_id = ?
            ORDER BY d.domain
        """, (company_id,))
        return [{"domain_id": r[0], "domain": r[1], "subdomain_count": r[2]} for r in rows]


@router.post("/domains", response_model=DomainOut)
async def add_domain(body: DomainCreate):
    async with get_db() as db:
        try:
            cursor = await db.execute(
                "INSERT INTO domains (domain, company_id) VALUES (?, ?)",
                (body.domain.strip().lower(), body.company_id)
            )
            await db.commit()
            return {"domain_id": cursor.lastrowid, "domain": body.domain.strip().lower(), "subdomain_count": 0}
        except Exception as e:
            if "UNIQUE" in str(e):
                raise HTTPException(409, "Domain already registered for this company")
            raise HTTPException(500, str(e))


@router.delete("/domains/{domain_id}")
async def delete_domain(domain_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM subdomains WHERE domain_id = ?", (domain_id,))
        await db.execute("DELETE FROM domains WHERE domain_id = ?", (domain_id,))
        await db.commit()
        return {"ok": True}


@router.get("/subdomains", response_model=list[SubdomainOut])
async def list_subdomains(company_id: int = Query(...)):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT s.subdomain_id, s.subdomain, s.ip_address, s.source, s.first_seen, d.domain
            FROM subdomains s
            INNER JOIN domains d ON s.domain_id = d.domain_id
            WHERE d.company_id = ?
            ORDER BY d.domain, s.subdomain
        """, (company_id,))
        return [{
            "subdomain_id": r[0], "subdomain": r[1], "ip_address": r[2],
            "source": r[3], "first_seen": r[4], "domain": r[5],
        } for r in rows]


@router.post("/discover")
async def trigger_discovery(company_id: int = Query(...)):
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT domain_id, domain FROM domains WHERE company_id = ?",
            (company_id,)
        )
        if not rows:
            raise HTTPException(400, "No domains registered for this company.")

        total_new = 0
        total_found = 0
        for r in rows:
            domain_id, domain = r[0], r[1]
            results = discover_all(domain)
            total_found += len(results)

            for entry in results:
                try:
                    await db.execute("""
                        INSERT INTO subdomains (subdomain, domain_id, source, ip_address)
                        VALUES (?, ?, ?, ?)
                    """, (entry['subdomain'], domain_id, entry['source'], entry['ip']))
                    total_new += 1
                except Exception as e:
                    if "UNIQUE" in str(e):
                        await db.execute("""
                            UPDATE subdomains SET ip_address = ?, source = ?
                            WHERE subdomain = ? AND domain_id = ?
                        """, (entry['ip'], entry['source'], entry['subdomain'], domain_id))

        await db.commit()
        return {"total_found": total_found, "new_subdomains": total_new, "domains_scanned": len(rows)}
