import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import ChatInput from "./ChatInput";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" } }),
}));

describe("ChatInput", () => {
  it("pastes Persian multiline clipboard text and keeps it after a failed send", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(false);
    render(<ChatInput disabled={false} onSend={onSend} />);
    const input = screen.getByRole("textbox");
    await user.click(input);
    await user.paste("متن فارسی\nخط دوم");
    expect(input).toHaveValue("متن فارسی\nخط دوم");
    await user.click(screen.getByRole("button", { name: /send message/i }));
    await waitFor(() => expect(onSend).toHaveBeenCalledWith("متن فارسی\nخط دوم"));
    expect(input).toHaveValue("متن فارسی\nخط دوم");
  });

  it("replaces only selected text when pasting", async () => {
    const user = userEvent.setup();
    render(<ChatInput disabled={false} initialValue="before OLD after" onSend={vi.fn()} />);
    const input = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.click(input);
    input.setSelectionRange(7, 10);
    await user.paste("NEW");
    expect(input).toHaveValue("before NEW after");
  });

  it("keeps the message when sending fails", async () => {
    const onSend = vi.fn().mockResolvedValue(false);
    render(<ChatInput disabled={false} onSend={onSend} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Retry this question" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => expect(onSend).toHaveBeenCalledWith("Retry this question"));
    expect(input).toHaveValue("Retry this question");
  });

  it("clears the message after a successful send", async () => {
    const onSend = vi.fn().mockResolvedValue(true);
    render(<ChatInput disabled={false} onSend={onSend} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Sent question" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("replaces send with a stop action while a response is being generated", () => {
    const onCancel = vi.fn();
    render(<ChatInput disabled={false} isSending onCancel={onCancel} onSend={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Stop generating" }));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(screen.getByRole("textbox")).toBeDisabled();
  });
});
