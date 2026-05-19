"use client";

import { useEffect, useState, useMemo } from "react";
import { useCompanyId } from "../layout";
import { api, Secret } from "@/lib/api";
import DataTable from "@/components/DataTable";
import TriageBadge from "@/components/TriageBadge";

export default function SecretsPage() {
  const companyId = useCompanyId();
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    api
      .getSecrets(companyId)
      .then(setSecrets)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [companyId]);

  const filtered = useMemo(() => {
    if (filterStatus === "all") return secrets;
    return secrets.filter((s) => s.triage_status === filterStatus);
  }, [secrets, filterStatus]);

  const handleTriageChange = async (id: number, status: string) => {
    try {
      await api.updateSecretTriage(id, status);
      setSecrets((prev) =>
        prev.map((s) => (s.secret_id === id ? { ...s, triage_status: status } : s))
      );
    } catch {}
  };

  const columns = [
    { key: "employee_name", label: "Employee" },
    { key: "secret_type", label: "Type" },
    {
      key: "secret_value",
      label: "Value",
      render: (row: Secret) => (
        <code className="text-xs bg-bg-tertiary px-2 py-1 rounded font-mono max-w-[200px] truncate inline-block">
          {row.secret_value.length > 40
            ? row.secret_value.substring(0, 40) + "..."
            : row.secret_value}
        </code>
      ),
    },
    {
      key: "repo_url",
      label: "Repository",
      render: (row: Secret) => (
        <a
          href={row.repo_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent hover:text-accent-hover text-xs underline"
        >
          {row.repo_url.replace(/^https?:\/\/(www\.)?/, "").substring(0, 40)}
        </a>
      ),
    },
    { key: "file_path", label: "File" },
    {
      key: "triage_status",
      label: "Status",
      render: (row: Secret) => (
        <TriageBadge
          status={row.triage_status}
          onChange={(s) => handleTriageChange(row.secret_id, s)}
        />
      ),
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-text-secondary">Loading secrets...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-1">Secret Triage</h1>
        <p className="text-text-secondary text-sm">
          Review exposed secrets found in employee repositories
        </p>
      </div>

      <div className="flex items-center gap-4">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="bg-bg-tertiary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="verified">Verified</option>
          <option value="not_working">Not Working</option>
          <option value="false_positive">False Positive</option>
        </select>
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
