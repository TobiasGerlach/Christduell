import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { SubscriptionStatus, billingApi } from "../api/billing";
import { useAuth } from "../auth/AuthContext";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export function SubscriptionScreen() {
  const { refresh } = useAuth();
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);
      setStatus(await billingApi.getStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Abo-Status nicht verfügbar");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const subscribe = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await billingApi.startCheckout();
      if (result.checkout_url && !result.activated) {
        // Stripe Checkout runs in the browser and confirms back via webhook.
        await Linking.openURL(result.checkout_url);
      }
      await load();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bezahlvorgang nicht möglich");
    } finally {
      setBusy(false);
    }
  }, [load, refresh]);

  const cancel = useCallback(() => {
    Alert.alert(
      "Abo kündigen?",
      "Dein Zugang bleibt bis zum Ende der bezahlten Periode bestehen. Danach nimmst du wieder an den Forschungsfragebögen teil.",
      [
        { text: "Abbrechen", style: "cancel" },
        {
          text: "Kündigen",
          style: "destructive",
          onPress: async () => {
            setBusy(true);
            try {
              setStatus(await billingApi.cancel());
              await refresh();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Kündigung fehlgeschlagen");
            } finally {
              setBusy(false);
            }
          },
        },
      ],
    );
  }, [refresh]);

  if (!status) {
    return (
      <View style={styles.center}>
        {error ? <Text style={styles.error}>{error}</Text> : <ActivityIndicator />}
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>
          {status.active ? "Christduell Plus" : "Kostenlos (Forschungstarif)"}
        </Text>
        <Text style={styles.cardBody}>
          {status.active
            ? `Aktiv bis ${formatDate(status.valid_until)}.`
            : "Du spielst kostenlos und nimmst dafür gelegentlich an Forschungsfragebögen teil."}
        </Text>
        {status.cancel_at_period_end && (
          <Text style={styles.notice}>
            Gekündigt — läuft am {formatDate(status.valid_until)} aus.
          </Text>
        )}
      </View>

      <Text style={styles.sectionTitle}>Was das Abo bietet</Text>
      <Text style={styles.bullet}>• Keine Forschungsfragebögen</Text>
      <Text style={styles.bullet}>• Unterstützt die Weiterentwicklung von Christduell</Text>
      <Text style={styles.bullet}>• Monatlich kündbar</Text>

      {error && <Text style={styles.error}>{error}</Text>}

      {status.provider === "none" ? (
        <Text style={styles.unavailable}>
          Das Abo ist auf diesem Server noch nicht freigeschaltet.
        </Text>
      ) : status.active && !status.cancel_at_period_end ? (
        <Pressable style={styles.secondaryButton} onPress={cancel} disabled={busy}>
          <Text style={styles.secondaryLabel}>Abo kündigen</Text>
        </Pressable>
      ) : (
        <Pressable style={styles.primaryButton} onPress={subscribe} disabled={busy}>
          {busy ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.primaryLabel}>
              Für {status.price_eur} € / Monat abonnieren
            </Text>
          )}
        </Pressable>
      )}

      <Text style={styles.legal}>
        Das Abo verlängert sich monatlich, bis du kündigst. Preise inkl. MwSt. Es gelten die
        Nutzungsbedingungen und die Widerrufsbelehrung.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20, gap: 12 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: "#EDE7F6", borderRadius: 12, padding: 16, gap: 6 },
  cardTitle: { fontSize: 18, fontWeight: "700" },
  cardBody: { color: "#4A4A4A", lineHeight: 20 },
  notice: { color: "#8A5A00", marginTop: 4 },
  sectionTitle: { fontSize: 16, fontWeight: "600", marginTop: 12 },
  bullet: { color: "#4A4A4A", lineHeight: 22 },
  primaryButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 12,
  },
  primaryLabel: { color: "#FFFFFF", fontWeight: "600", fontSize: 16 },
  secondaryButton: {
    borderWidth: 1,
    borderColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 12,
  },
  secondaryLabel: { color: "#6750A4", fontWeight: "600" },
  unavailable: { color: "#5B5B5B", marginTop: 12, textAlign: "center" },
  error: { color: "#B00020" },
  legal: { fontSize: 12, color: "#7A7A7A", marginTop: 16, lineHeight: 18 },
});
