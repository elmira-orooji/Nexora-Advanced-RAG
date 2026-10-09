import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Copy, FileText, Quote, Telescope, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ChatMessage, Source } from "../types/chat";
import { feedbackService, type FeedbackReason } from "../services/feedbackService";
import AnswerTrustBadge from "./AnswerTrustBadge";
import AnswerSources from "./AnswerSources";
import AnswerLoading from "./AnswerLoading";
import InlineError from "./InlineError";
import NexoraAvatar from "./NexoraAvatar";
import "../styles/chat-answer.css";

interface ChatWindowProps { messages: ChatMessage[]; isThinking: boolean; isSlow?: boolean; }

const focusableSelector = [
  "button:not([disabled])",
  "input:not([disabled])",
  "textarea:not([disabled])",
  "select:not([disabled])",
  "a[href]",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function useDialogFocus<T extends HTMLElement>(open: boolean, onClose: () => void) {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    window.setTimeout(() => {
      const first = ref.current?.querySelector<HTMLElement>(focusableSelector);
      (first || ref.current)?.focus();
    }, 0);
    return () => {
      if (previous?.isConnected) previous.focus();
    };
  }, [open]);
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !ref.current) return;
    const focusable = [...ref.current.querySelectorAll<HTMLElement>(focusableSelector)].filter((item) => item.offsetParent !== null || item === document.activeElement);
    if (!focusable.length) {
      event.preventDefault();
      ref.current.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  return { ref, onKeyDown };
}

function CopyTextButton({ value, success, failure, label, className, onError }: { value: string; success: string; failure: string; label: string; className?: string; onError: (message: string) => void }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current !== null) clearTimeout(timer.current); }, []);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2500);
    } catch { onError(failure); }
  };
  return <span className="chat-copy-control"><button type="button" className={className} aria-label={label} title={label} onClick={() => void copy()}><Copy size={14} /></button>{copied && <span role="status" className="chat-copy-confirmation">{success}</span>}</span>;
}

