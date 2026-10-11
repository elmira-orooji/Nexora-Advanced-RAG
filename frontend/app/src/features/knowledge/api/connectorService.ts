import { apiRequest } from "../../../lib/apiClient";
const headers = (json = false) => ({ ...(json ? { "Content-Type": "application/json" } : {}) });
const request = <T,>(path: string, init?: RequestInit) => apiRequest<T>(path, init);
export type ConnectorType = "website" | "github" | "google_drive" | "s3" | "sharepoint" | "webhook";
export interface Connector { id: string; document_set_id: string; connector_type: ConnectorType; name: string; source_url: string; status: string; last_error: string | null; last_synced_at: string | null; schedule_enabled: boolean; schedule_interval: "hourly" | "daily" | "weekly"; next_sync_at: string | null; last_sync_summary: { discovered?: number; created?: number; updated?: number; unchanged?: number; deleted?: number }; created_at: string; }
export const connectorService = {
  list: (setId: string, signal?: AbortSignal) => request<Connector[]>(`/document-sets/${setId}/connectors`, { headers: headers(), signal }),
  create: (setId: string, payload: { connector_type: ConnectorType; name: string; source_url: string; schedule_enabled?: boolean; schedule_interval?: "hourly" | "daily" | "weekly" }) => request<Connector>(`/document-sets/${setId}/connectors`, { method: "POST", headers: headers(true), body: JSON.stringify(payload) }),
  createWebhook: (setId: string, name: string) => request<{ connector: Connector; endpoint: string; secret: string }>(`/document-sets/${setId}/connectors/webhook`, { method: "POST", headers: headers(true), body: JSON.stringify({ name }) }),
  sync: (setId: string, id: string) => request<{ discovered: number; created: number; updated: number; unchanged: number; deleted: number }>(`/document-sets/${setId}/connectors/${id}/sync`, { method: "POST", headers: headers() }),
  remove: (setId: string, id: string) => request<void>(`/document-sets/${setId}/connectors/${id}`, { method: "DELETE", headers: headers() }),
  updateSchedule: (setId: string, id: string, schedule_enabled: boolean, schedule_interval: "hourly" | "daily" | "weekly") => request<Connector>(`/document-sets/${setId}/connectors/${id}/schedule`, { method: "PATCH", headers: headers(true), body: JSON.stringify({ schedule_enabled, schedule_interval }) }),
};
