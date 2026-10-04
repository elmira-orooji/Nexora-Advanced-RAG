import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, ChevronDown, Copy, FileText, Quote, Telescope, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import InlineError from "./InlineError";
import AnswerMarkdown from "./AnswerMarkdown";
import NexoraAvatar from "./NexoraAvatar";
import AnswerSources from "./AnswerSources";
import SourceRegionImage from "./SourceRegionImage";
import AnswerLoading from "./AnswerLoading";
import ConversationScrollRail from "./ConversationScrollRail";
import "../styles/chat-answer.css";

import { feedbackService, type FeedbackReason } from "../services/feedbackService";
import type { ChatMessage, Source } from "../types/chat";

interface Props {
  messages: ChatMessage[];
  isThinking: boolean;
  isSlow?: boolean;
  assistantName?: string;
  onContinue?: () => void;
  onCopySuccess?: (message: string) => void;
}

export default function OnyxChatWindow({ messages, isThinking, isSlow = false, assistantName, onContinue, onCopySuccess }: Props) {
  const { i18n } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const [evidence, setEvidence] = useState<{ selected: Source; sources: Source[] } | null>(null);
  const [copyError, setCopyError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  useEffect(() => {
    const viewport = scrollRef.current;
    if (viewport && followLatest.current) viewport.scrollTop = viewport.scrollHeight;
  }, [messages, isThinking]);
  useEffect(() => {
    const viewport = scrollRef.current;
    if (!viewport) return;
    let frame = 0;
    const keepLatestVisible = () => {
      if (!followLatest.current) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (followLatest.current) viewport.scrollTop = viewport.scrollHeight;
      });
    };
    const observer = new ResizeObserver(keepLatestVisible);
    observer.observe(viewport);
    if (viewport.firstElementChild) observer.observe(viewport.firstElementChild);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);

  return <div dir={isFa ? "rtl" : "ltr"} className={`chat-thread h-full${evidence ? " chat-thread--with-evidence" : " relative"}`}>
    {copyError && <div className="px-3 pt-3"><InlineError message={copyError} onDismiss={() => setCopyError("")} /></div>}
    <div ref={scrollRef} onScroll={(event) => { const node = event.currentTarget; followLatest.current = node.scrollHeight - node.scrollTop - node.clientHeight < 100; }} className="chat-thread-scroll h-full overflow-y-auto pe-1 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10">
      <div className="chat-thread-messages">
        {messages.map((message) => message.role === "user" ? <article key={message.id} data-scroll-message={message.id} className="chat-question">
          <div className="chat-question-stack"><span className="chat-question-label">{isFa ? "شما" : "You"}</span><div className="chat-question-bubble"><div dir="auto">{message.content}</div></div><div className="chat-question-meta"><time dateTime={message.createdAt} title={new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" }).format(new Date(message.createdAt))}>{new Intl.DateTimeFormat(i18n.language, { hour: "numeric", minute: "2-digit" }).format(new Date(message.createdAt))}</time><button type="button" onClick={() => { void copyQuestion(message.content, isFa, setCopyError, undefined, undefined, onCopySuccess); }} aria-label={isFa ? "کپی پرسش" : "Copy question"} title={isFa ? "کپی پرسش" : "Copy question"}><Copy size={14} /></button></div></div>
        </article> : <article key={message.id} data-scroll-message={message.id} className="chat-answer">
          <NexoraAvatar />
          <div className="chat-answer-body">
            <header className="chat-answer-heading">{assistantName && <span dir="auto">{assistantName}</span>}</header>
            {message.research && <details className="mb-4 overflow-hidden rounded-2xl border border-white/[.07] bg-white/[.025]"><summary className="flex cursor-pointer list-none items-center gap-2.5 px-4 py-3 text-xs font-semibold text-white/70"><Telescope size={14} className="text-[#c43cff]" />{isFa ? "فعالیت بازیابی" : "Retrieval activity"}<span className="ms-auto text-xs font-normal text-white/45">{message.research.steps.length} {isFa ? "جست‌وجو" : "searches"} · {message.research.evidenceReviewed} {isFa ? "منبع" : "sources"}</span><ChevronDown size={13} className="text-white/45" /></summary><div className="space-y-2 border-t border-white/[.06] px-4 py-3">{message.research.steps.map((step, stepIndex) => <div key={stepIndex} className="flex items-center gap-2 text-xs leading-5 text-white/55"><Check size={11} className="text-emerald-300/70" /><span className="min-w-0 flex-1 truncate">{step.query}</span><span className="shrink-0 text-white/45">{step.evidence_count}</span></div>)}</div></details>}

            <div className="chat-answer-text answer-markdown" dir="auto"><AnswerMarkdown content={message.content} sources={message.sources || []} onOpen={(source) => setEvidence({ selected: source, sources: message.sources?.length ? message.sources : [source] })} /></div>
            {message.truncated && <div className="mt-3 text-sm" role="status"><p>{isFa ? "پاسخ به محدودیت طول رسید و ناتمام ماند." : "The answer reached its length limit and is incomplete."}</p>{onContinue && message.id === messages.at(-1)?.id && <button type="button" disabled={isThinking} onClick={onContinue} className="mt-2 rounded-lg border px-3 py-2 disabled:opacity-50">{isFa ? "ادامهٔ پاسخ" : "Continue answer"}</button>}</div>}
            {message.sources?.filter((source) => source.visualQuery && source.documentId).map((source) => <SourceRegionImage key={source.id} source={source} isFa={isFa} />)}
            {message.sources?.length ? <AnswerSources sources={message.sources} isFa={isFa} onOpen={(source) => setEvidence({ selected: source, sources: message.sources ?? [source] })} /> : null}

            <div className="chat-answer-actions">
              <Action label={isFa ? "کپی" : "Copy"} onClick={() => { void copyQuestion(message.content, isFa, setCopyError, isFa ? "کپی پاسخ انجام نشد" : "Could not copy response", isFa ? "پاسخ کپی شد" : "Response copied"); }}><Copy size={13} /></Action>
              {message.responseId && <Feedback responseId={message.responseId} isFa={isFa} />}
            </div>
          </div>
        </article>)}
        {isThinking && <AnswerLoading isFa={isFa} assistantName={assistantName} slow={isSlow} />}
      </div>
    </div>
    <ConversationScrollRail viewportRef={scrollRef} isFa={isFa} messages={messages} />
    {evidence && <Evidence sources={evidence.sources} selected={evidence.selected} isFa={isFa} onSelect={(source) => setEvidence((current) => current ? { ...current, selected: source } : current)} onClose={() => setEvidence(null)} />}
  </div>;
}

async function copyQuestion(content: string, isFa: boolean, onError: (message: string) => void, failure?: string, success?: string, onSuccess?: (message: string) => void) {
  try {
    await navigator.clipboard.writeText(content);
    const message = success || (isFa ? "پرسش کپی شد" : "Question copied");
    if (onSuccess) onSuccess(message);
    else toast.success(message);
  } catch {
    onError(failure || (isFa ? "کپی پرسش انجام نشد" : "Could not copy question"));
  }
}

function Action({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return <button type="button" aria-label={label} title={label} onClick={onClick} className="chat-answer-action">{children}</button>;
}

function Feedback({ responseId, isFa }: { responseId: string; isFa: boolean }) {
  const [rating, setRating] = useState<1 | -1 | null>(null);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<FeedbackReason | "">("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const reasons: Array<[FeedbackReason, string]> = [["incorrect", isFa ? "پاسخ اشتباه بود" : "Incorrect answer"], ["irrelevant_source", isFa ? "منبع نامرتبط بود" : "Irrelevant source"], ["incomplete", isFa ? "پاسخ ناقص بود" : "Incomplete answer"], ["citation_issue", isFa ? "ارجاع مشکل داشت" : "Citation issue"], ["other", isFa ? "مورد دیگر" : "Something else"]];
  const positive = async () => { setSaving(true); setError(""); try { await feedbackService.save(responseId, 1); setRating(1); toast.success(isFa ? "از بازخورد شما متشکریم" : "Thanks for your feedback"); } catch (error) { setError((error as Error).message); } finally { setSaving(false); } };
  const negative = async () => { if (!reason) return; setSaving(true); setError(""); try { await feedbackService.save(responseId, -1, reason); setRating(-1); setOpen(false); toast.success(isFa ? "بازخورد ثبت شد" : "Feedback saved"); } catch (error) { setError((error as Error).message); } finally { setSaving(false); } };
  return <div className="relative flex items-center"><Action label={isFa ? "مفید" : "Helpful"} onClick={() => void positive()}><ThumbsUp size={13} className={rating === 1 ? "text-emerald-300" : ""} /></Action><Action label={isFa ? "غیرمفید" : "Not helpful"} onClick={() => setOpen((value) => !value)}><ThumbsDown size={13} className={rating === -1 ? "text-rose-300" : ""} /></Action>{open && <div className="nexora-dropdown absolute bottom-10 start-0 z-30 w-64 rounded-2xl border border-white/10 bg-[rgba(15,11,22,.98)] p-3 shadow-2xl backdrop-blur-2xl"><div className="flex items-center justify-between"><p className="text-xs font-semibold text-white/75">{isFa ? "مشکل پاسخ چه بود؟" : "What went wrong?"}</p><button onClick={() => setOpen(false)} className="text-white/50"><X size={13} /></button></div><div className="mt-2 space-y-1">{reasons.map(([value, label]) => <button key={value} aria-pressed={reason === value} onClick={() => setReason(value)} className={`w-full rounded-lg px-2.5 py-2 text-start text-xs ${reason === value ? "bg-[#7c27ff]/40 text-white/80" : "text-white/55 hover:bg-white/[.04]"}`}>{label}</button>)}</div>{error && <InlineError className="mt-2" message={error} onDismiss={() => setError("")} />}<button disabled={!reason || saving} onClick={() => void negative()} className="mt-2 h-9 w-full rounded-xl bg-[#7c27ff] text-xs font-semibold disabled:opacity-40">{saving ? "…" : isFa ? "ثبت بازخورد" : "Submit"}</button></div>}{error && !open && <div className="absolute bottom-10 start-0 z-30 w-64"><InlineError message={error} onDismiss={() => setError("")} /></div>}</div>;
}

function Evidence({ sources, selected, isFa, onSelect, onClose }: { sources: Source[]; selected: Source; isFa: boolean; onSelect: (source: Source) => void; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement;
    closeRef.current?.focus();
    return () => { if (previous instanceof HTMLElement && previous.isConnected) previous.focus(); };
  }, []);
  return <aside className="chat-evidence" aria-label={isFa ? "منابع ارجاع‌شده" : "Cited sources"} dir={isFa ? "rtl" : "ltr"} onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); onClose(); } }}>
    <header className="chat-evidence-header">
      <span className="chat-evidence-icon"><Quote size={19} /></span>
      <div className="chat-evidence-heading"><h2>{isFa ? "منابع ارجاع‌شده" : "Cited sources"}</h2><p>{isFa ? `${sources.length} منبع در این پاسخ` : `${sources.length} sources in this answer`}</p></div>
      <button ref={closeRef} type="button" className="chat-evidence-close" onClick={onClose} aria-label={isFa ? "بستن منابع" : "Close cited sources"}><X size={18} /></button>
    </header>
    <div className="chat-evidence-content">
      <div className="chat-evidence-list" role="list" aria-label={isFa ? "فهرست منابع پاسخ" : "Answer source list"}>
        {sources.map((source, index) => <button key={`${source.id}-${source.citationId ?? index}`} type="button" aria-pressed={source.id === selected.id} className={`chat-evidence-source${source.id === selected.id ? " is-selected" : ""}`} onClick={() => onSelect(source)}>
          <span className="chat-evidence-source-title"><FileText size={14} /><strong dir="auto">{source.title}</strong></span>
          <small>{isFa ? `منبع ${source.citationId ?? index + 1}` : `Source ${source.citationId ?? index + 1}`}{source.page ? ` · ${isFa ? "صفحه" : "Page"} ${source.page}` : source.chunkIndex != null ? ` · ${isFa ? "بخش" : "Chunk"} ${source.chunkIndex + 1}` : ""}</small>
          <span className="chat-evidence-source-excerpt" dir="auto">{source.excerpt || (isFa ? "متن گزیده موجود نیست." : "No excerpt available.")}</span>
        </button>)}
      </div>
      <section className="chat-evidence-selected" aria-live="polite">
        <div className="chat-evidence-file"><span className="chat-evidence-file-icon"><FileText size={19} /></span><div><strong dir="auto">{selected.title}</strong><span>{selected.page ? `${isFa ? "صفحه" : "Page"} ${selected.page}` : selected.chunkIndex != null ? `${isFa ? "بخش" : "Chunk"} ${selected.chunkIndex + 1}` : (isFa ? "سند مرجع" : "Source document")}</span><span className="text-violet-300">OCR · {selected.ocrProvenance?.provider ?? (isFa ? "ارائه‌دهنده ثبت نشده" : "provider not recorded")}</span></div></div>
        {selected.section && <p className="chat-evidence-section" dir="auto">{selected.section}</p>}
        <h3 className="chat-evidence-label">{isFa ? "متن منبع" : "Source passage"}</h3>
        <blockquote className="chat-evidence-passage" dir="auto">{selected.excerpt || (isFa ? "متن این منبع در دسترس نیست." : "No passage is available for this source.")}</blockquote>
      </section>
    </div>
    <footer className="chat-evidence-footer"><FileText size={13} /><span>{isFa ? "این بخش از سند برای پاسخ بازیابی شده است." : "This passage was retrieved to support the answer."}</span></footer>
  </aside>;
}
