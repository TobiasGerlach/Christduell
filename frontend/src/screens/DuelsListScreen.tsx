import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import { DuelSummary, duelsApi } from "../api/duels";
import { QuestionnaireType, researchApi } from "../api/research";
import { useAccount } from "../auth/AuthContext";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "DuelsList">;

// The list is the de-facto home screen, so it refreshes itself: an opponent's
// move should appear without the player knowing about pull-to-refresh.
const LIST_POLL_INTERVAL_MS = 15000;

type TurnIndicator = { color: string; label: string } | null;


export function DuelsListScreen({ navigation }: Props) {
  const account = useAccount();
  const [duels, setDuels] = useState<DuelSummary[]>([]);
  const [dueQuestionnaire, setDueQuestionnaire] = useState<QuestionnaireType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [duelsResult, questionnaire] = await Promise.all([
        duelsApi.list(),
        // A pending questionnaire is not worth failing the whole screen over.
        researchApi.getCurrentQuestionnaire().catch(() => null),
      ]);
      setDuels(duelsResult);
      setDueQuestionnaire(questionnaire?.due_questionnaire ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Duelle konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => navigation.addListener("focus", load), [navigation, load]);

  useEffect(() => {
    const interval = setInterval(() => {
      // Keep polling only while this screen is the visible one; deeper screens
      // (an open duel) poll for themselves.
      if (navigation.isFocused()) load();
    }, LIST_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [navigation, load]);

  const indicatorFor = useCallback(
    (duel: DuelSummary): TurnIndicator => {
      if (duel.status === "finished") return null;
      if (duel.acting_player_id === account.id) {
        const midRound = duel.action === "answer_question" && (duel.position ?? 1) > 1;
        return midRound
          ? { color: "#EF6C00", label: "Angefangen – weiterspielen!" }
          : { color: "#2E7D32", label: "Du bist dran" };
      }
      return { color: "#C62828", label: "Gegner ist dran" };
    },
    [account.id],
  );

  const decline = useCallback(
    (duel: DuelSummary) => {
      Alert.alert("Herausforderung ablehnen?", `Duell gegen ${duel.challenger_display_name}`, [
        { text: "Abbrechen", style: "cancel" },
        {
          text: "Ablehnen",
          style: "destructive",
          onPress: async () => {
            try {
              await duelsApi.decline(duel.id);
              await load();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Ablehnen fehlgeschlagen");
            }
          },
        },
      ]);
    },
    [load],
  );

  const describe = useCallback(
    (duel: DuelSummary) => {
      const isChallenger = duel.challenger_id === account.id;
      const opponentName = isChallenger
        ? duel.opponent_display_name
        : duel.challenger_display_name;
      const ownScore = isChallenger ? duel.challenger_score : duel.opponent_score;
      const opponentScore = isChallenger ? duel.opponent_score : duel.challenger_score;
      const statusLabel =
        duel.status === "finished"
          ? ownScore > opponentScore
            ? "gewonnen"
            : ownScore < opponentScore
              ? "verloren"
              : "unentschieden"
          : duel.status === "pending"
            ? "wartet auf Start"
            : "läuft";
      return { opponentName, line: `${ownScore} – ${opponentScore} · ${statusLabel}` };
    },
    [account.id],
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Pressable style={styles.profileBadge} onPress={() => navigation.navigate("Profile")}>
        <Text style={styles.profileName}>{account.display_name}</Text>
        <Text style={styles.profileRank}>
          {account.rank} · {Math.round(account.rating)}
        </Text>
      </Pressable>

      {dueQuestionnaire && (
        <Pressable
          style={styles.questionnaireBanner}
          onPress={() => navigation.navigate("Questionnaire")}
        >
          <Text style={styles.bannerTitle}>Ein Fragebogen wartet auf dich</Text>
          <Text style={styles.bannerBody}>
            Damit bleibt Christduell für dich kostenlos. Jetzt ausfüllen →
          </Text>
        </Pressable>
      )}

      <Pressable style={styles.startButton} onPress={() => navigation.navigate("NewDuel")}>
        <Text style={styles.startButtonLabel}>Neues Duell</Text>
      </Pressable>

      {error && <Text style={styles.error}>{error}</Text>}

      <FlatList
        data={duels}
        keyExtractor={(duel) => String(duel.id)}
        contentContainerStyle={styles.list}
        ListEmptyComponent={<Text style={styles.empty}>Noch keine Duelle — starte eines!</Text>}
        renderItem={({ item }) => {
          const { opponentName, line } = describe(item);
          const canDecline = item.status === "pending" && item.opponent_id === account.id;
          const indicator = indicatorFor(item);
          return (
            <Pressable
              style={styles.card}
              onPress={() => navigation.navigate("Duel", { duelId: item.id })}
              onLongPress={canDecline ? () => decline(item) : undefined}
            >
              <View style={styles.cardHeader}>
                <Text style={styles.cardTitle}>gegen {opponentName}</Text>
                {indicator && <View style={[styles.turnDot, { backgroundColor: indicator.color }]} />}
              </View>
              <Text style={styles.cardSubtitle}>{line}</Text>
              {indicator && (
                <Text style={[styles.turnLabel, { color: indicator.color }]}>{indicator.label}</Text>
              )}
              {canDecline && <Text style={styles.cardHint}>Lange drücken zum Ablehnen</Text>}
            </Pressable>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
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
  questionnaireBanner: {
    backgroundColor: "#FFF3E0",
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  bannerTitle: { fontWeight: "700", color: "#8A5A00" },
  bannerBody: { color: "#8A5A00", marginTop: 2, fontSize: 13 },
  startButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    marginBottom: 16,
  },
  startButtonLabel: { color: "#FFFFFF", fontWeight: "600" },
  list: { gap: 12 },
  card: { backgroundColor: "#F4F1FB", borderRadius: 12, padding: 16 },
  cardHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  turnDot: { width: 12, height: 12, borderRadius: 6 },
  turnLabel: { marginTop: 6, fontSize: 13, fontWeight: "600" },
  cardTitle: { fontSize: 16, fontWeight: "600" },
  cardSubtitle: { marginTop: 4, color: "#5B5B5B" },
  cardHint: { marginTop: 6, fontSize: 11, color: "#9A9A9A" },
  empty: { textAlign: "center", marginTop: 48, color: "#5B5B5B" },
  error: { color: "#B00020", marginBottom: 12 },
});
