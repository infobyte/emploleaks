"use client";

import { useState } from "react";
import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Employee, Username, Credential, Secret, EmailEntry, api } from "@/lib/api";
import {
  ChevronDown,
  GripVertical,
  Trash2,
  EyeOff,
  Eye,
  AlertTriangle,
  KeyRound,
  ShieldAlert,
  Globe,
  Mail,
  AtSign,
  Plus,
  Check,
  X,
  ExternalLink,
  FileWarning,
} from "lucide-react";

function SortableEmployeeRow({
  employee,
  departments,
  onExclude,
  onDelete,
  onChangeDept,
}: {
  employee: Employee;
  departments: string[];
  onExclude: () => void;
  onDelete: () => void;
  onChangeDept: (empId: number, dept: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: employee.employee_id });

  const [rowExpanded, setRowExpanded] = useState(false);
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const [usernames, setUsernames] = useState<Username[]>([]);
  const [loadedUsernames, setLoadedUsernames] = useState(false);
  const [addingUsername, setAddingUsername] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [emails, setEmails] = useState<EmailEntry[]>([]);
  const [creds, setCreds] = useState<Credential[]>([]);
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [loadedDetails, setLoadedDetails] = useState(false);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
  };

  const e = employee;
  const indicators: { label: string; Icon: typeof AlertTriangle; cls: string }[] = [];
  if (e.has_breaches) indicators.push({ label: "Breaches", Icon: AlertTriangle, cls: "text-warning" });
  if (e.has_credentials) indicators.push({ label: "Creds", Icon: KeyRound, cls: "text-danger" });
  if (e.has_secrets) indicators.push({ label: "Secrets", Icon: ShieldAlert, cls: "text-critical" });

  const emailCount = e.confirmed_emails.length + e.potential_emails.length;
  const socialCount = e.social_profiles?.length ?? 0;

  const handleToggleExpand = async () => {
    if (!rowExpanded && !loadedUsernames) {
      try {
        const data = await api.getUsernames(e.employee_id);
        setUsernames(data);
        setLoadedUsernames(true);
      } catch { /* ignore */ }
    }
    setRowExpanded(!rowExpanded);
  };

  const handleToggleDetails = async () => {
    if (!detailsExpanded && !loadedDetails) {
      try {
        const [emailData, credData, secretData] = await Promise.all([
          api.getEmployeeEmails(e.employee_id).catch(() => [] as EmailEntry[]),
          e.has_credentials
            ? api.getEmployeeCredentials(e.employee_id).catch(() => [] as Credential[])
            : Promise.resolve([] as Credential[]),
          e.has_secrets
            ? api.getEmployeeSecrets(e.employee_id).catch(() => [] as Secret[])
            : Promise.resolve([] as Secret[]),
        ]);
        setEmails(emailData);
        setCreds(credData);
        setSecrets(secretData);
        setLoadedDetails(true);
      } catch { /* ignore */ }
    }
    setDetailsExpanded(!detailsExpanded);
  };

  const handleAddUsername = async () => {
    if (!newUsername.trim()) return;
    try {
      const created = await api.addUsername(e.employee_id, newUsername.trim());
      setUsernames([...usernames, created]);
      setNewUsername("");
      setAddingUsername(false);
    } catch { /* ignore */ }
  };

  const handleDeleteUsername = async (id: number) => {
    try {
      await api.deleteUsername(id);
      setUsernames(usernames.filter((u) => u.username_id !== id));
    } catch { /* ignore */ }
  };

  return (
    <div ref={setNodeRef} style={style}>
      <div
        className={`flex items-center gap-2 px-3 py-2 border-b border-border/40 last:border-b-0 hover:bg-bg-hover/50 transition-colors group ${
          e.excluded ? "opacity-40" : ""
        }`}
      >
        <div
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing p-0.5 text-text-tertiary hover:text-text-secondary shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <GripVertical className="w-3.5 h-3.5" />
        </div>

        {e.profile_photo_url ? (
          <img src={e.profile_photo_url} alt="" className="w-8 h-8 rounded-full object-cover shrink-0" />
        ) : (
          <div className="w-8 h-8 rounded-full bg-bg-tertiary flex items-center justify-center text-text-secondary text-xs font-medium shrink-0">
            {(e.name || "?").charAt(0).toUpperCase()}
          </div>
        )}

        <div className="flex-1 min-w-0 flex items-center gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-text-primary truncate">{e.name || "Unknown"}</p>
            {e.title && <p className="text-xs text-text-secondary truncate">{e.title}</p>}
          </div>

          <div className="hidden sm:flex items-center gap-3 shrink-0">
            {emailCount > 0 && (
              <span className="flex items-center gap-1 text-[11px] text-text-tertiary">
                <Mail className="w-3 h-3" />
                {emailCount}
              </span>
            )}
            {socialCount > 0 && (
              <span className="flex items-center gap-1 text-[11px] text-text-tertiary">
                <Globe className="w-3 h-3" />
                {socialCount}
              </span>
            )}
            {indicators.map((ind) => (
              <span key={ind.label} className={`flex items-center gap-1 text-[11px] ${ind.cls}`}>
                <ind.Icon className="w-3 h-3" />
                {ind.label}
              </span>
            ))}
          </div>
        </div>

        <select
          value={e.department || ""}
          onChange={(ev) => onChangeDept(e.employee_id, ev.target.value)}
          className="text-[11px] bg-bg-tertiary border border-border rounded-md px-1.5 py-1 text-text-primary focus:outline-none focus:border-accent shrink-0 max-w-[120px] cursor-pointer"
          title="Change department"
        >
          <option value="">Unassigned</option>
          {departments.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>

        <div className="flex items-center gap-0.5 shrink-0">
          <button
            onClick={handleToggleDetails}
            className="p-1 rounded-md hover:bg-bg-tertiary text-text-tertiary hover:text-text-primary transition-colors"
            title="Show details (emails, credentials, secrets)"
          >
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${detailsExpanded ? "rotate-180 text-accent" : ""}`} />
          </button>
          <button
            onClick={handleToggleExpand}
            className="p-1 rounded-md hover:bg-bg-tertiary text-text-tertiary hover:text-text-primary transition-colors"
            title="Manage usernames"
          >
            <AtSign className={`w-3.5 h-3.5 ${rowExpanded ? "text-accent" : ""}`} />
          </button>
          <button
            onClick={onExclude}
            className="p-1 rounded-md hover:bg-bg-tertiary text-text-tertiary hover:text-warning transition-colors opacity-0 group-hover:opacity-100"
            title={e.excluded ? "Include" : "Exclude"}
          >
            {e.excluded ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={onDelete}
            className="p-1 rounded-md hover:bg-bg-tertiary text-text-tertiary hover:text-danger transition-colors opacity-0 group-hover:opacity-100"
            title="Delete"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {detailsExpanded && (
        <div className="px-10 py-3 bg-bg-tertiary/30 border-b border-border/40 space-y-3">
          {/* Emails */}
          {emails.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider flex items-center gap-1.5">
                <Mail className="w-3 h-3" />
                Emails ({emails.length})
              </p>
              {emails.map((em) => (
                <div key={`${em.type}-${em.email_id}`} className="flex items-center gap-2 text-xs">
                  <Mail className="w-3 h-3 text-text-tertiary shrink-0" />
                  <span className="text-text-primary flex-1 truncate">{em.email}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${em.type === "confirmed" ? "bg-success/10 text-success" : "bg-accent/10 text-accent"}`}>
                    {em.type === "confirmed" ? "conf" : "pot"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Credentials */}
          {creds.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider flex items-center gap-1.5">
                <KeyRound className="w-3 h-3 text-danger" />
                Leaked Credentials ({creds.length})
              </p>
              <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                {creds.map((c) => (
                  <div key={c.password_id} className="flex items-center gap-2 text-xs bg-bg-secondary border border-border/50 rounded px-2 py-1.5">
                    <span className="text-text-primary truncate max-w-[160px]" title={c.identifier}>{c.identifier}</span>
                    <code className="text-[11px] bg-bg-tertiary px-1.5 py-0.5 rounded font-mono text-danger truncate max-w-[140px]" title={c.password}>
                      {c.password}
                    </code>
                    {c.url && (
                      <span className="text-[10px] text-text-secondary truncate max-w-[180px] font-mono" title={c.url}>
                        @ {c.url}
                      </span>
                    )}
                    <span className="text-[10px] text-text-tertiary ml-auto shrink-0">{c.breach_context || "—"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Secrets */}
          {secrets.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider flex items-center gap-1.5">
                <FileWarning className="w-3 h-3 text-critical" />
                Secrets ({secrets.length})
              </p>
              <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                {secrets.map((s) => (
                  <div key={s.secret_id} className="flex items-center gap-2 text-xs bg-bg-secondary border border-border/50 rounded px-2 py-1.5">
                    <ShieldAlert className="w-3 h-3 text-critical shrink-0" />
                    <span className="text-[10px] font-medium bg-critical/10 text-critical rounded px-1.5 py-0.5 shrink-0">
                      {s.secret_type}
                    </span>
                    <code className="text-[11px] bg-bg-tertiary px-1.5 py-0.5 rounded font-mono truncate max-w-[200px]" title={s.secret_value}>
                      {s.secret_value}
                    </code>
                    <a
                      href={s.repo_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-text-secondary hover:text-accent truncate max-w-[160px] ml-auto inline-flex items-center gap-1"
                      title={s.repo_url}
                    >
                      <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                      {s.file_path || s.repo_url.split("/").slice(-2).join("/")}
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Social profiles */}
          {e.social_profiles && e.social_profiles.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider flex items-center gap-1.5">
                <Globe className="w-3 h-3" />
                Connected Accounts ({e.social_profiles.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {e.social_profiles.map((sp, i) => (
                  <a
                    key={`${sp.platform}-${i}`}
                    href={sp.url ? (sp.url.startsWith("http") ? sp.url : `https://${sp.url}`) : "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] bg-bg-secondary border border-border/50 text-text-primary px-2 py-1 rounded-md hover:bg-bg-hover transition-colors"
                    title={sp.url || sp.platform}
                  >
                    <Globe className="w-3 h-3 text-text-secondary" />
                    {sp.platform}
                    {sp.url && <ExternalLink className="w-2.5 h-2.5 text-text-tertiary" />}
                  </a>
                ))}
              </div>
            </div>
          )}

          {emails.length === 0 && creds.length === 0 && secrets.length === 0 && (!e.social_profiles || e.social_profiles.length === 0) && (
            <p className="text-xs text-text-tertiary text-center py-2">No data to display for this employee.</p>
          )}
        </div>
      )}

      {rowExpanded && (
        <div className="px-10 py-2 bg-bg-tertiary/30 border-b border-border/40 space-y-1.5">
          <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Usernames</p>
          {usernames.map((u) => (
            <div key={u.username_id} className="flex items-center gap-2 group/u">
              <AtSign className="w-3 h-3 text-text-tertiary shrink-0" />
              <span className="text-xs text-text-primary flex-1 truncate">{u.username}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-tertiary text-text-tertiary">{u.source}</span>
              <button
                onClick={() => handleDeleteUsername(u.username_id)}
                className="p-1 text-text-tertiary hover:text-danger opacity-0 group-hover/u:opacity-100 transition-opacity"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))}
          {addingUsername ? (
            <div className="flex items-center gap-2">
              <input
                value={newUsername}
                onChange={(ev) => setNewUsername(ev.target.value)}
                placeholder="username"
                className="flex-1 text-xs bg-bg-tertiary border border-border rounded px-2 py-1 text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent"
                onKeyDown={(ev) => ev.key === "Enter" && handleAddUsername()}
                autoFocus
              />
              <button onClick={handleAddUsername} className="p-1 text-success hover:text-success/80"><Check className="w-3 h-3" /></button>
              <button onClick={() => setAddingUsername(false)} className="p-1 text-text-secondary hover:text-text-primary"><X className="w-3 h-3" /></button>
            </div>
          ) : (
            <button
              onClick={() => setAddingUsername(true)}
              className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-accent transition-colors"
            >
              <Plus className="w-3 h-3" />
              Add username
            </button>
          )}
        </div>
      )}
    </div>
  );
}

interface Props {
  department: string;
  employees: Employee[];
  allDepartments: string[];
  onExclude: (id: number) => void;
  onDelete: (id: number) => void;
  onChangeDept: (empId: number, dept: string) => void;
  defaultExpanded?: boolean;
}

export default function DeptSection({
  department,
  employees,
  allDepartments,
  onExclude,
  onDelete,
  onChangeDept,
  defaultExpanded = true,
}: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const { setNodeRef, isOver } = useDroppable({ id: department });

  return (
    <div
      ref={setNodeRef}
      className={`bg-bg-secondary border rounded-xl overflow-hidden transition-colors ${
        isOver ? "border-accent ring-1 ring-accent/20" : "border-border"
      }`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-bg-hover/50 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <ChevronDown className={`w-4 h-4 text-text-tertiary transition-transform ${expanded ? "" : "-rotate-90"}`} />
          <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide">{department}</h3>
          <span className="text-[11px] text-text-secondary bg-bg-tertiary px-2 py-0.5 rounded-full font-medium">
            {employees.length}
          </span>
        </div>
        {isOver && (
          <span className="text-[10px] text-accent font-medium">Drop here</span>
        )}
      </button>

      {expanded && (
        <SortableContext
          items={employees.map((e) => e.employee_id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="border-t border-border">
            {employees.length === 0 ? (
              <p className="text-xs text-text-tertiary text-center py-4">
                No employees — drag or reassign someone here
              </p>
            ) : (
              employees.map((emp) => (
                <SortableEmployeeRow
                  key={emp.employee_id}
                  employee={emp}
                  departments={allDepartments}
                  onExclude={() => onExclude(emp.employee_id)}
                  onDelete={() => onDelete(emp.employee_id)}
                  onChangeDept={onChangeDept}
                />
              ))
            )}
          </div>
        </SortableContext>
      )}
    </div>
  );
}
