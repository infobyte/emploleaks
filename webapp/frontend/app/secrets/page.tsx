"use client";

import { useEffect, useState, useMemo } from "react";
import { useCompanyId } from "../layout";
import { api, Secret } from "@/lib/api";
import DataTable from "@/components/DataTable";
import TriageBadge from "@/components/TriageBadge";
import { ShieldAlert, Filter, ExternalLink } from "lucide-react";

export default function SecretsPage() {
  const companyId = useCompanyId();
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    api.getSecrets(companyId).then(setSecrets).catch(() => {}).finally(() => setLoading(false));
  }, [companyId]);

  const filtered = useMemo(() => {
    if (filterStatus === "all") return secrets;
    return secrets.filter((s) => s.triage_status === filterStatus);
  }, [secrets, filterStatus]);

  const handleTriageChange = async (id: number, status: string) => {
    try {
      await api.updateSecretTriage(id, status);
      setSecrets((prev) => prev.map((s) => (s.secret_id === id ? { ...s, triage_status: status } : s)));
    } catch { /* ignore */ }
  };

  const columns = [
    { key: "employee_name", label: "Employee" },
    { key: "secret_type", label: "Type", render: (row: Secret) => (
      <span className="text-xs bg-bg-tertiary px-2 py-0.5 rounded">{row.secret_type}</span>
    )},
    {
      key: "secret_value", label: "Value",
      render: (row: Secret) => (
        <code className="text-xs bg-bg-tertiary px-2 py-0.5 rounded font-mono max-w-[200px] truncate inline-block">
          {row.secret_value.length > 40 ? row.secret_value.substring(0, 40) + "..." : row.secret_value}
        </code>
      ),
    },
    {
      key: "repo_url", label: "Repository",
      render: (row: Secret) => (
        <a href={row.repo_url} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-accent hover:text-accent-hover text-xs">
          {row.repo_url.replace(/^https?:\/\/(www\.)?/, "").substring(0, 30)}
          <ExternalLink className="w-3 h-3" />
        </a>
      ),
    },
    { key: "file_path", label: "File", render: (row: Secret) => (
      <span className="text-xs text-text-secondary font-mono">{row.file_path}</span>
    )},
    {
      key: "triage_status", label: "Status",
      render: (row: Secret) => (
        <TriageBadge status={row.triage_status} onChange={(s) => handleTriageChange(row.secret_id, s)} />
      ),
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-text-secondary animate-pulse">Loading secrets...</div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-text-secondary" />
          Secrets
        </h1>
        <p className="text-sm text-text-secondary mt-0.5">Exposed secrets found in employee repositories</p>
      </div>

      <div className="flex items-center gap-3">
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
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        keyField="secret_id"
        searchKeys={["employee_name", "secret_type", "repo_url", "file_path"]}
        emptyMessage="No secrets found"
      />
    </div>
  );
}
