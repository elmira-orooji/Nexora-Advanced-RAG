import { confirmAction } from "../services/confirmation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Database, Play, Plus, Square, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { knowledgeService, type EvaluationCase, type MetadataFilters, type PipelineTraceResponse } from "../services/knowledgeService";
import "./RetrievalPlayground.css";

type Props = { setId: string; documentIds: string[]; filters: MetadataFilters; isFa: boolean; canManage: boolean; onClose: () => void };

export default function EvaluationDataset({ setId, documentIds, filters, isFa, canManage, onClose }: Props) {
  const dialogRef = useRef<HTMLElement>(null);
  const [cases, setCases] = useState<EvaluationCase[]>([]); const [loading, setLoading] = useState(true); const [adding, setAdding] = useState(false);
  const [question, setQuestion] = useState(""); const [answer, setAnswer] = useState(""); const [keywords, setKeywords] = useState("");
  const [relevantChunks, setRelevantChunks] = useState("");
  const [running, setRunning] = useState<string | null>(null); const [results, setResults] = useState<Record<string, PipelineTraceResponse>>({});
  const [batchRunning, setBatchRunning] = useState(false); const [batchProgress, setBatchProgress] = useState(0); const stopBatch = useRef(false);
  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    const focusable = dialog?.querySelector<HTMLElement>("button:not(:disabled), input:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex='-1'])");
    (focusable ?? dialog)?.focus();
    return () => previouslyFocused?.focus();
  }, []);

  const handleDialogKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex='-1'])"));
    if (!focusable.length) { event.preventDefault(); dialogRef.current.focus(); return; }
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  const load = useCallback(() => knowledgeService.listEvaluationCases(setId).then(setCases).catch((error) => toast.error((error as Error).message)).finally(() => setLoading(false)), [setId]);
  useEffect(() => { void load(); }, [load]);
  const create = async () => { if (question.trim().length < 2) return; try { const item = await knowledgeService.createEvaluationCase(setId, { question: question.trim(), expected_answer: answer.trim() || null, expected_keywords: keywords.split(",").map((value) => value.trim()).filter(Boolean), relevant_chunk_ids: relevantChunks.split(",").map((value) => value.trim()).filter(Boolean) }); setCases((items) => [item, ...items]); setQuestion(""); setAnswer(""); setKeywords(""); setRelevantChunks(""); setAdding(false); } catch (error) { toast.error((error as Error).message); } };
  const run = async (item: EvaluationCase) => { setRunning(item.id); try { const result = await knowledgeService.tracePipeline(item.question, setId, 5, documentIds, filters); setResults((values) => ({ ...values, [item.id]: result })); } catch (error) { toast.error((error as Error).message); } finally { setRunning(null); } };
  const runAll = async () => {
    if (!cases.length) return; stopBatch.current = false; setBatchRunning(true); setBatchProgress(0); setResults({});
    let completed = 0;
    for (const item of [...cases].reverse()) {
      if (stopBatch.current) break;
      setRunning(item.id);
      try { const result = await knowledgeService.tracePipeline(item.question, setId, 5, documentIds, filters); setResults((values) => ({ ...values, [item.id]: result })); }
      catch (error) { toast.error(`${item.question.slice(0, 35)}: ${(error as Error).message}`); }
      completed += 1; setBatchProgress(completed);
    }
    setRunning(null); setBatchRunning(false);
    if (!stopBatch.current) toast.success(isFa ? "اجرای گروهی تکمیل شد" : "Batch evaluation completed");
  };
  const evaluated = cases.filter((item) => results[item.id]);
  const keywordCoverage = (item: EvaluationCase, result: PipelineTraceResponse) => item.expected_keywords.length ? item.expected_keywords.filter((word) => result.answer.toLocaleLowerCase().includes(word.toLocaleLowerCase())).length / item.expected_keywords.length * 100 : null;
  const retrievalMetrics = (item: EvaluationCase, result: PipelineTraceResponse) => {
    const relevant = new Set(item.relevant_chunk_ids); if (!relevant.size) return null;
    const retrieved = result.results.map((value) => value.chunk_id); const hits = retrieved.filter((id) => relevant.has(id)); const first = retrieved.findIndex((id) => relevant.has(id));
    const cited = result.citations.map((value) => value.chunk_id);
    return { recall: hits.length / relevant.size * 100, mrr: first < 0 ? 0 : 1 / (first + 1), citationPrecision: cited.length ? cited.filter((id) => relevant.has(id)).length / cited.length * 100 : 0 };
  };
  const coverages = evaluated.map((item) => keywordCoverage(item, results[item.id])).filter((value): value is number => value !== null);
  const retrievalScores = evaluated.map((item) => retrievalMetrics(item, results[item.id])).filter((value): value is NonNullable<ReturnType<typeof retrievalMetrics>> => value !== null);
  const summary = evaluated.length ? { grounded: Math.round(evaluated.filter((item) => results[item.id].grounded).length / evaluated.length * 100), recall: retrievalScores.length ? Math.round(retrievalScores.reduce((sum, value) => sum + value.recall, 0) / retrievalScores.length) : null, mrr: retrievalScores.length ? retrievalScores.reduce((sum, value) => sum + value.mrr, 0) / retrievalScores.length : null, citationPrecision: retrievalScores.length ? Math.round(retrievalScores.reduce((sum, value) => sum + value.citationPrecision, 0) / retrievalScores.length) : null, coverage: coverages.length ? Math.round(coverages.reduce((sum, value) => sum + value, 0) / coverages.length) : null, latency: Math.round(evaluated.reduce((sum, item) => sum + results[item.id].total_duration_ms, 0) / evaluated.length) } : null;

  const metrics = summary ? [
    [isFa ? "یادآوری@K" : "Recall@K", summary.recall === null ? "—" : `${summary.recall}%`],
    ["MRR", summary.mrr === null ? "—" : summary.mrr.toFixed(3)],
    [isFa ? "دقت استناد" : "Citation precision", summary.citationPrecision === null ? "—" : `${summary.citationPrecision}%`],
    [isFa ? "پاسخ مستند" : "Groundedness", `${summary.grounded}%`],
    [isFa ? "زمان پاسخ" : "Latency", `${summary.latency} ms`],
  ] : [];

  return <section ref={dialogRef} tabIndex={-1} aria-labelledby="evaluation-dialog-title" onKeyDown={handleDialogKeyDown} className="evaluation-view" dir={isFa ? "rtl" : "ltr"}>
      <header className="evaluation-header">
        <div className="evaluation-title">
          <span className="evaluation-mark" aria-hidden="true"><Database size={18} /></span>
          <div><h2 id="evaluation-dialog-title">{isFa ? "مجموعهٔ ارزیابی" : "Evaluation dataset"}</h2><p>{cases.length.toLocaleString(isFa ? "fa-IR" : "en-US")} {isFa ? "سناریوی ارزیابی" : "evaluation cases"}</p></div>
        </div>
        <div className="evaluation-actions">
          {batchRunning
            ? <button type="button" onClick={() => { stopBatch.current = true; }} aria-label={isFa ? "توقف اجرا" : "Stop run"} title={isFa ? "توقف اجرا" : "Stop run"} className="evaluation-icon-button is-warning"><Square size={14} /></button>
            : <button type="button" disabled={!cases.length || loading} onClick={() => void runAll()} aria-label={isFa ? "اجرای همهٔ سناریوها" : "Run all cases"} title={isFa ? "اجرای همهٔ سناریوها" : "Run all cases"} className="evaluation-icon-button is-primary"><Play size={14} /></button>}
          {canManage && <button type="button" onClick={() => setAdding((value) => !value)} aria-label={isFa ? "افزودن سناریو" : "Add case"} aria-expanded={adding} className={`evaluation-icon-button ${adding ? "is-active" : ""}`}><Plus size={16} /></button>}
          <button type="button" onClick={onClose} aria-label={isFa ? "بازگشت به آزمایشگاه بازیابی" : "Back to retrieval lab"} className="evaluation-icon-button"><ArrowLeft size={16} /></button>
        </div>
      </header>
      {(batchRunning || summary) && <section className="evaluation-summary" aria-label={isFa ? "خلاصهٔ ارزیابی" : "Evaluation summary"}>
        {batchRunning && <div className="evaluation-progress"><div><span>{isFa ? "در حال اجرای گروهی" : "Running batch evaluation"}</span><span dir="ltr">{batchProgress} / {cases.length}</span></div><div className="evaluation-progress-track"><span style={{ width: `${cases.length ? batchProgress / cases.length * 100 : 0}%` }} /></div></div>}
        {summary && <div className="evaluation-metrics">{metrics.map(([label, value]) => <div key={label}><p>{label}</p><strong>{value}</strong></div>)}</div>}
      </section>}
      {adding && <section className="evaluation-form">
        <div className="evaluation-form-fields">
          <label>{isFa ? "سؤال مرجع" : "Reference question"}<input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={isFa ? "سؤال را بنویسید" : "Enter the reference question"} /></label>
          <label>{isFa ? "پاسخ مورد انتظار (اختیاری)" : "Expected answer (optional)"}<textarea value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder={isFa ? "پاسخ مرجع" : "Reference answer"} /></label>
          <label>{isFa ? "کلیدواژه‌های لازم" : "Required keywords"}<input value={keywords} onChange={(event) => setKeywords(event.target.value)} placeholder={isFa ? "با کاما جدا کنید" : "Comma separated"} /></label>
          <label>{isFa ? "شناسهٔ قطعه‌های مرتبط" : "Relevant chunk IDs"}<input value={relevantChunks} onChange={(event) => setRelevantChunks(event.target.value)} placeholder={isFa ? "شناسه‌ها را با کاما جدا کنید" : "Comma-separated chunk UUIDs"} dir="ltr" /></label>
        </div>
        <p className="evaluation-form-hint">{isFa ? "برای محاسبهٔ Recall@K، MRR و دقت استناد، شناسهٔ قطعه‌های مرتبطِ مرجع را وارد کنید." : "Reference relevant chunk IDs are required for Recall@K, MRR, and citation precision."}</p>
        <div className="evaluation-form-actions"><button type="button" onClick={() => setAdding(false)} className="evaluation-secondary-action">{isFa ? "انصراف" : "Cancel"}</button><button type="button" onClick={() => void create()} className="evaluation-primary-action">{isFa ? "افزودن سناریو" : "Add case"}</button></div>
      </section>}
      <div className="evaluation-list">
        {loading ? <div role="status" aria-label={isFa ? "در حال بارگذاری سناریوهای ارزیابی" : "Loading evaluation cases"} className="evaluation-loading"><span /></div>
          : cases.map((item) => {
            const result = results[item.id];
            const answerLower = result?.answer.toLocaleLowerCase() || "";
            const matched = item.expected_keywords.filter((keyword) => answerLower.includes(keyword.toLocaleLowerCase())).length;
            const coverage = item.expected_keywords.length ? Math.round(matched / item.expected_keywords.length * 100) : null;
            const passed = Boolean(result?.grounded && (coverage === null || coverage >= 70));
            return <article key={item.id} className="evaluation-case">
              <div className="evaluation-case-heading"><div className="evaluation-case-copy"><p>{item.question}</p>{item.expected_keywords.length > 0 && <div className="evaluation-keywords">{item.expected_keywords.map((keyword) => <span key={keyword}>{keyword}</span>)}</div>}</div>
                <div className="evaluation-case-actions"><button type="button" disabled={running === item.id || batchRunning} onClick={() => void run(item)} aria-label={isFa ? `اجرای سناریوی ${item.question}` : `Run evaluation: ${item.question}`} className="evaluation-icon-button is-primary"><Play size={13} /></button>{canManage && <button type="button" disabled={batchRunning} aria-label={isFa ? `حذف سناریوی ${item.question}` : `Delete evaluation: ${item.question}`} onClick={async () => { if (!await confirmAction(isFa ? `سناریوی «${item.question}» حذف شود؟` : `Delete evaluation case “${item.question}”?`)) return; try { await knowledgeService.deleteEvaluationCase(setId, item.id); setCases((values) => values.filter((value) => value.id !== item.id)); } catch (error) { toast.error((error as Error).message); } }} className="evaluation-icon-button is-danger"><Trash2 size={13} /></button>}</div>
              </div>
              {result && <div className="evaluation-result"><div className="evaluation-result-meta"><span className={passed ? "is-success" : "is-danger"}>{passed ? "PASS" : "FAIL"}</span><span className={result.grounded ? "is-success" : "is-warning"}>{result.grounded ? (isFa ? "مستند" : "Grounded") : (isFa ? "بدون استناد" : "Ungrounded")}</span><span>{result.citations.length.toLocaleString(isFa ? "fa-IR" : "en-US")} {isFa ? "استناد" : "citations"}</span><span>{result.total_duration_ms.toLocaleString(isFa ? "fa-IR" : "en-US")} {isFa ? "میلی‌ثانیه" : "ms"}</span>{coverage !== null && <span className={coverage >= 70 ? "is-success" : "is-warning"}>{isFa ? "پوشش کلیدواژه" : "Keyword coverage"}: {coverage.toLocaleString(isFa ? "fa-IR" : "en-US")}٪</span>}</div><p>{result.answer}</p></div>}
            </article>;
          })}
        {!loading && !cases.length && <div className="evaluation-empty"><span className="evaluation-empty-mark"><Database size={20} /></span><h3>{isFa ? "هنوز سناریویی ثبت نشده" : "No evaluation cases yet"}</h3><p>{isFa ? "برای سنجش کیفیت بازیابی، یک سناریوی مرجع اضافه کنید." : "Add a reference case to measure retrieval quality."}</p>{canManage && <button type="button" onClick={() => setAdding(true)} className="evaluation-primary-action"><Plus size={15} />{isFa ? "افزودن سناریو" : "Add a case"}</button>}</div>}
      </div>
  </section>;
}
