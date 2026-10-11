import { describe, expect, it } from "vitest";

import { DEFAULT_API_URL, resolveApiUrl } from "./api";

describe("resolveApiUrl", () => {
  it.each([undefined, "", "   "])("uses the same-origin API path when configuration is missing", (value) => {
    expect(resolveApiUrl(value)).toBe(DEFAULT_API_URL);
  });

  it("normalizes a configured API URL", () => {
    expect(resolveApiUrl(" https://api.example.com/v1/// ")).toBe("https://api.example.com/v1");
  });

  it("supports a same-origin root API", () => {
    expect(resolveApiUrl("/")).toBe("");
  });
});
