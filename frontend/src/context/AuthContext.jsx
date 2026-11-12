import React, {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authService } from "@/services/authService";
import { tokenVault } from "@/services/api";
import { useAppStore } from "@/store/useAppStore";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const pushToast = useAppStore((s) => s.pushToast);

  const [user, setUser] = useState(null);
  const [isInitializing, setIsInitializing] = useState(() =>
    Boolean(tokenVault.getAccessToken())
  );

  const clearSession = useCallback(
    (notify = false) => {
      tokenVault.clear();
      setUser(null);
      queryClient.clear();
      if (notify) {
        pushToast({
          title: "Session expired",
          description: "Please sign in again to continue.",
          variant: "warning",
        });
      }
    },
    [pushToast, queryClient]
  );

  useEffect(() => {
    tokenVault.onSessionExpired(() => {
      clearSession(true);
    });
    return () => {
      tokenVault.onSessionExpired(null);
    };
  }, [clearSession]);

  useEffect(() => {
    let active = true;
    const token = tokenVault.getAccessToken();
    if (!token) {
      setIsInitializing(false);
      return;
    }

    authService
      .getMe()
      .then((profile) => {
        if (active) setUser(profile);
      })
      .catch(() => {
        if (active) {
          tokenVault.clear();
          setUser(null);
        }
      })
      .finally(() => {
        if (active) setIsInitializing(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(
    async ({ email, password, rememberMe = false }) => {
      const res = await authService.login({ email, password, rememberMe });
      setUser(res.user);
      return res;
    },
    []
  );

  const register = useCallback(async ({ name, email, password }) => {
    const res = await authService.register({ name, email, password });
    setUser(res.user);
    return res;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch {
      // Clear local session even if backend token already expired
    } finally {
      clearSession(false);
    }
  }, [clearSession]);

  const refreshUser = useCallback(async () => {
    const profile = await authService.getMe();
    setUser(profile);
    return profile;
  }, []);

  const updateProfile = useCallback(async (payload) => {
    const updated = await authService.updateProfile(payload);
    setUser(updated);
    return updated;
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isInitializing,
      login,
      register,
      logout,
      refreshUser,
      updateProfile,
    }),
    [
      user,
      isInitializing,
      login,
      register,
      logout,
      refreshUser,
      updateProfile,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

