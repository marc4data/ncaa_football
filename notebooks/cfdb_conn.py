"""Notebook connection to the cfdb serving layer.

Imported by the setup cell of every analysis notebook so that connection details live in
one place rather than being retyped (and drifting) per notebook.

WHAT THIS CONNECTS TO
---------------------
The `srv_*` views are the serving layer: denormalized, pre-joined, one row per grain, built
by dbt into the `serving` schema. They exist in three places and this module reaches any of
them by flipping one environment variable:

    postgres    the local transform warehouse (docker compose up -d postgres) -- the
                default, and the only one that needs no secrets
    databricks  the transform warehouse after the M4 cutover, catalog `workspace`
    serving     the droplet's serving Postgres, which the Streamlit site reads

The serving droplet publishes no ports (see src/publish_marts.py), so `serving` only works
from inside the compose network or through an SSH tunnel you opened yourself.

READ-ONLY BY CONSTRUCTION
-------------------------
`q()` refuses anything that is not a single SELECT or WITH. That is a guard against a
mistyped cell, not a security boundary -- point this at a read-only role if you have one.

THE SITE'S SINGLE-TABLE RULE DOES NOT APPLY HERE. site/db.py is held to one `srv_*` table
per query because a Streamlit page must not define metrics. A notebook is exploration, so
join freely; just remember that anything you want the SITE to show has to become a dbt
model, never a query that lives only in a notebook.

Usage
-----
    import cfdb_conn as cf

    cf.check()                                   # what am I connected to?
    cf.tables()                                  # what srv_ views exist?
    cf.columns("srv_standings")                  # what's in one?
    cf.peek("srv_standings")                     # first few rows

    df = cf.q(f'''
        select season, school, wins, losses
        from {cf.t("srv_standings")}
        where season = :season and classification = 'fbs'
    ''', {"season": 2025}, limit=200)
"""
from __future__ import annotations

import os
import re
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

# --------------------------------------------------------------------------------------
# Repo root and .env
#
# Resolved by walking up from THIS FILE rather than from the working directory, so the
# notebook loads the same .env whether it was started from notebooks/, from the repo root,
# or from a Jupyter server rooted somewhere else entirely.
# --------------------------------------------------------------------------------------


def _find_repo_root() -> Path:
    for parent in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (parent / "dbt" / "dbt_project.yml").exists():
            return parent
    return Path(__file__).resolve().parent.parent


REPO_ROOT = _find_repo_root()

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:  # python-dotenv is in requirements.txt; keep the import soft anyway
    pass


# --------------------------------------------------------------------------------------
# Configuration
#
# Env var names are DELIBERATELY THE ONES THE REPO ALREADY USES (PG_*, DATABRICKS_*), so
# one .env serves the ingestion scripts, dbt and this module. Nothing here is new config
# to maintain; the notebook-only knobs are the two CFDB_NOTEBOOK_* ones.
# --------------------------------------------------------------------------------------

BACKEND = os.getenv("CFDB_NOTEBOOK_BACKEND", "postgres").strip().lower()

# The dbt layer schemas (dbt/dbt_project.yml). Serving is what a notebook normally wants;
# marts and staging are here for when you need to see behind a serving view.
SERVING_SCHEMA = os.getenv("CFDB_NOTEBOOK_SCHEMA", "serving")
MARTS_SCHEMA = "marts"
STAGING_SCHEMA = "staging"

# A default ceiling on any query that does not carry its own LIMIT. srv_team_game_log is
# 221,268 rows and srv_player_play is far larger; an accidental unbounded select is slow
# on Postgres and expensive on Databricks. Raise it per call with limit=, or limit=None.
DEFAULT_LIMIT = 5_000

_PG = {
    "postgres": {
        "host": os.getenv("PG_HOST", "localhost"),
        "port": os.getenv("PG_PORT", "5432"),
        "user": os.getenv("PG_USER", "cfdb"),
        "password": os.getenv("PG_PASSWORD", "cfdb"),
        "database": os.getenv("PG_DB", "cfdb"),
    },
    # THE DROPLET'S SERVING POSTGRES, THROUGH AN SSH TUNNEL. The defaults below are the
    # LOCAL end of that tunnel, which is why they are ordinary values and not secrets:
    # 127.0.0.1 is your own machine, and the port is whichever one you forwarded.
    #
    # Nothing here names the droplet. deploy/README.md is explicit that the host is
    # addressed by environment variable and never by a literal -- not because an IP is
    # secret, but because a literal in a repo that may go public is a complete map with no
    # upside. `tunnel_command()` builds the ssh line from those variables instead.
    "remote": {
        "host": os.getenv("CFDB_REMOTE_PG_HOST", "127.0.0.1"),
        "port": os.getenv("CFDB_REMOTE_PG_PORT", "15432"),
        "user": os.getenv("CFDB_REMOTE_PG_USER", "cfdb"),
        "password": os.getenv("CFDB_REMOTE_PG_PASSWORD", "cfdb"),
        "database": os.getenv("CFDB_REMOTE_PG_DB", "cfdb"),
    },
}

