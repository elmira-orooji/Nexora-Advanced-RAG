import { createPortal } from "react-dom";
import { useState } from "react";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { BookOpen, Check, Database, FolderKanban, Settings2, X } from "lucide-react";
import InlineError from "../../../components/InlineError";
import { knowledgeService, type DocumentSet } from "../../../services/knowledgeService";

export function ChunkingSettingsDialog({ item, isFa, onClose, onSaved }: { item: DocumentSet; isFa: boolean; onClose: () => void; onSaved: () => void }) {
  const [child, setChild] = useState(item.child_chunk_size);
  const [overlap, setOverlap] = useState(item.chunk_overlap);
  const [parent, setParent] = useState(item.parent_chunk_size);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const valid = [child, overlap, parent].every(Number.isInteger) && child >= 200 && child <= 2000 && overlap >= 0 && overlap <= 500 && overlap < child && parent >= 600 && parent >= child && parent <= 8000;
  const presets = [
    { key: "precise", label: isFa ? "دقیق" : "Precise", values: [500, 80, 1800] },
    { key: "balanced", label: isFa ? "متعادل" : "Balanced", values: [800, 120, 2400] },
    { key: "context", label: isFa ? "متن گسترده" : "Broad context", values: [1200, 180, 3600] },
  ];
  const save = async () => { if (!valid || saving) return; setError(""); setSaving(true); try { await knowledgeService.updateSet(item.id, { child_chunk_size: child, chunk_overlap: overlap, parent_chunk_size: parent }); toast.success(isFa ? "تنظیمات Chunking ذخیره شد" : "Chunking settings saved"); onSaved(); } catch (error) { setError((error as Error).message); } finally { setSaving(false); } };
  return createPortal(<div className="app-shell" style={{ fontFamily: isFa ? "Vazirmatn, sans-serif" : "Inter, sans-serif" }}>
    <div className="kb-page fixed inset-0 z-[90] grid place-items-center p-4 backdrop-blur-sm" style={{ background: "#18213380" }} dir={isFa ? "rtl" : "ltr"} onMouseDown={onClose}>
      <motion.form className="chunk-settings" role="dialog" aria-modal="true" aria-labelledby="chunk-settings-title" initial={{ opacity: 0, scale: .97 }} animate={{ opacity: 1, scale: 1 }} onMouseDown={(event) => event.stopPropagation()} onSubmit={(event) => { event.preventDefault(); void save(); }} onKeyDown={(event) => { if (event.key === "Escape" && !saving) onClose(); }}>
        <header className="chunk-settings-header"><span className="chunk-settings-icon"><Settings2 size={22} /></span><div><h2 id="chunk-settings-title">{isFa ? "تنظیمات Chunking" : "Chunking settings"}</h2><p>{isFa ? "نحوهٔ تقسیم اسناد برای بازیابی و پاسخ‌دهی" : "Fine-tune how your documents are split and retrieved."}</p></div><button type="button" onClick={onClose} aria-label={isFa ? "بستن" : "Close settings"} className="chunk-settings-close"><X size={19} /></button></header>
        <div className="chunk-settings-content">
          <div className="chunk-settings-scope"><Database size={14} /><span>{isFa ? "پایگاه دانش" : "Knowledge base"}</span><strong>{item.name}</strong></div>
          <fieldset className="chunk-presets"><legend>{isFa ? "روش تقسیم متن" : "Chunking profile"}</legend><div>{presets.map((preset, index) => {
            const selected = child === preset.values[0] && overlap === preset.values[1] && parent === preset.values[2];
            return <button type="button" key={preset.key} disabled={saving} aria-pressed={selected} className={selected ? "is-selected" : ""} onClick={() => { setChild(preset.values[0]); setOverlap(preset.values[1]); setParent(preset.values[2]); }}><span className="chunk-preset-name">{preset.label}<span className="chunk-preset-check">{selected && <Check size={12} />}</span></span><small>{(isFa ? ["بخش‌های کوتاه و دقیق", "تعادل دقت و زمینه", "زمینهٔ بیشتر برای پاسخ"] : ["Focused passages", "Precision meets context", "More answer context"])[index]}</small></button>;
          })}</div></fieldset>
          <fieldset className="chunk-fields" disabled={saving}><legend>{isFa ? "تنظیم دقیق" : "Fine-tune parameters"}</legend><div><ChunkNumber label={isFa ? "اندازه Child" : "Child size"} value={child} min={200} max={2000} onChange={setChild} /><ChunkNumber label={isFa ? "هم‌پوشانی" : "Overlap"} value={overlap} min={0} max={500} onChange={setOverlap} /><ChunkNumber label={isFa ? "اندازه Parent" : "Parent size"} value={parent} min={600} max={8000} onChange={setParent} /></div></fieldset>
          <div className="chunk-settings-note"><BookOpen size={17} /><p>{isFa ? "Child کوچک‌تر برای بازیابی دقیق‌تر و Parent بزرگ‌تر برای زمینهٔ بیشتر پاسخ است. هم‌پوشانی باید کمتر از اندازهٔ Child باشد." : "Smaller children focus retrieval; larger parents add answer context. Keep overlap smaller than the child size."}</p></div>
          {!valid && <p role="alert" className="chunk-settings-error">{isFa ? "مقادیر باید در محدودهٔ مشخص‌شده باشند؛ Parent حداقل برابر Child و هم‌پوشانی کمتر از Child باشد." : "Use the indicated ranges. Parent must be at least child size; overlap must be smaller than child size."}</p>}
          {error && <InlineError message={error} onDismiss={() => setError("")} />}
        </div>
        <footer className="chunk-settings-footer"><span>{isFa ? "برای اسناد جدید و پردازش مجدد" : "Applies to new and reprocessed documents"}</span><div><button type="button" onClick={onClose} disabled={saving} className="chunk-cancel">{isFa ? "انصراف" : "Cancel"}</button><button type="submit" disabled={!valid || saving} className="chunk-save">{saving ? (isFa ? "در حال ذخیره…" : "Saving…") : (isFa ? "ذخیره تنظیمات" : "Save settings")}</button></div></footer>
      </motion.form>
    </div>
  </div>, document.body);
}

