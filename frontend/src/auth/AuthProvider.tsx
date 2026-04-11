import { createContext, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { AuthUser, LoginInput, RegisterInput } from "@/lib/api";
import { getCurrentSession, login as loginApi, logout as logoutApi, refreshSession, register as registerApi } from "@/lib/api";

export interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<AuthUser>;
  register: (input: RegisterInput) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<boolean>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadSession = useCallback(async () => {
    try {
      const session = await getCurrentSession();
      setUser(session.authenticated ? session.user : null);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const login = useCallback(async (input: LoginInput) => {
    const result = await loginApi(input);
    setUser(result.user);
    return result.user;
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    const result = await registerApi(input);
    setUser(result.user);
    return result.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } catch {
      // Intentionally ignore logout transport failures and clear local session state.
    }
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const result = await refreshSession();
      setUser(result.user);
      return true;
    } catch {
      setUser(null);
      return false;
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, login, register, logout, refresh }),
    [user, isLoading, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
