import { describe, expect, it } from "vitest";
import { inspectUnicode } from "./unicodeInspector";

describe("inspectUnicode", () => {
  it("counts Arabic variants without changing the inspected text", () => {
    const text = "يكي کتاب";
    const result = inspectUnicode(text);
    expect(result.codePointCount).toBe(Array.from(text).length);
    expect(result.findings.find((item) => item.codePoint === "U+064A")?.count).toBe(2);
    expect(result.findings.find((item) => item.codePoint === "U+0643")?.count).toBe(1);
    expect(text).toBe("يكي کتاب");
  });

  it("distinguishes intentional Persian joiners from bidi controls and replacement characters", () => {
    const result = inspectUnicode("می\u200cروم\u202eمتن\u202c�");
    expect(result.findings.find((item) => item.codePoint === "U+200C")?.labelFa).toContain("نیم‌فاصله");
    expect(result.findings.find((item) => item.codePoint === "U+202E")?.kind).toBe("bidi-control");
    expect(result.findings.find((item) => item.codePoint === "U+FFFD")?.kind).toBe("replacement");
  });

  it("reports Unicode code points separately from UTF-16 units", () => {
    const result = inspectUnicode("A😀");
    expect(result.codePointCount).toBe(2);
    expect(result.utf16UnitCount).toBe(3);
    expect(result.findings).toHaveLength(0);
  });
});
