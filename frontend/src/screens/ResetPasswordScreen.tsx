import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import { authApi } from "../api/auth";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "ResetPassword">;

export function ResetPasswordScreen({ route, navigation }: Props) {
  const token = route.params?.token ?? "";
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async () => {
    if (busy) return;
    if (password.length < 8) {
      setError("Das Passwort braucht mindestens 8 Zeichen.");
      return;
    }
    if (password !== repeat) {
      setError("Die Passwörter stimmen nicht überein.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Der Link ist abgelaufen oder wurde schon benutzt.",
      );
    } finally {
      setBusy(false);
    }
  }, [busy, password, repeat, token]);

  if (!token) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Link unvollständig</Text>
        <Text style={styles.body}>
          Öffne den Link aus der E-Mail bitte direkt — er enthält einen Sicherheitscode.
        </Text>
      </View>
    );
  }

  if (done) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Geschafft! ✅</Text>
        <Text style={styles.body}>Dein Passwort ist geändert. Melde dich jetzt damit an.</Text>
        <Pressable
          style={styles.primaryButton}
          onPress={() => navigation.reset({ index: 0, routes: [{ name: "Login" }] })}
        >
          <Text style={styles.primaryLabel}>Zur Anmeldung</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Neues Passwort</Text>
      <TextInput
        style={styles.input}
        placeholder="Neues Passwort (min. 8 Zeichen)"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoComplete="new-password"
      />
      <TextInput
        style={styles.input}
        placeholder="Passwort wiederholen"
        value={repeat}
        onChangeText={setRepeat}
        secureTextEntry
        autoComplete="new-password"
        onSubmitEditing={submit}
      />
      {error && <Text style={styles.error}>{error}</Text>}
      <Pressable style={styles.primaryButton} onPress={submit} disabled={busy}>
        {busy ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.primaryLabel}>Passwort speichern</Text>
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
