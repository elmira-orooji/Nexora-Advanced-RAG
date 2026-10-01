import { describe, expect, it } from "vitest";
import { operationError, processingStageLabel } from "./operationFeedback";

describe("operation feedback", () => {
  it("preserves stored Jina error strings for inline feedback", () => {
    expect(operationError("Jina OCR request failed (HTTP 403)", "processing", false)).toContain("HTTP 403");
  });

  it("does not label retry waiting as active extraction", () => {
    expect(processingStageLabel("retry_wait", false)).toBe("Processing failed; waiting to retry");
    expect(processingStageLabel("requeued", true)).toContain("متوقف شد");
  });
  it("turns technical network failures into an actionable upload message", () => {
    expect(operationError(new Error("Failed to fetch"), "upload", false)).toMatch(/couldn't be uploaded/i);
  });

  it("keeps an OCR provider failure actionable instead of hiding it as a network failure", () => {
    expect(operationError(new Error("MinerU file upload failed: network error (timed out)"), "processing", false)).toContain("timed out");
  });

  it("uses a meaningful localized processing stage", () => {
    expect(processingStageLabel("embedding", true)).toBe("در حال ایندکس‌کردن");
  });
});
