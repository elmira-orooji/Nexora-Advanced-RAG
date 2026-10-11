import { describe, expect, it, vi } from "vitest";
import { runUploadQueue, type UploadQueueUpdate } from "./uploadQueue";

describe("runUploadQueue", () => {
  it("limits concurrency, reports progress, and continues after a failed file", async () => {
    const items = Array.from({ length: 6 }, (_, index) => ({ id: `file-${index}` }));
    let active = 0;
    let maximumActive = 0;
    const updates = new Map<string, UploadQueueUpdate[]>();
    const onUpdate = vi.fn((id: string, update: UploadQueueUpdate) => {
      updates.set(id, [...(updates.get(id) ?? []), update]);
    });

    const result = await runUploadQueue({
      items,
      concurrency: 3,
      onUpdate,
      upload: async (item, onProgress) => {
        active += 1;
        maximumActive = Math.max(maximumActive, active);
        onProgress(45);
        await Promise.resolve();
        active -= 1;
        if (item.id === "file-2") throw new Error("Unsupported file");
      },
    });

    expect(maximumActive).toBe(3);
    expect(result).toEqual({ succeeded: 5, failed: 1 });
    expect(updates.get("file-2")?.at(-1)).toEqual(expect.objectContaining({ status: "error", error: "Unsupported file" }));
    expect(updates.get("file-5")?.at(-1)).toEqual(expect.objectContaining({ status: "success", progress: 100 }));
    expect(onUpdate).toHaveBeenCalledWith("file-0", expect.objectContaining({ progress: 45 }));
  });
});
