#!/usr/bin/env bash
# Nightly serving-database backup (register item: "serving-db backups on the droplet").
#
# pg_dump into a dated file, keep 14 days. The serving database is rebuildable from the
# warehouse, so this is convenience rather than the last line of defence — but restoring
# from a dump is minutes and rebuilding is a full publish cycle.
set -euo pipefail

STACK_DIR="/opt/cfdb"
KEEP_DAYS=14
STAMP=$(date -u +%Y-%m-%dT%H-%M-%SZ)
OUT="/opt/cfdb/backups/cfdb-${STAMP}.sql.gz"

cd "$STACK_DIR"
# --clean --if-exists makes the dump restorable over an existing database.
docker compose exec -T postgres pg_dump -U "${SERVING_PG_USER:-cfdb}" \
  --clean --if-exists "${SERVING_PG_DB:-cfdb}" | gzip > "$OUT"

# A zero-length or trivially small dump means failure; fail loudly rather than rotating
# good backups out in favour of an empty one.
SIZE=$(stat -c%s "$OUT")
if [ "$SIZE" -lt 1000 ]; then
  echo "ERROR: backup is only ${SIZE} bytes — treating as failed" >&2
  rm -f "$OUT"
  exit 1
fi

find /opt/cfdb/backups -name 'cfdb-*.sql.gz' -mtime +${KEEP_DAYS} -delete
echo "backup ok: $OUT ($((SIZE/1024)) KiB)"
