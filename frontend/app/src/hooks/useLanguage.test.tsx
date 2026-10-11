import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useLanguage } from "./useLanguage";

describe("useLanguage", () => {
  it("persists Persian and updates the document direction", async () => {
    const { result } = renderHook(() => useLanguage());
    act(() => result.current.changeLanguage("fa"));

    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(document.documentElement.lang).toBe("fa");
    expect(localStorage.getItem("lang")).toBe("fa");
  });

  it("restores English direction", async () => {
    localStorage.setItem("lang", "en");
    const { result } = renderHook(() => useLanguage());
    act(() => result.current.changeLanguage("en"));
    await waitFor(() => expect(document.documentElement.dir).toBe("ltr"));
  });
});
