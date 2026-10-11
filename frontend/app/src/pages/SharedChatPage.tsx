import { useEffect, useRef, useState } from "react";
import { FileText, LockKeyhole, MessageSquareText, Quote, Sparkles, X } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { authService } from "../features/auth/api/authService";
import { shareService, type SharedChat } from "../features/chat/api/shareService";
import AnswerSources from "../features/chat/components/AnswerSources";
import AnswerTrustBadge from "../features/chat/components/AnswerTrustBadge";
import type { Source } from "../features/chat/types/chat";
import "../styles/chat-answer.css";

function toSource(source: SharedChat["messages"][number]["sources"][number], index: number): Source {
  return { id: `${source.title}-${index}`, title: source.title, citationId: source.citation_id, excerpt: source.excerpt, page: source.page, section: source.section, ocrProvenance: source.ocr_provenance };
}

export default function SharedChatPage() {
  const { visibility, token } = useParams();
  const mode = visibility === "team" ? "team" : "link";
  const [data, setData] = useState<SharedChat | null>(null);
  const [error, setError] = useState("");
  const [evidence, setEvidence] = useState<Source | null>(null);
  useEffect(() => { if (!token) return; shareService.view(token, mode).then(setData).catch((reason) => setError(reason.message)); }, [mode, token]);

  if (mode === "team" && !authService.isAuthenticated()) return <div className="nexora-page grid min-h-[100dvh] place-items-center p-5"><div className="nexora-surface nexora-empty-state w-full max-w-sm"><LockKeyhole className="text-[var(--brand)]" /><h1 className="nexora-empty-state__title">Team-only conversation</h1><p className="nexora-empty-state__description">Sign in to your workspace to view this shared conversation.</p><Link to="/" className="nexora-action nexora-action--primary mt-2">Sign in</Link></div></div>;

  return <div className="nexora-page min-h-[100dvh] px-4 py-8 sm:px-6"><main className="mx-auto max-w-3xl"><header className="nexora-surface p-5 sm:p-6"><div className="flex items-center gap-3"><span className="grid size-11 place-items-center rounded-2xl bg-[var(--brand-soft)] text-[var(--brand)]"><MessageSquareText size={19} /></span><div className="min-w-0"><h1 className="truncate text-lg font-semibold text-[var(--text-primary)]">{data?.title || "Shared conversation"}</h1><p className="mt-1 text-xs text-[var(--text-muted)]">{data ? `Shared by ${data.owner_username} · ${new Date(data.created_at).toLocaleDateString()}` : "Loading read-only snapshot…"}</p></div></div></header>
    {error && <div className="mt-4 rounded-[var(--radius-panel)] border border-[color-mix(in_srgb,var(--status-danger)_30%,var(--border-subtle))] bg-[var(--state-danger-soft)] p-5 text-center text-xs text-[var(--status-danger)]">This shared conversation could not be loaded. Please check the link and try again.</div>}
    <section className="mt-4 space-y-4" aria-label="Shared conversation messages">{data?.messages.map((message, index) => {
      const sources = message.sources.map(toSource);
      return <article key={index} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>{message.role === "assistant" && <span className="mt-1 grid size-8 shrink-0 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><Sparkles size={14} /></span>}<div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "rounded-br-md bg-[var(--brand)] text-[var(--text-inverse)]" : "rounded-tl-md border border-[var(--border-subtle)] bg-[var(--surface-panel)] text-[var(--text-primary)]"}`}><p className="whitespace-pre-wrap">{message.content}</p>{message.role === "assistant" && <AnswerTrustBadge answerBasis={message.answer_basis} grounded={message.grounded} sourceCount={sources.length} isFa={false} onOpenSources={sources.length ? () => setEvidence(sources[0]) : undefined} />}{sources.length > 0 && <AnswerSources sources={sources} isFa={false} onOpen={setEvidence} />}</div></article>;
    })}</section><footer className="mt-8 text-center text-xs text-[var(--text-subtle)]">Read-only conversation snapshot · Nexora</footer></main>{evidence && <SharedEvidence source={evidence} onClose={() => setEvidence(null)} />}</div>;
}

function SharedEvidence({ source, onClose }: { source: Source; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { closeRef.current?.focus(); }, []);
  return <div className="nexora-modal-backdrop fixed inset-0 z-50 grid place-items-center p-4" onMouseDown={onClose}><section role="dialog" aria-modal="true" aria-labelledby="shared-source-title" className="nexora-surface w-full max-w-xl p-5" onMouseDown={(event) => event.stopPropagation()} onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}><header className="flex items-start justify-between gap-4"><div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><Quote size={18} /></span><div><h2 id="shared-source-title" className="text-sm font-semibold">Source {source.citationId ?? ""}</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Retrieved passage used in this answer</p></div></div><button ref={closeRef} type="button" onClick={onClose} className="app-icon-button grid size-8 place-items-center rounded-lg" aria-label="Close source"><X size={15} /></button></header><div className="mt-5 rounded-xl border border-[var(--border-subtle)] p-4"><div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)]"><FileText size={14} className="text-[var(--brand)]" />{source.title}</div>{(source.page || source.section) && <p className="mt-2 text-xs text-[var(--text-muted)]">{source.page ? `Page ${source.page}` : ""}{source.page && source.section ? " · " : ""}{source.section || ""}</p>}<blockquote className="mt-4 whitespace-pre-wrap border-s-2 border-[var(--brand)] bg-[var(--brand-soft)] p-4 text-sm leading-7 text-[var(--text-primary)]">{source.excerpt || "No source passage is available in this snapshot."}</blockquote></div></section></div>;
}
