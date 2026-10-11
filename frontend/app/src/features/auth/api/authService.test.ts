import { beforeEach, describe, expect, it, vi } from "vitest";
import { authService } from "./authService";

const user = {
  id: "user-1",
  username: "elmira",
  role: "admin" as const,
  organization_id: "org-1",
  organization_name: "Nexora",
  organization_slug: "nexora",
};

describe("authService", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("creates a cookie-backed session without storing an access token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      expires_in: 3600,
      user,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    const session = await authService.login({
      username: " elmira ",
      password: "password123",
      rememberMe: true,
      organization: " NEXORA ",
    });

    expect(session.user).toEqual(user);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/auth/login", expect.objectContaining({
      credentials: "include",
      body: JSON.stringify({
        username: "elmira",
        password: "password123",
        remember_me: true,
        organization: "nexora",
      }),
    }));
    const stored = JSON.parse(localStorage.getItem("knowledgeflow.auth") ?? "{}") as Record<string, unknown>;
    expect(stored.user).toEqual(user);
    expect(stored).not.toHaveProperty("accessToken");
  });

  it("removes an expired local session", () => {
    localStorage.setItem("knowledgeflow.auth", JSON.stringify({ user, expiresAt: Date.now() - 1 }));
    expect(authService.getSession()).toBeNull();
    expect(localStorage.getItem("knowledgeflow.auth")).toBeNull();
  });

  it("preserves the login status and retry delay for actionable feedback", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      detail: "Too many login attempts. Try again later.",
    }), { status: 429, headers: { "Content-Type": "application/json", "Retry-After": "45" } }));

    await expect(authService.login({
      username: "elmira",
      password: "password123",
      rememberMe: false,
      organization: "nexora",
    })).rejects.toMatchObject({
      name: "LoginRequestError",
      status: 429,
      retryAfterSeconds: 45,
    });
  });

  it("reports a connection failure separately from an invalid login", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(authService.login({
      username: "elmira",
      password: "password123",
      rememberMe: false,
      organization: "nexora",
    })).rejects.toMatchObject({ status: 0 });
  });

  it("changes a password through the cookie-backed authentication endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));

    await authService.changePassword("old-password", "new-password");

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/auth/change-password", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: "old-password", new_password: "new-password" }),
    });
  });
});
