import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { KnowledgeDocument } from "../../../services/knowledgeService";
import { DocumentRow } from "./DocumentRow";

describe("DocumentRow pause availability", () => {
  it.each([
    ["queued", "queued", 0, true],
    ["processing", "extracting", 10, true],
    ["processing", "indexing", 65, true],
    ["processing", "indexing", 95, false],
    ["processing", "indexing", 100, false],
    ["paused", "paused", 10, false],
  ])("handles %s / %s at %i%%", (status, stage, progress, visible) => {
    const document: KnowledgeDocument = {
      id: "document-1", filename: "news_data.txt", content_type: "text/plain",
      status, processing_stage: stage, processing_progress: progress,
      processing_error: null, ocr_provenance: null, author: null, language: null,
      source_type: null, document_date: null, tags: [],
      created_at: "2026-10-04T00:00:00Z", updated_at: "2026-10-04T00:00:00Z",
    };
    render(<DocumentRow document={document} isAdmin isFa={false} canDelete
      onRetry={vi.fn()} onPause={vi.fn()} onRemove={vi.fn()} />);
    const button = screen.queryByRole("button", { name: "Pause processing" });
    if (visible) expect(button).toBeInTheDocument();
    else expect(button).not.toBeInTheDocument();
  });
});
