import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ReportReason, questionsApi } from "../api/questions";

const REASONS: { value: ReportReason; label: string; hint: string }[] = [
  { value: "wrong_answer", label: "Antwort ist falsch", hint: "Die markierte Antwort stimmt nicht" },
  { value: "ambiguous", label: "Mehrdeutig", hint: "Mehrere Antworten sind vertretbar" },
  { value: "typo", label: "Schreibfehler", hint: "Tippfehler oder holprige Formulierung" },
  { value: "inappropriate", label: "Unpassend", hint: "Gehört so nicht in die App" },
  { value: "other", label: "Etwas anderes", hint: "" },
];

interface Props {
  visible: boolean;
  questionId: number;
  onClose: () => void;
}

export function ReportQuestionModal({ visible, questionId, onClose }: Props) {
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const reset = useCallback(() => {
    setReason(null);
    setNote("");
    setError(null);
    setDone(false);
    setBusy(false);
  }, []);

  const close = useCallback(() => {
    reset();
    onClose();
  }, [onClose, reset]);

  const submit = useCallback(async () => {
    if (!reason || busy) return;
    setBusy(true);
    setError(null);
    try {
      await questionsApi.report(questionId, reason, note);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Melden fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }, [busy, note, questionId, reason]);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={close}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          {done ? (
            <>
              <Text style={styles.title}>Danke!</Text>
              <Text style={styles.body}>
                Wir schauen uns die Frage an. Wenn mehrere Menschen sie melden, wird sie
                automatisch nicht mehr gestellt.
              </Text>
              <Pressable style={styles.primaryButton} onPress={close}>
                <Text style={styles.primaryLabel}>Schließen</Text>
              </Pressable>
            </>
          ) : (
            <>
              <Text style={styles.title}>Frage melden</Text>
              <Text style={styles.body}>Was stimmt mit dieser Frage nicht?</Text>

              {REASONS.map((option) => (
                <Pressable
                  key={option.value}
                  style={[styles.option, reason === option.value && styles.optionSelected]}
                  onPress={() => setReason(option.value)}
                >
                  <Text
                    style={[
                      styles.optionLabel,
                      reason === option.value && styles.optionLabelSelected,
                    ]}
                  >
                    {option.label}
                  </Text>
                  {option.hint ? (
                    <Text
                      style={[
                        styles.optionHint,
                        reason === option.value && styles.optionLabelSelected,
                      ]}
                    >
                      {option.hint}
                    </Text>
                  ) : null}
                </Pressable>
              ))}

              <TextInput
                style={styles.note}
                placeholder="Anmerkung (optional)"
                value={note}
                onChangeText={setNote}
                multiline
                maxLength={500}
              />

              {error && <Text style={styles.error}>{error}</Text>}

              <View style={styles.actions}>
                <Pressable style={styles.secondaryButton} onPress={close}>
                  <Text style={styles.secondaryLabel}>Abbrechen</Text>
                </Pressable>
                <Pressable
                  style={[styles.primaryButton, styles.grow, !reason && styles.disabled]}
                  onPress={submit}
                  disabled={!reason || busy}
                >
                  {busy ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <Text style={styles.primaryLabel}>Melden</Text>
                  )}
                </Pressable>
              </View>
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.4)" },
  sheet: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    gap: 8,
  },
  title: { fontSize: 20, fontWeight: "700" },
  body: { color: "#4A4A4A", marginBottom: 8, lineHeight: 20 },
  option: {
    borderWidth: 1,
    borderColor: "#D9D2E9",
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  optionSelected: { backgroundColor: "#6750A4", borderColor: "#6750A4" },
  optionLabel: { fontWeight: "600", color: "#333333" },
  optionHint: { fontSize: 12, color: "#7A7A7A", marginTop: 2 },
  optionLabelSelected: { color: "#FFFFFF" },
  note: {
    borderWidth: 1,
    borderColor: "#D9D2E9",
    borderRadius: 10,
    padding: 10,
    minHeight: 60,
    marginTop: 8,
    textAlignVertical: "top",
  },
  actions: { flexDirection: "row", gap: 10, marginTop: 12 },
  grow: { flex: 1 },
  primaryButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  primaryLabel: { color: "#FFFFFF", fontWeight: "600" },
  disabled: { opacity: 0.4 },
  secondaryButton: {
    borderWidth: 1,
    borderColor: "#D9D2E9",
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 18,
    alignItems: "center",
  },
  secondaryLabel: { color: "#4A4A4A", fontWeight: "600" },
  error: { color: "#B00020", marginTop: 8 },
});
