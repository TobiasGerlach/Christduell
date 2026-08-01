import { api } from "./client";

export type ReportReason =
  | "wrong_answer"
  | "ambiguous"
  | "typo"
  | "inappropriate"
  | "other";

export interface QuestionReportResponse {
  status: string;
  /** True when this report was the one that pulled the question out of circulation. */
  question_retired: boolean;
}

export const questionsApi = {
  report: (questionId: number, reason: ReportReason, note?: string) =>
    api.post<QuestionReportResponse>(`/questions/${questionId}/report`, {
      reason,
      note: note?.trim() || null,
    }),
};
