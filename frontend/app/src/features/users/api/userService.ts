import type { DocumentSet } from "../../knowledge/api/knowledgeService";
import { apiRequest } from "../../../lib/apiClient";

const headers = (json = false) => ({ ...(json ? { "Content-Type": "application/json" } : {}) });
const request = <T,>(path: string, init?: RequestInit) => apiRequest<T>(path, init);

export interface ManagedUser { id: string; username: string; job_title: string | null; role: "admin" | "user"; is_active: boolean; created_at: string; }
export interface CreateManagedUser { username: string; password: string; job_title?: string; role: "admin" | "user"; is_active: boolean; }
export type PermissionLevel = "view" | "edit" | "manage";
export interface SetPermission { document_set_id: string; document_set_name: string; permission: PermissionLevel; }

export const userService = {
  list: () => request<ManagedUser[]>("/users", { headers: headers() }),
  create: (payload: CreateManagedUser) => request<ManagedUser>("/users", { method: "POST", headers: headers(true), body: JSON.stringify(payload) }),
  remove: (userId: string) => request<void>(`/users/${userId}`, { method: "DELETE", headers: headers() }),
  listSets: () => request<DocumentSet[]>("/document-sets", { headers: headers() }),
  permissions: (userId: string) => request<SetPermission[]>(`/users/${userId}/document-set-permissions`, { headers: headers() }),
  savePermissions: (userId: string, permissions: Array<{ document_set_id: string; permission: PermissionLevel }>) => request<SetPermission[]>(`/users/${userId}/document-set-permissions`, { method: "PUT", headers: headers(true), body: JSON.stringify({ permissions }) }),
};
