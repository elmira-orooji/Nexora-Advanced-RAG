import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ShieldCheck, X } from "lucide-react";
import "../styles/knowledge.css";
import InlineError from "./InlineError";
import { userService, type ManagedUser, type PermissionLevel } from "../services/userService";
import type { DocumentSet } from "../services/knowledgeService";

export default function UserKnowledgeAccess({ user, isFa }: { user: ManagedUser; isFa: boolean }) {
  const [open, setOpen] = useState(false);
  const label = isFa ? "دسترسی پایگاه‌های دانش" : "Knowledge access";
  return <><button type="button" className="team-access-button" onClick={() => setOpen(true)} aria-label={`${label}: ${user.username}`} title={label}><span>{isFa ? "دسترسی‌ها" : "Access"}</span></button>
    {open && <AccessDialog key={user.id} user={user} isFa={isFa} onClose={() => setOpen(false)} />}</>;
}

function AccessDialog({ user, isFa, onClose }: { user: ManagedUser; isFa: boolean; onClose: () => void }) {
  const [sets, setSets] = useState<DocumentSet[]>([]);
  const [access, setAccess] = useState<Record<string, PermissionLevel>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const dialog = useRef<HTMLFormElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    return () => { previous?.focus(); };
  }, []);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    Promise.all([userService.listSets(), userService.permissions(user.id)])
      .then(([items, permissions]) => { if (active) { setSets(items); setAccess(Object.fromEntries(permissions.map((item) => [item.document_set_id, item.permission]))); } })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [user.id, revision]);
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading || saving || error) return;
    setSaving(true);
    try {
      await userService.savePermissions(user.id, Object.entries(access).map(([document_set_id, permission]) => ({ document_set_id, permission })));
      onClose();
    } catch (reason) { setError((reason as Error).message); }
    finally { setSaving(false); }
  };
  const cancel = isFa ? "بستن" : "Close";
  return createPortal(<div className="app-shell"><div dir={isFa ? "rtl" : "ltr"} className="kb-page nexora-modal-backdrop fixed inset-0 z-[90] grid place-items-center p-4" onMouseDown={() => { if (!saving) onClose(); }}>
    <form ref={dialog} tabIndex={-1} onSubmit={save} role="dialog" aria-modal="true" aria-labelledby="knowledge-access-title" className="chunk-settings member-dialog" onMouseDown={(event) => event.stopPropagation()} onKeyDown={(event) => {
      if (event.key === "Escape" && !saving) onClose();
      if (event.key === "Tab") {
        const controls = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), select:not(:disabled), [tabindex="0"]') || []);
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first?.focus(); }
      }
    }}>
      <header className="chunk-settings-header"><span className="chunk-settings-icon"><ShieldCheck size={22} /></span><div><h2 id="knowledge-access-title">{isFa ? "دسترسی پایگاه‌های دانش" : "Knowledge access"}</h2><p><bdi>{user.username}</bdi></p></div><button type="button" disabled={saving} aria-label={cancel} onClick={onClose} className="chunk-settings-close"><X size={19} /></button></header>
      <div className="chunk-settings-content overflow-y-auto" style={{ maxHeight: "60dvh" }}>
        <p className="mb-4 text-xs leading-6 kb-muted">{isFa ? "برای هر پایگاه، سطح دسترسی را مشخص کنید. «بدون دسترسی» مجوز قبلی را لغو می‌کند." : "Choose access for each knowledge base. No access revokes an existing permission."}</p>
        {loading ? <p role="status">{isFa ? "در حال دریافت دسترسی‌ها…" : "Loading permissions…"}</p> : error ? <><InlineError message={error} /><button type="button" className="chunk-cancel mt-3" onClick={() => setRevision((value) => value + 1)}>{isFa ? "تلاش دوباره" : "Retry"}</button></> : sets.length ? sets.map((set) => <label key={set.id} className="mb-3 flex flex-wrap items-center justify-between gap-3"><span className="min-w-0 flex-1 break-words text-sm">{set.name}</span><select aria-label={set.name} disabled={saving} className="member-input" style={{ width: "auto", maxWidth: "100%" }} value={access[set.id] || "none"} onChange={(event) => { const value = event.target.value; setAccess((current) => { const next = { ...current }; if (value === "none") delete next[set.id]; else next[set.id] = value as PermissionLevel; return next; }); }}>
          <option value="none">{isFa ? "بدون دسترسی" : "No access"}</option><option value="view">{isFa ? "مشاهده" : "View"}</option><option value="edit">{isFa ? "ویرایش" : "Edit"}</option><option value="manage">{isFa ? "مدیریت" : "Manage"}</option>
        </select></label>) : <p>{isFa ? "ابتدا یک پایگاه دانش ایجاد کنید." : "Create a knowledge base first."}</p>}
      </div>
      <footer className="chunk-settings-footer"><div className="kb-set-footer-actions"><button type="button" disabled={saving} onClick={onClose} className="chunk-cancel">{cancel}</button><button type="submit" disabled={loading || saving || Boolean(error)} className="chunk-save">{saving ? (isFa ? "در حال ذخیره…" : "Saving…") : (isFa ? "ذخیره دسترسی‌ها" : "Save permissions")}</button></div></footer>
    </form>
  </div></div>, document.body);
}
