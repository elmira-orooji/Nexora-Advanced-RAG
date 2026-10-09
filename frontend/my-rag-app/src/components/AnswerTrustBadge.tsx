import { CheckCircle2, HelpCircle, ShieldAlert, SplitSquareHorizontal } from "lucide-react";
import type { AnswerBasis } from "../types/chat";

type TrustState = "sources" | "general" | "hybrid" | "insufficient";

interface AnswerTrustBadgeProps {
  answerBasis?: AnswerBasis | null;
  grounded?: boolean | null;
  sourceCount?: number;
  isFa: boolean;
  compact?: boolean;
  onOpenSources?: () => void;
}

export function resolveAnswerTrust(answerBasis?: AnswerBasis | null, grounded?: boolean | null, sourceCount = 0): TrustState {
  if (answerBasis === "hybrid") return "hybrid";
  if (answerBasis === "general") return "general";
  if (answerBasis === "sources") return sourceCount > 0 || grounded ? "sources" : "insufficient";
  if (sourceCount > 0 || grounded) return "sources";
  return "insufficient";
}

export default function AnswerTrustBadge({ answerBasis, grounded, sourceCount = 0, isFa, compact = false, onOpenSources }: AnswerTrustBadgeProps) {
  const state = resolveAnswerTrust(answerBasis, grounded, sourceCount);
  const copy = {
    sources: {
      label: isFa ? "پاسخ مستند" : "Source-grounded",
      detail: isFa ? `${sourceCount} منبع قابل بررسی` : `${sourceCount} verifiable ${sourceCount === 1 ? "source" : "sources"}`,
      icon: CheckCircle2,
    },
    hybrid: {
      label: isFa ? "پاسخ ترکیبی" : "Hybrid answer",
      detail: isFa ? "فقط بخش‌های ارجاع‌دار مستند هستند" : "Only cited claims are source-backed",
      icon: SplitSquareHorizontal,
    },
    general: {
      label: isFa ? "دانش عمومی مدل" : "General model answer",
      detail: isFa ? "به اسناد سازمانی متصل نیست" : "Not grounded in workspace documents",
      icon: HelpCircle,
    },
    insufficient: {
      label: isFa ? "منبع کافی پیدا نشد" : "Insufficient sources",
      detail: isFa ? "پاسخ مستند قابل تولید نبود" : "No grounded answer could be produced",
      icon: ShieldAlert,
    },
  }[state];
  const Icon = copy.icon;

  const content = <><Icon size={compact ? 12 : 14} /><span>{copy.label}</span>{!compact && state !== "insufficient" && <small>{copy.detail}</small>}</>;
  const className = `answer-trust-badge is-${state}${compact ? " is-compact" : ""}`;
  if (state === "sources" && onOpenSources) return <button type="button" className={`${className} is-actionable`} onClick={onOpenSources} aria-label={isFa ? "مشاهده منابع پاسخ مستند" : "View sources for this grounded answer"}>{content}</button>;
  return <div className={className} role="status" aria-label={`${copy.label}. ${copy.detail}`} title={copy.detail}>
    {content}
  </div>;
}
