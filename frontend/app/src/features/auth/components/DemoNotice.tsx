import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { authService } from "../api/authService";

export default function DemoNotice() {
  const { i18n } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const [limit, setLimit] = useState<number | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    authService.demoStatus(controller.signal).then(value => setLimit(value.question_limit)).catch(() => {});
    return () => controller.abort();
  }, []);
  return <aside dir={isFa ? "rtl" : "ltr"} className="relative z-20 shrink-0 border-b px-4 py-2 text-center text-xs leading-6" style={{ background: "var(--surface-panel)", borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}>
    <strong style={{ color: "var(--brand-action)" }}>{isFa ? "دموی زنده" : "Live demo"}</strong>
    {isFa ? ` · پاسخ واقعی از اسناد نمونه${limit ? ` · سقف ${limit.toLocaleString("fa")} درخواست پاسخ در هر نشست` : ""}. اطلاعات شخصی وارد نکنید.` : ` · Real answers from sample documents${limit ? ` · Up to ${limit} answer requests per session` : ""}. Please avoid personal information.`}
  </aside>;
}
