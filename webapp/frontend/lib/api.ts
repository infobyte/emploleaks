const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8421/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface Company {
  company_id: number;
  company_name: string;
  company_logo_url?: string | null;
}

export interface DashboardStats {
  total_employees: number;
  total_emails: number;
  total_breaches: number;
  total_credentials: number;
  total_username_credentials: number;
  total_secrets: number;
  departments: string[];
}

export interface Finding {
  severity: string;
  title: string;
  description: string;
}

export interface DashboardData {
  stats: DashboardStats;
  findings: Finding[];
}

export interface EmailEntry {
  email_id: number;
  email: string;
  type: "confirmed" | "potential";
}

export interface SocialProfile {
  profile_id: number;
  platform: string;
  url: string | null;
  email_recovery: string | null;
  phone_recovery: string | null;
  employee_id: number;
  employee_name: string | null;
  source_email: string | null;
}

export interface EmployeeSocialProfile {
  platform: string;
  url: string | null;
}

export interface Employee {
  employee_id: number;
  name: string | null;
  title: string | null;
  profile_photo_url: string | null;
  department: string | null;
  excluded: number;
  confirmed_emails: string[];
  potential_emails: string[];
  phones: string[];
  websites: string[];
  githubs: string[];
  twitters: string[];
  social_profiles: EmployeeSocialProfile[];
  has_breaches: boolean;
  has_credentials: boolean;
  has_secrets: boolean;
}

export interface Credential {
  password_id: number;
  source_type: "email" | "username";
  identifier: string;
  password: string;
  url: string | null;
  breach_context: string | null;
  triage_status: string;
  employee_name: string | null;
}

export interface Secret {
  secret_id: number;
  employee_name: string | null;
  repo_url: string;
  secret_type: string;
  secret_value: string;
  file_path: string | null;
  triage_status: string;
}

export interface Breach {
  employee_name: string | null;
  email: string;
  breach_name: string;
  breach_date: string | null;
}

export interface Domain {
  domain_id: number;
  domain: string;
  subdomain_count: number;
}

export interface Subdomain {
  subdomain_id: number;
  subdomain: string;
  ip_address: string | null;
  source: string | null;
  first_seen: string | null;
  domain: string | null;
}

export interface Username {
  username_id: number;
  username: string;
  employee_id: number;
  employee_name: string | null;
  source: string;
}

export const api = {
  getCompanies: () => request<Company[]>("/companies"),
  createCompany: (name: string) => request<Company>("/companies", { method: "POST", body: JSON.stringify({ name }) }),
  deleteCompany: (id: number) => request<void>(`/companies/${id}`, { method: "DELETE" }),

  getDashboard: (companyId: number) => request<DashboardData>(`/dashboard/${companyId}`),

  getEmployees: (companyId: number) => request<Employee[]>(`/employees?company_id=${companyId}`),
  updateEmployee: (id: number, data: { department?: string; excluded?: number }) =>
    request<Employee>(`/employees/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  bulkDepartment: (employee_ids: number[], department: string) =>
    request<{ updated: number }>("/employees/bulk-department", {
      method: "PATCH",
      body: JSON.stringify({ employee_ids, department }),
    }),
  deleteEmployee: (id: number) => request<void>(`/employees/${id}`, { method: "DELETE" }),
  classifyEmployees: (companyId: number) =>
    request<{ classified: number }>(`/employees/classify?company_id=${companyId}`, { method: "POST" }),

  getEmployeeEmails: (employeeId: number) => request<EmailEntry[]>(`/employees/${employeeId}/emails`),
  createEmail: (employeeId: number, email: string, type: string) =>
    request<EmailEntry>(`/employees/${employeeId}/emails`, {
      method: "POST",
      body: JSON.stringify({ email, type }),
    }),
  updateEmail: (emailId: number, email: string, type: string, currentType: string) =>
    request<{ updated: boolean }>(`/emails/${emailId}?current_type=${currentType}`, {
      method: "PATCH",
      body: JSON.stringify({ email, type }),
    }),
  deleteEmail: (emailId: number, type: string) =>
    request<void>(`/emails/${emailId}?type=${type}`, { method: "DELETE" }),

  getSocialProfiles: (companyId: number) => request<SocialProfile[]>(`/social-profiles?company_id=${companyId}`),
  lookupSocialProfiles: (companyId: number) =>
    request<{ found: number; emails_checked: number }>(`/social-profiles/lookup?company_id=${companyId}`, {
      method: "POST",
    }),

  getCredentials: (companyId: number) => request<Credential[]>(`/credentials?company_id=${companyId}`),
  getEmployeeCredentials: (employeeId: number) =>
    request<Credential[]>(`/employees/${employeeId}/credentials`),
  getEmployeeSecrets: (employeeId: number) =>
    request<Secret[]>(`/employees/${employeeId}/secrets`),
  updateCredentialTriage: (id: number, sourceType: string, triage_status: string) =>
    request<{ updated: boolean }>(`/credentials/${id}?source_type=${sourceType}`, {
      method: "PATCH",
      body: JSON.stringify({ triage_status }),
    }),
  bulkCredentialTriage: (ids: number[], source_type: string, triage_status: string) =>
    request<{ updated: number }>("/credentials/bulk-triage", {
      method: "PATCH",
      body: JSON.stringify({ ids, source_type, triage_status }),
    }),

  getSecrets: (companyId: number) => request<Secret[]>(`/secrets?company_id=${companyId}`),
  updateSecretTriage: (id: number, triage_status: string) =>
    request<{ updated: boolean }>(`/secrets/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ triage_status }),
    }),

  getBreaches: (companyId: number) => request<Breach[]>(`/breaches?company_id=${companyId}`),

  getDomains: (companyId: number) => request<Domain[]>(`/domains?company_id=${companyId}`),
  addDomain: (domain: string, companyId: number) =>
    request<Domain>("/domains", { method: "POST", body: JSON.stringify({ domain, company_id: companyId }) }),
  deleteDomain: (domainId: number) => request<void>(`/domains/${domainId}`, { method: "DELETE" }),
  getSubdomains: (companyId: number) => request<Subdomain[]>(`/subdomains?company_id=${companyId}`),
  triggerDiscovery: (companyId: number) =>
    request<{ total_found: number; new_subdomains: number; domains_scanned: number }>(
      `/discover?company_id=${companyId}`, { method: "POST" }
    ),

  getUsernames: (employeeId: number) => request<Username[]>(`/employees/${employeeId}/usernames`),
  addUsername: (employeeId: number, username: string) =>
    request<Username>(`/employees/${employeeId}/usernames`, {
      method: "POST", body: JSON.stringify({ username }),
    }),
  deleteUsername: (usernameId: number) => request<void>(`/usernames/${usernameId}`, { method: "DELETE" }),
  lookupProfiles: (companyId: number) =>
    request<{ found: number; usernames_checked: number }>(
      `/social-profiles/lookup-usernames?company_id=${companyId}`, { method: "POST" }
    ),
};
