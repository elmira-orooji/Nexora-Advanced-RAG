import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../../i18n";
import RenameConversationDialog from "./RenameConversationDialog";

const conversation = {
  id: "conversation-1",
  title: "Quarterly report",
  document_id: null,
  document_set_id: null,
  assistant_id: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("RenameConversationDialog", () => {
  it("exposes an accessible modal and restores focus after closing", async () => {
    const user = userEvent.setup();
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    const onClose = vi.fn();

    const { unmount } = render(<RenameConversationDialog conversation={conversation} onClose={onClose} onRename={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: "Rename conversation" })).toHaveAttribute("aria-modal", "true");
    expect(screen.getByLabelText("Conversation title")).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledOnce();
    unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("trims and submits a changed title", async () => {
    const user = userEvent.setup();
    const onRename = vi.fn().mockResolvedValue(undefined);
    render(<RenameConversationDialog conversation={conversation} onClose={vi.fn()} onRename={onRename} />);

    const input = screen.getByLabelText("Conversation title");
    await user.clear(input);
    await user.type(input, "  Updated report  ");
    await user.click(screen.getByRole("button", { name: "Save title" }));

    expect(onRename).toHaveBeenCalledWith("Updated report");
  });

  it("keeps the dialog open and reports an API failure", async () => {
    const user = userEvent.setup();
    const onRename = vi.fn().mockRejectedValue(new Error("Rename unavailable"));
    render(<RenameConversationDialog conversation={conversation} onClose={vi.fn()} onRename={onRename} />);

    const input = screen.getByLabelText("Conversation title");
    await user.clear(input);
    await user.type(input, "Updated report");
    await user.click(screen.getByRole("button", { name: "Save title" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Rename unavailable");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
