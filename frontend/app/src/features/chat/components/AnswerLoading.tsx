import NexoraAvatar from "../../../components/NexoraAvatar";
export default function AnswerLoading({ isFa, assistantName, slow = false }: { isFa: boolean; assistantName?: string; slow?: boolean }) {
  const label = slow
    ? (isFa ? "دریافت پاسخ بیش از حد معمول طول کشیده است. می‌توانید آن را متوقف کنید." : "This is taking longer than usual. You can stop the request.")
    : (isFa ? "در حال آماده‌سازی پاسخ" : "Preparing your answer");
  return <article className="answer-progress" dir={isFa ? "rtl" : "ltr"} role="status" aria-live="polite">
    <div className="answer-progress-brand"><NexoraAvatar /><span dir="auto" className={!assistantName || assistantName.toLowerCase() == "nexora" ? "answer-progress-wordmark" : undefined}>{assistantName || "Nexora"}</span></div>
    <div className="answer-progress-status"><span>{label}</span><span className="answer-progress-pulse" aria-hidden="true"><i /><i /><i /></span></div>
  </article>;
}
