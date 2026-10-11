import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { LoaderCircle, Pencil, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { ConversationSummary } from "../api/conversationService";

const MAX_TITLE_LENGTH = 200;
const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface RenameConversationDialogProps {
  conversation: ConversationSummary;
  onClose: () => void;
  onRename: (title: string) => Promise<void>;
}

export default function RenameConversationDialog({ conversation, onClose, onRename }: RenameConversationDialogProps) {
  const { i18n, t } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const titleId = useId();
  const descriptionId = useId();
  const errorId = useId();
  const dialogRef = useRef<HTMLFormElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState(conversation.title);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    inputRef.current?.focus();
    inputRef.current?.select();
    return () => previouslyFocused?.focus();
  }, []);

  const close = () => {
    if (!saving) onClose();
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const normalizedTitle = title.trim();
    if (!normalizedTitle) {
      setError(t("conversationRename.required"));
      inputRef.current?.focus();
      return;
    }
    if (normalizedTitle.length > MAX_TITLE_LENGTH) {
      setError(t("conversationRename.tooLong", { count: MAX_TITLE_LENGTH }));
      inputRef.current?.focus();
      return;
    }
    if (normalizedTitle === conversation.title) {
      onClose();
      return;
    }

    setError("");
    setSaving(true);
    try {
      await onRename(normalizedTitle);
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : t("conversationRename.failed"));
      setSaving(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return createPortal(
    <div className="app-shell nexora-modal-backdrop fixed inset-0 z-[100] grid place-items-center p-4" dir={isFa ? "rtl" : "ltr"} onMouseDown={close}>
      <form
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        onSubmit={(event) => void submit(event)}
        onKeyDown={handleKeyDown}
        onMouseDown={(event) => event.stopPropagation()}
        className="app-glass-panel w-full max-w-md rounded-[24px] border border-white/10 bg-[#0c1732]/95 p-5 shadow-[0_30px_90px_rgba(0,0,0,.48)]"
      >
        <header className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-[#7c27ff]/20 text-[#d9a6ff]" aria-hidden="true"><Pencil size={17} /></span>
            <div>
              <h2 id={titleId} className="text-sm font-semibold text-white">{t("conversationRename.title")}</h2>
              <p id={descriptionId} className="mt-1 text-xs leading-5 text-white/45">{t("conversationRename.description")}</p>
            </div>
          </div>
          <button type="button" onClick={close} disabled={saving} aria-label={t("conversationRename.close")} className="app-icon-button grid size-9 shrink-0 place-items-center rounded-xl disabled:opacity-40"><X size={16} /></button>
        </header>

        <label htmlFor="conversation-title" className="mt-6 block text-xs font-medium text-white/65">{t("conversationRename.label")}</label>
        <input
          ref={inputRef}
          id="conversation-title"
          value={title}
          maxLength={MAX_TITLE_LENGTH + 1}
          disabled={saving}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : descriptionId}
          onChange={(event) => { setTitle(event.target.value); setError(""); }}
          className="mt-2 h-12 w-full rounded-xl border border-white/10 bg-black/20 px-4 text-sm text-white outline-none transition focus:border-[#9b6cff] focus:ring-4 focus:ring-[#7c27ff]/15 disabled:opacity-50"
        />
        <div className="mt-2 flex min-h-5 items-start justify-between gap-3 text-xs">
          <span id={errorId} role={error ? "alert" : undefined} className="text-rose-300">{error}</span>
          <span aria-hidden="true" className="shrink-0 text-white/30">{title.length.toLocaleString(isFa ? "fa" : "en")} / {MAX_TITLE_LENGTH.toLocaleString(isFa ? "fa" : "en")}</span>
        </div>

        <footer className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={close} disabled={saving} className="rounded-xl border border-white/10 px-4 py-2.5 text-xs font-semibold text-white/60 transition hover:bg-white/[.06] disabled:opacity-40">{t("conversationRename.cancel")}</button>
          <button type="submit" disabled={saving || !title.trim()} className="flex min-w-24 items-center justify-center gap-2 rounded-xl bg-[#7c27ff] px-4 py-2.5 text-xs font-semibold text-white shadow-[0_10px_30px_rgba(124,39,255,.25)] transition hover:bg-[#8b3dff] disabled:cursor-not-allowed disabled:opacity-45">
            {saving && <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />}
            {saving ? t("conversationRename.saving") : t("conversationRename.save")}
          </button>
        </footer>
      </form>
    </div>,
    document.body,
  );
}
