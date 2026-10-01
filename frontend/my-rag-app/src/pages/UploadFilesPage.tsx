import { createPortal } from "react-dom";
import { confirmAction } from "../services/confirmation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useDropzone } from "react-dropzone";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  BookOpen, Building2, Check, ChevronDown, Cloud, Database, FileText, FolderKanban, GitBranch as Github, Globe2, Link2, MessageSquareText, MoreHorizontal,
  FlaskConical, PanelRightClose, Pencil, Plus, RefreshCw, ScanSearch, Search, Settings2, SlidersHorizontal, Telescope, Trash2, UploadCloud, Zap, X, Filter,
} from "lucide-react";
import "../styles/knowledge.css";
import ChatInput from "../components/ChatInput";
import ChatWindow from "../components/ChatWindow";
import RetrievalPlayground from "../components/RetrievalPlayground";
import DocumentChunkInspector from "../components/DocumentChunkInspector";
import InlineError from "../components/InlineError";
import { authService } from "../services/authService";
import { knowledgeService, type DocumentSet, type KnowledgeDocument, type MetadataFilters, type ResearchResponse } from "../services/knowledgeService";
import type { ChatMessage } from "../types/chat";
import { connectorService, type Connector, type ConnectorType } from "../services/connectorService";
import { runUploadQueue } from "../lib/uploadQueue";
import { operationError, processingStageLabel } from "../lib/operationFeedback";

const DOCUMENT_POLL_BASE_DELAY = 1_500;
const DOCUMENT_POLL_MAX_DELAY = 30_000;
const MAX_CONCURRENT_UPLOADS = 3;

type UploadTask = {
  id: string;
  filename: string;
  progress: number;
  status: "queued" | "uploading" | "success" | "error";
  error?: string;
};

interface UploadFilesPageProps {
  initialAction?: "create" | "upload";
}

