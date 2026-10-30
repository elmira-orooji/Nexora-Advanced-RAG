import Markdown from "react-markdown";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import remarkGfm from "remark-gfm";
import type { Source } from "../types/chat";

type MarkdownNode = { type: string; value?: string; url?: string; children?: MarkdownNode[] };

// Convert citations only in prose. Code and existing links stay untouched.
function citationLinks() {
  return (tree: MarkdownNode) => {
    const walk = (node: MarkdownNode) => {
      if (["code", "inlineCode", "link", "image"].includes(node.type) || !node.children) return;
      node.children = node.children.flatMap((child): MarkdownNode[] => {
        if (child.type !== "text" || !child.value) { walk(child); return [child]; }
        return child.value.split(/(\[\d+\])/g).filter(Boolean).map((value) => {
          const match = /^\[(\d+)\]$/.exec(value);
          return match ? { type: "link", url: `#citation-${match[1]}`, children: [{ type: "text", value }] } : { type: "text", value };
        });
      });
    };
    walk(tree);
  };
}

export default function AnswerMarkdown({ content, sources, onOpen, animate = false }: { content: string; sources: Source[]; onOpen: (source: Source) => void; animate?: boolean }) {
  const { i18n } = useTranslation();
  const noAnswerMessages = [
    "پاسخی برای سوال شما یافت نشد",
    "پاسخی برای سوال شما در اسناد موجود نیست",
    "در اسناد مجاز اطلاعات مرتبطی برای پاسخ پیدا نشد",
    "No answer was found for your question",
    "No relevant information was found in the permitted indexed documents",
    "The available documents do not provide enough information to answer this question",
  ];
  const normalized = content.trim().replace(/[.。]+$/, "");
  const displayedContent = noAnswerMessages.includes(normalized)
    ? (i18n.language.startsWith("fa") ? "پاسخی برای سوال شما یافت نشد" : "No answer was found for your question.")
    : content;
  const [visibleLength, setVisibleLength] = useState(animate ? 0 : displayedContent.length);
  useEffect(() => {
    if (!animate || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVisibleLength(displayedContent.length);
      return;
    }
    let length = 0;
    setVisibleLength(0);
    // Reveal complete words; cap total duration for long answers.
    const words = displayedContent.match(/\S+\s*/g) || [];
    let index = 0;
    const batch = Math.max(1, Math.ceil(words.length / 160));
    const timer = window.setInterval(() => {
      for (let count = 0; count < batch && index < words.length; count++) length += words[index++].length;
      setVisibleLength(index >= words.length ? displayedContent.length : length);
      if (index >= words.length) window.clearInterval(timer);
    }, 70);
    return () => window.clearInterval(timer);
  }, [animate, displayedContent]);
  return <Markdown remarkPlugins={[remarkGfm, citationLinks]} skipHtml components={{
    a: ({ href, children }) => {
      const match = /^#citation-(\d+)$/.exec(href || "");
      if (match) {
        const source = sources.find((item) => item.citationId === Number(match[1]));
        return source ? <button type="button" className="chat-answer-citation" title={source.title} onClick={() => onOpen(source)}>{source.citationId}</button> : <>{children}</>;
      }
      return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
    },
    img: ({ alt }) => <span>{alt}</span>,
    table: ({ children }) => <div className="answer-table-scroll"><table>{children}</table></div>,
  }}>{displayedContent.slice(0, visibleLength)}</Markdown>;
}
