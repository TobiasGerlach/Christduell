import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import { DuelSummary, duelsApi } from "../api/duels";
import { QuestionnaireType, researchApi } from "../api/research";
import { useAccount } from "../auth/AuthContext";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "DuelsList">;

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
          return (
            <Pressable
              style={styles.card}
              onPress={() => navigation.navigate("Duel", { duelId: item.id })}
              onLongPress={canDecline ? () => decline(item) : undefined}
            >
              <Text style={styles.cardTitle}>gegen {opponentName}</Text>
              <Text style={styles.cardSubtitle}>{line}</Text>
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
  cardTitle: { fontSize: 16, fontWeight: "600" },
  cardSubtitle: { marginTop: 4, color: "#5B5B5B" },
  cardHint: { marginTop: 6, fontSize: 11, color: "#9A9A9A" },
  empty: { textAlign: "center", marginTop: 48, color: "#5B5B5B" },
  error: { color: "#B00020", marginBottom: 12 },
});
