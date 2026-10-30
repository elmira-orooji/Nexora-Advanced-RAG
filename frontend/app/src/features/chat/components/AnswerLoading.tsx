import NexoraAvatar from "../../../components/NexoraAvatar";
export default function AnswerLoading({ isFa, assistantName, slow = false }: { isFa: boolean; assistantName?: string; slow?: boolean }) {
  const label = slow
    ? (isFa ? "دریافت پاسخ بیش از حد معمول طول کشیده است. می‌توانید آن را متوقف کنید." : "This is taking longer than usual. You can stop the request.")
    : (isFa ? "در حال آماده‌سازی پاسخ" : "Preparing your answer");
  return <article className="answer-progress" dir={isFa ? "rtl" : "ltr"} role="status" aria-live="polite">
    <div className="answer-progress-brand"><NexoraAvatar /><span dir="auto">{assistantName || "Nexora"}</span></div>
    <div className="answer-progress-status"><span className="answer-progress-orbit" aria-hidden="true" /><span>{label}</span></div>
    <div className="answer-progress-track" aria-hidden="true"><span /></div>
  </article>;
}
