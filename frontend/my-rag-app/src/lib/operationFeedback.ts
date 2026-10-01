export type OperationKind = "load" | "members" | "upload" | "processing" | "sync" | "answer";

export function operationError(error: unknown, operation: OperationKind, isFa: boolean): string {
  const raw = error instanceof Error ? error.message.trim() : typeof error === "string" ? error.trim() : "";
  const normalized = raw.toLowerCase();
  const timedOut = error instanceof Error && error.name === "ApiTimeoutError";
  const genericNetworkError = !raw || normalized.includes("failed to fetch") || normalized.includes("network error") || normalized === "request failed";
  const ocrProviderError = operation === "processing" && /jina|mineru|google vision|azure document intelligence/.test(normalized);
  if (operation === "processing" && normalized.startsWith("document processing was interrupted")) {
    return isFa
      ? (normalized.includes("retry limit") ? "پردازش متوقف شد و سقف تلاش‌های مجدد پایان یافت. علت توقف پردازشگر را بررسی کنید." : "پردازش قبلی متوقف شد؛ سند برای پردازش دوباره در صف قرار گرفت.")
      : raw;
  }
  const copy = isFa
    ? {
        load: "دریافت اطلاعات انجام نشد. اتصال را بررسی کنید و دوباره تلاش کنید.",
        members: "دریافت اعضای تیم انجام نشد. اتصال سرویس را بررسی کنید یا دوباره تلاش کنید.",
        upload: "بارگذاری فایل انجام نشد. اتصال و نوع فایل را بررسی کنید و دوباره تلاش کنید.",
        processing: "پردازش سند انجام نشد. دوباره تلاش کنید؛ اگر ادامه داشت، فایل را بررسی کنید.",
        sync: "همگام‌سازی انجام نشد. اتصال منبع را بررسی کنید و دوباره تلاش کنید.",
        answer: "پاسخ دریافت نشد. چند لحظه دیگر دوباره تلاش کنید.",
      }
    : {
        load: "We couldn't load this information. Check your connection and try again.",
        members: "We couldn't load team members. Check the service connection and try again.",
        upload: "The file couldn't be uploaded. Check the connection and file type, then try again.",
        processing: "The document couldn't be processed. Try again; if it persists, check the file.",
        sync: "The connector couldn't sync. Check the source connection and try again.",
        answer: "We couldn't generate an answer. Please try again in a moment.",
      };
  if (ocrProviderError) {
    return isFa
      ? `OCR با سرویس خارجی انجام نشد. ${raw}`
      : `OCR could not be completed by the external service. ${raw}`;
  }
  if (timedOut) {
    return isFa
      ? "پاسخ سرویس بیش از حد معمول طول کشید. اتصال را بررسی کنید و دوباره تلاش کنید."
      : "The service took longer than usual to respond. Check your connection and try again.";
  }
  return genericNetworkError ? copy[operation] : raw;
}

export function processingStageLabel(stage: string, isFa: boolean): string {
  const labels: Record<string, [string, string]> = {
    queued: ["در صف پردازش", "Queued for processing"],
    paused: ["پردازش موقتاً متوقف شده است", "Processing paused"],
    retry_wait: ["خطای پردازش؛ در انتظار تلاش مجدد", "Processing failed; waiting to retry"],
    requeued: ["پردازش قبلی متوقف شد؛ دوباره در صف قرار گرفت", "Processing interrupted; queued again"],
    dead_letter: ["پردازش ناموفق؛ نیاز به بررسی", "Processing failed; review required"],
    extracting: ["در حال خواندن محتوا", "Reading content"],
    chunking: ["در حال آماده‌سازی بخش‌ها", "Preparing passages"],
    embedding: ["در حال ایندکس‌کردن", "Indexing for search"],
    indexing: ["در حال ایندکس‌کردن", "Indexing for search"],
    processing: ["در حال پردازش سند", "Processing document"],
  };
  return labels[stage.toLowerCase()]?.[isFa ? 0 : 1] ?? (isFa ? "در حال پردازش سند" : "Processing document");
}
