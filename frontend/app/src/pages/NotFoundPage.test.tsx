import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import NotFoundPage from "./NotFoundPage";
import "../i18n";

describe("NotFoundPage", () => {
  it("shows the invalid path and a route back to sign in", () => {
    render(<MemoryRouter initialEntries={["/missing/report"]}><NotFoundPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByText("/missing/report")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to sign in/i })).toHaveAttribute("href", "/");
  });
});
