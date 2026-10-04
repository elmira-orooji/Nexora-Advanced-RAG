import NexoraAvatar from "./NexoraAvatar";
export default function AnswerLoading({ isFa, assistantName, slow = false }: { isFa: boolean; assistantName?: string; slow?: boolean }) {
  const label = slow
    ? (isFa ? "دریافت پاسخ بیش از حد معمول طول کشیده است. می‌توانید آن را متوقف کنید." : "This is taking longer than usual. You can stop the request.")
    : (isFa ? "در حال آماده‌سازی پاسخ" : "Preparing your answer");
  const liveLabel = isFa ? "در حال فکر کردن" : "Thinking";
  return <article className="chat-answer chat-loading" dir={isFa ? "rtl" : "ltr"}>
    <div className="chat-answer-body" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      <header className="chat-answer-heading" aria-hidden="true">
        <NexoraAvatar />
        <strong className={assistantName ? undefined : "nexora-wordmark"} dir={assistantName ? "auto" : "ltr"}>{assistantName || "Nexora"}</strong>
        <span className="answer-thinking-state"><span />{liveLabel}</span>
      </header>
      <div className="answer-thinking-content" aria-hidden="true">
        <p>{label}</p><span className="answer-thinking-dots"><i /><i /><i /></span>
      </div>
    </div>
  </article>;
}
