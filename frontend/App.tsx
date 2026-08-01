import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";

import { AuthProvider } from "./src/auth/AuthContext";
import { DevPlayerSwitcher } from "./src/components/DevPlayerSwitcher";
import { RootNavigator } from "./src/navigation/RootNavigator";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export default function App() {
  // Push tokens are registered from AuthContext once a player is signed in —
  // an anonymous device has no player row to attach a token to.
  return (
    <AuthProvider>
      <RootNavigator />
      {/* Local-only: renders nothing outside a web development build. */}
      <DevPlayerSwitcher />
      <StatusBar style="auto" />
    </AuthProvider>
  );
}
