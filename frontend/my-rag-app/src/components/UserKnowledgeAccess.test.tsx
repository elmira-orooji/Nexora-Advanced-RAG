import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import UserKnowledgeAccess from "./UserKnowledgeAccess";
const mocks = vi.hoisted(() => ({ listSets: vi.fn(), permissions: vi.fn(), savePermissions: vi.fn() }));
vi.mock("../services/userService", () => ({ userService: mocks }));
const user = { id: "user-1", username: "member", role: "user" as const, is_active: true, job_title: null, created_at: "2026-01-01" };
beforeEach(() => {
  vi.clearAllMocks();
  mocks.listSets.mockResolvedValue([{ id: "a", name: "Insurance" }, { id: "b", name: "Company" }]);
  mocks.permissions.mockResolvedValue([{ document_set_id: "a", permission: "view" }]);
  mocks.savePermissions.mockResolvedValue([]);
});
it("loads existing permissions and saves grants and revocations", async () => {
  render(<UserKnowledgeAccess user={user} isFa={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Knowledge access: member" }));
  expect(await screen.findByRole("combobox", { name: "Insurance" })).toHaveValue("view");
  fireEvent.change(screen.getByRole("combobox", { name: "Insurance" }), { target: { value: "none" } });
  fireEvent.change(screen.getByRole("combobox", { name: "Company" }), { target: { value: "manage" } });
  fireEvent.click(screen.getByRole("button", { name: "Save permissions" }));
  await waitFor(() => expect(mocks.savePermissions).toHaveBeenCalledWith("user-1", [{ document_set_id: "b", permission: "manage" }]));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});
it("prevents saving when loading permissions fails and supports retry", async () => {
  mocks.permissions.mockRejectedValueOnce(new Error("Cannot load permissions"));
  render(<UserKnowledgeAccess user={user} isFa={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Knowledge access: member" }));
  expect(await screen.findByText("Cannot load permissions")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save permissions" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("combobox", { name: "Insurance" })).toHaveValue("view");
  expect(mocks.savePermissions).not.toHaveBeenCalled();
});
it("cancels without changing permissions", async () => {
  render(<UserKnowledgeAccess user={user} isFa={true} />);
  fireEvent.click(screen.getByRole("button", { name: "دسترسی پایگاه‌های دانش: member" }));
  await screen.findByRole("combobox", { name: "Insurance" });
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(mocks.savePermissions).not.toHaveBeenCalled();
});
