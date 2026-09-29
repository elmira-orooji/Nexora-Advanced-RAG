import { CircleAlert, X } from "lucide-react";

export default function InlineError({ message, onDismiss, className = "" }: { message: string; onDismiss?: () => void; className?: string }) {
  if (!message) return null;
  return <div role="alert" className={`nexora-inline-error ${className}`}>
    <CircleAlert size={16} aria-hidden="true" />
    <p dir="auto">{message}</p>
    {onDismiss && <button type="button" onClick={onDismiss} aria-label="Dismiss error"><X size={14} /></button>}
  </div>;
}
