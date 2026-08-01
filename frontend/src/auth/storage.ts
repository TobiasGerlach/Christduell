import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

import { currentDevPlayer } from "./devPlayers";

/**
 * Namespaced by the `?player=` demo account when one is in play, so two browser
 * tabs on the same origin can hold two different sessions at once. Without a
 * dev player it is a single plain key, exactly as in a released build.
 */
function tokenKey(): string {
  const devPlayer = currentDevPlayer();
  return devPlayer ? `christduell.accessToken.${devPlayer}` : "christduell.accessToken";
}

/**
 * Token storage. Native builds use the OS keychain via expo-secure-store, which
 * has no web implementation — there the token goes to localStorage instead.
 */
export async function saveToken(token: string): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.setItem(tokenKey(), token);
    return;
  }
  await SecureStore.setItemAsync(tokenKey(), token);
}

export async function loadToken(): Promise<string | null> {
  if (Platform.OS === "web") {
    return window.localStorage.getItem(tokenKey());
  }
  return SecureStore.getItemAsync(tokenKey());
}

export async function clearToken(): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.removeItem(tokenKey());
    return;
  }
  await SecureStore.deleteItemAsync(tokenKey());
}
