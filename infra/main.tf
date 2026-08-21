locals {
  name_prefix = "${var.project}-${var.environment}"
}

# Suffix for resources that need a globally-unique name (ACR, Notification Hub namespace).
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# Signing key for the API's access tokens. Generated here so it never has to be
# invented or pasted by hand; it lives in Terraform state, so keep state remote
# and access-controlled. Changing it invalidates every issued token.
resource "random_password" "secret_key" {
  length  = 64
  special = false
}

# Database credentials: generated rather than typed into a tfvars file that
# then has to be kept secret. Both live in Terraform state, so keep state remote
# and access-controlled.
resource "random_password" "postgres" {
  length  = 40
  special = false
}

resource "azurerm_resource_group" "main" {
  name     = "${local.name_prefix}-rg"
  location = var.location
}

# --- Container registry -----------------------------------------------------

resource "azurerm_container_registry" "main" {
  name                = "${var.project}${var.environment}${random_string.suffix.result}acr"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
}

# --- Database ----------------------------------------------------------------
#
# SQLite on the App Service file share was the earlier design. It is a single
# writer over an SMB mount, which is unsafe the moment two containers overlap —
# and they do on every deploy. Managed Postgres also brings automatic backups
# with point-in-time restore, which the file share had no equivalent for.

resource "azurerm_postgresql_flexible_server" "main" {
  name                = "${local.name_prefix}-${random_string.suffix.result}-pg"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  version             = "16"

  administrator_login    = var.postgres_admin_username
  administrator_password = random_password.postgres.result

  sku_name   = var.postgres_sku
  storage_mb = var.postgres_storage_mb
  # Never let the disk (and the bill) grow on its own; resize deliberately instead.
  auto_grow_enabled = false
  zone              = "1"

  # Reachable from the Web App, narrowed by the firewall rule below. A private
  # endpoint would be tighter but needs a VNet the App Service is integrated
  # with — worth doing once there is more than one service to connect.
  public_network_access_enabled = true

  backup_retention_days        = var.postgres_backup_retention_days
  geo_redundant_backup_enabled = false

  lifecycle {
    # Losing the database because a name changed is not a recoverable mistake.
    prevent_destroy = true
  }
}

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "${var.project}_${var.environment}"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "utf8"

  lifecycle {
    prevent_destroy = true
  }
}

# 0.0.0.0 is Azure's sentinel for "other Azure services", not for the whole
# internet — it lets the Web App connect without opening the server publicly.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# --- Backend compute (Web App for Containers) -------------------------------

resource "azurerm_service_plan" "main" {
  name                = "${local.name_prefix}-plan"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = var.app_service_sku
}

resource "azurerm_linux_web_app" "backend" {
  name                = "${local.name_prefix}-api"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.main.id

  # Tokens and Stripe keys travel on every request — never over plain HTTP.
  https_only = true

  site_config {
    container_registry_use_managed_identity = true
    # Without this the app is unloaded when idle and every first request pays a
    # cold start.
    always_on         = true
    health_check_path = "/health"
    # Minutes an instance may fail /health before App Service recycles it (provider requires it alongside the path).
    health_check_eviction_time_in_min = 2
    minimum_tls_version               = "1.2"
    ftps_state                        = "Disabled"

    application_stack {
      docker_image_name   = var.container_image
      docker_registry_url = "https://${azurerm_container_registry.main.login_server}"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    ENVIRONMENT = var.environment
    DATABASE_URL = join("", [
      "postgresql+psycopg://",
      var.postgres_admin_username,
      ":",
      urlencode(random_password.postgres.result),
      "@",
      azurerm_postgresql_flexible_server.main.fqdn,
      ":5432/",
      azurerm_postgresql_flexible_server_database.main.name,
      "?sslmode=require",
    ])
    SECRET_KEY                               = random_password.secret_key.result
    CORS_ORIGINS                             = var.cors_origins
    AZURE_NOTIFICATION_HUB_NAME              = azurerm_notification_hub.main.name
    AZURE_NOTIFICATION_HUB_CONNECTION_STRING = azurerm_notification_hub_authorization_rule.backend.primary_connection_string
    PUSH_ENABLED                             = tostring(var.push_enabled)
    RESEARCH_ENABLED                         = tostring(var.research_enabled)
    EXPO_ACCESS_TOKEN                        = var.expo_access_token
    BILLING_PROVIDER                         = var.billing_provider
    STRIPE_SECRET_KEY                        = var.stripe_secret_key
    STRIPE_PRICE_ID                          = var.stripe_price_id
    STRIPE_WEBHOOK_SECRET                    = var.stripe_webhook_secret
    BILLING_SUCCESS_URL                      = var.billing_success_url
    BILLING_CANCEL_URL                       = var.billing_cancel_url
    WEBSITES_PORT                            = "8000"
  }

  lifecycle {
    # The CD pipeline updates the running image; Terraform must not roll it back
    # to whatever `container_image` happened to say at the last apply.
    ignore_changes = [site_config[0].application_stack[0].docker_image_name]
  }
}

# Grant the Web App's managed identity permission to pull images from ACR.
resource "azurerm_role_assignment" "web_app_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_linux_web_app.backend.identity[0].principal_id
}

# --- Push notifications ------------------------------------------------------

resource "azurerm_notification_hub_namespace" "main" {
  name                = "${local.name_prefix}-${random_string.suffix.result}-ns"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  namespace_type      = "NotificationHub"
  sku_name            = "Free"
}

resource "azurerm_notification_hub" "main" {
  name                = "${local.name_prefix}-hub"
  namespace_name      = azurerm_notification_hub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}

# Listen+manage rule the backend uses to register devices and send pushes.
resource "azurerm_notification_hub_authorization_rule" "backend" {
  name                  = "backend"
  notification_hub_name = azurerm_notification_hub.main.name
  namespace_name        = azurerm_notification_hub_namespace.main.name
  resource_group_name   = azurerm_resource_group.main.name

  listen = true
  manage = true
  send   = true
}
