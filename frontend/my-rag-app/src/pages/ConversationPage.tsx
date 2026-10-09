import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, FileText, FileUp, Loader2, MessageSquareText, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import "../styles/conversation.css";
import NexoraAvatar from "../components/NexoraAvatar";
import InlineError from "../components/InlineError";
import KnowledgeSetPicker, { ALL_KNOWLEDGE_SETS } from "../components/KnowledgeSetPicker";
import { assistantService, type CustomAssistant } from "../services/assistantService";
import ChatInput from "../components/ChatInput";
import OnyxChatWindow from "../components/OnyxChatWindow";
import { conversationService, type ConversationDetail, type PersistedMessage } from "../services/conversationService";
import { knowledgeService, type DocumentSet } from "../services/knowledgeService";
import { authService } from "../services/authService";
import type { ChatMessage } from "../types/chat";

interface ConversationPageProps {
  conversationId: string | null;
  onConversationChange: (id: string) => void;
  onConversationsUpdated: () => void;
  onOpenKnowledge: (intent?: "create" | "upload") => void;
}

function toChatMessage(message: PersistedMessage): ChatMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content.replace(/\[Source\s+(\d+)\]/gi, "[$1]"),
    createdAt: message.created_at,
    grounded: Boolean(message.sources?.length),
    answerBasis: message.answer_basis ?? undefined,
    truncated: message.truncated,
    responseId: message.answer_id || undefined,
    sources: message.sources?.map((source, index) => ({
      id: source.chunk_id,
      citationId: index + 1,
      documentId: source.document_id,
      title: source.filename,
      chunkIndex: source.chunk_index,
      excerpt: source.content,
      score: source.score,
      page: source.page,
      section: source.section,
      ocrProvenance: source.ocr_provenance,
      visualQuery: source.visual_query,
    })),
  };
}

