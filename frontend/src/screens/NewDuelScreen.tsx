import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import { duelsApi } from "../api/duels";
import { PlayerProfile, playersApi } from "../api/players";
import type { RootStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "NewDuel">;

const MIN_QUERY_LENGTH = 3;

export function NewDuelScreen({ navigation }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PlayerProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [challenging, setChallenging] = useState(false);

  const search = useCallback(async () => {
    const term = query.trim();
    if (term.length < MIN_QUERY_LENGTH) {
      setError(`Bitte mindestens ${MIN_QUERY_LENGTH} Zeichen eingeben`);
      return;
    }
    setSearching(true);
    setError(null);
    try {
      setResults(await playersApi.search(term));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Suche fehlgeschlagen");
    } finally {
      setSearching(false);
    }
  }, [query]);

  const startDuel = useCallback(
    async (start: () => Promise<{ id: number }>) => {
      if (challenging) return;
      setChallenging(true);
      setError(null);
      try {
        const duel = await start();
        navigation.replace("Duel", { duelId: duel.id });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Duell konnte nicht gestartet werden");
        setChallenging(false);
      }
    },
    [challenging, navigation],
  );

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Gegner suchen</Text>
      <View style={styles.searchRow}>
        <TextInput
          style={styles.input}
          placeholder="Name oder E-Mail-Adresse"
          value={query}
          onChangeText={setQuery}
          autoCapitalize="none"
          autoCorrect={false}
          onSubmitEditing={search}
          returnKeyType="search"
        />
        <Pressable style={styles.searchButton} onPress={search} disabled={searching}>
          {searching ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.searchLabel}>Suchen</Text>
          )}
        </Pressable>
      </View>

      {error && <Text style={styles.error}>{error}</Text>}

      <FlatList
        data={results ?? []}
        keyExtractor={(player) => String(player.id)}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          results === null ? null : (
            <Text style={styles.empty}>
              Niemand gefunden. Eine E-Mail-Adresse muss exakt stimmen.
            </Text>
          )
        }
        renderItem={({ item }) => (
          <Pressable
            style={styles.card}
            disabled={challenging}
            onPress={() => startDuel(() => duelsApi.challengePlayer(item.id))}
          >
            <Text style={styles.cardTitle}>{item.display_name}</Text>
            <Text style={styles.cardSubtitle}>
              {item.rank_emoji} {item.rank} · {Math.round(item.rating)}
            </Text>
          </Pressable>
        )}
      />

      <View style={styles.footer}>
        <Text style={styles.footerHint}>Niemanden zum Spielen?</Text>
        <Pressable
          style={styles.randomButton}
          disabled={challenging}
          onPress={() => startDuel(() => duelsApi.challengeRandom())}
        >
          {challenging ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.randomLabel}>Zufallsgegner finden</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  heading: { fontSize: 18, fontWeight: "600", marginBottom: 12 },
  searchRow: { flexDirection: "row", gap: 8 },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#D9D2E9",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: "#FFFFFF",
  },
  searchButton: {
    backgroundColor: "#6750A4",
    borderRadius: 12,
    paddingHorizontal: 20,
    justifyContent: "center",
  },
  searchLabel: { color: "#FFFFFF", fontWeight: "600" },
  list: { gap: 12, paddingTop: 16 },
  card: { backgroundColor: "#F4F1FB", borderRadius: 12, padding: 16 },
  cardTitle: { fontSize: 16, fontWeight: "600" },
  cardSubtitle: { marginTop: 4, color: "#5B5B5B" },
  empty: { textAlign: "center", marginTop: 32, color: "#5B5B5B" },
  error: { color: "#B00020", marginTop: 12 },
  footer: { borderTopWidth: 1, borderTopColor: "#EDE7F6", paddingTop: 16, gap: 8 },
  footerHint: { textAlign: "center", color: "#5B5B5B" },
  randomButton: {
    backgroundColor: "#4A3B7C",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  randomLabel: { color: "#FFFFFF", fontWeight: "600" },
});