_DATABRICKS = {
    "server_hostname": os.getenv("DATABRICKS_SERVER_HOSTNAME", ""),
    "http_path": os.getenv("DATABRICKS_HTTP_PATH", ""),
    "access_token": os.getenv("DATABRICKS_TOKEN", ""),
    "catalog": os.getenv("DATABRICKS_CATALOG", "workspace"),
}


class ConfigError(RuntimeError):
    """Raised with an actionable message when the backend is not configured."""


def _backend() -> str:
    if BACKEND not in ("postgres", "remote", "databricks"):
        raise ConfigError(
            f"CFDB_NOTEBOOK_BACKEND={BACKEND!r} is not one of postgres, remote, databricks"
        )
    return BACKEND


# --------------------------------------------------------------------------------------
# Relation naming
#
# Postgres qualifies with schema; Unity Catalog wants catalog.schema.table. One helper
# hides the difference so a notebook query is portable across both.
# --------------------------------------------------------------------------------------


def t(table: str, schema: Optional[str] = None) -> str:
    """Fully-qualified relation name for the active backend.

        cf.t("srv_standings")                   -> serving.srv_standings
                                                -> workspace.serving.srv_standings
        cf.t("fct_game", cf.MARTS_SCHEMA)       -> marts.fct_game
    """
    schema = schema or SERVING_SCHEMA
    if _backend() == "databricks":
        return f"{_DATABRICKS['catalog']}.{schema}.{table}"
    return f"{schema}.{table}"


# --------------------------------------------------------------------------------------
# Connections
# --------------------------------------------------------------------------------------


@lru_cache(maxsize=None)
def engine():
    """One pooled SQLAlchemy engine per process, for the Postgres backends."""
    from sqlalchemy import create_engine

    name = _backend()
    if name == "databricks":
        raise ConfigError("engine() is Postgres-only; the Databricks backend uses connection()")
    cfg = _PG[name]
    url = (f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}"
           f"@{cfg['host']}:{cfg['port']}/{cfg['database']}")
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})


_DBX_CONN = None


def connection():
    """The Databricks SQL connection, opened lazily and reused.

    The serverless warehouse auto-starts on first query, so an initial call can take ~30s.
    """
    global _DBX_CONN
    from databricks import sql as databricks_sql

    missing = [k for k in ("server_hostname", "http_path", "access_token")
               if not _DATABRICKS[k]]
    if missing:
        env = {"server_hostname": "DATABRICKS_SERVER_HOSTNAME",
               "http_path": "DATABRICKS_HTTP_PATH",
               "access_token": "DATABRICKS_TOKEN"}
        raise ConfigError(
            "Databricks is not configured; set "
            + ", ".join(env[k] for k in missing)
            + f" in {REPO_ROOT / '.env'}"
        )
    if _DBX_CONN is None or not getattr(_DBX_CONN, "open", True):
        _DBX_CONN = databricks_sql.connect(
            server_hostname=_DATABRICKS["server_hostname"],
            http_path=_DATABRICKS["http_path"],
            access_token=_DATABRICKS["access_token"],
            catalog=_DATABRICKS["catalog"],
        )
    return _DBX_CONN


def reset() -> None:
    """Drop cached connections. Call after editing .env, or when a session has gone stale."""
    global _DBX_CONN
    engine.cache_clear()
    if _DBX_CONN is not None:
        try:
            _DBX_CONN.close()
        except Exception:
            pass
        _DBX_CONN = None


# --------------------------------------------------------------------------------------
# Querying
# --------------------------------------------------------------------------------------

# A single SELECT or WITH, and nothing else. Semicolon-separated statements are rejected
# too: `select 1; drop table x` is one string to pandas and two statements to the server.
_READ_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_HAS_LIMIT = re.compile(r"\blimit\s+\d+\s*;?\s*$", re.IGNORECASE)


def _guard(sql: str) -> str:
    stripped = sql.strip().rstrip(";")
    if not _READ_ONLY.match(stripped):
        raise ValueError(
            "cfdb_conn is read-only: q() runs a single SELECT or WITH. "
            f"Got: {stripped.split()[0] if stripped.split() else '(empty)'}"
        )
    if ";" in stripped:
        raise ValueError("cfdb_conn runs one statement at a time; remove the ';'")
    return stripped


