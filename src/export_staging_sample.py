"""Export a sample of every staging table to one Excel workbook, a tab per table.

Rule, as asked: up to 10,000 rows per table. Any table with more than that is narrowed to
Oklahoma State, 2025, ordered by season and week ascending.

WHICH IS NOT UNIFORMLY POSSIBLE, and the interesting part of the job is what to do about
it. Staging models are shaped like the endpoints they unpack, so the columns needed to
express "Oklahoma State, 2025" are not in all of them:

  stg_games              home_team / away_team, season, week   -> filter directly
  stg_rankings           school, season, week                  -> filter directly
  stg_team_season_stat   school, season, no week               -> filter, order by season
  stg_teams              school, season, no week               -> filter, order by season
  stg_game_team_stat     game_id, team_id — NO NAME, NO SEASON -> resolve the ids

That last one is the case worth naming. It holds 194,580 rows and carries neither a team
name nor a season, so the filter cannot be written against it as stated. It CAN be
expressed by resolving Oklahoma State's team_id and the 2025 game_ids from the tables that
do carry them, which is the same request answered through a join — so that is what happens,
and the Index sheet records that the narrowing was indirect rather than literal.

A filtered sheet that comes back EMPTY is written anyway, with its headers and a note.
Oklahoma State was unranked all of 2025, so stg_rankings is legitimately empty — and an
empty tab with no explanation is indistinguishable from a broken export.

Usage:
  python -m src.export_staging_sample
  python -m src.export_staging_sample --out /tmp/staging_sample.xlsx --team "Texas" --season 2024
"""
import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROW_CAP = 10_000
SCHEMA = "staging"

# Candidate columns, in preference order, for expressing the narrowing. Checked against
# information_schema per table rather than assumed — the shape of a staging model follows
# its endpoint, not a convention.
TEAM_COLUMNS = ("school", "team", "team_name")
PAIR_COLUMNS = ("home_team", "away_team")
ORDER_COLUMNS = ("season", "year", "week")


