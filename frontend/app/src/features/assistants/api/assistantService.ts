import type { DocumentSet } from "../../knowledge/api/knowledgeService";
import { apiRequest } from "../../../lib/apiClient";

const headers = (json = false) => ({ ...(json ? { "Content-Type": "application/json" } : {}) });
const request = <T,>(path: string, init?: RequestInit) => apiRequest<T>(path, init);

export interface CustomAssistant { model_id: string | null; answer_mode: "sources" | "hybrid"; id: string; name: string; description: string | null; instructions: string; is_active: boolean; created_by_id: string; document_set_ids: string[]; document_set_names: string[]; created_at: string; updated_at: string; }
export interface AssistantPayload { model_id: string | null; answer_mode: "sources" | "hybrid"; name: string; description?: string; instructions: string; document_set_ids: string[]; is_active: boolean; }
export interface AssistantAnswer { answer_basis: "sources" | "general" | "hybrid"; response_id: string; answer: string; grounded: boolean; citations: Array<{ id: number; chunk_id: string; document_id: string; filename: string; chunk_index: number; excerpt: string; score: number; page: number | null; section: string | null; ocr_provenance: { provider: string; model?: string; completed_at: string } | null }>; }

export const assistantService = {
  models: () => request<Array<{ id: string; name: string; free: boolean }>>("/assistants/models", { headers: headers() }),
  list: () => request<CustomAssistant[]>("/assistants", { headers: headers() }),
  listSets: () => request<DocumentSet[]>("/document-sets", { headers: headers() }),
  create: (payload: AssistantPayload) => request<CustomAssistant>("/assistants", { method: "POST", headers: headers(true), body: JSON.stringify(payload) }),
  update: (id: string, payload: Partial<AssistantPayload>) => request<CustomAssistant>(`/assistants/${id}`, { method: "PATCH", headers: headers(true), body: JSON.stringify(payload) }),
  remove: (id: string) => request<void>(`/assistants/${id}`, { method: "DELETE", headers: headers() }),
  ask: (id: string, question: string) => request<AssistantAnswer>(`/assistants/${id}/answer`, { method: "POST", headers: headers(true), body: JSON.stringify({ question, limit: 5 }) }),
};
