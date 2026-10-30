import { lazy, Suspense, useEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";
const AgentAudioVisualizerAura = lazy(() => import("../../../components/agents-ui/agent-audio-visualizer-aura").then(module => ({ default: module.AgentAudioVisualizerAura })));
import NexoraAvatar from "../../../components/NexoraAvatar";
export default function AnswerLoading({ isFa, assistantName, slow = false }: { isFa: boolean; assistantName?: string; slow?: boolean }) {
  const reducedMotion = useReducedMotion();
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    const observer = new MutationObserver(() => setDark(document.documentElement.classList.contains("dark")));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  const label = slow
    ? (isFa ? "دریافت پاسخ بیش از حد معمول طول کشیده است. می‌توانید آن را متوقف کنید." : "This is taking longer than usual. You can stop the request.")
    : (isFa ? "در حال آماده‌سازی پاسخ" : "Preparing your answer");
  return <article className="answer-progress" dir={isFa ? "rtl" : "ltr"} role="status" aria-live="polite">
    <div className="answer-progress-brand"><NexoraAvatar /><span dir="auto" style={!assistantName || assistantName.trim().toLowerCase() === "nexora" ? { fontFamily: '"Cyber Copix", sans-serif', fontWeight: 400 } : undefined} className={!assistantName || assistantName.trim().toLowerCase() === "nexora" ? "answer-progress-wordmark" : undefined}>{assistantName || "Nexora"}</span></div>
    <div className="answer-progress-status"><span>{label}</span><span className="answer-progress-aura" aria-hidden="true">{reducedMotion ? <span className="answer-progress-static-dot" /> : <Suspense fallback={<span className="answer-progress-static-dot" />}><AgentAudioVisualizerAura size="icon" state="thinking" color="#7950bb" themeMode={dark ? "dark" : "light"} /></Suspense>}</span></div>
  </article>;
}
