import { create } from "zustand";
import api from "@/lib/api";

interface User {
  id: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_admin: boolean;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
  
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: User) => void;
  setError: (err: string | null) => void;
  fetchMe: () => Promise<User | null>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: localStorage.getItem("access_token"),
  refreshToken: localStorage.getItem("refresh_token"),
  isAuthenticated: !!localStorage.getItem("access_token"),
  loading: false,
  error: null,

  setTokens: (access, refresh) => {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
    set({ accessToken: access, refreshToken: refresh, isAuthenticated: true });
  },

  setUser: (user) => set({ user }),
  
  setError: (err) => set({ error: err }),

  fetchMe: async () => {
    set({ loading: true, error: null });
    try {
      const res = await api.get("/users/me");
      const user = res.data;
      set({ user, loading: false });
      return user;
    } catch (err: any) {
      set({ error: err.response?.data?.detail || "Session expired", loading: false });
      get().logout();
      return null;
    }
  },

  logout: () => {
    // Attempt backend logout if possible
    const token = get().refreshToken;
    if (token) {
      api.post("/auth/logout", { refresh_token: token }).catch(() => {});
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
  }
}));
