import process from "node:process";

// Vercel's same-origin gateway keeps session cookies on the public demo host.
// Secrets are runtime-only variables and must never use a VITE_ prefix.
export default {
  async fetch(request: Request): Promise<Response> {
    const origin = process.env.NEXORA_API_ORIGIN;
    const secret = process.env.DEMO_PROXY_SECRET;
    if (!origin || !secret || secret.length < 32) {
      return Response.json({ detail: "The demo backend has not been connected yet." }, { status: 503, headers: { "Cache-Control": "no-store" } });
    }
    let upstream: URL;
    try {
      upstream = new URL(origin);
      if (upstream.protocol !== "https:" || upstream.username || upstream.password || upstream.pathname !== "/" || upstream.search || upstream.hash) throw new Error("Invalid origin");
    } catch {
      return Response.json({ detail: "The demo backend configuration is invalid." }, { status: 503 });
    }
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return new Response(null, { status: 404 });
    const mutation = !["GET", "HEAD", "OPTIONS"].includes(request.method);
    if (mutation && request.headers.get("origin") !== url.origin) {
      return Response.json({ detail: "Request origin is not permitted." }, { status: 403 });
    }
    const headers = new Headers({ "x-nexora-demo-proxy": secret });
    for (const name of ["accept", "content-type", "cookie", "origin", "authorization", "x-request-id"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    headers.set("x-nexora-client-ip", request.headers.get("x-vercel-forwarded-for")?.split(",")[0]?.trim() || "unknown");
    // Public demo requests contain only short JSON chat inputs, never uploads.
    if (Number(request.headers.get("content-length") || 0) > 16384) return new Response(null, { status: 413 });
    const body = mutation ? await request.text() : undefined;
    if (body && new TextEncoder().encode(body).byteLength > 16384) return new Response(null, { status: 413 });
    try {
      const result = await fetch(new URL(url.pathname + url.search, upstream), {
        method: request.method, headers, body, redirect: "manual", signal: AbortSignal.timeout(110_000),
      });
      if (result.status >= 300 && result.status < 400) {
        await result.body?.cancel();
        return Response.json({ detail: "Unexpected backend redirect." }, { status: 502 });
      }
      const responseHeaders = new Headers(result.headers);
      for (const name of ["content-encoding", "content-length", "connection", "transfer-encoding"]) responseHeaders.delete(name);
      responseHeaders.set("Cache-Control", "no-store");
      return new Response(result.body, { status: result.status, headers: responseHeaders });
    } catch {
      return Response.json({ detail: "The demo service is temporarily unavailable. Please try again." }, { status: 502, headers: { "Cache-Control": "no-store" } });
    }
  },
};
