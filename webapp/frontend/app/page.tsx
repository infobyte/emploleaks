"use client";

import { useEffect, useState } from "react";
import { useCompanyId } from "./layout";
import { api, DashboardData } from "@/lib/api";
import StatsCard from "@/components/StatsCard";

export default function DashboardPage() {
  const companyId = useCompanyId();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    api
      .getDashboard(companyId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [companyId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-text-secondary">Loading dashboard...</div>
      </div>
    );
  }

  if (!data) {
    return <p className="text-text-secondary">Failed to load dashboard.</p>;
  }

  const { stats, findings } = data;

  const severityColors: Record<string, string> = {
    critical: "border-critical bg-critical/10 text-critical",
    high: "border-danger bg-danger/10 text-danger",
    medium: "border-warning bg-warning/10 text-warning",
    low: "border-accent bg-accent/10 text-accent",
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold mb-1">Dashboard</h1>
        <p className="text-text-secondary text-sm">Overview of OSINT intelligence gathered</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatsCard label="Employees" value={stats.total_employees} icon="👥" color="accent" />
        <StatsCard label="Emails" value={stats.total_emails} icon="📧" color="accent" />
        <StatsCard label="Breaches" value={stats.total_breaches} icon="⚠️" color="warning" />
        <StatsCard
          label="Email Creds"
          value={stats.total_credentials}
          icon="🔑"
          color="danger"
        />
        <StatsCard
          label="User Creds"
          value={stats.total_username_credentials}
          icon="🔐"
          color="critical"
        />
        <StatsCard label="Secrets" value={stats.total_secrets} icon="🔒" color="danger" />
      </div>

      {findings.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Key Findings</h2>
          <div className="space-y-3">
            {findings.map((f, i) => (
              <div
                key={i}
                className={`border-l-4 rounded-r-xl p-4 bg-bg-secondary ${
                  severityColors[f.severity] || severityColors.low
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold uppercase">{f.severity}</span>
                  <span className="text-sm font-semibold text-text-primary">{f.title}</span>
                </div>
                <p className="text-sm text-text-secondary">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {stats.departments.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Departments</h2>
          <div className="flex flex-wrap gap-2">
            {stats.departments.map((d) => (
              <span
                key={d}
                className="bg-bg-tertiary border border-border text-text-primary px-3 py-1.5 rounded-full text-sm"
              >
                {d}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
