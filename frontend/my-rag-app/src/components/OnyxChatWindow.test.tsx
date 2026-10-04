import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import OnyxChatWindow from "./OnyxChatWindow";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ i18n: { language: "en" } }) }));
vi.mock("./AnswerMarkdown", () => ({ default: ({ content }: { content: string }) => <p>{content}</p> }));
vi.mock("./AnswerSources", () => ({ default: () => null }));
vi.mock("./ConversationScrollRail", () => ({ default: () => null }));

describe("truncated answers", () => {
  beforeEach(() => vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} }));
  afterEach(() => vi.unstubAllGlobals());
  it("shows a warning and continues only the latest answer", () => {
    const onContinue = vi.fn();
    render(<OnyxChatWindow messages={[{ id: "1", role: "assistant", content: "Incomplete", truncated: true, createdAt: "2026-10-04T00:00:00Z" }]} isThinking={false} onContinue={onContinue} />);
    expect(screen.getByText(/length limit/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue answer" }));
    expect(onContinue).toHaveBeenCalledOnce();
  });

  it("does not offer another continuation while sending", () => {
    render(<OnyxChatWindow messages={[{ id: "1", role: "assistant", content: "Incomplete", truncated: true, createdAt: "2026-10-04T00:00:00Z" }]} isThinking onContinue={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Continue answer" })).toBeDisabled();
  });

  it("does not show a length warning for complete answers", () => {
    render(<OnyxChatWindow messages={[{ id: "1", role: "assistant", content: "Complete", createdAt: "2026-10-04T00:00:00Z" }]} isThinking={false} onContinue={vi.fn()} />);
    expect(screen.queryByText(/length limit/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Continue answer" })).not.toBeInTheDocument();
  });
});
