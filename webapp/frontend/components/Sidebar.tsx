"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Company } from "@/lib/api";
import {
  LayoutDashboard,
  Users,
  KeyRound,
  ShieldAlert,
  AlertTriangle,
  ChevronDown,
  Search,
  Building2,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Dashboard", Icon: LayoutDashboard },
  { href: "/employees", label: "Employees", Icon: Users },
  { href: "/credentials", label: "Credentials", Icon: KeyRound },
  { href: "/secrets", label: "Secrets", Icon: ShieldAlert },
  { href: "/breaches", label: "Breaches", Icon: AlertTriangle },
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
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.getCompanies().then(setCompanies).catch(() => {});
  }, []);

  const selected = companies.find((c) => c.company_id === companyId);

  return (
    <aside className="w-60 bg-bg-secondary border-r border-border flex flex-col min-h-screen shrink-0">
      <div className="px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Search className="w-5 h-5 text-accent" />
          <h1 className="text-base font-semibold tracking-tight text-text-primary">
            EmploLeaks
          </h1>
        </div>
      </div>

      <div className="px-3 py-3 border-b border-border">
        <div className="relative">
          <button
            onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-tertiary border border-border text-sm text-text-primary hover:border-border-light transition-colors"
          >
            <Building2 className="w-4 h-4 text-text-secondary shrink-0" />
            <span className="flex-1 text-left truncate">
              {selected ? selected.company_name : "Select company"}
            </span>
            <ChevronDown className={`w-4 h-4 text-text-secondary transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
          {open && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-bg-tertiary border border-border rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto">
              {companies.map((c) => (
                <button
                  key={c.company_id}
                  onClick={() => { onCompanyChange(c.company_id); setOpen(false); }}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-bg-hover transition-colors first:rounded-t-lg last:rounded-b-lg ${
                    c.company_id === companyId ? "text-accent bg-accent/5" : "text-text-primary"
                  }`}
                >
                  {c.company_name}
                </button>
              ))}
              {companies.length === 0 && (
                <p className="px-3 py-2 text-xs text-text-secondary">No companies found</p>
              )}
            </div>
          )}
        </div>
      </div>

      <nav className="flex-1 px-3 py-2">
        <p className="px-3 py-2 text-[10px] font-medium text-text-tertiary uppercase tracking-widest">
          Navigation
        </p>
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] mb-0.5 transition-colors ${
                active
                  ? "bg-accent/10 text-accent font-medium"
                  : "text-text-secondary hover:bg-bg-hover hover:text-text-primary"
              }`}
            >
              <item.Icon className="w-4 h-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 py-3 border-t border-border">
        <p className="text-[11px] text-text-tertiary">EmploLeaks v1.0</p>
      </div>
    </aside>
  );
}
