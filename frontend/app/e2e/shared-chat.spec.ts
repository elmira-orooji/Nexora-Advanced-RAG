import { expect, test } from "@playwright/test";

import { API_PATTERN, stubApi } from "./helpers.js";

test.describe("Shared chat page", () => {
  test("renders a public shared conversation without authentication", async ({ page }) => {
    const sharedData = {
      id: "share-1",
      title: "Refund policy discussion",
      owner_username: "ada",
      visibility: "link",
      messages: [
        { role: "user", content: "What is the refund policy?", sources: [] },
        {
          role: "assistant",
          content: "You can request a refund within 30 days of purchase.",
          grounded: true,
          answer_basis: "grounded",
          sources: [{ title: "policy.pdf", excerpt: "The refund window is 30 days." }],
        },
      ],
      created_at: "2025-02-01T00:00:00Z",
      expires_at: null,
    };

    // Stub the public share endpoint (no auth required).
    await page.route(API_PATTERN, async (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname.startsWith("/api/v1/share/link/") || pathname.startsWith("/api/v1/shared/link/")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(sharedData),
        });
      }
      return route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
    });

    await page.goto("/share/link/test-token-123");

    // Should render the shared conversation title.
    await expect(page.getByText("Refund policy discussion")).toBeVisible({ timeout: 10_000 });

    // Should show the user message.
    await expect(page.getByText("What is the refund policy?")).toBeVisible();

    // Should show the assistant answer.
    await expect(page.getByText(/refund within 30 days/i)).toBeVisible();
  });
});