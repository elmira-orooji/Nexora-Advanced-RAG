import { useState } from "react";
import toast from "react-hot-toast";
import { FileText, Pause, Play, RefreshCw, ScanSearch, X } from "lucide-react";
import DocumentChunkInspector from "../../../components/DocumentChunkInspector";
import InlineError from "../../../components/InlineError";
import { type KnowledgeDocument } from "../../../services/knowledgeService";
import { operationError, processingStageLabel } from "../../../lib/operationFeedback";

export function DocumentRow({ document, isAdmin, isFa, canDelete, onRetry, onPause, onRemove }: { document: KnowledgeDocument; isAdmin: boolean; isFa: boolean; canDelete: boolean; onRetry: () => Promise<void>; onPause: () => Promise<void>; onRemove: () => Promise<void> }) {
  const [retryError, setRetryError] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [pausing, setPausing] = useState(false);
  const ready = document.status === "indexed";
  const active = ["queued", "processing", "paused"].includes(document.status);
  if (ready) return <IndexedDocumentRow document={document} isAdmin={isAdmin} isFa={isFa} canDelete={canDelete} onRemove={onRemove} />;
  if (active) {
    const paused = document.status === "paused";
    // At 95%, extraction has completed and vector indexing belongs to the
    // durable outbox, not the pausable processing job.
    const canPause = !paused && !(document.processing_stage === "indexing" && document.processing_progress >= 95);
    const waiting = paused || ["retry_wait", "requeued", "queued"].includes(document.processing_stage);
    return <div className="group grid grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 px-4 py-3.5 hover:bg-white/[.025]">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-white/[.07] bg-white/[.035] kb-accent">{paused ? <Pause size={16} /> : <RefreshCw size={16} className={waiting ? "" : "animate-spin"} />}</span>
      <div className="min-w-0 flex-1">
        <p className="nexora-file-name text-sm font-semibold kb-text">{document.filename}</p>
        <div className="mt-2 max-w-sm">
          <div className="mb-1 flex justify-between gap-3 text-xs kb-muted"><span>{processingStageLabel(document.processing_stage, isFa)}</span><span className="shrink-0" dir="ltr">{document.processing_progress.toLocaleString(isFa ? "fa-IR" : "en-US")}{isFa ? "٪" : "%"}</span></div>
          {!waiting && <div className="h-1 overflow-hidden rounded-full bg-white/[.06]"><div className="h-full rounded-full bg-gradient-to-r from-[#7c27ff] to-[#c43cff] transition-all duration-500" style={{ width: `${document.processing_progress}%` }} /></div>}
          <p className="nexora-text-wrap mt-1 text-xs kb-muted">{paused ? (isFa ? "با ادامه، استخراج سند از ابتدا شروع می‌شود." : "Resuming restarts document extraction from the beginning.") : (isFa ? "پس از ایندکس‌شدن، پاسخ‌ها می‌توانند از این سند استفاده کنند." : "This document will become available to answers after indexing.")}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {isAdmin && canPause && <button disabled={pausing || retrying} onClick={async () => {
          setRetryError(""); setPausing(true);
          try { await onPause(); }
          catch (error) { setRetryError(operationError(error, "processing", isFa)); }
          finally { setPausing(false); }
        }} title={isFa ? "مکث پردازش" : "Pause processing"} aria-label={isFa ? "مکث پردازش" : "Pause processing"} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted hover:text-[#d9a6ff] disabled:opacity-50"><Pause size={14} /></button>}
        {isAdmin && (paused || document.processing_stage === "retry_wait") && <button disabled={retrying || pausing} onClick={async () => {
          setRetryError(""); setRetrying(true);
          try { await onRetry(); }
          catch (error) { setRetryError(operationError(error, "processing", isFa)); }
          finally { setRetrying(false); }
        }} title={paused ? (isFa ? "ادامهٔ پردازش از ابتدا" : "Resume processing from the beginning") : (isFa ? "تلاش مجدد برای پردازش" : "Retry processing")} aria-label={paused ? (isFa ? "ادامهٔ پردازش" : "Resume processing") : (isFa ? "تلاش مجدد برای پردازش" : "Retry processing")} className="app-icon-button grid size-8 place-items-center rounded-lg text-amber-200/70 hover:text-amber-200 disabled:opacity-50">{paused && !retrying ? <Play size={14} /> : <RefreshCw size={14} className={retrying ? "animate-spin" : ""} />}</button>}
        {canDelete && <button onClick={() => void onRemove()} aria-label={isFa ? "حذف سند و لغو پردازش" : "Delete document and cancel processing"} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted hover:text-rose-300"><X size={14} /></button>}
      </div>
      {document.processing_error && <div className="col-start-2 col-end-3 min-w-0"><InlineError message={operationError(document.processing_error, "processing", isFa)} /></div>}
      {retryError && <div className="col-start-2 col-end-3 min-w-0"><InlineError message={retryError} onDismiss={() => setRetryError("")} /></div>}
    </div>;
  }
  if (document.status === "failed") return <div className="group flex flex-wrap items-center gap-3 px-4 py-3.5 hover:bg-white/[.025]"><span className="grid size-10 shrink-0 place-items-center rounded-xl border border-rose-300/10 bg-rose-300/[.04] text-rose-200/60"><FileText size={17} /></span><div className="min-w-0 flex-1"><p className="nexora-file-name text-sm font-semibold kb-text">{document.filename}</p><p className="nexora-text-wrap mt-1 line-clamp-2 text-xs leading-5 text-rose-200/80">{operationError(document.processing_error, "processing", isFa)}</p></div>{isAdmin && <button onClick={async () => { setRetryError(""); try { await onRetry(); toast.success(isFa ? "پردازش مجدد آغاز شد؛ وضعیت را در همین فهرست دنبال کنید." : "Processing restarted. Follow its status in this list."); } catch (error) { setRetryError(operationError(error, "processing", isFa)); } }} title={isFa ? "تلاش مجدد برای پردازش" : "Retry processing"} aria-label={isFa ? "تلاش مجدد برای پردازش" : "Retry processing"} className="app-icon-button grid size-8 place-items-center rounded-lg text-amber-200/70 hover:text-amber-200"><RefreshCw size={13} /></button>}{canDelete && <button onClick={() => void onRemove()} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted hover:text-rose-300"><X size={14} /></button>}{retryError && <div className="basis-full"><InlineError message={retryError} onDismiss={() => setRetryError("")} /></div>}</div>;
  return <div className="group flex items-center gap-3 px-4 py-3.5 hover:bg-white/[.025]"><span className="grid size-10 shrink-0 place-items-center rounded-xl border border-white/[.07] bg-white/[.035] kb-accent"><FileText size={17} /></span><div className="min-w-0 flex-1"><p className="nexora-file-name text-sm font-semibold kb-text">{document.filename}</p><p className="mt-1 text-xs kb-muted">{new Intl.DateTimeFormat(isFa ? "fa-IR" : "en", { dateStyle: "medium" }).format(new Date(document.created_at))}</p>{document.ocr_provenance && <p className="mt-1 text-xs text-violet-200/80">OCR · {document.ocr_provenance.provider}</p>}</div><span className={`rounded-full border px-2.5 py-1 text-xs ${ready ? "border-emerald-300/10 bg-emerald-300/[.055] text-emerald-200/75" : document.status === "failed" ? "border-rose-300/10 bg-rose-300/[.055] text-rose-200/75" : "border-amber-300/10 bg-amber-300/[.055] text-amber-200/75"}`}>{document.status}</span>{canDelete && <button onClick={() => void onRemove()} title={isFa ? "حذف سند و لغو پردازش" : "Delete document and cancel processing"} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted opacity-100 hover:text-rose-300 md:opacity-0 md:group-hover:opacity-100"><X size={14} /></button>}</div>;
}

function IndexedDocumentRow({ document, isAdmin, isFa, canDelete, onRemove }: { document: KnowledgeDocument; isAdmin: boolean; isFa: boolean; canDelete: boolean; onRemove: () => Promise<void> }) {
  const [inspecting, setInspecting] = useState(false);
  const providerLabel = document.ocr_provenance?.provider === "jina" ? "Jina" : document.ocr_provenance?.provider === "mineru" ? "MinerU" : document.ocr_provenance?.provider;
  const ocrTitle = document.ocr_provenance ? `${providerLabel}${document.ocr_provenance.model ? ` · ${document.ocr_provenance.model}` : ""}` : undefined;
  return <><div className="group flex items-center gap-3 px-4 py-3.5 hover:bg-white/[.025]"><span className="grid size-10 shrink-0 place-items-center rounded-xl border border-white/[.07] bg-white/[.035] kb-accent"><FileText size={17} /></span><div className="min-w-0 flex-1"><p className="nexora-file-name text-sm font-semibold kb-text">{document.filename}</p><p className="mt-1 text-xs kb-muted">{new Intl.DateTimeFormat(isFa ? "fa-IR" : "en", { dateStyle: "medium" }).format(new Date(document.created_at))}</p>{document.ocr_provenance && <p title={ocrTitle} aria-label={isFa ? `متن با OCR سرویس ${providerLabel} استخراج شده است` : `OCR processed by ${providerLabel}`} className="mt-1 text-xs text-violet-200/80">OCR · {providerLabel}</p>}</div><span className="rounded-full border border-emerald-300/10 bg-emerald-300/[.055] px-2.5 py-1 text-xs text-emerald-200/75">{document.status}</span><button onClick={() => setInspecting(true)} title={isFa ? "بازرسی سند و قطعه‌ها" : "Inspect document chunks"} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted hover:text-[#d9a6ff]"><ScanSearch size={14} /></button>{canDelete && <button onClick={() => void onRemove()} title={isFa ? "حذف سند و لغو پردازش" : "Delete document and cancel processing"} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted opacity-100 hover:text-rose-300 md:opacity-0 md:group-hover:opacity-100"><X size={14} /></button>}</div>{inspecting && <DocumentChunkInspector documentId={document.id} isAdmin={isAdmin} isFa={isFa} onClose={() => setInspecting(false)} />}</>;
}
