import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";

import { ConsentStatus, researchApi } from "../api/research";

export function ResearchConsentScreen() {
  const [status, setStatus] = useState<ConsentStatus | null>(null);
  const [healthConsent, setHealthConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);
      const current = await researchApi.getConsent();
      setStatus(current);
      setHealthConsent(current.health_data_consented);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status nicht verfügbar");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const consent = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await researchApi.giveConsent(healthConsent));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Einwilligung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }, [healthConsent]);

  const withdraw = useCallback(() => {
    Alert.alert(
      "Einwilligung widerrufen?",
      "Die Verbindung zwischen dir und deinen bisherigen Antworten wird dauerhaft getrennt. Die Antworten selbst bleiben anonym erhalten und können danach nicht mehr zugeordnet werden.",
      [
        { text: "Abbrechen", style: "cancel" },
        {
          text: "Widerrufen",
          style: "destructive",
          onPress: async () => {
            setBusy(true);
            try {
              await researchApi.withdrawConsent();
              await load();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Widerruf fehlgeschlagen");
            } finally {
              setBusy(false);
            }
          },
        },
      ],
    );
  }, [load]);

  if (!status) {
    return (
      <View style={styles.center}>
        {error ? <Text style={styles.error}>{error}</Text> : <ActivityIndicator />}
      </View>
    );
  }

  if (!status.research_enabled) {
    return (
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.heading}>Forschungsteilnahme</Text>
        <Text style={styles.body}>
          Während der Testphase ist die Forschungsteilnahme deaktiviert — es werden keine
          Fragebögen gestellt und keine Forschungsdaten erhoben. Du kannst Christduell ganz
          normal spielen.
        </Text>
        {status.consented && (
          <Pressable style={styles.dangerButton} onPress={withdraw} disabled={busy}>
            <Text style={styles.dangerLabel}>Frühere Einwilligung widerrufen</Text>
          </Pressable>
        )}
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.heading}>Forschungsteilnahme</Text>
      <Text style={styles.body}>
        Christduell ist kostenlos, weil es Teil eines Forschungsprojekts ist. Nach einigen
        gespielten Duellen laden wir dich zu Fragebögen ein — zuerst zu deinem
        Glaubenshintergrund, später optional zu Aufmerksamkeit und Wahrnehmung.
      </Text>

      <View style={styles.factsBox}>
        <Text style={styles.fact}>
          • Deine Antworten werden ausschließlich unter einem zufälligen Pseudonym
          gespeichert — nicht unter deinem Namen oder deiner E-Mail-Adresse.
        </Text>
        <Text style={styles.fact}>
          • Du kannst deine Einwilligung jederzeit widerrufen. Danach lassen sich deine
          Antworten dir nicht mehr zuordnen.
        </Text>
        <Text style={styles.fact}>
          • Die Teilnahme ist freiwillig. Ohne Teilnahme kannst du das Abo wählen.
        </Text>
        <Text style={styles.fact}>
          • Fragebögen erscheinen frühestens nach {status.games_required} abgeschlossenen Duellen
          (aktuell: {status.games_played}).
        </Text>
      </View>

      <View style={styles.switchRow}>
        <View style={styles.switchTextBox}>
          <Text style={styles.switchLabel}>Gesundheitsbezogene Fragebögen</Text>
          <Text style={styles.switchHint}>
            Separate Einwilligung für Fragen zu Aufmerksamkeit (ADHS) und Wahrnehmung
            (Autismus). Diese Angaben sind besonders geschützte Gesundheitsdaten. Ohne diese
            Zustimmung nimmst du nur am ersten Fragebogen teil.
          </Text>
        </View>
        <Switch value={healthConsent} onValueChange={setHealthConsent} disabled={busy} />
      </View>

      {error && <Text style={styles.error}>{error}</Text>}

      {status.consented ? (
        <>
          <Text style={styles.activeNotice}>Du nimmst aktuell an der Forschung teil.</Text>
          <Pressable style={styles.primaryButton} onPress={consent} disabled={busy}>
            <Text style={styles.primaryLabel}>Auswahl aktualisieren</Text>
          </Pressable>
          <Pressable style={styles.dangerButton} onPress={withdraw} disabled={busy}>
            <Text style={styles.dangerLabel}>Einwilligung widerrufen</Text>
          </Pressable>
        </>
      ) : (
        <Pressable style={styles.primaryButton} onPress={consent} disabled={busy}>
          {busy ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.primaryLabel}>Einwilligen und teilnehmen</Text>
          )}
        </Pressable>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20, gap: 12 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  heading: { fontSize: 20, fontWeight: "700" },
  body: { color: "#4A4A4A", lineHeight: 21 },
  factsBox: { backgroundColor: "#F4F1FB", borderRadius: 12, padding: 14, gap: 8 },
  fact: { color: "#4A4A4A", lineHeight: 20 },
  switchRow: { flexDirection: "row", alignItems: "flex-start", gap: 12, marginTop: 8 },
  switchTextBox: { flex: 1 },
  switchLabel: { fontWeight: "600" },
  switchHint: { color: "#5B5B5B", fontSize: 13, lineHeight: 18, marginTop: 4 },
  activeNotice: { color: "#2E7D32", fontWeight: "600" },
  primaryButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  primaryLabel: { color: "#FFFFFF", fontWeight: "600" },
  dangerButton: { paddingVertical: 14, alignItems: "center" },
  dangerLabel: { color: "#B00020" },
  error: { color: "#B00020" },
});
