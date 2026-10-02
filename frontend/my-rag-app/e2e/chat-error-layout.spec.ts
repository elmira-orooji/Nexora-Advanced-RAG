import { expect, test } from "@playwright/test";
import { seedSession, stubApi } from "./helpers.js";

for (const width of [390, 1536]) {
  test(`chat error aligns with composer at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    seedSession(page);
    await stubApi(page);
    await page.route("**/api/v1/conversations/*/messages", (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "The AI response service is temporarily unavailable. Please retry shortly. Request ID: 08310b36-48f7-497f-b460-21f24400e2df" }) }));
    await page.goto("/home/chat/conv-1");
    const input = page.getByRole("textbox", { name: "Message" });
    await input.fill("What are the policy terms?");
    await page.getByRole("button", { name: "Send message" }).click();
    const error = page.locator(".conversation-dock > .nexora-inline-error");
    await expect(error).toBeVisible();
    const errorBox = await error.boundingBox();
    const composerBox = await page.locator(".conversation-dock .app-composer").boundingBox();
    expect(errorBox).not.toBeNull();
    expect(composerBox).not.toBeNull();
    expect(Math.abs(errorBox!.x - composerBox!.x)).toBeLessThan(1);
    expect(Math.abs(errorBox!.width - composerBox!.width)).toBeLessThan(1);
    expect(await error.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  });
}
