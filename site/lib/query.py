"""The only way this app talks to a database.

Enforces the three architecture rules in code rather than in review (§0.1):

  G-1  serving and nothing else            — the relation must start `srv_`
  G-2  one relation per query, no joins    — rejected before it reaches the database
  G-3  no metric arithmetic in the app     — cannot be enforced here, but nothing in this
                                             module computes anything either

Violations raise at call time rather than returning a wrong answer quietly. A page that
tries to join has a serving-view change request, not a bug to work around.
"""
import os
import re
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

FORBIDDEN = re.compile(r"\b(join|union|insert|update|delete|drop|create|alter|grant)\b",
                       re.IGNORECASE)
RELATION = re.compile(r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_.]*)", re.IGNORECASE)
HAS_LIMIT = re.compile(r"\blimit\s+\d+", re.IGNORECASE)


class QueryContractError(Exception):
    """The query broke one of the architecture rules."""


@st.cache_resource
def engine():
    user = os.getenv("CFDB_READ_USER", "cfdb_read")
    password = os.getenv("CFDB_READ_PASSWORD", "")
    host = os.getenv("SERVING_PG_HOST", os.getenv("PG_HOST", "localhost"))
    port = os.getenv("SERVING_PG_PORT", os.getenv("PG_PORT", "5432"))
    database = os.getenv("SERVING_PG_DB", os.getenv("PG_DB", "cfdb"))
    return create_engine(
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}",
        pool_pre_ping=True)


def check_contract(sql: str) -> str:
    """Validate a query against G-1/G-2 and AC-G.39. Returns the relation it reads."""
    if FORBIDDEN.search(sql):
        raise QueryContractError(
            "Query contains a join or a write. Every query reads exactly one serving view; "
            "if a page needs two things side by side, that is a serving-view change.")
    # A comma in the FROM clause is a join in older syntax and slips past the keyword
    # check entirely — `from srv_x, srv_y` reads two relations and looks like one.
    from_clause = re.split(r"\b(where|group\s+by|order\s+by|limit)\b", sql,
                           flags=re.IGNORECASE)[0]
    from_clause = from_clause[from_clause.lower().rfind(" from ") + 6:] \
        if " from " in from_clause.lower() else ""
    if "," in from_clause:
        raise QueryContractError(
            "FROM clause names more than one relation (comma join). Exactly one serving "
            "view per query (G-2).")
    relations = RELATION.findall(sql)
    if len(relations) != 1:
        raise QueryContractError(
            f"Query names {len(relations)} relations; exactly one is allowed (AC-G.3).")
    relation = relations[0].split(".")[-1]
    if not relation.startswith("srv_"):
        raise QueryContractError(
            f"Query reads `{relation}`. The site reads serving and nothing else (G-1).")
    if not HAS_LIMIT.search(sql):
        raise QueryContractError(
            "Query has no explicit LIMIT (AC-G.39). An unbounded select is a defect even "
            "where today's filter happens to make it small.")
    return relation


def cache_ttl() -> int:
    """300 s inside the live scoring window, 3600 s outside it (AC-G.37).

    Driven by the SAME cadence configuration the lines DAG uses — the file is shipped into
    the image rather than the rule being restated here, because a duplicated season window
    is a rule that will disagree with itself in November.
    """
    try:
        import json
        from pathlib import Path
        config = json.loads(
            (Path(__file__).resolve().parent / "lines_cadence.json").read_text())
        today = datetime.now(timezone.utc).date()
        start = datetime.fromisoformat(config["first_game_date"]).date()
        end = datetime.fromisoformat(config["season_end_date"]).date()
        return 300 if start <= today <= end else 3600
    except Exception:                                            # noqa: BLE001
        # A missing config must not make the site uncacheable; the conservative choice is
        # the shorter TTL, which is stale less often at the cost of more queries.
        return 300


@st.cache_data(ttl=3600, show_spinner=False)
def _run(sql: str, params: dict) -> pd.DataFrame:
    with engine().connect() as connection:
        return pd.read_sql(text(sql), connection, params=params)


def query(sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    """Run a contract-checked query, cached on the full parameter set (AC-G.36)."""
    check_contract(sql)
    return _run(sql, params or {})
