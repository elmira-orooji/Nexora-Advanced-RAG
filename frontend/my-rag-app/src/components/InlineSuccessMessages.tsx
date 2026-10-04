import toast, { resolveValue, useToasterStore } from "react-hot-toast";
import { CircleCheck, X } from "lucide-react";
import { useTranslation } from "react-i18next";

/** Success feedback stays in document flow instead of covering page controls. */
export default function InlineSuccessMessages() {
  const { toasts } = useToasterStore();
  const { i18n } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const messages = toasts.filter((item) => item.visible && item.type === "success");
  if (!messages.length) return null;
  return <div dir={isFa ? "rtl" : "ltr"} className="relative z-20 shrink-0 px-4 pt-3 sm:px-7" aria-label={isFa ? "نتیجهٔ عملیات" : "Operation results"}>
    <div className="mx-auto flex w-full max-w-[1000px] flex-col gap-2">
      {messages.map((item) => <div key={item.id} role="status" aria-live="polite" className="flex min-w-0 items-start gap-2 px-3 py-2.5 text-sm" style={{ background: "transparent", color: "var(--text-primary)" }}>
        <CircleCheck size={17} className="mt-0.5 shrink-0" style={{ color: "var(--status-success)" }} aria-hidden="true" />
        <div dir="auto" className="min-w-0 flex-1 break-words leading-6">{resolveValue(item.message, item)}</div>
        <button type="button" className="grid size-7 shrink-0 place-items-center rounded-md hover:bg-white/5" onClick={() => toast.dismiss(item.id)} aria-label={isFa ? "بستن پیام موفقیت" : "Dismiss success message"}><X size={15} /></button>
      </div>)}
    </div>
  </div>;
}
