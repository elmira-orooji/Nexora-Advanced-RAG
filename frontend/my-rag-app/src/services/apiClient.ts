import { authService } from "./authService";
import { API_URL } from "../config/api";

export const AUTH_EXPIRED_EVENT = "nexora:auth-expired";
export const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;

export class ApiTimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`The request timed out after ${Math.ceil(timeoutMs / 1000)} seconds`);
    this.name = "ApiTimeoutError";
  }
}

export class ApiResponseError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly requestId: string | null;

  constructor(message: string, status: number, code: string | null, requestId: string | null) {
    super(message);
    this.name = "ApiResponseError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export type ApiRequestInit = RequestInit & { timeoutMs?: number };

type ErrorPayload = {
  detail?: string | { message?: string };
  error?: { code?: string; message?: string; request_id?: string };
};

function errorMessage(payload: ErrorPayload | null, fallback: string) {
  if (typeof payload?.error?.message === "string") return payload.error.message;
  if (typeof payload?.detail === "string") return payload.detail;
  if (payload?.detail && typeof payload.detail.message === "string") return payload.detail.message;
  return fallback;
}

function hasApiErrorMessage(payload: ErrorPayload | null) {
  return typeof payload?.error?.message === "string"
    || typeof payload?.detail === "string"
    || (payload?.detail !== null && typeof payload?.detail === "object" && typeof payload.detail.message === "string");
}

export async function apiFetch(path: string, init: ApiRequestInit = {}) {
  const { timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, signal: externalSignal, ...fetchInit } = init;
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort(externalSignal?.reason);
  externalSignal?.addEventListener("abort", abortFromCaller, { once: true });
  const timer = timeoutMs > 0 ? window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs) : undefined;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...fetchInit,
      signal: controller.signal,
      credentials: init.credentials ?? "include",
    });
  } catch (error) {
    if (timedOut) throw new ApiTimeoutError(timeoutMs);
    throw error;
  } finally {
    if (timer !== undefined) window.clearTimeout(timer);
    externalSignal?.removeEventListener("abort", abortFromCaller);
  }

  if (response.status === 401) {
    authService.clearLocalSession();
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }

  return response;
}

export async function apiRequest<T>(path: string, init?: ApiRequestInit, fallback = "Request failed"): Promise<T> {
  const response = await apiFetch(path, init);
  if (response.status === 204) return undefined as T;

  const payload = (await response.json().catch(() => null)) as ErrorPayload | T | null;
  if (!response.ok) {
    const error = payload as ErrorPayload | null;
    const requestId = typeof error?.error?.request_id === "string"
      ? error.error.request_id
      : response.headers.get("X-Request-ID");
    const message = hasApiErrorMessage(error)
      ? errorMessage(error, fallback)
      : `${fallback} (HTTP ${response.status})`;
    throw new ApiResponseError(
      response.status >= 500 && requestId ? `${message} · Request ID: ${requestId}` : message,
      response.status,
      typeof error?.error?.code === "string" ? error.error.code : null,
      requestId,
    );
  }
  return payload as T;
}

export function apiUpload<T>(path: string, body: FormData, onProgress: (progress: number) => void, idempotencyKey?: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_URL}${path}`);
    request.withCredentials = true;
    if (idempotencyKey) request.setRequestHeader("Idempotency-Key", idempotencyKey);
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    });
    request.addEventListener("load", () => {
      const payload = (() => {
        try { return JSON.parse(request.responseText) as T | ErrorPayload; }
        catch { return null; }
      })();
      if (request.status === 401) {
        authService.clearLocalSession();
        window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
      }
      if (request.status >= 200 && request.status < 300) {
        onProgress(100);
        resolve(payload as T);
      } else {
        reject(new Error(errorMessage(payload as ErrorPayload | null, "Upload failed")));
      }
    });
    request.addEventListener("error", () => reject(new Error("Network error while uploading")));
    request.addEventListener("abort", () => reject(new DOMException("Upload aborted", "AbortError")));
    request.send(body);
  });
}
