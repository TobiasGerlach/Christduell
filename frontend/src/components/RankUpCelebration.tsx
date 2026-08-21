import { useCallback, useEffect, useRef, useState } from "react";
import { Animated, Easing, Pressable, StyleSheet, Text } from "react-native";

import { useAuth } from "../auth/AuthContext";
import { loadValue, saveValue } from "../auth/storage";
import { formatRank } from "../lib/rank";

// Celebrates every climb on the ladder: a division step gets the small
// wording, a whole new rank the big one. The last celebrated ladder_step is
// persisted per account, so a climb that happened while the app was closed
// still gets its moment on the next launch — and nothing is celebrated twice.

const CONFETTI = ["🎉", "✨", "⭐", "🎊", "💜", "✨", "🎉", "⭐", "✨", "🎊", "💜", "⭐"];
const SHOW_MS = 4200;

interface Celebration {
  emoji: string;
  title: string;
  rankLabel: string;
}

function ConfettiPiece({ index }: { index: number }) {
  const fall = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(fall, {
      toValue: 1,
      duration: 2600 + (index % 5) * 350,
      delay: (index % 7) * 120,
      easing: Easing.in(Easing.quad),
      useNativeDriver: true,
    }).start();
  }, [fall, index]);

  // Deterministic pseudo-random spread — no Math.random so re-renders are stable.
  const left = ((index * 83) % 100) / 100;
  const drift = ((index * 47) % 60) - 30;

  return (
    <Animated.Text
      style={[
        styles.confetti,
        {
          left: `${left * 100}%`,
          transform: [
            {
              translateY: fall.interpolate({ inputRange: [0, 1], outputRange: [-60, 700] }),
            },
            { translateX: fall.interpolate({ inputRange: [0, 1], outputRange: [0, drift] }) },
            {
              rotate: fall.interpolate({
                inputRange: [0, 1],
                outputRange: ["0deg", `${drift * 12}deg`],
              }),
            },
          ],
        },
      ]}
    >
      {CONFETTI[index % CONFETTI.length]}
    </Animated.Text>
  );
}

export function RankUpCelebration() {
  const { account } = useAuth();
  const [celebration, setCelebration] = useState<Celebration | null>(null);
  const opacity = useRef(new Animated.Value(0)).current;
  const emojiScale = useRef(new Animated.Value(0)).current;
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The steps already handled this session, so a slow storage write can't
  // trigger the same celebration twice.
  const handledStep = useRef<number | null>(null);

  const dismiss = useCallback(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current);
    Animated.timing(opacity, { toValue: 0, duration: 250, useNativeDriver: true }).start(() =>
      setCelebration(null),
    );
  }, [opacity]);

  useEffect(() => {
    if (!account) {
      handledStep.current = null;
      return;
    }
    const key = `ladderStep.${account.id}`;
    let cancelled = false;

    (async () => {
      const stored = await loadValue(key);
      if (cancelled) return;
      const previous = handledStep.current ?? (stored === null ? null : Number(stored));

      if (previous === null || Number.isNaN(previous)) {
        // First sighting of this account on this device: set the baseline
        // silently — greeting a new login with confetti would be noise.
        handledStep.current = account.ladder_step;
        await saveValue(key, String(account.ladder_step));
        return;
      }
      if (account.ladder_step <= previous) {
        handledStep.current = Math.max(previous, handledStep.current ?? previous);
        return;
      }

      handledStep.current = account.ladder_step;
      await saveValue(key, String(account.ladder_step));

      const newRank = account.rank_division === 5 || Math.floor(previous / 5) < Math.floor(account.ladder_step / 5);
      setCelebration({
        emoji: account.rank_emoji,
        title: newRank ? "NEUER RANG!" : "AUFSTIEG!",
        rankLabel: formatRank(account.rank, account.rank_division),
      });
      opacity.setValue(0);
      emojiScale.setValue(0);
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 300, useNativeDriver: true }),
        Animated.spring(emojiScale, {
          toValue: 1,
          friction: 4,
          tension: 60,
          useNativeDriver: true,
        }),
      ]).start();
      if (hideTimer.current) clearTimeout(hideTimer.current);
      hideTimer.current = setTimeout(dismiss, SHOW_MS);
    })();

    return () => {
      cancelled = true;
    };
  }, [account, opacity, emojiScale, dismiss]);

  if (!celebration) return null;

  return (
    <Animated.View style={[styles.overlay, { opacity }]}>
      <Pressable style={styles.fill} onPress={dismiss}>
        {CONFETTI.map((_, i) => (
          <ConfettiPiece key={i} index={i} />
        ))}
        <Animated.Text style={[styles.emoji, { transform: [{ scale: emojiScale }] }]}>
          {celebration.emoji}
        </Animated.Text>
        <Text style={styles.title}>{celebration.title}</Text>
        <Text style={styles.rankLabel}>{celebration.rankLabel}</Text>
        <Text style={styles.hint}>Tippen zum Schließen</Text>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(43, 22, 96, 0.92)",
    zIndex: 1000,
  },
  fill: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12, overflow: "hidden" },
  confetti: { position: "absolute", top: 0, fontSize: 26 },
  emoji: { fontSize: 96 },
  title: { color: "#FFD75E", fontSize: 28, fontWeight: "800", letterSpacing: 3 },
  rankLabel: { color: "#FFFFFF", fontSize: 22, fontWeight: "700" },
  hint: { color: "#B9A8E8", fontSize: 13, marginTop: 24 },
});
