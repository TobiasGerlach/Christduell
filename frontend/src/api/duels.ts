import { api } from "./client";

export type DuelStatus = "pending" | "active" | "finished";
export type DuelAction = "pick_category" | "answer_question" | "finished";

export interface DuelSummary {
  challenger_display_name: string;
  opponent_display_name: string;
  id: number;
  challenger_id: number;
  opponent_id: number;
  status: DuelStatus;
  challenger_score: number;
  opponent_score: number;
  created_at: string;
  finished_at: string | null;
  action: DuelAction;
  acting_player_id: number | null;
  position: number | null;
}

export interface DuelStateResponse {
  duel_id: number;
  challenger_id: number;
  opponent_id: number;
  challenger_display_name: string;
  opponent_display_name: string;
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
  reference: string | null;
  explanation: string | null;
  is_correct: boolean;
  is_timeout: boolean;
  correct_choice_index: number;
  round_revealed: boolean;
  duel_finished: boolean;
  opponent_choice_index: number | null;
  opponent_is_timeout: boolean | null;
}

export interface DuelHistoryAnswer {
  player_id: number;
  selected_choice_index: number | null;
  is_correct: boolean | null;
  is_timeout: boolean;
}

export interface DuelHistoryQuestion {
  reference: string | null;
  explanation: string | null;
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

// The acting player is taken from the auth token on the server, so none of
// these calls pass a player id.
export const duelsApi = {
  list: () => api.get<DuelSummary[]>("/duels"),

  challengePlayer: (opponentId: number) =>
    api.post<DuelSummary>("/duels", { opponent_id: opponentId }),

  challengeByEmail: (opponentEmail: string) =>
    api.post<DuelSummary>("/duels", { opponent_email: opponentEmail }),

  challengeRandom: () => api.post<DuelSummary>("/duels/random"),

  decline: (duelId: number) => api.post<DuelSummary>(`/duels/${duelId}/decline`),

  getState: (duelId: number) => api.get<DuelStateResponse>(`/duels/${duelId}/state`),

  getRecommendations: (duelId: number) =>
    api.get<CategoryRecommendation[]>(`/duels/${duelId}/recommendations`),

  pickCategory: (duelId: number, category: string) =>
    api.post<DuelStateResponse>(`/duels/${duelId}/rounds`, { category }),

  getQuestion: (duelId: number, roundId: number, position: number) =>
    api.get<QuestionToAnswer>(`/duels/${duelId}/rounds/${roundId}/questions/${position}`),

  submitAnswer: (
    duelId: number,
    roundId: number,
    position: number,
    selectedChoiceIndex: number | null,
  ) =>
    api.post<AnswerResult>(`/duels/${duelId}/rounds/${roundId}/questions/${position}/answer`, {
      selected_choice_index: selectedChoiceIndex,
    }),

  getHistory: (duelId: number) => api.get<DuelHistoryResponse>(`/duels/${duelId}/history`),
};
