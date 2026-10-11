import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import ProtectedRoute from "./ProtectedRoute";

const user = {
  id: "user-1",
  username: "member",
  role: "user",
  organization_id: "org-1",
  organization_name: "Nexora",
  organization_slug: "nexora",
};

function LoginDestination() {
  const location = useLocation();
  return <div>Login destination: {(location.state as { from?: string } | null)?.from}</div>;
}

function renderRoutes(initialEntry = "/home/settings") {
  return render(<MemoryRouter initialEntries={[initialEntry]}>
    <Routes>
      <Route path="/" element={<LoginDestination />} />
      <Route path="/home/settings" element={<ProtectedRoute><div>Private settings</div></ProtectedRoute>} />
    </Routes>
  </MemoryRouter>);
}

describe("ProtectedRoute", () => {
  it("redirects an unauthenticated visitor to login", () => {
    renderRoutes();
    expect(screen.getByText("Login destination: /home/settings")).toBeInTheDocument();
  });

  it("preserves query parameters and the hash in the login destination", () => {
    renderRoutes("/home/settings?tab=security#sessions");
    expect(screen.getByText("Login destination: /home/settings?tab=security#sessions")).toBeInTheDocument();
  });

  it("allows a user with a valid session", () => {
    sessionStorage.setItem("knowledgeflow.auth", JSON.stringify({ user, expiresAt: Date.now() + 60_000 }));
    renderRoutes();
    expect(screen.getByText("Private settings")).toBeInTheDocument();
  });
});
