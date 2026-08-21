import { api } from "./client";

export interface PlayerProfile {
  id: number;
  display_name: string;
  rating: number;
  rank: string;
  rank_emoji: string;
}

export const playersApi = {
  getProfile: (playerId: number) => api.get<PlayerProfile>(`/players/${playerId}`),

  /** Finds opponents. Email matches must be exact; display names match by prefix. */
  search: (query: string) =>
    api.get<PlayerProfile[]>(`/players/search?q=${encodeURIComponent(query)}`),
};
