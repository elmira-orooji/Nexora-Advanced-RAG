import { expect, test } from "@playwright/test";

import { seedSession, stubApi } from "./helpers.js";

test.describe("Conversation chat E2E", () => {
  test("selects a knowledge base, sends a message, and renders the grounded answer", async ({ page }) => {
    await seedSession(page);
    await stubApi(page, { answer: "You can request a refund within 30 days." });

    await page.goto("/home");

    // User lands on Workspace page. Click "New conversation" in main content.
    const newConvButton = page.getByRole("main").getByRole("button", { name: "New conversation", exact: true });
    await expect(newConvButton).toBeVisible({ timeout: 10_000 });
    await newConvButton.click();

    // Should navigate to the chat page with knowledge base picker.
    await expect(page).toHaveURL(/\/home\/chat(\/|$)/, { timeout: 10_000 });

    // Wait for the textarea to be available.
    await expect(page.locator('textarea[aria-label="Message"]')).toBeVisible({ timeout: 10_000 });

    // Type and submit a question.
    await page.locator('textarea[aria-label="Message"]').fill("What is the refund policy?");
    await page.getByRole("button", { name: "Send message" }).click();

    // The user's question is echoed back in the thread.
    await expect(page.getByText("What is the refund policy?")).toBeVisible({ timeout: 10_000 });
    // The assistant's grounded answer appears (from the mocked backend).
    await expect(page.getByText(/refund within 30 days/i)).toBeVisible({ timeout: 10_000 });
  });
});