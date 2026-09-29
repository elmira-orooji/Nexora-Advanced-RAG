import { useCallback, useEffect, useRef, useSyncExternalStore, type ReactNode } from "react";
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
  const updateToastHeight = handlers.updateHeight;

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
        return <ToastItem key={item.id} item={item} fa={fa} label={labels[item.type]} Icon={Icon} offset={handlers.calculateOffset(item, { gutter: 8, defaultPosition: "top-right" })} onHeightUpdate={updateToastHeight} onDismiss={() => toast.dismiss(item.id)}>
          {resolveValue(item.message, item)}
        </ToastItem>;
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

function ToastItem({ item, fa, label, Icon, offset, onHeightUpdate, onDismiss, children }: {
  item: ReturnType<typeof useToaster>["toasts"][number];
  fa: boolean;
  label: string;
  Icon: typeof CircleCheck;
  offset: number;
  onHeightUpdate: (id: string, height: number) => void;
  onDismiss: () => void;
  children: ReactNode;
}) {
  const ref = useCallback((element: HTMLElement | null) => {
    if (!element) return;
    const updateHeight = () => onHeightUpdate(item.id, element.getBoundingClientRect().height);
    updateHeight();
    const observer = new MutationObserver(updateHeight);
    observer.observe(element, { subtree: true, childList: true, characterData: true });
  }, [item.id, onHeightUpdate]);
  const variant = item.className?.includes("nexora-toast--warning") ? "warning" : item.type;

  return <article ref={ref} className={`nexora-toast is-visible nexora-toast--${variant}`} style={{ top: offset }} {...item.ariaProps}>
    <span className="nexora-toast__icon" aria-hidden="true"><Icon size={18} /></span>
    <div className="nexora-toast__content"><div dir="auto">{children}</div></div>
    <button type="button" className="nexora-toast__close" aria-label={fa ? `بستن پیام ${label}` : `Dismiss ${label}`} onClick={onDismiss}><X size={15} /></button>
  </article>;
}
