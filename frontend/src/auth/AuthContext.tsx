import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { Account, authApi } from "../api/auth";
import { api, setAccessToken, setUnauthorizedHandler } from "../api/client";
import { registerForPushNotifications } from "../notifications/registerForPushNotifications";
import { DEV_PASSWORD, DEV_PLAYERS, currentDevPlayer } from "./devPlayers";
import { clearToken, loadToken, saveToken } from "./storage";

interface AuthValue {
  account: Account | null;
  /** True until the stored token has been checked — keeps the login screen from flashing. */
  initialising: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (displayName: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  deleteAccount: () => Promise<void>;
  refresh: () => Promise<void>;
  setAccount: (account: Account) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [initialising, setInitialising] = useState(true);

  const applySession = useCallback(async (token: string, player: Account) => {
    setAccessToken(token);
    await saveToken(token);
    setAccount(player);
    // Best effort: a missing push token only costs notifications, not the login.
    registerForPushNotifications().catch((err) =>
      console.warn("Push registration failed:", err),
    );
  }, []);

  const forgetSession = useCallback(async () => {
    setAccessToken(null);
    setAccount(null);
    await clearToken();
  }, []);

  // Restore a previous session on cold start.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const token = await loadToken();
      if (!token) {
        // `?player=anna` on the web dev build: sign that demo account in rather
        // than showing a login form we already know the answer to.
        const devPlayer = currentDevPlayer();
        if (devPlayer) {
          try {
            const response = await authApi.login(DEV_PLAYERS[devPlayer].email, DEV_PASSWORD);
            if (!cancelled) await applySession(response.access_token, response.player);
          } catch (error) {
            console.warn(
              `Auto-login as ${devPlayer} failed — run \`make reset-db\` to seed the demo players.`,
              error,
            );
          }
        }
        if (!cancelled) setInitialising(false);
        return;
      }
      setAccessToken(token);
      try {
        const player = await authApi.me();
        if (!cancelled) {
          setAccount(player);
          registerForPushNotifications().catch(() => undefined);
        }
      } catch {
        // Expired or revoked token — start over at the login screen.
        await forgetSession();
      } finally {
        if (!cancelled) setInitialising(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [forgetSession, applySession]);

  // A 401 from any endpoint means the session is gone; drop it everywhere at once.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      void forgetSession();
    });
    return () => setUnauthorizedHandler(null);
  }, [forgetSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await authApi.login(email, password);
      await applySession(response.access_token, response.player);
    },
    [applySession],
  );

  const register = useCallback(
    async (displayName: string, email: string, password: string) => {
      const response = await authApi.register(displayName, email, password);
      await applySession(response.access_token, response.player);
    },
    [applySession],
  );

  const logout = useCallback(async () => {
    // Stop this device from receiving duel pushes meant for the person logging out.
    await api.delete("/notifications/register-token").catch(() => undefined);
    await forgetSession();
  }, [forgetSession]);

  const deleteAccount = useCallback(async () => {
    await authApi.deleteAccount();
    await forgetSession();
  }, [forgetSession]);

  const refresh = useCallback(async () => {
    setAccount(await authApi.me());
  }, []);

  const value = useMemo(
    () => ({
      account,
      initialising,
      login,
      register,
      logout,
      deleteAccount,
      refresh,
      setAccount,
    }),
    [account, initialising, login, register, logout, deleteAccount, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return value;
}

/** For screens that only render behind the auth gate, where an account is guaranteed. */
export function useAccount(): Account {
  const { account } = useAuth();
  if (account === null) {
    throw new Error("useAccount used outside an authenticated screen");
  }
  return account;
}
