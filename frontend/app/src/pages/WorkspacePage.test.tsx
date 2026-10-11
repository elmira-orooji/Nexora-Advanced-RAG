import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import WorkspacePage from "./WorkspacePage";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" } }),
}));

describe("WorkspacePage", () => {
  it("keeps overview actions distinct from starting a new conversation", () => {
    const onNewConversation = vi.fn();
    const onOpenConversation = vi.fn();
    const onOpenKnowledge = vi.fn();
    render(<WorkspacePage currentUser={{ id: "user-1", username: "sara", role: "admin", organization_id: "org-1", organization_name: "Nexora", organization_slug: "nexora" }} conversations={[{ id: "chat-1", title: "Quarterly policy", document_id: null, document_set_id: null, assistant_id: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-02T00:00:00Z" }]} onNewConversation={onNewConversation} onOpenConversation={onOpenConversation} onOpenKnowledge={onOpenKnowledge} />);

    fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
    expect(onNewConversation).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: /Quarterly policy/ }));
    expect(onOpenConversation).toHaveBeenCalledWith("chat-1");

    fireEvent.click(screen.getByRole("button", { name: /knowledge base/i }));
    expect(onOpenKnowledge).toHaveBeenCalledOnce();
  });

  it("does not expose knowledge management to non-admin users", () => {
    render(<WorkspacePage currentUser={{ id: "user-1", username: "sara", role: "user", organization_id: "org-1", organization_name: "Nexora", organization_slug: "nexora" }} conversations={[]} onNewConversation={vi.fn()} onOpenConversation={vi.fn()} onOpenKnowledge={vi.fn()} />);

    expect(screen.queryByRole("button", { name: /knowledge base/i })).not.toBeInTheDocument();
  });
});
