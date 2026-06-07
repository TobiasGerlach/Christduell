import { api } from "./client";

export type DuelStatus = "pending" | "active" | "finished";
export type DuelAction = "pick_category" | "answer_question" | "finished";

export interface DuelSummary {
  id: number;
  challenger_id: number;
  opponent_id: number;
  status: DuelStatus;
  challenger_score: number;
  opponent_score: number;
  created_at: string;
  finished_at: string | null;
}

export interface DuelStateResponse {
  duel_id: number;
  status: DuelStatus;
  action: DuelAction;
  acting_player_id: number | null;
  waiting_player_id: number | null;
  round_sequence: number | null;
  round_id: number | null;
  position: number | null;
  challenger_score: number;
  opponent_score: number;
}

export interface CategoryRecommendation {
  category: string;
  display_name: string;
}

export interface QuestionToAnswer {
  round_id: number;
  position: number;
  question_id: number;
  category: string;
  prompt: string;
  choices: string[];
  shown_at: string;
  seconds_remaining: number;
}

export interface AnswerResult {
  is_correct: boolean;
  is_timeout: boolean;
  correct_choice_index: number;
  round_revealed: boolean;
  duel_finished: boolean;
}

export interface DuelHistoryAnswer {
  player_id: number;
  selected_choice_index: number | null;
  is_correct: boolean | null;
  is_timeout: boolean;
}

export interface DuelHistoryQuestion {
  position: number;
  prompt: string;
  choices: string[];
  correct_choice_index: number | null;
  answers: DuelHistoryAnswer[];
}

export interface DuelHistoryRound {
  sequence: number;
  category: string;
  category_display_name: string;
  picked_by_id: number;
  revealed: boolean;
  questions: DuelHistoryQuestion[];
}

export interface DuelHistoryResponse {
  duel_id: number;
  challenger_id: number;
  opponent_id: number;
  rounds: DuelHistoryRound[];
}

export const duelsApi = {
  listForPlayer: (playerId: number) =>
    api.get<DuelSummary[]>(`/duels?player_id=${playerId}`),

  create: (challengerId: number, opponentId: number) =>
    api.post<DuelSummary>("/duels", { challenger_id: challengerId, opponent_id: opponentId }),

  getState: (duelId: number, playerId: number) =>
    api.get<DuelStateResponse>(`/duels/${duelId}/state?player_id=${playerId}`),

  getRecommendations: (duelId: number, playerId: number) =>
    api.get<CategoryRecommendation[]>(`/duels/${duelId}/recommendations?player_id=${playerId}`),

  pickCategory: (duelId: number, playerId: number, category: string) =>
    api.post<DuelStateResponse>(`/duels/${duelId}/rounds`, { player_id: playerId, category }),

  getQuestion: (duelId: number, roundId: number, position: number, playerId: number) =>
    api.get<QuestionToAnswer>(
      `/duels/${duelId}/rounds/${roundId}/questions/${position}?player_id=${playerId}`,
    ),

  submitAnswer: (
    duelId: number,
    roundId: number,
    position: number,
    playerId: number,
    selectedChoiceIndex: number | null,
  ) =>
    api.post<AnswerResult>(`/duels/${duelId}/rounds/${roundId}/questions/${position}/answer`, {
      player_id: playerId,
      selected_choice_index: selectedChoiceIndex,
    }),

  getHistory: (duelId: number, playerId: number) =>
    api.get<DuelHistoryResponse>(`/duels/${duelId}/history?player_id=${playerId}`),
};
