#!/usr/bin/env bash
# Downloads the SQLite database from the Azure Web App to a local backup file.
#
# Usage:
#   ./scripts/backup-db.sh                          # auto-detects app name from Terraform
#   WEBAPP_NAME=my-app ./scripts/backup-db.sh       # explicit override
#
# Prerequisites: az CLI logged in, terraform state present (or WEBAPP_NAME set).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$REPO_ROOT/backups"

# Resolve webapp name from Terraform output if not set explicitly.
if [[ -z "${WEBAPP_NAME:-}" ]]; then
  WEBAPP_NAME=$(cd "$REPO_ROOT/infra" && terraform output -raw backend_url \
    | sed 's|https://||' | cut -d'.' -f1)
fi

RESOURCE_GROUP=$(cd "$REPO_ROOT/infra" && terraform output -raw resource_group_name)

mkdir -p "$BACKUP_DIR"
DEST="$BACKUP_DIR/christduell-$(date +%Y%m%d-%H%M%S).db"

echo "Downloading /home/christduell.db from $WEBAPP_NAME ..."

# App Service exposes the /home Azure Files share via the Kudu REST API.
az webapp deploy \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME" \
  --src-path /dev/null \
  --type static \
  --clean false \
  --async false 2>/dev/null || true

# Use the Kudu VFS endpoint to download the file directly.
KUDU_URL="https://${WEBAPP_NAME}.scm.azurewebsites.net/api/vfs/home/christduell.db"
az rest \
  --method GET \
  --url "$KUDU_URL" \
  --headers "Accept=application/octet-stream" \
  --output-file "$DEST"

echo "Saved to $DEST"
echo "Size: $(du -h "$DEST" | cut -f1)"
