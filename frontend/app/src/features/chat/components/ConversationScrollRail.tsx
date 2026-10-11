import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { ChatMessage } from "../types/chat";
import { useEffect, useState, type RefObject } from "react";

interface Props {
  viewportRef: RefObject<HTMLDivElement | null>;
  isFa: boolean;
  messages: ChatMessage[];
}

export default function ConversationScrollRail({ viewportRef, isFa, messages }: Props) {
  const reducedMotion = useReducedMotion();
  const [keyboardFocus, setKeyboardFocus] = useState(false);
  const [preview, setPreview] = useState<{ id: string; tick: number; y: number } | null>(null);
  const updatePreview = (clientY: number, bounds: DOMRect) => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const fraction = Math.max(0, Math.min(1, (clientY - bounds.top) / bounds.height));
    const target = fraction * (viewport.scrollHeight - viewport.clientHeight);
    const origin = viewport.getBoundingClientRect().top;
    const articles = Array.from(viewport.querySelectorAll<HTMLElement>("[data-scroll-message]"));
    const nearest = articles.reduce<HTMLElement | null>((best, item) => {
      const distance = (node: HTMLElement) => Math.abs(node.getBoundingClientRect().top - origin + viewport.scrollTop - target);
      return !best || distance(item) < distance(best) ? item : best;
    }, null);
    if (nearest) setPreview({ id: nearest.dataset.scrollMessage!, tick: Math.round(fraction * 27), y: Math.max(65, Math.min(bounds.height - 65, clientY - bounds.top)) });
  };
  const [metrics, setMetrics] = useState({ progress: 0, visible: 1 });
  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    let frame = 0;
    const measure = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const maximum = viewport.scrollHeight - viewport.clientHeight;
        setMetrics({
          progress: maximum > 1 ? Math.max(0, Math.min(1, viewport.scrollTop / maximum)) : 0,
          visible: maximum > 1 ? viewport.clientHeight / viewport.scrollHeight : 1,
        });
      });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(viewport);
    if (viewport.firstElementChild) observer.observe(viewport.firstElementChild);
    viewport.addEventListener("scroll", measure, { passive: true });
    measure();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      viewport.removeEventListener("scroll", measure);
    };
  }, [viewportRef]);

  if (metrics.visible >= 1) return null;
  const activeLength = Math.max(1, Math.round(metrics.visible * 28));
  const activeStart = Math.round(metrics.progress * (28 - activeLength));
  const message = messages.find((item) => item.id === preview?.id);
  return <div className={`conversation-scroll-rail ${keyboardFocus ? "is-keyboard-focused" : ""}`} onPointerLeave={() => setPreview(null)}>
    <AnimatePresence>
      {preview && message && <motion.div key="preview" className="conversation-scroll-preview" role="tooltip"
        initial={{ opacity: 0, x: isFa ? -6 : 6 }} animate={{ opacity: 1, x: 0, top: preview.y }} exit={{ opacity: 0 }}
        transition={reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 400, damping: 32 }}>
        <span>{message.role === "user" ? (isFa ? "شما" : "You") : "Nexora"}</span>
        <p dir="auto">{message.content}</p>
      </motion.div>}
    </AnimatePresence>
    <div className="conversation-scroll-ticks" aria-hidden="true">
      {Array.from({ length: 28 }, (_, index) => <span key={index} style={{ width: preview ? `${7 + Math.max(0, 5 - Math.abs(index - preview.tick)) * 2.6}px` : undefined }} className={index >= activeStart && index < activeStart + activeLength ? "is-active" : ""} />)}
    </div>
    <input
      type="range" min={0} max={1000} step={1}
      value={Math.round(metrics.progress * 1000)}
      aria-label={isFa ? "موقعیت در گفتگو" : "Conversation scroll position"}
      aria-orientation="vertical"
      aria-valuetext={`${Math.round(metrics.progress * 100)}%`}
      onPointerDown={(event) => {
        event.preventDefault();
        setKeyboardFocus(false);
        event.currentTarget.focus();
        event.currentTarget.setPointerCapture(event.pointerId);
        const bounds = event.currentTarget.getBoundingClientRect();
        const viewport = viewportRef.current;
        if (viewport) viewport.scrollTop = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)) * (viewport.scrollHeight - viewport.clientHeight);
      }}
      onPointerMove={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        if (event.pointerType === "mouse") updatePreview(event.clientY, bounds);
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
        const viewport = viewportRef.current;
        if (viewport) viewport.scrollTop = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)) * (viewport.scrollHeight - viewport.clientHeight);
      }}
      onBlur={() => { setKeyboardFocus(false); setPreview(null); }}
      onKeyDown={(event) => {
        setKeyboardFocus(true);
        if (event.key === "Escape") { setPreview(null); return; }
        const viewport = viewportRef.current;
        if (!viewport) return;
        const maximum = viewport.scrollHeight - viewport.clientHeight;
        const destinations: Record<string, number> = {
          Home: 0, End: maximum,
          ArrowUp: viewport.scrollTop - 40, ArrowDown: viewport.scrollTop + 40,
          PageUp: viewport.scrollTop - viewport.clientHeight, PageDown: viewport.scrollTop + viewport.clientHeight,
        };
        if (event.key in destinations) { event.preventDefault(); viewport.scrollTop = destinations[event.key]; }
      }}
      onInput={(event) => {
        const viewport = viewportRef.current;
        if (viewport) viewport.scrollTop = Number(event.currentTarget.value) / 1000 * (viewport.scrollHeight - viewport.clientHeight);
      }}
    />
  </div>;
}

