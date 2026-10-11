import { expect, test } from "@playwright/test";

test.describe("Guest route redirect", () => {
  test("unauthenticated user is redirected away from /home", async ({ page }) => {
    // Do NOT seed session - user is unauthenticated.
    await page.goto("/home");

    // Should be redirected away from /home (to / or /login).
    await expect(page).not.toHaveURL(/\/home/, { timeout: 10_000 });
  });

  test("unauthenticated user is redirected away from the knowledge page", async ({ page }) => {
    await page.goto("/home/knowledge");

    // Should be redirected away from the protected knowledge route.
    await expect(page).not.toHaveURL(/\/home\/knowledge/, { timeout: 10_000 });
  });
});
