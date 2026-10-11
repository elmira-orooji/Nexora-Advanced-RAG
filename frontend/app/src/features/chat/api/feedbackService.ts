import { apiRequest } from "../../../lib/apiClient";
export type FeedbackReason = "incorrect" | "irrelevant_source" | "incomplete" | "citation_issue" | "other";

export const feedbackService = {
  async save(answerId: string, rating: -1 | 1, reason?: FeedbackReason, comment?: string) {
    return apiRequest(`/answers/${answerId}/feedback`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating, reason: reason || null, comment: comment || null }),
    }, "Could not save feedback");
  },
};