def _clean(value):
    """One cell value openpyxl will accept.

    Three conversions, each of which has broken a workbook in this project before: a
    tz-aware datetime makes openpyxl raise outright, a NaN produces a file Excel refuses to
    open with a repair prompt, and a jsonb column arrives as a dict or list that openpyxl
    cannot serialise at all.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, (dict, list)):
        import json
        return json.dumps(value)[:32000]        # Excel's per-cell ceiling is 32,767
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, str) and len(value) > 32000:
        return value[:32000]
    return value


def columns_of(cursor, table: str) -> list:
    cursor.execute("""
        select column_name from information_schema.columns
        where table_schema = %s and table_name = %s
        order by ordinal_position
    """, (SCHEMA, table))
    return [row[0] for row in cursor.fetchall()]


def build_query(cursor, table: str, row_count: int, team: str, season: int) -> tuple:
    """Return (sql, params, note) for one table.

    The note is what the Index sheet reports. Every sheet gets one, because "10,000 rows of
    194,580" and "12 rows, the whole of Oklahoma State's 2025" are very different things to
    be looking at and the tab itself cannot tell you which it is.
    """
    cols = set(columns_of(cursor, table))
    order = [c for c in ORDER_COLUMNS if c in cols]
    order_sql = f" order by {', '.join(order)} asc" if order else ""

    if row_count <= ROW_CAP:
        return (f"select * from {SCHEMA}.{table}{order_sql} limit {ROW_CAP}", {},
                f"Whole table ({row_count:,} rows), under the {ROW_CAP:,} cap.")

    # Over the cap: narrow. Season first, then whichever team column exists.
    where, params = [], {}
    applied = []
    if "season" in cols:
        where.append("season = %(season)s")
        params["season"] = season
        applied.append(f"season {season}")

    team_col = next((c for c in TEAM_COLUMNS if c in cols), None)
    if team_col:
        where.append(f"{team_col} = %(team)s")
        params["team"] = team
        applied.append(f"{team_col} = {team!r}")
    elif all(c in cols for c in PAIR_COLUMNS):
        where.append("(%(team)s in (home_team, away_team))")
        params["team"] = team
        applied.append(f"{team!r} as home or away")
    elif "team_id" in cols and "game_id" in cols:
        # No name, no season. Resolve both through the tables that do carry them — the same
        # request expressed as a join rather than a literal.
        where.append(f"""team_id in (
            select distinct team_id from {SCHEMA}.stg_teams where school = %(team)s)""")
        where.append(f"""game_id in (
            select game_id from {SCHEMA}.stg_games where season = %(season)s)""")
        params.update({"team": team, "season": season})
        applied.append(f"team_id and game_id resolved for {team!r} in {season} "
                       f"(this table carries neither a name nor a season)")

    if not where:
        return (f"select * from {SCHEMA}.{table}{order_sql} limit {ROW_CAP}", {},
                f"OVER CAP at {row_count:,} rows and NOT NARROWABLE — no season, team or "
                f"id column to filter on. Showing the first {ROW_CAP:,} rows instead.")

    sql = f"select * from {SCHEMA}.{table} where {' and '.join(where)}{order_sql} limit {ROW_CAP}"
    return sql, params, (f"{row_count:,} rows in full, narrowed to " + "; ".join(applied)
                         + (f"; ordered by {', '.join(order)}" if order else ""))


def export(out_path: Path, team: str, season: int) -> dict:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    from .load_raw_to_postgres import get_conn

    connection = get_conn()
    cursor = connection.cursor()
    cursor.execute("""
        select table_name from information_schema.tables
        where table_schema = %s order by table_name
    """, (SCHEMA,))
    tables = [row[0] for row in cursor.fetchall()]

    book = Workbook()
    book.remove(book.active)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F4858")
    index_rows = []

    for table in tables:
        cursor.execute(f"select count(*) from {SCHEMA}.{table}")
        total = cursor.fetchone()[0]
        sql, params, note = build_query(cursor, table, total, team, season)
        cursor.execute(sql, params)
        headers = [d[0] for d in cursor.description]
        rows = cursor.fetchall()

        # Excel caps a sheet name at 31 characters. Every staging name fits today; asserting
        # it rather than truncating means a future long name fails loudly instead of
        # silently colliding with another truncated tab.
        sheet_name = table[:31]
        tab = book.create_sheet(sheet_name)
        for index, header in enumerate(headers, start=1):
            cell = tab.cell(1, index, header)
            cell.font, cell.fill = header_font, header_fill
        for r, row in enumerate(rows, start=2):
            for index, value in enumerate(row, start=1):
                tab.cell(r, index, _clean(value))

        if not rows:
            # Headers with no rows is an ambiguous artifact — it reads as a broken export
            # rather than an honest empty result. Say which it is, on the sheet.
            tab.cell(2, 1, f"No rows. {note}")
            tab.cell(2, 1).font = Font(italic=True, color="A03030")

        tab.freeze_panes = "A2"
        if headers:
            tab.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(len(rows) + 1, 2)}"
        for index, header in enumerate(headers, start=1):
            longest = len(str(header))
            for row in rows[:400]:                # sample, not the whole column
                value = row[index - 1]
                if value is not None:
                    longest = max(longest, min(len(str(value)), 60))
            tab.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 9), 46)

        index_rows.append((table, total, len(rows), note))
        print(f"  {table:26s} {len(rows):>7,} of {total:>9,}  {note[:60]}")

    _write_index(book, index_rows, team, season, header_font, header_fill)
    connection.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    book.save(out_path)
    return {"tables": len(index_rows),
            "rows": sum(r[2] for r in index_rows),
            "path": str(out_path)}


def _write_index(book, index_rows, team, season, header_font, header_fill) -> None:
    """What each tab is, and why it holds what it holds.

    Without this the workbook cannot answer its own most obvious question: is this tab the
    whole table, the first 10,000 rows, or one team's season?
    """
    from openpyxl.utils import get_column_letter

    tab = book.create_sheet("Index", 0)
    tab.cell(1, 1, "cfdb — staging layer sample").font = header_font
    tab.cell(1, 1).fill = header_fill
    tab.cell(2, 1, f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    tab.cell(3, 1, f"Rule: up to {ROW_CAP:,} rows per table. Anything larger is narrowed to "
                   f"{team}, {season}, ordered by season and week ascending.")
    tab.cell(4, 1, "Staging is the layer BELOW the site's serving views: one model per CFBD "
                   "endpoint, JSON unpacked and failed responses filtered out. Shapes follow "
                   "the endpoint, which is why not every table can express the same filter.")

    for index, label in enumerate(("Table", "Rows in full", "Rows exported", "Note"), start=1):
        cell = tab.cell(6, index, label)
        cell.font, cell.fill = header_font, header_fill
    for r, (table, total, exported, note) in enumerate(index_rows, start=7):
        tab.cell(r, 1, table)
        tab.cell(r, 2, total).number_format = "#,##0"
        tab.cell(r, 3, exported).number_format = "#,##0"
        tab.cell(r, 4, note)
    tab.freeze_panes = "A7"
    for index, width in enumerate((28, 14, 14, 110), start=1):
        tab.column_dimensions[get_column_letter(index)].width = width


def main() -> int:
    parser = argparse.ArgumentParser(description="Sample every staging table into one workbook.")
    parser.add_argument("--out", type=Path,
                        default=Path("data/exports/staging_sample.xlsx"))
    parser.add_argument("--team", default="Oklahoma State")
    parser.add_argument("--season", type=int, default=2025)
    args = parser.parse_args()

    print(f"Sampling {SCHEMA}: <= {ROW_CAP:,} rows per table, "
          f"larger tables narrowed to {args.team} {args.season}\n")
    summary = export(args.out, args.team, args.season)
    print(f"\n{summary['tables']} sheet(s), {summary['rows']:,} rows -> {summary['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
