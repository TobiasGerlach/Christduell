import { api } from "./client";

export type SubscriptionTier = "research" | "paid";

export interface Account {
  id: number;
  display_name: string;
  email: string;
  rating: number;
  rank: string;
  rank_emoji: string;
  rank_division: number;
  ladder_step: number;
  subscription_tier: SubscriptionTier;
  subscription_active: boolean;
  subscription_valid_until: string | null;
  subscription_cancel_at_period_end: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  player: Account;
}

export const authApi = {
  forgotPassword: (email: string) => api.post<void>("/auth/forgot-password", { email }),

  resetPassword: (token: string, newPassword: string) =>
    api.post<void>("/auth/reset-password", { token, new_password: newPassword }),

  register: (displayName: string, email: string, password: string, minAgeConfirmed: boolean) =>
    api.post<TokenResponse>("/auth/register", {
      display_name: displayName,
      email,
      password,
      min_age_confirmed: minAgeConfirmed,
    }),

  login: (email: string, password: string) =>
    api.post<TokenResponse>("/auth/login", { email, password }),

  me: () => api.get<Account>("/auth/me"),

  updateDisplayName: (displayName: string) =>
    api.patch<Account>("/auth/me", { display_name: displayName }),

  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<void>("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    }),

  deleteAccount: () => api.delete<void>("/auth/me"),
};
