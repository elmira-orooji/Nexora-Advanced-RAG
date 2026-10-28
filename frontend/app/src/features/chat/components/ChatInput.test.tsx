import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import ChatInput from "./ChatInput";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" } }),
}));

describe("ChatInput", () => {
  it("clears immediately while the response is pending and restores on failure", async () => {
    let finish!: (success: boolean) => void;
    const onSend = vi.fn(() => new Promise<boolean>((resolve) => { finish = resolve; }));
    render(<ChatInput disabled={false} initialValue="Pending question" onSend={onSend} />);
    const input = screen.getByRole("textbox");
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    expect(input).toHaveValue("");
    await act(async () => { finish(false); });
    expect(input).toHaveValue("Pending question");
  });

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

  it("adds recognized speech to the draft without sending it", async () => {
    class MockRecognition {
      static latest: MockRecognition | undefined;
      lang = "";
      continuous = false;
      interimResults = false;
      onresult: ((event: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      start = vi.fn();
      stop = vi.fn(() => this.onend?.());
      abort = vi.fn();
      constructor() { MockRecognition.latest = this; }
    }
    Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: MockRecognition });
    const onSend = vi.fn();
    const { unmount } = render(<ChatInput disabled={false} initialValue="Existing draft" onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: /voice input/i }));
    const instance = MockRecognition.latest;
    expect(instance?.lang).toBe("en-US");
    expect(instance?.start).toHaveBeenCalledOnce();
    act(() => instance?.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: "spoken words" } }] }));
    expect(screen.getByRole("textbox")).toHaveValue("Existing draft spoken words");
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /stop voice input/i }));
    expect(instance?.stop).toHaveBeenCalledOnce();
    unmount();
    delete (window as Window & { SpeechRecognition?: typeof MockRecognition }).SpeechRecognition;
  });

  it("shows an inline message when speech recognition is unavailable", () => {
    render(<ChatInput disabled={false} onSend={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /voice input/i }));
    expect(screen.getByRole("status")).toHaveTextContent("Voice input is not supported");
  });
});
