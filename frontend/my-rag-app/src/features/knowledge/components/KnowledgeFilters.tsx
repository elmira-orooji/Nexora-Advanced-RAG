import { useState } from "react";
import { Check, ChevronDown, Database, FileText, SlidersHorizontal, X, Filter } from "lucide-react";
import { type KnowledgeDocument, type MetadataFilters } from "../../../services/knowledgeService";

export function MetadataFilterBar({ documents, filters, onChange, isFa }: { documents: KnowledgeDocument[]; filters: MetadataFilters; onChange: (value: MetadataFilters) => void; isFa: boolean }) {
  const [open, setOpen] = useState(false);
  const languages = [...new Set(documents.map((item) => item.language).filter(Boolean))] as string[];
  const types = [...new Set(documents.map((item) => item.source_type).filter(Boolean))] as string[];
  const tags = [...new Set(documents.flatMap((item) => item.tags))];
  const count = Object.values(filters).filter((value) => Array.isArray(value) ? value.length : Boolean(value)).length;
  const toggle = (key: "languages" | "source_types" | "tags", value: string) => {
    const current = filters[key] || [];
    onChange({ ...filters, [key]: current.includes(value) ? current.filter((item) => item !== value) : [...current, value] });
  };
  return <div className="mb-2"><button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="metadata-filter-trigger"><Filter size={14} />{isFa ? "فیلتر اطلاعات سند" : "Metadata filters"}{count > 0 && <span>{count}</span>}<ChevronDown size={12} className={open ? "rotate-180" : ""} /></button>
    {open && <section className="metadata-filter-panel" dir={isFa ? "rtl" : "ltr"} aria-label={isFa ? "فیلتر اطلاعات سند" : "Metadata filters"}>
      <header><span>{isFa ? "محدودکردن نتایج" : "Refine results"}</span>{count > 0 && <button type="button" onClick={() => onChange({})}>{isFa ? "پاک‌کردن همه" : "Clear all"}</button>}</header>
      <FilterGroup title={isFa ? "زبان" : "Language"} values={languages} selected={filters.languages || []} onToggle={(value) => toggle("languages", value)} />
      <FilterGroup title={isFa ? "نوع منبع" : "Source type"} values={types} selected={filters.source_types || []} onToggle={(value) => toggle("source_types", value)} />
      <FilterGroup title={isFa ? "برچسب" : "Tags"} values={tags} selected={filters.tags || []} onToggle={(value) => toggle("tags", value)} />
      <fieldset className="metadata-dates"><legend>{isFa ? "بازهٔ تاریخ سند" : "Document date range"}</legend><div>
        <label>{isFa ? "از تاریخ" : "From"}<input type="date" dir="ltr" max={filters.date_to || undefined} value={filters.date_from || ""} onChange={(event) => onChange({ ...filters, date_from: event.target.value || undefined })} /></label>
        <label>{isFa ? "تا تاریخ" : "To"}<input type="date" dir="ltr" min={filters.date_from || undefined} value={filters.date_to || ""} onChange={(event) => onChange({ ...filters, date_to: event.target.value || undefined })} /></label>
      </div></fieldset>
    </section>}
  </div>;
}

function FilterGroup({ title, values, selected, onToggle }: { title: string; values: string[]; selected: string[]; onToggle: (value: string) => void }) {
  if (!values.length) return null;
  return <fieldset className="metadata-filter-group"><legend>{title}</legend><div>{values.map((value) => <button type="button" key={value} aria-pressed={selected.includes(value)} onClick={() => onToggle(value)}>{selected.includes(value) && <Check size={12} />}<span>{value}</span></button>)}</div></fieldset>;
}

export function ScopeSelector({ documents, selectedIds, open, copy, isFa, onToggle, onChange, onClose }: { documents: KnowledgeDocument[]; selectedIds: string[]; open: boolean; copy: Record<string, string>; isFa: boolean; onToggle: () => void; onChange: (ids: string[]) => void; onClose: () => void }) {
  const selectedDocuments = documents.filter((item) => selectedIds.includes(item.id));
  const toggle = (id: string) => onChange(selectedIds.includes(id) ? selectedIds.filter((item) => item !== id) : [...selectedIds, id]);
  return <div className="answer-scope" dir={isFa ? "rtl" : "ltr"} onKeyDown={(event) => { if (event.key === "Escape" && open) { event.stopPropagation(); onClose(); } }}>
    <button type="button" onClick={onToggle} aria-expanded={open} className="metadata-filter-trigger scope-trigger"><SlidersHorizontal size={14} /><span className="scope-trigger-label">{selectedIds.length ? `${selectedIds.length} ${copy.selectedSources}` : copy.allSources}</span><ChevronDown size={12} className={open ? "rotate-180" : ""} /></button>
    {selectedDocuments.length > 0 && <div className="scope-selected">{selectedDocuments.map((document) => <span key={document.id}><FileText size={12} /><span title={document.filename}>{document.filename}</span><button type="button" aria-label={`${isFa ? "حذف از انتخاب" : "Deselect"} ${document.filename}`} onClick={() => toggle(document.id)}><X size={12} /></button></span>)}</div>}
    {open && <><button type="button" aria-label={isFa ? "بستن انتخاب اسناد" : "Close source selector"} onClick={onClose} className="fixed inset-0 z-[59] cursor-default" /><section className="scope-panel" aria-label={copy.chooseSources}>
      <header><div><h3>{copy.chooseSources}</h3><p>{isFa ? "فقط اسناد آماده قابل انتخاب هستند" : "Only ready documents can be selected"}</p></div><button type="button" onClick={onClose} aria-label={isFa ? "بستن" : "Close"}><X size={15} /></button></header>
      <div className="scope-options">
        <button type="button" aria-pressed={selectedIds.length === 0} className="scope-option scope-all" onClick={() => onChange([])}><span className="scope-file-icon"><Database size={16} /></span><span>{copy.allSources}<small>{isFa ? "جست‌وجو در کل مجموعه" : "Search across the entire set"}</small></span><span className="scope-check">{selectedIds.length === 0 && <Check size={12} />}</span></button>
        {documents.length ? documents.map((document) => <button type="button" key={document.id} aria-pressed={selectedIds.includes(document.id)} className="scope-option" onClick={() => toggle(document.id)}><span className="scope-file-icon"><FileText size={16} /></span><span title={document.filename}>{document.filename}</span><span className="scope-check">{selectedIds.includes(document.id) && <Check size={12} />}</span></button>) : <p className="scope-empty">{isFa ? "سند آماده‌ای وجود ندارد" : "No ready documents"}</p>}
      </div>
      <footer><span>{selectedIds.length ? `${selectedIds.length} ${copy.selectedSources}` : copy.allSources}</span><button type="button" onClick={onClose}>{isFa ? "انجام شد" : "Done"}</button></footer>
    </section></>}
  </div>;
}
