import { describe, expect, it, vi } from "vitest";
import { apiRequest, AUTH_EXPIRED_EVENT } from "./apiClient";

describe("apiRequest authentication handling", () => {
  it("clears local session and announces a 401 response", async () => {
    localStorage.setItem("knowledgeflow.auth", JSON.stringify({ expiresAt: Date.now() + 60_000, user: {} }));
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Expired" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    }));
    const listener = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, listener);

    await expect(apiRequest("/private")).rejects.toThrow("Expired");

    expect(localStorage.getItem("knowledgeflow.auth")).toBeNull();
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(AUTH_EXPIRED_EVENT, listener);
  });

  it("keeps the server error code and request ID for actionable UI feedback", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      detail: "Document set not found",
      error: { code: "not_found", message: "Document set not found", request_id: "req-contract-1" },
    }), {
      status: 404,
      headers: { "Content-Type": "application/json", "X-Request-ID": "req-contract-1" },
    }));

    await expect(apiRequest("/document-sets/missing")).rejects.toMatchObject({
      name: "ApiResponseError",
      status: 404,
      code: "not_found",
      requestId: "req-contract-1",
    });
  });

  it("includes the HTTP status when a gateway returns a non-JSON error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("Bad Gateway", {
      status: 502,
      headers: { "Content-Type": "text/plain" },
    }));

    await expect(apiRequest("/search/trace")).rejects.toMatchObject({
      name: "ApiResponseError",
      message: "Request failed (HTTP 502)",
      status: 502,
    });
  });

  it("includes the request ID for server errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      detail: "Internal server error",
      error: { code: "internal_error", message: "Internal server error", request_id: "trace-failure-test" },
    }), { status: 500, headers: { "Content-Type": "application/json" } }));

    await expect(apiRequest("/search/trace")).rejects.toMatchObject({
      name: "ApiResponseError",
      message: "Internal server error · Request ID: trace-failure-test",
      requestId: "trace-failure-test",
    });
  });
});
