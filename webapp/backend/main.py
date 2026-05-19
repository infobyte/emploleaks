from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import get_db, ensure_columns
from routers import companies, dashboard, employees, credentials, secrets, breaches, emails, social


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with get_db() as db:
        await ensure_columns(db)
    yield


app = FastAPI(title="EmploLeaks API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(credentials.router, prefix="/api")
app.include_router(secrets.router, prefix="/api")
app.include_router(breaches.router, prefix="/api")
app.include_router(emails.router, prefix="/api")
app.include_router(social.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
