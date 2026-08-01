import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { CategoryRecommendation, duelsApi } from "../api/duels";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "CategoryPicker">;

export function CategoryPickerScreen({ route, navigation }: Props) {
  const { duelId, roundSequence } = route.params;
  const [recommendations, setRecommendations] = useState<CategoryRecommendation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [picking, setPicking] = useState<string | null>(null);
  // Tracked separately from the list: "still loading" and "nothing to offer"
  // look identical otherwise, and the empty case used to spin forever.
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRecommendations(await duelsApi.getRecommendations(duelId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kategorien konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }, [duelId]);

  useEffect(() => {
    load();
  }, [load]);

  const pick = useCallback(
    async (category: string) => {
      if (picking) return;
      setPicking(category);
      try {
        setError(null);
        const state = await duelsApi.pickCategory(duelId, category);
        if (state.round_id != null) {
          navigation.replace("PlayQuestion", { duelId, roundId: state.round_id, position: 1 });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to pick category");
        setPicking(null);
      }
    },
    [duelId, navigation, picking],
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  if (error || recommendations.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>
          {error ?? "Zurzeit sind keine Kategorien verfügbar."}
        </Text>
        <Pressable style={styles.retry} onPress={load}>
          <Text style={styles.retryLabel}>Erneut versuchen</Text>
        </Pressable>
        <Pressable onPress={() => navigation.goBack()}>
          <Text style={styles.back}>Zurück zum Duell</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Runde {roundSequence} von 8 — wähle eine Kategorie</Text>
      {recommendations.map((rec) => (
        <Pressable
          key={rec.category}
          style={styles.option}
          onPress={() => pick(rec.category)}
          disabled={picking !== null}
        >
          {picking === rec.category ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.optionLabel}>{rec.display_name}</Text>
          )}
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, gap: 16, justifyContent: "center" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 16, padding: 24 },
  retry: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 24,
  },
  retryLabel: { color: "#FFFFFF", fontWeight: "600" },
  back: { color: "#6750A4" },
  heading: { fontSize: 18, fontWeight: "600", textAlign: "center", marginBottom: 8 },
  option: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 18,
    alignItems: "center",
  },
  optionLabel: { color: "#FFFFFF", fontWeight: "600", fontSize: 16 },
  error: { color: "#B00020", textAlign: "center" },
});
