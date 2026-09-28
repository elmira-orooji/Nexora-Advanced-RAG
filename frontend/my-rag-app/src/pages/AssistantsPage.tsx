import { confirmAction } from "../services/confirmation";
import { useEffect, useRef, useState } from "react";
import { Bot, ChevronDown, FileStack, MessageSquareText, Pencil, Plus, Power, Search, Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import "../styles/assistants.css";
import { authService } from "../services/authService";
import { assistantService, type AssistantPayload, type CustomAssistant } from "../services/assistantService";
import type { DocumentSet } from "../services/knowledgeService";
import { sectionCopy } from "../locales/copy";

interface AssistantsPageProps {
  onStartConversation: (assistantId: string) => Promise<boolean>;
}

export default function AssistantsPage({ onStartConversation }: AssistantsPageProps) {
  const { i18n, t } = useTranslation(); const fa = i18n.language.startsWith("fa"); const admin = authService.getUser()?.role === "admin";
  const [items, setItems] = useState<CustomAssistant[]>([]); const [sets, setSets] = useState<DocumentSet[]>([]); const [editing, setEditing] = useState<CustomAssistant | "new" | null>(null); const [startingAssistantId, setStartingAssistantId] = useState<string | null>(null); const [loading, setLoading] = useState(true);
  const c = sectionCopy(t, "assistantsPage", ["eyebrow", "title", "subtitle", "add", "empty", "choose", "knowledge", "inactive", "active", "edit", "remove", "noKnowledge", "selectKnowledge", "searchKnowledge", "noKnowledgeMatches"]);
  const load = async () => { try { const [assistants, knowledgeSets] = await Promise.all([assistantService.list(), assistantService.listSets()]); setItems(assistants); setSets(knowledgeSets); } catch (e) { toast.error((e as Error).message); } finally { setLoading(false); } };
  useEffect(() => {
    let active = true;
    Promise.all([assistantService.list(), assistantService.listSets()])
      .then(([assistants, knowledgeSets]) => {
        if (!active) return;
        setItems(assistants);
        setSets(knowledgeSets);
      })
      .catch((error) => { if (active) toast.error((error as Error).message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const choose = async (item: CustomAssistant) => {
    if (!item.is_active || startingAssistantId) return;
    setStartingAssistantId(item.id);
    await onStartConversation(item.id);
    setStartingAssistantId(null);
  };
  const remove = async (item: CustomAssistant) => { if (!await confirmAction(fa ? `دستیار «${item.name}» حذف شود؟` : `Delete “${item.name}”?`)) return; try { await assistantService.remove(item.id); toast.success(fa ? "دستیار حذف شد" : "Assistant deleted"); await load(); } catch (e) { toast.error((e as Error).message); } };
  return <div dir={fa ? "rtl" : "ltr"} className="assistants-page flex h-full min-h-0 overflow-hidden">
    <section className="flex min-w-0 flex-1 flex-col px-4 py-5 sm:px-6 lg:px-8"><header className="assistants-header shrink-0"><div className="assistants-heading-copy"><div className="assistants-eyebrow">{c.eyebrow}</div><div className="assistants-title-row"><h1 className="text-2xl font-semibold tracking-[-.025em]">{c.title}</h1>{admin && <button onClick={() => setEditing("new")} className="assistants-create flex h-10 items-center gap-2 px-4 text-xs font-semibold"><Plus size={15} />{c.add}</button>}</div><p className="mt-2 text-xs leading-6 as-muted">{c.subtitle}</p></div></header>
      <div className="mt-6 grid min-h-0 flex-1 auto-rows-min grid-cols-1 gap-3 overflow-y-auto pb-2 sm:grid-cols-2 xl:grid-cols-3">{loading ? <div className="col-span-full grid min-h-48 place-items-center"><span className="nexora-loader" /></div> : items.length ? items.map((item) => <article key={item.id} className="assistant-card"><div className="flex items-start justify-between"><span className="assistant-emblem"><Bot size={20} /></span><div className="flex items-center gap-1">{!item.is_active && <span className="rounded-full border border-white/10 px-2 py-1 text-xs as-muted">{c.inactive}</span>}{admin && <button aria-label={`${c.edit}: ${item.name}`} onClick={(e) => { e.stopPropagation(); setEditing(item); }} className="app-icon-button grid size-8 place-items-center rounded-lg as-muted hover:text-white"><Pencil size={13} /></button>}{admin && <button aria-label={`${c.remove}: ${item.name}`} onClick={(e) => { e.stopPropagation(); void remove(item); }} className="app-icon-button grid size-8 place-items-center rounded-lg as-muted hover:text-rose-300"><Trash2 size={13} /></button>}</div></div><h2 className="mt-4 text-sm font-semibold"><button type="button" className="assistant-card-select" onClick={() => void choose(item)} disabled={!item.is_active || startingAssistantId !== null}>{startingAssistantId === item.id ? (fa ? "در حال آغاز گفتگو…" : "Starting conversation…") : item.name}</button></h2><p className="mt-2 line-clamp-2 min-h-10 text-xs leading-5 as-muted">{item.description || item.instructions}</p><div className="mt-4 flex items-center gap-2 border-t border-white/[.06] pt-3 text-xs as-muted"><FileStack size={12} /><span className="truncate">{item.document_set_names.length ? `${item.document_set_names.length} ${c.knowledge}` : c.noKnowledge}</span></div><p className="mt-3 flex items-center gap-1.5 text-xs as-muted"><MessageSquareText size={12} />{fa ? "گفتگوی جدید در گفت‌وگوهای اخیر ذخیره می‌شود" : "New chats are saved in Recent chats"}</p></article>) : <div className="assistants-empty col-span-full"><span className="assistants-empty-icon"><Bot size={24} /></span><h2>{c.empty}</h2><p>{fa ? (admin ? "یک دستیار با دستورالعمل و منابع اختصاصی بسازید." : "دستیارهای فعال پس از ایجاد توسط مدیر اینجا نمایش داده می‌شوند.") : (admin ? "Create an assistant with its own instructions and knowledge sources." : "Active assistants will appear here once your administrator creates them.")}</p>{admin && <button type="button" onClick={() => setEditing("new")} className="assistants-create"><Plus size={15} />{c.add}</button>}</div>}</div>
    </section>
    {editing && <AssistantDialog item={editing === "new" ? undefined : editing} sets={sets} fa={fa} onClose={() => setEditing(null)} onSaved={async () => { setEditing(null); await load(); }} />}
  </div>;
}

function AssistantDialog({ item, sets, fa, onClose, onSaved }: { item?: CustomAssistant; sets: DocumentSet[]; fa: boolean; onClose: () => void; onSaved: () => void }) {
  const { t } = useTranslation();
  const pickerCopy = sectionCopy(t, "assistantsPage", ["selectKnowledge", "searchKnowledge", "noKnowledgeMatches"]);
  const [modelId, setModelId] = useState(item?.model_id || "");
  const [models, setModels] = useState<Array<{ id: string; name: string; free: boolean }>>([]);
  const [modelsError, setModelsError] = useState(false);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelAttempt, setModelAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    assistantService.models().then((result) => { if (active) setModels(result); })
      .catch(() => { if (active) setModelsError(true); })
      .finally(() => { if (active) setModelsLoading(false); });
    return () => { active = false; };
  }, [modelAttempt]);
  const [answerMode, setAnswerMode] = useState<"sources" | "hybrid">(item?.answer_mode || "hybrid");
  const [setSearch, setSetSearch] = useState("");
  const filteredSets = sets.filter((set) => set.name.toLocaleLowerCase().includes(setSearch.trim().toLocaleLowerCase()));
  const modalRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const modal = modalRef.current;
    modal?.showModal();
    return () => modal?.close();
  }, []);
  const [name, setName] = useState(item?.name || ""); const [description, setDescription] = useState(item?.description || ""); const [instructions, setInstructions] = useState(item?.instructions || ""); const [selectedSets, setSelectedSets] = useState<string[]>(item?.document_set_ids || []); const [active, setActive] = useState(item?.is_active ?? true); const [saving, setSaving] = useState(false);
  const valid = name.trim().length >= 2 && instructions.trim().length >= 10;
  const submit = async (e: React.FormEvent) => { e.preventDefault(); if (!valid) return; setSaving(true); const payload: AssistantPayload = { model_id: modelId.trim() || null, answer_mode: answerMode, name: name.trim(), description: description.trim(), instructions: instructions.trim(), document_set_ids: selectedSets, is_active: active }; try { if (item) await assistantService.update(item.id, payload); else await assistantService.create(payload); toast.success(fa ? "دستیار ذخیره شد" : "Assistant saved"); onSaved(); } catch (error) { toast.error((error as Error).message); } finally { setSaving(false); } };
  return <dialog ref={modalRef} className="assistant-form-overlay" aria-labelledby="assistant-form-title" onCancel={(event) => { event.preventDefault(); onClose(); }} onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <form onSubmit={submit} onMouseDown={(e) => e.stopPropagation()} className="assistant-dialog assistant-form" dir={fa ? "rtl" : "ltr"}>
      <header className="assistant-form-header">
        <span className="assistant-emblem"><Bot size={20} /></span>
        <div><h2 id="assistant-form-title">{fa ? (item ? "ویرایش دستیار" : "ساخت دستیار") : (item ? "Edit assistant" : "Create assistant")}</h2>
        <p>{fa ? "نقش دستیار و منابع پاسخ‌گویی را مشخص کنید." : "Define its role and choose its knowledge sources."}</p></div>
        <button type="button" onClick={onClose} className="assistant-form-close" aria-label={fa ? "بستن" : "Close"}><X size={18} /></button>
      </header>
      <div className="assistant-form-body">
        <Field label={fa ? "نام" : "Name"}><input autoFocus dir="auto" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={100} placeholder={fa ? "مثلاً دستیار پشتیبانی" : "e.g. Support assistant"} /></Field>
        <Field label={fa ? "توضیح کوتاه (اختیاری)" : "Short description (optional)"}><input dir="auto" maxLength={300} value={description} onChange={(e) => setDescription(e.target.value)} placeholder={fa ? "این دستیار چه کاری انجام می‌دهد؟" : "What does this assistant help with?"} /></Field>
        <Field label={fa ? "دستورالعمل" : "Instructions"}><textarea dir="auto" rows={4} value={instructions} onChange={(e) => setInstructions(e.target.value)} required minLength={10} maxLength={5000} placeholder={fa ? "نقش، محدوده پاسخ و لحن دستیار را مشخص کنید..." : "Define the role, answer boundaries, and tone..."} /></Field>
        <div className="assistant-model-settings">
          <Field label="Models">
            <select dir="ltr" value={modelId} onChange={(e) => setModelId(e.target.value)} aria-busy={modelsLoading}>
              <option value="">{fa ? "پیش‌فرض سرور" : "Server default"}</option>
              <option value="openrouter/free">{fa ? "انتخاب خودکار رایگان" : "Free model router"}</option>
              {modelId && modelId !== "openrouter/free" && !models.some((model) => model.id === modelId) && <option value={modelId}>{modelId}</option>}
              {[true, false].map((free) => <optgroup key={String(free)} label={free ? (fa ? "رایگان" : "Free") : (fa ? "پولی / مبتنی بر مصرف" : "Paid / usage-based")}>
                {models.filter((model) => model.free === free && model.id !== "openrouter/free").map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
              </optgroup>)}
            </select>
            {modelsLoading && <span className="assistant-form-hint" role="status">{fa ? "در حال دریافت مدل‌ها…" : "Loading models…"}</span>}
          </Field>
          <Field label={fa ? "حالت پاسخ" : "Answer mode"}>
            <select value={answerMode} onChange={(e) => setAnswerMode(e.target.value as "sources" | "hybrid")}>
              <option value="hybrid">{fa ? "ترکیبی: منابع و دانش عمومی" : "Hybrid: sources + general knowledge"}</option>
              <option value="sources">{fa ? "فقط منابع" : "Sources only"}</option>
            </select>
          </Field>
          <p className="assistant-form-hint">{fa ? "مدل‌های پولی از اعتبار حساب استفاده می‌کنند." : "Paid models use your account credits."}</p>
          {modelsError && <div className="assistant-form-hint" role="alert">{fa ? "دریافت مدل‌ها ناموفق بود. " : "Could not load models. "}<button type="button" onClick={() => { setModelsError(false); setModelsLoading(true); setModelAttempt((value) => value + 1); }}>{fa ? "تلاش دوباره" : "Retry"}</button></div>}
        </div>
        <fieldset className="assistant-form-knowledge">
          <legend>{fa ? "مجموعه‌های دانش" : "Knowledge sets"}</legend>
          {sets.length > 0 && <details className="assistant-set-picker">
            <summary>
              <span>{selectedSets.length ? (fa ? `${selectedSets.length} مجموعه انتخاب شده` : `${selectedSets.length} selected`) : pickerCopy.selectKnowledge}</span>
              {selectedSets.length > 0 && <span className="assistant-set-count">{selectedSets.length}</span>}
              <ChevronDown className="assistant-set-chevron" size={16} aria-hidden="true" />
            </summary>
            <div className="assistant-set-menu">
              {sets.length > 6 && <label className="assistant-set-search"><Search size={15} aria-hidden="true" /><input type="search" value={setSearch} onChange={(event) => setSetSearch(event.target.value)} placeholder={pickerCopy.searchKnowledge} /></label>}
              <div className="assistant-set-options">
                {filteredSets.map((set) => <label className="assistant-set-option" key={set.id}>
                  <input type="checkbox" checked={selectedSets.includes(set.id)} onChange={(event) => setSelectedSets((current) => event.target.checked ? [...current, set.id] : current.filter((id) => id !== set.id))} />
                  <span dir="auto">{set.name}</span>
                </label>)}
                {!filteredSets.length && <p className="assistant-set-empty">{pickerCopy.noKnowledgeMatches}</p>}
              </div>
            </div>
          </details>}
          {!sets.length && <p className="assistant-form-hint">{fa ? "ابتدا در پایگاه دانش یک مجموعه بسازید." : "Create a knowledge set in Knowledge base first."}</p>}
        </fieldset>
        <button type="button" role="switch" aria-checked={active} onClick={() => setActive(!active)} className="assistant-form-status">
          <span><Power size={15} />{fa ? "دستیار فعال باشد" : "Assistant is active"}</span>
          <span className="assistant-form-toggle" aria-hidden="true"><span /></span>
        </button>
      </div>
      <footer className="assistant-form-footer">
        <button type="button" onClick={onClose} className="assistant-form-cancel">{fa ? "انصراف" : "Cancel"}</button>
        <button type="submit" disabled={!valid || saving} className="assistant-form-save">{saving ? (fa ? "در حال ذخیره…" : "Saving…") : fa ? "ذخیره دستیار" : "Save assistant"}</button>
      </footer>
    </form>
  </dialog>;
}
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="assistant-form-field">{label}<div className="mt-2">{children}</div></label>; }