export default function ConversationPage({ conversationId, onConversationChange, onConversationsUpdated, onOpenKnowledge }: ConversationPageProps) {
  const allKnowledgeSetsId = ALL_KNOWLEDGE_SETS;
  const [assistant, setAssistant] = useState<Pick<CustomAssistant, "id" | "name" | "document_set_names"> | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [sets, setSets] = useState<DocumentSet[]>([]);
  const [selectedSetIds, setSelectedSetIds] = useState<string[]>([]);
  const selectedSetId = selectedSetIds[0] ?? "";
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sendError, setSendError] = useState("");
  const [loadRevision, setLoadRevision] = useState(0);
  const [sending, setSending] = useState(false);
  const [sendSlow, setSendSlow] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState("");
  const createdConversationId = useRef<string | null>(null);
  const sendAbortController = useRef<AbortController | null>(null);
  const sendSlowTimer = useRef<number | null>(null);
  const { i18n } = useTranslation();
  const isFa = i18n.language.startsWith("fa");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError(null);
    createdConversationId.current = null;
    const task = conversationId
      ? conversationService.get(conversationId).then((value) => { if (active) setDetail(value); })
      : knowledgeService.listSets().then((value) => {
          if (!active) return;
          setSets(value);
          setSelectedSetIds((current) => current.length ? current.filter((id) => id === allKnowledgeSetsId || value.some((set) => set.id === id)) : (value.length ? [allKnowledgeSetsId] : []));
          setDetail(null);
        });
    task
      .catch((error) => {
        if (!active) return;
        const message = (error as Error).message || (isFa ? "دریافت گفتگو ناموفق بود." : "We couldn't load this conversation.");
        setLoadError(message);
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [conversationId, isFa, loadRevision]);

  const assistantId = detail?.assistant_id;
  useEffect(() => {
    if (!assistantId) return;
    let active = true;
    assistantService.list().then((items) => {
      if (active) {
        const match = items.find((item) => item.id === assistantId);
        setAssistant(match ? { id: match.id, name: match.name, document_set_names: match.document_set_names } : null);
      }
    }).catch(() => { if (active) setAssistant(null); });
    return () => { active = false; };
  }, [assistantId]);
  const assistantName = assistant?.id === assistantId ? assistant?.name : undefined;
  const assistantSources = assistant?.id === assistantId ? (assistant?.document_set_names ?? []) : [];

  const messages = useMemo(() => {
    const persisted = detail?.messages.map(toChatMessage) ?? [];
    if (!pendingPrompt) return persisted;
    return [...persisted, { id: "pending-user-message", role: "user" as const, content: pendingPrompt, createdAt: new Date().toISOString() }];
  }, [detail, pendingPrompt]);
  const selectedSet = sets.find((item) => item.id === selectedSetId);
  const isAllKnowledgeSets = selectedSetId === allKnowledgeSetsId;
  const indexedDocumentCount = isAllKnowledgeSets
    ? sets.reduce((total, item) => total + item.indexed_document_count, 0)
    : sets.filter((set) => selectedSetIds.includes(set.id)).reduce((total, item) => total + item.indexed_document_count, 0);
  const knowledgeReady = indexedDocumentCount > 0;
  const canCreateKnowledge = authService.getUser()?.role === "admin";
  const detailMatchesConversation = conversationId
    ? detail?.id === conversationId
    : detail === null;

  useEffect(() => () => {
    sendAbortController.current?.abort();
    if (sendSlowTimer.current !== null) window.clearTimeout(sendSlowTimer.current);
  }, []);

  const cancelSend = () => {
    sendAbortController.current?.abort();
    sendAbortController.current = null;
    if (sendSlowTimer.current !== null) window.clearTimeout(sendSlowTimer.current);
    sendSlowTimer.current = null;
    setSendSlow(false);
    setPendingPrompt("");
    setSending(false);
  };

  const send = async (content: string) => {
    setSendError("");
    setPendingPrompt(content);
    setSending(true);
    setSendSlow(false);
    sendSlowTimer.current = window.setTimeout(() => setSendSlow(true), 8_000);
    const controller = new AbortController();
    sendAbortController.current = controller;
    try {
      let id = conversationId ?? createdConversationId.current;
      if (!id) {
        if (!selectedSetId || !knowledgeReady) throw new Error(isFa ? "ابتدا یک سند را بارگذاری و آماده‌سازی کنید." : "Upload and finish indexing a document before starting a conversation.");
        const created = isAllKnowledgeSets
          ? await conversationService.createForWorkspace(undefined, controller.signal)
          : selectedSetIds.length > 1
            ? await conversationService.createForSets(selectedSetIds, undefined, controller.signal)
            : await conversationService.createForSet(selectedSetId, undefined, controller.signal);
        id = created.id;
        createdConversationId.current = id;
      }
      await conversationService.send(id, content, controller.signal);
      if (controller.signal.aborted) return false;
      const updated = await conversationService.get(id, controller.signal);
      if (controller.signal.aborted) return false;
      setDetail(updated);
      onConversationsUpdated();
      if (!conversationId) onConversationChange(id);
      return true;
    } catch (error) {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) return false;
      setSendError((error as Error).message);
      return false;
    } finally {
      if (sendAbortController.current === controller) {
        sendAbortController.current = null;
        if (sendSlowTimer.current !== null) window.clearTimeout(sendSlowTimer.current);
        sendSlowTimer.current = null;
        setSendSlow(false);
        setPendingPrompt("");
        setSending(false);
      }
    }
  };

  if (loading) return <div className="grid h-full place-items-center conversation-muted" role="status" aria-live="polite" aria-label={isFa ? "در حال بارگذاری گفتگو" : "Loading conversation"}><Loader2 className="animate-spin" aria-hidden="true" /></div>;

  if (loadError || !detailMatchesConversation) return <div dir={isFa ? "rtl" : "ltr"} className="grid h-full place-items-center px-5 text-center">
    <div className="max-w-sm rounded-2xl border border-rose-300/20 bg-rose-400/[.06] p-6 shadow-[0_18px_50px_rgba(0,0,0,.16)]">
      <span className="mx-auto grid size-11 place-items-center rounded-xl border border-rose-300/20 bg-rose-400/10 text-rose-200"><MessageSquareText size={19} /></span>
      <h1 className="mt-4 text-base font-semibold text-white">{isFa ? "گفتگو بارگذاری نشد" : "Conversation could not be loaded"}</h1>
      <p className="mt-2 text-sm leading-6 conversation-muted">{loadError || (isFa ? "لطفاً دوباره تلاش کنید." : "Please try again.")}</p>
      <button type="button" onClick={() => setLoadRevision((value) => value + 1)} className="mt-5 inline-flex h-10 items-center gap-2 rounded-xl bg-[#7c27ff] px-4 text-sm font-semibold text-white shadow-[0_8px_24px_rgba(124,39,255,.25)] transition hover:bg-[#9238ff] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c43cff]"><RefreshCw size={15} />{isFa ? "تلاش مجدد" : "Try again"}</button>
    </div>
  </div>;

  if (!messages.length && !conversationId) {
    return <div dir={isFa ? "rtl" : "ltr"} className="conversation-page conversation-page--welcome flex h-full min-h-0 flex-col overflow-x-hidden overflow-y-auto px-4 sm:px-7 lg:px-10">

      <main className="conversation-welcome">
        <div className="conversation-intro">
          <span className="conversation-emblem">
            <img src="/brand/nexora-symbol.svg" alt="" width={48} height={48} />
          </span>
          <h1 className="conversation-title">
            {isFa ? "امروز چه چیزی را بررسی کنیم؟" : "What would you like to explore?"}
          </h1>
          <p className="conversation-description">
            {isFa ? "از دانش سازمانی خود سؤال کنید و پاسخ‌هایی دقیق، مستند و قابل پیگیری دریافت کنید." : "Ask across your organizational knowledge and get precise, source-grounded answers you can verify."}
          </p>
        </div>

        <div className="conversation-compose-area">
          <div className="conversation-context">
            <div className="conversation-selector">
              <BookOpen size={12} className="shrink-0 conversation-accent" />
              <span className="hidden sm:inline">{isFa ? "پایگاه دانش" : "Knowledge base"}</span>
              <KnowledgeSetPicker sets={sets} value={selectedSetIds} onChange={setSelectedSetIds} isFa={isFa} disabled={sending} />
            </div>
            <span className="text-xs conversation-muted" title={!knowledgeReady && !canCreateKnowledge ? (isFa ? "برای دسترسی به پایگاه دانش و اسناد آماده، با مدیر فضای کاری تماس بگیرید." : "Contact your workspace administrator for access to indexed knowledge.") : undefined}>
              {knowledgeReady ? (isAllKnowledgeSets || selectedSetIds.length > 1 ? (isFa ? "آمادهٔ پاسخ‌گویی" : "Ready for answers") : `${indexedDocumentCount} ${isFa ? "سند آماده" : "indexed documents"}`) : !sets.length ? (isFa ? "پایگاه دانش قابل‌دسترسی وجود ندارد" : "No accessible knowledge base") : !selectedSetIds.length ? (isFa ? "حداقل یک پایگاه دانش انتخاب کنید." : "Select at least one knowledge base.") : (isFa ? "بدون سند آماده" : "No indexed documents")}
            </span>
          </div>

          {knowledgeReady && sendError && <InlineError className="mb-3" message={sendError} onDismiss={() => setSendError("")} />}
          <ChatInput prominent disabled={!knowledgeReady} isSending={sending} onSend={send} onCancel={cancelSend} />
          {!knowledgeReady && canCreateKnowledge && <KnowledgeStartPanel isFa={isFa} hasSet={Boolean(selectedSet) || (isAllKnowledgeSets && sets.length > 0)} canCreate={canCreateKnowledge} onOpenKnowledge={onOpenKnowledge} />}

          <div className="mt-4 flex items-center justify-center gap-1.5 text-xs conversation-muted"><FileText size={10} />{isFa ? "پاسخ‌ها همراه با ارجاع به منابع ذخیره می‌شوند" : "Answers are saved with traceable source citations"}</div>
        </div>
      </main>
    </div>;
  }

  return <div dir={isFa ? "rtl" : "ltr"} className="conversation-page relative mx-auto flex h-full w-full flex-col overflow-hidden px-4 sm:px-7 lg:px-10">
    <header className="relative z-10 h-[72px] shrink-0">
      <div className="conversation-header-inner flex h-full w-full items-center justify-between gap-4 border-b border-white/[.045]">
        <div className="flex min-w-0 items-center gap-3">
          <NexoraAvatar />
          <div className="min-w-0"><h1 className="truncate text-sm font-semibold tracking-[-.02em] conversation-muted">{detail?.title || (isFa ? "گفتگوی جدید" : "New conversation")}</h1></div>
        </div>
        {assistantName && <div className="hidden items-center gap-3 sm:flex"><span className="conversation-assistant-context">{isFa ? `دستیار: ${assistantName}` : `Assistant: ${assistantName}`}</span><span className="conversation-assistant-context" title={assistantSources.length ? assistantSources.join(" · ") : undefined}><BookOpen size={12} />{assistantSources.length ? (isFa ? `${assistantSources.length} پایگاه دانش متصل` : `${assistantSources.length} connected knowledge ${assistantSources.length === 1 ? "base" : "bases"}`) : (isFa ? "بدون منبع اختصاصی" : "No dedicated knowledge base")}</span></div>}
      </div>
    </header>

    <section className="relative z-10 min-h-0 flex-1 overflow-hidden px-0 sm:px-3">
      {messages.length ? <OnyxChatWindow messages={messages} isThinking={sending} isSlow={sendSlow} assistantName={assistantName} onContinue={() => void send(isFa ? "پاسخ قبلی ناتمام ماند. فقط ادامهٔ آن را بدون تکرار بخش قبلی، با همان منابع و از محل قطع‌شدن بنویس." : "The previous answer was cut off. Continue from where it stopped, using the same sources and without repeating the previous part.")} /> : <div className="flex h-full flex-col items-center justify-center text-center">
        <span className="conversation-assistant-emblem"><img src="/brand/nexora-symbol.svg" alt="" width={48} height={48} /></span>
        <h2 className="conversation-assistant-title">{assistantName ? (isFa ? `گفتگو با ${assistantName} را آغاز کنید` : `Start a conversation with ${assistantName}`) : (isFa ? "گفتگوی مستند را آغاز کنید" : "Start a source-grounded conversation")}</h2>
        <p className="mt-2 max-w-md text-sm leading-6 conversation-muted">{assistantName ? (assistantSources.length ? (isFa ? `این دستیار از ${assistantSources.join("، ")} استفاده می‌کند. پاسخ‌ها و منابع در گفت‌وگوهای اخیر ذخیره می‌شوند.` : `This assistant uses ${assistantSources.join(", ")}. Answers and sources are saved in Recent chats.`) : (isFa ? "این دستیار منبع اختصاصی ندارد. پاسخ‌ها و منابع در گفت‌وگوهای اخیر ذخیره می‌شوند." : "This assistant has no dedicated knowledge base. Answers and sources are saved in Recent chats.")) : (isFa ? "پایگاه دانشی را انتخاب کنید. پیام‌ها، پاسخ‌ها و منابع شما در گفت‌وگوهای اخیر باقی می‌مانند." : "Choose the knowledge base this conversation should use. Your messages, answers, and sources remain available in Recent chats.")}</p>
        {!conversationId && <div className="mt-6 w-full max-w-sm text-left text-xs conversation-muted">
          <span className="mb-2 flex items-center gap-2"><BookOpen size={13} />Knowledge base</span>
          <KnowledgeSetPicker sets={sets} value={selectedSetIds} onChange={setSelectedSetIds} isFa={isFa} disabled={sending} />
        </div>}
      </div>}
    </section>
    <div className="conversation-dock relative z-20 shrink-0 px-0 pb-4 pt-3 sm:px-3 sm:pb-5">{sendError && <InlineError className="mb-3" message={sendError} onDismiss={() => setSendError("")} />}<ChatInput prominent disabled={!conversationId && !selectedSetId} isSending={sending} onSend={send} onCancel={cancelSend} /><div className="mt-2 flex items-center justify-center gap-1.5 text-xs conversation-muted"><FileText size={10} />{isFa ? "پاسخ‌ها ممکن است خطا داشته باشند؛ منابع را بررسی کنید." : "AI can make mistakes. Verify important details in the cited sources."}</div></div>
  </div>;
}

