import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { AnswerResult, QuestionToAnswer, duelsApi } from "../api/duels";
import { ReportQuestionModal } from "../components/ReportQuestionModal";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "PlayQuestion">;

const QUESTION_TIME_LIMIT_SECONDS = 30;

export function PlayQuestionScreen({ route, navigation }: Props) {
  const { duelId, roundId, position } = route.params;
  const [question, setQuestion] = useState<QuestionToAnswer | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(QUESTION_TIME_LIMIT_SECONDS);
  const [selected, setSelected] = useState<number | null>(null);
  const [reporting, setReporting] = useState(false);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const submittedRef = useRef(false);

  useEffect(() => {
    submittedRef.current = false;
    setQuestion(null);
    setSelected(null);
    setResult(null);
    duelsApi
      .getQuestion(duelId, roundId, position)
      .then((q) => {
        setQuestion(q);
        setSecondsLeft(Math.ceil(q.seconds_remaining));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load question"));
  }, [duelId, roundId, position]);

  const submit = useCallback(
    async (choiceIndex: number | null) => {
      if (submittedRef.current) return;
      submittedRef.current = true;
      setSelected(choiceIndex);
      try {
        setError(null);
        setResult(await duelsApi.submitAnswer(duelId, roundId, position, choiceIndex));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to submit answer");
      }
    },
    [duelId, roundId, position],
  );

  // Countdown is purely cosmetic — derived from the server's `shown_at`
  // timestamp so it survives re-mounts, but the server independently enforces
  // the 30s cutoff and forces is_timeout regardless of what the client sends.
  useEffect(() => {
    if (!question || result) return;
    const shownAtMs = new Date(question.shown_at).getTime();
    const tick = () => {
      const elapsed = (Date.now() - shownAtMs) / 1000;
      const remaining = Math.max(0, QUESTION_TIME_LIMIT_SECONDS - elapsed);
      setSecondsLeft(Math.ceil(remaining));
      if (remaining <= 0) {
        submit(null);
      }
    };
    tick();
    const interval = setInterval(tick, 250);
    return () => clearInterval(interval);
  }, [question, result, submit]);

  const proceed = useCallback(() => {
    if (!result) return;
    if (position < 3) {
      navigation.replace("PlayQuestion", { duelId, roundId, position: position + 1 });
    } else if (result.duel_finished) {
      // Nothing left to do in this duel — drop the whole question/category
      // stack so "back" can't resurrect a finished question screen.
      navigation.reset({ index: 0, routes: [{ name: "DuelsList" }] });
    } else {
      navigation.navigate("Duel", { duelId });
    }
  }, [result, position, duelId, roundId, navigation]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (!question) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.timer}>{result ? "" : `⏱ ${secondsLeft}s`}</Text>
      <Text style={styles.prompt}>{question.prompt}</Text>

      {question.choices.map((choice, index) => {
        const isCorrectChoice = result != null && index === result.correct_choice_index;
        const isWrongSelection = result != null && selected === index && !result.is_correct;
        return (
          <Pressable
            key={index}
            style={[
              styles.choice,
              isCorrectChoice && styles.choiceCorrect,
              isWrongSelection && styles.choiceWrong,
            ]}
            onPress={() => submit(index)}
            disabled={selected !== null}
          >
            <Text style={styles.choiceLabel}>{choice}</Text>
          </Pressable>
        );
      })}

      {result && (
        <View style={styles.feedback}>
          <Text style={result.is_correct ? styles.feedbackCorrect : styles.feedbackWrong}>
            {result.is_timeout ? "Zeit abgelaufen!" : result.is_correct ? "Richtig!" : "Leider falsch."}
          </Text>
          {result.explanation && <Text style={styles.explanation}>{result.explanation}</Text>}
          {result.reference && <Text style={styles.reference}>{result.reference}</Text>}
          <Pressable onPress={() => setReporting(true)}>
            <Text style={styles.reportLink}>Frage melden</Text>
          </Pressable>
          <Pressable style={styles.continueButton} onPress={proceed}>
            <Text style={styles.continueButtonLabel}>
              {position < 3 ? "Weiter" : "Zurück zum Duell"}
            </Text>
          </Pressable>
        </View>
      )}

      <ReportQuestionModal
        visible={reporting}
        questionId={question.question_id}
        onClose={() => setReporting(false)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, gap: 12 },
  explanation: { marginTop: 8, color: "#4A4A4A", lineHeight: 20, textAlign: "center" },
  reportLink: {
    marginTop: 12,
    color: "#7A7A7A",
    fontSize: 12,
    textAlign: "center",
    textDecorationLine: "underline",
  },
  reference: { marginTop: 4, color: "#7A7A7A", fontSize: 12, textAlign: "center" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  timer: { textAlign: "right", fontSize: 16, fontWeight: "600", color: "#6750A4" },
  prompt: { fontSize: 20, fontWeight: "600", marginBottom: 8 },
  choice: {
    backgroundColor: "#F4F1FB",
    borderRadius: 12,
    padding: 16,
  },
  choiceCorrect: { backgroundColor: "#C8E6C9" },
  choiceWrong: { backgroundColor: "#FFCDD2" },
  choiceLabel: { fontSize: 16 },
  feedback: { marginTop: 16, alignItems: "center", gap: 12 },
  feedbackCorrect: { color: "#2E7D32", fontSize: 18, fontWeight: "700" },
  feedbackWrong: { color: "#B00020", fontSize: 18, fontWeight: "700" },
  continueButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 32,
  },
  continueButtonLabel: { color: "#FFFFFF", fontWeight: "600" },
  error: { color: "#B00020" },
});
