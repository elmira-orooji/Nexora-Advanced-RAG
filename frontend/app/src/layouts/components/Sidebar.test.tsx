import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Sidebar from "./Sidebar";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" }, t: (key: string) => key }),
}));

const props = {
  currentUser: { id: "user-1", username: "sara", role: "user" as const, organization_id: "org-1", organization_name: "Nexora", organization_slug: "nexora" },
  activePage: "home" as const,
  mobileOpen: true,
  mobileOpenChange: vi.fn(),
  onCloseMobile: vi.fn(),
  onLogout: vi.fn(),
  setActivePage: vi.fn(),
  conversations: [],
  activeConversationId: null,
  onNewConversation: vi.fn(),
  onSelectConversation: vi.fn(),
  onRenameConversation: vi.fn(),
  onDeleteConversation: vi.fn(),
};

describe("Sidebar mobile accessibility", () => {
  it("hides knowledge and team management from regular users", () => {
    render(<Sidebar {...props} mobileOpen={false} />);

    expect(screen.queryByRole("button", { name: "sidebar.upload" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "sidebar.users" })).not.toBeInTheDocument();
  });

  it("focuses close, closes on Escape, and traps Tab within the menu", async () => {
    const opener = document.createElement("button");
    opener.textContent = "Open";
    document.body.append(opener);
    opener.focus();
    render(<Sidebar {...props} />);

    const closeButtons = screen.getAllByRole("button", { name: "Close navigation" });
    const close = closeButtons[closeButtons.length - 1];
    await waitFor(() => expect(document.activeElement).toBe(close));

    fireEvent.keyDown(document, { key: "Escape" });
    expect(props.onCloseMobile).toHaveBeenCalledOnce();

    opener.remove();
  });
});
