import { expect, test, type Page } from "@playwright/test";
import { adminUser, seedSession, stubApi, sampleDocument } from "./helpers.js";

const sizes = [{ width: 320, height: 640 }, { width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1024, height: 768 }, { width: 1440, height: 900 }, { width: 844, height: 390 }];
async function withinViewport(page: Page) {
  const issues = await page.evaluate(() => {
    const selectors = ".analytics-header,.analytics-summary,.preferences-card,.team-member-row,.assistant-card,.kb-header,.conversation-dock,[role=dialog],dialog[open]";
    return [...document.querySelectorAll<HTMLElement>(selectors)].filter((el) => el.getBoundingClientRect().width && getComputedStyle(el).visibility !== "hidden").flatMap((el) => {
      const rect = el.getBoundingClientRect();
      const modalOutside = el.matches("[role=dialog],dialog[open]") && (rect.top < -1 || rect.bottom > innerHeight + 1);
      return modalOutside || rect.left < -1 || rect.right > innerWidth + 1 || el.scrollWidth > el.clientWidth + 2 ? [`${el.className}: ${rect.left}, ${rect.right}, overflow ${el.scrollWidth - el.clientWidth}`] : [];
    });
  });
  expect(issues).toEqual([]);
}

for (const language of ["en", "fa"]) for (const size of sizes) {
  test(`${language} pages and forms fit ${size.width}x${size.height}`, async ({ page }) => {
    await page.setViewportSize(size);
    seedSession(page, adminUser);
    await page.addInitScript((lang) => localStorage.setItem("lang", lang), language);
    await stubApi(page, { documents: [sampleDocument] });
    await page.route("**/api/v1/users", (route) => route.fulfill({ json: [{ id: "user-1", username: "long-user-name-for-responsive-layout", job_title: "Senior product manager for knowledge operations", role: "user", is_active: true, created_at: "2026-09-30T12:00:00Z" }] }));
    await page.route("**/api/v1/assistants", (route) => route.fulfill({ json: [{ id: "assistant-1", name: "Knowledge operations assistant", description: "Assistant with company knowledge sources", instructions: "Answer using evidence", is_active: true, document_set_ids: ["set-1"], document_set_names: ["Onboarding Manual"], created_at: "2026-09-30", updated_at: "2026-09-30" }] }));
    await page.route("**/api/v1/assistants/models", (route) => route.fulfill({ json: [] }));
    for (const [route, selector] of [["/home", ".analytics-summary"], ["/home/settings", ".preferences-card"], ["/home/users", ".team-member-row"], ["/home/assistants", ".assistants-header"], ["/home/knowledge", ".kb-header"], ["/home/chat/conv-1", ".chat-answer"]]) {
      await page.goto(route);
      await expect(page.locator(selector).first()).toBeVisible();
      await withinViewport(page);
    }
    await page.goto("/home/assistants");
    await page.locator(".assistants-header .assistants-create").click();
    await expect(page.locator("dialog[open]")).toBeVisible();
    await withinViewport(page);
    await page.goto("/home/users");
    await page.locator(".team-header .team-primary").click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await withinViewport(page);
    await page.goto("/home/knowledge");
    await page.locator(".kb-set-card").first().click();
    if (language === "fa" && size.width === 768) await page.screenshot({ path: "test-results/responsive-knowledge-tablet.png" });
    await page.locator(".kb-header-actions button").filter({ has: page.locator(".lucide-flask-conical") }).click();
    await expect(page.locator(".trace-panel")).toBeVisible();
    await withinViewport(page);
    await page.locator(".trace-actions button").first().click();
    await expect(page.locator(".retriever-compare")).toBeVisible();
    await withinViewport(page);
  });
}
