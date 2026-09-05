"""What CFBD serves, what we fetch, what we land, and what we actually expose.

WHY THIS EXISTS. Until now the answer to "how much of the API is in the warehouse" was a
number someone counted by hand, differently each time. The pipeline was streamlined toward one
website, and streamlining is invisible from the inside: every DAG is green, every page renders,
and the fields nobody's page happened to need were never fetched, never unnested, and never
missed. `stg_games` reads nineteen of the forty-one fields the spec publishes for /games; the
twenty-two it drops include both conference names, both line-score arrays and every Elo
column, and nothing anywhere said so.

So this walks four sources and writes one table:

    the spec         config/api-docs.json — what the API serves (the denominator)
    the registry     src/endpoints.py     — what we have decided to fetch
    the raw layer    warehouse or data/raw — what has actually landed
    dbt staging      dbt/models/staging/  — what is exposed as columns

Run it:

    python -m src.coverage_matrix                 # writes docs/cfbd_coverage.md
    python -m src.coverage_matrix --check         # exit 1 if the committed doc is stale

ON THE FIELD COUNTS. "Unnested" is decided by matching the leaf name of each spec field path
against the keys the staging SQL passes to the `json_get_*` macros. That is a heuristic and it
is stated in the output, because the alternative — matching full dot-paths — reports zero
coverage for every endpoint whose payload nests, which is most of the interesting ones. Leaf
matching can overcount when a nested object repeats a name; it cannot miss a field that is
genuinely exposed. For a document whose job is to find gaps, erring toward "covered" keeps it
honest about how big the gap is.
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.data_dictionary.spec import Spec
from src.endpoints import BY_PATH, Endpoint

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "config" / "api-docs.json"
STAGING_DIR = ROOT / "dbt" / "models" / "staging"
RAW_DIR = ROOT / "data" / "raw"
OUTPUT = ROOT / "docs" / "cfbd_coverage.md"

# Raw tables that are ours, not CFBD's — pipeline telemetry that lands in the same schema
# because it goes through the same loader. They have staging models and no endpoint, and
# counting them as coverage would flatter the number.
OPS_TABLES = {"raw_manifest", "raw_dbt_test_result", "raw_deploy_status",
              "raw_model_prediction", "raw_warehouse_usage"}

# Aliases in the staging SQL that name the HTTP envelope rather than the payload. `params` is
# the request; `content` is the response wrapper whose `data` key holds the body. Counting
# either as an unnested field would credit us for reading our own bookkeeping.
ENVELOPE_ALIASES = {"params", "content"}

# The first argument is normally a quoted column alias — json_get_string('team', 'school').
# It can also be a bare Jinja VARIABLE holding a built expression, as in the CFP matchup
# model's `json_get_string(slot, 'seed')` where `slot` is an array element resolved in a
# {% set %}. Accepting both spellings matters: reading only the quoted form reported
# /playoffs/cfp/games as 17 of 19 when `seed` was exposed as slot_1_seed and slot_2_seed.
#
# The alias may also be QUALIFIED — `json_get_string('r.b', 'lineYards')` in the advanced
# box score, where eight blocks are joined and each needs its table alias. That is why the
# pattern allows a dot.
#
# Same failure direction each time, and this is the third instance: undercounting invents a
# hole that is not there and sends the next person to rewrite a finished model. The pattern
# to watch for is any new way of naming the first argument — a variable, a qualified column,
# a macro result — each of which has cost a round of confusion before being allowed here.
FIELD_ACCESS = re.compile(
    r"json_get_(?:string|nested_string|object|array_element_string)\("
    r"\s*'?([a-z_][a-z0-9_.]*)'?\s*,\s*(\[[^\]]*\]|'[^']*')")
SOURCE_REF = re.compile(r"source\(\s*'raw'\s*,\s*'([a-z0-9_]+)'\s*\)")

# Jinja `{% set %}` blocks, and the quoted tokens inside them.
#
# THE REGEX ABOVE READS STRING LITERALS PASSED TO THE JSON MACROS, AND THAT STOPPED BEING THE
# WHOLE PICTURE. The advanced-stats models generate offense and defense from one list —
# `json_get_nested_string('row_json', [side, metric])` — so the field names live in a `set`
# block and never appear as a literal argument. The matrix read those models as 6 of 20 and 4
# of 25 when they in fact expose every field.
#
# That is the failure direction this document must not have. Undercounting looks like a gap
# that is not there and sends the next person to rewrite a model that is already complete;
# it also makes the headline number wrong in a way that is invisible unless you happen to
# check one model by hand. A token inside a `set` list in these models IS a field name by
# construction, so reading them is not a heuristic stretched further — it is reading the same
# information from where the model actually keeps it.
JINJA_SET = re.compile(r"{%-?\s*set\s.*?%}", re.S)
QUOTED = re.compile(r"'([A-Za-z_][A-Za-z0-9_]*)'")

# Field names can also live in a MACRO the model calls. The five passing models share
# thirteen measures via `passing_metrics()` in dbt/macros/passing.sql, defined once so they
# cannot drift apart — which is the right thing to do and made the names invisible to a
# reader that only opens model files.
#
# THIS IS THE FOURTH SHAPE THIS MATCHER HAS MISSED, and they share a root: it infers what a
# model reads from the text of one file, so anything that moves a name out of that file —
# into a loop variable, a qualified alias, or a macro — disappears. Each time the symptom was
# the same, a completed model reported as a gap.
MACRO_DIR = ROOT / "dbt" / "macros"
MACRO_CALL = re.compile(r"\b([a-z_][a-z0-9_]*)\(\s*\)")
MACRO_DEF = re.compile(r"{%-?\s*macro\s+([a-z_][a-z0-9_]*)\s*\(.*?{%-?\s*endmacro", re.S)

# An endpoint whose entire response is a bare array of scalars — /stats/categories. The spec
# flattener has no key to name, so it emits this sentinel. There is no field to unnest: a
# model that reads the endpoint at all has read all of it.
SCALAR_SENTINEL = "(scalar)"

# Endpoints that are partial ON PURPOSE, with the reason. Without this the gap table reads
# "26 fields dropped" and sends the next person to unnest a composite whose parts are already
# modelled somewhere better — which is the same wasted trip the status column exists to
# prevent, one level down.
#
# The bar for an entry is high: the fields must be genuinely exposed elsewhere, from the
# endpoint that owns them. This is not a place to retire awkward work.
PARTIAL_BY_DESIGN = {
    "playoffs/cfp":
        "COMPOSITE. Its `participants[]` is what /playoffs/cfp/participants serves and its "
        "`rounds[].matchups[]` is what /playoffs/cfp/games serves — both fully modelled from "
        "the endpoints that own them. Unnesting them here as well would put the same rows in "
        "two places from sources that can drift between fetches, with no way to say which is "
        "right. stg_cfp_bracket holds what only this endpoint has: the format, field size, "
        "status and champion.",
}


@dataclass
class Row:
    path: str
    endpoint: Optional[Endpoint]
    landed: bool
    row_count: Optional[int]
    models: List[str]
    fields_available: int
    fields_unnested: int
    missing_fields: List[str]

    @property
    def registered(self) -> bool:
        return self.endpoint is not None

    @property
    def swept(self) -> bool:
        return bool(self.endpoint and self.endpoint.include)

    @property
    def status(self) -> str:
        """The one column a reader scans. Ordered by how far from usable it is."""
        if not self.registered:
            return "unregistered"
        if not self.landed:
            return "no raw data"
        if not self.models:
            return "raw only"
        if self.fields_unnested < self.fields_available:
            return "partial"
        return "complete"


def macro_tokens() -> Dict[str, Set[str]]:
    """Macro name -> the quoted tokens in its body.

    Only zero-argument macros matter here: those are the ones used to share a field list.
    """
    tokens: Dict[str, Set[str]] = {}
    if not MACRO_DIR.exists():
        return tokens
    for path in sorted(MACRO_DIR.glob("*.sql")):
        text = path.read_text()
        for match in MACRO_DEF.finditer(text):
            tokens[match.group(1)] = set(QUOTED.findall(match.group(0)))
    return tokens


def staging_models() -> Dict[str, Dict[str, Set[str]]]:
    """raw table name -> {model name -> the payload keys that model reads}."""
    by_table: Dict[str, Dict[str, Set[str]]] = {}
    macros = macro_tokens()
    for sql_file in sorted(STAGING_DIR.glob("*.sql")):
        text = sql_file.read_text()
        keys: Set[str] = set()
        for alias, argument in FIELD_ACCESS.findall(text):
            if alias in ENVELOPE_ALIASES:
                continue
            if argument.startswith("["):
                parts = re.findall(r"'([^']+)'", argument)
                if parts:
                    keys.add(parts[-1])
            else:
                keys.add(argument.strip("'"))
        # Field names the model builds by looping over a list rather than naming inline.
        for block in JINJA_SET.findall(text):
            keys |= set(QUOTED.findall(block))
        # Field names the model gets from a shared macro rather than declaring itself.
        for name in set(MACRO_CALL.findall(text)):
            keys |= macros.get(name, set())
        for table in SOURCE_REF.findall(text):
            by_table.setdefault(table, {})[sql_file.stem] = keys
    return by_table


def landed_from_database() -> Dict[str, int]:
    """Raw table -> row count, straight from the warehouse. Raises if it cannot be reached.

    OPT-IN, AND IT NEVER FALLS BACK. Since the migration the real warehouse runs on the
    droplet and is not published off it, while port 5432 on this laptop still answers — that
    is the PAUSED stack, the M3 rollback. A generator that connected to whatever responded
    would stamp months-old counts as "the warehouse" and be believed, which is the same
    mistake as reading the database and calling it a working website.

    So the caller asks for this explicitly with --warehouse, and if it is not there the run
    fails instead of quietly answering from somewhere else.
    """
    import psycopg2
    # One place resolves the warehouse target, and one place refuses a default that
    # cannot work (R-312). Rolling our own getenv here is how it drifted before.
    from src.load_raw_to_postgres import pg_params
    connection = psycopg2.connect(
        connect_timeout=10, **pg_params())
    counts: Dict[str, int] = {}
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute("select table_name from information_schema.tables "
                           "where table_schema = 'raw'")
            tables = [name for (name,) in cursor.fetchall()]
            for table in tables:
                # Successful responses only, matching landed_from_directory. A table holding
                # nothing but 400s is not an endpoint whose data nobody reads.
                cursor.execute(
                    "select count(*) from information_schema.columns where "
                    "table_schema = 'raw' and table_name = %s and column_name = 'status_code'",
                    (table,))
                has_status = cursor.fetchone()[0] > 0
                if has_status:
                    cursor.execute(f'select count(*) from raw."{table}" '
                                   f'where status_code = 200')
                else:
                    cursor.execute(f'select count(*) from raw."{table}"')
                found = cursor.fetchone()[0]
                if found:
                    counts[table] = found
    finally:
        connection.close()
    return counts


def landed_from_directory() -> Dict[str, int]:
    """Raw key -> number of SUCCESSFUL response files on disk, as the offline fallback.

    SUCCESSFUL, NOT MERELY PRESENT. Counting files made an endpoint that has only ever
    returned errors look like one whose data nobody reads. /coaches/tenures is exactly that:
    both landed files are 400s — "coachId or team is required" — and the matrix reported it
    as `raw only`, which sends the reader off to write a staging model over an empty table.

    The distinction matters for the status column: "landed, nothing reads it" is a modelling
    task, while "registered, never fetched" is a backfill task, and they were being conflated
    in the one direction that wastes the most time.
    """
    if not RAW_DIR.exists():
        return {}
    counts: Dict[str, int] = {}
    for directory in sorted(RAW_DIR.iterdir()):
        if not directory.is_dir():
            continue
        successes = 0
        for path in directory.glob("*.json"):
            if path.name == "manifest.json":
                continue
            try:
                payload = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(payload, dict) and payload.get("status_code") == 200:
                successes += 1
        if successes:
            counts[f"raw_{directory.name}"] = successes
    return counts


def build_rows(spec: Spec, landed: Dict[str, int]) -> List[Row]:
    _, fields, _ = spec.extract()
    available: Dict[str, List[str]] = {}
    for field in fields:
        available.setdefault(field["key"], []).append(field["field_path"])

    models_by_table = staging_models()
    rows: List[Row] = []
    for path in sorted(p.lstrip("/") for p in spec.doc["paths"]):
        key = path.replace("/", "_")
        table = f"raw_{key}"
        paths_available = available.get(key, [])
        leaves = {p.split(".")[-1].rstrip("[]") for p in paths_available}
        models = models_by_table.get(table, {})
        exposed: Set[str] = set()
        for keys in models.values():
            exposed |= keys
        # A bare scalar array has no field to unnest; reading the endpoint reads all of it.
        if leaves == {SCALAR_SENTINEL} and models:
            exposed = exposed | leaves
        rows.append(Row(
            path=path,
            endpoint=BY_PATH.get(path),
            landed=table in landed,
            row_count=landed.get(table),
            models=sorted(models),
            fields_available=len(leaves),
            fields_unnested=len(leaves & exposed),
            missing_fields=sorted(leaves - exposed),
        ))
    return rows


def render(rows: List[Row], spec: Spec, source: str, generated: str) -> str:
    total_available = sum(r.fields_available for r in rows)
    total_unnested = sum(r.fields_unnested for r in rows)
    by_status: Dict[str, int] = {}
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1

    out: List[str] = []
    w = out.append
    w("# CFBD coverage matrix")
    w("")
    w("**Generated — do not edit by hand.** `python -m src.coverage_matrix`")
    w("")
    w(f"Spec v{spec.version} · {len(rows)} endpoints · generated {generated} · "
      f"raw counts from {source}")
    w("")
    w("What the API serves, what we fetch, what has landed, and what is actually exposed as")
    w("columns. The last of those is the one that was never measured: the pipeline was")
    w("streamlined toward one website, and a field nobody's page needed was never fetched,")
    w("never unnested, and never missed. Every DAG stayed green throughout.")
    w("")
    w("## Where it stands")
    w("")
    w("| Status | Endpoints | Meaning |")
    w("|---|---:|---|")
    for status, meaning in (
            ("complete", "every field the spec publishes is exposed as a column"),
            ("partial", "a staging model exists but drops fields"),
            ("raw only", "responses have landed; nothing reads them"),
            ("no raw data", "registered, never fetched"),
            ("unregistered", "the API serves it; we have not decided about it")):
        w(f"| {status} | {by_status.get(status, 0)} | {meaning} |")
    w("")
    percent = (100.0 * total_unnested / total_available) if total_available else 0.0
    w(f"**Fields exposed: {total_unnested} of {total_available} ({percent:.1f}%).** "
      "That percentage is the product gap in one number.")
    w("")
    w("## By endpoint")
    w("")
    w("`Swept` means the endpoint is in the default breadth sweep; `CLI` means registered but")
    w("opt-in, because its cost is a different order of magnitude or it needs an argument no")
    w("sweep can invent.")
    w("")
    w("| Endpoint | Registered | Raw | Staging model | Fields | Status |")
    w("|---|---|---:|---|---:|---|")
    for row in rows:
        if not row.registered:
            registered = "—"
        elif row.swept:
            registered = "swept"
        else:
            registered = "CLI"
        raw = "—" if not row.landed else (
            f"{row.row_count:,}" if row.row_count is not None else "yes")
        models = ", ".join(f"`{m}`" for m in row.models) or "—"
        fields = (f"{row.fields_unnested}/{row.fields_available}"
                  if row.fields_available else "—")
        w(f"| `{row.path}` | {registered} | {raw} | {models} | {fields} | {row.status} |")
    w("")
    w("## What each gap costs")
    w("")
    w("Endpoints with a staging model that drops fields. These are the cheapest wins: the")
    w("data is already landed and the model already exists — the fields were simply not")
    w("carried through.")
    w("")
    w("| Endpoint | Model | Dropped | Fields not exposed |")
    w("|---|---|---:|---|")
    partials = [r for r in rows if r.status == "partial"
                and r.path not in PARTIAL_BY_DESIGN]
    for row in sorted(partials, key=lambda r: -(r.fields_available - r.fields_unnested)):
        dropped = row.fields_available - row.fields_unnested
        shown = ", ".join(f"`{f}`" for f in row.missing_fields[:12])
        if len(row.missing_fields) > 12:
            shown += f", … (+{len(row.missing_fields) - 12})"
        w(f"| `{row.path}` | {', '.join(row.models)} | {dropped} | {shown} |")
    if not partials:
        w("| — | — | 0 | Nothing left in this category. |")
    w("")

    by_design = [r for r in rows if r.path in PARTIAL_BY_DESIGN]
    if by_design:
        w("## Partial on purpose")
        w("")
        w("These read as incomplete above and are not work to do. Each one's missing fields")
        w("are exposed elsewhere, from the endpoint that owns them.")
        w("")
        for row in sorted(by_design, key=lambda r: r.path):
            dropped = row.fields_available - row.fields_unnested
            w(f"**`{row.path}`** — {dropped} fields not exposed here. "
              f"{PARTIAL_BY_DESIGN[row.path]}")
            w("")
    w("## How the columns are decided")
    w("")
    w("- **Registered** — presence in `src/endpoints.py`, and whether `include` puts it in")
    w("  the default sweep.")
    w("- **Raw** — a `raw.raw_<key>` table in the warehouse, or a `data/raw/<key>/`")
    w("  directory when the warehouse is not reachable. The header says which answered.")
    w("- **Staging model** — any `dbt/models/staging/*.sql` that selects from that raw table.")
    w("- **Fields** — leaf names in the spec's response schema, against the keys the model")
    w("  passes to the `json_get_*` macros. Leaf matching, not full dot-path: matching full")
    w("  paths reports zero for every endpoint whose payload nests, which is most of them.")
    w("  It can overcount when a nested object reuses a name; it cannot miss a field that is")
    w("  genuinely exposed. For a document that exists to find gaps, that is the safe")
    w("  direction to be wrong in — the real gap is at least this big.")
    w("")
    return "\n".join(out)


def generate(warehouse: bool = False) -> str:
    spec = Spec(json.loads(SPEC_PATH.read_text()))
    if warehouse:
        counts = {t: n for t, n in landed_from_database().items() if t not in OPS_TABLES}
        source = "the warehouse (row counts)"
    else:
        counts = landed_from_directory()
        source = "`data/raw/` (response files on disk)"
    rows = build_rows(spec, counts)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return render(rows, spec, source, generated)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare only; exit 1 if docs/cfbd_coverage.md is stale")
    parser.add_argument("--warehouse", action="store_true",
                        help="take raw counts from Postgres instead of data/raw. Only "
                             "correct where the LIVE warehouse is reachable — port 5432 on "
                             "the laptop is the paused stack, not production.")
    args = parser.parse_args(argv)

    rendered = generate(warehouse=args.warehouse)
    if args.check:
        current = OUTPUT.read_text() if OUTPUT.exists() else ""
        # The header line carries the generation date and the raw source, neither of which
        # is a coverage change — comparing them would fail for the passage of time, or for
        # being run on a different machine.
        #
        # COMPARE LIKE FOR LIKE. Row counts come from whichever source was asked, so a
        # --check without --warehouse against a doc generated with it will differ on every
        # landed row. Check in the mode the doc was written in.
        strip = re.compile(r"^Spec v.*$", re.MULTILINE)
        if strip.sub("", current) == strip.sub("", rendered):
            print(f"{OUTPUT.relative_to(ROOT)} is current")
            return 0
        print(f"::error::{OUTPUT.relative_to(ROOT)} is stale. "
              f"Run: python -m src.coverage_matrix", file=sys.stderr)
        return 1

    OUTPUT.write_text(rendered)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
