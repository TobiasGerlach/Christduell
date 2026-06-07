import { useEffect } from "react";
import { StatusBar } from "expo-status-bar";
import * as Notifications from "expo-notifications";

import { CURRENT_PLAYER_ID } from "./src/currentPlayer";
import { RootNavigator } from "./src/navigation/RootNavigator";
import { registerForPushNotifications } from "./src/notifications/registerForPushNotifications";

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
