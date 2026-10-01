import { apiFetch, apiRequest, apiUpload, type ApiRequestInit } from "./apiClient";

export interface KnowledgeDocument {
  id: string;
  filename: string;
  content_type: string | null;
  status: string;
  processing_error: string | null;
  processing_progress: number;
  processing_stage: string;
  ocr_provenance: { provider: string; model?: string; completed_at: string } | null;
  author: string | null;
  language: string | null;
  source_type: string | null;
  document_date: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  parent_index: number;
  parent_content: string;
  token_count: number | null;
  created_at: string;
  page_number: number | null;
  is_active: boolean;
  keywords: string[];
  suggested_questions: string[];
}

export interface DocumentDetail extends KnowledgeDocument {
  chunks: DocumentChunk[];
}

export interface MetadataFilters {
  authors?: string[];
  languages?: string[];
  source_types?: string[];
  tags?: string[];
  date_from?: string;
  date_to?: string;
}

export interface DocumentSet {
  id: string;
  name: string;
  description: string | null;
  created_by_id: string;
  document_count: number;
  indexed_document_count: number;
  access_level: "view" | "edit" | "manage";
  child_chunk_size: number;
  chunk_overlap: number;
  parent_chunk_size: number;
  created_at: string;
  updated_at: string;
}

interface RagResponse {
  response_id: string;
  answer: string;
  grounded: boolean;
  citations: Array<{
    id: number;
    chunk_id: string;
    document_id: string;
    filename: string;
    chunk_index: number;
    excerpt: string;
    score: number;
    page: number | null;
    section: string | null;
    ocr_provenance: { provider: string; model?: string; completed_at: string } | null;
  }>;
  sources: Array<{
    chunk_id: string;
    document_id: string;
    filename: string;
    content: string;
    score: number;
    ocr_provenance: { provider: string; model?: string; completed_at: string } | null;
  }>;
}

export interface ResearchResponse extends RagResponse {
  steps: Array<{ query: string; evidence_count: number }>;
  evidence_reviewed: number;
}

export interface PlaygroundResult {
  chunk_id: string; document_id: string; filename: string; chunk_index: number; parent_index: number;
  content: string; matched_child_content: string; score: number;
  diagnostics: { method: string; vector_rank: number | null; bm25_rank: number | null; hybrid_score: number; reranker_score: number; term_coverage: number; phrase_match: boolean; expanded_to_parent: boolean };
}
export interface PlaygroundResponse { query: string; scoped_document_count: number; result_count: number; results: PlaygroundResult[]; }
export interface PipelineTraceResponse {
  question: string; answer: string; grounded: boolean; total_duration_ms: number;
  stages: Array<{ key: "question" | "retrieval" | "rerank" | "answer"; duration_ms: number; input_count: number; output_count: number }>;
  results: PlaygroundResult[];
  citations: Array<{ id: number; chunk_id: string; filename: string; ocr_provenance: { provider: string; model?: string; completed_at: string } | null }>;
  usage: UsageMetrics | null;
}
export interface UsageMetrics { model: string; latency_ms: number; prompt_tokens: number; completion_tokens: number; total_tokens: number; estimated_cost_usd: number; }
export interface EvaluationCase { id: string; document_set_id: string; question: string; expected_answer: string | null; expected_keywords: string[]; relevant_chunk_ids: string[]; created_at: string; updated_at: string; }
export interface RetrieverConfig { name: string; vector_weight: number; bm25_weight: number; use_reranker: boolean; top_k: number; }
export interface RetrieverVariant { config: RetrieverConfig; duration_ms: number; answer: string; grounded: boolean; results: PlaygroundResult[]; citations: Array<{ id: number; chunk_id: string; filename: string }>; usage: UsageMetrics | null; }
export interface RetrieverComparison { question: string; overlap_count: number; rank_changes: Record<string, number>; variant_a: RetrieverVariant; variant_b: RetrieverVariant; }

function headers(json = false) {
  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
  };
}

const request = <T,>(path: string, init?: ApiRequestInit) => apiRequest<T>(path, init);

