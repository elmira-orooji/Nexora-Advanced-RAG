import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Eye, EyeOff, KeyRound, Languages, LoaderCircle, Moon, Palette, Sun } from "lucide-react";
import toast from "react-hot-toast";
import "../styles/settings.css";
import { sectionCopy } from "../locales/copy";
import { authService } from "../services/authService";

interface SettingsPageProps {
  theme: "light" | "dark";
  setTheme: (theme: "light" | "dark") => void;
}

type PasswordFieldKey = "current" | "new" | "confirm";

export default function SettingsPage({ theme, setTheme }: SettingsPageProps) {
  const { i18n, t } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const copy = sectionCopy(t, "settings", ["title", "subtitle", "appearance", "appearanceSub", "light", "dark", "language", "languageSub", "ltr", "rtl", "security", "securitySub", "currentPassword", "newPassword", "confirmPassword", "showPasswords", "hidePasswords", "savePassword", "savingPassword", "passwordChanged", "passwordMismatch", "passwordTooShort", "passwordRequired", "currentPasswordIncorrect"]);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [visiblePasswords, setVisiblePasswords] = useState<Record<PasswordFieldKey, boolean>>({ current: false, new: false, confirm: false });
  const [passwordError, setPasswordError] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);

  const changeLanguage = (language: "en" | "fa") => {
    void i18n.changeLanguage(language);
    localStorage.setItem("lang", language);
    document.documentElement.setAttribute("lang", language);
    document.documentElement.setAttribute("dir", language === "fa" ? "rtl" : "ltr");
  };

  const submitPassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!currentPassword) { setPasswordError(copy.passwordRequired); return; }
    if (newPassword.length < 8) { setPasswordError(copy.passwordTooShort); return; }
    if (newPassword !== confirmPassword) { setPasswordError(copy.passwordMismatch); return; }
    setPasswordError("");
    setSavingPassword(true);
    try {
      await authService.changePassword(currentPassword, newPassword);
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      toast.success(copy.passwordChanged);
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      setPasswordError(message.toLowerCase().includes("current password is incorrect") ? copy.currentPasswordIncorrect : (message || (isFa ? "تغییر رمز عبور انجام نشد. دوباره تلاش کنید." : "Password could not be changed. Please try again.")));
    } finally { setSavingPassword(false); }
  };

  return (
    <div className="preferences-page" dir={isFa ? "rtl" : "ltr"}>
      <div className="preferences-content">
        <header className="preferences-header">
          <h1>{copy.title}</h1>
          <p>{copy.subtitle}</p>
        </header>
        <section className="preferences-card" aria-labelledby="appearance-title">
          <div className="preferences-section-heading">
            <span className="preferences-icon"><Palette size={18} aria-hidden="true" /></span>
            <div><h2 id="appearance-title">{copy.appearance}</h2><p>{copy.appearanceSub}</p></div>
          </div>
          <div className="preferences-options" role="radiogroup" aria-labelledby="appearance-title">
            {(["light", "dark"] as const).map((value) => {
              const Icon = value === "light" ? Sun : Moon;
              return <label key={value} className="preferences-choice">
                <input type="radio" name="appearance" value={value} checked={theme === value} onChange={() => setTheme(value)} />
                <span className={`preferences-preview preferences-preview--${value}`} aria-hidden="true">
                  <span className="preferences-preview-sidebar"><i /><i /><i /></span>
                  <span className="preferences-preview-body"><i /><span><i /><i /></span><i /></span>
                </span>
                <span className="preferences-choice-footer"><Icon size={16} aria-hidden="true" /><span>{copy[value]}</span><span className="preferences-check" aria-hidden="true">{theme === value && <Check size={12} />}</span></span>
              </label>;
            })}
          </div>
        </section>
        <section className="preferences-card" aria-labelledby="language-title">
          <div className="preferences-section-heading">
            <span className="preferences-icon"><Languages size={18} aria-hidden="true" /></span>
            <div><h2 id="language-title">{copy.language}</h2><p>{copy.languageSub}</p></div>
          </div>
          <div className="preferences-options" role="radiogroup" aria-labelledby="language-title">
            {(["en", "fa"] as const).map((language) => {
              const active = language === "fa" ? isFa : !isFa;
              return <label key={language} className="preferences-choice preferences-language">
                <input type="radio" name="language" value={language} checked={active} onChange={() => changeLanguage(language)} />
                <span className="preferences-language-symbol" aria-hidden="true">{language === "fa" ? "فا" : "En"}</span>
                <span className="preferences-language-copy"><strong lang={language}>{language === "fa" ? "فارسی" : "English"}</strong><span>{language === "fa" ? copy.rtl : copy.ltr}</span></span>
                <span className="preferences-check" aria-hidden="true">{active && <Check size={12} />}</span>
              </label>;
            })}
          </div>
        </section>
        <section className="preferences-card" aria-labelledby="password-title">
          <div className="preferences-section-heading">
            <span className="preferences-icon"><KeyRound size={18} aria-hidden="true" /></span>
            <div><h2 id="password-title">{copy.security}</h2><p>{copy.securitySub}</p></div>
          </div>
          <form className="preferences-password-form" onSubmit={(event) => void submitPassword(event)} noValidate>
            <div className="preferences-password-fields">
              {([
                { key: "current", label: copy.currentPassword, value: currentPassword, autoComplete: "current-password", setValue: setCurrentPassword },
                { key: "new", label: copy.newPassword, value: newPassword, autoComplete: "new-password", setValue: setNewPassword },
                { key: "confirm", label: copy.confirmPassword, value: confirmPassword, autoComplete: "new-password", setValue: setConfirmPassword },
              ] as const).map((field) => {
                const visible = visiblePasswords[field.key];
                const fieldId = `settings-password-${field.key}`;
                return <div className="preferences-password-field" key={field.key}>
                  <label htmlFor={fieldId}>{field.label}</label>
                  <div className="preferences-password-input-wrap">
                    <input id={fieldId} value={field.value} onChange={(event) => { field.setValue(event.target.value); setPasswordError(""); }} type={visible ? "text" : "password"} autoComplete={field.autoComplete} disabled={savingPassword} />
                    <button type="button" className="preferences-password-visibility" onClick={() => setVisiblePasswords((current) => ({ ...current, [field.key]: !current[field.key] }))} aria-label={`${visible ? copy.hidePasswords : copy.showPasswords}: ${field.label}`} aria-pressed={visible} disabled={savingPassword}>
                      {visible ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
                    </button>
                  </div>
                </div>;
              })}
            </div>
            {passwordError && <p className="preferences-password-error" role="alert">{passwordError}</p>}
            <button className="preferences-password-submit" type="submit" disabled={savingPassword}>{savingPassword && <LoaderCircle className="animate-spin" size={15} aria-hidden="true" />}{savingPassword ? copy.savingPassword : copy.savePassword}</button>
          </form>
        </section>
      </div>
    </div>
  );
}
