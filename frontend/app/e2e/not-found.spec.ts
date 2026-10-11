import { expect, test } from "@playwright/test";

test.describe("404 Not Found page", () => {
  test("shows not found page for a completely invalid top-level route", async ({ page }) => {
    // Navigate to a route that doesn't match any pattern (not /, /home/*, or /share/*).
    await page.goto("/totally-invalid-route-xyz");

    // Should show the "Page not found" heading.
    await expect(page.getByRole("heading", { name: /page not found|صفحه پیدا نشد/i })).toBeVisible({ timeout: 10_000 });
  });
});