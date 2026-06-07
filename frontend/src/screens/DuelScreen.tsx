import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { Duel, duelsApi } from "../api/duels";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "Duel">;

export function DuelScreen({ route }: Props) {
  const { duelId } = route.params;
  const [duel, setDuel] = useState<Duel | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    duelsApi
      .get(duelId)
      .then(setDuel)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load duel"));
  }, [duelId]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (!duel) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.score}>
        {duel.challenger_score} – {duel.opponent_score}
      </Text>
      <Text style={styles.status}>{duel.status.toUpperCase()}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", gap: 8 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  score: { fontSize: 40, fontWeight: "700" },
  status: { color: "#5B5B5B", letterSpacing: 1 },
  error: { color: "#B00020" },
});
