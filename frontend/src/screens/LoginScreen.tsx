import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";

import { useAuth } from "../auth/AuthContext";

type Mode = "login" | "register";

// Set at build time; without them the screen falls back to honest beta wording
// instead of asserting consent to documents that do not exist.
const TERMS_URL = process.env.EXPO_PUBLIC_TERMS_URL ?? "";
const PRIVACY_URL = process.env.EXPO_PUBLIC_PRIVACY_URL ?? "";

export function LoginScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(displayName.trim(), email.trim(), password, ageConfirmed);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anmeldung fehlgeschlagen");
      setBusy(false);
    }
  }, [busy, displayName, email, login, mode, password, register]);

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Christduell</Text>
        <Text style={styles.subtitle}>
          {mode === "login" ? "Willkommen zurück!" : "Konto erstellen und loslegen"}
        </Text>

        {mode === "register" && (
          <TextInput
            style={styles.input}
            placeholder="Anzeigename"
            value={displayName}
            onChangeText={setDisplayName}
            autoCapitalize="words"
            autoComplete="name"
          />
        )}

        <TextInput
          style={styles.input}
          placeholder="E-Mail"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          autoComplete="email"
        />

        <TextInput
          style={styles.input}
          placeholder={mode === "register" ? "Passwort (min. 8 Zeichen)" : "Passwort"}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete={mode === "register" ? "new-password" : "current-password"}
          onSubmitEditing={submit}
        />

        {mode === "register" && (
          <View style={styles.ageRow}>
            <Switch value={ageConfirmed} onValueChange={setAgeConfirmed} />
            <Text style={styles.ageLabel}>
              Ich bin mindestens 16 Jahre alt, oder meine Erziehungsberechtigten sind mit der
              Nutzung einverstanden.
            </Text>
          </View>
        )}

        {error && <Text style={styles.error}>{error}</Text>}

        <Pressable style={styles.primaryButton} onPress={submit} disabled={busy}>
          {busy ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.primaryLabel}>
              {mode === "login" ? "Anmelden" : "Registrieren"}
            </Text>
          )}
        </Pressable>

        <Pressable
          onPress={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
        >
          <Text style={styles.switchMode}>
            {mode === "login"
              ? "Noch kein Konto? Jetzt registrieren"
              : "Schon registriert? Zur Anmeldung"}
          </Text>
        </Pressable>

        <View style={styles.legalBox}>
          {TERMS_URL && PRIVACY_URL ? (
            <Text style={styles.legalText}>
              Mit der Registrierung stimmst du den{" "}
              <Text style={styles.legalLink} onPress={() => Linking.openURL(TERMS_URL)}>
                Nutzungsbedingungen
              </Text>{" "}
              und der{" "}
              <Text style={styles.legalLink} onPress={() => Linking.openURL(PRIVACY_URL)}>
                Datenschutzerklärung
              </Text>{" "}
              zu.
            </Text>
          ) : (
            // No links configured yet: do not claim agreement to documents that
            // are not there. The organiser hands the information out instead.
            <Text style={styles.legalText}>
              Testversion. Nutzungsbedingungen und Datenschutzinformationen erhältst du von
              deiner Ansprechperson.
            </Text>
          )}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { padding: 24, gap: 12, justifyContent: "center", flexGrow: 1 },
  title: { fontSize: 32, fontWeight: "700", textAlign: "center", color: "#6750A4" },
  subtitle: { textAlign: "center", color: "#5B5B5B", marginBottom: 12 },
  input: {
    borderWidth: 1,
    borderColor: "#D9D2E9",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    backgroundColor: "#FFFFFF",
  },
  primaryButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 4,
  },
  primaryLabel: { color: "#FFFFFF", fontWeight: "600", fontSize: 16 },
  switchMode: { textAlign: "center", color: "#6750A4", marginTop: 8 },
  error: { color: "#B00020" },
  ageRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  ageLabel: { flex: 1, fontSize: 12, color: "#5B5B5B", lineHeight: 17 },
  legalBox: { marginTop: 24 },
  legalLink: { color: "#6750A4", textDecorationLine: "underline" },
  legalText: { fontSize: 12, color: "#7A7A7A", textAlign: "center", lineHeight: 18 },
});
