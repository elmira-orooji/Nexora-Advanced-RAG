import Markdown from "react-markdown";
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

export default function AnswerMarkdown({ content, sources, onOpen }: { content: string; sources: Source[]; onOpen: (source: Source) => void }) {
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
  }}>{content}</Markdown>;
}
