export const DEFAULT_API_URL = "/api/v1";

export function resolveApiUrl(configuredUrl?: string) {
  const url = configuredUrl?.trim() || DEFAULT_API_URL;
  return url === "/" ? "" : url.replace(/\/+$/, "");
}

export const API_URL = resolveApiUrl(import.meta.env.VITE_API_URL);
