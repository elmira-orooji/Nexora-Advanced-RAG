import { useId, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import type { Source } from "../types/chat";

// Adapted from Vengeance UI Highlight Grid: one shared highlight follows the
// active cell. Motion layout handles wrapping, resizing, and RTL coordinates.
export default function AnswerSources({ sources, isFa, onOpen }: { sources: Source[]; isFa: boolean; onOpen: (source: Source) => void }) {
  const id = useId();
  const reduced = useReducedMotion();
  const [active, setActive] = useState<number | null>(null);
  const [expanded, setExpanded] = useState(false);
  return <section className="answer-source-section" aria-label={isFa ? "منابع استفاده‌شده در پاسخ" : "Sources used in this answer"}>
    <div className="answer-source-label"><span>{sources.length}</span>{isFa ? "منبع استفاده‌شده در پاسخ" : "Sources used in this answer"}</div>
    <div className="answer-source-grid" onMouseLeave={() => setActive(null)}>
      {(expanded ? sources : sources.slice(0, 4)).map((source, index) => <button key={`${source.id}-${index}`} type="button" className="answer-source-card"
        onMouseEnter={() => setActive(index)} onFocus={() => setActive(index)} onBlur={() => setActive(null)} onClick={() => onOpen(source)}>
        {active === index && <motion.span className="answer-source-highlight" layoutId={`source-${id}`} transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 35 }} />}
        <span className="answer-source-info"><strong dir="auto">{source.title}</strong><small>{isFa ? "منبع" : "Source"} {source.citationId ?? index + 1}{source.page ? ` · ${isFa ? "صفحه" : "Page"} ${source.page}` : ""}</small><small className="answer-source-ocr">OCR · {source.ocrProvenance?.provider ?? (isFa ? "ارائه‌دهنده ثبت نشده" : "provider not recorded")}</small></span>
        <ArrowUpRight size={14} className="answer-source-arrow" />
      </button>)}
    </div>
    {sources.length > 4 && <button className="answer-source-expand" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>{expanded ? (isFa ? "نمایش کمتر" : "Show less") : (isFa ? "نمایش همهٔ منابع" : "Show all sources")}</button>}
  </section>;
}
