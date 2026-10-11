import { describe, expect, it } from "vitest";
import { findPersianSearchMatches, toPersianSearchKey } from "./persianSearch";

describe("Persian OCR search normalization", () => {
  it("matches Arabic and Persian yeh/kaf without altering displayed text", () => {
    const source = "كیفیت ثبت";
    expect(toPersianSearchKey(source)).toBe(toPersianSearchKey("کیفیت ثبت"));
    expect(findPersianSearchMatches(source, "کیفیت")).toEqual([{ start: 0, end: 5 }]);
    expect(source).toBe("كیفیت ثبت");
  });

  it("matches across whitespace, half-spaces, diacritics, and invisible marks", () => {
    const source = "می\u200cرِوم";
    expect(findPersianSearchMatches(source, "می روم")).toEqual([{ start: 0, end: source.length }]);
  });

  it("matches Persian, Arabic, and Latin digit forms", () => {
    expect(findPersianSearchMatches("شماره ۱۴۰۳", "شماره ١٤٠٣")).toEqual([{ start: 0, end: 10 }]);
    expect(toPersianSearchKey("1403")).toBe(toPersianSearchKey("۱۴۰۳"));
  });

  it("preserves source offsets when matching text after emoji", () => {
    expect(findPersianSearchMatches("مدرک 📄 شماره ۱۲", "شماره 12")).toEqual([{ start: 8, end: 16 }]);
  });
});
