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

variable "postgres_admin_username" {
  description = "Administrator login for the PostgreSQL flexible server."
  type        = string
  default     = "christduell_admin"
}

variable "postgres_admin_password" {
  description = "Administrator password for the PostgreSQL flexible server."
  type        = string
  sensitive   = true
}

variable "app_service_sku" {
  description = "SKU for the Linux App Service Plan running the backend container."
  type        = string
  default     = "B1"
}

variable "postgres_sku" {
  description = "SKU for the PostgreSQL flexible server."
  type        = string
  default     = "B_Standard_B1ms"
}
