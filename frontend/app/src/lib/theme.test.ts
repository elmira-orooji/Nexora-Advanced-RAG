import { afterEach, describe, expect, it, vi } from "vitest";

import { getPreferredTheme, saveTheme, THEME_STORAGE_KEY } from "./theme";

describe("theme preferences", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses the same stored preference for login and the application", () => {
    saveTheme("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(getPreferredTheme()).toBe("light");
  });

  it("uses the system preference only when no valid saved preference exists", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "unexpected");
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));

    expect(getPreferredTheme()).toBe("light");
  });
});
