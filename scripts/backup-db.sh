#!/usr/bin/env bash
# Takes an off-site dump of the production PostgreSQL database.
#
# Azure already keeps automatic backups with point-in-time restore (see
# postgres_backup_retention_days in infra/), so this is not the primary safety
# net — it is the copy you hold yourself, for migrations, for local debugging on
# real data, and for the case where the whole subscription is unavailable.
#
# Usage:
#   ./scripts/backup-db.sh                    # reads the connection from Terraform
#   DATABASE_URL=postgresql://... ./scripts/backup-db.sh
#
# Prerequisites: pg_dump (brew install libpq), and either DATABASE_URL or a
# Terraform state you can read.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$REPO_ROOT/backups"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "Reading the connection string from Terraform ..."
  DATABASE_URL=$(cd "$REPO_ROOT/infra" && terraform output -raw database_url)
fi

# The app uses SQLAlchemy's driver-qualified scheme; pg_dump wants the plain one.
DUMP_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump not found. On macOS: brew install libpq && brew link --force libpq" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
DEST="$BACKUP_DIR/christduell-$(date +%Y%m%d-%H%M%S).dump"

echo "Dumping to $DEST ..."
# Custom format: compressed, and restorable selectively with pg_restore.
pg_dump --format=custom --no-owner --no-privileges --file="$DEST" "$DUMP_URL"

echo "Saved to $DEST"
echo "Size: $(du -h "$DEST" | cut -f1)"

# A dump you have never read is a hope, not a backup.
if pg_restore --list "$DEST" > /dev/null 2>&1; then
  TABLES=$(pg_restore --list "$DEST" | grep -c "TABLE DATA" || true)
  echo "Verified: readable archive containing $TABLES table(s) of data."
else
  echo "WARNING: the dump could not be read back by pg_restore" >&2
  exit 1
fi

echo
echo "Restore with:"
echo "  pg_restore --clean --if-exists --no-owner --dbname=\"\$DATABASE_URL\" \"$DEST\""
