import { expect, test } from "@playwright/test";

import { seedSession, stubApi } from "./helpers.js";

const viewports = [
  { name: "mobile-small", width: 320, height: 640 },
  { name: "mobile", width: 390, height: 844 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "laptop", width: 1024, height: 768 },
  { name: "desktop", width: 1440, height: 900 },
];

test.describe("Accessibility and responsive baseline", () => {
  for (const viewport of viewports) {
    test(`keeps the login screen within the ${viewport.name} viewport`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/");

      await expect(page.getByRole("main")).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
  }

  test("supports LTR and RTL language semantics without horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await page.getByRole("button", { name: "Change language" }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "fa");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });

  test("keeps mobile navigation keyboard-operable with a 44px touch target", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    await seedSession(page);
    await stubApi(page);
    await page.goto("/home");

    const openNavigation = page.getByRole("button", { name: "Open navigation" });
    await expect(openNavigation).toBeVisible();
    const bounds = await openNavigation.boundingBox();
    expect(bounds?.width).toBeGreaterThanOrEqual(44);
    expect(bounds?.height).toBeGreaterThanOrEqual(44);

    await openNavigation.focus();
    await page.keyboard.press("Enter");
    const sidebar = page.locator('aside[aria-label="Main sidebar"]');
    await expect(sidebar).toHaveAttribute("aria-modal", "true");
    await page.keyboard.press("Escape");
    await expect(sidebar).not.toHaveAttribute("aria-modal", "true");
    await expect(openNavigation).toBeFocused();
  });

  test("exposes named landmarks and honors reduced-motion preferences", async ({ page }) => {
    await seedSession(page);
    await stubApi(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/home");

    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByRole("complementary", { name: "Main sidebar" })).toBeVisible();
    await expect(page.getByRole("main").getByRole("button", { name: "New conversation", exact: true })).toBeVisible();
    await expect(page.locator(".app-orb").first()).toHaveCSS("animation-name", "none");
  });
});
