import type { AppNotification } from "./notificationService";

const templates: Record<string, { title: string; variants: Array<[string, (name: string) => string]> }> = {
  document_processed: { title: "سند آماده است", variants: [
    [" has been indexed and is ready to use.", (name) => `فایل ${name} پردازش شده و آمادهٔ استفاده است.`],
    [" is already indexed and ready to use.", (name) => `فایل ${name} قبلاً پردازش شده و آمادهٔ استفاده است.`],
  ] },
  document_failed: { title: "پردازش سند ناموفق بود", variants: [
    [" could not be processed. Review the document and retry it from Knowledge base.", (name) => `پردازش فایل ${name} انجام نشد. سند را بررسی کنید و از بخش پایگاه دانش دوباره تلاش کنید.`],
  ] },
  connector_synced: { title: "همگام‌سازی اتصال انجام شد", variants: [
    [" was synchronized successfully.", (name) => `اتصال ${name} با موفقیت همگام‌سازی شد.`],
  ] },
  connector_failed: { title: "همگام‌سازی اتصال ناموفق بود", variants: [
    [" could not be synchronized after multiple attempts. Review its configuration and retry it.", (name) => `همگام‌سازی اتصال ${name} پس از چند بار تلاش انجام نشد. تنظیمات آن را بررسی کنید و دوباره تلاش کنید.`],
  ] },
};

/** Translate known persisted system templates without altering user-supplied names. */
export function notificationText(item: Pick<AppNotification, "kind" | "title" | "body">, isFa: boolean) {
  const template = isFa ? templates[item.kind] : undefined;
  if (!template) return { title: item.title, body: item.body };
  const variant = template.variants.find(([suffix]) => item.body.endsWith(suffix));
  if (!variant) return { title: template.title, body: item.body };
  const name = item.body.slice(0, -variant[0].length);
  return { title: template.title, body: variant[1](`\u2068${name}\u2069`) };
}
