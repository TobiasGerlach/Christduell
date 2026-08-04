#!/usr/bin/env bash
# Runs the backend test suite against a real PostgreSQL.
#
# Production runs Postgres and development runs SQLite, so "it passed locally"
# is not evidence the deployment works. This starts a throwaway cluster, runs
# the suite against it, and removes it again. Nothing touches any Postgres you
# already have — it uses its own data directory and port.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PG_TEST_PORT:-55433}"
PGDATA="${TMPDIR:-/tmp}/christduell-pgtest-$PORT"

for candidate in /opt/homebrew/opt/postgresql@*/bin /usr/local/opt/postgresql@*/bin /usr/lib/postgresql/*/bin; do
  [[ -x "$candidate/initdb" ]] && PG_BIN="$candidate" && break
done
PG_BIN="${PG_BIN:-$(dirname "$(command -v initdb 2>/dev/null || echo /nonexistent/x)")}"

if [[ ! -x "$PG_BIN/initdb" ]]; then
  echo "PostgreSQL not found. macOS: brew install postgresql@16" >&2
  echo "Alternatively point the suite at any Postgres yourself:" >&2
  echo "  TEST_DATABASE_URL=postgresql+psycopg://user@host/db uv run --project backend pytest" >&2
  exit 1
fi

cleanup() {
  "$PG_BIN/pg_ctl" -D "$PGDATA" stop -m immediate >/dev/null 2>&1 || true
  rm -rf "$PGDATA"
}
trap cleanup EXIT

echo "Starting a temporary PostgreSQL on port $PORT ..."
rm -rf "$PGDATA"
"$PG_BIN/initdb" -D "$PGDATA" -U christduell --auth=trust >/dev/null
"$PG_BIN/pg_ctl" -D "$PGDATA" -o "-p $PORT -h 127.0.0.1" -l "$PGDATA/server.log" start >/dev/null

for _ in $(seq 1 30); do
  "$PG_BIN/pg_isready" -h 127.0.0.1 -p "$PORT" >/dev/null 2>&1 && break
  sleep 0.5
done

# Two databases: pytest builds its schema with create_all, so letting Alembic
# loose on the same one would collide with the leftovers.
"$PG_BIN/psql" -h 127.0.0.1 -p "$PORT" -U christduell -d postgres \
  -c "create database christduell_test;" \
  -c "create database christduell_migrations;" >/dev/null

export TEST_DATABASE_URL="postgresql+psycopg://christduell@127.0.0.1:$PORT/christduell_test"
echo "Running the suite against $TEST_DATABASE_URL"
cd "$REPO_ROOT/backend" && uv run pytest -q

echo
echo "Checking the migrations apply, roll back and reapply on Postgres ..."
# The reapply is the point: a downgrade that leaves enum types behind passes a
# single upgrade and fails the moment you roll a deployment back and forward.
export DATABASE_URL="postgresql+psycopg://christduell@127.0.0.1:$PORT/christduell_migrations"
uv run alembic upgrade head >/dev/null
uv run alembic downgrade base >/dev/null
uv run alembic upgrade head >/dev/null
uv run alembic check
echo "Migrations round-trip cleanly."
