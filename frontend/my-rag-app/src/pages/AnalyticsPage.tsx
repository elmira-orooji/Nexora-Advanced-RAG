import { useEffect, useRef, useState, type ReactNode } from "react";
import { Activity, ArrowDownToLine, Bot, ChevronDown, CircleAlert, Database, FileSpreadsheet, FileText, FileCheck2, MessageSquareText, Printer, UsersRound, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import InlineError from "../components/InlineError";

import { analyticsService, type AnalyticsOverview, type DailyMetric, type RankedMetric } from "../services/analyticsService";
import { authService } from "../services/authService";
import { createXlsxWorkbook } from "../services/xlsxExport";
import "../styles/analytics.css";
import { sectionCopy } from "../locales/copy";

const CW = 760, CH = 250, TOP = 18, BOTTOM = 34;
type WorkspaceIssue = AnalyticsOverview["recent_issues"][number];

function issueFingerprint(issue: WorkspaceIssue) {
  return JSON.stringify([issue.kind, issue.name, issue.detail, issue.occurred_at]);
}

function readSeenIssues(storageKey: string): string[] {
  try {
    const stored = localStorage.getItem(storageKey);
    const parsed: unknown = stored ? JSON.parse(stored) : [];
    return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === "string") : [];
  } catch {
    return [];
  }
}

function readSeenFailedCount(storageKey: string): number {
  try {
    const count = Number(localStorage.getItem(storageKey));
    return Number.isFinite(count) && count > 0 ? count : 0;
  } catch {
    return 0;
  }
}

