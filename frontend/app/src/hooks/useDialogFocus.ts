import { useEffect, useRef, type KeyboardEvent } from "react";
const focusableSelector = [
    "button:not([disabled])",
    "input:not([disabled])",
    "textarea:not([disabled])",
    "select:not([disabled])",
    "a[href]",
    "[tabindex]:not([tabindex='-1'])",
].join(",");
export function useDialogFocus<T extends HTMLElement>(open: boolean, onClose: () => void) {
    const ref = useRef<T | null>(null);
    useEffect(() => {
        if (!open)
            return undefined;
        const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        const timer = window.setTimeout(() => {
            const first = ref.current?.querySelector<HTMLElement>(focusableSelector);
            (first || ref.current)?.focus();
        }, 0);
        return () => {
            window.clearTimeout(timer);
            if (previous?.isConnected)
                previous.focus();
        };
    }, [open]);
    const onKeyDown = (event: KeyboardEvent) => {
        if (event.key === "Escape") {
            event.stopPropagation();
            onClose();
            return;
        }
        if (event.key !== "Tab" || !ref.current)
            return;
        const focusable = [...ref.current.querySelectorAll<HTMLElement>(focusableSelector)].filter((item) => item.offsetParent !== null || item === document.activeElement);
        if (!focusable.length) {
            event.preventDefault();
            ref.current.focus();
            return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        }
        else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    };
    return { ref, onKeyDown };
}