function ChunkNumber({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return <label className="text-xs font-semibold kb-muted">{label}<input type="number" value={value} min={min} max={max} onChange={(event) => onChange(Number(event.target.value))} className="mt-2 h-11 w-full rounded-xl border border-white/[.09] bg-black/25 px-3 text-sm kb-text outline-none focus:border-[#18c7f4]/45" /><span className="mt-1 block text-xs font-normal kb-muted">{min} – {max} chars</span></label>;
}

export function SetDialog({ mode, item, isFa, copy, onClose, onSaved }: { mode: "create" | "edit"; item?: DocumentSet; isFa: boolean; copy: Record<string, string>; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(item?.name || ""); const [description, setDescription] = useState(item?.description || ""); const [saving, setSaving] = useState(false); const [error, setError] = useState("");
  const submit = async (event: React.FormEvent) => { event.preventDefault(); if (saving || name.trim().length < 2) return; setError(""); setSaving(true); try { if (mode === "create") await knowledgeService.createSet({ name: name.trim(), description: description.trim() }); else if (item) await knowledgeService.updateSet(item.id, { name: name.trim(), description: description.trim() || null }); toast.success(isFa ? "مجموعه ذخیره شد" : "Knowledge set saved"); onSaved(); } catch (error) { setError((error as Error).message); } finally { setSaving(false); } };
  return createPortal(<div className="app-shell" style={{ fontFamily: isFa ? "Vazirmatn, sans-serif" : "Inter, sans-serif" }}>
    <div className="kb-page fixed inset-0 z-[80] grid place-items-center p-4 backdrop-blur-sm" style={{ background: "#18213380" }} dir={isFa ? "rtl" : "ltr"} onMouseDown={onClose}>
      <motion.form className="chunk-settings kb-set-dialog" role="dialog" aria-modal="true" aria-labelledby="set-dialog-title" initial={{ opacity: 0, scale: .97 }} animate={{ opacity: 1, scale: 1 }} onSubmit={submit} onMouseDown={(event) => event.stopPropagation()} onKeyDown={(event) => { if (event.key === "Escape" && !saving) onClose(); }}>
        <header className="chunk-settings-header"><span className="chunk-settings-icon"><FolderKanban size={22} /></span><div><h2 id="set-dialog-title">{mode === "create" ? copy.createTitle : copy.editTitle}</h2><p>{isFa ? "اسناد مرتبط را در یک پایگاه دانش سازمان‌دهی کنید." : "Organize related documents in one knowledge base."}</p></div><button type="button" onClick={onClose} className="chunk-settings-close" aria-label={isFa ? "بستن" : "Close dialog"}><X size={19} /></button></header>
        <div className="chunk-settings-content kb-set-fields">
          <label><span>{copy.name}</span><input autoFocus required disabled={saving} value={name} onChange={(event) => setName(event.target.value)} maxLength={120} placeholder={isFa ? "مثلاً راهنمای پشتیبانی" : "e.g. Support handbook"} /></label>
          <label><span>{copy.description}<small>{isFa ? "اختیاری" : "Optional"}</small></span><textarea disabled={saving} value={description} onChange={(event) => setDescription(event.target.value)} maxLength={500} rows={3} placeholder={isFa ? "این مجموعه شامل چه اطلاعاتی است؟" : "What information belongs in this collection?"} /><small className="kb-set-counter">{description.length} / 500</small></label>
          {error && <InlineError message={error} onDismiss={() => setError("")} />}
        </div>
        <footer className="chunk-settings-footer"><div className="kb-set-footer-actions"><button type="button" onClick={onClose} disabled={saving} className="chunk-cancel">{copy.cancel}</button><button type="submit" disabled={saving || name.trim().length < 2} className="chunk-save">{saving ? (isFa ? "در حال ذخیره…" : "Saving…") : mode === "create" ? copy.create : copy.save}</button></div></footer>
      </motion.form>
    </div>
  </div>, document.body);
}

