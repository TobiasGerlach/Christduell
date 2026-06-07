import { api } from "./client";

export interface PlayerProfile {
  id: number;
  display_name: string;
  rating: number;
  rank: string;
}

export const playersApi = {
  getProfile: (playerId: number) => api.get<PlayerProfile>(`/players/${playerId}`),
};
