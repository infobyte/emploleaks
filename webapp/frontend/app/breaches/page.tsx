"use client";

import { useEffect, useState } from "react";
import { useCompanyId } from "../layout";
import { api, Breach } from "@/lib/api";
import DataTable from "@/components/DataTable";
import { AlertTriangle } from "lucide-react";

export default function BreachesPage() {
  const companyId = useCompanyId();
  const [breaches, setBreaches] = useState<Breach[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    api.getBreaches(companyId).then(setBreaches).catch(() => {}).finally(() => setLoading(false));
  }, [companyId]);

  const columns = [
    { key: "employee_name", label: "Employee" },
    {
      key: "email", label: "Email",
      render: (row: Breach) => <span className="text-accent text-xs">{row.email}</span>,
    },
    { key: "breach_name", label: "Breach", render: (row: Breach) => (
      <span className="text-xs font-medium">{row.breach_name}</span>
    )},
    { key: "breach_date", label: "Date", render: (row: Breach) => (
      <span className="text-xs text-text-secondary">{row.breach_date || "—"}</span>
    )},
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-text-secondary animate-pulse">Loading breaches...</div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-text-secondary" />
          Data Breaches
        </h1>
        <p className="text-sm text-text-secondary mt-0.5">Employee emails found in known data breaches</p>
      </div>

      <DataTable
        columns={columns}
        data={breaches}
        keyField="email"
        searchKeys={["employee_name", "email", "breach_name"]}
        emptyMessage="No breach records found"
      />
    </div>
  );
}