export default function AnalyticsPage({ notificationCenter }: { notificationCenter?: ReactNode }) {
  const { i18n, t } = useTranslation();
  const fa = i18n.language.startsWith("fa");
  const user = authService.getUser();
  const organizationKey = user?.organization_id ?? user?.username ?? "workspace";
  const seenIssuesStorageKey = `nexora:analytics:seen-issues:${organizationKey}`;
  const seenFailedCountStorageKey = `nexora:analytics:seen-failed-count:${organizationKey}`;
  const detailsRef = useRef<HTMLDialogElement>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState<{ days: 7 | 30 | 90; revision: number }>({ days: 30, revision: 0 });
  const [loadedDays, setLoadedDays] = useState<7 | 30 | 90>(30);
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [inlineError, setInlineError] = useState("");
  const [, setSeenIssuesRevision] = useState(0);
  const seenIssues = readSeenIssues(seenIssuesStorageKey);

  useEffect(() => {
    let active = true;
    analyticsService.overview(query.days)
      .then((result) => { if (active) { setData(result); setLoadedDays(query.days); } })
      .catch((error) => { if (active) setInlineError(error.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [query]);

  useEffect(() => {
    if (!exportMenuOpen) return;
    const closeMenu = (event: PointerEvent) => {
      if (!exportMenuRef.current?.contains(event.target as Node)) setExportMenuOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setExportMenuOpen(false); };
    document.addEventListener("pointerdown", closeMenu);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("pointerdown", closeMenu); document.removeEventListener("keydown", closeOnEscape); };
  }, [exportMenuOpen]);

  const selectPeriod = (value: 7 | 30 | 90) => {
    if (value === loadedDays || loading) return;
    setLoading(true);
    setQuery((current) => ({ days: value, revision: current.revision + 1 }));
  };

  const c = sectionCopy(t, "analytics", ["welcome", "subtitle", "export", "exportExcel", "exportCsv", "exportPdf", "exportPdfHint", "exportFailed", "reportTitle", "period", "generatedAt", "dailyData", "date", "negativeFeedback", "queries", "users", "grounded", "satisfaction", "noFeedback", "unanswered", "coverage", "citations", "performance", "performanceSub", "query", "groundedLabel", "health", "indexed", "failed", "healthy", "quality", "positive", "feedbackCoverage", "assistants", "knowledge", "issues", "empty"]);
  const unseenIssueCount = data?.recent_issues.filter((issue) => !seenIssues.includes(issueFingerprint(issue))).length ?? 0;
  const seenFailedDocuments = readSeenFailedCount(seenFailedCountStorageKey);
  const hasUnseenFailedDocuments = (data?.failed_documents ?? 0) > seenFailedDocuments;
  const openDetails = () => {
    if (data) {
      const next = [...new Set([...seenIssues, ...data.recent_issues.map(issueFingerprint)])];
      try { localStorage.setItem(seenIssuesStorageKey, JSON.stringify(next)); } catch { /* Keep the current view usable if storage is unavailable. */ }
      try { localStorage.setItem(seenFailedCountStorageKey, String(data.failed_documents)); } catch { /* Keep the current view usable if storage is unavailable. */ }
      setSeenIssuesRevision((revision) => revision + 1);
    }
    detailsRef.current?.showModal();
  };

  const download = (content: BlobPart, type: string, extension: string) => {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `nexora-analytics-${loadedDays}d.${extension}`; anchor.click();
    URL.revokeObjectURL(url);
  };

  const exportCsv = () => {
    if (!data) return;
    const rows = [[c.date, c.queries, c.grounded, c.negativeFeedback], ...data.daily.map((item) => [formatAnalyticsDate(item.date, fa), item.queries, item.grounded, item.negative_feedback])];
    const csv = rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n");
    download(`\ufeff${csv}`, "text/csv;charset=utf-8", "csv");
  };

  const exportExcel = () => {
    if (!data) return;
    try {
      const reportRows = [[c.reportTitle], [c.period, `${loadedDays} ${fa ? "روز" : "days"}`], [c.generatedAt, new Date().toLocaleString(fa ? "fa-IR" : "en")], [], [c.queries, data.total_queries], [c.users, data.active_users], [c.grounded, `${data.grounded_rate}%`], [c.satisfaction, data.positive_feedback_rate == null ? c.noFeedback : `${data.positive_feedback_rate}%`], [c.health, `${data.indexed_documents} ${c.indexed}`]];
      const dailyRows = [[c.date, c.queries, c.grounded, c.negativeFeedback], ...data.daily.map((item) => [formatAnalyticsDate(item.date, fa), item.queries, item.grounded, item.negative_feedback])];
      download(createXlsxWorkbook([{ name: fa ? "خلاصه" : "Overview", rows: reportRows }, { name: fa ? "داده روزانه" : "Daily data", rows: dailyRows }]), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx");
    } catch { setInlineError(c.exportFailed); }
  };

  const exportPdf = () => {
    if (!data) return;
    const report = window.open("", "_blank");
    if (!report) { setInlineError(c.exportFailed); return; }
    report.opener = null;
    const escape = (value: string | number) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
    const rows = data.daily.map((item) => `<tr><td>${escape(formatAnalyticsDate(item.date, fa))}</td><td>${item.queries}</td><td>${item.grounded}</td><td>${item.negative_feedback}</td></tr>`).join("");
    report.document.write(`<!doctype html><html dir="${fa ? "rtl" : "ltr"}" lang="${fa ? "fa" : "en"}"><head><title>${escape(c.reportTitle)}</title><style>body{font-family:${fa ? "Vazirmatn, Tahoma, sans-serif" : "Inter, Arial, sans-serif"};color:#15203a;padding:32px}h1{font-size:20px}p{color:#52617a}table{width:100%;border-collapse:collapse;margin-top:24px;font-size:12px}th,td{border:1px solid #dce2eb;padding:9px;text-align:start}th{background:#f4f1ff;color:#5520bd}@media print{body{padding:0}}</style></head><body><h1>${escape(c.reportTitle)}</h1><p>${escape(c.period)}: ${loadedDays} ${fa ? "روز" : "days"} · ${escape(c.generatedAt)}: ${escape(new Date().toLocaleString(fa ? "fa-IR" : "en"))}</p><table><thead><tr><th>${escape(c.date)}</th><th>${escape(c.queries)}</th><th>${escape(c.grounded)}</th><th>${escape(c.negativeFeedback)}</th></tr></thead><tbody>${rows}</tbody></table><script>window.onload=()=>window.print()</script></body></html>`);
    report.document.close();
  };

  if (loading && !data) return <div className="analytics-dashboard grid h-full place-items-center an-surface"><span role="status" aria-label={fa ? "در حال بارگذاری" : "Loading"} className="analytics-spinner" /></div>;

  return <div dir={fa ? "rtl" : "ltr"} className="analytics-dashboard analytics-viewport">
    <div className="analytics-content">
      <header className="analytics-header flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div><h1 className="mt-2 text-xl font-semibold tracking-[-.025em] sm:text-[25px]">{c.welcome}, <span className="an-text">{user?.username ?? (fa ? "کاربر" : "User")}</span></h1><p className="mt-1.5 text-xs an-muted">{c.subtitle}</p></div>
        <div className="flex flex-wrap items-center gap-2"><div className="analytics-period" role="group" aria-label={fa ? "بازه زمانی" : "Date range"}>{([7, 30, 90] as const).map((value) => <button key={value} onClick={() => selectPeriod(value)} disabled={loading} aria-pressed={loadedDays === value} className={loadedDays === value ? "is-active" : ""}>{fa ? `${value} روز` : `${value} days`}</button>)}</div>{notificationCenter && <div className="analytics-notification-control">{notificationCenter}</div>}<div className="analytics-export-menu" ref={exportMenuRef}><button type="button" onClick={() => setExportMenuOpen((value) => !value)} disabled={!data || loading} className="analytics-export" aria-haspopup="menu" aria-expanded={exportMenuOpen}><ArrowDownToLine size={13} />{c.export}<ChevronDown size={13} aria-hidden="true" /></button>{exportMenuOpen && <div className="analytics-export-options" role="menu"><button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportExcel(); }}><FileSpreadsheet size={15} aria-hidden="true" /><span>{c.exportExcel}</span></button><button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportCsv(); }}><FileText size={15} aria-hidden="true" /><span>{c.exportCsv}</span></button><button type="button" role="menuitem" title={c.exportPdfHint} onClick={() => { setExportMenuOpen(false); exportPdf(); }}><Printer size={15} aria-hidden="true" /><span>{c.exportPdf}</span></button></div>}</div></div>
      </header>
      {inlineError && <InlineError message={inlineError} onDismiss={() => setInlineError("")} />}

      {data && <>
        <section className="analytics-summary">
          <Metric icon={MessageSquareText} label={c.queries} value={fmt(data.total_queries)} detail={`${data.unanswered_queries} ${c.unanswered}`} />
          <Metric icon={UsersRound} label={c.users} value={fmt(data.active_users)} detail={`${data.feedback_coverage}% ${c.coverage}`} />
          <Metric icon={FileCheck2} label={c.grounded} value={`${data.grounded_rate}%`} detail={`${data.average_citations} ${c.citations}`} />
          <Metric icon={Activity} label={c.satisfaction} value={data.positive_feedback_rate == null ? "—" : `${data.positive_feedback_rate}%`} detail={data.positive_feedback_rate == null ? c.noFeedback : `${data.feedback_coverage}% ${c.coverage}`} />
        </section>

        <section className="analytics-chart-section">
          <Card className="analytics-chart-panel">
            <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5">
              <h2>{c.performance}</h2>
              <div className="flex items-center gap-4 text-xs an-muted">
                <Legend color="var(--an-violet)" label={c.query} />
                <Legend dashed color="var(--an-cyan)" label={c.groundedLabel} />
              </div>
            </div>
            <div className="analytics-chart-body"><TrendChart daily={data.daily} fa={fa} /></div>
          </Card>
        </section>

        <div className="analytics-health-summary">
          <span><Database size={16} aria-hidden="true" />{c.health}</span>
          <span><strong>{fmt(data.indexed_documents)}</strong> {c.indexed}</span>
          {data.failed_documents > 0 && <span className={hasUnseenFailedDocuments ? "an-danger" : "an-muted"}><strong>{fmt(data.failed_documents)}</strong> {c.failed}</span>}
          <span>{c.feedbackCoverage}: {data.feedback_coverage}%</span>
        </div>

        <button type="button" className="analytics-details-button" onClick={openDetails}>
          {fa ? "جزئیات بیشتر" : "More details"}
          {unseenIssueCount > 0 && <span className="an-danger"> · {unseenIssueCount} {c.issues}</span>}
        </button>
        <dialog ref={detailsRef} className="analytics-details-dialog" aria-labelledby="analytics-details-title">
          <header className="analytics-dialog-header">
            <h2 id="analytics-details-title">{fa ? "جزئیات فضای کاری" : "Workspace details"}</h2>
            <button type="button" className="analytics-export" onClick={() => detailsRef.current?.close()}>{fa ? "بستن" : "Close"}</button>
          </header>
        {data.recent_issues.length > 0 && <Card className="mb-4 p-5">
          <h2 className="flex items-center gap-2"><CircleAlert size={16} className={unseenIssueCount ? "an-danger" : "an-muted"} />{c.issues}</h2>
          <ul className="analytics-issues">{data.recent_issues.slice(0, 4).map((item, index) =>
            <li key={`${item.name}-${index}`}><strong>{item.name}</strong><p>{item.detail}</p></li>
          )}</ul>
        </Card>}


          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <Ranking title={c.assistants} icon={Bot} items={data.assistants} empty={c.empty} />
            <Ranking title={c.knowledge} icon={Database} items={data.knowledge_sets} empty={c.empty} />
          </div>
        </dialog>
      </>}
    </div>
  </div>;
}

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`analytics-panel ${className}`}>{children}</div>;
}
function Metric({ icon: Icon, label, value, detail }: { icon: LucideIcon; label: string; value: string; detail: string }) {
  return <div className="analytics-metric" title={detail}>
    <div className="analytics-metric__label"><span>{label}</span><Icon size={16} /></div>
    <p className="analytics-metric__value">{value}</p>
  </div>;
}

