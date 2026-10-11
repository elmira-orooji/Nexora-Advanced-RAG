import { expect, test } from "@playwright/test";

import { regularUser, seedSession, stubApi } from "./helpers.js";

test.describe("Authentication", () => {
  test("keeps autofilled login fields transparent", async ({ page }) => {
    await page.goto("/");
    const session = await page.context().newCDPSession(page);
    await session.send("DOM.enable");
    await session.send("CSS.enable");
    const { root } = await session.send("DOM.getDocument");
    for (const selector of ["#username", "#password"]) {
      const field = page.locator(selector);
      await field.fill("saved-value");
      const { nodeId } = await session.send("DOM.querySelector", { nodeId: root.nodeId, selector });
      await session.send("CSS.forcePseudoState", { nodeId, forcedPseudoClasses: ["autofill"] });
      for (const focused of [false, true]) {
        if (focused) await field.focus();
        else await field.blur();
        await expect(field).toHaveCSS("box-shadow", "none");
        await expect(field).toHaveCSS("background-clip", "text");
      }
    }
    await expect(page.locator("#username")).toHaveAttribute("autocomplete", "username");
    await expect(page.locator("#password")).toHaveAttribute("autocomplete", "current-password");
    await session.detach();
  });

  test("shows validation errors for an empty login form", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.locator("#username-error")).toBeVisible();
    await expect(page.locator("#password-error")).toBeVisible();
    await expect(page).toHaveURL(/\/$/);
  });

  test("signs in successfully and lands on the dashboard", async ({ page }) => {
    await stubApi(page);
    await page.goto("/");

    await page.locator("#username").fill(regularUser.username);
    await page.locator("#password").fill("supersecret");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/home(\/|$)/);
    await expect(page.locator('aside[aria-label="Main sidebar"]')).toBeVisible();
    await expect(page.getByText(regularUser.organization_name)).toBeVisible();
  });

  test("logs out and returns to the sign-in screen", async ({ page }) => {
    await stubApi(page);
    await seedSession(page);
    await page.goto("/home");

    await expect(page.locator('aside[aria-label="Main sidebar"]')).toBeVisible();
    await page.getByRole("button", { name: "Log out" }).click();
    await page.getByRole("button", { name: "Yes, confirm" }).click();

    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator("#username")).toBeVisible();
  });
});
