import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalyticsPage from "./AnalyticsPage";

const mocks = vi.hoisted(() => ({ overview: vi.fn(), toastError: vi.fn() }));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" }, t: (key: string) => key }),
}));
vi.mock("react-hot-toast", () => ({ default: { error: mocks.toastError } }));
vi.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div> },
  useReducedMotion: () => true,
}));
vi.mock("../services/authService", () => ({ authService: { getUser: () => ({ username: "manager" }) } }));
vi.mock("../services/analyticsService", () => ({ analyticsService: { overview: mocks.overview } }));

const overview = {
  period_days: 30,
  total_queries: 12,
  active_users: 3,
  grounded_rate: 75,
  positive_feedback_rate: 80,
  feedback_coverage: 50,
  unanswered_queries: 1,
  average_citations: 2,
  indexed_documents: 9,
  failed_documents: 0,
  daily: [{ date: "2026-09-01", queries: 12, grounded: 9, negative_feedback: 1 }],
  assistants: [],
  knowledge_sets: [],
  negative_reasons: [],
  recent_issues: [],
};
const recentIssue = {
  kind: "document",
  name: "report.pdf",
  detail: "OCR processing failed",
  occurred_at: "2026-09-24T14:46:00Z",
};

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.overview.mockResolvedValueOnce(overview);
  });

  it("keeps the loaded period selected when a new period fails", async () => {
    mocks.overview.mockRejectedValueOnce(new Error("Analytics unavailable"));
    render(<AnalyticsPage />);

    const thirtyDays = await screen.findByRole("button", { name: "30 days" });
    await waitFor(() => expect(thirtyDays).toHaveAttribute("aria-pressed", "true"));
    fireEvent.click(screen.getByRole("button", { name: "7 days" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Analytics unavailable");
    expect(mocks.toastError).not.toHaveBeenCalled();
    expect(thirtyDays).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "7 days" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getAllByText("12").length).toBeGreaterThan(0);
  });

  it("marks workspace attention items as seen after opening their details", async () => {
    mocks.overview.mockReset().mockResolvedValue({ ...overview, failed_documents: 2, recent_issues: [recentIssue] });
    Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
      configurable: true,
      value: vi.fn(function (this: HTMLDialogElement) { this.setAttribute("open", ""); }),
    });

    const firstView = render(<AnalyticsPage />);
    const detailsButton = await screen.findByRole("button", { name: /More details/ });
    expect(detailsButton).toHaveTextContent("1 analytics.issues");
    const failedDocuments = screen.getByText(/analytics\.failed/).closest("span");
    expect(failedDocuments).not.toBeNull();
    expect(failedDocuments).toHaveClass("an-danger");

    fireEvent.click(detailsButton);
    await waitFor(() => expect(detailsButton).not.toHaveTextContent("1 analytics.issues"));
    await waitFor(() => expect(failedDocuments).toHaveClass("an-muted"));
    expect(localStorage.getItem("nexora:analytics:seen-issues:manager")).toContain("report.pdf");
    expect(localStorage.getItem("nexora:analytics:seen-failed-count:manager")).toBe("2");

    firstView.unmount();
    render(<AnalyticsPage />);
    expect(await screen.findByRole("button", { name: "More details" })).not.toHaveTextContent("1 analytics.issues");
  });
});
