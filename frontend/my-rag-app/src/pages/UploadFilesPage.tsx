import { useKnowledgeChat } from "../features/knowledge/hooks/useKnowledgeChat";
import { useDocumentPolling } from "../features/knowledge/hooks/useDocumentPolling";
import { useKnowledgeUpload } from "../features/knowledge/hooks/useKnowledgeUpload";
import { ChunkingSettingsDialog, SetDialog } from "../features/knowledge/components/KnowledgeDialogs";
import { CloudConnectorDialog } from "../features/knowledge/components/ConnectorDialogs";
import { DocumentRow } from "../features/knowledge/components/DocumentRow";
import { ConnectorStatus } from "../features/knowledge/components/ConnectorStatus";
import { MetadataFilterBar, ScopeSelector } from "../features/knowledge/components/KnowledgeFilters";
import LoadingSkeleton from "../components/LoadingSkeleton";
import { confirmAction } from "../services/confirmation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  BookOpen, Check, ChevronDown, FileText, FolderKanban, Link2, MessageSquareText, MoreHorizontal,
  FlaskConical, PanelRightClose, Pencil, Plus, RefreshCw, Search, Settings2, Telescope, Trash2, UploadCloud, Zap, X,
} from "lucide-react";
import "../styles/knowledge.css";
import ChatInput from "../components/ChatInput";
import ChatWindow from "../components/ChatWindow";
import RetrievalPlayground from "../components/RetrievalPlayground";
import InlineError from "../components/InlineError";
import { authService } from "../services/authService";
import { knowledgeService, type DocumentSet, type KnowledgeDocument, type MetadataFilters } from "../services/knowledgeService";
import { connectorService, type Connector } from "../services/connectorService";
import { operationError } from "../lib/operationFeedback";

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
  const [chatOpen, setChatOpen] = useState(() => window.matchMedia("(min-width: 1280px)").matches);
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
  const { chatMessages, setChatMessages, chatError, setChatError, isThinking, isChatSlow, handleChatMessage, cancelChatMessage } = useKnowledgeChat({ selectedSetId, selectedDocumentIds, metadataFilters, answerMode, isFa });
  const selectedSetIdRef = useRef(selectedSetId);

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
  useDocumentPolling(selectedSetId, documents, applyDocuments);

  const { uploadTasks, setUploadTasks, uploadError, setUploadError, uploading, getInputProps, getRootProps, isDragActive, open } = useKnowledgeUpload({ selectedSetId, isFa, refreshSetData, loadSets, setPageError });

  const filtered = useMemo(() => documents.filter((item) =>
    item.filename.toLowerCase().includes(query.toLowerCase()) && (statusFilter === "all" || item.status === statusFilter)
  ), [documents, query, statusFilter]);



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
          {selectedSet && <div className="kb-selected-set-header flex shrink-0 items-center justify-between gap-3"><div className="min-w-0 flex-1"><h2 className="nexora-file-name text-lg font-semibold">{selectedSet.name}</h2><p className="nexora-file-name mt-1 text-xs kb-muted">{selectedSet.description}</p></div><div className="kb-selected-set-actions flex shrink-0 items-center gap-2">{(isAdmin || selectedSet.access_level === "edit" || selectedSet.access_level === "manage") && <button onClick={() => setConnectorDialog(true)} className="kb-connect flex h-9 items-center gap-1.5 px-3 text-xs font-medium"><Link2 size={13} />{copy.connect}</button>}{(isAdmin || selectedSet.access_level === "manage") && <div className="relative"><button aria-label={isFa ? "گزینه‌های مجموعه" : "Set options"} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)} className="app-icon-button grid size-9 place-items-center rounded-xl kb-muted"><MoreHorizontal size={17} /></button>{menuOpen && <div className="nexora-dropdown absolute end-0 top-11 z-30 w-40 rounded-xl border border-white/10 bg-[#15121c] p-1.5 shadow-2xl"><button onClick={() => { setDialog("edit"); setMenuOpen(false); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs kb-text hover:bg-white/5"><Pencil size={13} />{copy.edit}</button><button onClick={() => void deleteSet(selectedSet)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-rose-300/75 hover:bg-rose-400/5"><Trash2 size={13} />{copy.delete}</button></div>}</div>}</div></div>}
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
{loading ? <LoadingSkeleton variant="rows" /> : filtered.length ? filtered.map((doc) => <DocumentRow key={doc.id} document={doc} isAdmin={isAdmin || selectedSet?.access_level === "edit" || selectedSet?.access_level === "manage"} isFa={isFa} canDelete={isAdmin} onPause={async () => { await knowledgeService.pauseDocument(doc.id); await refreshSetData(selectedSetId); await loadSets(); }} onRetry={async () => { await knowledgeService.retryDocument(doc.id); await refreshSetData(selectedSetId); await loadSets(); }} onRemove={async () => { if (!selectedSetId || !await confirmAction(isFa ? `سند «${doc.filename}» برای همیشه حذف و پردازش آن لغو شود؟` : `Permanently delete “${doc.filename}” and cancel its processing?`)) return; try { await knowledgeService.deleteDocument(doc.id); setDocuments((items) => items.filter((item) => item.id !== doc.id)); await loadSets(); toast.success(isFa ? "سند حذف و پردازش آن لغو شد" : "Document deleted and processing cancelled"); } catch (error) { setPageError(operationError(error, "load", isFa)); } }} />) : <div className="grid h-full min-h-28 place-items-center text-xs kb-muted">{selectedSet ? copy.empty : (isFa ? "یک مجموعه انتخاب کنید" : "Select a knowledge set")}</div>}
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
            <span className="knowledge-assistant-logo grid size-10 shrink-0 place-items-center"><img src="/brand/nexora-symbol.svg" alt="" width={36} height={36} /></span>
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
