import {
  BrowserRouter,
  Routes,
  Route,
} from "react-router-dom";

import LoginPage from "./pages/LoginPage";
import GuestRoute from "./components/GuestRoute";
import ProtectedRoute from "./components/ProtectedRoute";
import ErrorBoundary from "./components/ErrorBoundary";
import { lazy, Suspense, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { AUTH_EXPIRED_EVENT } from "./services/apiClient";

const AppLayout = lazy(() => import("./layouts/AppLayout"));
const SharedChatPage = lazy(() => import("./pages/SharedChatPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function RouteFallback() {
  return <div className="nexora-page grid min-h-[100dvh] place-items-center" role="status" aria-label="Loading page">
    <span className="nexora-loader" />
  </div>;
}

function SessionExpiryHandler() {
  const navigate = useNavigate();
  const location = useLocation();
  const { i18n } = useTranslation();

  useEffect(() => {
    const handleExpiry = () => {
      navigate("/", { replace: true, state: { reason: "session-expired" } });
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, handleExpiry);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpiry);
  }, [i18n.language, location.pathname, navigate]);

  return null;
}


export default function App() {
  
    const { i18n } = useTranslation();

  useEffect(() => {
    document.documentElement.dir =
      i18n.language === "fa"
        ? "rtl"
        : "ltr";
  }, [i18n.language]);

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <SessionExpiryHandler />
        <Routes>
          <Route
            path="/"
            element={<GuestRoute><LoginPage /></GuestRoute>}
          />

          <Route
            path="/home/*"
            element={<ProtectedRoute><ErrorBoundary><Suspense fallback={<RouteFallback />}><AppLayout /></Suspense></ErrorBoundary></ProtectedRoute>}
          />
          <Route path="/share/:visibility/:token" element={<ErrorBoundary><Suspense fallback={<RouteFallback />}><SharedChatPage /></Suspense></ErrorBoundary>} />
          <Route path="*" element={<Suspense fallback={<RouteFallback />}><NotFoundPage /></Suspense>} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
