import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../auth/AuthContext";
import {
  DEV_PLAYERS,
  currentDevPlayer,
  devSwitchingEnabled,
  otherDevPlayer,
  switchToDevPlayer,
} from "../auth/devPlayers";

/**
 * A local-only badge for switching between the two demo players in one click.
 * Renders nothing outside a web development build.
 */
export function DevPlayerSwitcher() {
  const { account } = useAuth();
  const active = currentDevPlayer();

  if (!devSwitchingEnabled() || active === null) return null;

  const other = otherDevPlayer(active);

  return (
    <View style={styles.container} pointerEvents="box-none">
      <View style={styles.pill}>
        <Text style={styles.label}>
          {account ? account.display_name : DEV_PLAYERS[active].label}
        </Text>
        <Pressable style={styles.button} onPress={() => switchToDevPlayer(other)}>
          <Text style={styles.buttonLabel}>→ {DEV_PLAYERS[other].label}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: "absolute", right: 16, bottom: 16 },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "#1D1B20",
    borderRadius: 999,
    paddingVertical: 8,
    paddingLeft: 14,
    paddingRight: 8,
    opacity: 0.92,
  },
  label: { color: "#FFFFFF", fontSize: 13, fontWeight: "600" },
  button: {
    backgroundColor: "#6750A4",
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  buttonLabel: { color: "#FFFFFF", fontSize: 13, fontWeight: "700" },
});
