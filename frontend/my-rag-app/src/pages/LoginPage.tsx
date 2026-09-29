import { useEffect, useState } from "react";
import type { KeyboardEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { motion, useReducedMotion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  Check,
  CircleAlert,
  Eye,
  EyeOff,
  Languages,
  LoaderCircle,
  LockKeyhole,
  Moon,
  Sun,
  UserRound,
  WifiOff,
} from "lucide-react";

import { useLanguage } from "../hooks/useLanguage";
import { loginSchema } from "../schemas/loginSchema";
import type { LoginSchemaType } from "../schemas/loginSchema";
import { authService, LoginRequestError } from "../services/authService";
import { getPostLoginDestination } from "../utils/authNavigation";
import { getPreferredTheme, saveTheme, type Theme } from "../utils/theme";
import "../styles/login.css";

function loginErrorMessage(error: unknown, isRtl: boolean) {
  const requestError = error instanceof LoginRequestError ? error : null;
  const wait = requestError?.retryAfterSeconds;

  if (requestError?.status === 0) {
    return isRtl
      ? "ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی کنید و دوباره تلاش کنید."
      : "We couldn't reach the server. Check your internet connection and try again.";
  }
  if (requestError?.status === 401) {
    return isRtl
      ? "نام کاربری یا رمز عبور صحیح نیست. املای نام کاربری و زبان صفحه‌کلید را بررسی کنید."
      : "The username or password is incorrect. Check the username and your keyboard language, then try again.";
  }
  if (requestError?.status === 403) {
    return isRtl
      ? "این حساب غیرفعال است. برای فعال‌سازی با مدیر فضای کاری تماس بگیرید."
      : "This account is inactive. Contact your workspace administrator to restore access.";
  }
  if (requestError?.status === 429) {
    const waitText = wait
      ? isRtl
        ? ` حدود ${wait} ثانیه`
        : ` about ${wait} seconds`
      : isRtl ? " چند دقیقه" : " a few minutes";
    return isRtl
      ? `برای حفاظت از حساب، ورود موقتاً محدود شده است.${waitText} صبر کنید و دوباره تلاش کنید.`
      : `Sign-in is temporarily limited to protect your account. Wait${waitText} and try again.`;
  }
  if (requestError && requestError.status >= 500) {
    return isRtl
      ? "سرویس ورود موقتاً در دسترس نیست. چند دقیقه دیگر دوباره تلاش کنید."
      : "The sign-in service is temporarily unavailable. Please try again in a few minutes.";
  }
  return isRtl
    ? "ورود انجام نشد. چند لحظه دیگر دوباره تلاش کنید."
    : "We couldn't sign you in. Please try again in a moment.";
}

function fieldErrorMessage(error: string | undefined, field: "username" | "password", isRtl: boolean) {
  if (!error) return undefined;
  const messages = {
    username: isRtl
      ? { required: "نام کاربری را وارد کنید.", short: "نام کاربری باید حداقل ۳ کاراکتر باشد." }
      : { required: "Enter your username.", short: "Your username must be at least 3 characters." },
    password: isRtl
      ? { required: "رمز عبور را وارد کنید.", short: "رمز عبور باید حداقل ۸ کاراکتر باشد." }
      : { required: "Enter your password.", short: "Your password must be at least 8 characters." },
  };
  return error.toLowerCase().includes("required") ? messages[field].required : messages[field].short;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const reduceMotion = useReducedMotion();
  const { language, changeLanguage } = useLanguage();
  const { t: translate } = useTranslation();
  const [showPassword, setShowPassword] = useState(false);
  const [theme, setTheme] = useState<Theme>(getPreferredTheme);
  const [capsLock, setCapsLock] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isLoading, setIsLoading] = useState(false);
  const [serverError, setServerError] = useState(() => (location.state as { reason?: string } | null)?.reason === "session-expired" ? (language === "fa" ? "نشست شما منقضی شده است. دوباره وارد شوید." : "Your session has expired. Please sign in again.") : "");
  const [successMessage, setSuccessMessage] = useState("");
  const t = {
    username: translate("login.username"), usernamePlaceholder: translate("login.usernamePlaceholder"),
    password: translate("login.password"), passwordPlaceholder: translate("login.passwordPlaceholder"),
    remember: translate("login.remember"), loading: translate("login.loading"), success: translate("login.success"),
    changeLanguage: translate("login.changeLanguage"), showPassword: translate("login.showPassword"), hidePassword: translate("login.hidePassword"),
  };
  const isRtl = language === "fa";

  const {
    register,
    handleSubmit,
    formState: { errors },
    clearErrors,
    setFocus,
  } = useForm<LoginSchemaType>({
    resolver: zodResolver(loginSchema) as never,
    reValidateMode: "onSubmit",
    defaultValues: {
      username: "",
      password: "",
      rememberMe: false,
      organization: "default",
    },
  });
  const usernameField = register("username");
  const passwordField = register("password");

  const clearFieldFeedback = (field: "username" | "password") => {
    clearErrors(field);
    setServerError("");
    setSuccessMessage("");
  };

  useEffect(() => {
    const online = () => setIsOnline(true);
    const offline = () => setIsOnline(false);
    window.addEventListener("online", online);
    window.addEventListener("offline", offline);
    return () => {
      window.removeEventListener("online", online);
      window.removeEventListener("offline", offline);
    };
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    saveTheme(theme);
  }, [theme]);

  const updateCapsLock = (event: KeyboardEvent<HTMLInputElement>) =>
    setCapsLock(event.getModifierState("CapsLock"));

  const toggleTheme = () => {
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      return next;
    });
  };

  const onSubmit = async (data: LoginSchemaType) => {
    setServerError("");
    setSuccessMessage("");
    if (!navigator.onLine) {
      setServerError(isRtl ? "اتصال اینترنت در دسترس نیست." : "You appear to be offline.");
      return;
    }
    try {
      setIsLoading(true);
      const session = await authService.login(data);
      setSuccessMessage(t.success);
      await new Promise((resolve) => window.setTimeout(resolve, 650));
      const destination = getPostLoginDestination(location.state);
      navigate(destination, { replace: true, state: { role: session.user.role } });
    } catch (error) {
      setServerError(loginErrorMessage(error, isRtl));
      setFocus("password");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      dir="ltr"
      className={`nexora-login ${theme === "light" ? "nexora-login--light" : ""}`}
    >
      <section className="nexora-login__shell">
        <aside dir="ltr" className="nexora-login__visual" aria-label={isRtl ? "فضای دانش نکسورا" : "Nexora knowledge workspace"}>
          <img src="/assets/nexora-rag-hero-transparent-v2.png" alt="Nexora retrieval augmented generation knowledge network" />
          <div className="nexora-login__visual-shade" />
        </aside>

        <main dir={isRtl ? "rtl" : "ltr"} className="nexora-login__main" aria-labelledby="login-title">
          <div className="nexora-login__halos" aria-hidden="true">
            <span />
            <span />
          </div>
          <div className="nexora-login__toolbar">
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={isRtl ? (theme === "dark" ? "فعال‌کردن حالت روشن" : "فعال‌کردن حالت تیره") : (theme === "dark" ? "Switch to light mode" : "Switch to dark mode")}
              className="nexora-login__theme-toggle"
            >
              {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            </button>
            <button
              type="button"
              onClick={() => changeLanguage(language === "en" ? "fa" : "en")}
              aria-label={t.changeLanguage}
              className="nexora-login__language-toggle"
            >
              <Languages size={15} />
              <span>{language === "en" ? "FA" : "EN"}</span>
            </button>
          </div>

          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="nexora-login__form-wrap"
          >
            <div className="nexora-login__brand" dir="ltr">
              <img src="/brand/nexora-symbol.svg" alt="" width={42} height={42} />
              <span className="nexora-login__brand-copy">
                <span className="nexora-login__wordmark">Nexora</span>
                <span className="nexora-login__signature">by elmira</span>
              </span>
            </div>
            <header className="nexora-login__heading">
              <h1 id="login-title">{isRtl ? "خوش آمدید" : "Welcome back"}</h1>
              <p>{isRtl ? "برای ادامه، اطلاعات حساب خود را وارد کنید." : "Enter your account details to continue."}</p>
            </header>

            <form onSubmit={handleSubmit(onSubmit)} noValidate className="nexora-login__form">
              <LoginField
                id="username"
                label={t.username}
                error={
                  fieldErrorMessage(errors.username?.message, "username", isRtl)
                }
                icon={<UserRound size={17} />}
                isRtl={isRtl}
              >
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  autoFocus
                  aria-invalid={Boolean(errors.username)}
                  aria-describedby={errors.username ? "username-error" : undefined}
                  {...usernameField}
                  onChange={(event) => {
                    void usernameField.onChange(event);
                    clearFieldFeedback("username");
                  }}
                  placeholder={t.usernamePlaceholder}
                />
              </LoginField>

              <LoginField
                id="password"
                label={t.password}
                error={
                  fieldErrorMessage(errors.password?.message, "password", isRtl)
                }
                icon={<LockKeyhole size={17} />}
                isRtl={isRtl}
                trailing={
                  <button
                    type="button"
                    aria-label={showPassword ? t.hidePassword : t.showPassword}
                    aria-pressed={showPassword}
                    aria-controls="password"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => setShowPassword((current) => !current)}
                    className="nexora-login__password-toggle"
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                }
              >
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={errors.password ? "password-error" : undefined}
                  {...passwordField}
                  onChange={(event) => {
                    void passwordField.onChange(event);
                    clearFieldFeedback("password");
                  }}
                  onKeyUp={updateCapsLock}
                  onKeyDown={updateCapsLock}
                  onBlur={(event) => {
                    void passwordField.onBlur(event);
                    setCapsLock(false);
                  }}
                  placeholder={t.passwordPlaceholder}
                />
              </LoginField>

              {capsLock && (
                <p role="status" className="nexora-login__notice nexora-login__notice--warning">
                  <CircleAlert size={13} />
                  {isRtl ? "Caps Lock روشن است." : "Caps Lock is on."}
                </p>
              )}
              {!isOnline && (
                <p role="alert" className="nexora-login__notice nexora-login__notice--warning">
                  <WifiOff size={13} />
                  {isRtl ? "اتصال شبکه قطع است." : "Network connection is unavailable."}
                </p>
              )}
              {serverError && (
                <motion.p
                  initial={reduceMotion ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: reduceMotion ? 0 : 0.16 }}
                  role="alert"
                  className="nexora-login__error nexora-login__feedback"
                >
                  {serverError}
                </motion.p>
              )}
              {successMessage && (
                <motion.p
                  initial={reduceMotion ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: reduceMotion ? 0 : 0.16 }}
                  role="status"
                  aria-live="polite"
                  className="nexora-login__success nexora-login__feedback"
                >
                  <span>{successMessage}</span>
                </motion.p>
              )}

              <div className="nexora-login__options">
                <label>
                  <input type="checkbox" {...register("rememberMe")} />
                  <span className="nexora-login__checkbox"><Check size={11} /></span>
                  {t.remember}
                </label>
              </div>

              <motion.button
                whileHover={reduceMotion || isLoading ? undefined : { scale: 1.01 }}
                whileTap={reduceMotion || isLoading ? undefined : { scale: .98 }}
                transition={{ type: "spring", stiffness: 500, damping: 30, mass: .5 }}
                type="submit"
                disabled={isLoading || !isOnline}
                aria-busy={isLoading}
                className="nexora-login__submit"
              >
                {isLoading && <LoaderCircle size={18} className="nexora-login__loading-icon animate-spin" aria-hidden="true" />}
                <span>{isLoading ? t.loading : isRtl ? "ورود" : "Sign in"}</span>
              </motion.button>
            </form>

          </motion.div>
        </main>
      </section>
    </div>
  );
}

function LoginField({
  id,
  label,
  error,
  icon,
  trailing,
  isRtl,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  icon: React.ReactNode;
  trailing?: React.ReactNode;
  isRtl: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="nexora-login__field" data-invalid={Boolean(error)}>
      <label htmlFor={id}>{label}</label>
      <div className="nexora-login__control" data-has-action={Boolean(trailing)}>
        <span className="nexora-login__leading-icon" aria-hidden="true">{icon}</span>
        {children}
        {trailing && <div className={`nexora-login__trailing ${isRtl ? "is-rtl" : ""}`}>{trailing}</div>}
      </div>
      {error && (
        <p id={`${id}-error`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
