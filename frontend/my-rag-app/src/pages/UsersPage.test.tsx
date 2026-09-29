import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UsersPage from "./UsersPage";

const mocks = vi.hoisted(() => ({ list: vi.fn(), toastError: vi.fn() }));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { language: "en" }, t: (key: string) => key }),
}));
vi.mock("react-hot-toast", () => ({ default: { error: mocks.toastError, success: vi.fn() } }));
vi.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div> },
  useReducedMotion: () => true,
}));
vi.mock("../services/userService", () => ({ userService: { list: mocks.list, remove: vi.fn() } }));
vi.mock("../components/AddUserForm", () => ({ default: () => null }));

describe("UsersPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows a service error separately from the empty state and retries", async () => {
    mocks.list
      .mockRejectedValueOnce(new Error("Directory service unavailable"))
      .mockResolvedValueOnce([{ id: "user-1", username: "sara", role: "user", is_active: true, job_title: null, created_at: "2026-09-01T00:00:00Z" }]);

    render(<UsersPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Directory service unavailable");
    expect(screen.queryByText("No members match your search.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("sara")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("turns a technical network error into an actionable recovery message", async () => {
    mocks.list.mockRejectedValueOnce(new Error("Failed to fetch"));

    render(<UsersPage />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("We couldn't load team members. Check the service connection and try again.");
    expect(screen.getByText("Technical details")).toBeInTheDocument();
    expect(mocks.toastError).not.toHaveBeenCalled();
  });

  it("lists admins first and orders each role by creation time", async () => {
    mocks.list.mockResolvedValueOnce([
      { id: "user-new", username: "new user", role: "user", is_active: true, job_title: null, created_at: "2026-09-03T00:00:00Z" },
      { id: "admin-new", username: "new admin", role: "admin", is_active: true, job_title: null, created_at: "2026-09-02T00:00:00Z" },
      { id: "user-old", username: "old user", role: "user", is_active: true, job_title: null, created_at: "2026-09-01T00:00:00Z" },
      { id: "admin-old", username: "old admin", role: "admin", is_active: true, job_title: null, created_at: "2026-08-31T00:00:00Z" },
    ]);

    const { container } = render(<UsersPage />);

    await screen.findByText("old admin");
    expect(Array.from(container.querySelectorAll(".team-member-row .tm-text")).map((node) => node.textContent)).toEqual([
      "old admin", "new admin", "old user", "new user",
    ]);
  });
});
