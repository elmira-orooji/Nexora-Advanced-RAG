import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import toast from "react-hot-toast";
import AppToaster from "./AppToaster";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" } }),
}));

describe("AppToaster", () => {
  afterEach(() => toast.remove());

  it("renders a toast without triggering an update loop", async () => {
    const { container } = render(<AppToaster />);
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    await act(async () => {
      toast.success("Saved successfully");
      await Promise.resolve();
    });

    expect(await screen.findByText("Saved successfully")).toBeInTheDocument();
    expect(container.querySelectorAll("article.nexora-toast")).toHaveLength(1);
    expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining("Maximum update depth"));
    errorSpy.mockRestore();
  });
});
