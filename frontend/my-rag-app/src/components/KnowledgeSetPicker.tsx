import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

export const ALL_KNOWLEDGE_SETS = "__all_knowledge_sets__";

export default function KnowledgeSetPicker({ sets, value, onChange, isFa, disabled = false }: {
  sets: Array<{ id: string; name: string }>;
  value: string[];
  onChange: (ids: string[]) => void;
  isFa: boolean;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); } };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  const all = value.includes(ALL_KNOWLEDGE_SETS);
  const names = sets.filter((set) => value.includes(set.id)).map((set) => set.name);
  const allLabel = isFa ? "همهٔ پایگاه‌های دانش" : "All knowledge bases";
  const label = all ? allLabel : names.length === 1 ? names[0] : names.length ? (isFa ? `${names.length.toLocaleString("fa-IR")} پایگاه انتخاب شده` : `${names.length} knowledge bases selected`) : (isFa ? "انتخاب پایگاه دانش" : "Select knowledge bases");
  return <div ref={root} className="conversation-knowledge-picker">
    <button ref={trigger} type="button" disabled={disabled || !sets.length} aria-expanded={open} aria-controls={panelId} aria-label={isFa ? "انتخاب پایگاه‌های دانش" : "Select knowledge bases"} title={all ? allLabel : names.join(isFa ? "، " : ", ")} className="conversation-knowledge-picker__trigger" onClick={() => setOpen((current) => !current)}>
      <span>{sets.length ? label : (isFa ? "پایگاه دانشی موجود نیست" : "No knowledge base available")}</span><ChevronDown size={12} />
    </button>
    {open && <div id={panelId} role="group" aria-label={isFa ? "پایگاه‌های دانش" : "Knowledge bases"} className="conversation-knowledge-picker__panel">
      <label className={all ? "is-selected" : ""}><input type="checkbox" disabled={disabled} checked={all} onChange={() => onChange([ALL_KNOWLEDGE_SETS])} /><span>{allLabel}</span></label>
      {sets.map((set) => <label key={set.id} className={value.includes(set.id) ? "is-selected" : ""}>
        <input type="checkbox" disabled={disabled} checked={!all && value.includes(set.id)} onChange={() => onChange(all ? [set.id] : value.includes(set.id) ? value.filter((id) => id !== set.id) : [...value, set.id])} /><span>{set.name}</span>
      </label>)}
    </div>}
  </div>;
}
