"use client";

import { useEffect, useState } from "react";
import { useCompanyId } from "../layout";
import { api, Breach } from "@/lib/api";
import DataTable from "@/components/DataTable";

export default function BreachesPage() {
  const companyId = useCompanyId();
  const [breaches, setBreaches] = useState<Breach[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    api
      .getBreaches(companyId)
      .then(setBreaches)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [companyId]);

  const columns = [
    { key: "employee_name", label: "Employee" },
    {
      key: "email",
      label: "Email",
      render: (row: Breach) => <span className="text-accent">{row.email}</span>,
    },
    { key: "breach_name", label: "Breach" },
    { key: "breach_date", label: "Date" },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-text-secondary">Loading breaches...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-1">Data Breaches</h1>
        <p className="text-text-secondary text-sm">
          Employee emails found in known data breaches
        </p>
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
