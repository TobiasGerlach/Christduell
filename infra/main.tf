locals {
  name_prefix = "${var.project}-${var.environment}"
}

# Suffix for resources that need a globally-unique name (ACR, Postgres server).
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
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

  site_config {
    container_registry_use_managed_identity = true

    application_stack {
      docker_image_name   = var.container_image
      docker_registry_url = "https://${azurerm_container_registry.main.login_server}"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    ENVIRONMENT                              = var.environment
    DATABASE_URL                             = local.database_url
    AZURE_NOTIFICATION_HUB_NAME              = azurerm_notification_hub.main.name
    AZURE_NOTIFICATION_HUB_CONNECTION_STRING = azurerm_notification_hub_authorization_rule.backend.primary_connection_string
    WEBSITES_PORT                            = "8000"
  }
}

# Grant the Web App's managed identity permission to pull images from ACR.
resource "azurerm_role_assignment" "web_app_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_linux_web_app.backend.identity[0].principal_id
}

# --- Database ----------------------------------------------------------------

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${var.project}-${var.environment}-${random_string.suffix.result}-pg"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = "16"
  administrator_login           = var.postgres_admin_username
  administrator_password        = var.postgres_admin_password
  sku_name                      = var.postgres_sku
  storage_mb                    = 32768
  zone                          = "1"
  public_network_access_enabled = true
}

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "${var.project}_${var.environment}"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

# Allow Azure services (incl. the Web App) to reach the database.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

locals {
  database_url = "postgresql://${var.postgres_admin_username}:${var.postgres_admin_password}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.main.name}?sslmode=require"
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
