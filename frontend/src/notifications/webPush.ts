// Web Push for the browser/PWA build. The native app has its own channel
// (Expo, registerForPushNotifications); this file is web-only and no-ops
// everywhere else.

import { Platform } from "react-native";

import { api } from "../api/client";

function pushSupported(): boolean {
  return (
    Platform.OS === "web" &&
    typeof navigator !== "undefined" &&
    "serviceWorker" in navigator &&
    typeof window !== "undefined" &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/** Whether the enable-notifications banner should be offered at all. */
export async function canOfferWebPush(): Promise<boolean> {
  if (!pushSupported()) return false;
  if (Notification.permission === "denied") return false;
  if (await getSubscription()) return false;
  // Only offer if the server actually has VAPID keys configured.
  try {
    await api.get<{ public_key: string }>("/notifications/web-push/public-key");
    return true;
  } catch {
    return false;
  }
}

async function getSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.getRegistration();
  if (!registration) return null;
  return registration.pushManager.getSubscription();
}

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

/**
 * Ask for permission and register this browser with the backend. Must be
 * called from a user gesture (button tap) — Safari enforces that.
 * Returns true when the subscription is active.
 */
export async function enableWebPush(): Promise<boolean> {
  if (!pushSupported()) return false;

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return false;

  const { public_key } = await api.get<{ public_key: string }>(
    "/notifications/web-push/public-key",
  );
  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;

  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key),
    }));

  const json = subscription.toJSON();
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) return false;
  await api.post("/notifications/web-push/subscriptions", {
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
  });
  return true;
}

/** Best-effort teardown on logout so the next account doesn't get our pushes. */
export async function disableWebPush(): Promise<void> {
  if (!pushSupported()) return;
  try {
    const subscription = await getSubscription();
    if (!subscription) return;
    await api
      .delete(
        `/notifications/web-push/subscriptions?endpoint=${encodeURIComponent(subscription.endpoint)}`,
      )
      .catch(() => undefined);
    await subscription.unsubscribe();
  } catch {
    // Losing the unsubscribe is acceptable; the server also prunes dead
    // endpoints and reassigns shared browsers on the next subscribe.
  }
}
