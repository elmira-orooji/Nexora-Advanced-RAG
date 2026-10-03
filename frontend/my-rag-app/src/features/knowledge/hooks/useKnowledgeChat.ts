import { useEffect, useRef, useState } from "react";
import { knowledgeService, type MetadataFilters, type ResearchResponse } from "../../../services/knowledgeService";
import { operationError } from "../../../lib/operationFeedback";
import type { ChatMessage } from "../../../types/chat";

export function useKnowledgeChat({ selectedSetId, selectedDocumentIds, metadataFilters, answerMode, isFa }: { selectedSetId: string; selectedDocumentIds: string[]; metadataFilters: MetadataFilters; answerMode: "quick" | "research"; isFa: boolean }) {
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatError, setChatError] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [isChatSlow, setIsChatSlow] = useState(false);
  const chatAbortController = useRef<AbortController | null>(null);
  const chatSlowTimer = useRef<number | null>(null);
  useEffect(() => () => {
    chatAbortController.current?.abort();
    if (chatSlowTimer.current !== null) window.clearTimeout(chatSlowTimer.current);
  }, []);
  const cancelChatMessage = () => {
    chatAbortController.current?.abort();
    chatAbortController.current = null;
    if (chatSlowTimer.current !== null) window.clearTimeout(chatSlowTimer.current);
    chatSlowTimer.current = null;
    setIsChatSlow(false);
    setIsThinking(false);
  };

  const handleChatMessage = async (content: string) => {
    setChatError("");
    if (!selectedSetId) {
      setChatError(isFa ? "ابتدا یک مجموعه انتخاب کنید" : "Select a knowledge set first");
      return false;
    }
    setChatMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content, createdAt: new Date().toISOString() }]);
    setIsThinking(true);
    setIsChatSlow(false);
    const controller = new AbortController();
    chatAbortController.current = controller;
    chatSlowTimer.current = window.setTimeout(() => setIsChatSlow(true), 8_000);
    try {
      const isResearch = answerMode === "research";
      const result = isResearch
        ? await knowledgeService.research(content, selectedSetId, selectedDocumentIds, metadataFilters, controller.signal)
        : await knowledgeService.ask(content, selectedSetId, selectedDocumentIds, metadataFilters, controller.signal);
      setChatMessages((current) => [...current, {
        id: crypto.randomUUID(), role: "assistant", content: result.answer, responseId: result.response_id, createdAt: new Date().toISOString(),
        grounded: result.grounded,
        research: isResearch ? { steps: (result as ResearchResponse).steps, evidenceReviewed: (result as ResearchResponse).evidence_reviewed } : undefined,
        sources: result.citations.map((citation) => ({
          id: citation.chunk_id,
          citationId: citation.id,
          documentId: citation.document_id,
          title: citation.filename,
          chunkIndex: citation.chunk_index,
          excerpt: citation.excerpt,
          score: citation.score,
          page: citation.page,
          section: citation.section,
          ocrProvenance: citation.ocr_provenance,
        })),
      }]);
      return true;
    } catch (error) {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) return false;
      setChatError(operationError(error, "answer", isFa));
      return false;
    } finally {
      if (chatAbortController.current === controller) {
        chatAbortController.current = null;
        if (chatSlowTimer.current !== null) window.clearTimeout(chatSlowTimer.current);
        chatSlowTimer.current = null;
        setIsChatSlow(false);
        setIsThinking(false);
      }
    }
  };
  return { chatMessages, setChatMessages, chatError, setChatError, isThinking, isChatSlow, handleChatMessage, cancelChatMessage };
}
