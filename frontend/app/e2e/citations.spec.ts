import { expect, test } from "@playwright/test";

import { seedSession, stubApi } from "./helpers.js";

test.describe("Citation interaction", () => {
  test("clicking a citation button opens the evidence drawer with correct content", async ({ page }) => {
    await seedSession(page);
    await stubApi(page, {
      answer: "The refund policy allows returns within 30 days [1] of purchase.",
    });

    await page.goto("/home");

    // Navigate to new conversation via sidebar button (unique).
    const sidebar = page.getByRole("complementary", { name: "Main sidebar" });
    await sidebar.getByRole("button", { name: "New conversation" }).click();

    await expect(page.locator('textarea[aria-label="Message"]')).toBeVisible({ timeout: 10_000 });

    // Send a message to trigger an answer with citations.
    await page.locator('textarea[aria-label="Message"]').fill("What is the refund policy?");
    await page.getByRole("button", { name: "Send message" }).click();

    // Wait for the assistant answer to appear.
    await expect(page.getByText(/refund policy/i)).toBeVisible({ timeout: 15_000 });

    // The citation button [1] should be visible and clickable.
    const citationButton = page.locator("button").filter({ hasText: /^1$/ }).first();
    await expect(citationButton).toBeVisible({ timeout: 5_000 });

    // Click the citation to open the evidence drawer.
    await citationButton.click();

    // The evidence drawer should open with source details.
    const drawer = page.getByRole("complementary", { name: "Source details" });
    await expect(drawer).toBeVisible({ timeout: 5_000 });

    // The drawer should show the source excerpt.
    await expect(drawer.getByText(/refund window is 30 days/i)).toBeVisible();

    // The drawer should show the document filename.
    await expect(drawer.getByText("policy.pdf")).toBeVisible();

    // The drawer should show the page number and section.
    await expect(drawer.getByText("Page 4")).toBeVisible();
    await expect(drawer.getByText("Refunds")).toBeVisible();
  });
});