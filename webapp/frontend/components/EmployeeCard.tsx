"use client";

import { useState } from "react";
import { Employee, EmailEntry, Username, Credential, Secret, api } from "@/lib/api";
import {
  Mail,
  ChevronDown,
  Trash2,
  EyeOff,
  Eye,
  AlertTriangle,
  KeyRound,
  ShieldAlert,
  Plus,
  Pencil,
  X,
  Check,
  Globe,
  ExternalLink,
  AtSign,
  FileWarning,
} from "lucide-react";

interface Props {
  employee: Employee;
  onExclude?: () => void;
  onDelete?: () => void;
  compact?: boolean;
  onRefresh?: () => void;
}

export default function EmployeeCard({ employee, onExclude, onDelete, compact, onRefresh }: Props) {
  const e = employee;
  const [expanded, setExpanded] = useState(false);
  const [emails, setEmails] = useState<EmailEntry[]>([]);
  const [usernames, setUsernames] = useState<Username[]>([]);
  const [creds, setCreds] = useState<Credential[]>([]);
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [loadingEmails, setLoadingEmails] = useState(false);
  const [addingEmail, setAddingEmail] = useState(false);
  const [addingUsername, setAddingUsername] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newEmailType, setNewEmailType] = useState<"confirmed" | "potential">("confirmed");
  const [newUsername, setNewUsername] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");

  const allEmails = [...e.confirmed_emails, ...e.potential_emails];
  const indicators: { label: string; Icon: typeof AlertTriangle; cls: string }[] = [];
  if (e.has_breaches) indicators.push({ label: "Breaches", Icon: AlertTriangle, cls: "text-warning" });
  if (e.has_credentials) indicators.push({ label: "Credentials", Icon: KeyRound, cls: "text-danger" });
  if (e.has_secrets) indicators.push({ label: "Secrets", Icon: ShieldAlert, cls: "text-critical" });

  const loadData = async () => {
    if (emails.length > 0) return;
    setLoadingEmails(true);
    try {
      const [emailData, usernameData, credData, secretData] = await Promise.all([
        api.getEmployeeEmails(e.employee_id),
        api.getUsernames(e.employee_id),
        e.has_credentials ? api.getEmployeeCredentials(e.employee_id).catch(() => []) : Promise.resolve([] as Credential[]),
        e.has_secrets ? api.getEmployeeSecrets(e.employee_id).catch(() => []) : Promise.resolve([] as Secret[]),
      ]);
      setEmails(emailData);
      setUsernames(usernameData);
      setCreds(credData);
      setSecrets(secretData);
    } catch { /* ignore */ }
    setLoadingEmails(false);
  };

  const handleExpand = () => {
    if (!expanded) loadData();
    setExpanded(!expanded);
  };

  const handleAddEmail = async () => {
    if (!newEmail.trim()) return;
    try {
      const created = await api.createEmail(e.employee_id, newEmail.trim(), newEmailType);
      setEmails([...emails, created]);
      setNewEmail("");
      setAddingEmail(false);
      onRefresh?.();
    } catch { /* ignore */ }
  };

  const handleDeleteEmail = async (emailId: number, type: string) => {
    try {
      await api.deleteEmail(emailId, type);
      setEmails(emails.filter((em) => em.email_id !== emailId));
      onRefresh?.();
    } catch { /* ignore */ }
  };

  const handleEditSave = async (emailId: number, currentType: string) => {
    if (!editValue.trim()) return;
    try {
      await api.updateEmail(emailId, editValue.trim(), currentType, currentType);
      setEmails(emails.map((em) => (em.email_id === emailId ? { ...em, email: editValue.trim() } : em)));
      setEditingId(null);
      onRefresh?.();
    } catch { /* ignore */ }
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

  const handleDeleteUsername = async (usernameId: number) => {
    try {
      await api.deleteUsername(usernameId);
      setUsernames(usernames.filter((u) => u.username_id !== usernameId));
    } catch { /* ignore */ }
  };

  return (
    <div
      className={`bg-bg-secondary border border-border rounded-xl hover:border-border-light transition-colors ${
        e.excluded ? "opacity-40" : ""
      }`}
    >
      <div className="p-3 flex items-start gap-3">
        {e.profile_photo_url ? (
          <img src={e.profile_photo_url} alt="" className="w-9 h-9 rounded-full object-cover shrink-0" />
        ) : (
          <div className="w-9 h-9 rounded-full bg-bg-tertiary flex items-center justify-center text-text-secondary text-xs font-medium shrink-0">
            {(e.name || "?").charAt(0).toUpperCase()}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text-primary truncate">{e.name || "Unknown"}</p>
          {e.title && <p className="text-xs text-text-secondary truncate mt-0.5">{e.title}</p>}
          {!compact && indicators.length > 0 && (
            <div className="flex items-center gap-3 mt-1.5">
              {indicators.map((ind) => (
                <span key={ind.label} className={`flex items-center gap-1 text-[11px] ${ind.cls}`}>
                  <ind.Icon className="w-3 h-3" />
                  {ind.label}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {!compact && (
            <button
              onClick={handleExpand}
              className="p-1.5 rounded-md hover:bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
              title="Expand details"
            >
              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} />
            </button>
          )}
          {onExclude && (
            <button
              onClick={onExclude}
              className="p-1.5 rounded-md hover:bg-bg-tertiary text-text-secondary hover:text-warning transition-colors"
              title={e.excluded ? "Include" : "Exclude"}
            >
              {e.excluded ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            </button>
          )}
          {onDelete && (
            <button
              onClick={onDelete}
              className="p-1.5 rounded-md hover:bg-bg-tertiary text-text-secondary hover:text-danger transition-colors"
              title="Delete"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {!compact && !expanded && (
        <div className="px-3 pb-3 pt-0 flex items-center gap-3">
          {allEmails.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-text-secondary">
              <Mail className="w-3 h-3" />
              <span>{allEmails.length} email{allEmails.length !== 1 ? "s" : ""}</span>
            </div>
          )}
          {e.social_profiles && e.social_profiles.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-text-secondary">
              <Globe className="w-3 h-3" />
              <span>{e.social_profiles.length} account{e.social_profiles.length !== 1 ? "s" : ""}</span>
            </div>
          )}
        </div>
      )}

      {expanded && (
        <div className="border-t border-border px-3 py-2.5 space-y-3">
          {/* Emails section */}
          <div className="space-y-1.5">
            <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Emails</p>
            {loadingEmails ? (
              <p className="text-xs text-text-secondary py-1">Loading...</p>
            ) : (
              <>
                {emails.map((em) => (
                  <div key={`${em.type}-${em.email_id}`} className="flex items-center gap-2 group">
                    {editingId === em.email_id ? (
                      <>
                        <input
                          value={editValue}
                          onChange={(ev) => setEditValue(ev.target.value)}
                          className="flex-1 text-xs bg-bg-tertiary border border-border rounded px-2 py-1 text-text-primary focus:outline-none focus:border-accent"
                          onKeyDown={(ev) => ev.key === "Enter" && handleEditSave(em.email_id, em.type)}
                        />
                        <button onClick={() => handleEditSave(em.email_id, em.type)} className="p-1 text-success hover:text-success/80"><Check className="w-3 h-3" /></button>
                        <button onClick={() => setEditingId(null)} className="p-1 text-text-secondary hover:text-text-primary"><X className="w-3 h-3" /></button>
                      </>
                    ) : (
                      <>
                        <Mail className="w-3 h-3 text-text-tertiary shrink-0" />
                        <span className="text-xs text-text-primary flex-1 truncate">{em.email}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${em.type === "confirmed" ? "bg-success/10 text-success" : "bg-accent/10 text-accent"}`}>
                          {em.type === "confirmed" ? "conf" : "pot"}
                        </span>
                        <button
                          onClick={() => { setEditingId(em.email_id); setEditValue(em.email); }}
                          className="p-1 text-text-tertiary hover:text-text-primary opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Pencil className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => handleDeleteEmail(em.email_id, em.type)}
                          className="p-1 text-text-tertiary hover:text-danger opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </>
                    )}
                  </div>
                ))}
                {addingEmail ? (
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      value={newEmail}
                      onChange={(ev) => setNewEmail(ev.target.value)}
                      placeholder="email@example.com"
                      className="flex-1 text-xs bg-bg-tertiary border border-border rounded px-2 py-1 text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent"
                      onKeyDown={(ev) => ev.key === "Enter" && handleAddEmail()}
                      autoFocus
                    />
                    <select
                      value={newEmailType}
                      onChange={(ev) => setNewEmailType(ev.target.value as "confirmed" | "potential")}
                      className="text-[10px] bg-bg-tertiary border border-border rounded px-1.5 py-1 text-text-primary"
                    >
                      <option value="confirmed">Confirmed</option>
                      <option value="potential">Potential</option>
                    </select>
                    <button onClick={handleAddEmail} className="p-1 text-success hover:text-success/80"><Check className="w-3 h-3" /></button>
                    <button onClick={() => setAddingEmail(false)} className="p-1 text-text-secondary hover:text-text-primary"><X className="w-3 h-3" /></button>
                  </div>
                ) : (
                  <button
                    onClick={() => setAddingEmail(true)}
                    className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-accent transition-colors pt-1"
                  >
                    <Plus className="w-3 h-3" />
                    Add email
                  </button>
                )}
              </>
            )}
          </div>

          {/* Usernames section */}
          <div className="space-y-1.5">
            <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Usernames</p>
            {usernames.map((u) => (
              <div key={u.username_id} className="flex items-center gap-2 group">
                <AtSign className="w-3 h-3 text-text-tertiary shrink-0" />
                <span className="text-xs text-text-primary flex-1 truncate">{u.username}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-tertiary text-text-tertiary">{u.source}</span>
                <button
                  onClick={() => handleDeleteUsername(u.username_id)}
                  className="p-1 text-text-tertiary hover:text-danger opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
            {addingUsername ? (
              <div className="flex items-center gap-2 pt-1">
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
                className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-accent transition-colors pt-1"
              >
                <Plus className="w-3 h-3" />
                Add username
              </button>
            )}
          </div>

          {/* Leaked credentials section */}
          {creds.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider flex items-center gap-1.5">
                <KeyRound className="w-3 h-3 text-danger" />
                Leaked Credentials ({creds.length})
              </p>
              <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                {creds.map((c) => (
                  <div key={c.password_id} className="flex items-center gap-2 text-xs bg-bg-tertiary/50 border border-border/50 rounded px-2 py-1.5">
                    <Mail className="w-3 h-3 text-text-tertiary shrink-0" />
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

          {/* Secrets section */}
          {secrets.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider flex items-center gap-1.5">
                <FileWarning className="w-3 h-3 text-critical" />
                Secrets ({secrets.length})
              </p>
              <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                {secrets.map((s) => (
                  <div key={s.secret_id} className="flex items-center gap-2 text-xs bg-bg-tertiary/50 border border-border/50 rounded px-2 py-1.5">
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

          {/* Connected accounts section */}
          {e.social_profiles && e.social_profiles.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Connected Accounts</p>
              <div className="flex flex-wrap gap-1.5">
                {e.social_profiles.map((sp, i) => (
                  <a
                    key={`${sp.platform}-${i}`}
                    href={sp.url ? (sp.url.startsWith("http") ? sp.url : `https://${sp.url}`) : "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] bg-bg-tertiary text-text-primary px-2 py-1 rounded-md hover:bg-bg-hover transition-colors"
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
        </div>
      )}
    </div>
  );
}
