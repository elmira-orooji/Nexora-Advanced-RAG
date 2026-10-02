import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConversationPage from "./ConversationPage";

const mocks = vi.hoisted(() => ({
  createForSet: vi.fn(),
  createForSets: vi.fn(),
  createForWorkspace: vi.fn(),
  send: vi.fn(),
  get: vi.fn(),
  listSets: vi.fn(),
  listAssistants: vi.fn(),
  getUser: vi.fn(),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" } }),
}));
vi.mock("react-hot-toast", () => ({ default: { error: vi.fn() } }));
vi.mock("../services/assistantService", () => ({ assistantService: { list: mocks.listAssistants } }));
vi.mock("../services/authService", () => ({ authService: { getUser: mocks.getUser } }));
vi.mock("../services/conversationService", () => ({
  conversationService: {
    createForSet: mocks.createForSet,
    createForSets: mocks.createForSets,
    createForWorkspace: mocks.createForWorkspace,
    send: mocks.send,
    get: mocks.get,
  },
}));
vi.mock("../services/knowledgeService", () => ({
  knowledgeService: { listSets: mocks.listSets },
}));
vi.mock("../components/OnyxChatWindow", () => ({
  default: () => <div>Conversation messages</div>,
}));

describe("ConversationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getUser.mockReturnValue({ role: "admin" });
    mocks.listSets.mockResolvedValue([{ id: "set-1", name: "Knowledge", indexed_document_count: 1 }]);
    mocks.createForSet.mockResolvedValue({ id: "conversation-1" });
    mocks.createForSets.mockResolvedValue({ id: "conversation-1" });
    mocks.createForWorkspace.mockResolvedValue({ id: "conversation-1" });
    mocks.get.mockResolvedValue({ id: "conversation-1", title: "First chat", messages: [] });
    mocks.listAssistants.mockResolvedValue([]);
  });

  it("navigates to a new conversation only after the first response is ready", async () => {
    let finishSend: (() => void) | undefined;
    mocks.send.mockImplementation(() => new Promise<void>((resolve) => { finishSend = resolve; }));
    const onConversationChange = vi.fn();

    render(
      <ConversationPage
        conversationId={null}
        onConversationChange={onConversationChange}
        onConversationsUpdated={vi.fn()}
        onOpenKnowledge={vi.fn()}
      />,
    );

    const input = await screen.findByRole("textbox");
    fireEvent.change(input, { target: { value: "First question" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => expect(mocks.createForWorkspace).toHaveBeenCalledOnce());
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith("conversation-1", "First question", expect.any(AbortSignal)));
    expect(onConversationChange).not.toHaveBeenCalled();

    finishSend?.();
    await waitFor(() => expect(onConversationChange).toHaveBeenCalledWith("conversation-1"));
  });

  it("sends a new conversation with only the selected knowledge bases", async () => {
    mocks.listSets.mockResolvedValueOnce([
      { id: "set-1", name: "Insurance", indexed_document_count: 1 },
      { id: "set-2", name: "Company", indexed_document_count: 1 },
    ]);
    mocks.send.mockResolvedValueOnce(undefined);
    render(<ConversationPage conversationId={null} onConversationChange={vi.fn()} onConversationsUpdated={vi.fn()} onOpenKnowledge={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Select knowledge bases" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Insurance" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Company" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Question" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    await waitFor(() => expect(mocks.createForSets).toHaveBeenCalledWith(["set-1", "set-2"], undefined, expect.any(AbortSignal)));
    expect(mocks.createForWorkspace).not.toHaveBeenCalled();
    expect(mocks.createForSet).not.toHaveBeenCalled();
  });

  it("offers a direct knowledge-base CTA when none exists", async () => {
    mocks.listSets.mockResolvedValueOnce([]);
    const onOpenKnowledge = vi.fn();

    render(<ConversationPage conversationId={null} onConversationChange={vi.fn()} onConversationsUpdated={vi.fn()} onOpenKnowledge={onOpenKnowledge} />);

    fireEvent.click(await screen.findByRole("button", { name: "Create knowledge base" }));
    expect(onOpenKnowledge).toHaveBeenCalledWith("create");
    fireEvent.click(screen.getByRole("button", { name: "Upload first document" }));
    expect(onOpenKnowledge).toHaveBeenLastCalledWith("upload");
  });

  it("holds the chat until a selected knowledge base has an indexed document", async () => {
    mocks.listSets.mockResolvedValueOnce([{ id: "set-1", name: "Knowledge", indexed_document_count: 0 }]);

    render(<ConversationPage conversationId={null} onConversationChange={vi.fn()} onConversationsUpdated={vi.fn()} onOpenKnowledge={vi.fn()} />);

    expect(await screen.findByText("This knowledge base is not ready for answers yet")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Upload first document" })).toBeInTheDocument();
  });

  it("shows an assistant conversation's saved context and connected knowledge", async () => {
    mocks.get.mockResolvedValueOnce({ id: "assistant-chat", title: "Policy chat", assistant_id: "assistant-1", messages: [] });
    mocks.listAssistants.mockResolvedValueOnce([{ id: "assistant-1", name: "Policy assistant", document_set_names: ["Policies"] }]);

    render(<ConversationPage conversationId="assistant-chat" onConversationChange={vi.fn()} onConversationsUpdated={vi.fn()} onOpenKnowledge={vi.fn()} />);

    expect(await screen.findByText("Assistant: Policy assistant")).toBeInTheDocument();
    expect(screen.getByText("1 connected knowledge base")).toBeInTheDocument();
    expect(screen.getByText(/Answers and sources are saved in Recent chats/)).toBeInTheDocument();
  });

  it("keeps the chat composer and suggestions for users without knowledge access", async () => {
    mocks.getUser.mockReturnValue({ role: "user" });
    mocks.listSets.mockResolvedValueOnce([]);
    const openKnowledge = vi.fn();
    render(<ConversationPage conversationId={null} onConversationChange={vi.fn()} onConversationsUpdated={vi.fn()} onOpenKnowledge={openKnowledge} />);
    expect(await screen.findByRole("textbox", { name: "Message" })).toBeDisabled();
    expect(screen.getByText("No accessible knowledge base")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Upload first document" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create knowledge base" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Summarize knowledge/i })).toBeEnabled();
    expect(screen.getByText("No accessible knowledge base").closest(".conversation-context")).not.toBeNull();
    expect(document.querySelector(".conversation-knowledge-notice")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Summarize knowledge/i }));
    expect(mocks.send).not.toHaveBeenCalled();
    expect(openKnowledge).not.toHaveBeenCalled();
  });

  it("lets users with indexed knowledge use the same chat composer as admins", async () => {
    mocks.getUser.mockReturnValue({ role: "user" });
    render(<ConversationPage conversationId={null} onConversationChange={vi.fn()} onConversationsUpdated={vi.fn()} onOpenKnowledge={vi.fn()} />);
    expect(await screen.findByRole("textbox", { name: "Message" })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Summarize knowledge/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Select knowledge bases" })).toBeEnabled();
  });
});
