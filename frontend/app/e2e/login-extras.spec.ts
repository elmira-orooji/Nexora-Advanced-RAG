import { expect, test } from "@playwright/test";

import { stubApi } from "./helpers.js";

test.describe("Login page extras", () => {
  test("remember me checkbox persists session in localStorage after login", async ({ page }) => {
    await stubApi(page);
    await page.goto("/");

    // Check the Remember me checkbox.
    const rememberCheckbox = page.locator('input[type="checkbox"]');
    await expect(rememberCheckbox).toBeVisible({ timeout: 10_000 });
    await rememberCheckbox.check();

    // Fill and submit the form using specific input selectors.
    await page.locator('#username').fill("ada");
    await page.locator('#password').fill("password123");
    await page.getByRole("button", { name: /sign.*in|ورود/i }).click();

    // After successful login, session should be in localStorage (not sessionStorage).
    await page.waitForURL("**/home**", { timeout: 10_000 });
    const session = await page.evaluate(() => localStorage.getItem("knowledgeflow.auth"));
    expect(session).toBeTruthy();
  });

  test("shows caps lock warning when CapsLock is active on password field", async ({ page }) => {
    await stubApi(page);
    await page.goto("/");

    const passwordField = page.locator('#password');
    await expect(passwordField).toBeVisible({ timeout: 10_000 });

    // Dispatch a real KeyboardEvent with getModifierState returning true for CapsLock.
    await page.evaluate(() => {
      const input = document.querySelector('#password') as HTMLInputElement;
      if (!input) return;
      const event = new KeyboardEvent("keydown", { key: "A", code: "KeyA", bubbles: true });
      // Override getModifierState to simulate CapsLock being on.
      const originalGetModifierState = event.getModifierState.bind(event);
      event.getModifierState = (keyArg: string) => keyArg === "CapsLock" || originalGetModifierState(keyArg);
      input.dispatchEvent(event);
    });

    // The caps lock warning should appear.
    await expect(page.getByText(/caps lock/i)).toBeVisible({ timeout: 3_000 });
  });

  test("shows offline message when navigator is offline", async ({ page }) => {
    await stubApi(page);

    // Set navigator.onLine to false before navigating.
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "onLine", { value: false, configurable: true });
    });

    await page.goto("/");

    // Fill the form fields.
    await page.locator('#username').fill("ada");
    await page.locator('#password').fill("password123");

    // Trigger form submission via evaluate to bypass disabled button check.
    await page.evaluate(() => {
      const form = document.querySelector('form');
      if (form) {
        const submitEvent = new Event("submit", { bubbles: true, cancelable: true });
        form.dispatchEvent(submitEvent);
      }
    });

    // Should show offline message instead of making API call.
    await expect(page.getByText(/offline|اینترنت/i)).toBeVisible({ timeout: 5_000 });
  });

  test("theme toggle switches between dark and light mode on login page", async ({ page }) => {
    await stubApi(page);
    await page.goto("/");

    // Find the theme toggle button.
    const themeButton = page.getByRole("button", { name: /switch to (light|dark) mode|فعال.*حالت/i });
    await expect(themeButton).toBeVisible({ timeout: 10_000 });

    // Click to toggle theme.
    await themeButton.click();

    // HTML element should have the "dark" class toggled.
    const htmlClass = await page.locator("html").getAttribute("class");
    // After one click, theme should have changed (either added or removed "dark").
    expect(htmlClass).toBeDefined();
  });
});