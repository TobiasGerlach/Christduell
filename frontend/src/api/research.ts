import { api } from "./client";

export type QuestionnaireType = "faith_background" | "adhd_screener" | "autism_screener";

export interface ConsentStatus {
  consented: boolean;
  health_data_consented: boolean;
  research_tier: boolean;
  games_played: number;
  games_required: number;
  withdrawn_at: string | null;
}

export interface QuestionnaireQuestion {
  key: string;
  text: string;
  type: "single_choice" | "multi_choice" | "scale" | "frequency_scale" | "agreement_scale" | "text" | "ranking";
  options?: string[];
  items?: string[];
  required?: boolean;
  scale_min?: number;
  scale_max?: number;
  scale_min_label?: string;
  scale_max_label?: string;
}

export interface QuestionnaireSection {
  key: string;
  title: string;
  questions: QuestionnaireQuestion[];
}

export interface QuestionnaireDefinition {
  type: QuestionnaireType;
  title: string;
  description: string;
  estimated_minutes: number;
  instrument_reference?: string;
  response_scale?: { type: string; options: string[] };
  sections: QuestionnaireSection[];
}

export interface QuestionnaireStatus {
  due_questionnaire: QuestionnaireType | null;
  questionnaire_definition: QuestionnaireDefinition | null;
}

export const researchApi = {
  getConsent: () => api.get<ConsentStatus>("/research/consent"),

  giveConsent: (healthDataConsent: boolean) =>
    api.post<ConsentStatus>("/research/consent", {
      general_consent: true,
      health_data_consent: healthDataConsent,
    }),

  withdrawConsent: () => api.delete<void>("/research/consent"),

  getCurrentQuestionnaire: () => api.get<QuestionnaireStatus>("/research/questionnaire/current"),

  submitAnswers: (
    type: QuestionnaireType,
    answers: Record<string, unknown>,
    finished: boolean,
  ) =>
    api.post<{ status: string }>(`/research/questionnaire/${type}/answers`, {
      answers,
      finished,
    }),
};
