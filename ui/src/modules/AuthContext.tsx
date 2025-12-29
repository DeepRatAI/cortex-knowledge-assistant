import React, { createContext, useContext, useEffect, useState } from "react";
import { setAuthToken } from "../services/api";

export interface AuthUser {
  id: string;
  username: string;
  user_type: "customer" | "employee" | string;
  role: string;
  dlp_level: string;
  can_access_all_subjects: boolean;
  subject_ids: string[];
}

export interface AuthState {
  token: string | null;
  user: AuthUser | null;
}

interface AuthContextValue extends AuthState {
  login: (state: AuthState) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const STORAGE_KEY = "cortex_auth_state";

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [state, setState] = useState<AuthState>(() => {
    if (typeof window === "undefined") return { token: null, user: null };
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return { token: null, user: null };
      const parsed = JSON.parse(raw) as AuthState;
      return parsed;
    } catch {
      return { token: null, user: null };
    }
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!state.token || !state.user) {
      sessionStorage.removeItem(STORAGE_KEY);
      return;
    }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const login = (next: AuthState) => {
    setState(next);
    setAuthToken(next.token);
  };

  const logout = () => {
    setState({ token: null, user: null });
    setAuthToken(null);
  };

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