def q(sql: str, params: Optional[Dict[str, Any]] = None,
      limit: Optional[int] = DEFAULT_LIMIT) -> pd.DataFrame:
    """Run a read-only query and return a DataFrame.

    Named parameters use `:name` on both backends -- always parameterize rather than
    f-stringing a value in, so a team called O'Brien's does not end the statement.

    `limit` appends a LIMIT when the query does not already carry one. Pass limit=None to
    opt out, which you want for aggregates and should think twice about otherwise.
    """
    statement = _guard(sql)
    if limit is not None and not _HAS_LIMIT.search(statement):
        statement = f"{statement}\nlimit {int(limit)}"

    if _backend() == "databricks":
        frame = _q_databricks(statement, params or {})
    else:
        from sqlalchemy import text
        with engine().connect() as conn:
            frame = pd.read_sql(text(statement), conn, params=params or {})

    if limit is not None and len(frame) == limit:
        warnings.warn(
            f"query returned exactly {limit} rows -- it is probably truncated by the "
            f"default limit. Pass limit= a larger number, or limit=None.",
            stacklevel=2,
        )
    return _numeric(frame)


def _numeric(frame: pd.DataFrame) -> pd.DataFrame:
    """Turn Postgres NUMERIC into float.

    psycopg2 maps NUMERIC to decimal.Decimal to protect precision, which is right for money
    and wrong for everything a notebook does with it: the column arrives as dtype object,
    so `.mean()` is awkward and matplotlib refuses to plot it outright. Every NUMERIC in the
    serving layer is a rate or an average, where float is the honest type -- so convert
    here rather than making each notebook remember `.astype(float)`.
    """
    from decimal import Decimal

    for name in frame.columns[frame.dtypes == object]:
        column = frame[name].dropna()
        if not column.empty and isinstance(column.iloc[0], Decimal):
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
    return frame


def _q_databricks(statement: str, params: Dict[str, Any]) -> pd.DataFrame:
    """Execute on Databricks, retrying once if the cached connection has gone stale."""
    for attempt in (1, 2):
        try:
            with connection().cursor() as cur:
                cur.execute(statement, params or None)
                try:
                    return cur.fetchall_arrow().to_pandas()
                except AttributeError:  # older connector without the arrow path
                    cols = [d[0] for d in cur.description]
                    return pd.DataFrame(cur.fetchall(), columns=cols)
        except Exception:
            if attempt == 2:
                raise
            reset()
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------------------
# Discovery -- what is in the serving layer, without leaving the notebook
# --------------------------------------------------------------------------------------


def tables(schema: Optional[str] = None) -> pd.DataFrame:
    """Every table in a layer schema, with its row count where the engine knows one."""
    schema = schema or SERVING_SCHEMA
    if _backend() == "databricks":
        frame = q(f"show tables in {_DATABRICKS['catalog']}.{schema}", limit=None)
        return frame.rename(columns={"tableName": "table_name"})[["table_name"]] \
                    .sort_values("table_name").reset_index(drop=True)
    return q("""
        select c.relname as table_name,
               c.reltuples::bigint as approx_rows
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = :schema and c.relkind in ('r', 'v', 'm')
        order by c.relname
    """, {"schema": schema}, limit=None)


def columns(table: str, schema: Optional[str] = None) -> pd.DataFrame:
    """Column names, types and -- where dbt persisted them -- descriptions."""
    schema = schema or SERVING_SCHEMA
    if _backend() == "databricks":
        return q(f"describe table {t(table, schema)}", limit=None)
    return q("""
        select a.attname as column_name,
               format_type(a.atttypid, a.atttypmod) as data_type,
               not a.attnotnull as is_nullable,
               col_description(a.attrelid, a.attnum) as description
        from pg_attribute a
        join pg_class c on c.oid = a.attrelid
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = :schema and c.relname = :table
          and a.attnum > 0 and not a.attisdropped
        order by a.attnum
    """, {"schema": schema, "table": table}, limit=None)


def dictionary(table: Optional[str] = None) -> pd.DataFrame:
    """The warehouse's own data dictionary -- srv_data_dictionary, one row per column.

    Preferred over `columns()` when it is built: the descriptions are the dbt schema.yml
    text, so this is the same catalogue the site's Data Dictionary page renders.
    """
    sql = f"""
        select layer, table_name, column_name, ordinal_position, data_type,
               is_nullable, table_description, column_description, description_status
        from {t('srv_data_dictionary')}
    """
    params: Dict[str, Any] = {}
    if table:
        sql += " where table_name = :table"
        params["table"] = table
    sql += " order by table_name, ordinal_position"
    return q(sql, params, limit=None)


