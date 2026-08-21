import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import { authApi } from "../api/auth";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "ForgotPassword">;

export function ForgotPasswordScreen({ navigation }: Props) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async () => {
    if (!email.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await authApi.forgotPassword(email.trim());
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Das hat nicht geklappt — versuch es nochmal.");
    } finally {
      setBusy(false);
    }
  }, [email, busy]);

  if (sent) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>E-Mail unterwegs 📬</Text>
        <Text style={styles.body}>
          Wenn ein Konto mit dieser Adresse existiert, ist gerade eine E-Mail mit einem
          Zurücksetz-Link losgeschickt worden. Der Link ist 60 Minuten gültig — schau auch im
          Spam-Ordner nach.
        </Text>
        <Pressable style={styles.primaryButton} onPress={() => navigation.goBack()}>
          <Text style={styles.primaryLabel}>Zurück zur Anmeldung</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Passwort vergessen?</Text>
      <Text style={styles.body}>
        Gib die E-Mail-Adresse deines Kontos ein — wir schicken dir einen Link zum Zurücksetzen.
      </Text>
      <TextInput
        style={styles.input}
        placeholder="E-Mail"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="email-address"
        autoComplete="email"
        onSubmitEditing={submit}
      />
      {error && <Text style={styles.error}>{error}</Text>}
      <Pressable style={styles.primaryButton} onPress={submit} disabled={busy}>
        {busy ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.primaryLabel}>Link anfordern</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, gap: 14, justifyContent: "center" },
  title: { fontSize: 24, fontWeight: "700", textAlign: "center" },
  body: { color: "#5B5B5B", textAlign: "center", lineHeight: 20 },
  input: {
    backgroundColor: "#F4F1FB",
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
  },
  primaryButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  primaryLabel: { color: "#FFFFFF", fontWeight: "600", fontSize: 16 },
  error: { color: "#B00020", textAlign: "center" },
});
