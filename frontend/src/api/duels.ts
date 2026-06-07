import { api } from "./client";

export type DuelStatus = "pending" | "active" | "finished";

export interface Duel {
  id: number;
  challenger_id: number;
  opponent_id: number;
  status: DuelStatus;
  challenger_score: number;
  opponent_score: number;
  created_at: string;
  finished_at: string | null;
}

export const duelsApi = {
  listForPlayer: (playerId: number) => api.get<Duel[]>(`/duels?player_id=${playerId}`),
  get: (duelId: number) => api.get<Duel>(`/duels/${duelId}`),
  create: (challengerId: number, opponentId: number) =>
    api.post<Duel>("/duels", { challenger_id: challengerId, opponent_id: opponentId }),
};
