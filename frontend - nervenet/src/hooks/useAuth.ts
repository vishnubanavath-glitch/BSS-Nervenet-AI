import { useCallback } from "react";
import { useAuthStore } from "@/store/authStore";
import api from "@/lib/api";

export const useAuth = () => {
  const { user, accessToken, isAuthenticated, loading, error, setTokens, setUser, setError, logout, fetchMe } = useAuthStore();

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    setError(null);
    try {
      await api.post("/auth/register", { email, password, full_name: fullName });
      // Login automatically upon signup
      const loginRes = await api.post("/auth/login", { email, password });
      setTokens(loginRes.data.access_token, loginRes.data.refresh_token);
      const userRes = await api.get("/users/me");
      setUser(userRes.data);
      return true;
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed");
      return false;
    }
  }, [setTokens, setUser, setError]);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const loginRes = await api.post("/auth/login", { email, password });
      setTokens(loginRes.data.access_token, loginRes.data.refresh_token);
      const userRes = await api.get("/users/me");
      setUser(userRes.data);
      return true;
    } catch (err: any) {
      setError(err.response?.data?.detail || "Invalid login credentials");
      return false;
    }
  }, [setTokens, setUser, setError]);

  return {
    user,
    accessToken,
    isAuthenticated,
    loading,
    error,
    register,
    login,
    logout,
    fetchMe
  };
};
