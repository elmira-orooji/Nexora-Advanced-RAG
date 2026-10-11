import { useState } from "react";
import { createPortal } from "react-dom";
import "../../../styles/knowledge.css";
import { Power, ChevronDown, UserPlus, X } from "lucide-react";
import toast from "react-hot-toast";
import { userService, type ManagedUser } from "../api/userService";
import { useTranslation } from "react-i18next";
import { sectionCopy } from "../../../locales/copy";

interface AddUserFormProps {
  isFa: boolean;
  onClose: () => void;
  onCreated: (user: ManagedUser) => void;
}

export default function AddUserForm({ isFa, onClose, onCreated }: AddUserFormProps) {
  const { t } = useTranslation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [role, setRole] = useState<"admin" | "user">("user");
  const [active, setActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const validUsername = /^[A-Za-z0-9_.-]{3,100}$/.test(username.trim());
  const valid = validUsername && password.length >= 8 && jobTitle.trim().length <= 120;
  const copy = sectionCopy(t, "addUser", ["title", "subtitle", "username", "usernameHint", "password", "passwordHint", "job", "jobPlaceholder", "role", "user", "admin", "active", "cancel", "save", "saving", "success"]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!valid || saving) return;
    setSaving(true); setError("");
    try {
      const created = await userService.create({ username: username.trim(), password, job_title: jobTitle.trim() || undefined, role, is_active: active });
      toast.success(copy.success);
      onCreated(created);
    } catch (reason) { setError((reason as Error).message); }
    finally { setSaving(false); }
  };

  return createPortal(<div className="app-shell"><div className="kb-page nexora-modal-backdrop fixed inset-0 z-[90] grid place-items-center p-4" style={{ fontFamily: isFa ? "Vazirmatn, sans-serif" : "Inter, sans-serif" }} dir={isFa ? "rtl" : "ltr"} onMouseDown={onClose}>
    <form onSubmit={submit} onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="add-member-title" className="chunk-settings member-dialog" onKeyDown={(event) => { if (event.key === "Escape" && !saving) onClose(); }}>
      <header className="chunk-settings-header"><span className="chunk-settings-icon"><UserPlus size={22} /></span><div><h2 id="add-member-title">{copy.title}</h2><p>{copy.subtitle}</p></div><button type="button" aria-label={copy.cancel} onClick={onClose} className="chunk-settings-close"><X size={19} /></button></header>
      <div className="chunk-settings-content">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={copy.username} hint={copy.usernameHint}><input autoFocus maxLength={100} disabled={saving} value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="off" className="member-input" /></Field>
        <Field label={copy.job}><input disabled={saving} value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} placeholder={copy.jobPlaceholder} maxLength={120} className="member-input" /></Field>
        <Field label={copy.password} hint={copy.passwordHint}><input disabled={saving} type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" className="member-input" /></Field>
        <Field label={copy.role}><div className="relative block"><select disabled={saving} value={role} onChange={(event) => setRole(event.target.value as "admin" | "user")} className="member-input appearance-none pe-9"><option value="user">{copy.user}</option><option value="admin">{copy.admin}</option></select><ChevronDown size={14} className="pointer-events-none absolute end-3 top-1/2 -translate-y-1/2 kb-muted" /></div></Field>
      </div>
      <button type="button" role="switch" aria-checked={active} disabled={saving} onClick={() => setActive((value) => !value)} className="member-active"><span><Power size={16} />{copy.active}</span><span className="member-switch" aria-hidden="true"><span /></span></button>
      {error && <p role="alert" className="chunk-settings-error">{error}</p>}
      </div>
      <footer className="chunk-settings-footer"><div className="kb-set-footer-actions"><button type="button" disabled={saving} onClick={onClose} className="chunk-cancel">{copy.cancel}</button><button type="submit" disabled={!valid || saving} className="chunk-save">{saving ? copy.saving : copy.save}</button></div></footer>
    </form>
  </div></div>, document.body);
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return <label className="block text-xs font-semibold kb-muted"><span>{label}</span><div className="mt-2">{children}</div>{hint && <span className="mt-1.5 block text-xs font-normal leading-4 kb-muted">{hint}</span>}</label>;
}
