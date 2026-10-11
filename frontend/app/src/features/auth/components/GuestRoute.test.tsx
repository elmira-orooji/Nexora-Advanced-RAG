import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import GuestRoute from "./GuestRoute";

const user = {
  id: "user-1",
  username: "member",
  role: "user",
  organization_id: "org-1",
  organization_name: "Nexora",
  organization_slug: "nexora",
};

function renderRoutes() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<GuestRoute><div>Login page</div></GuestRoute>} />
        <Route path="/home" element={<div>Workspace</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("GuestRoute", () => {
  it("shows login to an unauthenticated visitor", () => {
    renderRoutes();
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("redirects an authenticated user to the workspace", () => {
    sessionStorage.setItem("knowledgeflow.auth", JSON.stringify({ user, expiresAt: Date.now() + 60_000 }));
    renderRoutes();
    expect(screen.getByText("Workspace")).toBeInTheDocument();
  });
});
