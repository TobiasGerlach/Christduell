variable "project" {
  description = "Short project name used as a prefix for resource names."
  type        = string
  default     = "christduell"
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, production)."
  type        = string
  default     = "production"
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "westeurope"
}

variable "container_image" {
  description = "Full container image reference the Web App should run, e.g. <acr-login-server>/christduell-backend:latest."
  type        = string
}

variable "app_service_sku" {
  description = "SKU for the Linux App Service Plan running the backend container."
  type        = string
  default     = "B1"
}

variable "postgres_admin_username" {
  description = "Administrator login for the PostgreSQL flexible server."
  type        = string
  default     = "christduell_admin"
}

variable "postgres_sku" {
  description = "SKU for the PostgreSQL flexible server. B_Standard_B1ms is the cheapest burstable tier."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "postgres_storage_mb" {
  description = "Provisioned storage. 32 GB is the smallest tier; backups up to this size are included."
  type        = number
  default     = 32768
}

variable "postgres_backup_retention_days" {
  description = "Days of point-in-time restore to keep (7-35). Included in the price."
  type        = number
  default     = 14
}

variable "research_enabled" {
  description = "Master switch for the research questionnaires. Keep FALSE until the consent texts are lawyer-approved — they collect Art. 9 GDPR data (religious beliefs, health screeners)."
  type        = bool
  default     = false
}

variable "cors_origins" {
  description = "Comma-separated browser origins allowed to call the API (the Expo web build's URL)."
  type        = string
  default     = ""
}

variable "push_enabled" {
  description = "Whether the backend actually sends push notifications via the Expo push service."
  type        = bool
  default     = false
}

variable "expo_access_token" {
  description = "Expo access token, required only if push notifications are sent from an Expo account with enhanced security enabled."
  type        = string
  default     = ""
  sensitive   = true
}

variable "billing_provider" {
  description = "Subscription provider: none (off), or stripe. 'fake' is rejected outside local development."
  type        = string
  default     = "none"

  validation {
    condition     = contains(["none", "stripe"], var.billing_provider)
    error_message = "billing_provider must be 'none' or 'stripe' — 'fake' hands out free subscriptions and is local-only."
  }
}

variable "stripe_secret_key" {
  description = "Stripe secret key (sk_live_… in production)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "stripe_price_id" {
  description = "Stripe price id for the monthly subscription."
  type        = string
  default     = ""
}

variable "stripe_webhook_secret" {
  description = "Signing secret of the Stripe webhook endpoint (whsec_…)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "billing_success_url" {
  description = "Where Stripe sends the browser after a successful checkout."
  type        = string
  default     = ""
}

variable "billing_cancel_url" {
  description = "Where Stripe sends the browser after an abandoned checkout."
  type        = string
  default     = ""
}
