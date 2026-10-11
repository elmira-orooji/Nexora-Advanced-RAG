import { expect, test } from "@playwright/test";

import { seedSession, stubApi } from "./helpers.js";

test.describe("Language switch", () => {
  test("switches from English to Persian via Settings page and updates dir attribute", async ({ page }) => {
    await seedSession(page);
    await stubApi(page);

    await page.goto("/home");

    // Should start in English (LTR).
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible({ timeout: 10_000 });

    // Navigate to Settings page via sidebar.
    const sidebar = page.getByRole("complementary", { name: "Main sidebar" });
    await sidebar.getByRole("button", { name: "Settings" }).click();

    // Find the Persian language option - click the label/symbol that wraps the radio.
    const faLabel = page.locator('label').filter({ hasText: /fa|فارسی|persian/i }).first();
    await expect(faLabel).toBeVisible({ timeout: 10_000 });
    await faLabel.click({ force: true });

    // Should switch to Persian (RTL).
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  });

  test("persists language preference across page reloads", async ({ page }) => {
    await seedSession(page);
    await stubApi(page);

    // Set language to Persian before loading.
    await page.addInitScript(() => {
      localStorage.setItem("lang", "fa");
    });

    await page.goto("/home");

    // Should load in Persian (RTL) immediately.
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  });
});