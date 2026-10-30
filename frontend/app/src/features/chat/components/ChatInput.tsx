import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { ArrowUp, Mic, MicOff, Square } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "framer-motion";
const VoiceAura = lazy(() => import("../../../components/agents-ui/agent-audio-visualizer-aura").then(module => ({ default: module.AgentAudioVisualizerAura })));


interface SpeechRecognitionResultEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognitionController extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

interface SpeechRecognitionWindow extends Window {
  SpeechRecognition?: new () => SpeechRecognitionController;
  webkitSpeechRecognition?: new () => SpeechRecognitionController;
}

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
  const [isListening, setIsListening] = useState(false);
  const reducedMotion = useReducedMotion();
  const [voiceError, setVoiceError] = useState("");
  const sendPending = useRef(false);
  const recognitionRef = useRef<SpeechRecognitionController | null>(null);

  useEffect(() => () => {
    recognitionRef.current?.abort();
    recognitionRef.current = null;
  }, []);

  useEffect(() => {
    if (!disabled && !isSending) return;
    recognitionRef.current?.abort();
  }, [disabled, isSending]);

  const toggleVoiceInput = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }

    const speechWindow = window as SpeechRecognitionWindow;
    const SpeechRecognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceError(isFa ? "ورودی صوتی در این مرورگر پشتیبانی نمی‌شود." : "Voice input is not supported in this browser.");
      return;
    }

    setVoiceError("");
    const recognition = new SpeechRecognition();
    recognition.lang = isFa ? "fa-IR" : "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    let finalTranscript = "";
    const draftAtStart = value;
    recognition.onresult = (event) => {
      if (recognitionRef.current !== recognition) return;
      let interimTranscript = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (result.isFinal) finalTranscript += result[0]?.transcript ?? "";
        else interimTranscript += result[0]?.transcript ?? "";
      }
      const transcript = `${finalTranscript}${interimTranscript}`.trim();
      if (transcript) setValue([draftAtStart.trimEnd(), transcript].filter(Boolean).join(draftAtStart.trim() ? " " : ""));
    };
    recognition.onerror = (event) => {
      if (recognitionRef.current !== recognition) return;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setVoiceError(isFa ? "دسترسی میکروفون مجاز نیست. مجوز میکروفون مرورگر را بررسی کنید." : "Microphone access was denied. Check your browser's microphone permission.");
      } else if (event.error !== "no-speech" && event.error !== "aborted") {
        setVoiceError(isFa ? "تشخیص گفتار انجام نشد. دوباره تلاش کنید." : "Speech could not be recognized. Please try again.");
      }
    };
    recognition.onend = () => {
      if (recognitionRef.current !== recognition) return;
      recognitionRef.current = null;
      setIsListening(false);
    };
    recognitionRef.current = recognition;
    setIsListening(true);
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setIsListening(false);
      setVoiceError(isFa ? "شروع ضبط گفتار ممکن نشد. دوباره تلاش کنید." : "Could not start voice input. Please try again.");
    }
  };

  const handleSend = async () => {
    const message = value.trim();
    if (!message || disabled || isSending || sendPending.current) return;
    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    recognition?.abort();
    setIsListening(false);
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
    <div className={`mx-auto w-full ${prominent ? "max-w-4xl" : "max-w-3xl"}`}>
    <div className="app-composer flex w-full items-end gap-2 rounded-[22px] p-2 sm:p-2.5">
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
      <div className="mb-0.5 flex shrink-0 items-center gap-1">
      {isListening && <span className="grid size-10 place-items-center shrink-0" role="status" aria-label={isFa ? "در حال دریافت صدا" : "Listening"}>
        {reducedMotion ? <span className="size-2 rounded-full bg-[var(--brand)]" /> : <Suspense fallback={<span className="size-2 rounded-full bg-[var(--brand)]" />}><VoiceAura size="icon" state="listening" color="#7950bb" themeMode={document.documentElement.classList.contains("dark") ? "dark" : "light"} /></Suspense>}
      </span>}

      <button
        type="button"
        onClick={toggleVoiceInput}
        disabled={disabled || isSending}
        aria-label={isListening ? (isFa ? "توقف ورودی صوتی" : "Stop voice input") : (isFa ? "ورودی صوتی" : "Voice input")}
        aria-pressed={isListening}
        title={isListening ? (isFa ? "توقف ورودی صوتی" : "Stop voice input") : (isFa ? "ورودی صوتی" : "Voice input")}
        className={`grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] transition hover:bg-[var(--brand-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500 ${isListening ? "text-red-500" : "text-slate-500"} disabled:opacity-40`}
      >
        {isListening ? <MicOff size={18} aria-hidden="true" /> : <Mic size={18} aria-hidden="true" />}
      </button>
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
    </div>
    {voiceError && <p role="status" className="px-3 pt-1 text-xs text-red-600 dark:text-red-400">{voiceError}</p>}
    </div>
  );
}
