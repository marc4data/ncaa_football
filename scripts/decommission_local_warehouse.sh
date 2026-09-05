#!/usr/bin/env bash
#
# Decommission the cfdb warehouse from the LOCAL Postgres instance.
#
# The laptop stack was the pipeline until 2026-08-27..30, when it moved to the droplet.
# It has been a paused rollback since. This removes cfdb from it while KEEPING the
# Postgres instance itself, and keeping the local Airflow metadata database.
#
# WHY A DATABASE DROP RATHER THAN FOUR SCHEMA DROPS
# cfdb and airflow live in SEPARATE DATABASES on this instance, so `drop database cfdb`
# removes raw/staging/marts/serving atomically and cannot touch airflow. Dropping the four
# schemas one at a time is slower, fights locks, and can leave partial state on failure.
#
# WHY THE `cfdb` ROLE SURVIVES  <-- the important one
# `cfdb` is this instance's ONLY superuser, and it OWNS the `airflow` and `postgres`
# databases. Dropping it would leave the instance with no superuser login, and
# `drop owned by cfdb` inside the airflow database would delete every Airflow table.
# The name is a historical artefact, not a reason to remove the account. Only the
# genuinely cfdb-specific, non-superuser role `cfdb_read` is dropped.
#
# Default is a dry run. Pass --apply to execute.
set -euo pipefail

CONTAINER="claude_code-postgres-1"
DB="cfdb"
KEEP_DB="airflow"
DROP_ROLE="cfdb_read"
KEEP_ROLE="cfdb"
BACKUP_DIR="${HOME}/cfdb_decommission_backup"

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

say() { printf '%s\n' "$*"; }
run() { docker exec -i "$CONTAINER" psql -U "$KEEP_ROLE" -v ON_ERROR_STOP=1 "$@"; }
val() { docker exec -i "$CONTAINER" psql -U "$KEEP_ROLE" -At "$@"; }

# --- guards ---------------------------------------------------------------
# Addressing the server by CONTAINER NAME rather than host:port is itself the guard
# against the failure that matters: a forwarded local port pointing at the droplet.
# `docker exec` can only reach a container on this machine.
docker inspect "$CONTAINER" >/dev/null 2>&1 || { say "FATAL: no container $CONTAINER"; exit 1; }
[[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" == "true" ]] \
  || { say "FATAL: $CONTAINER is not running"; exit 1; }

schemas=$(val -d "$DB" -c "select count(*) from information_schema.schemata
                           where schema_name in ('raw','staging','marts','serving');")
[[ "$schemas" -ge 3 ]] || { say "FATAL: only $schemas/4 warehouse schemas — wrong server?"; exit 1; }

# The droplet has no local Airflow metadata DB; this instance does. A second, independent
# check that we are pointed at the laptop.
has_airflow=$(val -d postgres -Atc "select count(*) from pg_database where datname='$KEEP_DB';")
[[ "$has_airflow" == "1" ]] || { say "FATAL: no '$KEEP_DB' database — wrong server?"; exit 1; }

size=$(val -d postgres -c "select pg_size_pretty(pg_database_size('$DB'));")
af_before=$(val -d "$KEEP_DB" -c "select count(*) from information_schema.tables where table_schema='public';")

say "container ......... $CONTAINER"
say "drop database ..... $DB ($size, $schemas/4 warehouse schemas)"
say "drop role ......... $DROP_ROLE"
say "KEEP database ..... $KEEP_DB ($af_before tables)"
say "KEEP role ......... $KEEP_ROLE (superuser; owns $KEEP_DB and postgres)"
say "backup ............ $BACKUP_DIR"

if [[ "$APPLY" -eq 0 ]]; then
  say ""
  say "DRY RUN — nothing changed. Re-run with --apply to execute."
  exit 0
fi

# --- backup ---------------------------------------------------------------
# The droplet warehouse is a proven superset of this database, so this dump is insurance
# against a mistake in THIS script, not against data loss. Delete it once satisfied.
mkdir -p "$BACKUP_DIR"
stamp=$(date +%Y%m%d-%H%M%S)
dump="$BACKUP_DIR/cfdb-local-$stamp.dump"
say ""
say "dumping $DB -> $dump"
docker exec -i "$CONTAINER" pg_dump -U "$KEEP_ROLE" -d "$DB" -Fc | cat > "$dump"
say "dump size: $(du -h "$dump" | cut -f1)"

# --- drop -----------------------------------------------------------------
# WITH (FORCE) terminates the idle connections the paused Airflow pool holds open;
# without it the drop blocks indefinitely on them. Postgres 13+.
say "dropping database $DB"
run -d postgres -c "drop database $DB with (force);"

say "dropping role $DROP_ROLE"
run -d postgres -c "drop role if exists $DROP_ROLE;"

# --- verify ---------------------------------------------------------------
say ""
say "verifying"
gone=$(val -d postgres -c "select count(*) from pg_database where datname='$DB';")
role_gone=$(val -d postgres -c "select count(*) from pg_roles where rolname='$DROP_ROLE';")
af_after=$(val -d "$KEEP_DB" -c "select count(*) from information_schema.tables where table_schema='public';")
su=$(val -d postgres -c "select rolsuper from pg_roles where rolname='$KEEP_ROLE';")

fail=0
[[ "$gone" == "0" ]]            || { say "  FAIL: database $DB still present"; fail=1; }
[[ "$role_gone" == "0" ]]       || { say "  FAIL: role $DROP_ROLE still present"; fail=1; }
[[ "$af_after" == "$af_before" ]] || { say "  FAIL: $KEEP_DB tables $af_before -> $af_after"; fail=1; }
[[ "$su" == "t" ]]              || { say "  FAIL: $KEEP_ROLE is no longer superuser"; fail=1; }

if [[ "$fail" -eq 0 ]]; then
  say "  database $DB .......... gone"
  say "  role $DROP_ROLE ......... gone"
  say "  database $KEEP_DB ....... intact ($af_after tables)"
  say "  role $KEEP_ROLE ............ intact (superuser)"
  say ""
  say "Done. Backup kept at $dump — delete it when you are satisfied."
else
  say ""
  say "VERIFICATION FAILED — restore from $dump"
  exit 1
fi
