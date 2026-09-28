import { apiRequest } from "./apiClient";

export interface AppNotification {
  id: string;
  kind: string;
  severity: "success" | "error" | "warning";
  title: string;
  body: string;
  target_path: string | null;
  read_at: string | null;
  created_at: string;
}

export const notificationService = {
  list: () => apiRequest<AppNotification[]>("/notifications", { headers: {} }),
  markRead: (id: string) => apiRequest<AppNotification>(`/notifications/${id}/read`, { method: "POST", headers: {} }),
  markAllRead: () => apiRequest<void>("/notifications/read-all", { method: "POST", headers: {} }),
  delete: (id: string) => apiRequest<void>(`/notifications/${id}`, { method: "DELETE", headers: {} }),
};
