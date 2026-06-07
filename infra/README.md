# Christduell — Azure infrastructure (Terraform)

Provisions everything the backend needs to run in Azure:

- **Resource group** — container for all resources
- **Azure Container Registry (ACR)** — stores the backend's Docker images
- **Linux App Service Plan + Web App for Containers** — runs the FastAPI backend,
  pulling images from ACR via a system-assigned managed identity (no stored
  registry credentials)
- **Azure Database for PostgreSQL — Flexible Server** — production database
  (the backend defaults to SQLite locally; Terraform wires `DATABASE_URL` to
  Postgres in deployed environments)
- **Notification Hub (namespace + hub + authorization rule)** — push
  notification delivery to iOS/Android; its connection string is injected into
  the Web App as `AZURE_NOTIFICATION_HUB_CONNECTION_STRING`

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.13
- An Azure subscription and the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli),
  logged in with `az login` (the `azurerm` provider uses your CLI session by default)

## First-time setup

1. **(Recommended) Create remote state storage** so Terraform state isn't only
   on your laptop:

   ```sh
   az group create -n christduell-tfstate-rg -l westeurope
   az storage account create -n christduelltfstate -g christduell-tfstate-rg -l westeurope --sku Standard_LRS
   az storage container create -n tfstate --account-name christduelltfstate
   ```

   Then uncomment the `backend "azurerm"` block in `providers.tf`.

2. **Copy the variables file and fill in your secrets:**

   ```sh
   cp terraform.tfvars.example terraform.tfvars
   ```

   `terraform.tfvars` is gitignored — never commit real credentials.

3. **Initialize, plan, apply:**

   ```sh
   terraform init
   terraform plan
   terraform apply
   ```

## Wiring up CI/CD

After the first `apply`, fetch the values the GitHub Actions deploy workflow
(`.github/workflows/backend-deploy.yml`) needs as repo secrets:

```sh
terraform output container_registry_login_server
az acr credential show --name <acr-name> --query "{user:username, pass:passwords[0].value}"
az ad sp create-for-rbac --name christduell-deploy --role contributor \
  --scopes "$(terraform output -raw resource_group_name | xargs -I{} az group show -n {} --query id -o tsv)" \
  --sdk-auth
```

Map these to the `ACR_LOGIN_SERVER`, `ACR_USERNAME`, `ACR_PASSWORD`,
`AZURE_CREDENTIALS`, and `AZURE_WEBAPP_NAME` secrets in the repo settings.

## Notes

- `postgres_admin_password` and the notification hub connection string are
  marked `sensitive` — use `terraform output -raw notification_hub_connection_string`
  to read them when needed, and prefer a secrets manager (e.g. Azure Key Vault)
  over plain `tfvars` for anything beyond local experimentation.
- Default SKUs (`B1` App Service, `B_Standard_B1ms` Postgres, `Free` Notification
  Hub namespace) are sized for development/testing — bump `app_service_sku` and
  `postgres_sku` before going to production with real users.
