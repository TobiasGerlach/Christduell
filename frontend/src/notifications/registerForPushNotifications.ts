import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { api } from "../api/client";

/**
 * Asks for notification permission, fetches an Expo push token, and registers
 * it with the backend so duel alerts ("Du bist dran!") can be delivered to the
 * logged-in player. Requires an authenticated session — call it after login.
 *
 * Returns null on simulators/emulators, on web, or if the user declines
 * permission: push tokens require a physical device.
 */
export async function registerForPushNotifications(): Promise<string | null> {
  if (Platform.OS === "web") {
    return null;
  }

  if (!Device.isDevice) {
    console.warn("Push notifications require a physical device");
    return null;
  }

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("default", {
      name: "default",
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let status = existingStatus;
  if (status !== "granted") {
    ({ status } = await Notifications.requestPermissionsAsync());
  }
  if (status !== "granted") {
    console.warn("Push notification permission was not granted");
    return null;
  }

  const projectId = Constants.expoConfig?.extra?.eas?.projectId;
  const { data: pushToken } = await Notifications.getExpoPushTokenAsync(
    projectId ? { projectId } : undefined,
  );

  await api.post("/notifications/register-token", { push_token: pushToken });

  return pushToken;
}
