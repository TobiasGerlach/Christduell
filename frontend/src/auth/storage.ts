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

/**
 * Small non-secret values (e.g. the last celebrated ladder step). localStorage
 * on web, SecureStore on native — not because it is sensitive, but because it
 * is the one persistent store already in the bundle.
 */
export async function saveValue(key: string, value: string): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.setItem(`christduell.${key}`, value);
    return;
  }
  await SecureStore.setItemAsync(`christduell.${key.replace(/[^A-Za-z0-9._-]/g, "_")}`, value);
}

export async function loadValue(key: string): Promise<string | null> {
  if (Platform.OS === "web") {
    return window.localStorage.getItem(`christduell.${key}`);
  }
  return SecureStore.getItemAsync(`christduell.${key.replace(/[^A-Za-z0-9._-]/g, "_")}`);
}