function TrendChart({ daily, fa }: { daily: DailyMetric[]; fa: boolean }) {
  const values = daily.length ? daily : [{ date: new Date().toISOString(), queries: 0, grounded: 0, negative_feedback: 0 }];
  const max = Math.max(1, ...values.flatMap((item) => [item.queries, item.grounded]));
  const queries = path(values.map((item) => item.queries), max), grounded = path(values.map((item) => item.grounded), max);
  const area = `${queries} L ${CW},${CH - BOTTOM} L 0,${CH - BOTTOM} Z`;
  return <div dir="ltr" className="analytics-trend relative h-[270px] w-full overflow-hidden"><svg viewBox={`0 0 ${CW} ${CH}`} preserveAspectRatio="none" role="img" aria-label={fa ? "روند پرسش‌ها و پاسخ‌های مستند" : "Queries and grounded answers over time"} className="h-[235px] w-full overflow-visible"><defs><linearGradient id="queryArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--an-violet)" stopOpacity=".26" /><stop offset="1" stopColor="var(--an-violet)" stopOpacity="0" /></linearGradient></defs>{[0, 1, 2, 3, 4].map((row) => { const y = TOP + row * ((CH - TOP - BOTTOM) / 4); return <g key={row}><line x1="0" y1={y} x2={CW} y2={y} stroke="var(--an-line)" strokeWidth="1" /><text x="4" y={y - 5} fill="var(--an-muted)" fontSize="12">{Math.round(max * (1 - row / 4))}</text></g>; })}<path d={area} fill="url(#queryArea)" /><path d={queries} fill="none" stroke="var(--an-violet)" strokeWidth="2.2" vectorEffect="non-scaling-stroke"  /><path d={grounded} fill="none" stroke="var(--an-cyan)" strokeWidth="2" strokeDasharray="5 4" vectorEffect="non-scaling-stroke" /></svg><div className="absolute inset-x-0 bottom-0 flex justify-between px-1 text-xs an-muted">{labels(values.length).map((index) => <span key={index}>{new Date(values[index].date).toLocaleDateString(fa ? "fa-IR" : "en", { month: "short", day: "numeric" })}</span>)}</div></div>;
}

