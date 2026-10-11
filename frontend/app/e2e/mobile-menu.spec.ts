import { expect, test } from "@playwright/test";

import { seedSession, stubApi } from "./helpers.js";

test.describe("Mobile menu", () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test("opens sidebar via hamburger button on mobile viewport", async ({ page }) => {
    await seedSession(page);
    await stubApi(page);

    await page.goto("/home");

    // On mobile, the "Open navigation" button should be visible.
    const openNavButton = page.getByRole("button", { name: "Open navigation" });
    await expect(openNavButton).toBeVisible({ timeout: 10_000 });
    await openNavButton.click();

    // Sidebar should become visible with aria-modal="true".
    const sidebar = page.getByRole("complementary", { name: "Main sidebar" });
    await expect(sidebar).toHaveAttribute("aria-modal", "true");
    await expect(sidebar.getByText("Workspace")).toBeVisible({ timeout: 5_000 });
  });

  test("closes mobile sidebar when backdrop is clicked", async ({ page }) => {
    await seedSession(page);
    await stubApi(page);

    await page.goto("/home");

    // Open mobile menu.
    await page.getByRole("button", { name: "Open navigation" }).click();
    const sidebar = page.getByRole("complementary", { name: "Main sidebar" });
    await expect(sidebar).toHaveAttribute("aria-modal", "true");

    // Click the backdrop to close.
    const backdrop = page.locator(".nexora-sidebar-backdrop");
    await backdrop.click();

    // Sidebar should no longer be modal.
    await expect(sidebar).not.toHaveAttribute("aria-modal", "true", { timeout: 5_000 });
  });
});