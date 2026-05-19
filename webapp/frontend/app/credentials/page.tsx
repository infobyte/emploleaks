"use client";

import { useEffect, useState, useMemo } from "react";
import { useCompanyId } from "../layout";
import { api, Credential } from "@/lib/api";
import DataTable from "@/components/DataTable";
import TriageBadge from "@/components/TriageBadge";
import { KeyRound, Filter, CheckCircle, XCircle, Ban } from "lucide-react";

export default function CredentialsPage() {
  const companyId = useCompanyId();
  const [creds, setCreds] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"email" | "username">("email");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    api.getCredentials(companyId).then(setCreds).catch(() => {}).finally(() => setLoading(false));
  }, [companyId]);

  const filtered = useMemo(() => {
    let rows = creds.filter((c) => c.source_type === tab);
    if (filterStatus !== "all") rows = rows.filter((c) => c.triage_status === filterStatus);
    return rows;
  }, [creds, tab, filterStatus]);

  const handleTriageChange = async (id: number, sourceType: string, status: string) => {
    try {
      await api.updateCredentialTriage(id, sourceType, status);
      setCreds((prev) =>
        prev.map((c) => c.password_id === id && c.source_type === sourceType ? { ...c, triage_status: status } : c)
      );
    } catch { /* ignore */ }
  };

  const handleBulkTriage = async (status: string) => {
    if (selected.size === 0) return;
    try {
      await api.bulkCredentialTriage(Array.from(selected), tab, status);
      setCreds((prev) =>
        prev.map((c) => selected.has(c.password_id) && c.source_type === tab ? { ...c, triage_status: status } : c)
      );
      setSelected(new Set());
    } catch { /* ignore */ }
  };

  const emailCount = creds.filter((c) => c.source_type === "email").length;
  const usernameCount = creds.filter((c) => c.source_type === "username").length;

  const renderUrl = (row: Credential) =>
    row.url ? (
      <span className="text-xs text-text-secondary font-mono truncate max-w-[260px] inline-block" title={row.url}>
        {row.url}
      </span>
    ) : (
      <span className="text-xs text-text-tertiary">—</span>
    );

  const columns =
    tab === "email"
      ? [
          { key: "employee_name", label: "Employee" },
          { key: "identifier", label: "Email" },
          {
            key: "password", label: "Password",
            render: (row: Credential) => (
              <code className="text-xs bg-bg-tertiary px-2 py-0.5 rounded font-mono">{row.password}</code>
            ),
          },
          { key: "url", label: "URL", render: renderUrl },
          { key: "breach_context", label: "Source" },
          {
            key: "triage_status", label: "Status",
            render: (row: Credential) => (
              <TriageBadge status={row.triage_status} onChange={(s) => handleTriageChange(row.password_id, row.source_type, s)} />
            ),
          },
        ]
      : [
          {
            key: "identifier", label: "Username",
            render: (row: Credential) => (
              <code className="text-xs bg-bg-tertiary px-2 py-0.5 rounded font-mono">{row.identifier}</code>
            ),
          },
          {
            key: "password", label: "Password",
            render: (row: Credential) => (
              <code className="text-xs bg-bg-tertiary px-2 py-0.5 rounded font-mono">{row.password}</code>
            ),
          },
          { key: "url", label: "URL", render: renderUrl },
          { key: "breach_context", label: "Source" },
          {
            key: "triage_status", label: "Status",
            render: (row: Credential) => (
              <TriageBadge status={row.triage_status} onChange={(s) => handleTriageChange(row.password_id, row.source_type, s)} />
            ),
          },
        ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-text-secondary animate-pulse">Loading credentials...</div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
          <KeyRound className="w-5 h-5 text-text-secondary" />
          Credentials
        </h1>
        <p className="text-sm text-text-secondary mt-0.5">Review and classify leaked credentials</p>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex bg-bg-secondary border border-border rounded-lg overflow-hidden">
          <button
            onClick={() => { setTab("email"); setSelected(new Set()); }}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === "email" ? "bg-accent text-white" : "text-text-secondary hover:text-text-primary"
            }`}
          >
            By Email ({emailCount})
          </button>
          <button
            onClick={() => { setTab("username"); setSelected(new Set()); }}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === "username" ? "bg-accent text-white" : "text-text-secondary hover:text-text-primary"
            }`}
          >
            By Username ({usernameCount})
          </button>
        </div>

        <div className="flex items-center gap-1.5">
          <Filter className="w-3.5 h-3.5 text-text-tertiary" />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-bg-secondary border border-border rounded-lg px-2.5 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent transition-colors"
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="verified">Verified</option>
            <option value="not_working">Not Working</option>
            <option value="false_positive">False Positive</option>
          </select>
        </div>

        {selected.size > 0 && (
          <div className="flex items-center gap-2 ml-auto bg-bg-secondary border border-border rounded-lg px-3 py-1.5">
            <span className="text-xs text-text-secondary">{selected.size} selected</span>
            <button onClick={() => handleBulkTriage("verified")} className="inline-flex items-center gap-1 text-success text-xs hover:underline">
              <CheckCircle className="w-3 h-3" /> Verified
            </button>
            <button onClick={() => handleBulkTriage("not_working")} className="inline-flex items-center gap-1 text-text-secondary text-xs hover:underline">
              <XCircle className="w-3 h-3" /> Not Working
            </button>
            <button onClick={() => handleBulkTriage("false_positive")} className="inline-flex items-center gap-1 text-danger text-xs hover:underline">
              <Ban className="w-3 h-3" /> False Positive
            </button>
          </div>
        )}
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        keyField="password_id"
        searchKeys={["identifier", "password", "employee_name", "breach_context", "url"]}
        emptyMessage="No credentials found"
        selectable
        selectedIds={selected}
        onSelectionChange={setSelected}
      />
    </div>
  );
}
