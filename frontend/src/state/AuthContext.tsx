import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { auth as authApi } from "@/api/authClient";
import type { CurrentUser } from "@/api/types";

/**
 * Phase 21 — who's signed in, app-wide. Backed by the httpOnly session
 * cookie the backend sets on login/signup; this context just reflects it
 * (via GET /api/v1/auth/me) so any screen can read the current user without
 * re-fetching it itself.
 */
interface AuthContextValue {
  user: CurrentUser | null;
  /** True only while the initial /me check on page load is in flight. */
  loading: boolean;
  /** Re-checks /me — call after signup/login to pick up the new session. */
  refresh: () => Promise<void>;
  setUser: (user: CurrentUser) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setUser(await authApi.me());
    } catch {
      // 401 ("not signed in") is the expected, non-error steady state here —
      // any failure just means there's no one to show as logged in.
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    await authApi.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, refresh, setUser, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
