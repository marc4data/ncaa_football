#!/usr/bin/env bash
#
# The ONLY thing the Airflow publish key can do on the droplet.
#
# Installed at /usr/local/bin/cfdb_publish.sh, owned by root, mode 0755, and named as a
# forced command in ~cfdb_publish/.ssh/authorized_keys:
#
#   command="/usr/local/bin/cfdb_publish.sh",no-pty,no-port-forwarding,
#   no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... airflow-publish-only
#
# WHY THIS EXISTS AT ALL. Publishing used to run as root over SSH, executing
# `docker compose exec postgres psql`. Two separate problems with that:
#
#   1. A key that can open a root shell is a key that can do anything, and it lived in a
#      scheduler that runs code from a repository.
#   2. Docker socket access IS root. `docker run -v /:/host` and you own the box. So a
#      "restricted" publish user in the docker group would have been theatre.
#
# The fix is that this script never touches Docker. Postgres is bound to 127.0.0.1:5433 and
# reached with psql, so the publish identity's blast radius is the serving database — which
# is precisely what publishing does. The forced command is the second layer: even holding
# the key, the client cannot choose what runs.
#
# THE INTERFACE IS AN ALLOWLIST, NOT A PASSTHROUGH. An earlier sketch had an `sql <text>`
# verb, which would have handed back the arbitrary execution the forced command exists to
# remove. Every verb here is fixed; the only client-supplied values are identifiers, and
# they are validated against a strict pattern before reaching psql.
#
# Verbs, chosen via SSH_ORIGINAL_COMMAND:
#
#   ensure-schema <schema>          CREATE SCHEMA IF NOT EXISTS
#   restore <schema>                stream a pg_dump on stdin into the database
#   grant <schema> <role>           re-grant SELECT to the read-only role
#   count <schema> <table>          row count, for post-publish verification
#   ping                            confirm the key and the database both work
#
set -euo pipefail
umask 077

export PGHOST="${CFDB_PGHOST:-127.0.0.1}"
export PGPORT="${CFDB_PGPORT:-5433}"

# Database and role from a 0600 file owned by this user; the password from ~/.pgpass, also
# 0600. Neither is ever an argument — an argument is visible in `ps` to every user on the
# box for the life of the call, and a publish runs for minutes.
#
# Sourced rather than baked in so rotating the serving credentials is a file edit and not a
# redeploy of this script.
PG_ENV="${HOME}/.pg_env"
if [[ -r "$PG_ENV" ]]; then
    # shellcheck disable=SC1090
    set -a; . "$PG_ENV"; set +a
fi
: "${PGDATABASE:?PGDATABASE is not set; ~/.pg_env is missing or unreadable}"
: "${PGUSER:?PGUSER is not set; ~/.pg_env is missing or unreadable}"
export PGDATABASE PGUSER

PSQL=(psql -v ON_ERROR_STOP=1 -q --no-psqlrc)

refuse() {
    echo "cfdb_publish: refused: $*" >&2
    exit 1
}

# Identifiers only. Rejecting rather than quoting is deliberate: quoting correctly is
# subtle, and cfdb has never had a schema or table that needs it.
valid_ident() {
    [[ "$1" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || refuse "not a valid identifier: $1"
}

read -r -a ARGS <<< "${SSH_ORIGINAL_COMMAND:-}"
VERB="${ARGS[0]:-}"

case "$VERB" in
    ping)
        "${PSQL[@]}" -tAc 'select 1' >/dev/null
        echo "cfdb_publish: ok"
        ;;

    ensure-schema)
        schema="${ARGS[1]:-}"; valid_ident "$schema"
        "${PSQL[@]}" -c "CREATE SCHEMA IF NOT EXISTS ${schema}"
        ;;

    restore)
        schema="${ARGS[1]:-}"; valid_ident "$schema"
        # The dump arrives on stdin and carries --clean --if-exists, so this replaces each
        # table rather than appending. Marts are derived data; a blunt replace is always
        # safe and is the reason no merge logic exists here.
        "${PSQL[@]}"
        ;;

    grant)
        schema="${ARGS[1]:-}"; valid_ident "$schema"
        role="${ARGS[2]:-}";   valid_ident "$role"
        # --clean drops and recreates each table, and a recreated table does not inherit
        # the old one's grants. Without this the site breaks on the first republish with a
        # permission error that looks like a database fault and is a publish-job fault.
        "${PSQL[@]}" \
            -c "GRANT USAGE ON SCHEMA ${schema} TO \"${role}\"" \
            -c "GRANT SELECT ON ALL TABLES IN SCHEMA ${schema} TO \"${role}\"" \
            -c "ALTER DEFAULT PRIVILEGES IN SCHEMA ${schema} GRANT SELECT ON TABLES TO \"${role}\""
        ;;

    count)
        schema="${ARGS[1]:-}"; valid_ident "$schema"
        table="${ARGS[2]:-}";  valid_ident "$table"
        "${PSQL[@]}" -tAc "select count(*) from ${schema}.${table}"
        ;;

    *)
        refuse "unknown verb '${VERB}'. This key runs a fixed set of publish steps and \
nothing else."
        ;;
esac
