import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { en } from "./locales/en";
import { fa } from "./locales/fa";

i18n.use(initReactI18next).init({
  lng: localStorage.getItem("lang") || "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  resources: { en: { translation: en }, fa: { translation: fa } },
});

export default i18n;
