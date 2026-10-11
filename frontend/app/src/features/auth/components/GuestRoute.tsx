import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { authService } from "../api/authService";
import { getPostLoginDestination } from "../../../lib/authNavigation";

export default function GuestRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (authService.isAuthenticated()) {
    const destination = getPostLoginDestination(location.state);
    return <Navigate to={destination} replace />;
  }

  return children;
}