function path(values: number[], max: number) { return values.map((value, index) => { const x = values.length === 1 ? CW / 2 : index / (values.length - 1) * CW; const y = TOP + (1 - value / max) * (CH - TOP - BOTTOM); return `${index ? "L" : "M"} ${x.toFixed(1)},${y.toFixed(1)}`; }).join(" "); }
function formatAnalyticsDate(value: string, fa: boolean) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  const date = match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12) : new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(fa ? "fa-IR-u-ca-persian" : "en-CA", { year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}
function labels(length: number) { if (length <= 5) return Array.from({ length }, (_, index) => index); return [...new Set([0, Math.floor((length - 1) / 4), Math.floor((length - 1) / 2), Math.floor((length - 1) * .75), length - 1])]; }
function Legend({ color, label, dashed = false }: { color: string; label: string; dashed?: boolean }) { return <span className="flex items-center gap-1.5"><span className="w-4 border-t-2" style={{ borderColor: color, borderStyle: dashed ? "dashed" : "solid" }} />{label}</span>; }
function Ranking({ title, icon: Icon, items, empty }: { title: string; icon: LucideIcon; items: RankedMetric[]; empty: string }) { const max = Math.max(1, ...items.map((item) => item.queries)); return <Card className="p-5"><div className="flex items-center justify-between"><h2 className="text-xs font-semibold">{title}</h2><Icon size={15} className="an-muted" /></div><div className="mt-4 space-y-4">{items.length ? items.slice(0, 5).map((item, index) => <div key={item.id || item.name}><div className="mb-2 flex items-center gap-2"><span className="grid size-5 place-items-center rounded an-surface text-xs an-muted">{index + 1}</span><span className="min-w-0 flex-1 truncate text-xs an-muted">{item.name}</span><span className="text-xs an-muted">{item.queries}</span><span className="rounded an-surface px-1.5 py-0.5 text-xs an-muted">{item.grounded_rate}%</span></div><div className="analytics-track ms-7 h-1 overflow-hidden rounded-full"><div className="h-full rounded-full analytics-bar" style={{ width: `${item.queries / max * 100}%` }} /></div></div>) : <Empty text={empty} />}</div></Card>; }
function Empty({ text }: { text: string }) { return <div className="grid min-h-28 place-items-center text-xs an-muted">{text}</div>; }
function fmt(value: number) { return Intl.NumberFormat("en", { notation: value >= 1000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value); }
