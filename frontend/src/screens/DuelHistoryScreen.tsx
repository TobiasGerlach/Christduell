import { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";

import { DuelHistoryQuestion, DuelHistoryResponse, DuelHistoryRound, duelsApi } from "../api/duels";
import { useAccount } from "../auth/AuthContext";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "DuelHistory">;

function QuestionRow({ question, playerId }: { question: DuelHistoryQuestion; playerId: number }) {
  const correctChoice =
    question.correct_choice_index != null ? question.choices[question.correct_choice_index] : null;

  return (
    <View style={styles.question}>
      <Text style={styles.questionPrompt}>
        {question.position}. {question.prompt}
      </Text>
      {correctChoice != null && <Text style={styles.questionAnswer}>Richtig: {correctChoice}</Text>}
      {question.explanation && <Text style={styles.questionExplanation}>{question.explanation}</Text>}
      {question.reference && <Text style={styles.questionReference}>{question.reference}</Text>}
      {question.answers.map((answer) => {
        const label = answer.player_id === playerId ? "Du" : "Gegner";
        const outcome = answer.is_timeout
          ? "Zeit abgelaufen"
          : answer.is_correct
            ? "richtig"
            : "falsch";
        return (
          <Text key={answer.player_id} style={answer.is_correct ? styles.correct : styles.incorrect}>
            {label}: {outcome}
          </Text>
        );
      })}
    </View>
  );
}

function RoundCard({ round, playerId }: { round: DuelHistoryRound; playerId: number }) {
  const pickerLabel = round.picked_by_id === playerId ? "Du" : "Gegner";

  return (
    <View style={styles.roundCard}>
      <Text style={styles.roundTitle}>
        Runde {round.sequence} · {round.category_display_name}
      </Text>
      <Text style={styles.roundSubtitle}>Gewählt von: {pickerLabel}</Text>

      {!round.revealed ? (
        <Text style={styles.pending}>Noch nicht abgeschlossen …</Text>
      ) : (
        round.questions.map((question) => (
          <QuestionRow key={question.position} question={question} playerId={playerId} />
        ))
      )}
    </View>
  );
}

export function DuelHistoryScreen({ route }: Props) {
  const { duelId } = route.params;
  const account = useAccount();
  const [history, setHistory] = useState<DuelHistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    duelsApi
      .getHistory(duelId)
      .then(setHistory)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load history"));
  }, [duelId]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (!history) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {history.rounds.map((round) => (
        <RoundCard key={round.sequence} round={round} playerId={account.id} />
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  questionExplanation: { color: "#4A4A4A", fontSize: 13, lineHeight: 18, marginTop: 2 },
  questionReference: { color: "#7A7A7A", fontSize: 11, marginTop: 1 },
  container: { padding: 16, gap: 12 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  roundCard: {
    backgroundColor: "#F4F1FB",
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  roundTitle: { fontSize: 16, fontWeight: "700" },
  roundSubtitle: { color: "#5B5B5B" },
  pending: { color: "#5B5B5B", fontStyle: "italic" },
  question: { gap: 2, marginTop: 4 },
  questionPrompt: { fontSize: 14, fontWeight: "600" },
  questionAnswer: { color: "#5B5B5B", fontSize: 13 },
  correct: { color: "#2E7D32", fontSize: 13 },
  incorrect: { color: "#B00020", fontSize: 13 },
  error: { color: "#B00020" },
});
