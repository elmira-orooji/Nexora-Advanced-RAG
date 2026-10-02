import { useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import { useTranslation } from "react-i18next";

interface ChatInputProps {
  disabled: boolean;
  onSend: (message: string) => boolean | Promise<boolean>;
  isSending?: boolean;
  onCancel?: () => void;
  initialValue?: string;
  prominent?: boolean;
}

export default function ChatInput({ disabled, onSend, isSending = false, onCancel, initialValue = "", prominent = false }: ChatInputProps) {
  const { i18n } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const [value, setValue] = useState(initialValue);
  const sendPending = useRef(false);

  const handleSend = async () => {
    const message = value.trim();
    if (!message || disabled || isSending || sendPending.current) return;
    const draft = value;
    sendPending.current = true;
    setValue("");
    try {
      if (!await onSend(message)) setValue((current) => current || draft);
    } catch {
      setValue((current) => current || draft);
    } finally {
      sendPending.current = false;
    }
  };

  return (
    <div className={`app-composer mx-auto flex w-full items-end gap-2 rounded-[22px] p-2 sm:p-2.5 ${prominent ? "max-w-4xl" : "max-w-3xl"}`}>
      <textarea
        aria-label={isFa ? "پیام" : "Message"}
        rows={1}
        value={value}
        disabled={disabled || isSending}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            void handleSend();
          }
        }}
        placeholder={isFa ? "از پایگاه دانش خود بپرسید..." : "Ask your knowledge base..."}
        className="chat-composer-textarea max-h-32 min-h-10 min-w-0 flex-1 resize-none overflow-y-auto bg-transparent px-1 py-2.5 text-sm leading-6 outline-none disabled:opacity-50"
      />
      <button
        type="button"
        onClick={isSending ? onCancel : () => void handleSend()}
        disabled={isSending ? !onCancel : disabled || !value.trim()}
        aria-label={isSending ? (isFa ? "توقف تولید پاسخ" : "Stop generating") : (isFa ? "ارسال پیام" : "Send message")}
        title={isSending ? (isFa ? "توقف تولید پاسخ" : "Stop generating") : undefined}
        className={`chat-send-button mb-0.5 grid size-10 shrink-0 place-items-center rounded-xl text-white transition ${isSending ? "bg-[#4b556b] shadow-[0_8px_20px_rgba(30,41,59,.22)] hover:bg-[#374151]" : "bg-[#7c27ff] shadow-[0_8px_24px_rgba(124,39,255,.35)] hover:-translate-y-0.5 hover:bg-[#9238ff]"} disabled:translate-y-0 disabled:bg-white/[.06] disabled:text-white/20 disabled:shadow-none`}
      >
        {isSending ? <Square size={15} fill="currentColor" /> : <ArrowUp size={18} />}
      </button>
    </div>
  );
}
