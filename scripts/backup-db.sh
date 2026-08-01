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

# App Service exposes the /home Azure Files share through the Kudu VFS endpoint.
KUDU_BASE="https://${WEBAPP_NAME}.scm.azurewebsites.net/api/vfs/home"

az rest --method GET --url "$KUDU_BASE/christduell.db" \
  --headers "Accept=application/octet-stream" --output-file "$DEST"

# The database runs in WAL mode, so recent commits may live in the -wal file
# rather than the main one. Copying only christduell.db can therefore lose the
# newest writes; fetch its companions too so SQLite can recover the full state.
# They may legitimately be absent right after a checkpoint.
for suffix in "-wal" "-shm"; do
  az rest --method GET --url "$KUDU_BASE/christduell.db${suffix}" \
    --headers "Accept=application/octet-stream" \
    --output-file "${DEST}${suffix}" 2>/dev/null \
    || rm -f "${DEST}${suffix}"
done

echo "Saved to $DEST"
echo "Size: $(du -h "$DEST" | cut -f1)"

# Prove the copy is readable rather than discovering it during a restore.
if command -v sqlite3 >/dev/null 2>&1; then
  if sqlite3 "$DEST" "pragma quick_check;" | grep -qx "ok"; then
    echo "Integrity check: ok ($(sqlite3 "$DEST" 'select count(*) from player') players, \
$(sqlite3 "$DEST" 'select count(*) from question') questions)"
  else
    echo "WARNING: the downloaded database did not pass its integrity check" >&2
    exit 1
  fi
else
  echo "Note: install sqlite3 to have this script verify the backup."
fi
