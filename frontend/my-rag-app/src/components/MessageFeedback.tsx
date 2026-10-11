import { useState } from "react";
import { ThumbsDown, ThumbsUp, X } from "lucide-react";
import { feedbackService, type FeedbackReason } from "../services/feedbackService";
import { useDialogFocus } from "../hooks/useDialogFocus";
import { useTransientMessage } from "../hooks/useTransientMessage";
import InlineError from "./InlineError";
export default function MessageFeedback({ responseId, isFa }: {
    responseId: string;
    isFa: boolean;
}) {
    const [rating, setRating] = useState<1 | -1 | null>(null);
    const [open, setOpen] = useState(false);
    const [reason, setReason] = useState<FeedbackReason | "">("");
    const [comment, setComment] = useState("");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const { message: feedbackStatus, show: setFeedbackStatus } = useTransientMessage();
    const positive = async () => {
      setSaving(true);
      setError("");
      setFeedbackStatus("");
      try {
        await feedbackService.save(responseId, 1);
        setRating(1);
        setOpen(false);
        setFeedbackStatus(isFa ? "از بازخورد شما متشکریم" : "Thanks for your feedback");
    }
    catch (e) {
        setError((e as Error).message);
        setOpen(true);
    }
    finally {
        setSaving(false);
      }
    };
    const negative = async () => {
      if (!reason) return;
      setSaving(true);
      setError("");
      setFeedbackStatus("");
      try {
        await feedbackService.save(responseId, -1, reason, comment.trim());
        setRating(-1);
        setOpen(false);
        setFeedbackStatus(isFa ? "بازخورد ثبت شد" : "Feedback saved");
    }
    catch (e) {
        setError((e as Error).message);
    }
    finally {
        setSaving(false);
      }
    };
    const reasons: Array<[
        FeedbackReason,
        string
    ]> = [
        ["incorrect", isFa ? "پاسخ اشتباه بود" : "The answer was incorrect"],
        ["irrelevant_source", isFa ? "منبع نامرتبط بود" : "The source was irrelevant"],
        ["incomplete", isFa ? "پاسخ ناقص بود" : "The answer was incomplete"],
        ["citation_issue", isFa ? "ارجاع مشکل داشت" : "The citation had an issue"],
        ["other", isFa ? "مورد دیگر" : "Something else"],
    ];
    const close = () => setOpen(false);
    const dialog = useDialogFocus<HTMLDivElement>(open, close);
    return <div className="chat-feedback relative flex items-center gap-1">
    <button disabled={saving} onClick={() => void positive()} aria-label="Helpful" className={`chat-feedback-action grid size-7 place-items-center rounded-lg transition ${rating === 1 ? "is-positive" : ""}`}><ThumbsUp size={13}/></button>
    <button disabled={saving} onClick={() => setOpen(!open)} aria-label="Not helpful" className={`chat-feedback-action grid size-7 place-items-center rounded-lg transition ${rating === -1 ? "is-negative" : ""}`}><ThumbsDown size={13}/></button>
    {feedbackStatus && <span role="status" className="chat-copy-confirmation">{feedbackStatus}</span>}
    {open && <div ref={dialog.ref} role="dialog" aria-modal="false" aria-labelledby={`feedback-title-${responseId}`} tabIndex={-1} onKeyDown={dialog.onKeyDown} className="nexora-dropdown absolute bottom-9 start-0 z-30 w-72 chat-feedback-dialog p-3"><div className="flex items-center justify-between"><p id={`feedback-title-${responseId}`} className="text-xs font-semibold">{isFa ? "مشکل پاسخ چه بود؟" : "What was wrong with the answer?"}</p><button onClick={close} aria-label={isFa ? "بستن پنجره بازخورد" : "Close feedback dialog"} className="grid size-6 place-items-center rounded-md "><X size={12}/></button></div><div className="mt-2 space-y-1">{reasons.map(([value, label]) => <button key={value} aria-pressed={reason === value} onClick={() => setReason(value)} className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-start text-xs ${reason === value ? "is-selected" : ""}`}><span className={`size-2 rounded-full border ${reason === value ? "border-[var(--answer-accent)] bg-[var(--answer-accent)]" : "border-[var(--answer-border)]"}`}/>{label}</button>)}</div>{reason === "other" && <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} rows={2} placeholder={isFa ? "توضیح اختیاری..." : "Optional details..."} className="mt-2 w-full resize-none rounded-xl chat-feedback-comment p-2.5 text-xs outline-none"/>}{error && <InlineError className="mt-2" message={error} onDismiss={() => setError("")}/>}<button disabled={!reason || saving} onClick={() => void negative()} className="mt-3 h-9 w-full rounded-xl chat-feedback-submit text-xs font-semibold disabled:opacity-40">{saving ? "…" : isFa ? "ثبت بازخورد" : "Submit feedback"}</button></div>}
  </div>;
}
