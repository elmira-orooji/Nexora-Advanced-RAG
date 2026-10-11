import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AssistantsPage from "./AssistantsPage";

const mocks = vi.hoisted(() => ({ list: vi.fn(), listSets: vi.fn() }));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" }, t: (key: string) => key }),
}));
vi.mock("react-hot-toast", () => ({ default: { error: vi.fn(), success: vi.fn() } }));
vi.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div> },
  useReducedMotion: () => true,
}));
vi.mock("../features/auth/api/authService", () => ({ authService: { getUser: () => ({ role: "user" }) } }));
vi.mock("../features/assistants/api/assistantService", () => ({
  assistantService: { list: mocks.list, listSets: mocks.listSets, remove: vi.fn(), models: vi.fn() },
}));

describe("AssistantsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.list.mockResolvedValue([{ id: "assistant-1", name: "Policy assistant", description: "Answers policy questions", instructions: "Answer policy questions", is_active: true, model_id: null, answer_mode: "sources", created_by_id: "admin-1", document_set_ids: [], document_set_names: [], created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" }]);
    mocks.listSets.mockResolvedValue([]);
  });

  it("starts a persistent conversation instead of opening a local assistant chat", async () => {
    const onStartConversation = vi.fn().mockResolvedValue(true);
    render(<AssistantsPage onStartConversation={onStartConversation} />);

    fireEvent.click(await screen.findByRole("button", { name: "Policy assistant" }));

    await waitFor(() => expect(onStartConversation).toHaveBeenCalledWith("assistant-1"));
    expect(screen.queryByRole("textbox", { name: /message/i })).not.toBeInTheDocument();
    expect(screen.getByText("New chats are saved in Recent chats")).toBeInTheDocument();
  });
});
