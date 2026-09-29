import { useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "../styles/knowledge.css";
import "./DocumentChunkInspector.css";
import { Boxes, ChevronRight, Copy, Eye, FileText, Pencil, Power, ScanSearch, Search, Sparkles, Tags, X } from "lucide-react";
import toast from "react-hot-toast";
import InlineError from "./InlineError";
import { knowledgeService, type DocumentChunk, type DocumentDetail } from "../services/knowledgeService";
import { inspectUnicode, type UnicodeFinding } from "../lib/unicodeInspector";
import { findPersianSearchMatches, toPersianSearchKey } from "../lib/persianSearch";

type Props = { documentId: string; isAdmin: boolean; isFa: boolean; onClose: () => void };

export default function DocumentChunkInspector({ documentId, isAdmin, isFa, onClose }: Props) {
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [parentIndex, setParentIndex] = useState<number | null>(null);
  const [selectedChunk, setSelectedChunk] = useState<DocumentChunk | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [operationError, setOperationError] = useState("");

  useEffect(() => {
    let active = true;
    knowledgeService.getDocument(documentId).then((result) => { if (active) setDocument(result); }).catch(() => undefined).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [documentId]);

  useEffect(() => {
    if (document?.content_type !== "application/pdf") return;
    let objectUrl: string | null = null;
    knowledgeService.getDocumentContent(documentId).then((blob) => { objectUrl = URL.createObjectURL(blob); setPreviewUrl(objectUrl); }).catch(() => undefined);
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [document?.content_type, documentId]);

  const parents = useMemo(() => {
    if (!document) return [];
    const needle = toPersianSearchKey(query);
    const groups = new Map<number, { index: number; content: string; children: DocumentChunk[] }>();
    for (const chunk of document.chunks) {
      if (needle && !toPersianSearchKey(chunk.content).includes(needle) && !toPersianSearchKey(chunk.parent_content).includes(needle)) continue;
      const group = groups.get(chunk.parent_index) || { index: chunk.parent_index, content: chunk.parent_content, children: [] };
      group.children.push(chunk); groups.set(chunk.parent_index, group);
    }
    return [...groups.values()].sort((a, b) => a.index - b.index);
  }, [document, query]);

  const parent = parents.find((item) => item.index === parentIndex) || parents[0];
  const tokens = document?.chunks.reduce((sum, chunk) => sum + (chunk.token_count || 0), 0) || 0;

  const chooseChunk = (chunk: DocumentChunk) => { setSelectedChunk(chunk); if (document?.content_type === "application/pdf") setPreviewOpen(true); };
  const updateSelected = async (data: { content?: string; is_active?: boolean }) => {
    if (!document || !selectedChunk) return;
    setSaving(true);
    setOperationError("");
    try {
      const updated = await knowledgeService.updateChunk(document.id, selectedChunk.id, data);
      const next = { ...document, chunks: document.chunks.map((item) => item.id === updated.id ? updated : item) };
      setDocument(next); setSelectedChunk(updated); setEditing(false);
      toast.success(isFa ? "Chunk به‌روزرسانی شد" : "Chunk updated");
    } catch (error) { setOperationError((error as Error).message); }
    finally { setSaving(false); }
  };
  const enrichSelected = async () => {
    if (!document || !selectedChunk) return;
    setSaving(true);
    setOperationError("");
    try {
      const updated = await knowledgeService.enrichChunk(document.id, selectedChunk.id);
      setDocument({ ...document, chunks: document.chunks.map((item) => item.id === updated.id ? updated : item) });
      setSelectedChunk(updated); toast.success(isFa ? "Keyword و سؤال‌ها تولید شدند" : "Keywords and questions generated");
    } catch (error) { setOperationError((error as Error).message); }
    finally { setSaving(false); }
  };

  return createPortal(<div className="app-shell"><div className="kb-page inspector-overlay" style={{ background: "#18213380", fontFamily: isFa ? "Vazirmatn, sans-serif" : "Inter, sans-serif" }} dir={isFa ? "rtl" : "ltr"} onMouseDown={onClose}><aside role="dialog" aria-modal="true" aria-labelledby="inspector-title" onKeyDown={(event) => { if (event.key === "Escape" && !editing) onClose(); }} onMouseDown={(event) => event.stopPropagation()} className="inspector-panel">
    <header className="inspector-header flex h-20 shrink-0 items-center justify-between border-b inspector-border px-5"><div className="flex min-w-0 items-center gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-xl inspector-tint inspector-accent"><Boxes size={18} /></span><div className="min-w-0"><h2 id="inspector-title" className="nexora-file-name text-sm font-semibold">{isFa ? "بازرس سند و قطعه‌ها" : "Document / Chunk Inspector"}</h2><p className="nexora-file-name mt-1 text-xs inspector-muted">{document?.filename || (isFa ? "در حال بارگذاری…" : "Loading…")}</p></div></div><button aria-label={isFa ? "بستن بازرس" : "Close inspector"} onClick={onClose} className="app-icon-button grid size-9 place-items-center rounded-xl"><X size={16} /></button></header>
    {!loading && !document && <p role="alert" className="inspector-empty">{isFa ? "بارگذاری سند انجام نشد. پنجره را ببندید و دوباره تلاش کنید." : "Could not load the document. Close this window and try again."}</p>}
    {loading ? <div className="grid flex-1 place-items-center"><span className="size-5 animate-spin rounded-full border-2 inspector-border border-t-[#c43cff]" /></div> : document && <>
      <div className="inspector-stats grid shrink-0 grid-cols-2 gap-2 border-b inspector-border p-4 sm:grid-cols-4">{[[isFa ? "Parentها" : "Parents", parents.length], [isFa ? "Childها" : "Children", document.chunks.length], [isFa ? "توکن‌ها" : "Tokens", tokens || "—"], [isFa ? "وضعیت" : "Status", document.status]].map(([label, value]) => <div key={label} className="rounded-xl border inspector-border inspector-surface p-3"><p className="text-xs inspector-muted">{label}</p><p className="mt-1 text-xs font-semibold inspector-text">{value}</p></div>)}</div>
      <div className="flex shrink-0 gap-2 border-b inspector-border p-4"><label className="relative min-w-0 flex-1"><Search size={14} className="absolute start-3 top-1/2 -translate-y-1/2 inspector-muted" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={isFa ? "جست‌وجو در متن قطعه‌ها…" : "Search inside chunks…"} className="h-10 w-full rounded-xl border inspector-border inspector-surface ps-9 pe-3 text-xs outline-none focus:inspector-border" /></label>{document.content_type === "application/pdf" && <button disabled={!previewUrl} onClick={() => setPreviewOpen((value) => !value)} className={`flex h-10 shrink-0 items-center gap-2 rounded-xl border px-3 text-xs font-semibold ${previewOpen ? "inspector-border inspector-tint inspector-accent" : "inspector-border inspector-muted"}`}><Eye size={14} /><span className="hidden sm:inline">{isFa ? "پیش‌نمایش PDF" : "PDF preview"}</span></button>}</div>
      {previewOpen && previewUrl && <div className="grid h-[44%] min-h-[260px] shrink-0 border-b inspector-border inspector-subtle md:grid-cols-[1fr_310px]"><iframe title={document.filename} src={`${previewUrl}#page=${selectedChunk?.page_number || 1}&view=FitH`} className="h-full w-full bg-white" /><aside className="min-h-0 overflow-y-auto border-s inspector-border p-4"><div className="flex items-center justify-between"><p className="text-xs font-semibold inspector-accent">{isFa ? "منبع انتخاب‌شده" : "Selected source"}</p>{selectedChunk?.page_number && <span className="rounded-lg inspector-tint px-2 py-1 text-xs inspector-accent">{isFa ? "صفحه" : "Page"} {selectedChunk.page_number}</span>}</div>{selectedChunk ? <HighlightedSource text={selectedChunk.content} query={query} /> : <p className="mt-5 text-xs leading-5 inspector-muted">{isFa ? "یک Child Chunk را انتخاب کنید تا منبع آن برجسته شود." : "Select a child chunk to highlight its source."}</p>}</aside></div>}
      {operationError && <div className="shrink-0 px-4 pt-3"><InlineError message={operationError} onDismiss={() => setOperationError("")} /></div>}
      {selectedChunk && <ChunkEnrichment chunk={selectedChunk} isFa={isFa} isAdmin={isAdmin} saving={saving} onEnrich={() => void enrichSelected()} />}
      {isAdmin && selectedChunk && <div className="shrink-0 border-b inspector-border inspector-tint p-3">{editing ? <div><textarea autoFocus value={draft} onChange={(event) => setDraft(event.target.value)} className="max-h-40 min-h-24 w-full resize-y rounded-xl border inspector-border inspector-subtle p-3 text-xs leading-5 inspector-text outline-none focus:inspector-border" /><div className="mt-2 flex justify-end gap-2"><button onClick={() => setEditing(false)} className="rounded-lg px-3 py-2 text-xs inspector-muted">{isFa ? "انصراف" : "Cancel"}</button><button disabled={saving || draft.trim().length < 20} onClick={() => void updateSelected({ content: draft.trim() })} className="rounded-lg bg-[#7c27ff] px-4 py-2 text-xs font-semibold disabled:opacity-40">{isFa ? "ذخیره تغییرات" : "Save changes"}</button></div></div> : <div className="flex items-center justify-between gap-3"><div className="min-w-0"><p className="truncate text-xs font-semibold inspector-text">CHILD {selectedChunk.chunk_index + 1}</p><p className={`mt-1 text-xs ${selectedChunk.is_active ? "text-emerald-300/55" : "text-amber-300/60"}`}>{selectedChunk.is_active ? (isFa ? "فعال در Retrieval" : "Active in retrieval") : (isFa ? "غیرفعال و خارج از Retrieval" : "Disabled from retrieval")}</p></div><div className="flex gap-2"><button onClick={() => { setDraft(selectedChunk.content); setEditing(true); }} className="flex h-9 items-center gap-1.5 rounded-lg border inspector-border px-3 text-xs inspector-muted"><Pencil size={12} />{isFa ? "ویرایش" : "Edit"}</button><button disabled={saving} onClick={() => void updateSelected({ is_active: !selectedChunk.is_active })} className={`flex h-9 items-center gap-1.5 rounded-lg border px-3 text-xs ${selectedChunk.is_active ? "border-amber-300/15 text-amber-200/60" : "border-emerald-300/15 text-emerald-200/60"}`}><Power size={12} />{selectedChunk.is_active ? (isFa ? "غیرفعال‌کردن" : "Disable") : (isFa ? "فعال‌کردن" : "Enable")}</button></div></div>}</div>}
      <div className="inspector-workspace"><nav aria-label={isFa ? "بخش‌های والد" : "Parent blocks"} className="inspector-nav min-h-0 overflow-y-auto border-e inspector-border p-3">{parents.map((item) => <button key={item.index} aria-pressed={parent?.index === item.index} onClick={() => { setParentIndex(item.index); setSelectedChunk(null); setEditing(false); }} className={`mb-1 flex w-full items-center gap-3 rounded-xl p-3 text-start ${parent?.index === item.index ? "inspector-tint inspector-text" : "inspector-muted hover:inspector-surface"}`}><span className="grid size-8 shrink-0 place-items-center rounded-lg inspector-subtle text-xs font-semibold">P{item.index + 1}</span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-semibold">{isFa ? "بخش والد" : "Parent block"} {item.index + 1}</span><span className="mt-1 block text-xs inspector-muted">{item.children.length} child · {item.content.length} chars</span></span><ChevronRight size={12} /></button>)}</nav>
        <section className="inspector-content min-h-0 overflow-y-auto p-4">{!parent && <p className="inspector-empty">{isFa ? "قطعه‌ای با این جست‌وجو پیدا نشد." : "No chunks match your search."}</p>}{parent && <><div className="rounded-2xl border inspector-border inspector-tint p-4"><div className="mb-3 flex justify-between"><span className="text-xs font-semibold inspector-accent">PARENT {parent.index + 1}</span><span className="text-xs inspector-muted">{parent.content.length} chars</span></div><p className="whitespace-pre-wrap text-xs leading-6 inspector-text">{parent.content}</p></div><UnicodeInspector text={selectedChunk?.content ?? parent.content} isFa={isFa} scope={selectedChunk ? `CHILD ${selectedChunk.chunk_index + 1}` : `PARENT ${parent.index + 1}`} /><p className="my-4 text-xs font-semibold uppercase tracking-[.1em] inspector-muted">{isFa ? "قطعه‌های فرزند" : "Child chunks"}</p><div className="space-y-3">{parent.children.map((chunk) => <button key={chunk.id} aria-pressed={selectedChunk?.id === chunk.id} onClick={() => { chooseChunk(chunk); setEditing(false); }} className={`block w-full rounded-2xl border p-4 text-start transition ${selectedChunk?.id === chunk.id ? "inspector-border inspector-tint" : "inspector-border inspector-surface hover:inspector-surface"}`}><div className="mb-3 flex justify-between gap-2"><span className="flex items-center gap-2 text-xs font-semibold inspector-text"><FileText size={13} className="inspector-accent" />CHILD {chunk.chunk_index + 1}</span><span className="text-xs inspector-muted">{chunk.page_number ? `${isFa ? "صفحه" : "Page"} ${chunk.page_number} · ` : ""}{chunk.content.length} chars</span></div><p className="whitespace-pre-wrap text-xs leading-6 inspector-muted">{chunk.content}</p></button>)}</div></>}</section>
      </div>
    </>}
  </aside></div></div>, window.document.body);
}

function UnicodeInspector({ text, isFa, scope }: { text: string; isFa: boolean; scope: string }) {
  const [error, setError] = useState("");
  const report = useMemo(() => inspectUnicode(text), [text]);
  const findingsCount = report.findings.reduce((sum, finding) => sum + finding.count, 0);
  const copyCodePoint = async (finding: UnicodeFinding) => {
    try {
      await navigator.clipboard.writeText(finding.codePoint);
      toast.success(isFa ? `${finding.codePoint} کپی شد` : `${finding.codePoint} copied`);
    } catch {
      setError(isFa ? "کپی کدپوینت انجام نشد" : "Could not copy code point");
    }
  };

  return <details className="unicode-inspector">
    <summary className="unicode-inspector-summary"><ScanSearch size={15} /><span>{isFa ? "بازرس یونیکد" : "Unicode inspector"}</span><bdi dir="ltr">{scope}</bdi><span className="unicode-inspector-count">{isFa ? `${report.codePointCount} نویسه` : `${report.codePointCount} code points`}</span></summary>
    <div className="unicode-inspector-body"><div className="unicode-inspector-stats"><span>{isFa ? "کدپوینت" : "Code points"}<bdi dir="ltr">{report.codePointCount}</bdi></span><span>{isFa ? "واحد UTF-16" : "UTF-16 units"}<bdi dir="ltr">{report.utf16UnitCount}</bdi></span><span>{isFa ? "رخدادهای ویژه" : "Special occurrences"}<bdi dir="ltr">{findingsCount}</bdi></span></div>{error && <InlineError className="mt-3" message={error} onDismiss={() => setError("")} />}
      <p className="unicode-inspector-note">{isFa ? "تحلیل فقط‌خواندنی است؛ متن اصلی تغییر نمی‌کند. نویسه‌های نامرئی ممکن است عمدی باشند." : "Read-only analysis; the original text is unchanged. Invisible characters may be intentional."}</p>
      {report.findings.length ? <ul className="unicode-inspector-findings">{report.findings.map((finding) => <li key={finding.codePoint} className={`unicode-inspector-finding is-${finding.kind}`}><span className="unicode-inspector-glyph" aria-hidden="true">{finding.kind === "bidi-control" || finding.kind === "invisible-format" ? "◌" : finding.character}</span><div className="unicode-inspector-description"><div className="unicode-inspector-title">{isFa ? finding.labelFa : finding.labelEn}<span>×{finding.count}</span></div><p>{isFa ? finding.detailFa : finding.detailEn}</p></div><button type="button" onClick={() => void copyCodePoint(finding)} aria-label={isFa ? `کپی ${finding.codePoint}` : `Copy ${finding.codePoint}`} title={isFa ? `کپی ${finding.codePoint}` : `Copy ${finding.codePoint}`}><bdi dir="ltr">{finding.codePoint}</bdi><Copy size={12} /></button></li>)}</ul> : <p className="unicode-inspector-empty">{isFa ? "در این بخش از متن، نویسهٔ ویژهٔ قابل‌گزارشی پیدا نشد." : "No notable Unicode characters were found in this text."}</p>}
    </div>
  </details>;
}

function ChunkEnrichment({ chunk, isFa, isAdmin, saving, onEnrich }: { chunk: DocumentChunk; isFa: boolean; isAdmin: boolean; saving: boolean; onEnrich: () => void }) {
  const empty = !chunk.keywords.length && !chunk.suggested_questions.length;
  return <div className="max-h-48 shrink-0 overflow-y-auto border-b inspector-border inspector-surface px-4 py-3"><div className="flex items-center justify-between"><p className="flex items-center gap-2 text-xs font-semibold inspector-muted"><Sparkles size={12} className="inspector-accent" />{isFa ? "درک معنایی Chunk" : "Chunk intelligence"}</p>{isAdmin && <button disabled={saving} onClick={onEnrich} className="rounded-lg border inspector-border px-2.5 py-1.5 text-xs inspector-accent disabled:opacity-40">{empty ? (isFa ? "تولید" : "Generate") : (isFa ? "تولید مجدد" : "Regenerate")}</button>}</div>{empty ? <p className="mt-3 text-xs inspector-muted">{isFa ? "برای این Chunk هنوز Keyword یا سؤال پیشنهادی تولید نشده است." : "No keywords or suggested questions have been generated yet."}</p> : <div className="mt-3 grid gap-3 md:grid-cols-2"><div><p className="mb-2 flex items-center gap-1.5 text-xs inspector-muted"><Tags size={10} />Keywords</p><div className="flex flex-wrap gap-1.5">{chunk.keywords.map((keyword) => <span key={keyword} className="rounded-lg border inspector-border inspector-tint px-2 py-1 text-xs inspector-accent">{keyword}</span>)}</div></div><div><p className="mb-2 text-xs inspector-muted">{isFa ? "سؤال‌های پیشنهادی" : "Suggested questions"}</p><ul className="space-y-1.5">{chunk.suggested_questions.map((question) => <li key={question} className="text-xs leading-4 inspector-muted">• {question}</li>)}</ul></div></div>}</div>;
}

function HighlightedSource({ text, query }: { text: string; query: string }) {
  const ranges = findPersianSearchMatches(text, query);
  if (!ranges.length) return <p className="mt-4 whitespace-pre-wrap rounded-xl inspector-surface p-3 text-xs leading-6 inspector-text">{text}</p>;

  const parts: ReactNode[] = [];
  let cursor = 0;
  for (const [index, range] of ranges.entries()) {
    if (range.start > cursor) parts.push(text.slice(cursor, range.start));
    parts.push(<mark key={index} className="rounded inspector-tint px-0.5 text-white">{text.slice(range.start, range.end)}</mark>);
    cursor = range.end;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return <p className="mt-4 whitespace-pre-wrap rounded-xl inspector-surface p-3 text-xs leading-6 inspector-text">{parts}</p>;
}
