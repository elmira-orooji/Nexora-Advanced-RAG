import { GitBranch as Github, Globe2, RefreshCw } from "lucide-react";
import { type Connector } from "../../../services/connectorService";
import { operationError } from "../../../lib/operationFeedback";

export function ConnectorStatus({ connector, syncing, isFa, onSync }: { connector: Connector; syncing: boolean; isFa: boolean; onSync: () => Promise<void> }) {
  const failed = connector.status === "failed";
  const ready = connector.status === "ready";
  const label = syncing ? (isFa ? "در حال همگام‌سازی" : "Syncing now") : failed ? (isFa ? "همگام‌سازی ناموفق" : "Sync failed") : ready ? (isFa ? "آماده" : "Ready") : (isFa ? "در انتظار همگام‌سازی" : "Waiting to sync");
  return <div className="min-w-[185px] shrink-0 rounded-xl border border-white/[.07] bg-white/[.025] p-2.5" aria-label={`${connector.name}: ${label}`}>
    <div className="flex items-center gap-2"><span className="kb-accent">{connector.connector_type === "github" ? <Github size={13} /> : <Globe2 size={13} />}</span><span className="min-w-0 flex-1 truncate text-xs font-medium kb-text">{connector.name}</span><button type="button" title={failed ? (isFa ? "تلاش مجدد برای همگام‌سازی" : "Retry sync") : (isFa ? "همگام‌سازی اکنون" : "Sync now")} aria-label={failed ? (isFa ? "تلاش مجدد برای همگام‌سازی" : "Retry sync") : (isFa ? "همگام‌سازی اکنون" : "Sync now")} disabled={syncing} onClick={() => void onSync()} className="app-icon-button grid size-7 place-items-center rounded-lg kb-muted hover:text-white"><RefreshCw size={12} className={syncing ? "animate-spin" : ""} /></button></div>
    <p className={`mt-2 text-xs ${failed ? "text-rose-300/85" : ready ? "text-emerald-300/85" : "text-amber-200/80"}`}>{label}</p>
    {failed && <p className="mt-1 line-clamp-2 text-xs leading-5 kb-muted">{operationError(connector.last_error, "sync", isFa)}</p>}
  </div>;
}

