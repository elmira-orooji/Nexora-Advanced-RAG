export type UploadQueueItem = {
  id: string;
};

export type UploadQueueUpdate = {
  status: "uploading" | "success" | "error";
  progress?: number;
  error?: string;
};

type UploadQueueOptions<T extends UploadQueueItem> = {
  items: T[];
  concurrency: number;
  upload: (item: T, onProgress: (progress: number) => void) => Promise<void>;
  onUpdate: (id: string, update: UploadQueueUpdate) => void;
};

export async function runUploadQueue<T extends UploadQueueItem>({
  items,
  concurrency,
  upload,
  onUpdate,
}: UploadQueueOptions<T>) {
  let cursor = 0;
  let succeeded = 0;

  const worker = async () => {
    while (true) {
      const index = cursor++;
      if (index >= items.length) break;
      const item = items[index];
      onUpdate(item.id, { status: "uploading", progress: 0 });
      try {
        await upload(item, (progress) => onUpdate(item.id, { status: "uploading", progress }));
        succeeded += 1;
        onUpdate(item.id, { status: "success", progress: 100 });
      } catch (error) {
        onUpdate(item.id, {
          status: "error",
          error: error instanceof Error ? error.message : "Upload failed",
        });
      }
    }
  };

  const workerCount = Math.min(Math.max(1, concurrency), items.length);
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return { succeeded, failed: items.length - succeeded };
}
