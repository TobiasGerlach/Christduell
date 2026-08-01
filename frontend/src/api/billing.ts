import { api } from "./client";
import type { SubscriptionTier } from "./auth";

export interface SubscriptionStatus {
  /** "none" = subscriptions are switched off on this server. */
  provider: "none" | "fake" | "stripe";
  price_eur: string;
  tier: SubscriptionTier;
  active: boolean;
  valid_until: string | null;
  cancel_at_period_end: boolean;
}

export interface CheckoutResponse {
  /** Where to send the browser; null when the provider activated it directly. */
  checkout_url: string | null;
  activated: boolean;
}

export const billingApi = {
  getStatus: () => api.get<SubscriptionStatus>("/billing/status"),
  startCheckout: () => api.post<CheckoutResponse>("/billing/checkout"),
  cancel: () => api.post<SubscriptionStatus>("/billing/cancel"),
};
