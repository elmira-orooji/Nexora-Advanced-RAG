import { useEffect } from "react";
import { knowledgeService, type KnowledgeDocument } from "../../../services/knowledgeService";
const DOCUMENT_POLL_BASE_DELAY = 1_500;
const DOCUMENT_POLL_MAX_DELAY = 30_000;

export function useDocumentPolling(selectedSetId: string, documents: KnowledgeDocument[], applyDocuments: (items: KnowledgeDocument[]) => void) {
  const hasActiveDocuments = documents.some((item) => ["queued", "processing"].includes(item.status));
  useEffect(() => {
    if (!selectedSetId || !hasActiveDocuments) return;
    const controller = new AbortController();
    let timer: number | undefined;
    let retryDelay = DOCUMENT_POLL_BASE_DELAY;
    const poll = async () => {
      try {
        const items = await knowledgeService.listDocuments(selectedSetId, controller.signal);
        if (!controller.signal.aborted) {
          applyDocuments(items);
          retryDelay = DOCUMENT_POLL_BASE_DELAY;
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        retryDelay = Math.min(retryDelay * 2, DOCUMENT_POLL_MAX_DELAY);
      } finally {
        if (!controller.signal.aborted) timer = window.setTimeout(() => void poll(), retryDelay);
      }
    };
    timer = window.setTimeout(() => void poll(), DOCUMENT_POLL_BASE_DELAY);
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [applyDocuments, hasActiveDocuments, selectedSetId]);

}
