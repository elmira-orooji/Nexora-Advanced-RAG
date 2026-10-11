export function getPostLoginDestination(state: unknown) {
  if (!state || typeof state !== "object" || !("from" in state)) return "/home";

  const requestedPath = (state as { from?: unknown }).from;
  return typeof requestedPath === "string" && /^\/home(?:[/?#]|$)/.test(requestedPath)
    ? requestedPath
    : "/home";
}
