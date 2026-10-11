import type { Page, Route } from "@playwright/test";
import type { AuthUser } from "../src/features/auth/types/auth.js";

export const SESSION_KEY = "knowledgeflow.auth";
export const API_PATTERN = "**/api/v1/**";

export const regularUser: AuthUser = {
  id: "u-1",
  username: "ada",
  role: "user",
  organization_id: "o-1",
  organization_name: "Acme Corp",
  organization_slug: "acme",
};

export const adminUser: AuthUser = {
  id: "u-admin",
  username: "admin",
  role: "admin",
  organization_id: "o-1",
  organization_name: "Acme Corp",
  organization_slug: "acme",
};

export const knowledgeSet = {
  id: "set-1",
  name: "Onboarding Manual",
  description: "Company onboarding handbook",
  created_by_id: "u-1",
  document_count: 1,
  indexed_document_count: 2,
  access_level: "view",
  child_chunk_size: 512,
  chunk_overlap: 64,
  parent_chunk_size: 2048,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-02T00:00:00Z",
};

export const sampleDocument = {
  id: "doc-1",
  filename: "handbook.pdf",
  status: "indexed",
  size_bytes: 102400,
  created_at: "2025-01-15T00:00:00Z",
  uploaded_at: "2025-01-15T00:00:00Z",
  indexed_at: "2025-01-15T00:01:00Z",
  chunk_count: 12,
  error: null,
};

const analyticsOverview = {
  period_days: 7,
  total_queries: 0,
  active_users: 1,
  grounded_rate: 0,
  positive_feedback_rate: null,
  feedback_coverage: 0,
  unanswered_queries: 0,
  average_citations: 0,
  indexed_documents: 1,
  failed_documents: 0,
  daily: [],
  assistants: [],
  knowledge_sets: [],
  negative_reasons: [],
  recent_issues: [],
};

/** Seed a valid auth session before the app boots (localStorage). */
export function seedSession(page: Page, user: AuthUser = regularUser): void {
  page.addInitScript(
    ([key, value]) => {
      localStorage.clear();
      localStorage.setItem(key, JSON.stringify(value));
    },
    [SESSION_KEY, { expiresAt: Date.now() + 3_600_000, user }] as const,
  );
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify(body),
  });
}

/**
 * Intercept every `/api/v1/*` request and return canned responses so end-to-end
 * tests never depend on the FastAPI backend (or its database/LLM providers).
 */
export async function stubApi(page: Page, options: { answer?: string; conversations?: unknown[]; documents?: unknown[] } = {}): Promise<void> {
  const answer = options.answer ?? "You can request a refund within 30 days.";
  const conversations = options.conversations ?? [];
  const documents = options.documents ?? [];
  const assistantMessage = {
    id: "m-2",
    role: "assistant",
    content: answer,
    sources: [
      {
        chunk_id: "c-1",
        document_id: "d-1",
        filename: "policy.pdf",
        content: "The refund window is 30 days after purchase.",
        score: 0.92,
        chunk_index: 0,
        page: 4,
        section: "Refunds",
      },
    ],
    answer_id: "a-1",
    created_at: "2025-02-01T00:00:00Z",
  };

  await page.route(API_PATTERN, async (route) => {
    const request = route.request();
    const method = request.method();
    const { pathname } = new URL(request.url());

    // Authentication
    if (method === "POST" && pathname.endsWith("/auth/login")) {
      return json(route, { expires_in: 3600, user: regularUser });
    }
    if (method === "POST" && pathname.endsWith("/auth/logout")) {
      return route.fulfill({ status: 204 });
    }

    // Analytics overview (admin users see AnalyticsPage on /home)
    if (method === "GET" && pathname.startsWith("/api/v1/analytics/overview")) {
      return json(route, analyticsOverview);
    }

    // Conversation sidebar list
    if (method === "GET" && pathname === "/api/v1/conversations") {
      return json(route, conversations);
    }

    // Knowledge base sets
    if (method === "GET" && pathname === "/api/v1/document-sets") {
      return json(route, [knowledgeSet]);
    }

    // Documents list for a set
    if (method === "GET" && pathname === "/api/v1/documents") {
      return json(route, documents);
    }

    if (method === "GET" && /\/document-sets\/[^/]+\/documents$/.test(pathname)) {
      return json(route, documents);
    }

    // Upload file
    if (method === "POST" && pathname === "/api/v1/documents/ingest") {
      return json(route, {
        id: "doc-new",
        filename: "uploaded-file.pdf",
        status: "queued",
        size_bytes: 51200,
        uploaded_at: "2025-02-01T00:00:00Z",
        indexed_at: null,
        chunk_count: 0,
        error: null,
      });
    }

    if (method === "POST" && /\/document-sets\/[^/]+\/documents$/.test(pathname)) {
      return json(route, {
        id: "doc-new",
        filename: "uploaded-file.pdf",
        status: "queued",
        size_bytes: 51200,
        uploaded_at: "2025-02-01T00:00:00Z",
        indexed_at: null,
        chunk_count: 0,
        error: null,
      });
    }

    // Cloud connectors and retrieval/evaluation side panels on the Knowledge page.
    if (method === "GET" && /\/document-sets\/[^/]+\/connectors$/.test(pathname)) {
      return json(route, []);
    }

    if (method === "GET" && /\/document-sets\/[^/]+\/evaluation-cases$/.test(pathname)) {
      return json(route, []);
    }

    // Rename conversation
    if (method === "PATCH" && /\/conversations\/[^/]+$/.test(pathname)) {
      return json(route, {
        id: "conv-1",
        title: "Renamed conversation",
        document_id: null,
        document_set_id: "set-1",
        assistant_id: null,
        created_at: "2025-02-01T00:00:00Z",
        updated_at: "2025-02-01T00:01:00Z",
      });
    }

    // Delete conversation
    if (method === "DELETE" && /\/conversations\/[^/]+$/.test(pathname)) {
      return route.fulfill({ status: 204 });
    }

    // Create a conversation when the first message is sent
    if (method === "POST" && pathname === "/api/v1/conversations") {
      return json(route, {
        id: "conv-1",
        title: "New conversation",
        document_id: null,
        document_set_id: "set-1",
        assistant_id: null,
        created_at: "2025-02-01T00:00:00Z",
        updated_at: "2025-02-01T00:00:00Z",
      });
    }

    // Send a message -> assistant reply
    if (method === "POST" && /\/conversations\/[^/]+\/messages$/.test(pathname)) {
      return json(route, assistantMessage);
    }

    // Load conversation detail
    if (method === "GET" && /\/conversations\/[^/]+$/.test(pathname)) {
      return json(route, {
        id: "conv-1",
        title: "Onboarding Q",
        document_id: null,
        document_set_id: "set-1",
        assistant_id: null,
        created_at: "2025-02-01T00:00:00Z",
        updated_at: "2025-02-01T00:00:00Z",
        messages: [
          {
            id: "m-1",
            role: "user",
            content: "What is the refund policy?",
            sources: null,
            answer_id: null,
            created_at: "2025-02-01T00:00:00Z",
          },
          assistantMessage,
        ],
      });
    }

    return route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
  });
}
