import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useDocumentPolling } from "./useDocumentPolling";
import type { KnowledgeDocument } from "../../../services/knowledgeService";
const listDocuments = vi.hoisted(() => vi.fn());
vi.mock("../../../services/knowledgeService", () => ({ knowledgeService: { listDocuments } }));
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); });
it("polls active documents and aborts pending requests on cleanup", async () => {
  vi.useFakeTimers();
  const items = [{ id: "doc", status: "processing" }] as KnowledgeDocument[];
  const apply = vi.fn();
  listDocuments.mockResolvedValue(items);
  const { unmount } = renderHook(() => useDocumentPolling("set", items, apply));
  await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
  expect(listDocuments).toHaveBeenCalledWith("set", expect.any(AbortSignal));
  expect(apply).toHaveBeenCalledWith(items);
  const signal = listDocuments.mock.calls[0][1] as AbortSignal;
  unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
  expect(listDocuments).toHaveBeenCalledTimes(1);
});
it("does not poll ready documents", async () => {
  vi.useFakeTimers();
  const items = [{ id: "doc", status: "indexed" }] as KnowledgeDocument[];
  renderHook(() => useDocumentPolling("set", items, vi.fn()));
  await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
  expect(listDocuments).not.toHaveBeenCalled();
});
