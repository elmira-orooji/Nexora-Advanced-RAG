import { describe, expect, it } from "vitest";

import { getPostLoginDestination } from "./authNavigation";

describe("getPostLoginDestination", () => {
  it("restores a protected workspace destination", () => {
    expect(getPostLoginDestination({ from: "/home/settings?tab=security#sessions" }))
      .toBe("/home/settings?tab=security#sessions");
  });

  it.each([
    undefined,
    { reason: "session-expired" },
    { from: "https://example.com" },
    { from: "//example.com" },
    { from: "/share/team/token" },
  ])("falls back to the workspace for an invalid state", (state) => {
    expect(getPostLoginDestination(state)).toBe("/home");
  });
});
