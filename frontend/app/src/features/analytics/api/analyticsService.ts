import { apiRequest } from "../../../lib/apiClient";
export interface DailyMetric { date: string; queries: number; grounded: number; negative_feedback: number; }
export interface RankedMetric { id: string | null; name: string; queries: number; grounded_rate: number; positive_rate: number | null; }
export interface AnalyticsOverview { period_days: number; total_queries: number; active_users: number; grounded_rate: number; positive_feedback_rate: number | null; feedback_coverage: number; unanswered_queries: number; average_citations: number; indexed_documents: number; failed_documents: number; daily: DailyMetric[]; assistants: RankedMetric[]; knowledge_sets: RankedMetric[]; negative_reasons: Array<{ reason: string; count: number }>; recent_issues: Array<{ kind: string; name: string; detail: string; occurred_at: string }>; }
export interface NegativeFeedback { feedback_id: string; answer_id: string; document_set_id: string | null; document_set_name: string | null; question: string; answer: string; reason: string | null; comment: string | null; evaluation_case_id: string | null; created_at: string; }
export const analyticsService = {
  overview: (days: 7 | 30 | 90) => apiRequest<AnalyticsOverview>(`/analytics/overview?days=${days}`, undefined, "Analytics request failed"),
  negativeFeedback: () => apiRequest<NegativeFeedback[]>("/analytics/negative-feedback", undefined, "Analytics request failed"),
  convertFeedback: (feedbackId: string) => apiRequest<NegativeFeedback>(`/analytics/negative-feedback/${feedbackId}/evaluation-case`, { method: "POST" }, "Analytics request failed"),
};
