import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import toast from "react-hot-toast";
import AppToaster from "./AppToaster";
import InlineSuccessMessages from "./InlineSuccessMessages";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" } }),
}));

describe("AppToaster", () => {
  afterEach(() => toast.remove());

  it("dismisses inline success messages", async () => {
    render(<><AppToaster /><InlineSuccessMessages /></>);
    act(() => { toast.success("Operation completed"); });
    expect(await screen.findByText("Operation completed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss success message" }));
    expect(screen.queryByText("Operation completed")).not.toBeInTheDocument();
  });

  it("keeps errors in their existing notification presentation", async () => {
    const { container } = render(<><AppToaster /><InlineSuccessMessages /></>);
    act(() => { toast.error("Operation failed"); });
    expect(await screen.findByText("Operation failed")).toBeInTheDocument();
    expect(container.querySelectorAll("article.nexora-toast")).toHaveLength(1);
    expect(screen.queryByLabelText("Operation results")).not.toBeInTheDocument();
  });

  it("renders a toast without triggering an update loop", async () => {
    const { container } = render(<><AppToaster /><InlineSuccessMessages /></>);
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    await act(async () => {
      toast.success("Saved successfully");
      await Promise.resolve();
    });

    expect(await screen.findByText("Saved successfully")).toBeInTheDocument();
    expect(container.querySelectorAll("article.nexora-toast")).toHaveLength(0);
    expect(screen.getByRole("status")).toHaveTextContent("Saved successfully");
    expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining("Maximum update depth"));
    errorSpy.mockRestore();
  });
});
