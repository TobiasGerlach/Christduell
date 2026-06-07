import { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { Duel, duelsApi } from "../api/duels";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "DuelsList">;

// TODO: replace with the authenticated player's id once login lands.
const CURRENT_PLAYER_ID = 1;

export function DuelsListScreen({ navigation }: Props) {
  const [duels, setDuels] = useState<Duel[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadDuels = useCallback(async () => {
    try {
      setError(null);
      setDuels(await duelsApi.listForPlayer(CURRENT_PLAYER_ID));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load duels");
    }
  }, []);

  useEffect(() => {
    loadDuels();
  }, [loadDuels]);

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={duels}
        keyExtractor={(duel) => String(duel.id)}
        contentContainerStyle={styles.list}
        ListEmptyComponent={<Text style={styles.empty}>No duels yet — challenge a friend!</Text>}
        renderItem={({ item }) => (
          <Pressable
            style={styles.card}
            onPress={() => navigation.navigate("Duel", { duelId: item.id })}
          >
            <Text style={styles.cardTitle}>Duel #{item.id}</Text>
            <Text style={styles.cardSubtitle}>
              {item.challenger_score} – {item.opponent_score} · {item.status}
            </Text>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  list: { gap: 12 },
  card: {
    backgroundColor: "#F4F1FB",
    borderRadius: 12,
    padding: 16,
  },
  cardTitle: { fontSize: 16, fontWeight: "600" },
  cardSubtitle: { marginTop: 4, color: "#5B5B5B" },
  empty: { textAlign: "center", marginTop: 48, color: "#5B5B5B" },
  error: { color: "#B00020", marginBottom: 12 },
});
