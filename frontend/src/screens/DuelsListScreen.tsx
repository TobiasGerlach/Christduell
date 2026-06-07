import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { DuelSummary, duelsApi } from "../api/duels";
import { PlayerProfile, playersApi } from "../api/players";
import { CURRENT_PLAYER_ID } from "../currentPlayer";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "DuelsList">;

// The seed data ships exactly two test players (Anna #1, Tobias #2) — pick
// "the other one" as the sparring partner for ad-hoc test duels.
const TEST_OPPONENT_ID = CURRENT_PLAYER_ID === 1 ? 2 : 1;

function scoreLineFor(duel: DuelSummary): string {
  const isChallenger = duel.challenger_id === CURRENT_PLAYER_ID;
  const ownScore = isChallenger ? duel.challenger_score : duel.opponent_score;
  const opponentScore = isChallenger ? duel.opponent_score : duel.challenger_score;
  return `${ownScore} – ${opponentScore} · ${duel.status}`;
}

export function DuelsListScreen({ navigation }: Props) {
  const [duels, setDuels] = useState<DuelSummary[]>([]);
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [duelsResult, profileResult] = await Promise.all([
        duelsApi.listForPlayer(CURRENT_PLAYER_ID),
        playersApi.getProfile(CURRENT_PLAYER_ID),
      ]);
      setDuels(duelsResult);
      setProfile(profileResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load duels");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const unsubscribe = navigation.addListener("focus", load);
    return unsubscribe;
  }, [navigation, load]);

  const startTestDuel = useCallback(async () => {
    setCreating(true);
    try {
      setError(null);
      await duelsApi.create(CURRENT_PLAYER_ID, TEST_OPPONENT_ID);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start duel");
    } finally {
      setCreating(false);
    }
  }, [load]);

  return (
    <View style={styles.container}>
      {profile && (
        <View style={styles.profileBadge}>
          <Text style={styles.profileName}>{profile.display_name}</Text>
          <Text style={styles.profileRank}>
            {profile.rank} · {Math.round(profile.rating)}
          </Text>
        </View>
      )}

      <Pressable style={styles.startButton} onPress={startTestDuel} disabled={creating}>
        {creating ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.startButtonLabel}>Testduell starten</Text>
        )}
      </Pressable>

      {error && <Text style={styles.error}>{error}</Text>}

      <FlatList
        data={duels}
        keyExtractor={(duel) => String(duel.id)}
        contentContainerStyle={styles.list}
        ListEmptyComponent={<Text style={styles.empty}>Noch keine Duelle — starte eines!</Text>}
        renderItem={({ item }) => (
          <Pressable
            style={styles.card}
            onPress={() => navigation.navigate("Duel", { duelId: item.id })}
          >
            <Text style={styles.cardTitle}>Duell #{item.id}</Text>
            <Text style={styles.cardSubtitle}>{scoreLineFor(item)}</Text>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  profileBadge: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#EDE7F6",
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  profileName: { fontSize: 16, fontWeight: "700" },
  profileRank: { color: "#5B5B5B" },
  startButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    marginBottom: 16,
  },
  startButtonLabel: { color: "#FFFFFF", fontWeight: "600" },
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
