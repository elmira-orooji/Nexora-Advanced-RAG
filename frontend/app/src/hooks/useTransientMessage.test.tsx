import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useTransientMessage } from "./useTransientMessage";

describe("useTransientMessage", () => {
  afterEach(() => vi.useRealTimers());

  it("restarts the timer when the same message is repeated", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useTransientMessage(2500));
    act(() => result.current.show("Copied"));
    act(() => vi.advanceTimersByTime(2000));
    act(() => result.current.show("Copied"));
    act(() => vi.advanceTimersByTime(2000));
    expect(result.current.message).toBe("Copied");
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.message).toBe("");
  });

  it("clears the timer on unmount", () => {
    vi.useFakeTimers();
    const { result, unmount } = renderHook(() => useTransientMessage());
    act(() => result.current.show("Saved"));
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
