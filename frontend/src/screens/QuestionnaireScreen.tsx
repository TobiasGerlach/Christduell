import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import {
  QuestionnaireDefinition,
  QuestionnaireQuestion,
  QuestionnaireType,
  researchApi,
} from "../api/research";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "Questionnaire">;

type AnswerValue = string | number | string[];

/** Choice labels for a question, which may live on the question or on the shared scale. */
function optionsFor(
  question: QuestionnaireQuestion,
  definition: QuestionnaireDefinition,
): string[] {
  if (question.options) return question.options;
  if (question.type === "frequency_scale" || question.type === "agreement_scale") {
    return definition.response_scale?.options ?? [];
  }
  return [];
}

function scalePoints(question: QuestionnaireQuestion): number[] {
  const min = question.scale_min ?? 1;
  const max = question.scale_max ?? 5;
  return Array.from({ length: max - min + 1 }, (_, index) => min + index);
}

export function QuestionnaireScreen({ navigation }: Props) {
  const [definition, setDefinition] = useState<QuestionnaireDefinition | null>(null);
  const [type, setType] = useState<QuestionnaireType | null>(null);
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({});
  const [sectionIndex, setSectionIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const status = await researchApi.getCurrentQuestionnaire();
        setDefinition(status.questionnaire_definition);
        setType(status.due_questionnaire);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Fragebogen nicht verfügbar");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const section = definition?.sections[sectionIndex];
  const isLastSection = definition ? sectionIndex === definition.sections.length - 1 : false;

  const sectionAnswers = useMemo(() => {
    if (!section) return {};
    return Object.fromEntries(
      section.questions
        .filter((question) => answers[question.key] !== undefined)
        .map((question) => [question.key, answers[question.key]]),
    );
  }, [answers, section]);

  const setAnswer = useCallback((key: string, value: AnswerValue) => {
    setAnswers((current) => ({ ...current, [key]: value }));
  }, []);

  const toggleMulti = useCallback((key: string, option: string) => {
    setAnswers((current) => {
      const existing = (current[key] as string[] | undefined) ?? [];
      return {
        ...current,
        [key]: existing.includes(option)
          ? existing.filter((item) => item !== option)
          : [...existing, option],
      };
    });
  }, []);

  const submitSection = useCallback(async () => {
    if (!type) return;
    setBusy(true);
    setError(null);
    try {
      // Progress is saved section by section, so a dropped connection or a
      // closed app never costs more than the current page.
      await researchApi.submitAnswers(type, sectionAnswers, isLastSection);
      if (isLastSection) {
        navigation.goBack();
      } else {
        setSectionIndex((index) => index + 1);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }, [isLastSection, navigation, sectionAnswers, type]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!definition || !section || !type) {
    return (
      <View style={styles.center}>
        <Text style={styles.body}>
          {error ?? "Aktuell steht kein Fragebogen an. Spiel weiter — wir melden uns!"}
        </Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {sectionIndex === 0 && (
        <View style={styles.introBox}>
          <Text style={styles.title}>{definition.title}</Text>
          <Text style={styles.body}>{definition.description}</Text>
          <Text style={styles.meta}>Dauer: ca. {definition.estimated_minutes} Minuten</Text>
          {definition.instrument_reference && (
            <Text style={styles.reference}>{definition.instrument_reference}</Text>
          )}
        </View>
      )}

      <Text style={styles.progress}>
        Abschnitt {sectionIndex + 1} von {definition.sections.length}
      </Text>
      <Text style={styles.sectionTitle}>{section.title}</Text>

      {section.questions.map((question) => (
        <View key={question.key} style={styles.questionBox}>
          <Text style={styles.questionText}>{question.text}</Text>

          {(question.type === "single_choice" ||
            question.type === "frequency_scale" ||
            question.type === "agreement_scale") &&
            optionsFor(question, definition).map((option) => (
              <Pressable
                key={option}
                style={[
                  styles.option,
                  answers[question.key] === option && styles.optionSelected,
                ]}
                onPress={() => setAnswer(question.key, option)}
              >
                <Text
                  style={[
                    styles.optionLabel,
                    answers[question.key] === option && styles.optionLabelSelected,
                  ]}
                >
                  {option}
                </Text>
              </Pressable>
            ))}

          {question.type === "multi_choice" &&
            (question.options ?? []).map((option) => {
              const selected = ((answers[question.key] as string[]) ?? []).includes(option);
              return (
                <Pressable
                  key={option}
                  style={[styles.option, selected && styles.optionSelected]}
                  onPress={() => toggleMulti(question.key, option)}
                >
                  <Text style={[styles.optionLabel, selected && styles.optionLabelSelected]}>
                    {selected ? "✓ " : ""}
                    {option}
                  </Text>
                </Pressable>
              );
            })}

          {question.type === "scale" && (
            <>
              <View style={styles.scaleRow}>
                {scalePoints(question).map((point) => (
                  <Pressable
                    key={point}
                    style={[
                      styles.scalePoint,
                      answers[question.key] === point && styles.optionSelected,
                    ]}
                    onPress={() => setAnswer(question.key, point)}
                  >
                    <Text
                      style={[
                        styles.optionLabel,
                        answers[question.key] === point && styles.optionLabelSelected,
                      ]}
                    >
                      {point}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <View style={styles.scaleLabels}>
                <Text style={styles.scaleLabel}>{question.scale_min_label}</Text>
                <Text style={styles.scaleLabel}>{question.scale_max_label}</Text>
              </View>
            </>
          )}

          {question.type === "text" && (
            <TextInput
              style={styles.textInput}
              multiline
              value={(answers[question.key] as string) ?? ""}
              onChangeText={(value) => setAnswer(question.key, value)}
              placeholder="Freitext (freiwillig)"
            />
          )}

          {question.type === "ranking" && (
            <>
              <Text style={styles.hint}>
                Tippe die Begriffe in der Reihenfolge ihrer Wichtigkeit an.
              </Text>
              {(question.items ?? []).map((item) => {
                const order = ((answers[question.key] as string[]) ?? []).indexOf(item);
                return (
                  <Pressable
                    key={item}
                    style={[styles.option, order >= 0 && styles.optionSelected]}
                    onPress={() => toggleMulti(question.key, item)}
                  >
                    <Text
                      style={[styles.optionLabel, order >= 0 && styles.optionLabelSelected]}
                    >
                      {order >= 0 ? `${order + 1}. ` : ""}
                      {item}
                    </Text>
                  </Pressable>
                );
              })}
            </>
          )}
        </View>
      ))}

      {error && <Text style={styles.error}>{error}</Text>}

      <Pressable style={styles.primaryButton} onPress={submitSection} disabled={busy}>
        {busy ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.primaryLabel}>
            {isLastSection ? "Fragebogen abschließen" : "Weiter"}
          </Text>
        )}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20, gap: 12, paddingBottom: 48 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  introBox: { backgroundColor: "#F4F1FB", borderRadius: 12, padding: 16, gap: 8 },
  title: { fontSize: 20, fontWeight: "700" },
  body: { color: "#4A4A4A", lineHeight: 21 },
  meta: { color: "#5B5B5B", fontSize: 13 },
  reference: { color: "#7A7A7A", fontSize: 11, lineHeight: 16 },
  progress: { color: "#6750A4", fontWeight: "600", marginTop: 8 },
  sectionTitle: { fontSize: 18, fontWeight: "700", marginBottom: 4 },
  questionBox: { gap: 6, marginBottom: 12 },
  questionText: { fontWeight: "600", lineHeight: 21 },
  hint: { color: "#5B5B5B", fontSize: 13 },
  option: {
    borderWidth: 1,
    borderColor: "#D9D2E9",
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  optionSelected: { backgroundColor: "#6750A4", borderColor: "#6750A4" },
  optionLabel: { color: "#333333" },
  optionLabelSelected: { color: "#FFFFFF", fontWeight: "600" },
  scaleRow: { flexDirection: "row", gap: 8 },
  scalePoint: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#D9D2E9",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  scaleLabels: { flexDirection: "row", justifyContent: "space-between" },
  scaleLabel: { fontSize: 11, color: "#7A7A7A", flex: 1 },
  textInput: {
    borderWidth: 1,
    borderColor: "#D9D2E9",
    borderRadius: 10,
    padding: 12,
    minHeight: 80,
    textAlignVertical: "top",
  },
  primaryButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 8,
  },
  primaryLabel: { color: "#FFFFFF", fontWeight: "600" },
  error: { color: "#B00020" },
});
