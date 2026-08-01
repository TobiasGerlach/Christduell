import { Platform } from "react-native";

/**
 * Local convenience for playing both sides of a duel without logging in and out.
 *
 * Adding `?player=anna` or `?player=tobias` to the web build's URL signs that
 * seeded demo account in automatically, and each one keeps its own stored token
 * — so two ordinary browser tabs can be two different players at once instead of
 * fighting over the same localStorage entry.
 *
 * Development builds on web only: `__DEV__` is false in anything `eas build`
 * produces, so this cannot reach a released app.
 */

export const DEV_PLAYERS = {
  anna: { email: "anna@example.com", label: "Anna" },
  tobias: { email: "tobias@example.com", label: "Tobias" },
} as const;

export type DevPlayerKey = keyof typeof DEV_PLAYERS;

/** Matches SEED_PASSWORD in backend/app/db/seed.py. */
export const DEV_PASSWORD = "christduell-dev";

export function devSwitchingEnabled(): boolean {
  return __DEV__ && Platform.OS === "web" && typeof window !== "undefined";
}

/** The demo player named in the URL, if any. */
export function currentDevPlayer(): DevPlayerKey | null {
  if (!devSwitchingEnabled()) return null;
  const value = new URLSearchParams(window.location.search).get("player");
  // ?player=1 / ?player=2 also work — they were the old seeded ids.
  const alias: Record<string, DevPlayerKey> = { "1": "anna", "2": "tobias" };
  const key = alias[value ?? ""] ?? value;
  return key !== null && key in DEV_PLAYERS ? (key as DevPlayerKey) : null;
}

export function otherDevPlayer(key: DevPlayerKey): DevPlayerKey {
  return key === "anna" ? "tobias" : "anna";
}

/** Reloads into the other demo player's session. */
export function switchToDevPlayer(key: DevPlayerKey): void {
  const url = new URL(window.location.href);
  url.searchParams.set("player", key);
  window.location.href = url.toString();
}
