import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ShieldCheck, X } from "lucide-react";
import "../../../styles/knowledge.css";
import InlineError from "../../../components/InlineError";
import { userService, type DocumentCatalogItem, type ManagedUser, type PermissionLevel } from "../api/userService";
import type { DocumentSet } from "../../knowledge/api/knowledgeService";

export default function UserKnowledgeAccess({ user, isFa }: { user: ManagedUser; isFa: boolean }) {
  const [open, setOpen] = useState(false);
  const label = isFa ? "دسترسی پایگاه‌های دانش" : "Knowledge access";
  return <><button type="button" className="team-access-button" onClick={() => setOpen(true)} aria-label={`${label}: ${user.username}`} title={label}><span>{isFa ? "دسترسی‌ها" : "Access"}</span></button>
    {open && <AccessDialog key={user.id} user={user} isFa={isFa} onClose={() => setOpen(false)} />}</>;
}

function AccessDialog({ user, isFa, onClose }: { user: ManagedUser; isFa: boolean; onClose: () => void }) {
  const [sets, setSets] = useState<DocumentSet[]>([]);
  const [access, setAccess] = useState<Record<string, PermissionLevel>>({});
  const [documentAccess, setDocumentAccess] = useState<Record<string, PermissionLevel>>({});
  const [documents, setDocuments] = useState<DocumentCatalogItem[]>([]);
  const [documentSearch, setDocumentSearch] = useState("");
  const [documentOffset, setDocumentOffset] = useState(0);
  const [documentTotal, setDocumentTotal] = useState(0);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const dialog = useRef<HTMLFormElement>(null);
  const documentAccessInitialized = useRef(false);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    return () => { previous?.focus(); };
  }, []);
  useEffect(() => {
    let active = true;
    Promise.all([userService.listSets(), userService.permissions(user.id)])
      .then(([items, permissions]) => { if (active) { setSets(items); setAccess(Object.fromEntries(permissions.map((item) => [item.document_set_id, item.permission]))); } })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [user.id, revision]);
  useEffect(() => {
    let active = true;
    userService.documentCatalog(user.id, documentOffset, 25, documentSearch)
      .then((catalog) => {
        if (!active) return;
        setDocuments((current) => documentOffset === 0
          ? catalog.documents
          : [...current, ...catalog.documents.filter((item) => !current.some((existing) => existing.id === item.id))]);
        setDocumentTotal(catalog.total);
        if (!documentAccessInitialized.current) {
          setDocumentAccess(Object.fromEntries(catalog.permissions.map((item) => [item.document_id, item.permission])));
          documentAccessInitialized.current = true;
        }
      })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setDocumentsLoading(false); });
    return () => { active = false; };
  }, [user.id, documentOffset, documentSearch, revision]);
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading || saving || error) return;
    setSaving(true);
    try {
      await userService.savePermissions(
        user.id,
        Object.entries(access).map(([document_set_id, permission]) => ({ document_set_id, permission })),
        Object.entries(documentAccess).map(([document_id, permission]) => ({ document_id, permission })),
      );
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
        {loading ? <p role="status">{isFa ? "در حال دریافت دسترسی‌ها…" : "Loading permissions…"}</p> : error ? <><InlineError message={error} /><button type="button" className="chunk-cancel mt-3" onClick={() => { setLoading(true); setDocumentsLoading(true); setError(""); setRevision((value) => value + 1); }}>{isFa ? "تلاش دوباره" : "Retry"}</button></> : <>
          {sets.length ? sets.map((set) => <label key={set.id} className="mb-3 flex flex-wrap items-center justify-between gap-3"><span className="min-w-0 flex-1 break-words text-sm">{set.name}</span><select aria-label={set.name} disabled={saving} className="member-input" style={{ width: "auto", maxWidth: "100%" }} value={access[set.id] || "none"} onChange={(event) => { const value = event.target.value; setAccess((current) => { const next = { ...current }; if (value === "none") delete next[set.id]; else next[set.id] = value as PermissionLevel; return next; }); }}>
          <option value="none">{isFa ? "بدون دسترسی" : "No access"}</option><option value="view">{isFa ? "مشاهده" : "View"}</option><option value="edit">{isFa ? "ویرایش" : "Edit"}</option><option value="manage">{isFa ? "مدیریت" : "Manage"}</option>
          </select></label>) : <p>{isFa ? "ابتدا یک پایگاه دانش ایجاد کنید." : "Create a knowledge base first."}</p>}
          <div className="mt-6 border-t border-[var(--kb-line)] pt-4">
            <h3 className="text-sm font-semibold">{isFa ? "دسترسی سندمحور" : "Document-level access"}</h3>
            <p className="mb-3 mt-2 text-xs leading-5 kb-muted">{isFa ? "با ثبت اولین مجوز صریح برای یک سند، دسترسی آن سند فقط به کاربران مجاز محدود می‌شود. در غیر این صورت، مجوز مجموعه اعمال می‌شود." : "Once any direct grant is set on a document, only explicitly granted users can access it. Otherwise, access follows the knowledge set."}</p>
            <input value={documentSearch} disabled={saving} onChange={(event) => { setDocumentsLoading(true); setDocumentSearch(event.target.value); setDocumentOffset(0); setDocuments([]); }} placeholder={isFa ? "جست‌وجوی نام سند" : "Search documents"} aria-label={isFa ? "جست‌وجوی اسناد" : "Search documents"} className="member-input mb-3 w-full" />
            {documents.map((document) => {
              const inheritsSetGrant = document.document_set_names.some((name) => {
                const set = sets.find((item) => item.name === name);
                return set ? Boolean(access[set.id]) : false;
              });
              const scopeLabel = document.restricted
                ? (isFa ? "محدودشده" : "Restricted")
                : inheritsSetGrant ? (isFa ? "ارث‌بری از مجموعه" : "Inherited") : (isFa ? "بدون دسترسی" : "No access");
              return <label key={document.id} className="mb-2 flex flex-wrap items-center gap-3 rounded-xl border border-[var(--kb-line)] p-3">
              <span className="min-w-0 flex-1"><span className="block break-words text-xs font-medium">{document.filename}</span><span className="mt-1 block text-[11px] kb-muted">{document.document_set_names.join(" · ") || (isFa ? "بدون مجموعه" : "No knowledge set")} · {scopeLabel}</span></span>
              <select aria-label={`${isFa ? "دسترسی سند" : "Document access"}: ${document.filename}`} disabled={saving} className="member-input" style={{ width: "auto", maxWidth: "100%" }} value={documentAccess[document.id] || "none"} onChange={(event) => { const value = event.target.value; setDocumentAccess((current) => { const next = { ...current }; if (value === "none") delete next[document.id]; else next[document.id] = value as PermissionLevel; return next; }); }}>
                <option value="none">{isFa ? "بدون مجوز مستقیم" : "No direct grant"}</option><option value="view">{isFa ? "مشاهده" : "View"}</option><option value="edit">{isFa ? "ویرایش" : "Edit"}</option><option value="manage">{isFa ? "مدیریت" : "Manage"}</option>
              </select>
            </label>;
            })}
            {documentsLoading && <p role="status" className="text-xs kb-muted">{isFa ? "در حال دریافت اسناد…" : "Loading documents…"}</p>}
            {!documentsLoading && !documents.length && <p className="text-xs kb-muted">{isFa ? "سندی پیدا نشد." : "No documents found."}</p>}
            {documents.length < documentTotal && <button type="button" disabled={documentsLoading || saving} onClick={() => { setDocumentsLoading(true); setDocumentOffset((value) => value + 25); }} className="chunk-cancel mt-2">{isFa ? "نمایش اسناد بیشتر" : "Load more documents"}</button>}
          </div>
        </>}
      </div>
      <footer className="chunk-settings-footer"><div className="kb-set-footer-actions"><button type="button" disabled={saving} onClick={onClose} className="chunk-cancel">{cancel}</button><button type="submit" disabled={loading || saving || Boolean(error)} className="chunk-save">{saving ? (isFa ? "در حال ذخیره…" : "Saving…") : (isFa ? "ذخیره دسترسی‌ها" : "Save permissions")}</button></div></footer>
    </form>
  </div></div>, document.body);
}
