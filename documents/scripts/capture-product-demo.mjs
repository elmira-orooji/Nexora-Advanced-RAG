import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.env.NEXORA_DEMO_URL || "http://localhost:5173";
const require = createRequire(import.meta.url);
const { chromium } = require("../../frontend/app/node_modules/playwright");
const username = process.env.NEXORA_DEMO_USERNAME;
const password = process.env.NEXORA_DEMO_PASSWORD;
if (!username || !password) throw new Error("Set NEXORA_DEMO_USERNAME and NEXORA_DEMO_PASSWORD before capturing.");

const output = path.resolve("documents/media/frames");
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(8_000);

try {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Username").fill(username);
  await page.getByRole("textbox", { name: "Password" }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/home/, { timeout: 20_000 });

  for (const [theme, language, frame] of [
    ["light", "en", "01-light-en"],
    ["dark", "en", "02-dark-en"],
    ["dark", "fa", "03-dark-fa"],
    ["light", "fa", "04-light-fa"],
  ]) {
    await page.evaluate(({ theme, language }) => {
      localStorage.setItem("theme", theme);
      localStorage.setItem("lang", language);
    }, { theme, language });
    await page.goto(`${baseUrl}/home/chat`, { waitUntil: "commit", timeout: 8_000 });
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(output, `${frame}.png`) });
    console.log(`Captured ${frame}`);
  }
} finally {
  await browser.close();
}