export default function ChatWindow({ messages, isThinking, isSlow = false }: ChatWindowProps) {
  const { i18n } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const [evidence, setEvidence] = useState<Source | null>(null);
  const [copyError, setCopyError] = useState("");

  return <div className="chat-thread knowledge-chat relative h-full" dir={isFa ? "rtl" : "ltr"}>
    {copyError && <div className="px-3 pt-3"><InlineError message={copyError} onDismiss={() => setCopyError("")} /></div>}
    <div className="chat-thread-scroll h-full overflow-y-auto pe-1">
      <div className="chat-thread-messages">
      {messages.map((message) => message.role === "user"
        ? <article key={message.id} className="chat-question"><div className="chat-question-stack"><div className="chat-question-bubble">{message.content}</div><div className="chat-question-meta"><time dateTime={message.createdAt} title={new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" }).format(new Date(message.createdAt))}>{new Intl.DateTimeFormat(i18n.language, { hour: "numeric", minute: "2-digit" }).format(new Date(message.createdAt))}</time><CopyTextButton value={message.content} success={isFa ? "پرسش کپی شد" : "Question copied"} failure={isFa ? "کپی پرسش انجام نشد" : "Could not copy question"} label={isFa ? "کپی پرسش" : "Copy question"} onError={setCopyError} /></div></div></article>
        : <article key={message.id} className="chat-answer">
          <NexoraAvatar />
          <div className="chat-answer-body">
            <header className="chat-answer-heading"><strong>Nexora</strong></header>
            <div className="chat-answer-text" dir="auto"><CitedText content={message.content} sources={message.sources || []} onOpen={setEvidence} /></div>
            <AnswerTrustBadge answerBasis={message.answerBasis} grounded={message.grounded} sourceCount={message.sources?.length ?? 0} isFa={isFa} onOpenSources={message.sources?.length ? () => setEvidence(message.sources![0]) : undefined} />
            {message.research && <details className="chat-answer-research"><summary><Telescope size={14} />{isFa ? "مراحل پژوهش" : "Research trail"}<span>{message.research.steps.length} {isFa ? "جست‌وجو" : "searches"} · {message.research.evidenceReviewed} {isFa ? "شاهد" : "evidence"}</span></summary><div className="chat-answer-research-steps">{message.research.steps.map((step, index) => <div key={index}><span className="chat-answer-source-number">{index + 1}</span><span className="chat-answer-research-query">{step.query}</span><span>{step.evidence_count}</span></div>)}</div></details>}
            {message.sources?.length ? <AnswerSources sources={message.sources} isFa={isFa} onOpen={setEvidence} /> : null}
            <div className="chat-answer-actions"><CopyTextButton value={message.content} success={isFa ? "پاسخ کپی شد" : "Response copied"} failure={isFa ? "کپی پاسخ ناموفق بود" : "Could not copy response"} label={isFa ? "کپی پاسخ" : "Copy response"} className="chat-answer-action" onError={setCopyError} />{message.responseId && <MessageFeedback responseId={message.responseId} isFa={isFa} />}</div>
          </div>
        </article>)}
      {isThinking && <AnswerLoading isFa={isFa} slow={isSlow} />}
      </div>
    </div>
    {evidence && <EvidenceDrawer source={evidence} isFa={isFa} onClose={() => setEvidence(null)} />}
  </div>;
}

function MessageFeedback({ responseId, isFa }: { responseId: string; isFa: boolean }) {
  const [rating, setRating] = useState<1 | -1 | null>(null);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<FeedbackReason | "">("");
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState("");
  useEffect(() => {
    if (!feedbackStatus) return;
    const timer = setTimeout(() => setFeedbackStatus(""), 2500);
    return () => clearTimeout(timer);
  }, [feedbackStatus]);
  const positive = async () => { setSaving(true); setError(""); setFeedbackStatus(""); try { await feedbackService.save(responseId, 1); setRating(1); setOpen(false); setFeedbackStatus(isFa ? "از بازخورد شما متشکریم" : "Thanks for your feedback"); } catch (e) { setError((e as Error).message); setOpen(true); } finally { setSaving(false); } };
  const negative = async () => { if (!reason) return; setSaving(true); setError(""); setFeedbackStatus(""); try { await feedbackService.save(responseId, -1, reason, comment.trim()); setRating(-1); setOpen(false); setFeedbackStatus(isFa ? "بازخورد ثبت شد" : "Feedback saved"); } catch (e) { setError((e as Error).message); } finally { setSaving(false); } };
  const reasons: Array<[FeedbackReason, string]> = [
    ["incorrect", isFa ? "پاسخ اشتباه بود" : "The answer was incorrect"],
    ["irrelevant_source", isFa ? "منبع نامرتبط بود" : "The source was irrelevant"],
    ["incomplete", isFa ? "پاسخ ناقص بود" : "The answer was incomplete"],
    ["citation_issue", isFa ? "ارجاع مشکل داشت" : "The citation had an issue"],
    ["other", isFa ? "مورد دیگر" : "Something else"],
  ];
  const close = () => setOpen(false);
  const dialog = useDialogFocus<HTMLDivElement>(open, close);
  return <div className="chat-feedback relative flex items-center gap-1">
    <button disabled={saving} onClick={() => void positive()} aria-label="Helpful" className={`grid size-7 place-items-center rounded-lg transition ${rating === 1 ? "bg-emerald-300/10 text-emerald-200" : "text-white/25 hover:bg-white/[.06] hover:text-white/70"}`}><ThumbsUp size={13} /></button>
    <button disabled={saving} onClick={() => setOpen(!open)} aria-label="Not helpful" className={`grid size-7 place-items-center rounded-lg transition ${rating === -1 ? "bg-rose-300/10 text-rose-200" : "text-white/25 hover:bg-white/[.06] hover:text-white/70"}`}><ThumbsDown size={13} /></button>
    {feedbackStatus && <span role="status" className="chat-copy-confirmation">{feedbackStatus}</span>}
    {open && <div ref={dialog.ref} role="dialog" aria-modal="false" aria-labelledby={`feedback-title-${responseId}`} tabIndex={-1} onKeyDown={dialog.onKeyDown} className="nexora-dropdown absolute bottom-9 start-0 z-30 w-72 rounded-2xl border border-white/10 bg-[rgba(18,14,25,.98)] p-3 shadow-2xl backdrop-blur-2xl"><div className="flex items-center justify-between"><p id={`feedback-title-${responseId}`} className="text-xs font-semibold text-white/75">{isFa ? "مشکل پاسخ چه بود؟" : "What was wrong with the answer?"}</p><button onClick={close} aria-label={isFa ? "بستن پنجره بازخورد" : "Close feedback dialog"} className="grid size-6 place-items-center rounded-md text-white/30 hover:bg-white/5"><X size={12} /></button></div><div className="mt-2 space-y-1">{reasons.map(([value, label]) => <button key={value} aria-pressed={reason === value} onClick={() => setReason(value)} className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-start text-xs ${reason === value ? "bg-[#7c27ff]/35 text-white/80" : "text-white/55 hover:bg-white/[.04]"}`}><span className={`size-2 rounded-full border ${reason === value ? "border-[#c43cff] bg-[#c43cff]" : "border-white/20"}`} />{label}</button>)}</div>{reason === "other" && <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} rows={2} placeholder={isFa ? "توضیح اختیاری..." : "Optional details..."} className="mt-2 w-full resize-none rounded-xl border border-white/10 bg-black/20 p-2.5 text-xs outline-none placeholder:text-white/30 focus:border-[#18c7f4]/40" />}{error && <InlineError className="mt-2" message={error} onDismiss={() => setError("")} />}<button disabled={!reason || saving} onClick={() => void negative()} className="mt-3 h-9 w-full rounded-xl bg-[#7c27ff] text-xs font-semibold disabled:opacity-40">{saving ? "…" : isFa ? "ثبت بازخورد" : "Submit feedback"}</button></div>}
  </div>;
}

function CitedText({ content, sources, onOpen }: { content: string; sources: Source[]; onOpen: (source: Source) => void }) {
  const sourceMap = useMemo(() => new Map(sources.map((s) => [s.citationId, s])), [sources]);
  const parts = content.split(/(\[\d+\])/g);
  return <>{parts.map((part, index) => {
    const match = part.match(/^\[(\d+)\]$/); const source = match ? sourceMap.get(Number(match[1])) : undefined;
    return source ? <button key={index} onClick={() => onOpen(source)} title={source.title} className="chat-answer-citation">{source.citationId}</button> : <span key={index}>{part}</span>;
  })}</>;
}

function EvidenceDrawer({ source, isFa, onClose }: { source: Source; isFa: boolean; onClose: () => void }) {
  const relevance = source.score == null ? null : Math.max(0, Math.min(100, Math.round(source.score * 100)));
  return <div className="absolute inset-0 z-20 flex flex-col overflow-hidden rounded-[20px] border border-white/10 bg-[rgba(12,9,18,.96)] shadow-2xl backdrop-blur-2xl">
    <header className="flex shrink-0 items-center justify-between border-b border-white/[.07] p-4"><div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl border border-[#18c7f4]/20 bg-[#7c27ff]/25 text-[#d9a6ff]"><Quote size={15} /></span><div><p className="text-xs font-semibold">{isFa ? `شاهد شماره ${source.citationId}` : `Evidence ${source.citationId}`}</p><p className="mt-0.5 text-xs text-white/50">{isFa ? "متن بازیابی‌شده از منبع" : "Retrieved source passage"}</p></div></div><button onClick={onClose} className="app-icon-button grid size-8 place-items-center rounded-lg text-white/40"><X size={15} /></button></header>
    <div className="min-h-0 flex-1 overflow-y-auto p-4"><div className="rounded-2xl border border-white/[.07] bg-white/[.03] p-4"><div className="flex items-start gap-3"><FileText size={16} className="mt-0.5 shrink-0 text-[#c43cff]" /><div className="min-w-0"><p className="break-words text-xs font-semibold text-white/75">{source.title}</p><div className="mt-2 flex flex-wrap gap-2 text-xs text-white/50">{source.page ? <span>{isFa ? "صفحه" : "Page"} {source.page}</span> : <span>{isFa ? "بخش" : "Chunk"} {(source.chunkIndex ?? 0) + 1}</span>}{source.section && <span>· {source.section}</span>}<span className="text-violet-200/80">OCR · {source.ocrProvenance?.provider ?? (isFa ? "ارائه‌دهنده ثبت نشده" : "provider not recorded")}</span></div></div></div></div><blockquote className="mt-4 whitespace-pre-wrap rounded-2xl border-s-2 border-[#18c7f4]/45 bg-[#7c27ff]/10 p-4 text-xs leading-6 text-white/65">{source.excerpt}</blockquote>{relevance !== null && <div className="mt-4"><div className="mb-2 flex justify-between text-xs text-white/50"><span>{isFa ? "ارتباط بازیابی" : "Retrieval relevance"}</span><span>{relevance}%</span></div><div className="h-1 overflow-hidden rounded-full bg-white/[.06]"><div className="h-full rounded-full bg-gradient-to-r from-[#7c27ff] to-[#c43cff]" style={{ width: `${relevance}%` }} /></div><p className="mt-2 text-xs leading-5 text-white/45">{isFa ? "این مقدار امتیاز بازیابی است و میزان صحت پاسخ محسوب نمی‌شود." : "This is a retrieval score, not an answer-confidence score."}</p></div>}</div>
  </div>;
}
