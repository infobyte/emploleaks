"use client";

import { useState, useMemo } from "react";
import { Search, ChevronUp, ChevronDown } from "lucide-react";

export interface Column {
  key: string;
  label: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  render?: (row: any) => React.ReactNode;
  sortable?: boolean;
}

interface Props {
  columns: Column[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[];
  keyField: string;
  searchKeys?: string[];
  emptyMessage?: string;
  selectable?: boolean;
  selectedIds?: Set<number>;
  onSelectionChange?: (ids: Set<number>) => void;
}

export default function DataTable({
  columns,
  data,
  keyField,
  searchKeys = [],
  emptyMessage = "No data found",
  selectable = false,
  selectedIds,
  onSelectionChange,
}: Props) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(0);
  const perPage = 25;

  const filtered = useMemo(() => {
    let rows = data;
    if (search) {
      const lower = search.toLowerCase();
      rows = rows.filter((row) =>
        searchKeys.some((k) => String(row[k] ?? "").toLowerCase().includes(lower))
      );
    }
    if (sortKey) {
      rows = [...rows].sort((a, b) => {
        const va = String(a[sortKey] ?? "");
        const vb = String(b[sortKey] ?? "");
        return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      });
    }
    return rows;
  }, [data, search, sortKey, sortAsc, searchKeys]);

  const pageCount = Math.ceil(filtered.length / perPage);
  const pageData = filtered.slice(page * perPage, (page + 1) * perPage);

  const handleSort = (key: string) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  };

  const toggleAll = () => {
    if (!onSelectionChange || !selectedIds) return;
    if (selectedIds.size === filtered.length) onSelectionChange(new Set());
    else onSelectionChange(new Set(filtered.map((r) => r[keyField] as number)));
  };

  const toggleOne = (id: number) => {
    if (!onSelectionChange || !selectedIds) return;
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectionChange(next);
  };

  return (
    <div>
      {searchKeys.length > 0 && (
        <div className="mb-3">
          <div className="relative max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
              className="w-full bg-bg-secondary border border-border rounded-lg pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent transition-colors"
            />
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-border bg-bg-secondary">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {selectable && (
                <th className="px-4 py-2.5 w-10">
                  <input
                    type="checkbox"
                    checked={selectedIds?.size === filtered.length && filtered.length > 0}
                    onChange={toggleAll}
                    className="accent-accent rounded"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-2.5 text-left text-[11px] font-medium text-text-secondary uppercase tracking-wider ${
                    col.sortable !== false ? "cursor-pointer hover:text-text-primary select-none" : ""
                  }`}
                  onClick={() => col.sortable !== false && handleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {sortKey === col.key && (
                      sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (selectable ? 1 : 0)}
                  className="px-4 py-12 text-center text-sm text-text-secondary"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              pageData.map((row) => (
                <tr
                  key={String(row[keyField])}
                  className="border-b border-border/40 hover:bg-bg-hover/50 transition-colors"
                >
                  {selectable && (
                    <td className="px-4 py-2.5">
                      <input
                        type="checkbox"
                        checked={selectedIds?.has(row[keyField] as number) ?? false}
                        onChange={() => toggleOne(row[keyField] as number)}
                        className="accent-accent rounded"
                      />
                    </td>
                  )}
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-2.5 text-text-primary">
                      {col.render ? col.render(row) : String(row[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between mt-2">
        <p className="text-xs text-text-tertiary">{filtered.length} result{filtered.length !== 1 ? "s" : ""}</p>
        {pageCount > 1 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-2 py-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-30 transition-colors"
            >
              Prev
            </button>
            <span className="text-xs text-text-secondary px-2">
              {page + 1} / {pageCount}
            </span>
            <button
              onClick={() => setPage(Math.min(pageCount - 1, page + 1))}
              disabled={page >= pageCount - 1}
              className="px-2 py-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-30 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
