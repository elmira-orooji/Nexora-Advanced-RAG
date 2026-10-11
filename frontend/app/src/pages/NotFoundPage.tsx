import { ArrowLeft, Home, SearchX } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { authService } from "../features/auth/api/authService";

export default function NotFoundPage() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const authenticated = authService.isAuthenticated();
  const fa = (i18n.resolvedLanguage ?? i18n.language ?? "en").startsWith("fa");

  return <main dir={fa ? "rtl" : "ltr"} className="nexora-page relative grid min-h-[100dvh] overflow-hidden px-5 py-12">
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <div className="absolute left-1/2 top-1/2 size-[34rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#7c27ff]/15 blur-[140px]" />
      <div className="app-grid absolute inset-0 opacity-40" />
    </div>
    <section className="nexora-surface relative z-10 m-auto w-full max-w-lg p-7 text-center backdrop-blur-xl sm:p-10" aria-labelledby="not-found-title">
      <img src="/brand/nexora-symbol.svg" alt="" className="mx-auto size-11" />
      <span className="mx-auto mt-8 grid size-14 place-items-center rounded-2xl border border-[#c43cff]/20 bg-[#7c27ff]/15 text-[#d9a6ff]" aria-hidden="true"><SearchX size={24} /></span>
      <p className="mt-5 text-xs font-semibold uppercase tracking-[.18em] text-[var(--brand)]">{t("notFound.eyebrow")}</p>
      <h1 id="not-found-title" className="mt-2 text-2xl font-semibold tracking-[-.03em] text-[var(--text-primary)] sm:text-3xl">{t("notFound.title")}</h1>
      <p className="mx-auto mt-3 max-w-sm text-sm leading-7 text-[var(--text-muted)]">{t("notFound.description")}</p>
      <code dir="ltr" className="mx-auto mt-5 block max-w-full overflow-hidden text-ellipsis whitespace-nowrap rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-raised)] px-3 py-2 text-xs text-[var(--text-subtle)]">{location.pathname}</code>
      <div className="mt-7 flex flex-col justify-center gap-2 sm:flex-row">
        <Link to={authenticated ? "/home" : "/"} className="nexora-action nexora-action--primary px-5"><Home size={15} />{authenticated ? t("notFound.home") : t("notFound.login")}</Link>
        {authenticated && <Link to="/" className="nexora-action nexora-action--secondary px-5"><ArrowLeft size={15} className={fa ? "rotate-180" : ""} />{t("notFound.login")}</Link>}
      </div>
    </section>
  </main>;
}
