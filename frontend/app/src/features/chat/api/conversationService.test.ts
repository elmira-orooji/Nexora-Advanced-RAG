import { describe, expect, it, vi } from "vitest";
import { conversationService } from "./conversationService";

describe("conversationService", () => {
  it("sends a message to the selected conversation with the retrieval limit", async () => {
    const payload = { id: "message-1", role: "assistant", content: "Answer", sources: null, answer_id: null, created_at: "now" };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));

    await expect(conversationService.send("conversation-42", "What is Nexora?")).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/conversations/conversation-42/messages", expect.objectContaining({
      method: "POST",
      credentials: "include",
      body: JSON.stringify({ content: "What is Nexora?", limit: 5 }),
    }));
  });

  it("creates a persistent conversation for an assistant", async () => {
    const payload = { id: "assistant-chat", assistant_id: "assistant-7" };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    }));

    await expect(conversationService.createForAssistant("assistant-7")).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/conversations", expect.objectContaining({
      method: "POST",
      credentials: "include",
      body: JSON.stringify({ assistant_id: "assistant-7", title: undefined }),
    }));
  });
});
