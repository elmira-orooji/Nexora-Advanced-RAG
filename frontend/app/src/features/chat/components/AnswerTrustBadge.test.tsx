import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AnswerTrustBadge, { resolveAnswerTrust } from "./AnswerTrustBadge";

describe("AnswerTrustBadge", () => {
  it("uses the insufficient state when no source supports an answer", () => {
    expect(resolveAnswerTrust(undefined, false, 0)).toBe("insufficient");
    render(<AnswerTrustBadge grounded={false} sourceCount={0} isFa={false} />);
    expect(screen.getByText("Insufficient sources")).toBeInTheDocument();
  });

  it("lets users open the supporting sources from a grounded badge", () => {
    const onOpenSources = vi.fn();
    render(<AnswerTrustBadge answerBasis="sources" grounded sourceCount={2} isFa={false} onOpenSources={onOpenSources} />);
    fireEvent.click(screen.getByRole("button", { name: /view sources/i }));
    expect(onOpenSources).toHaveBeenCalledOnce();
  });
});
