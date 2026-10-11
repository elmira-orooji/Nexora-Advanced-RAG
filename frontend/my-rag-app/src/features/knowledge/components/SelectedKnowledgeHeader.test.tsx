import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DocumentSet } from "../../../services/knowledgeService";
import SelectedKnowledgeHeader from "./SelectedKnowledgeHeader";

const item = { id: "set-1", name: "News", description: "Full description", access_level: "view" } as DocumentSet;
const labels = { connect: "Connect source", edit: "Edit", delete: "Delete" };

describe("SelectedKnowledgeHeader", () => {
  it("expands the description without changing the available actions", () => {
    render(<SelectedKnowledgeHeader item={item} isAdmin isFa={false} labels={labels}
      onConnect={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    const connect = screen.getByRole("button", { name: "Connect source" });
    fireEvent.click(screen.getByRole("button", { name: "Read more" }));
    expect(screen.getByText("Full description")).toHaveClass("kb-description-expanded");
    expect(screen.getByRole("button", { name: "Connect source" })).toBe(connect);
    fireEvent.click(screen.getByRole("button", { name: "Show less" }));
    expect(screen.getByText("Full description")).not.toHaveClass("kb-description-expanded");
  });

  it("does not expose management actions for read-only access", () => {
    render(<SelectedKnowledgeHeader item={item} isAdmin={false} isFa={false} labels={labels}
      onConnect={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Connect source" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Set options" })).not.toBeInTheDocument();
  });
});
