import { useEffect, useState } from "react";
import i18n from "../i18n";

export type Language = "en" | "fa";

export function useLanguage() {
  const [language, setLanguage] = useState<Language>(() =>
    localStorage.getItem("lang") === "fa" ? "fa" : "en"
  );

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === "fa" ? "rtl" : "ltr";
    void i18n.changeLanguage(language);
  }, [language]);

  const changeLanguage = (lang: Language) => {
    setLanguage(lang);
    localStorage.setItem("lang", lang);
  };

  return {
    language,
    changeLanguage,
  };
}
