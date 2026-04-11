import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import type { AuthRole } from "@/lib/api";

interface ProtectedRouteProps {
  children: ReactNode;
  allowedRoles?: AuthRole[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading session...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    const fallbackRoute = user.role === "manager" ? "/dashboard" : "/settings";
    return <Navigate to={fallbackRoute} replace />;
  }

  return <>{children}</>;
}
