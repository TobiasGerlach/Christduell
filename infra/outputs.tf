output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "container_registry_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "backend_url" {
  description = "Public URL of the deployed FastAPI backend."
  value       = "https://${azurerm_linux_web_app.backend.default_hostname}"
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "notification_hub_name" {
  value = azurerm_notification_hub.main.name
}

output "notification_hub_connection_string" {
  value     = azurerm_notification_hub_authorization_rule.backend.primary_connection_string
  sensitive = true
}