export const knowledgeService = {
  listSets: () => request<DocumentSet[]>("/document-sets", { headers: headers() }),
  createSet: (data: { name: string; description?: string; child_chunk_size?: number; chunk_overlap?: number; parent_chunk_size?: number }) =>
    request<DocumentSet>("/document-sets", { method: "POST", headers: headers(true), body: JSON.stringify(data) }),
  updateSet: (id: string, data: { name?: string; description?: string | null; child_chunk_size?: number; chunk_overlap?: number; parent_chunk_size?: number }) =>
    request<DocumentSet>(`/document-sets/${id}`, { method: "PATCH", headers: headers(true), body: JSON.stringify(data) }),
  deleteSet: (id: string) => request<void>(`/document-sets/${id}`, { method: "DELETE", headers: headers() }),
  listDocuments: (setId?: string, signal?: AbortSignal) =>
    request<KnowledgeDocument[]>(`/documents?limit=100${setId ? `&document_set_id=${encodeURIComponent(setId)}` : ""}`, { headers: headers(), signal }),
  getDocument: (documentId: string) => request<DocumentDetail>(`/documents/${documentId}`, { headers: headers() }),
  getDocumentContent: async (documentId: string) => {
    const response = await apiFetch(`/documents/${documentId}/content`, { headers: headers() });
    if (!response.ok) throw new Error("Document preview is unavailable");
    return response.blob();
  },
  updateChunk: (documentId: string, chunkId: string, data: { content?: string; is_active?: boolean }) =>
    request<DocumentChunk>(`/documents/${documentId}/chunks/${chunkId}`, { method: "PATCH", headers: headers(true), body: JSON.stringify(data) }),
  enrichChunk: (documentId: string, chunkId: string) =>
    request<DocumentChunk>(`/documents/${documentId}/chunks/${chunkId}/enrich`, { method: "POST", headers: headers() }),
  uploadDocument: async (file: File, setId: string, onProgress: (progress: number) => void = () => undefined, idempotencyKey?: string) => {
    const form = new FormData();
    form.append("file", file);
    return apiUpload<KnowledgeDocument>(`/documents/ingest?document_set_id=${encodeURIComponent(setId)}`, form, onProgress, idempotencyKey);
  },
  removeDocumentFromSet: (setId: string, documentId: string) =>
    request(`/document-sets/${setId}/documents/${documentId}`, { method: "DELETE", headers: headers() }),
  deleteDocument: (documentId: string) => request(`/documents/${documentId}`, { method: "DELETE", headers: headers() }),
  retryDocument: (documentId: string) => request<KnowledgeDocument>(`/documents/${documentId}/retry`, { method: "POST", headers: headers() }),
  pauseDocument: (documentId: string) => request<KnowledgeDocument>(`/documents/${documentId}/pause`, { method: "POST", headers: headers() }),
  updateMetadata: (documentId: string, data: { author?: string | null; language?: string | null; source_type?: string | null; document_date?: string | null; tags?: string[] }) =>
    request<KnowledgeDocument>(`/documents/${documentId}/metadata`, { method: "PATCH", headers: headers(true), body: JSON.stringify(data) }),
  testRetrieval: (query: string, documentSetId: string, limit: number, documentIds?: string[], filters?: MetadataFilters) =>
    request<PlaygroundResponse>("/search/playground", { method: "POST", headers: headers(true), body: JSON.stringify({ query, document_set_id: documentSetId, document_ids: documentIds?.length ? documentIds : null, limit, filters: filters && Object.keys(filters).length ? filters : null }) }),
  tracePipeline: (query: string, documentSetId: string, limit: number, documentIds?: string[], filters?: MetadataFilters) =>
    request<PipelineTraceResponse>("/search/trace", { method: "POST", headers: headers(true), body: JSON.stringify({ query, document_set_id: documentSetId, document_ids: documentIds?.length ? documentIds : null, limit, filters: filters && Object.keys(filters).length ? filters : null }) }),
  compareRetrievers: (query: string, documentSetId: string, configA: RetrieverConfig, configB: RetrieverConfig, documentIds?: string[], filters?: MetadataFilters) =>
    request<RetrieverComparison>("/search/compare", { method: "POST", headers: headers(true), body: JSON.stringify({ query, document_set_id: documentSetId, document_ids: documentIds?.length ? documentIds : null, limit: Math.max(configA.top_k, configB.top_k), filters: filters && Object.keys(filters).length ? filters : null, config_a: configA, config_b: configB }) }),
  listEvaluationCases: (setId: string) => request<EvaluationCase[]>(`/document-sets/${setId}/evaluation-cases`, { headers: headers() }),
  createEvaluationCase: (setId: string, data: { question: string; expected_answer?: string | null; expected_keywords: string[]; relevant_chunk_ids: string[] }) => request<EvaluationCase>(`/document-sets/${setId}/evaluation-cases`, { method: "POST", headers: headers(true), body: JSON.stringify(data) }),
  deleteEvaluationCase: (setId: string, caseId: string) => request<void>(`/document-sets/${setId}/evaluation-cases/${caseId}`, { method: "DELETE", headers: headers() }),
  ask: (question: string, documentSetId: string, documentIds?: string[], filters?: MetadataFilters, signal?: AbortSignal) =>
    request<RagResponse>("/rag/answer", {
      method: "POST",
      headers: headers(true),
      signal,
      timeoutMs: 90_000,
      body: JSON.stringify({
        question,
        document_set_id: documentSetId,
        document_ids: documentIds?.length ? documentIds : null,
        limit: 5,
        filters: filters && Object.keys(filters).length ? filters : null,
      }),
    }),
  research: (question: string, documentSetId: string, documentIds?: string[], filters?: MetadataFilters, signal?: AbortSignal) =>
    request<ResearchResponse>("/research/run", {
      method: "POST",
      headers: headers(true),
      signal,
      timeoutMs: 90_000,
      body: JSON.stringify({ question, document_set_id: documentSetId, document_ids: documentIds?.length ? documentIds : null, filters: filters && Object.keys(filters).length ? filters : null, max_steps: 4 }),
    }),
};
