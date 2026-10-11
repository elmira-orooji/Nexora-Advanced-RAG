import type { LoginSchemaType } from "../schemas/loginSchema";
import type { AuthSession, AuthUser, LoginResponse } from "../types/auth";
import { API_URL } from "../../../config/api";
const SESSION_KEY = "knowledgeflow.auth";

export class LoginRequestError extends Error {
  readonly status: number;
  readonly retryAfterSeconds: number | null;

  constructor(
    message: string,
    status: number,
    retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = "LoginRequestError";
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

function parseError(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

function saveSession(session: AuthSession, rememberMe: boolean) {
  localStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(SESSION_KEY);
  const storage = rememberMe ? localStorage : sessionStorage;
  storage.setItem(SESSION_KEY, JSON.stringify(session));
}

export const authService = {
  async login(data: LoginSchemaType): Promise<AuthSession> {
    let response: Response;
    try {
      response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: data.username.trim(),
          password: data.password,
          remember_me: data.rememberMe,
          organization: data.organization.trim().toLowerCase(),
        }),
      });
    } catch {
      throw new LoginRequestError("Network request failed", 0);
    }
    const payload = (await response.json().catch(() => null)) as LoginResponse | null;
    if (!response.ok || payload === null) {
      const retryAfter = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
      throw new LoginRequestError(
        parseError(payload, "Unable to sign in. Please try again."),
        response.status,
        Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
      );
    }
    const session: AuthSession = {
      expiresAt: Date.now() + payload.expires_in * 1000,
      user: payload.user,
    };
    saveSession(session, data.rememberMe);
    return session;
  },

  getSession(): AuthSession | null {
    const raw = sessionStorage.getItem(SESSION_KEY) || localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    try {
      const session = JSON.parse(raw) as AuthSession;
      const invalidExpiry = (
        typeof session.expiresAt !== "number" ||
        !Number.isFinite(session.expiresAt) ||
        session.expiresAt <= Date.now()
      );
      if (!session.user || invalidExpiry) {
        this.clearLocalSession();
        return null;
      }
      return session;
    } catch {
      this.clearLocalSession();
      return null;
    }
  },

  getUser(): AuthUser | null {
    return this.getSession()?.user ?? null;
  },

  isAuthenticated() {
    return this.getSession() !== null;
  },

  clearLocalSession() {
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(SESSION_KEY);
  },

  async logout() {
    try {
      await fetch(`${API_URL}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      this.clearLocalSession();
    }
  },

  async changePassword(currentPassword: string, newPassword: string) {
    const response = await fetch(`${API_URL}/auth/change-password`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(parseError(payload, "Password could not be changed. Please try again."));
    }
  },
};