def peek(table: str, n: int = 5, schema: Optional[str] = None) -> pd.DataFrame:
    """First n rows of a table. Deliberately unordered -- this is a shape check."""
    # limit=None, then head(n): asking q() for exactly n rows trips its own truncation
    # warning every single time, which would train you to ignore it where it matters.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return q(f"select * from {t(table, schema)}", limit=n).head(n)


def tunnel_command() -> str:
    """The ssh line that opens the tunnel this notebook's `remote` backend reads through.

    Built from environment variables so no droplet address lives in a tracked file:

        CFDB_DROPLET_HOST     root@<droplet>            the box
        CFDB_DROPLET_PG_ADDR  172.19.0.2:5432           serving Postgres ON ITS DOCKER
                                                        NETWORK -- it is not published to
                                                        the droplet's host, which is why
                                                        the forward targets a container IP
                                                        rather than localhost
        CFDB_REMOTE_PG_PORT   15432                     the local end

    Put the first two in the repo-root .env once and this prints a runnable line forever.
    """
    host = os.getenv("CFDB_DROPLET_HOST", "root@<CFDB_DROPLET_HOST unset>")
    remote = os.getenv("CFDB_DROPLET_PG_ADDR", "172.19.0.2:5432")
    local_port = _PG["remote"]["port"]
    return f"ssh -N -L {local_port}:{remote} {host}"


def _diagnose(exc: Exception) -> str:
    """Turn a connection failure into the thing you actually have to do about it."""
    text = str(exc).lower()
    name = _backend()
    if name == "remote" and ("refused" in text or "timeout" in text or "timed out" in text):
        return (
            "The tunnel does not appear to be up. Open it in another terminal and leave it "
            f"running:\n\n    {tunnel_command()}\n\n"
            "It prints nothing when it works -- `-N` means no remote command, so a silent "
            "terminal is the success case."
        )
    if name == "postgres" and "refused" in text:
        return ("The local warehouse is not running:\n\n    docker compose up -d postgres")
    return ""


def freshness() -> pd.DataFrame:
    """When each serving domain's data was last loaded, newest first.

    THE ANSWER TO "IS WHAT I AM LOOKING AT CURRENT". Every serving view carries its own
    `as_of_ts` rather than sharing a global one, deliberately: a four-hourly lines snapshot
    would otherwise make a poll from 1936 look equally fresh. So this reads the stamp off
    several views and lets them disagree, because they legitimately do.
    """
    views = ["srv_team_game_log", "srv_standings", "srv_game", "srv_odds_board",
             "srv_rankings", "srv_data_dictionary"]
    rows = []
    for view in views:
        try:
            frame = q(f"select max(as_of_ts) as as_of from {t(view)}", limit=None)
            rows.append({"view": view, "as_of_ts": frame["as_of"].iloc[0]})
        except Exception as exc:
            rows.append({"view": view, "as_of_ts": pd.NaT, "note": type(exc).__name__})
    out = pd.DataFrame(rows)
    out["as_of_ts"] = pd.to_datetime(out["as_of_ts"], errors="coerce", utc=True)
    return out.sort_values("as_of_ts", ascending=False).reset_index(drop=True)


def check() -> None:
    """Print what this notebook is connected to, and prove it with a live query."""
    name = _backend()
    print(f"repo root : {REPO_ROOT}")
    print(f"backend   : {name}")
    if name == "databricks":
        print(f"catalog   : {_DATABRICKS['catalog']}")
        print(f"host      : {_DATABRICKS['server_hostname'] or '(unset)'}")
    else:
        cfg = _PG[name]
        print(f"target    : {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}")
    print(f"schema    : {SERVING_SCHEMA}")
    try:
        found = tables()
        srv = [x for x in found["table_name"] if x.startswith("srv_")]
        print(f"connected : yes -- {len(srv)} srv_ views visible")
    except ConfigError as exc:
        print(f"connected : NO -- {exc}")
        return
    except Exception as exc:
        print(f"connected : NO -- {type(exc).__name__}: {exc}")
        hint = _diagnose(exc)
        if hint:
            print(f"\n{hint}")
        return

    # HOW OLD IS THIS DATA. Printed on every connect rather than left to be asked for --
    # a stale warehouse answers every query without complaint, and the wrong-but-plausible
    # number is the failure mode a notebook cannot see.
    try:
        stamps = freshness().dropna(subset=["as_of_ts"])
        if not stamps.empty:
            newest = stamps["as_of_ts"].max()
            age = pd.Timestamp.now(tz="UTC") - newest
            print(f"data as of: {newest:%Y-%m-%d %H:%M} UTC "
                  f"({age.days}d {age.seconds // 3600}h ago), newest of "
                  f"{len(stamps)} domains")
    except Exception:
        pass  # a warehouse without as_of_ts is a valid state, not an error
