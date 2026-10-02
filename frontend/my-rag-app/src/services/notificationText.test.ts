import { expect, it } from "vitest";
import { notificationText } from "./notificationText";

it.each([
  ["document_processed", " has been indexed and is ready to use.", "سند آماده است"],
  ["document_processed", " is already indexed and ready to use.", "سند آماده است"],
  ["document_failed", " could not be processed. Review the document and retry it from Knowledge base.", "پردازش سند ناموفق بود"],
  ["connector_synced", " was synchronized successfully.", "همگام‌سازی اتصال انجام شد"],
  ["connector_failed", " could not be synchronized after multiple attempts. Review its configuration and retry it.", "همگام‌سازی اتصال ناموفق بود"],
])("translates persisted %s notifications and preserves names", (kind, suffix, title) => {
  const result = notificationText({ kind, title: "English title", body: `Insurance قرارداد.pdf${suffix}` }, true);
  expect(result.title).toBe(title);
  expect(result.body).toContain("\u2068Insurance قرارداد.pdf\u2069");
  expect(result.body).not.toContain(suffix);
});

it("keeps the original English and unknown notifications intact", () => {
  const item = { kind: "document_processed", title: "Document is ready", body: "Insurance.pdf has been indexed and is ready to use." };
  expect(notificationText(item, false)).toEqual({ title: item.title, body: item.body });
  expect(notificationText({ ...item, kind: "custom" }, true)).toEqual({ title: item.title, body: item.body });
});
