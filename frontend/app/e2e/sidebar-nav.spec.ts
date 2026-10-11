import { expect, test } from "@playwright/test";

import { seedSession, stubApi } from "./helpers.js";

test.describe("Sidebar navigation", () => {
  test("navigates between Workspace and Knowledge base pages", async ({ page }) => {
    await seedSession(page);
    await stubApi(page);

    await page.goto("/home");

    // Should start on Workspace page.
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible({ timeout: 10_000 });

    // Click Knowledge base in sidebar nav.
    const sidebar = page.getByRole("complementary", { name: "Main sidebar" });
    await sidebar.getByRole("button", { name: "Knowledge base" }).click();

    // Should navigate to the knowledge base page - use heading for uniqueness.
    await expect(page.getByRole("heading", { name: /onboarding manual/i })).toBeVisible({ timeout: 10_000 });

    // Click Workspace in sidebar to go back.
    await sidebar.getByRole("button", { name: "Workspace" }).click();

    // Should be back on Workspace.
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible({ timeout: 10_000 });
  });

  test("shows active state on the current navigation item", async ({ page }) => {
    await seedSession(page);
    await stubApi(page);

    await page.goto("/home");

    const sidebar = page.getByRole("complementary", { name: "Main sidebar" });

    // The Workspace button should have aria-current="page".
    const homeButton = sidebar.getByRole("button", { name: "Workspace" });
    await expect(homeButton).toHaveAttribute("aria-current", "page");

    // Navigate to Knowledge base.
    await sidebar.getByRole("button", { name: "Knowledge base" }).click();
    await expect(page.getByRole("heading", { name: /onboarding manual/i })).toBeVisible({ timeout: 10_000 });

    // Now Knowledge base should be active.
    const kbButton = sidebar.getByRole("button", { name: "Knowledge base" });
    await expect(kbButton).toHaveAttribute("aria-current", "page");
  });

  test("collapses and expands the sidebar", async ({ page }) => {
    await seedSession(page);
    await stubApi(page);

    await page.goto("/home");

    const sidebar = page.getByRole("complementary", { name: "Main sidebar" });

    // Sidebar should be expanded initially.
    const collapseButton = sidebar.getByRole("button", { name: /collapse sidebar/i });
    await expect(collapseButton).toBeVisible({ timeout: 10_000 });

    // Click to collapse.
    await collapseButton.click();

    // Navigation labels should be hidden when collapsed (scoped to sidebar).
    await expect(sidebar.getByText("Workspace")).not.toBeVisible({ timeout: 3_000 });

    // Click expand button to restore.
    const expandButton = sidebar.getByRole("button", { name: /expand sidebar/i });
    await expect(expandButton).toBeVisible();
    await expandButton.click();

    // Labels should be visible again.
    await expect(sidebar.getByText("Workspace")).toBeVisible({ timeout: 5_000 });
  });
});