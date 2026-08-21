import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { DuelStateResponse, duelsApi } from "../api/duels";
import { useAccount } from "../auth/AuthContext";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "Duel">;

// Lightweight bridge while a push notification is the real mechanism: refresh
// the state while we are waiting on the opponent, so their move shows up
// without the player pulling to refresh.
const POLL_INTERVAL_MS = 8000;

export function DuelScreen({ route, navigation }: Props) {
  const { duelId } = route.params;
  const account = useAccount();
  const [state, setState] = useState<DuelStateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setState(await duelsApi.getState(duelId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load duel");
    }
  }, [duelId]);

  // Only poll while the opponent could actually change something. On a finished
  // duel, or while it is our own turn, nothing moves without us — polling then
  // is battery and mobile data spent on an answer we already have.
  const waitingForOpponent =
    state !== null && state.action !== "finished" && state.acting_player_id !== account.id;

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!waitingForOpponent) return;
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load, waitingForOpponent]);

  useEffect(() => {
    const unsubscribe = navigation.addListener("focus", load);
    return unsubscribe;
  }, [navigation, load]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (!state) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  const isMyTurn = state.acting_player_id === account.id;
  const isChallenger = state.challenger_id === account.id;
  const ownScore = isChallenger ? state.challenger_score : state.opponent_score;
  const otherScore = isChallenger ? state.opponent_score : state.challenger_score;
  const opponentName = isChallenger
    ? state.opponent_display_name
    : state.challenger_display_name;
  const leading = ownScore > otherScore ? "own" : ownScore < otherScore ? "other" : null;

  return (
    <View style={styles.container}>
      <View style={styles.scoreboard}>
        <View style={styles.scoreSide}>
          <Text style={styles.scoreName}>Du</Text>
          <Text style={[styles.score, leading === "own" && styles.scoreLeading]}>{ownScore}</Text>
        </View>
        <Text style={styles.scoreColon}>:</Text>
        <View style={styles.scoreSide}>
          <Text style={styles.scoreName} numberOfLines={1}>
            {opponentName}
          </Text>
          <Text style={[styles.score, leading === "other" && styles.scoreLeading]}>
            {otherScore}
          </Text>
        </View>
      </View>

      {state.action === "finished" && (
        <>
          <Text style={styles.status}>DUELL BEENDET</Text>
          <Pressable style={styles.actionButton} onPress={() => navigation.popToTop()}>
            <Text style={styles.actionButtonLabel}>Zurück zur Übersicht</Text>
          </Pressable>
        </>
      )}

      {state.action === "pick_category" && isMyTurn && (
        <Pressable
          style={styles.actionButton}
          onPress={() =>
            navigation.navigate("CategoryPicker", {
              duelId,
              roundSequence: state.round_sequence ?? 1,
            })
          }
        >
          <Text style={styles.actionButtonLabel}>Kategorie wählen</Text>
        </Pressable>
      )}

      {state.action === "answer_question" && isMyTurn && state.round_id != null && state.position != null && (
        <Pressable
          style={styles.actionButton}
          onPress={() =>
            navigation.navigate("PlayQuestion", {
              duelId,
              roundId: state.round_id as number,
              position: state.position as number,
            })
          }
        >
          <Text style={styles.actionButtonLabel}>Frage {state.position} von 3 beantworten</Text>
        </Pressable>
      )}

      {state.action !== "finished" && !isMyTurn && (
        <View style={styles.waiting}>
          <ActivityIndicator />
          <Text style={styles.status}>Warte auf den Gegner …</Text>
        </View>
      )}

      <Pressable
        style={styles.historyButton}
        onPress={() => navigation.navigate("DuelHistory", { duelId })}
      >
        <Text style={styles.historyButtonLabel}>Verlauf ansehen</Text>
      </Pressable>

      {state.action !== "finished" && (
        <Pressable onPress={() => navigation.popToTop()}>
          <Text style={styles.overviewLink}>Zur Übersicht</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", gap: 16, padding: 24 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  waiting: { alignItems: "center", gap: 8 },
  scoreboard: { flexDirection: "row", alignItems: "flex-end", gap: 20 },
  scoreSide: { alignItems: "center", gap: 4, maxWidth: 130 },
  scoreName: { color: "#5B5B5B", fontSize: 14, fontWeight: "600" },
  score: { fontSize: 40, fontWeight: "700" },
  scoreColon: { fontSize: 32, fontWeight: "700", color: "#9A9A9A", paddingBottom: 2 },
  scoreLeading: { color: "#2E7D32" },
  overviewLink: { color: "#6750A4", fontWeight: "600", marginTop: 4 },
  status: { color: "#5B5B5B", letterSpacing: 1 },
  actionButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 24,
  },
  actionButtonLabel: { color: "#FFFFFF", fontWeight: "600", fontSize: 16 },
  historyButton: { marginTop: 8 },
  historyButtonLabel: { color: "#6750A4", fontWeight: "600" },
  error: { color: "#B00020" },
});