function KnowledgeStartPanel({ isFa, hasSet, canCreate, onOpenKnowledge }: { isFa: boolean; hasSet: boolean; canCreate: boolean; onOpenKnowledge: (intent?: "create" | "upload") => void }) {
  const title = hasSet
    ? (isFa ? "این پایگاه دانش هنوز برای پاسخ‌گویی آماده نیست" : "This knowledge base is not ready for answers yet")
    : (isFa ? "برای شروع، دانش سازمانی را اضافه کنید" : "Add organizational knowledge to get started");
  const description = hasSet
    ? (isFa ? "حداقل یک سند را بارگذاری کنید و پس از پایان پردازش، گفتگو را آغاز کنید." : "Upload at least one document, then start the conversation after indexing finishes.")
    : (isFa ? "یک پایگاه دانش بسازید، اولین سند را اضافه کنید و سپس پاسخ‌های دارای منبع دریافت کنید." : "Create a knowledge base, add a first document, then receive answers with sources.");

  if (!canCreate) return <section className="conversation-knowledge-notice mt-3" aria-labelledby="knowledge-start-title">
    <BookOpen size={16} className="shrink-0 conversation-accent" aria-hidden="true" />
    <div><h2 id="knowledge-start-title">{hasSet ? (isFa ? "اسناد این پایگاه دانش هنوز آماده نیستند" : "This knowledge base is not ready for answers yet") : (isFa ? "پایگاه دانش قابل‌دسترسی وجود ندارد" : "No accessible knowledge base")}</h2>
    <p>{isFa ? "برای دسترسی به پایگاه دانش و اسناد آماده، با مدیر فضای کاری تماس بگیرید." : "Contact your workspace administrator for access to indexed knowledge."}</p></div>
  </section>;

  return <section className="conversation-knowledge-start conversation-knowledge-start--compact mt-3 mx-auto w-full" aria-labelledby="knowledge-start-title">
    <div className="conversation-knowledge-start__icon"><BookOpen size={22} /></div>
    <span className="nexora-status nexora-status--info">{isFa ? "مسیر شروع" : "Getting started"}</span>
    <h2 id="knowledge-start-title">{title}</h2>
    <p>{description}</p>
    <div className="flex flex-wrap items-center justify-center gap-2">
      {!hasSet && canCreate && <button type="button" onClick={() => onOpenKnowledge("create")} className="nexora-action nexora-action--primary"><PlusIcon />{isFa ? "ساخت پایگاه دانش" : "Create knowledge base"}</button>}
      <button type="button" onClick={() => onOpenKnowledge("upload")} className={hasSet ? "nexora-action nexora-action--primary" : "nexora-action nexora-action--secondary"}><FileUp size={14} />{isFa ? "بارگذاری اولین سند" : "Upload first document"}</button>
    </div>
    {!canCreate && !hasSet && <p className="conversation-knowledge-start__access">{isFa ? "برای ساخت پایگاه دانش، از مدیر فضای کاری دسترسی بگیرید." : "Ask a workspace administrator to create a knowledge base for you."}</p>}
  </section>;
}

function PlusIcon() { return <span aria-hidden="true" className="text-sm leading-none">+</span>; }
