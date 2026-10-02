import { Component, type ErrorInfo, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { CircleAlert, RefreshCw, RotateCcw } from "lucide-react";
import "../styles/application-error.css";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return <ApplicationError error={this.state.error} onRetry={() => this.setState({ hasError: false, error: null })} />;
    }
    return this.props.children;
  }
}

function ApplicationError({ error, onRetry }: { error: Error | null; onRetry: () => void }) {
  const { i18n } = useTranslation();
  const fa = i18n.language.startsWith("fa");
  return <section className="application-error" dir={fa ? "rtl" : "ltr"} aria-labelledby="application-error-title">
    <div className="application-error-card">
      <div className="application-error-brand"><img src="/brand/nexora-symbol.svg" alt="" /><span>Nexora</span></div>
      <div className="application-error-icon"><CircleAlert size={28} aria-hidden="true" /></div>
      <p className="application-error-label">{fa ? "خطا در نمایش صفحه" : "Page could not be displayed"}</p>
      <h1 id="application-error-title">{fa ? "این صفحه درست بارگذاری نشد" : "Let’s get you back on track"}</h1>
      <p className="application-error-description">{fa ? "دوباره تلاش کنید. اگر خطا ادامه داشت، صفحه را مجدداً بارگذاری کنید." : "Try again to restore this page. If the issue continues, reload the application."}</p>
      <div className="application-error-actions">
        <button type="button" className="nexora-action nexora-action--primary" onClick={onRetry}><RotateCcw size={16} />{fa ? "تلاش دوباره" : "Try again"}</button>
        <button type="button" className="nexora-action nexora-action--secondary" onClick={() => window.location.reload()}><RefreshCw size={16} />{fa ? "بارگذاری مجدد" : "Reload page"}</button>
      </div>
      {error?.message && <details className="application-error-details"><summary>{fa ? "جزئیات فنی خطا" : "Technical details"}</summary><pre dir="ltr">{error.message}</pre></details>}
    </div>
  </section>;
}
