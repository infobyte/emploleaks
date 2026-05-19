"use client";

import { useEffect, useState, useMemo } from "react";
import { useCompanyId } from "../layout";
import { api, Domain, Subdomain } from "@/lib/api";
import DataTable from "@/components/DataTable";
import { Radar, Plus, Trash2, Search as SearchIcon, Globe, Server } from "lucide-react";

export default function DiscoveryPage() {
  const companyId = useCompanyId();
  const [domains, setDomains] = useState<Domain[]>([]);
  const [subdomains, setSubdomains] = useState<Subdomain[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [newDomain, setNewDomain] = useState("");

  const loadAll = () => {
    if (!companyId) return;
    setLoading(true);
    Promise.all([
      api.getDomains(companyId),
      api.getSubdomains(companyId),
    ])
      .then(([d, s]) => { setDomains(d); setSubdomains(s); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadAll(); }, [companyId]);

  const handleAddDomain = async () => {
    if (!newDomain.trim() || !companyId) return;
    try {
      const created = await api.addDomain(newDomain.trim(), companyId);
      setDomains([...domains, created]);
      setNewDomain("");
    } catch {
      alert("Could not add domain (may already exist).");
    }
  };

  const handleDeleteDomain = async (domainId: number) => {
    if (!confirm("Delete this domain and all its subdomains?")) return;
    try {
      await api.deleteDomain(domainId);
      setDomains(domains.filter((d) => d.domain_id !== domainId));
      setSubdomains(subdomains.filter((s) => {
        const dom = domains.find((d) => d.domain_id === domainId);
        return dom ? s.domain !== dom.domain : true;
      }));
    } catch { /* ignore */ }
  };

  const handleScan = async () => {
    if (!companyId) return;
    setScanning(true);
    try {
      const result = await api.triggerDiscovery(companyId);
      loadAll();
      alert(`Discovery complete: found ${result.total_found} subdomains (${result.new_subdomains} new) across ${result.domains_scanned} domain(s).`);
    } catch {
      alert("Discovery failed. Check backend logs.");
    } finally {
      setScanning(false);
    }
  };

  const uniqueIPs = useMemo(() => {
    const ips = new Set<string>();
    subdomains.forEach((s) => { if (s.ip_address) ips.add(s.ip_address); });
    return ips.size;
  }, [subdomains]);

  const sourceCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    subdomains.forEach((s) => {
      const src = s.source || "unknown";
      counts[src] = (counts[src] || 0) + 1;
    });
    return counts;
  }, [subdomains]);

  const columns = [
    {
      key: "subdomain", label: "Subdomain",
      render: (row: Subdomain) => (
        <span className="text-sm font-medium text-text-primary">{row.subdomain}</span>
      ),
    },
    {
      key: "ip_address", label: "IP Address",
      render: (row: Subdomain) => (
        <span className="text-xs font-mono text-accent">{row.ip_address || "—"}</span>
      ),
    },
    {
      key: "source", label: "Source",
      render: (row: Subdomain) => (
        <span className="text-xs text-text-secondary">{row.source || "—"}</span>
      ),
    },
    {
      key: "domain", label: "Parent Domain",
      render: (row: Subdomain) => (
        <span className="text-xs text-text-tertiary">{row.domain || "—"}</span>
      ),
    },
    {
      key: "first_seen", label: "First Seen",
      render: (row: Subdomain) => (
        <span className="text-xs text-text-tertiary">
          {row.first_seen ? new Date(row.first_seen).toLocaleDateString() : "—"}
        </span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-text-secondary animate-pulse">Loading discovery data...</div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <Radar className="w-5 h-5 text-text-secondary" />
            Discovery
          </h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Infrastructure reconnaissance — subdomain enumeration and DNS resolution
          </p>
        </div>
        <button
          onClick={handleScan}
          disabled={scanning || domains.length === 0}
          className="inline-flex items-center gap-1.5 bg-accent text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          <SearchIcon className="w-3.5 h-3.5" />
          {scanning ? "Scanning..." : "Run Discovery"}
        </button>
      </div>

      <div className="bg-bg-secondary border border-border rounded-xl p-4">
        <h2 className="text-xs font-semibold text-text-primary uppercase tracking-wide mb-3">Domains</h2>
        <div className="flex items-center gap-2 mb-3">
          <input
            type="text"
            value={newDomain}
            onChange={(e) => setNewDomain(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddDomain()}
            placeholder="example.com"
            className="flex-1 max-w-xs bg-bg-tertiary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent transition-colors"
          />
          <button
            onClick={handleAddDomain}
            className="inline-flex items-center gap-1 bg-bg-tertiary border border-border text-text-primary px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-bg-hover transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add
          </button>
        </div>
        {domains.length === 0 ? (
          <p className="text-xs text-text-tertiary py-2">No domains registered. Add a domain to start discovery.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {domains.map((d) => (
              <div
                key={d.domain_id}
                className="inline-flex items-center gap-2 bg-bg-tertiary px-3 py-1.5 rounded-lg group"
              >
                <Globe className="w-3.5 h-3.5 text-text-secondary" />
                <span className="text-sm text-text-primary">{d.domain}</span>
                <span className="text-[10px] text-text-tertiary">
                  {d.subdomain_count} sub{d.subdomain_count !== 1 ? "s" : ""}
                </span>
                <button
                  onClick={() => handleDeleteDomain(d.domain_id)}
                  className="p-0.5 text-text-tertiary hover:text-danger opacity-0 group-hover:opacity-100 transition-all"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {subdomains.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-bg-secondary border border-border rounded-xl p-3">
            <p className="text-2xl font-semibold text-text-primary">{subdomains.length}</p>
            <p className="text-xs text-text-secondary mt-0.5">Total Subdomains</p>
          </div>
          <div className="bg-bg-secondary border border-border rounded-xl p-3">
            <p className="text-2xl font-semibold text-text-primary">{uniqueIPs}</p>
            <p className="text-xs text-text-secondary mt-0.5">Unique IPs</p>
          </div>
          <div className="bg-bg-secondary border border-border rounded-xl p-3">
            <p className="text-2xl font-semibold text-text-primary">{domains.length}</p>
            <p className="text-xs text-text-secondary mt-0.5">Domains</p>
          </div>
          <div className="bg-bg-secondary border border-border rounded-xl p-3">
            <p className="text-xs text-text-secondary mb-1.5">Sources</p>
            <div className="flex flex-wrap gap-1">
              {Object.entries(sourceCounts).map(([src, count]) => (
                <span key={src} className="text-[10px] bg-bg-tertiary px-1.5 py-0.5 rounded text-text-primary">
                  {src} ({count})
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      <DataTable
        columns={columns}
        data={subdomains}
        keyField="subdomain_id"
        searchKeys={["subdomain", "ip_address", "source", "domain"]}
        emptyMessage={
          domains.length === 0
            ? "Add a domain above, then click \"Run Discovery\" to enumerate subdomains."
            : "No subdomains found yet. Click \"Run Discovery\" to scan."
        }
      />
    </div>
  );
}
