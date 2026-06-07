import { useEffect } from "react";
import { StatusBar } from "expo-status-bar";
import * as Notifications from "expo-notifications";

import { RootNavigator } from "./src/navigation/RootNavigator";
import { registerForPushNotifications } from "./src/notifications/registerForPushNotifications";

// TODO: replace with the authenticated player's id once login lands.
const CURRENT_PLAYER_ID = 1;

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export default function App() {
  useEffect(() => {
    registerForPushNotifications(CURRENT_PLAYER_ID).catch((err) =>
      console.warn("Push registration failed:", err),
    );
  }, []);

  return (
    <>
      <RootNavigator />
      <StatusBar style="auto" />
    </>
  );
}