export default function UploadFilesPage({ initialAction }: UploadFilesPageProps) {
  const { i18n, t } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const isAdmin = authService.getUser()?.role === "admin";
  const [sets, setSets] = useState<DocumentSet[]>([]);
  const [selectedSetId, setSelectedSetId] = useState("");
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [chatError, setChatError] = useState("");
  const [uploadTasks, setUploadTasks] = useState<UploadTask[]>([]);
  const [chatOpen, setChatOpen] = useState(() => window.matchMedia("(min-width: 1280px)").matches);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [isChatSlow, setIsChatSlow] = useState(false);
  const [dialog, setDialog] = useState<"create" | "edit" | null>(() => initialAction === "create" && isAdmin ? "create" : null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [connectorDialog, setConnectorDialog] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [answerMode, setAnswerMode] = useState<"quick" | "research">("quick");
  const [metadataFilters, setMetadataFilters] = useState<MetadataFilters>({});
  const [playgroundOpen, setPlaygroundOpen] = useState(false);
  const [chunkingOpen, setChunkingOpen] = useState(false);
  const selectedSetIdRef = useRef(selectedSetId);
  const chatAbortController = useRef<AbortController | null>(null);
  const chatSlowTimer = useRef<number | null>(null);
  const uploading = uploadTasks.some((task) => task.status === "queued" || task.status === "uploading");

  const applyDocuments = useCallback((items: KnowledgeDocument[]) => {
    const availableIds = new Set(items.filter((item) => item.status === "indexed").map((item) => item.id));
    setDocuments(items);
    setSelectedDocumentIds((current) => current.filter((id) => availableIds.has(id)));
  }, []);

  const copy = Object.fromEntries([
    "eyebrow", "title", "subtitle", "sets", "newSet", "allDocs", "documents", "indexed", "drop", "browse", "formats",
    "library", "search", "allStatuses", "empty", "chatTitle", "chatSub", "chatEmpty", "chatHint", "allSources",
    "selectedSources", "chooseSources", "clearSelection", "createTitle", "editTitle", "name", "description", "cancel",
    "save", "create", "edit", "delete", "connect", "connected",
  ].map((key) => [key, t(`knowledge.${key}`)])) as Record<string, string>;

  const selectedSet = sets.find((item) => item.id === selectedSetId);

  const loadSets = useCallback(async () => {
    try {
      const result = await knowledgeService.listSets();
      setSets(result);
      setSelectedSetId((current) => current && result.some((item) => item.id === current) ? current : result[0]?.id || "");
    } catch (error) { setPageError((error as Error).message); }
    finally { setLoading(false); }
  }, []);

  const refreshSetData = useCallback(async (setId: string) => {
    const [nextDocuments, nextConnectors] = await Promise.all([
      knowledgeService.listDocuments(setId),
      connectorService.list(setId),
    ]);
    if (selectedSetIdRef.current !== setId) return;
    applyDocuments(nextDocuments);
    setConnectors(nextConnectors);
  }, [applyDocuments]);

  useEffect(() => { selectedSetIdRef.current = selectedSetId; }, [selectedSetId]);
  useEffect(() => () => {
    chatAbortController.current?.abort();
    if (chatSlowTimer.current !== null) window.clearTimeout(chatSlowTimer.current);
  }, []);
  const initialUploadFocusHandled = useRef(false);
  useEffect(() => {
    if (initialAction !== "upload" || !selectedSetId || initialUploadFocusHandled.current) return;
    initialUploadFocusHandled.current = true;
    const timeoutId = window.setTimeout(() => document.getElementById("knowledge-upload-dropzone")?.focus(), 0);
    return () => window.clearTimeout(timeoutId);
  }, [initialAction, selectedSetId]);
  useEffect(() => {
    let active = true;
    knowledgeService.listSets()
      .then((result) => {
        if (!active) return;
        setSets(result);
        setSelectedSetId((current) => current && result.some((item) => item.id === current) ? current : result[0]?.id || "");
      })
      .catch((error) => { if (active) setPageError((error as Error).message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      if (!selectedSetId) applyDocuments([]);
      else setLoading(true);
      setChatMessages([]);
      setSelectedDocumentIds([]);
      setScopeOpen(false);
    });
    if (!selectedSetId) return () => controller.abort();
    knowledgeService.listDocuments(selectedSetId, controller.signal)
      .then((items) => { if (!controller.signal.aborted) applyDocuments(items); })
      .catch((error) => { if (error instanceof DOMException && error.name === "AbortError") return; setPageError(operationError(error, "load", isFa)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    connectorService.list(selectedSetId, controller.signal)
      .then((items) => { if (!controller.signal.aborted) setConnectors(items); })
      .catch((error) => { if (!(error instanceof DOMException && error.name === "AbortError") && !controller.signal.aborted) setConnectors([]); });
    return () => controller.abort();
  }, [applyDocuments, isFa, selectedSetId]);
  const hasActiveDocuments = documents.some((item) => ["queued", "processing"].includes(item.status));
  useEffect(() => {
    if (!selectedSetId || !hasActiveDocuments) return;
    const controller = new AbortController();
    let timer: number | undefined;
    let retryDelay = DOCUMENT_POLL_BASE_DELAY;
    const poll = async () => {
      try {
        const items = await knowledgeService.listDocuments(selectedSetId, controller.signal);
        if (!controller.signal.aborted) {
          applyDocuments(items);
          retryDelay = DOCUMENT_POLL_BASE_DELAY;
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        retryDelay = Math.min(retryDelay * 2, DOCUMENT_POLL_MAX_DELAY);
      } finally {
        if (!controller.signal.aborted) timer = window.setTimeout(() => void poll(), retryDelay);
      }
    };
    timer = window.setTimeout(() => void poll(), DOCUMENT_POLL_BASE_DELAY);
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [applyDocuments, hasActiveDocuments, selectedSetId]);

  const onDrop = useCallback(async (files: File[]) => {
    if (!selectedSetId || !files.length) return;
    const uploadSetId = selectedSetId;
    const batch = files.map((file) => ({ id: crypto.randomUUID(), file }));
    setUploadTasks(batch.map(({ id, file }) => ({ id, filename: file.name, progress: 0, status: "queued" })));
    const updateTask = (id: string, changes: Partial<UploadTask>) => {
      setUploadTasks((tasks) => tasks.map((task) => task.id === id ? { ...task, ...changes } : task));
    };
    const { succeeded, failed } = await runUploadQueue({
      items: batch,
      concurrency: MAX_CONCURRENT_UPLOADS,
      upload: async (entry, onProgress) => { await knowledgeService.uploadDocument(entry.file, uploadSetId, onProgress, entry.id); },
      onUpdate: (id, changes) => updateTask(id, changes),
    });
    if (succeeded > 0) {
      toast.success(isFa ? `${succeeded.toLocaleString("fa-IR")} فایل با موفقیت بارگذاری شد` : `${succeeded} file${succeeded === 1 ? "" : "s"} uploaded successfully`);
      await refreshSetData(uploadSetId);
      await loadSets();
    }
    if (failed > 0) {
      setPageError(isFa ? `بارگذاری ${failed.toLocaleString("fa-IR")} فایل ناموفق بود. جزئیات هر فایل در صف بارگذاری نمایش داده می‌شود.` : `${failed} file${failed === 1 ? "" : "s"} failed to upload. See the upload queue for details.`);
    }
  }, [isFa, loadSets, refreshSetData, selectedSetId]);

  const { getInputProps, getRootProps, isDragActive, open } = useDropzone({
    onDrop, noClick: true, disabled: !selectedSetId || uploading, maxSize: 100 * 1024 * 1024,
    accept: {
      "application/pdf": [".pdf"],
      "text/plain": [".txt"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/tiff": [".tif", ".tiff"],
    },
    onDropRejected: () => setUploadError(isFa
      ? "فایل PDF، TXT یا تصویر JPG، PNG و TIFF با حجم حداکثر ۱۰۰ مگابایت انتخاب کنید."
      : "Choose a PDF, TXT, JPG, PNG, or TIFF file up to 100 MB."),
  });

  const filtered = useMemo(() => documents.filter((item) =>
    item.filename.toLowerCase().includes(query.toLowerCase()) && (statusFilter === "all" || item.status === statusFilter)
  ), [documents, query, statusFilter]);

  const cancelChatMessage = () => {
    chatAbortController.current?.abort();
    chatAbortController.current = null;
    if (chatSlowTimer.current !== null) window.clearTimeout(chatSlowTimer.current);
    chatSlowTimer.current = null;
    setIsChatSlow(false);
    setIsThinking(false);
  };

  const handleChatMessage = async (content: string) => {
    setChatError("");
    if (!selectedSetId) {
      setChatError(isFa ? "ابتدا یک مجموعه انتخاب کنید" : "Select a knowledge set first");
      return false;
    }
    setChatMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content, createdAt: new Date().toISOString() }]);
    setIsThinking(true);
    setIsChatSlow(false);
    const controller = new AbortController();
    chatAbortController.current = controller;
    chatSlowTimer.current = window.setTimeout(() => setIsChatSlow(true), 8_000);
    try {
      const isResearch = answerMode === "research";
      const result = isResearch
        ? await knowledgeService.research(content, selectedSetId, selectedDocumentIds, metadataFilters, controller.signal)
        : await knowledgeService.ask(content, selectedSetId, selectedDocumentIds, metadataFilters, controller.signal);
      setChatMessages((current) => [...current, {
        id: crypto.randomUUID(), role: "assistant", content: result.answer, responseId: result.response_id, createdAt: new Date().toISOString(),
        grounded: result.grounded,
        research: isResearch ? { steps: (result as ResearchResponse).steps, evidenceReviewed: (result as ResearchResponse).evidence_reviewed } : undefined,
        sources: result.citations.map((citation) => ({
          id: citation.chunk_id,
          citationId: citation.id,
          documentId: citation.document_id,
          title: citation.filename,
          chunkIndex: citation.chunk_index,
          excerpt: citation.excerpt,
          score: citation.score,
          page: citation.page,
          section: citation.section,
          ocrProvenance: citation.ocr_provenance,
        })),
      }]);
      return true;
    } catch (error) {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) return false;
      setChatError(operationError(error, "answer", isFa));
      return false;
    } finally {
      if (chatAbortController.current === controller) {
        chatAbortController.current = null;
        if (chatSlowTimer.current !== null) window.clearTimeout(chatSlowTimer.current);
        chatSlowTimer.current = null;
        setIsChatSlow(false);
        setIsThinking(false);
      }
    }
  };

  const deleteSet = async (set: DocumentSet = selectedSet!) => {
    if (!set || !await confirmAction(isFa ? `مجموعه «${set.name}» حذف شود؟ اسناد حذف نمی‌شوند.` : `Delete “${set.name}”? Documents will be kept.`)) return;
    try { await knowledgeService.deleteSet(set.id); setMenuOpen(false); toast.success(isFa ? "مجموعه حذف شد" : "Set deleted"); await loadSets(); }
    catch (error) { setPageError((error as Error).message); }
  };

  return <div dir={isFa ? "rtl" : "ltr"} className="kb-page relative flex h-full overflow-hidden">
    <main className="kb-main min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8">
      <div className="kb-content mx-auto flex w-full max-w-[980px] flex-col gap-5">
        <header className="kb-header flex shrink-0 items-end justify-between gap-4">
          <div><div className="kb-eyebrow">{copy.eyebrow}</div><h1 className="text-2xl font-semibold tracking-[-.025em]">{copy.title}</h1><p className="mt-2 max-w-2xl text-xs leading-6 kb-muted">{copy.subtitle}</p></div>
          <div className="kb-header-actions flex items-center gap-2">{selectedSet && (isAdmin || selectedSet.access_level === "manage") && <button onClick={() => setChunkingOpen(true)} title={isFa ? "تنظیمات Chunking" : "Chunking settings"} className="app-icon-button grid size-11 place-items-center rounded-xl kb-muted hover:text-[#d9a6ff]"><Settings2 size={16} /></button>}{selectedSetId && <button onClick={() => setPlaygroundOpen(true)} className="app-icon-button flex h-11 items-center gap-2 rounded-xl px-3 text-xs kb-accent sm:px-4"><FlaskConical size={16} /><span className="hidden sm:inline">{isFa ? "آزمایش بازیابی" : "Playground"}</span></button>}{!chatOpen && <button onClick={() => setChatOpen(true)} className="app-icon-button flex h-11 items-center gap-2 rounded-xl px-4 text-sm kb-text sm:flex"><MessageSquareText size={17} />{copy.chatTitle}</button>}</div>
        </header>
        {pageError && <InlineError message={pageError} onDismiss={() => setPageError("")} />}

        <section className="kb-sets shrink-0">
          <div className="kb-sets-header mb-3 flex items-center justify-between"><h2 className="text-xs font-semibold uppercase tracking-[.14em] kb-muted">{copy.sets}</h2>{isAdmin && <button onClick={() => setDialog("create")} className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold kb-accent hover:bg-[#7c27ff]/20"><Plus size={14} />{copy.newSet}</button>}</div>
          <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-white/10">
            {sets.map((item) => {
              const canManageSet = isAdmin || item.access_level === "manage";
              return <article key={item.id} className="kb-set-card-wrap relative">
                <button onClick={() => { selectedSetIdRef.current = item.id; setSelectedSetId(item.id); }} aria-pressed={selectedSetId === item.id} className={`kb-set-card ${selectedSetId === item.id ? "is-active" : ""}`}>
                  <div className="flex items-start justify-between"><span className="kb-set-icon"><FolderKanban size={17} /></span>{selectedSetId === item.id && <span className="kb-selected-dot" />}</div>
                  <p className="nexora-file-name mt-3 text-sm font-semibold kb-text">{item.name}</p><p className="nexora-file-name mt-1 text-xs kb-muted">{item.description || (isFa ? "بدون توضیحات" : "No description")}</p><p className="mt-3 text-xs kb-muted">{item.document_count} {copy.documents} · {item.indexed_document_count} {copy.indexed}</p>
                </button>
                {canManageSet && <button type="button" onClick={() => void deleteSet(item)} aria-label={isFa ? `حذف مجموعه ${item.name}` : `Delete ${item.name}`} title={isFa ? "حذف مجموعه" : "Delete set"} className="kb-set-card-delete app-icon-button grid size-8 place-items-center rounded-lg text-rose-300/70 hover:bg-rose-400/10 hover:text-rose-200"><Trash2 size={14} /></button>}
              </article>;
            })}
            {!loading && !sets.length && <button onClick={() => isAdmin && setDialog("create")} className="grid min-h-[132px] min-w-[230px] place-items-center rounded-2xl border border-dashed border-white/10 text-xs kb-muted"><span className="flex flex-col items-center gap-2"><BookOpen size={20} />{isAdmin ? copy.newSet : (isFa ? "مجموعه‌ای وجود ندارد" : "No knowledge sets")}</span></button>}
          </div>
        </section>

        <div className="kb-set-content flex min-h-0 flex-1 flex-col gap-4">
          {selectedSet && <div className="flex shrink-0 items-center justify-between gap-3"><div className="min-w-0"><h2 className="nexora-file-name text-lg font-semibold">{selectedSet.name}</h2><p className="nexora-file-name mt-1 text-xs kb-muted">{selectedSet.description}</p></div><div className="flex items-center gap-2">{(isAdmin || selectedSet.access_level === "edit" || selectedSet.access_level === "manage") && <button onClick={() => setConnectorDialog(true)} className="kb-connect flex h-9 items-center gap-1.5 px-3 text-xs font-medium"><Link2 size={13} />{copy.connect}</button>}{(isAdmin || selectedSet.access_level === "manage") && <div className="relative"><button aria-label={isFa ? "گزینه‌های مجموعه" : "Set options"} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)} className="app-icon-button grid size-9 place-items-center rounded-xl kb-muted"><MoreHorizontal size={17} /></button>{menuOpen && <div className="nexora-dropdown absolute end-0 top-11 z-30 w-40 rounded-xl border border-white/10 bg-[#15121c] p-1.5 shadow-2xl"><button onClick={() => { setDialog("edit"); setMenuOpen(false); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs kb-text hover:bg-white/5"><Pencil size={13} />{copy.edit}</button><button onClick={() => void deleteSet(selectedSet)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-rose-300/75 hover:bg-rose-400/5"><Trash2 size={13} />{copy.delete}</button></div>}</div>}</div></div>}
          {connectors.length > 0 && <div className="flex shrink-0 gap-2 overflow-x-auto pb-1">{connectors.map((connector) => <ConnectorStatus key={connector.id} connector={connector} syncing={syncingId === connector.id} isFa={isFa} onSync={async () => { const setId = selectedSetId; setSyncingId(connector.id); setPageError(""); try { const result = await connectorService.sync(setId, connector.id); toast.success(isFa ? `${result.created} مورد اضافه و ${result.updated} مورد به‌روزرسانی شد` : `${result.created} created · ${result.updated} updated`); await refreshSetData(setId); await loadSets(); } catch (error) { setPageError(operationError(error, "sync", isFa)); } finally { setSyncingId(null); } }} />)}</div>}
          {(isAdmin || selectedSet?.access_level === "edit" || selectedSet?.access_level === "manage") && selectedSet && <><div id="knowledge-upload-dropzone" tabIndex={-1} {...getRootProps()} onClick={open} className={`knowledge-dropzone flex min-h-28 shrink-0 cursor-pointer items-center justify-center gap-4 rounded-[22px] p-4 transition ${isDragActive ? "is-active" : ""}`}><input {...getInputProps()} /><span className="kb-upload-icon">{uploading ? <span className="size-4 animate-spin rounded-full border-2 border-white/20 border-t-[#d9a6ff]" /> : <UploadCloud size={20} />}</span><div className="text-start"><p className="text-sm font-semibold kb-text">{copy.drop}</p><p className="mt-1 text-xs kb-muted">{copy.browse} · {copy.formats}</p></div></div>{uploadError && <InlineError message={uploadError} onDismiss={() => setUploadError("")} />}</>}
          {uploadTasks.length > 0 && <section className="app-glass-panel shrink-0 rounded-2xl border border-white/[.07] p-3" aria-label={isFa ? "وضعیت بارگذاری فایل‌ها" : "File upload status"}>
            <div className="mb-2 flex items-center justify-between"><p className="text-xs font-semibold kb-muted">{isFa ? "صف بارگذاری" : "Upload queue"}</p>{!uploading && <button type="button" onClick={() => setUploadTasks([])} className="text-xs kb-muted hover:text-white">{isFa ? "پاک‌کردن" : "Clear"}</button>}</div>
            <div className="grid gap-2 sm:grid-cols-2">{uploadTasks.map((task) => <article key={task.id} className="rounded-xl border border-white/[.06] bg-white/[.025] p-2.5" title={task.error}>
              <div className="flex items-center gap-2"><span className={`grid size-7 shrink-0 place-items-center rounded-lg ${task.status === "error" ? "bg-rose-400/10 text-rose-300" : task.status === "success" ? "bg-emerald-400/10 text-emerald-300" : "bg-[#7c27ff]/15 kb-accent"}`}>{task.status === "uploading" ? <RefreshCw size={12} className="animate-spin" /> : task.status === "success" ? <Check size={13} /> : task.status === "error" ? <X size={13} /> : <FileText size={12} />}</span><div className="min-w-0 flex-1"><p className="nexora-file-name text-xs font-medium kb-text">{task.filename}</p><p className={`nexora-text-wrap mt-0.5 text-xs ${task.status === "error" ? "text-rose-300/80" : "kb-muted"}`}>{task.status === "queued" ? (isFa ? "در صف بارگذاری" : "Waiting to upload") : task.status === "uploading" ? (isFa ? `در حال بارگذاری، ${task.progress.toLocaleString("fa-IR")}٪` : `Uploading, ${task.progress}%`) : task.status === "success" ? (isFa ? "بارگذاری شد؛ پردازش در حال شروع است" : "Uploaded; processing is starting") : operationError(task.error, "upload", isFa)}</p></div></div>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[.06]"><div className={`h-full rounded-full transition-[width] duration-200 ${task.status === "error" ? "bg-rose-400/70" : task.status === "success" ? "bg-emerald-400/70" : "bg-gradient-to-r from-[#7c27ff] to-[#c43cff]"}`} style={{ width: `${task.progress}%` }} /></div>
            </article>)}</div>
          </section>}
          <section className="kb-library app-glass-panel flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="kb-library-toolbar flex shrink-0 flex-col gap-3 border-b border-white/[.07] p-4 sm:flex-row sm:items-center sm:justify-between"><h2 className="text-sm font-semibold">{copy.library}</h2><div className="flex gap-2"><label className="relative flex-1 sm:w-56"><Search size={14} className="absolute start-3 top-1/2 -translate-y-1/2 kb-muted" /><input value={query} onChange={(e) => setQuery(e.target.value)} aria-label={copy.search} placeholder={copy.search} className="h-9 w-full rounded-xl border border-white/[.09] bg-white/[.035] ps-9 pe-3 text-xs outline-none placeholder:text-white/20" /></label><label className="relative"><select aria-label={copy.allStatuses} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-9 appearance-none rounded-xl border border-white/[.09] bg-[#0a1530] ps-3 pe-8 text-xs kb-muted"><option value="all">{copy.allStatuses}</option><option value="indexed">Indexed</option><option value="failed">Failed</option></select><ChevronDown size={13} className="absolute end-2.5 top-1/2 -translate-y-1/2 kb-muted" /></label></div></div>
            <div className="kb-document-list min-h-0 flex-1 divide-y divide-white/[.055] overflow-y-auto" tabIndex={0} role="region" aria-label={copy.library}>
{loading ? <div className="grid h-full place-items-center"><span className="nexora-loader" /></div> : filtered.length ? filtered.map((doc) => <DocumentRow key={doc.id} document={doc} isAdmin={isAdmin || selectedSet?.access_level === "edit" || selectedSet?.access_level === "manage"} isFa={isFa} canDelete={isAdmin} onRetry={async () => { await knowledgeService.retryDocument(doc.id); await refreshSetData(selectedSetId); await loadSets(); }} onRemove={async () => { if (!selectedSetId || !await confirmAction(isFa ? `سند «${doc.filename}» برای همیشه حذف و پردازش آن لغو شود؟` : `Permanently delete “${doc.filename}” and cancel its processing?`)) return; try { await knowledgeService.deleteDocument(doc.id); setDocuments((items) => items.filter((item) => item.id !== doc.id)); await loadSets(); toast.success(isFa ? "سند حذف و پردازش آن لغو شد" : "Document deleted and processing cancelled"); } catch (error) { setPageError(operationError(error, "load", isFa)); } }} />) : <div className="grid h-full min-h-28 place-items-center text-xs kb-muted">{selectedSet ? copy.empty : (isFa ? "یک مجموعه انتخاب کنید" : "Select a knowledge set")}</div>}
            </div>
          </section>
        </div>
      </div>
    </main>

    {chatOpen && <button aria-label={isFa ? "بستن دستیار" : "Close assistant"} onClick={() => setChatOpen(false)} className="fixed inset-x-0 bottom-0 top-16 z-40 bg-black/65 backdrop-blur-sm xl:hidden" />}
    <aside className={`knowledge-chat-panel fixed bottom-0 right-0 top-16 z-50 flex w-[min(100%,400px)] flex-col border-s border-white/[.09] transition duration-300 xl:relative xl:inset-auto xl:z-20 ${chatOpen ? "visible translate-x-0 xl:w-[360px]" : "invisible translate-x-full xl:w-0 xl:translate-x-0 xl:overflow-hidden"}`}>
      <div className="flex h-full w-[min(100vw,400px)] flex-col xl:w-[360px]">
        <header className="knowledge-assistant-header flex h-[74px] shrink-0 items-center justify-between px-5">
          <div className="flex min-w-0 items-center gap-3">
            <span className="knowledge-assistant-logo grid size-10 shrink-0 place-items-center rounded-xl"><MessageSquareText size={18} /></span>
            <div className="min-w-0"><h2 className="truncate text-sm font-semibold tracking-[-.01em]">{copy.chatTitle}</h2><p className="mt-1 truncate text-xs">{selectedSet?.name || copy.chatSub}</p></div>
          </div>
          <button aria-label={isFa ? "بستن دستیار" : "Close assistant"} onClick={() => setChatOpen(false)} className="knowledge-assistant-close app-icon-button grid size-9 shrink-0 place-items-center rounded-xl"><PanelRightClose size={17} className={`hidden xl:block ${isFa ? "-scale-x-100" : ""}`} /><X size={17} className="xl:hidden" /></button>
        </header>
        <div className="relative min-h-0 flex-1 p-4">{chatMessages.length ? <ChatWindow messages={chatMessages} isThinking={isThinking} isSlow={isChatSlow} /> : <div className="knowledge-assistant-empty flex h-full flex-col items-center justify-center px-7 text-center"><span className="knowledge-assistant-empty-icon grid size-14 place-items-center rounded-2xl"><img src="/brand/nexora-symbol.svg" alt="" width={24} height={24} /></span><h3 className="mt-5 text-sm font-semibold">{copy.chatEmpty}</h3><p className="mt-2 max-w-[255px] text-xs leading-5">{copy.chatHint}</p><span className="knowledge-assistant-context mt-5 max-w-[250px] truncate rounded-full px-3 py-1.5 text-xs font-medium">{selectedSet?.name || (isFa ? "مجموعه‌ای انتخاب نشده" : "No set selected")}</span></div>}</div>
        <div className="knowledge-assistant-dock relative shrink-0 p-3.5">
          <div className="knowledge-assistant-tools mb-3 grid grid-cols-2 gap-2">
            <MetadataFilterBar documents={documents} filters={metadataFilters} onChange={setMetadataFilters} isFa={isFa} />
            <ScopeSelector documents={documents.filter((item) => item.status === "indexed")} selectedIds={selectedDocumentIds} open={scopeOpen} copy={copy} isFa={isFa} onToggle={() => setScopeOpen((value) => !value)} onChange={setSelectedDocumentIds} onClose={() => setScopeOpen(false)} />
          </div>
          <div className="knowledge-answer-mode mb-3 grid grid-cols-2 gap-1 p-1" role="group" aria-label={isFa ? "حالت پاسخ" : "Answer mode"}>
            <button onClick={() => setAnswerMode("quick")} aria-pressed={answerMode === "quick"} className={answerMode === "quick" ? "is-active" : ""}><Zap size={13} /><span>{isFa ? "پاسخ سریع" : "Quick answer"}</span></button>
            <button onClick={() => setAnswerMode("research")} aria-pressed={answerMode === "research"} className={answerMode === "research" ? "is-active" : ""}><Telescope size={13} /><span>{isFa ? "پژوهش عمیق" : "Deep research"}</span></button>
          </div>
          {chatError && <InlineError className="mb-3" message={chatError} onDismiss={() => setChatError("")} />}
          <ChatInput disabled={isThinking || !selectedSetId} isSending={isThinking} onSend={handleChatMessage} onCancel={cancelChatMessage} />
        </div>
      </div>
    </aside>
    {dialog && <SetDialog mode={dialog} item={dialog === "edit" ? selectedSet : undefined} isFa={isFa} copy={copy} onClose={() => setDialog(null)} onSaved={async () => { setDialog(null); await loadSets(); }} />}
    {connectorDialog && selectedSetId && <CloudConnectorDialog setId={selectedSetId} isFa={isFa} onClose={() => setConnectorDialog(false)} onSaved={async () => { const setId = selectedSetId; setConnectorDialog(false); await refreshSetData(setId); await loadSets(); }} />}
    {playgroundOpen && selectedSetId && <RetrievalPlayground setId={selectedSetId} documentIds={selectedDocumentIds} filters={metadataFilters} isFa={isFa} onClose={() => setPlaygroundOpen(false)} />}
    {chunkingOpen && selectedSet && <ChunkingSettingsDialog item={selectedSet} isFa={isFa} onClose={() => setChunkingOpen(false)} onSaved={async () => { setChunkingOpen(false); await loadSets(); }} />}
  </div>;
}

function MetadataFilterBar({ documents, filters, onChange, isFa }: { documents: KnowledgeDocument[]; filters: MetadataFilters; onChange: (value: MetadataFilters) => void; isFa: boolean }) {
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

function ScopeSelector({ documents, selectedIds, open, copy, isFa, onToggle, onChange, onClose }: { documents: KnowledgeDocument[]; selectedIds: string[]; open: boolean; copy: Record<string, string>; isFa: boolean; onToggle: () => void; onChange: (ids: string[]) => void; onClose: () => void }) {
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

function ConnectorStatus({ connector, syncing, isFa, onSync }: { connector: Connector; syncing: boolean; isFa: boolean; onSync: () => Promise<void> }) {
  const failed = connector.status === "failed";
  const ready = connector.status === "ready";
  const label = syncing ? (isFa ? "در حال همگام‌سازی" : "Syncing now") : failed ? (isFa ? "همگام‌سازی ناموفق" : "Sync failed") : ready ? (isFa ? "آماده" : "Ready") : (isFa ? "در انتظار همگام‌سازی" : "Waiting to sync");
  return <div className="min-w-[185px] shrink-0 rounded-xl border border-white/[.07] bg-white/[.025] p-2.5" aria-label={`${connector.name}: ${label}`}>
    <div className="flex items-center gap-2"><span className="kb-accent">{connector.connector_type === "github" ? <Github size={13} /> : <Globe2 size={13} />}</span><span className="min-w-0 flex-1 truncate text-xs font-medium kb-text">{connector.name}</span><button type="button" title={failed ? (isFa ? "تلاش مجدد برای همگام‌سازی" : "Retry sync") : (isFa ? "همگام‌سازی اکنون" : "Sync now")} aria-label={failed ? (isFa ? "تلاش مجدد برای همگام‌سازی" : "Retry sync") : (isFa ? "همگام‌سازی اکنون" : "Sync now")} disabled={syncing} onClick={() => void onSync()} className="app-icon-button grid size-7 place-items-center rounded-lg kb-muted hover:text-white"><RefreshCw size={12} className={syncing ? "animate-spin" : ""} /></button></div>
    <p className={`mt-2 text-xs ${failed ? "text-rose-300/85" : ready ? "text-emerald-300/85" : "text-amber-200/80"}`}>{label}</p>
    {failed && <p className="mt-1 line-clamp-2 text-xs leading-5 kb-muted">{operationError(connector.last_error, "sync", isFa)}</p>}
  </div>;
}

function DocumentRow({ document, isAdmin, isFa, canDelete, onRetry, onRemove }: { document: KnowledgeDocument; isAdmin: boolean; isFa: boolean; canDelete: boolean; onRetry: () => Promise<void>; onRemove: () => Promise<void> }) {
  const [retryError, setRetryError] = useState("");
  const ready = document.status === "indexed";
  const active = ["queued", "processing"].includes(document.status);
  if (ready) return <IndexedDocumentRow document={document} isAdmin={isAdmin} isFa={isFa} canDelete={canDelete} onRemove={onRemove} />;
if (active) return <div className="group flex items-center gap-3 px-4 py-3.5 hover:bg-white/[.025]"><span className="grid size-10 shrink-0 place-items-center rounded-xl border border-white/[.07] bg-white/[.035] kb-accent"><RefreshCw size={16} className="animate-spin" /></span><div className="min-w-0 flex-1"><p className="nexora-file-name text-sm font-semibold kb-text">{document.filename}</p><div className="mt-2 max-w-sm"><div className="mb-1 flex justify-between text-xs kb-muted"><span>{processingStageLabel(document.processing_stage, isFa)}</span><span>{document.processing_progress}%</span></div><div className="h-1 overflow-hidden rounded-full bg-white/[.06]"><div className="h-full rounded-full bg-gradient-to-r from-[#7c27ff] to-[#c43cff] transition-all duration-500" style={{ width: `${document.processing_progress}%` }} /></div><p className="nexora-text-wrap mt-1 text-xs kb-muted">{isFa ? "پس از ایندکس‌شدن، پاسخ‌ها می‌توانند از این سند استفاده کنند." : "This document will become available to answers after indexing."}</p></div></div>{canDelete && <button onClick={() => void onRemove()} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted hover:text-rose-300"><X size={14} /></button>}</div>;
  if (document.status === "failed") return <div className="group flex flex-wrap items-center gap-3 px-4 py-3.5 hover:bg-white/[.025]"><span className="grid size-10 shrink-0 place-items-center rounded-xl border border-rose-300/10 bg-rose-300/[.04] text-rose-200/60"><FileText size={17} /></span><div className="min-w-0 flex-1"><p className="nexora-file-name text-sm font-semibold kb-text">{document.filename}</p><p className="nexora-text-wrap mt-1 line-clamp-2 text-xs leading-5 text-rose-200/80">{operationError(document.processing_error, "processing", isFa)}</p></div>{isAdmin && <button onClick={async () => { setRetryError(""); try { await onRetry(); toast.success(isFa ? "پردازش مجدد آغاز شد؛ وضعیت را در همین فهرست دنبال کنید." : "Processing restarted. Follow its status in this list."); } catch (error) { setRetryError(operationError(error, "processing", isFa)); } }} title={isFa ? "تلاش مجدد برای پردازش" : "Retry processing"} aria-label={isFa ? "تلاش مجدد برای پردازش" : "Retry processing"} className="app-icon-button grid size-8 place-items-center rounded-lg text-amber-200/70 hover:text-amber-200"><RefreshCw size={13} /></button>}{canDelete && <button onClick={() => void onRemove()} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted hover:text-rose-300"><X size={14} /></button>}{retryError && <div className="basis-full"><InlineError message={retryError} onDismiss={() => setRetryError("")} /></div>}</div>;
  return <div className="group flex items-center gap-3 px-4 py-3.5 hover:bg-white/[.025]"><span className="grid size-10 shrink-0 place-items-center rounded-xl border border-white/[.07] bg-white/[.035] kb-accent"><FileText size={17} /></span><div className="min-w-0 flex-1"><p className="nexora-file-name text-sm font-semibold kb-text">{document.filename}</p><p className="mt-1 text-xs kb-muted">{new Intl.DateTimeFormat(isFa ? "fa-IR" : "en", { dateStyle: "medium" }).format(new Date(document.created_at))}</p>{document.ocr_provenance && <p className="mt-1 text-xs text-violet-200/80">OCR · {document.ocr_provenance.provider}</p>}</div><span className={`rounded-full border px-2.5 py-1 text-xs ${ready ? "border-emerald-300/10 bg-emerald-300/[.055] text-emerald-200/75" : document.status === "failed" ? "border-rose-300/10 bg-rose-300/[.055] text-rose-200/75" : "border-amber-300/10 bg-amber-300/[.055] text-amber-200/75"}`}>{document.status}</span>{canDelete && <button onClick={() => void onRemove()} title={isFa ? "حذف سند و لغو پردازش" : "Delete document and cancel processing"} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted opacity-100 hover:text-rose-300 md:opacity-0 md:group-hover:opacity-100"><X size={14} /></button>}</div>;
}

function IndexedDocumentRow({ document, isAdmin, isFa, canDelete, onRemove }: { document: KnowledgeDocument; isAdmin: boolean; isFa: boolean; canDelete: boolean; onRemove: () => Promise<void> }) {
  const [inspecting, setInspecting] = useState(false);
  const providerLabel = document.ocr_provenance?.provider === "jina" ? "Jina" : document.ocr_provenance?.provider === "mineru" ? "MinerU" : document.ocr_provenance?.provider;
  const ocrTitle = document.ocr_provenance ? `${providerLabel}${document.ocr_provenance.model ? ` · ${document.ocr_provenance.model}` : ""}` : undefined;
  return <><div className="group flex items-center gap-3 px-4 py-3.5 hover:bg-white/[.025]"><span className="grid size-10 shrink-0 place-items-center rounded-xl border border-white/[.07] bg-white/[.035] kb-accent"><FileText size={17} /></span><div className="min-w-0 flex-1"><p className="nexora-file-name text-sm font-semibold kb-text">{document.filename}</p><p className="mt-1 text-xs kb-muted">{new Intl.DateTimeFormat(isFa ? "fa-IR" : "en", { dateStyle: "medium" }).format(new Date(document.created_at))}</p>{document.ocr_provenance && <p title={ocrTitle} aria-label={isFa ? `متن با OCR سرویس ${providerLabel} استخراج شده است` : `OCR processed by ${providerLabel}`} className="mt-1 text-xs text-violet-200/80">OCR · {providerLabel}</p>}</div><span className="rounded-full border border-emerald-300/10 bg-emerald-300/[.055] px-2.5 py-1 text-xs text-emerald-200/75">{document.status}</span><button onClick={() => setInspecting(true)} title={isFa ? "بازرسی سند و قطعه‌ها" : "Inspect document chunks"} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted hover:text-[#d9a6ff]"><ScanSearch size={14} /></button>{canDelete && <button onClick={() => void onRemove()} title={isFa ? "حذف سند و لغو پردازش" : "Delete document and cancel processing"} className="app-icon-button grid size-8 place-items-center rounded-lg kb-muted opacity-100 hover:text-rose-300 md:opacity-0 md:group-hover:opacity-100"><X size={14} /></button>}</div>{inspecting && <DocumentChunkInspector documentId={document.id} isAdmin={isAdmin} isFa={isFa} onClose={() => setInspecting(false)} />}</>;
}

function CloudConnectorDialog(props: { setId: string; isFa: boolean; onClose: () => void; onSaved: () => void }) {
  const { setId, isFa, onClose, onSaved } = props;
  const [type, setType] = useState<ConnectorType>("google_drive");
  const [name, setName] = useState(""); const [url, setUrl] = useState(""); const [saving, setSaving] = useState(false); const [webhookInfo, setWebhookInfo] = useState<{ endpoint: string; secret: string } | null>(null); const [error, setError] = useState("");
  if (!setId) return <ConnectorDialog {...props} />;
  const options: { type: ConnectorType; label: string; icon: React.ReactNode }[] = [
    { type: "google_drive", label: "Google Drive", icon: <Cloud size={15} /> },
    { type: "s3", label: "Amazon S3", icon: <Database size={15} /> },
    { type: "sharepoint", label: "SharePoint", icon: <Building2 size={15} /> },
    { type: "webhook", label: "Webhook", icon: <Zap size={15} /> },
    { type: "website", label: "Website", icon: <Globe2 size={15} /> },
    { type: "github", label: "GitHub", icon: <Github size={15} /> },
  ];
  const placeholders: Record<ConnectorType, string> = {
    google_drive: "https://drive.google.com/drive/folders/FOLDER_ID",
    s3: "https://bucket.s3.eu-central-1.amazonaws.com/prefix",
    sharepoint: "https://graph.microsoft.com/v1.0/drives/DRIVE_ID/items/FOLDER_ID/children",
    website: "https://example.com/docs", github: "https://github.com/owner/repository", webhook: "Generated automatically",
  };
  const valid = name.trim().length >= 2 && (type === "webhook" || /^https:\/\//i.test(url.trim()));
  const submit = async (event: React.FormEvent) => { event.preventDefault(); if (!valid) return; setError(""); setSaving(true); try { if (type === "webhook") { const created = await connectorService.createWebhook(setId, name.trim()); setWebhookInfo({ endpoint: created.endpoint, secret: created.secret }); return; } const connector = await connectorService.create(setId, { connector_type: type, name: name.trim(), source_url: url.trim() }); const result = await connectorService.sync(setId, connector.id); toast.success(isFa ? `${result.created} سند وارد شد` : `${result.created} documents imported`); onSaved(); } catch (error) { setError((error as Error).message); } finally { setSaving(false); } };
  if (webhookInfo) return createPortal(<div className="app-shell"><div className="kb-page fixed inset-0 z-[85] grid place-items-center p-4 backdrop-blur-sm" style={{ background: "#18213380", fontFamily: isFa ? "Vazirmatn, sans-serif" : "Inter, sans-serif" }} dir={isFa ? "rtl" : "ltr"}><div className="app-glass-panel w-full max-w-xl rounded-[24px] border border-white/10 p-6"><span className="grid size-10 place-items-center rounded-xl bg-[#7c27ff]/30 kb-accent"><Zap size={18} /></span><h2 className="mt-4 text-xl font-semibold">{isFa ? "Webhook آماده است" : "Webhook is ready"}</h2><p className="mt-2 text-xs leading-5 text-amber-100/45">{isFa ? "Secret فقط همین یک‌بار نمایش داده می‌شود؛ اکنون آن را ذخیره کنید." : "The secret is shown only once. Store it securely now."}</p>{([['Endpoint', webhookInfo.endpoint], ['X-Webhook-Secret', webhookInfo.secret]] as const).map(([label, value]) => <div key={label} className="mt-4"><p className="mb-2 text-xs font-semibold kb-muted">{label}</p><div className="flex items-center gap-2 rounded-xl border border-white/[.08] bg-black/25 p-2"><code className="min-w-0 flex-1 overflow-x-auto px-2 text-xs kb-text">{value}</code><button type="button" onClick={() => { void navigator.clipboard.writeText(value); toast.success("Copied"); }} className="rounded-lg bg-white/[.06] px-3 py-2 text-xs kb-muted">Copy</button></div></div>)}<button type="button" onClick={onSaved} className="mt-6 w-full rounded-xl bg-[#7c27ff] px-5 py-3 text-xs font-semibold">{isFa ? "انجام شد" : "Done"}</button></div></div></div>, document.body);
  return createPortal(<div className="app-shell" style={{ fontFamily: isFa ? "Vazirmatn, sans-serif" : "Inter, sans-serif" }}><div className="kb-page fixed inset-0 z-[85] grid place-items-center p-4 backdrop-blur-sm" style={{ background: "#18213380" }} dir={isFa ? "rtl" : "ltr"} onMouseDown={onClose}>
    <motion.form className="chunk-settings connector-settings" role="dialog" aria-modal="true" aria-labelledby="connector-title" initial={{ opacity: 0, scale: .97 }} animate={{ opacity: 1, scale: 1 }} onSubmit={submit} onMouseDown={(event) => event.stopPropagation()} onKeyDown={(event) => { if (event.key === "Escape" && !saving) onClose(); }}>
      <header className="chunk-settings-header"><span className="chunk-settings-icon"><Link2 size={22} /></span><div><h2 id="connector-title">{isFa ? "اتصال منبع جدید" : "Connect a new source"}</h2><p>{isFa ? "منبع ابری یا عمومی را به این پایگاه دانش متصل کنید." : "Connect a cloud or public source to this knowledge base."}</p></div><button type="button" onClick={onClose} className="chunk-settings-close" aria-label={isFa ? "بستن" : "Close connection dialog"}><X size={19} /></button></header>
      <div className="chunk-settings-content">
        <fieldset className="chunk-presets connector-options" disabled={saving}><legend>{isFa ? "انتخاب منبع" : "Choose a source"}</legend><div>{options.map((option) => <button type="button" key={option.type} aria-pressed={type === option.type} className={type === option.type ? "is-selected" : ""} onClick={() => { setType(option.type); setUrl(""); }}><span className="connector-option-icon">{option.icon}</span><span>{option.label}</span><span className="chunk-preset-check">{type === option.type && <Check size={12} />}</span></button>)}</div></fieldset>
        <div className="kb-set-fields connector-fields"><label><span>{isFa ? "نام اتصال" : "Connection name"}</span><input autoFocus required minLength={2} maxLength={120} disabled={saving} value={name} onChange={(event) => setName(event.target.value)} placeholder={options.find((option) => option.type === type)?.label} /></label>
        {type !== "webhook" && <label><span>{isFa ? "آدرس منبع" : "Source URL"}<small>HTTPS</small></span><input type="url" required dir="ltr" disabled={saving} value={url} onChange={(event) => setUrl(event.target.value)} placeholder={placeholders[type]} /></label>}</div>
        <div className="chunk-settings-note"><Link2 size={17} /><p>{type === "webhook" ? (isFa ? "پس از ساخت اتصال، آدرس دریافت رویداد و کلید محرمانه نمایش داده می‌شود." : "Create the connection to generate an endpoint and a secret for incoming events.") : type === "google_drive" ? (isFa ? "اطلاعات OAuth گوگل باید روی سرور تنظیم شده باشد. آدرس یک پوشه را وارد کنید." : "Google OAuth credentials must be configured on the server. Enter a folder URL.") : type === "s3" ? (isFa ? "آدرس HTTPS باکت یا پیشوند S3 را وارد کنید. اطلاعات دسترسی روی سرور می‌ماند." : "Enter an S3 bucket or prefix HTTPS URL. Credentials stay on the server.") : type === "sharepoint" ? (isFa ? "آدرس Microsoft Graph با مسیر children برای پوشهٔ موردنظر را وارد کنید." : "Use the Microsoft Graph /children URL for the target drive folder.") : (isFa ? "فقط منابع عمومی HTTPS پشتیبانی می‌شوند." : "Only public HTTPS sources are supported.")}</p></div>
        {error && <InlineError message={error} onDismiss={() => setError("")} />}
      </div>
      <footer className="chunk-settings-footer"><div className="kb-set-footer-actions"><button type="button" disabled={saving} onClick={onClose} className="chunk-cancel">{isFa ? "انصراف" : "Cancel"}</button><button type="submit" disabled={!valid || saving} className="chunk-save">{saving ? (isFa ? "در حال اتصال…" : "Connecting…") : type === "webhook" ? (isFa ? "ساخت Webhook" : "Create webhook") : (isFa ? "اتصال و همگام‌سازی" : "Connect and sync")}</button></div></footer>
    </motion.form>
  </div></div>, document.body);
}

function ConnectorDialog({ setId, isFa, onClose, onSaved }: { setId: string; isFa: boolean; onClose: () => void; onSaved: () => void }) {
  const [type, setType] = useState<"website" | "github">("website"); const [name, setName] = useState(""); const [url, setUrl] = useState(""); const [saving, setSaving] = useState(false); const [error, setError] = useState("");
  const valid = name.trim().length >= 2 && /^https:\/\//i.test(url.trim());
  const submit = async (event: React.FormEvent) => { event.preventDefault(); if (!valid) return; setError(""); setSaving(true); try { const connector = await connectorService.create(setId, { connector_type: type, name: name.trim(), source_url: url.trim() }); const result = await connectorService.sync(setId, connector.id); toast.success(isFa ? `${result.created} سند وارد شد` : `${result.created} documents imported`); onSaved(); } catch (e) { setError((e as Error).message); } finally { setSaving(false); } };
  return <div className="fixed inset-0 z-[85] grid place-items-center bg-black/75 p-4 backdrop-blur-md" onMouseDown={onClose}><motion.form initial={{ opacity: 0, scale: .97 }} animate={{ opacity: 1, scale: 1 }} onSubmit={submit} onMouseDown={(e) => e.stopPropagation()} className="app-glass-panel w-full max-w-md rounded-[24px] border border-white/10 p-6"><div className="flex items-start justify-between"><div><span className="grid size-10 place-items-center rounded-xl bg-[#7c27ff]/30 kb-accent"><Link2 size={18} /></span><h2 className="mt-4 text-xl font-semibold">{isFa ? "اتصال منبع جدید" : "Connect a new source"}</h2><p className="mt-2 text-xs leading-5 kb-muted">{isFa ? "محتوای عمومی وب یا مخزن GitHub را به این مجموعه اضافه کنید." : "Import public web content or a GitHub repository into this set."}</p></div><button type="button" onClick={onClose} className="app-icon-button grid size-9 place-items-center rounded-xl kb-muted"><X size={16} /></button></div><div className="mt-6 grid grid-cols-2 gap-2">{(["website", "github"] as const).map((value) => <button type="button" key={value} onClick={() => setType(value)} className={`flex items-center gap-2 rounded-xl border p-3 text-xs ${type === value ? "border-[#18c7f4]/35 bg-[#7c27ff]/25 kb-text" : "border-white/[.08] kb-muted"}`}>{value === "website" ? <Globe2 size={15} /> : <Github size={15} />}{value === "website" ? "Website URL" : "GitHub"}</button>)}</div><label className="mt-5 block text-xs font-semibold kb-muted">{isFa ? "نام اتصال" : "Connection name"}<input value={name} onChange={(e) => setName(e.target.value)} placeholder={type === "github" ? "Product repository" : "Documentation website"} className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm outline-none placeholder:text-white/20 focus:border-[#18c7f4]/50" /></label><label className="mt-4 block text-xs font-semibold kb-muted">URL<input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder={type === "github" ? "https://github.com/owner/repository" : "https://example.com/docs"} className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm outline-none placeholder:text-white/20 focus:border-[#18c7f4]/50" /></label><div className="mt-4 rounded-xl border border-amber-300/10 bg-amber-300/[.04] p-3 text-xs leading-4 kb-muted">{isFa ? "فقط منابع عمومی HTTPS پشتیبانی می‌شوند. وب‌سایت یک صفحه و GitHub حداکثر ۴۰ فایل متنی را همگام می‌کند." : "Only public HTTPS sources are supported. Website sync imports one page; GitHub sync imports up to 40 supported text files."}</div>{error && <div className="mt-3"><InlineError message={error} onDismiss={() => setError("")} /></div>}<div className="mt-6 flex justify-end gap-2"><button type="button" onClick={onClose} className="rounded-xl px-4 py-2.5 text-xs kb-muted">{isFa ? "انصراف" : "Cancel"}</button><button disabled={!valid || saving} className="rounded-xl bg-[#7c27ff] px-5 py-2.5 text-xs font-semibold disabled:opacity-40">{saving ? (isFa ? "در حال همگام‌سازی…" : "Syncing…") : isFa ? "اتصال و همگام‌سازی" : "Connect and sync"}</button></div></motion.form></div>;
}

function ChunkingSettingsDialog({ item, isFa, onClose, onSaved }: { item: DocumentSet; isFa: boolean; onClose: () => void; onSaved: () => void }) {
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

function SetDialog({ mode, item, isFa, copy, onClose, onSaved }: { mode: "create" | "edit"; item?: DocumentSet; isFa: boolean; copy: Record<string, string>; onClose: () => void; onSaved: () => void }) {
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
