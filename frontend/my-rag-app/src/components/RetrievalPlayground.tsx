import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ArrowDown, ArrowUpRight, Play, LoaderCircle, Bot, Database, FlaskConical, GitCompareArrows, ListFilter, Search, Sparkles, X } from "lucide-react";
import InlineError from "./InlineError";
import { knowledgeService, type MetadataFilters, type PipelineTraceResponse } from "../services/knowledgeService";
import "./RetrievalPlayground.css";
import RetrieverComparison from "./RetrieverComparison";
import { useTranslation } from "react-i18next";
import { sectionCopy } from "../locales/copy";

type Props = { setId: string; documentIds: string[]; filters: MetadataFilters; isFa: boolean; onClose: () => void };
const icons = { question: Search, retrieval: ListFilter, rerank: Sparkles, answer: Bot };

export default function RetrievalPlayground({ setId, documentIds, filters, isFa, onClose }: Props) {
  const { t } = useTranslation();
  const panel = useRef<HTMLElement>(null);
  const running = useRef(false);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLInputElement>("#trace-query-input")?.focus();
    return () => { previous?.focus(); };
  }, []);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(5);
  const [loading, setLoading] = useState(false);
  const [trace, setTrace] = useState<PipelineTraceResponse | null>(null);
  const [runError, setRunError] = useState("");
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const run = async () => { if (query.trim().length < 2 || running.current) return; running.current = true; setLoading(true); setRunError(""); try { setTrace(await knowledgeService.tracePipeline(query.trim(), setId, limit, documentIds, filters)); } catch (error) { setRunError((error as Error).message); } finally { running.current = false; setLoading(false); } };

  const labels = sectionCopy(t, "retrieval", ["title", "sub", "placeholder", "run", "total", "grounded", "ungrounded", "empty", "question", "retrieval", "rerank", "answer", "questionDescription", "retrievalDescription", "rerankDescription", "answerDescription"]);

  const steps = ["question", "retrieval", "rerank", "answer"] as const;
  const descriptions = [labels.questionDescription, labels.retrievalDescription, labels.rerankDescription, labels.answerDescription];

  return createPortal(<div className="app-shell trace-overlay" style={{ fontFamily: isFa ? "Vazirmatn, sans-serif" : "Inter, sans-serif" }} onMouseDown={onClose}>
    <aside ref={panel} className="trace-panel" dir={isFa ? "rtl" : "ltr"} role="dialog" aria-modal="true" aria-labelledby="trace-heading" onMouseDown={(event) => event.stopPropagation()} onKeyDown={(event) => {
        if (comparisonOpen) return;
        if (event.key === "Escape") { event.stopPropagation(); onClose(); }
        if (event.key === "Tab") {
          const focusable = Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), summary, [tabindex="0"]') ?? []).filter((element) => element.getClientRects().length > 0);
          const first = focusable[0]; const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
          if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }
      }}>
      <header className="trace-header">
        <div className="trace-heading"><span className="trace-logo"><FlaskConical size={22} /></span><div><p className="trace-eyebrow">{isFa ? "آزمایشگاه بازیابی" : "RETRIEVAL LAB"}</p><h2 id="trace-heading">{labels.title}</h2></div></div>
        <nav className="trace-actions" aria-label={isFa ? "ابزارهای آزمایش" : "Testing tools"}>
          <button onClick={() => setComparisonOpen(true)}><GitCompareArrows size={16} /><span>{isFa ? "مقایسه A/B" : "A/B compare"}</span></button>
          <button className="trace-close" onClick={onClose} aria-label={isFa ? "بستن" : "Close trace"}><X size={19} /></button>
        </nav>
      </header>
      <form className="trace-query" onSubmit={(event) => { event.preventDefault(); void run(); }}>
        <div className="trace-query-heading"><label htmlFor="trace-query-input">{isFa ? "پرسش آزمایشی" : "Test question"}</label><span><Database size={12} />{documentIds.length ? (isFa ? `${documentIds.length} سند انتخاب‌شده` : `${documentIds.length} selected documents`) : (isFa ? "پایگاه دانش فعلی" : "Current knowledge base")}</span></div>
        <div className="trace-query-controls"><div className="trace-input"><Search size={18} /><input id="trace-query-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={labels.placeholder} disabled={loading} /></div>
        <label className="trace-limit"><span>{isFa ? "تعداد نتایج" : "Top K"}</span><select aria-label={isFa ? "تعداد نتایج بازیابی" : "Retrieval result limit"} value={limit} disabled={loading} onChange={(event) => setLimit(Number(event.target.value))}>{[3, 5, 8].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <button className="trace-run" type="submit" disabled={loading || query.trim().length < 2}>{loading ? <LoaderCircle size={16} className="trace-spinner" /> : <Play size={15} />} {loading ? (isFa ? "در حال اجرا…" : "Running…") : labels.run}</button></div>
        <p className="trace-query-hint">{isFa ? "بازیابی، رتبه‌بندی و منابع پاسخ را در یک مسیر بررسی کنید." : "Inspect retrieval, ranking, and answer sources in a single run."}</p>
      </form>
      {runError && <div className="px-6 pt-3"><InlineError message={runError} onDismiss={() => setRunError("")} /></div>}
      <div className="trace-body" aria-busy={loading}>
        {loading && <div className="trace-progress" role="status"><LoaderCircle size={16} className="trace-spinner" />{isFa ? "در حال بازیابی منابع و ساخت پاسخ…" : "Retrieving sources and generating your answer…"}</div>}
        {!trace ? <div className="trace-empty">
          <span className="trace-empty-icon"><FlaskConical size={30} /></span>
          <p className="trace-eyebrow">{isFa ? "از پرسش تا پاسخ" : "FROM QUESTION TO ANSWER"}</p>
          <h3>{isFa ? "پشت صحنهٔ پاسخ را ببینید" : "See how your answer comes together"}</h3>
          <p className="trace-empty-description">{labels.empty}</p>
          <ol className="trace-path">{steps.map((step, index) => { const Icon = icons[step]; return <li key={step}><div className="trace-path-top"><Icon size={20} /><span>0{index + 1}</span></div><h4>{labels[step]}</h4><p>{descriptions[index]}</p>{index < 3 && <ArrowUpRight className="trace-path-arrow" size={14} />}</li>; })}</ol>
          <p className="trace-empty-note">{isFa ? "برای شروع، پرسشی دربارهٔ اسناد این پایگاه دانش وارد کنید." : "Start with a question about the documents in this knowledge base."}</p>
        </div> : <>
      <div className="trace-summary"><div><p>{labels.total}</p><strong>{trace.total_duration_ms.toLocaleString(isFa ? "fa-IR" : "en-US")} ms</strong></div><span className={trace.grounded ? "is-grounded" : "is-ungrounded"}>{trace.grounded ? labels.grounded : labels.ungrounded}</span></div>
      <div className="trace-stage-grid">{trace.stages.map((stage, index) => { const Icon = icons[stage.key]; return <div key={stage.key} className="trace-stage">{index < trace.stages.length - 1 && <ArrowDown size={13} className="trace-stage-arrow" />}<div className="trace-stage-top"><span><Icon size={15} /></span><time>{stage.duration_ms.toLocaleString(isFa ? "fa-IR" : "en-US")} {isFa ? "میلی‌ثانیه" : "ms"}</time></div><p>{labels[stage.key]}</p><small>{isFa ? `${stage.input_count.toLocaleString("fa-IR")} ورودی ← ${stage.output_count.toLocaleString("fa-IR")} خروجی` : `${stage.input_count} in → ${stage.output_count} out`}</small></div>; })}</div>
      <section className="trace-result-card"><p className="trace-result-label">01 · {labels.question}</p><p className="trace-result-question">{trace.question}</p></section>
      <section className="trace-result-card"><p className="trace-result-label">02–03 · {labels.retrieval} + {labels.rerank}</p><div className="trace-result-list">{trace.results.map((item, index) => <details key={`${item.chunk_id}-${index}`}><summary><span className="nexora-file-name">#{(index + 1).toLocaleString(isFa ? "fa-IR" : "en-US")} · {item.filename} · {isFa ? "قطعه" : "Child"} {(item.chunk_index + 1).toLocaleString(isFa ? "fa-IR" : "en-US")}</span><span>{Math.round(item.score * 100).toLocaleString(isFa ? "fa-IR" : "en-US")}{isFa ? "٪" : "%"}</span></summary><div className="trace-diagnostics">{[["Vector", item.diagnostics.vector_rank ?? "—"], ["BM25", item.diagnostics.bm25_rank ?? "—"], [isFa ? "بازرتبه‌بندی" : "Rerank", item.diagnostics.reranker_score.toFixed(3)]].map(([name, value]) => <div key={name}><p>{name}</p><strong>{value}</strong></div>)}</div><p className="nexora-text-wrap">{item.matched_child_content}</p></details>)}</div></section>
      <section className="trace-answer-card"><div><p className="trace-result-label">04 · {labels.answer}</p><span>{trace.citations.length.toLocaleString(isFa ? "fa-IR" : "en-US")} {isFa ? "منبع" : "citations"}</span></div><p className="trace-answer-text">{trace.answer}</p>{trace.citations.length > 0 && <div className="trace-citations">{trace.citations.map((citation) => <span key={citation.id}>[{citation.id.toLocaleString(isFa ? "fa-IR" : "en-US")}] {citation.filename}</span>)}</div>}</section>
      {trace.usage && <section className="trace-usage-grid">{[["Model", trace.usage.model], [isFa ? "زمان پاسخ مدل" : "LLM latency", `${trace.usage.latency_ms} ms`], [isFa ? "ورودی" : "Input", trace.usage.prompt_tokens], [isFa ? "خروجی" : "Output", trace.usage.completion_tokens], [isFa ? "هزینه" : "Cost", `$${trace.usage.estimated_cost_usd.toFixed(6)}`]].map(([label, value]) => <div key={label}><p>{label}</p><strong>{value}</strong></div>)}</section>}
    </>}</div>
    {comparisonOpen && <RetrieverComparison setId={setId} query={query} documentIds={documentIds} filters={filters} isFa={isFa} onClose={() => setComparisonOpen(false)} />}
  </aside></div>, document.body);
}
