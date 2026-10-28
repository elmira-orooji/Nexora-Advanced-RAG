import process from "node:process";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import gateway from "../../../../api/[...path]";

describe("Vercel demo gateway", () => {
  beforeEach(() => {
    vi.stubEnv("NEXORA_API_ORIGIN", "https://backend.example.test");
    vi.stubEnv("DEMO_PROXY_SECRET", "dummy-proxy-secret-of-at-least-32-characters");
  });
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

  it("forwards cookies and preserves a host-only session cookie without caching", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { headers: { "set-cookie": "nexora_session=dummy; Secure; HttpOnly; Path=/", "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await gateway.fetch(new Request("https://demo.vercel.app/api/v1/auth/demo", { method: "POST", headers: { origin: "https://demo.vercel.app", cookie: "old=dummy", "x-nexora-demo-proxy": "spoof", "x-nexora-client-ip": "spoof", "x-vercel-forwarded-for": "192.0.2.3" } }));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("https://backend.example.test/api/v1/auth/demo");
    expect(init.headers.get("cookie")).toBe("old=dummy");
    expect(init.headers.get("x-nexora-demo-proxy")).toBe(process.env.DEMO_PROXY_SECRET);
    expect(init.headers.get("x-nexora-client-ip")).toBe("192.0.2.3");
    expect(result.headers.get("set-cookie")).toContain("HttpOnly");
    expect(result.headers.get("cache-control")).toBe("no-store");
  });

  it("rejects cross-origin mutations before contacting the backend", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    const result = await gateway.fetch(new Request("https://demo.vercel.app/api/v1/auth/demo", { method: "POST", headers: { origin: "https://attacker.test" } }));
    expect(result.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fails closed when secrets or an HTTPS backend origin are missing", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NEXORA_API_ORIGIN", "http://localhost:8000");
    expect((await gateway.fetch(new Request("https://demo.vercel.app/api/v1/auth/demo"))).status).toBe(503);
    vi.stubEnv("NEXORA_API_ORIGIN", "https://backend.example.test"); vi.stubEnv("DEMO_PROXY_SECRET", "");
    expect((await gateway.fetch(new Request("https://demo.vercel.app/api/v1/auth/demo"))).status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("blocks uploads and refuses upstream redirects", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 302, headers: { location: "https://other.test" } }));
    vi.stubGlobal("fetch", fetchMock);
    const response = await gateway.fetch(new Request("https://demo.vercel.app/api/v1/conversations", { method: "POST", headers: { origin: "https://demo.vercel.app" }, body: "x".repeat(17000) }));
    expect(response.status).toBe(413);
    expect(fetchMock).not.toHaveBeenCalled();
    expect((await gateway.fetch(new Request("https://demo.vercel.app/api/v1/auth/demo"))).status).toBe(502);
  });
});
