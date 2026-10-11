import { useEffect, useState } from "react";

/** Restarts the dismissal timer even when the same message is shown again. */
export function useTransientMessage(durationMs = 2500) {
  const [notice, setNotice] = useState<{ text: string } | null>(null);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), durationMs);
    return () => window.clearTimeout(timer);
  }, [notice, durationMs]);
  return { message: notice?.text ?? "", show: (text: string) => setNotice(text ? { text } : null) };
}
