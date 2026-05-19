from pydantic import BaseModel
from typing import Optional


class CompanyOut(BaseModel):
    company_id: int
    company_name: str


class CompanyCreate(BaseModel):
    name: str


class DashboardStats(BaseModel):
    total_employees: int
    total_emails: int
    total_breaches: int
    total_credentials: int
    total_username_credentials: int
    total_secrets: int
    departments: list[str]


class Finding(BaseModel):
    severity: str
    title: str
    description: str


class DashboardOut(BaseModel):
    stats: DashboardStats
    findings: list[Finding]


class EmployeeOut(BaseModel):
    employee_id: int
    name: Optional[str] = None
    title: Optional[str] = None
    profile_photo_url: Optional[str] = None
    department: Optional[str] = None
    excluded: int = 0
    confirmed_emails: list[str] = []
    potential_emails: list[str] = []
    phones: list[str] = []
    websites: list[str] = []
    githubs: list[str] = []
    twitters: list[str] = []
    has_breaches: bool = False
    has_credentials: bool = False
    has_secrets: bool = False


class EmployeeUpdate(BaseModel):
    department: Optional[str] = None
    excluded: Optional[int] = None


class BulkDepartment(BaseModel):
    employee_ids: list[int]
    department: str


class CredentialOut(BaseModel):
    password_id: int
    source_type: str  # "email" or "username"
    identifier: str
    password: str
    breach_context: Optional[str] = None
    triage_status: str = "pending"
    employee_name: Optional[str] = None


class TriageUpdate(BaseModel):
    triage_status: str  # pending, verified, not_working, false_positive


class BulkTriage(BaseModel):
    ids: list[int]
    source_type: str  # "email" or "username"
    triage_status: str


class SecretOut(BaseModel):
    secret_id: int
    employee_name: Optional[str] = None
    repo_url: str
    secret_type: str
    secret_value: str
    file_path: Optional[str] = None
    triage_status: str = "pending"


class BreachOut(BaseModel):
    employee_name: Optional[str] = None
    email: str
    breach_name: str
    breach_date: Optional[str] = None
