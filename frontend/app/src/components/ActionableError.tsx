import { CircleAlert, RefreshCw } from "lucide-react";

import { operationError, type OperationKind } from "../lib/operationFeedback";

type ActionableErrorProps = {
  error: unknown;
  isFa: boolean;
  operation: OperationKind;
  title: string;
  onRetry: () => void;
};

export default function ActionableError({ error, isFa, operation, title, onRetry }: ActionableErrorProps) {
  const rawError = error instanceof Error ? error.message.trim() : typeof error === "string" ? error.trim() : "";
  const message = operationError(error, operation, isFa);

  return <div role="alert" className="grid h-full place-items-center px-6 text-center">
    <div className="max-w-sm">
      <CircleAlert className="mx-auto text-rose-300" size={28} aria-hidden="true" />
      <h3 className="mt-4 text-sm font-semibold tm-text">{title}</h3>
      <p className="mt-2 text-sm leading-6 tm-muted">{message}</p>
      {rawError && rawError !== message && <details className="mt-3 text-start text-xs tm-muted">
        <summary className="cursor-pointer select-none underline underline-offset-4">{isFa ? "جزئیات فنی" : "Technical details"}</summary>
        <p className="nexora-text-wrap mt-2 rounded-lg bg-black/10 p-2 text-xs leading-5">{rawError}</p>
      </details>}
      <button type="button" onClick={onRetry} className="team-primary mx-auto mt-5 flex h-10 items-center gap-2 px-4 text-xs font-semibold">
        <RefreshCw size={14} aria-hidden="true" />{isFa ? "تلاش مجدد" : "Try again"}
      </button>
    </div>
  </div>;
}
