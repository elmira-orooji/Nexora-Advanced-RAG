import { useMemo, useState } from "react";
import { FileText, Quote, Telescope, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ChatMessage, Source } from "../types/chat";
import CopyTextButton from "../../../components/CopyTextButton";
import MessageFeedback from "./MessageFeedback";
import AnswerTrustBadge from "./AnswerTrustBadge";
import AnswerSources from "./AnswerSources";
import AnswerLoading from "./AnswerLoading";
import InlineError from "../../../components/InlineError";
import NexoraAvatar from "../../../components/NexoraAvatar";
import "../../../styles/chat-answer.css";
interface ChatWindowProps {
    messages: ChatMessage[];
    isThinking: boolean;
    isSlow?: boolean;
}
export default function ChatWindow({ messages, isThinking, isSlow = false }: ChatWindowProps) {
    const { i18n } = useTranslation();
    const isFa = i18n.language.startsWith("fa");
    const [evidence, setEvidence] = useState<Source | null>(null);
    const [copyError, setCopyError] = useState("");
    return <div className="chat-thread knowledge-chat relative h-full" dir={isFa ? "rtl" : "ltr"}>
    {copyError && <div className="px-3 pt-3"><InlineError message={copyError} onDismiss={() => setCopyError("")}/></div>}
    <div className="chat-thread-scroll h-full overflow-y-auto pe-1">
      <div className="chat-thread-messages">
      {messages.map((message) => message.role === "user"
            ? <article key={message.id} className="chat-question"><div className="chat-question-stack"><div className="chat-question-bubble">{message.content}</div><div className="chat-question-meta"><time dateTime={message.createdAt} title={new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" }).format(new Date(message.createdAt))}>{new Intl.DateTimeFormat(i18n.language, { hour: "numeric", minute: "2-digit" }).format(new Date(message.createdAt))}</time><CopyTextButton value={message.content} success={isFa ? "پرسش کپی شد" : "Question copied"} failure={isFa ? "کپی پرسش انجام نشد" : "Could not copy question"} label={isFa ? "کپی پرسش" : "Copy question"} onError={setCopyError}/></div></div></article>
            : <article key={message.id} className="chat-answer">
          <NexoraAvatar />
          <div className="chat-answer-body">
            <header className="chat-answer-heading"><strong>Nexora</strong></header>
            <div className="chat-answer-text" dir="auto"><CitedText content={message.content} sources={message.sources || []} onOpen={setEvidence}/></div>
            <AnswerTrustBadge answerBasis={message.answerBasis} grounded={message.grounded} sourceCount={message.sources?.length ?? 0} isFa={isFa} onOpenSources={message.sources?.length ? () => setEvidence(message.sources![0]) : undefined}/>
            {message.research && <details className="chat-answer-research"><summary><Telescope size={14}/>{isFa ? "مراحل پژوهش" : "Research trail"}<span>{message.research.steps.length} {isFa ? "جست‌وجو" : "searches"} · {message.research.evidenceReviewed} {isFa ? "شاهد" : "evidence"}</span></summary><div className="chat-answer-research-steps">{message.research.steps.map((step, index) => <div key={index}><span className="chat-answer-source-number">{index + 1}</span><span className="chat-answer-research-query">{step.query}</span><span>{step.evidence_count}</span></div>)}</div></details>}
            {message.sources?.length ? <AnswerSources sources={message.sources} isFa={isFa} onOpen={setEvidence}/> : null}
            <div className="chat-answer-actions"><CopyTextButton value={message.content} success={isFa ? "پاسخ کپی شد" : "Response copied"} failure={isFa ? "کپی پاسخ ناموفق بود" : "Could not copy response"} label={isFa ? "کپی پاسخ" : "Copy response"} className="chat-answer-action" onError={setCopyError}/>{message.responseId && <MessageFeedback responseId={message.responseId} isFa={isFa}/>}</div>
          </div>
        </article>)}
      {isThinking && <AnswerLoading isFa={isFa} slow={isSlow}/>}
      </div>
    </div>
    {evidence && <EvidenceDrawer source={evidence} isFa={isFa} onClose={() => setEvidence(null)}/>}
  </div>;
}
function CitedText({ content, sources, onOpen }: {
    content: string;
    sources: Source[];
    onOpen: (source: Source) => void;
}) {
    const sourceMap = useMemo(() => new Map(sources.map((s) => [s.citationId, s])), [sources]);
    const parts = content.split(/(\[\d+\])/g);
    return <>{parts.map((part, index) => {
            const match = part.match(/^\[(\d+)\]$/);
            const source = match ? sourceMap.get(Number(match[1])) : undefined;
            return source ? <button key={index} onClick={() => onOpen(source)} title={source.title} className="chat-answer-citation">{source.citationId}</button> : <span key={index}>{part}</span>;
        })}</>;
}
function EvidenceDrawer({ source, isFa, onClose }: {
    source: Source;
    isFa: boolean;
    onClose: () => void;
}) {
    const relevance = source.score == null ? null : Math.max(0, Math.min(100, Math.round(source.score * 100)));
    return <div className="absolute inset-0 z-20 flex flex-col overflow-hidden rounded-[20px] border border-white/10 bg-[rgba(12,9,18,.96)] shadow-2xl backdrop-blur-2xl">
    <header className="flex shrink-0 items-center justify-between border-b border-white/[.07] p-4"><div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl border border-[#18c7f4]/20 bg-[#7c27ff]/25 text-[#d9a6ff]"><Quote size={15}/></span><div><p className="text-xs font-semibold">{isFa ? `شاهد شماره ${source.citationId}` : `Evidence ${source.citationId}`}</p><p className="mt-0.5 text-xs text-white/50">{isFa ? "متن بازیابی‌شده از منبع" : "Retrieved source passage"}</p></div></div><button onClick={onClose} className="app-icon-button grid size-8 place-items-center rounded-lg text-white/40"><X size={15}/></button></header>
    <div className="min-h-0 flex-1 overflow-y-auto p-4"><div className="rounded-2xl border border-white/[.07] bg-white/[.03] p-4"><div className="flex items-start gap-3"><FileText size={16} className="mt-0.5 shrink-0 text-[#c43cff]"/><div className="min-w-0"><p className="break-words text-xs font-semibold text-white/75">{source.title}</p><div className="mt-2 flex flex-wrap gap-2 text-xs text-white/50">{source.page ? <span>{isFa ? "صفحه" : "Page"} {source.page}</span> : <span>{isFa ? "بخش" : "Chunk"} {(source.chunkIndex ?? 0) + 1}</span>}{source.section && <span>· {source.section}</span>}<span className="text-violet-200/80">OCR · {source.ocrProvenance?.provider ?? (isFa ? "ارائه‌دهنده ثبت نشده" : "provider not recorded")}</span></div></div></div></div><blockquote className="mt-4 whitespace-pre-wrap rounded-2xl border-s-2 border-[#18c7f4]/45 bg-[#7c27ff]/10 p-4 text-xs leading-6 text-white/65">{source.excerpt}</blockquote>{relevance !== null && <div className="mt-4"><div className="mb-2 flex justify-between text-xs text-white/50"><span>{isFa ? "ارتباط بازیابی" : "Retrieval relevance"}</span><span>{relevance}%</span></div><div className="h-1 overflow-hidden rounded-full bg-white/[.06]"><div className="h-full rounded-full bg-gradient-to-r from-[#7c27ff] to-[#c43cff]" style={{ width: `${relevance}%` }}/></div><p className="mt-2 text-xs leading-5 text-white/45">{isFa ? "این مقدار امتیاز بازیابی است و میزان صحت پاسخ محسوب نمی‌شود." : "This is a retrieval score, not an answer-confidence score."}</p></div>}</div>
  </div>;
}
