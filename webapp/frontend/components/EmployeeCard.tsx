"use client";

import { Employee } from "@/lib/api";

interface Props {
  employee: Employee;
  onExclude?: () => void;
  onDelete?: () => void;
  compact?: boolean;
}

export default function EmployeeCard({ employee, onExclude, onDelete, compact }: Props) {
  const e = employee;
  const allEmails = [...e.confirmed_emails, ...e.potential_emails];
  const indicators = [];
  if (e.has_breaches) indicators.push({ label: "Breaches", cls: "bg-warning/20 text-warning" });
  if (e.has_credentials) indicators.push({ label: "Creds", cls: "bg-danger/20 text-danger" });
  if (e.has_secrets) indicators.push({ label: "Secrets", cls: "bg-critical/20 text-critical" });

  return (
    <div
      className={`bg-bg-secondary border border-border rounded-xl p-4 hover:border-accent/40 transition-colors ${
        e.excluded ? "opacity-50" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        {e.profile_photo_url ? (
          <img
            src={e.profile_photo_url}
            alt={e.name || ""}
            className="w-10 h-10 rounded-full object-cover shrink-0"
          />
        ) : (
          <div className="w-10 h-10 rounded-full bg-bg-tertiary flex items-center justify-center text-text-secondary text-sm shrink-0">
            {(e.name || "?")[0]}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm truncate">{e.name || "Unknown"}</p>
          {e.title && (
            <p className="text-xs text-text-secondary truncate">{e.title}</p>
          )}
        </div>
        {(onExclude || onDelete) && (
          <div className="flex gap-1 shrink-0">
            {onExclude && (
              <button
                onClick={onExclude}
                className="text-xs px-2 py-1 rounded bg-bg-tertiary hover:bg-warning/20 text-text-secondary hover:text-warning transition-colors"
                title={e.excluded ? "Include" : "Exclude"}
              >
                {e.excluded ? "✓" : "✕"}
              </button>
            )}
            {onDelete && (
              <button
                onClick={onDelete}
                className="text-xs px-2 py-1 rounded bg-bg-tertiary hover:bg-danger/20 text-text-secondary hover:text-danger transition-colors"
                title="Delete"
              >
                🗑
              </button>
            )}
          </div>
        )}
      </div>

      {!compact && (
        <>
          {allEmails.length > 0 && (
            <div className="mt-2 space-y-0.5">
              {allEmails.slice(0, 3).map((email) => (
                <p key={email} className="text-xs text-accent truncate">
                  {email}
                </p>
              ))}
              {allEmails.length > 3 && (
                <p className="text-xs text-text-secondary">+{allEmails.length - 3} more</p>
              )}
            </div>
          )}
          {indicators.length > 0 && (
            <div className="flex gap-1.5 mt-2">
              {indicators.map((ind) => (
                <span
                  key={ind.label}
                  className={`text-xs px-2 py-0.5 rounded-full ${ind.cls}`}
                >
                  {ind.label}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
