import { useEffect, useRef, useState } from "react";
import { Bell, CheckCheck, CircleAlert, CircleCheck, Trash2, X } from "lucide-react";
import toast from "react-hot-toast";
import InlineError from "./InlineError";
import { useTranslation } from "react-i18next";
import { notificationService, type AppNotification } from "../services/notificationService";

interface NotificationCenterProps {
  onNavigate: (path: string) => void;
}

export default function NotificationCenter({ onNavigate }: NotificationCenterProps) {
  const { i18n } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const [items, setItems] = useState<AppNotification[]>([]);
  const [deleting, setDeleting] = useState<string[]>([]);
  const [deleteError, setDeleteError] = useState("");
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const unread = items.filter((item) => !item.read_at).length;
  const load = () => notificationService.list().then(setItems).catch(() => undefined);

  useEffect(() => {
    load();
    const tick = () => load();
    const interval = window.setInterval(tick, document.hidden ? 300_000 : 60_000);
    const visibility = () => { if (!document.hidden) load(); };
    document.addEventListener("visibilitychange", visibility);
    return () => { window.clearInterval(interval); document.removeEventListener("visibilitychange", visibility); };
  }, []);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { if (!panelRef.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", escape); };
  }, [open]);

  const openNotification = async (item: AppNotification) => {
    if (!item.read_at) {
      const updated = await notificationService.markRead(item.id).catch(() => null);
      if (updated) setItems((current) => current.map((value) => value.id === item.id ? updated : value));
    }
    setOpen(false);
    if (item.target_path) onNavigate(item.target_path);
  };

  const markAllRead = async () => {
    await notificationService.markAllRead().catch(() => undefined);
    setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at ?? new Date().toISOString() })));
  };

  const deleteNotification = async (id: string) => {
    if (deleting.includes(id)) return;
    setDeleting((current) => [...current, id]);
    setDeleteError("");
    try {
      await notificationService.delete(id);
      setItems((current) => current.filter((item) => item.id !== id));
      toast.success(isFa ? "اعلان حذف شد" : "Notification deleted");
    } catch (error) {
      setDeleteError((error as Error).message || (isFa ? "حذف اعلان انجام نشد" : "Could not delete notification"));
    } finally {
      setDeleting((current) => current.filter((itemId) => itemId !== id));
    }
  };

  return <div ref={panelRef} className="relative" dir={isFa ? "rtl" : "ltr"}>
    <button type="button" onClick={() => setOpen((value) => !value)} aria-label={isFa ? "اعلان‌ها" : "Notifications"} aria-expanded={open} className="app-icon-button relative grid size-10 place-items-center rounded-xl">
      <Bell size={18} aria-hidden="true" />
      {unread > 0 && <span className="absolute end-1 top-1 grid min-w-4 h-4 place-items-center rounded-full bg-[#c43cff] px-1 text-[10px] font-bold text-white">{unread > 9 ? "9+" : unread}</span>}
    </button>
    {open && <section role="dialog" aria-label={isFa ? "اعلان‌ها" : "Notifications"} className="notification-center-panel entrance-motion-surface absolute end-0 top-12 z-[70] w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-white/10 bg-[#0b1630]/95 shadow-2xl backdrop-blur-xl">
      <header className="notification-center-header flex items-center justify-between border-b border-white/[.08] px-4 py-3">
        <h2 className="text-sm font-semibold">{isFa ? "اعلان‌ها" : "Notifications"}</h2>
        <div className="flex items-center gap-1"><button type="button" onClick={() => void markAllRead()} disabled={!unread} aria-label={isFa ? "خواندن همه" : "Mark all as read"} className="app-icon-button grid size-8 place-items-center rounded-lg text-white/55 hover:text-white disabled:opacity-30"><CheckCheck size={15} /></button><button type="button" onClick={() => setOpen(false)} aria-label={isFa ? "بستن" : "Close"} className="app-icon-button grid size-8 place-items-center rounded-lg text-white/55 hover:text-white"><X size={15} /></button></div>
      </header>
      {deleteError && <div className="px-3 pt-3"><InlineError message={deleteError} onDismiss={() => setDeleteError("")} /></div>}
      <div className="max-h-[min(26rem,calc(100vh-7rem))] overflow-y-auto p-2">
        {items.map((item) => <div key={item.id} className={`notification-center-item group flex items-start gap-1 rounded-xl transition hover:bg-white/[.055] ${item.read_at ? "opacity-60" : "bg-white/[.035]"}`}>
          <button type="button" onClick={() => void openNotification(item)} className="flex min-w-0 flex-1 items-start gap-3 p-3 text-start">
            <span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg ${item.severity === "error" ? "bg-rose-400/10 text-rose-300" : "bg-emerald-400/10 text-emerald-300"}`}>{item.severity === "error" ? <CircleAlert size={16} /> : <CircleCheck size={16} />}</span>
            <span className="min-w-0 flex-1"><span className="notification-center-title block text-xs font-semibold text-white/90">{item.title}</span><span className="notification-center-body mt-1 block text-xs leading-5 text-white/55">{item.body}</span><span className="notification-center-time mt-1.5 block text-[11px] text-white/35">{new Intl.DateTimeFormat(isFa ? "fa-IR" : "en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.created_at))}</span></span>
          </button>
          <button type="button" onClick={() => void deleteNotification(item.id)} disabled={deleting.includes(item.id)} aria-label={isFa ? "حذف اعلان" : "Delete notification"} title={isFa ? "حذف اعلان" : "Delete notification"} className="notification-center-delete me-1 mt-2 grid size-8 shrink-0 place-items-center rounded-lg text-white/50 opacity-70 transition hover:bg-rose-400/10 hover:text-rose-300 focus-visible:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-400 group-hover:opacity-100 disabled:cursor-wait disabled:opacity-40"><Trash2 size={15} aria-hidden="true" /></button>
        </div>)}
        {!items.length && <p className="notification-center-empty px-3 py-8 text-center text-xs text-white/45">{isFa ? "اعلان جدیدی وجود ندارد." : "No notifications yet."}</p>}
      </div>
    </section>}
  </div>;
}
