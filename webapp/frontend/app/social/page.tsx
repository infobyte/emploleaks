"use client";

import { useEffect, useState, useMemo } from "react";
import { useCompanyId } from "../layout";
import { api, SocialProfile } from "@/lib/api";
import DataTable from "@/components/DataTable";
import { Globe, Search as SearchIcon, ExternalLink, AtSign } from "lucide-react";

export default function SocialPage() {
  const companyId = useCompanyId();
  const [profiles, setProfiles] = useState<SocialProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [lookingUp, setLookingUp] = useState(false);
  const [lookingUpProfiles, setLookingUpProfiles] = useState(false);
  const [filterPlatform, setFilterPlatform] = useState("all");

  const load = () => {
    if (!companyId) return;
    setLoading(true);
    api.getSocialProfiles(companyId).then(setProfiles).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [companyId]);

  const platforms = useMemo(() => {
    const set = new Set<string>();
    profiles.forEach((p) => set.add(p.platform));
    return Array.from(set).sort();
  }, [profiles]);

  const filtered = useMemo(() => {
    if (filterPlatform === "all") return profiles;
    return profiles.filter((p) => p.platform === filterPlatform);
  }, [profiles, filterPlatform]);

  const platformCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    profiles.forEach((p) => { counts[p.platform] = (counts[p.platform] || 0) + 1; });
    return counts;
  }, [profiles]);

  const uniqueEmployees = useMemo(() => {
    return new Set(profiles.map((p) => p.employee_id)).size;
  }, [profiles]);

  const handleLookup = async () => {
    if (!companyId) return;
    setLookingUp(true);
    try {
      const result = await api.lookupSocialProfiles(companyId);
      load();
      alert(`Found ${result.found} new account(s) across ${result.emails_checked} email(s)`);
    } catch {
      alert("Email lookup failed. Check backend logs.");
    } finally {
      setLookingUp(false);
    }
  };

  const handleProfileLookup = async () => {
    if (!companyId) return;
    setLookingUpProfiles(true);
    try {
      const result = await api.lookupProfiles(companyId);
      load();
      alert(`Found ${result.found} new profile(s) across ${result.usernames_checked} username(s)`);
    } catch {
      alert("Profile lookup failed. Add usernames to employees first.");
    } finally {
      setLookingUpProfiles(false);
    }
  };

  const columns = [
    {
      key: "employee_name", label: "Employee",
      render: (row: SocialProfile) => (
        <span className="text-sm font-medium">{row.employee_name || "Unknown"}</span>
      ),
    },
    {
      key: "platform", label: "Platform",
      render: (row: SocialProfile) => (
        <span className="inline-flex items-center gap-1.5 text-xs bg-bg-tertiary px-2 py-1 rounded-md capitalize">
          <Globe className="w-3 h-3 text-text-secondary" />
          {row.platform}
        </span>
      ),
    },
    {
      key: "source_email", label: "Source Email",
      render: (row: SocialProfile) => (
        <span className="text-xs text-accent">{row.source_email || "—"}</span>
      ),
    },
    {
      key: "url", label: "URL",
      render: (row: SocialProfile) =>
        row.url ? (
          <a
            href={row.url.startsWith("http") ? row.url : `https://${row.url}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent-hover"
          >
            {row.url}
            <ExternalLink className="w-3 h-3" />
          </a>
        ) : (
          <span className="text-xs text-text-tertiary">—</span>
        ),
    },
    {
      key: "email_recovery", label: "Recovery Email",
      render: (row: SocialProfile) => (
        <span className="text-xs text-text-secondary">{row.email_recovery || "—"}</span>
      ),
    },
    {
      key: "phone_recovery", label: "Recovery Phone",
      render: (row: SocialProfile) => (
        <span className="text-xs text-text-secondary">{row.phone_recovery || "—"}</span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-text-secondary animate-pulse">Loading social profiles...</div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <Globe className="w-5 h-5 text-text-secondary" />
            Connected Accounts
          </h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Social media and service accounts linked to employee emails
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleLookup}
            disabled={lookingUp}
            className="inline-flex items-center gap-1.5 bg-accent text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
            title="Scan employee emails with Holehe"
          >
            <SearchIcon className="w-3.5 h-3.5" />
            {lookingUp ? "Scanning..." : "Email Lookup"}
          </button>
          <button
            onClick={handleProfileLookup}
            disabled={lookingUpProfiles}
            className="inline-flex items-center gap-1.5 bg-bg-secondary border border-border text-text-primary px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-bg-hover transition-colors disabled:opacity-50"
            title="Search usernames with Maigret (add usernames in Employee cards first)"
          >
            <AtSign className="w-3.5 h-3.5" />
            {lookingUpProfiles ? "Scanning..." : "Username Lookup"}
          </button>
        </div>
      </div>

      {profiles.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-bg-secondary border border-border rounded-xl p-3">
            <p className="text-2xl font-semibold text-text-primary">{profiles.length}</p>
            <p className="text-xs text-text-secondary mt-0.5">Total Accounts</p>
          </div>
          <div className="bg-bg-secondary border border-border rounded-xl p-3">
            <p className="text-2xl font-semibold text-text-primary">{platforms.length}</p>
            <p className="text-xs text-text-secondary mt-0.5">Platforms</p>
          </div>
          <div className="bg-bg-secondary border border-border rounded-xl p-3">
            <p className="text-2xl font-semibold text-text-primary">{uniqueEmployees}</p>
            <p className="text-xs text-text-secondary mt-0.5">Employees with Accounts</p>
          </div>
          <div className="bg-bg-secondary border border-border rounded-xl p-3">
            <p className="text-xs text-text-secondary mb-1.5">Top Platforms</p>
            <div className="flex flex-wrap gap-1">
              {Object.entries(platformCounts)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 4)
                .map(([p, c]) => (
                  <span key={p} className="text-[10px] bg-bg-tertiary px-1.5 py-0.5 rounded capitalize text-text-primary">
                    {p} ({c})
                  </span>
                ))}
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3">
        <select
          value={filterPlatform}
          onChange={(e) => setFilterPlatform(e.target.value)}
          className="bg-bg-secondary border border-border rounded-lg px-2.5 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent transition-colors"
        >
          <option value="all">All platforms ({profiles.length})</option>
          {platforms.map((p) => (
            <option key={p} value={p}>
              {p} ({platformCounts[p] || 0})
            </option>
          ))}
        </select>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        keyField="profile_id"
        searchKeys={["employee_name", "platform", "source_email", "url", "email_recovery"]}
        emptyMessage={profiles.length === 0
          ? "No social profiles found yet. Click \"Run Lookup\" to scan employee emails."
          : "No results match the filter."
        }
      />
    </div>
  );
}
