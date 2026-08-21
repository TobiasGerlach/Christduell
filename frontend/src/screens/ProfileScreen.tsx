import { useCallback, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import { authApi } from "../api/auth";
import { useAuth } from "../auth/AuthContext";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "Profile">;

export function ProfileScreen({ navigation }: Props) {
  const { account, logout, deleteAccount, setAccount } = useAuth();
  const [displayName, setDisplayName] = useState(account?.display_name ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const saveName = useCallback(async () => {
    setError(null);
    setMessage(null);
    try {
      setAccount(await authApi.updateDisplayName(displayName.trim()));
      setMessage("Name gespeichert");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    }
  }, [displayName, setAccount]);

  const confirmDelete = useCallback(() => {
    Alert.alert(
      "Konto löschen?",
      "Dein Konto und deine persönlichen Daten werden gelöscht. Eine bereits erteilte Forschungseinwilligung wird widerrufen. Das lässt sich nicht rückgängig machen.",
      [
        { text: "Abbrechen", style: "cancel" },
        {
          text: "Endgültig löschen",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteAccount();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
            }
          },
        },
      ],
    );
  }, [deleteAccount]);

  if (!account) return null;

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.card}>
        <Text style={styles.rank}>
        {account.rank_emoji} {account.rank}
      </Text>
        <Text style={styles.rating}>{Math.round(account.rating)} Punkte</Text>
        <Text style={styles.email}>{account.email}</Text>
      </View>

      <Text style={styles.label}>Anzeigename</Text>
      <TextInput style={styles.input} value={displayName} onChangeText={setDisplayName} />
      <Pressable style={styles.primaryButton} onPress={saveName}>
        <Text style={styles.primaryLabel}>Speichern</Text>
      </Pressable>

      {message && <Text style={styles.success}>{message}</Text>}
      {error && <Text style={styles.error}>{error}</Text>}

      <Pressable style={styles.linkRow} onPress={() => navigation.navigate("Subscription")}>
        <Text style={styles.linkLabel}>Abo verwalten</Text>
        <Text style={styles.linkValue}>
          {account.subscription_active ? "Christduell Plus" : "Kostenlos"}
        </Text>
      </Pressable>

      <Pressable style={styles.linkRow} onPress={() => navigation.navigate("ResearchConsent")}>
        <Text style={styles.linkLabel}>Forschungsteilnahme</Text>
        <Text style={styles.linkValue}>Verwalten</Text>
      </Pressable>

      <Pressable style={styles.secondaryButton} onPress={logout}>
        <Text style={styles.secondaryLabel}>Abmelden</Text>
      </Pressable>

      <Pressable style={styles.dangerButton} onPress={confirmDelete}>
        <Text style={styles.dangerLabel}>Konto löschen</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20, gap: 10 },
  card: { backgroundColor: "#EDE7F6", borderRadius: 12, padding: 16, marginBottom: 8 },
  rank: { fontSize: 20, fontWeight: "700" },
  rating: { color: "#4A4A4A", marginTop: 2 },
  email: { color: "#7A7A7A", marginTop: 6, fontSize: 12 },
  label: { fontWeight: "600", marginTop: 8 },
  input: {
    borderWidth: 1,
    borderColor: "#D9D2E9",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: "#FFFFFF",
  },
  primaryButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  primaryLabel: { color: "#FFFFFF", fontWeight: "600" },
  linkRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#EDE7F6",
  },
  linkLabel: { fontWeight: "600" },
  linkValue: { color: "#6750A4" },
  secondaryButton: {
    borderWidth: 1,
    borderColor: "#6750A4",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 20,
  },
  secondaryLabel: { color: "#6750A4", fontWeight: "600" },
  dangerButton: { paddingVertical: 14, alignItems: "center" },
  dangerLabel: { color: "#B00020" },
  success: { color: "#2E7D32" },
  error: { color: "#B00020" },
});
