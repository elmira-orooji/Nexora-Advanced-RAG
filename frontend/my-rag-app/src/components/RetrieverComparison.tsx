import { useState } from "react";
import { ArrowLeft, GitCompareArrows, Play } from "lucide-react";
import toast from "react-hot-toast";
import { knowledgeService, type MetadataFilters, type RetrieverComparison as Comparison, type RetrieverConfig } from "../services/knowledgeService";

type Props = { setId: string; query: string; documentIds: string[]; filters: MetadataFilters; isFa: boolean; onClose: () => void };
const initialA: RetrieverConfig = { name: "Balanced", vector_weight: 1, bm25_weight: 1, use_reranker: true, top_k: 5 };
const initialB: RetrieverConfig = { name: "Vector-heavy", vector_weight: 2, bm25_weight: .5, use_reranker: true, top_k: 5 };

export default function RetrieverComparison({ setId, query: initialQuery, documentIds, filters, isFa, onClose }: Props) {
  const [query, setQuery] = useState(initialQuery); const [a, setA] = useState(initialA); const [b, setB] = useState(initialB); const [data, setData] = useState<Comparison | null>(null); const [loading, setLoading] = useState(false);
  const run = async () => { if (query.trim().length < 2) return; setLoading(true); try { setData(await knowledgeService.compareRetrievers(query.trim(), setId, a, b, documentIds, filters)); } catch (error) { toast.error((error as Error).message); } finally { setLoading(false); } };
  return <div className="retriever-compare" dir={isFa ? "rtl" : "ltr"}>
    <header className="retriever-compare-header">
      <div className="retriever-compare-title">
        <span className="retriever-compare-mark"><GitCompareArrows size={18} /></span>
        <div><h2>{isFa ? "مقایسهٔ بازیاب‌ها" : "Retriever comparison"}</h2><p>{isFa ? "دو تنظیم را با پرسش و منابع یکسان مقایسه کنید." : "Compare two configurations with the same question and sources."}</p></div>
      </div>
      <button type="button" onClick={onClose} aria-label={isFa ? "بازگشت" : "Back"} className="retriever-compare-close app-icon-button"><ArrowLeft size={17} /></button>
    </header>
    <form className="retriever-compare-query" onSubmit={(event) => { event.preventDefault(); void run(); }}>
      <label htmlFor="retriever-compare-input">{isFa ? "پرسش" : "Question"}</label>
      <input id="retriever-compare-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={isFa ? "پرسشی برای مقایسه وارد کنید" : "Enter a question to compare"} />
      <button type="submit" disabled={loading || query.trim().length < 2}><Play size={14} />{loading ? (isFa ? "در حال مقایسه…" : "Comparing…") : isFa ? "مقایسه" : "Compare"}</button>
    </form>
    <div className="retriever-compare-body">
      <Variant config={a} onChange={setA} result={data?.variant_a} other={data?.variant_b} isFa={isFa} />
      <Variant config={b} onChange={setB} result={data?.variant_b} other={data?.variant_a} isFa={isFa} right />
    </div>
    {data && <footer className="retriever-compare-footer">{isFa ? `${data.overlap_count} نتیجهٔ مشترک · ${Object.values(data.rank_changes).filter((value) => value !== 0).length} تغییر رتبه` : `${data.overlap_count} shared results · ${Object.values(data.rank_changes).filter((value) => value !== 0).length} rank changes`}</footer>}
  </div>;
}

function Variant({ config, onChange, result, other, isFa, right }: { config: RetrieverConfig; onChange: (value: RetrieverConfig) => void; result?: Comparison["variant_a"]; other?: Comparison["variant_a"]; isFa: boolean; right?: boolean }) {
  const copy = isFa
    ? { vector: "وزن برداری", bm25: "وزن BM25", topK: "تعداد نتایج", reranker: "بازرتبه‌بند", latency: "زمان پاسخ", grounded: "مستند", citations: "منابع", yes: "بله", no: "خیر", answer: "پاسخ", empty: "پس از اجرای مقایسه، نتایج این تنظیم اینجا نمایش داده می‌شود.", unique: "منحصربه‌فرد" }
    : { vector: "Vector weight", bm25: "BM25 weight", topK: "Top K", reranker: "Reranker", latency: "Latency", grounded: "Grounded", citations: "Citations", yes: "Yes", no: "No", answer: "Answer", empty: "Run the comparison to see results for this configuration.", unique: "Unique" };
  return <section className={`retriever-variant ${right ? "is-second" : ""}`}>
    <div className="retriever-variant-heading"><span>{right ? "B" : "A"}</span><p>{isFa ? `تنظیم ${right ? "دوم" : "اول"}` : `Configuration ${right ? "B" : "A"}`}</p></div>
    <input aria-label={isFa ? "نام تنظیم بازیاب" : "Retriever configuration name"} value={config.name} onChange={(event) => onChange({ ...config, name: event.target.value })} className="retriever-variant-name" />
    <div className="retriever-variant-fields">
      <NumberField label={copy.vector} value={config.vector_weight} step={.1} onChange={(value) => onChange({ ...config, vector_weight: value })} />
      <NumberField label={copy.bm25} value={config.bm25_weight} step={.1} onChange={(value) => onChange({ ...config, bm25_weight: value })} />
      <NumberField label={copy.topK} value={config.top_k} step={1} onChange={(value) => onChange({ ...config, top_k: value })} />
    </div>
    <label className="retriever-reranker">{copy.reranker}<input type="checkbox" checked={config.use_reranker} onChange={(event) => onChange({ ...config, use_reranker: event.target.checked })} /></label>
    {result ? <>
      <div className="retriever-result-metrics">{[[copy.latency, `${result.duration_ms} ms`], [copy.grounded, result.grounded ? copy.yes : copy.no], [copy.citations, result.citations.length]].map(([label, value]) => <div key={label}><p>{label}</p><strong>{value}</strong></div>)}</div>
      <div className="retriever-result-list">{result.results.map((item, index) => { const otherRank = other?.results.findIndex((value) => value.chunk_id === item.chunk_id) ?? -1; return <article key={item.chunk_id}><div><span className="nexora-file-name">#{index + 1} · {item.filename}</span><span className={otherRank < 0 ? "is-unique" : ""}>{otherRank < 0 ? copy.unique : `Δ ${(otherRank + 1) - (index + 1)}`}</span></div><p className="nexora-text-wrap">{item.matched_child_content}</p></article>; })}</div>
      <div className="retriever-answer"><p>{copy.answer}</p><div className="nexora-text-wrap">{result.answer}</div></div>
    </> : <p className="retriever-variant-empty">{copy.empty}</p>}
  </section>;
}

function NumberField({ label, value, step, onChange }: { label: string; value: number; step: number; onChange: (value: number) => void }) { return <label className="retriever-number-field">{label}<input type="number" min={0} max={label.toLowerCase().includes("top k") || label.includes("تعداد") ? 8 : 3} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>; }

