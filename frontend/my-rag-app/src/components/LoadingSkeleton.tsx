import { useTranslation } from "react-i18next";
import "../styles/skeleton.css";

export default function LoadingSkeleton({ variant = "cards", label }: { variant?: "cards" | "rows" | "page"; label?: string }) {
  const { i18n } = useTranslation();
  return <div className={`loading-skeleton loading-skeleton--${variant}`} role="status" aria-label={label || (i18n.language.startsWith("fa") ? "در حال بارگذاری…" : "Loading…")}>
    {Array.from({ length: variant === "rows" ? 5 : 3 }, (_, index) => <div className="skeleton-card" key={index} aria-hidden="true">
      <div className="skeleton-block skeleton-cover" />
      <div className="skeleton-body"><div className="skeleton-block skeleton-avatar" /><div className="skeleton-lines"><div className="skeleton-block skeleton-line" /><div className="skeleton-block skeleton-line skeleton-line--short" /></div></div>
    </div>)}
  </div>;
}
