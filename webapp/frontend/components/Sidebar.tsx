"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Company } from "@/lib/api";

const NAV = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/employees", label: "Employees", icon: "👥" },
  { href: "/credentials", label: "Credentials", icon: "🔑" },
  { href: "/secrets", label: "Secrets", icon: "🔒" },
  { href: "/breaches", label: "Breaches", icon: "⚠️" },
];

export default function Sidebar({
  companyId,
  onCompanyChange,
}: {
  companyId: number | null;
  onCompanyChange: (id: number) => void;
}) {
  const pathname = usePathname();
  const [companies, setCompanies] = useState<Company[]>([]);

  useEffect(() => {
    api.getCompanies().then(setCompanies).catch(() => {});
  }, []);

  return (
    <aside className="w-64 bg-bg-secondary border-r border-border flex flex-col min-h-screen shrink-0">
      <div className="p-5 border-b border-border">
        <h1 className="text-xl font-bold tracking-tight">
          <span className="text-accent">Emplo</span>Leaks
        </h1>
        <p className="text-xs text-text-secondary mt-1">OSINT Intelligence Platform</p>
      </div>

      <div className="p-4 border-b border-border">
        <label className="text-xs text-text-secondary uppercase tracking-wider block mb-2">
          Company
        </label>
        <select
          className="w-full bg-bg-tertiary text-text-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
          value={companyId ?? ""}
          onChange={(e) => {
            const v = parseInt(e.target.value);
            if (!isNaN(v)) onCompanyChange(v);
          }}
        >
          <option value="">Select company...</option>
          {companies.map((c) => (
            <option key={c.company_id} value={c.company_id}>
              {c.company_name}
            </option>
          ))}
        </select>
      </div>

      <nav className="flex-1 p-3">
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm mb-1 transition-colors ${
                active
                  ? "bg-accent/15 text-accent font-medium"
                  : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
              }`}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border">
        <p className="text-xs text-text-secondary text-center">EmploLeaks v1.0</p>
      </div>
    </aside>
  );
}
