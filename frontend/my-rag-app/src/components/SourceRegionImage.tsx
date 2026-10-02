import { useEffect, useState } from "react";
import { apiRequest } from "../services/apiClient";
import InlineError from "./InlineError";
import type { Source } from "../types/chat";

interface Region { image: string; filename: string; page: number; width: number; height: number }

export default function SourceRegionImage({ source, isFa }: { source: Source; isFa: boolean }) {
  const [region, setRegion] = useState<Region | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setRegion(null);
    setError("");
    void apiRequest<Region>(`/documents/${source.documentId}/source-region`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chunk_id: source.id, query: source.visualQuery }), signal: controller.signal,
    }).then((value) => { if (!controller.signal.aborted) setRegion(value); }).catch((failure: unknown) => {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Source image unavailable");
    });
    return () => controller.abort();
  }, [source.id, source.documentId, source.visualQuery, revision]);
  const pageLabel = region ? `${isFa ? "صفحهٔ" : "Page"} ${region.page.toLocaleString(isFa ? "fa-IR" : "en")}` : "";
  return <figure className="source-region-image">
    <figcaption><strong dir="auto">{region?.filename ?? source.title}</strong>{region && <span>{pageLabel}</span>}</figcaption>
    {!region && !error && <p role="status">{isFa ? "در حال یافتن تصویر بخش مرتبط…" : "Locating the source region…"}</p>}
    {error && <><InlineError message={isFa ? `تصویر بخش موردنظر در دسترس نیست. ${error}` : error} /><button type="button" className="chat-answer-action" onClick={() => setRevision((value) => value + 1)}>{isFa ? "تلاش دوباره" : "Retry image"}</button></>}
    {region && <><img src={region.image} width={region.width} height={region.height} alt={`${region.filename} · ${pageLabel}`} onError={() => { setRegion(null); setError(isFa ? "نمایش تصویر انجام نشد." : "Could not display source image."); }} /><a href={region.image} download={`${region.filename}-page-${region.page}.png`}>{isFa ? "دریافت تصویر" : "Download image"}</a></>}
  </figure>;
}
