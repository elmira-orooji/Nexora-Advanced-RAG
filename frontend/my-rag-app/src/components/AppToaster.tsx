import { useEffect, useRef, useSyncExternalStore } from "react";
import toast, { useToaster, resolveValue } from "react-hot-toast";
import { CircleCheck, CircleAlert, Info, LoaderCircle, TriangleAlert, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { confirmationStore } from "../services/confirmation";
import "../styles/notifications.css";

export default function AppToaster() {
  const { i18n } = useTranslation();
  const fa = i18n.language.startsWith("fa");
  const { toasts, handlers } = useToaster({ duration: 4000, success: { duration: 3200 }, error: { duration: 6000 }, loading: { duration: Infinity } });
  const confirmation = useSyncExternalStore(confirmationStore.subscribe, confirmationStore.getSnapshot);
  const dialog = useRef<HTMLDialogElement>(null);
  const action = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const element = dialog.current;
    if (!element || !confirmation) return;
    element.showModal();
    return () => { element.close(); };
  }, [confirmation]);
  useEffect(() => { if (confirmation) action.current?.focus(); }, [confirmation]);

  const ConfirmationIcon = TriangleAlert;
  const notifications = toasts.filter((item) => item.visible);
  const labels = fa
    ? { success: "موفق", error: "خطا", warning: "هشدار", loading: "در حال انجام", blank: "اطلاع", custom: "اطلاع" }
    : { success: "Success", error: "Error", warning: "Warning", loading: "In progress", blank: "Notice", custom: "Notice" };

  const IconFor = (kind: string) => kind === "success" ? CircleCheck : kind === "error" ? CircleAlert : kind === "warning" ? TriangleAlert : kind === "loading" ? LoaderCircle : Info;

  return <>
    <div className="nexora-toast-stack" dir={fa ? "rtl" : "ltr"} onMouseEnter={handlers.startPause} onMouseLeave={handlers.endPause} aria-label={fa ? "اعلان‌های برنامه" : "Application notifications"}>
      {notifications.map((item) => {
        const Icon = IconFor(item.className?.includes("nexora-toast--warning") ? "warning" : item.type);
        return <article key={item.id} ref={(element) => { if (element) handlers.updateHeight(item.id, element.getBoundingClientRect().height); }} className={`nexora-toast is-visible nexora-toast--${item.className?.includes("nexora-toast--warning") ? "warning" : item.type}`} style={{ top: handlers.calculateOffset(item, { gutter: 8, defaultPosition: "top-right" }) }} {...item.ariaProps}>
          <span className="nexora-toast__icon" aria-hidden="true"><Icon size={18} /></span>
          <div className="nexora-toast__content"><div dir="auto">{resolveValue(item.message, item)}</div></div>
          <button type="button" className="nexora-toast__close" aria-label={fa ? `بستن پیام ${labels[item.type]}` : `Dismiss ${labels[item.type]}`} onClick={() => toast.dismiss(item.id)}><X size={15} /></button>
        </article>;
      })}
    </div>
    <dialog ref={dialog} dir={fa ? "rtl" : "ltr"} className="nexora-toast nexora-message-dialog is-confirmation nexora-toast--warning"
      role="alertdialog" aria-labelledby="notification-title" aria-describedby="notification-message"
      onCancel={(event) => { event.preventDefault(); confirmationStore.answer(false); }}>
      {confirmation && <>
        <div className="nexora-confirmation__heading">
          <span className="nexora-toast__icon" aria-hidden="true"><ConfirmationIcon size={20} /></span>
          <button type="button" className="nexora-confirmation__close" aria-label={fa ? "بستن" : "Close"} onClick={() => confirmationStore.answer(false)}><X size={17} /></button>
        </div>
        <div className="nexora-toast__content">
          <h2 id="notification-title">{fa ? "تأیید این اقدام" : "Confirm this action"}</h2>
          <div id="notification-message" dir="auto">{confirmation.message}</div>
        </div>
        <div className="nexora-message-actions">
          <button ref={action} type="button" onClick={() => confirmationStore.answer(false)}>{fa ? "انصراف" : "Cancel"}</button>
          <button type="button" className="is-confirm" onClick={() => confirmationStore.answer(true)}>{fa ? "بله، تأیید می‌کنم" : "Yes, confirm"}</button>
        </div>
      </>}
    </dialog>
  </>;
}
