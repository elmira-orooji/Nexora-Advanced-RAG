import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { knowledgeService } from "../../../services/knowledgeService";
import { runUploadQueue } from "../../../lib/uploadQueue";
const MAX_CONCURRENT_UPLOADS = 3;
type UploadTask = {
  id: string;
  filename: string;
  progress: number;
  status: "queued" | "uploading" | "success" | "error";
  error?: string;
};

export function useKnowledgeUpload({ selectedSetId, isFa, refreshSetData, loadSets, setPageError }: { selectedSetId: string; isFa: boolean; refreshSetData: (setId: string) => Promise<void>; loadSets: () => Promise<void>; setPageError: (message: string) => void }) {
  const [uploadTasks, setUploadTasks] = useState<UploadTask[]>([]);
  const [uploadError, setUploadError] = useState("");
  const uploading = uploadTasks.some((task) => task.status === "queued" || task.status === "uploading");
  const onDrop = useCallback(async (files: File[]) => {
    if (!selectedSetId || !files.length) return;
    const uploadSetId = selectedSetId;
    const batch = files.map((file) => ({ id: crypto.randomUUID(), file }));
    setUploadTasks(batch.map(({ id, file }) => ({ id, filename: file.name, progress: 0, status: "queued" })));
    const updateTask = (id: string, changes: Partial<UploadTask>) => {
      setUploadTasks((tasks) => tasks.map((task) => task.id === id ? { ...task, ...changes } : task));
    };
    const { succeeded, failed } = await runUploadQueue({
      items: batch,
      concurrency: MAX_CONCURRENT_UPLOADS,
      upload: async (entry, onProgress) => { await knowledgeService.uploadDocument(entry.file, uploadSetId, onProgress, entry.id); },
      onUpdate: (id, changes) => updateTask(id, changes),
    });
    if (succeeded > 0) {
      await refreshSetData(uploadSetId);
      await loadSets();
    }
    if (failed > 0) {
      setPageError(isFa ? `بارگذاری ${failed.toLocaleString("fa-IR")} فایل ناموفق بود. جزئیات هر فایل در صف بارگذاری نمایش داده می‌شود.` : `${failed} file${failed === 1 ? "" : "s"} failed to upload. See the upload queue for details.`);
    }
  }, [isFa, loadSets, refreshSetData, selectedSetId]);

  const { getInputProps, getRootProps, isDragActive, open } = useDropzone({
    onDrop, noClick: true, disabled: !selectedSetId || uploading, maxSize: 100 * 1024 * 1024,
    accept: {
      "application/pdf": [".pdf"],
      "text/plain": [".txt"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/tiff": [".tif", ".tiff"],
    },
    onDropRejected: () => setUploadError(isFa
      ? "فایل PDF، TXT یا تصویر JPG، PNG و TIFF با حجم حداکثر ۱۰۰ مگابایت انتخاب کنید."
      : "Choose a PDF, TXT, JPG, PNG, or TIFF file up to 100 MB."),
  });


 return { uploadTasks, setUploadTasks, uploadError, setUploadError, uploading, getInputProps, getRootProps, isDragActive, open };
}
