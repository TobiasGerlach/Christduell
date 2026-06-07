import { Platform } from "react-native";

const SEED_PLAYER_IDS = [1, 2];

function resolvePlayerId(): number {
  // Local web testing convenience: open separate browser windows at
  // ?player=1 / ?player=2 to play both sides of a duel at once. Falls back
  // to the seeded default (Anna, id 1) everywhere else, including native.
  if (Platform.OS === "web" && typeof window !== "undefined") {
    const fromQuery = Number(new URLSearchParams(window.location.search).get("player"));
    if (SEED_PLAYER_IDS.includes(fromQuery)) {
      return fromQuery;
    }
  }
  return 1;
}

// TODO: replace with the authenticated player's id once login lands.
export const CURRENT_PLAYER_ID = resolvePlayerId();
