import React, { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";

interface RouteGuardProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

export const RouteGuard: React.FC<RouteGuardProps> = ({ children, requireAdmin = false }) => {
  const { isAuthenticated, user, fetchMe, loading } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated && !user) {
      fetchMe();
    }
  }, [isAuthenticated, user, fetchMe]);

  if (loading && !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
          <p className="text-muted-foreground text-sm font-medium animate-pulse">Initializing environment...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requireAdmin && user && !user.is_admin) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
