import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EvaluationDataset from "./EvaluationDataset";

vi.mock("../services/knowledgeService", () => ({
  knowledgeService: {
    listEvaluationCases: vi.fn().mockResolvedValue([]),
  },
}));

function Harness() {
  const [open, setOpen] = useState(false);
  return <>
    <button onClick={() => setOpen(true)}>Open evaluations</button>
    {open && <aside role="dialog" aria-modal="true" aria-labelledby="evaluation-dialog-title"><EvaluationDataset setId="set-1" documentIds={[]} filters={{}} isFa={false} canManage onClose={() => setOpen(false)} /></aside>}
  </>;
}

describe("EvaluationDataset dialog", () => {
  beforeEach(() => vi.clearAllMocks());

  it("labels the dialog and icon buttons, traps focus, and restores focus on Escape", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open evaluations" });
    await user.click(opener);

    expect(screen.getByRole("dialog", { name: "Evaluation dataset" })).toHaveAttribute("aria-modal", "true");
    const add = screen.getByRole("button", { name: "Add case" });
    const emptyStateAdd = screen.getByRole("button", { name: "Add a case" });
    expect(screen.getByRole("button", { name: "Back to retrieval lab" })).toBeInTheDocument();
    await waitFor(() => expect(add).toHaveFocus());

    await user.tab({ shift: true });
    expect(emptyStateAdd).toHaveFocus();
    await user.tab();
    expect(add).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});
