"use client";

import { useEffect, useState } from "react";
import { useCompanyId } from "./layout";
import { api, DashboardData, SocialProfile } from "@/lib/api";
import StatsCard from "@/components/StatsCard";
import {
  Users,
  Mail,
  AlertTriangle,
  KeyRound,
  ShieldAlert,
  UserCheck,
  Globe,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const companyId = useCompanyId();
  const [data, setData] = useState<DashboardData | null>(null);
  const [socialProfiles, setSocialProfiles] = useState<SocialProfile[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    Promise.all([
      api.getDashboard(companyId),
      api.getSocialProfiles(companyId).catch(() => []),
    ])
      .then(([dashboard, socials]) => {
        setData(dashboard);
        setSocialProfiles(socials);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [companyId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-text-secondary animate-pulse">Loading dashboard...</div>
      </div>
    );
  }

  if (!data) {
    return <p className="text-text-secondary text-sm">Failed to load dashboard.</p>;
  }

  const { stats, findings } = data;

  const severityIcon: Record<string, string> = {
    critical: "bg-critical/10 border-critical/30 text-critical",
    high: "bg-danger/10 border-danger/30 text-danger",
    medium: "bg-warning/10 border-warning/30 text-warning",
    low: "bg-accent/10 border-accent/30 text-accent",
  };

  const platformCounts = socialProfiles.reduce((acc, sp) => {
    acc[sp.platform] = (acc[sp.platform] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-text-primary">Dashboard</h1>
        <p className="text-sm text-text-secondary mt-0.5">OSINT intelligence overview</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatsCard label="Employees" value={stats.total_employees} Icon={Users} color="accent" />
        <StatsCard label="Emails" value={stats.total_emails} Icon={Mail} color="accent" />
        <StatsCard label="Breaches" value={stats.total_breaches} Icon={AlertTriangle} color="warning" />
        <StatsCard label="Email Creds" value={stats.total_credentials} Icon={KeyRound} color="danger" />
        <StatsCard label="User Creds" value={stats.total_username_credentials} Icon={UserCheck} color="critical" />
        <StatsCard label="Secrets" value={stats.total_secrets} Icon={ShieldAlert} color="danger" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {findings.length > 0 && (
          <div className="bg-bg-secondary border border-border rounded-xl p-4">
            <h2 className="text-sm font-medium text-text-primary mb-3">Key Findings</h2>
            <div className="space-y-2">
              {findings.map((f, i) => (
                <div
                  key={i}
                  className={`border-l-2 rounded-r-lg px-3 py-2 text-xs ${
                    severityIcon[f.severity] || severityIcon.low
                  }`}
                >
                  <span className="font-semibold uppercase text-[10px] tracking-wider">{f.severity}</span>
                  <span className="mx-1.5 text-text-tertiary">·</span>
                  <span className="font-medium text-text-primary">{f.title}</span>
                  <p className="text-text-secondary mt-0.5">{f.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-4">
          {stats.departments.length > 0 && (
            <div className="bg-bg-secondary border border-border rounded-xl p-4">
              <h2 className="text-sm font-medium text-text-primary mb-3">Departments</h2>
              <div className="flex flex-wrap gap-1.5">
                {stats.departments.map((d) => (
                  <span
                    key={d}
                    className="bg-bg-tertiary text-text-primary px-2.5 py-1 rounded-md text-xs"
                  >
                    {d}
                  </span>
                ))}
              </div>
            </div>
          )}

          {Object.keys(platformCounts).length > 0 && (
            <div className="bg-bg-secondary border border-border rounded-xl p-4">
              <h2 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
                <Globe className="w-4 h-4 text-text-secondary" />
                Social Profiles Found
              </h2>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(platformCounts)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 8)
                  .map(([platform, count]) => (
                    <div key={platform} className="flex items-center justify-between px-2 py-1.5 bg-bg-tertiary rounded-md">
                      <span className="text-xs text-text-primary capitalize">{platform}</span>
                      <span className="text-xs text-text-secondary font-medium">{count}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-bg-secondary border border-border rounded-xl p-4">
        <h2 className="text-sm font-medium text-text-primary mb-3">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[
            { href: "/employees", label: "Manage Employees", Icon: Users },
            { href: "/credentials", label: "Triage Credentials", Icon: KeyRound },
            { href: "/secrets", label: "Review Secrets", Icon: ShieldAlert },
            { href: "/breaches", label: "View Breaches", Icon: AlertTriangle },
          ].map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-bg-tertiary hover:bg-bg-hover text-sm text-text-primary transition-colors group"
            >
              <action.Icon className="w-4 h-4 text-text-secondary" />
              <span className="flex-1 text-xs">{action.label}</span>
              <ArrowRight className="w-3 h-3 text-text-tertiary group-hover:text-text-secondary transition-colors" />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
