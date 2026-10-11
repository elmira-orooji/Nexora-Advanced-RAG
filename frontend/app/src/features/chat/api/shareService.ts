import type { AnswerBasis, ChatMessage } from "../types/chat";
import { apiRequest } from "../../../lib/apiClient";
export interface SharedChat { id: string; title: string; owner_username: string; visibility: "team" | "link"; messages: Array<{ role: "user" | "assistant"; content: string; grounded?: boolean; answer_basis?: AnswerBasis | null; sources: Array<{ title: string; citation_id?: number; excerpt?: string; page?: number | null; section?: string | null; ocr_provenance?: { provider: string; model?: string; completed_at: string } | null }> }>; created_at: string; expires_at: string | null; }
export const shareService = {
  async list() { return apiRequest<Array<{ id: string; title: string; visibility: "team" | "link"; expires_at: string | null; created_at: string }>>("/chat-shares"); },
  async create(title: string, visibility: "team" | "link", expiresInDays: 1 | 7 | 30 | null, messages: ChatMessage[]) {
    return apiRequest<{ id: string; share_token: string; visibility: "team" | "link"; expires_at: string | null }>("/chat-shares", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, visibility, expires_in_days: expiresInDays, messages: messages.map((message) => ({ role: message.role, content: message.content, grounded: message.grounded, answer_basis: message.answerBasis, sources: (message.sources || []).map((source) => ({ title: source.title, citation_id: source.citationId, excerpt: source.excerpt, page: source.page, section: source.section, ocr_provenance: source.ocrProvenance })) })) }) });
  },
  async view(token: string, visibility: "team" | "link") { return apiRequest<SharedChat>(`/shared/${visibility}/${encodeURIComponent(token)}`, { credentials: visibility === "team" ? "include" : "omit" }); },
  async revoke(id: string) { return apiRequest<void>(`/chat-shares/${id}`, { method: "DELETE" }, "Could not revoke shared conversation"); },
};
