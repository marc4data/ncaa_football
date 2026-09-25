"""Team Stats pivots in the writer, and a truncation warning means truncation. A228.

> **MARC, v16:** *"Team Stats needs to pivot Stat or Stat (null) with Value (numeric). Will
> need to do some cleansing before doing the pivot."*

🚨 A222 ANSWERED THIS ASK AND RECOMMENDED A NEW SERVING VIEW, on the argument that *"the ten
Player Stat sheets are pivoted per category because A175 did it upstream."* **They are not.**
All ten pivot in the exporter through `augment=_pivot_player_stats([...])`, against a melted
`srv_player_stats`. The precedent is exact and points the other way, which is what this round
followed.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from lib import workbook                                          # noqa: E402

SOURCE = (ROOT / "site" / "lib" / "workbook.py").read_text(encoding="utf-8")


def _sheet():
    return [s for s in workbook.SHEETS if s.name == "Team Stats"][0]


def _melted(teams=("Alpha", "Beta"), stats=None, in_scope=None):
    """A melted frame in `srv_team_stats`' shape."""
    stats = stats or list(workbook.TEAM_STAT_NAMES)
    rows = []
    for t_i, team in enumerate(teams):
        for s_i, stat in enumerate(stats):
            rows.append({"season": 2026, "school": team, "conference": "SEC",
                         "classification": "fbs", "stat_base_name": stat,
                         "stat_name": stat, "stat_value": 100 * t_i + s_i,
                         "stat_value_raw": str(100 * t_i + s_i), "rank_desc": s_i + 1,
                         "rank_asc": 1, "percentile": 0.5})
    df = pd.DataFrame(rows)
    df["rows_in_scope"] = in_scope if in_scope is not None else len(df)
    return df


# ── the pivot ─────────────────────────────────────────────────────────────────────────────

def test_the_pivot_gives_one_row_per_team():
    out = workbook._pivot_team_stats(_melted())
    assert len(out) == 2
    assert out["school"].is_unique


def test_the_identity_columns_come_first_and_in_the_sheets_order():
    out = workbook._pivot_team_stats(_melted())
    assert list(out.columns[:4]) == ["season", "school", "conference", "classification"]


def test_every_declared_statistic_becomes_a_column_in_the_declared_order():
    """⚠️ THE ORDER IS THE DECLARATION'S, NOT THE DATA'S. `sheet.columns` drives the header
    row, the widths and the Excel Table range, so a column the writer was not told about
    cannot be written — and one it was told about must exist even when a scope has no value
    for it."""
    out = workbook._pivot_team_stats(_melted())
    stat_cols = [c for c in out.columns
                 if c not in ("season", "school", "conference", "classification",
                              "rows_in_scope")]
    assert stat_cols == list(workbook.TEAM_STAT_NAMES)


def test_a_statistic_absent_from_the_data_is_an_EMPTY_column_not_a_missing_one():
    """🚨 138 TEAMS x 32 STATISTICS IS 4,416 AND THE VIEW HOLDS 4,348 — not every team has
    every statistic. A missing column would shift every header to its left."""
    partial = _melted(stats=list(workbook.TEAM_STAT_NAMES)[:5])
    out = workbook._pivot_team_stats(partial)
    stat_cols = [c for c in out.columns
                 if c not in ("season", "school", "conference", "classification",
                              "rows_in_scope")]
    assert stat_cols == list(workbook.TEAM_STAT_NAMES)
    assert out[list(workbook.TEAM_STAT_NAMES)[-1]].isna().all()


def test_the_values_survive_the_pivot_by_VALUE_not_by_count():
    """R-843 / B149: a count cannot see a swap. Each cell is checked against the melted row
    it came from."""
    melted = _melted()
    out = workbook._pivot_team_stats(melted).set_index("school")
    for team in ("Alpha", "Beta"):
        src = melted[melted["school"] == team].set_index("stat_base_name")["stat_value"]
        for stat in workbook.TEAM_STAT_NAMES:
            assert out.loc[team, stat] == src[stat], f"{team}/{stat}"


def test_the_pivot_returns_an_empty_frame_unchanged():
    assert workbook._pivot_team_stats(pd.DataFrame()).empty
    assert workbook._pivot_team_stats(None) is None


# ── 🚨 the truncation flag, which was wrong on ten sheets before this round ────────────────

def test_a_sheet_under_the_cap_does_NOT_report_itself_truncated():
    """🚨 THE DEFECT A228 FOUND, AND IT WAS LIVE ON TEN SHEETS.

    `SheetRead.truncated` is `rows_in_scope > rows`, and after a pivot the MELTED count is
    always greater than the pivoted one — so every pivoted sheet reported itself truncated
    for ever. 📊 Measured on live serving before the fix: all ten Player Stat sheets returned
    `truncated = True`, the largest reading 1,011 melted rows against a 5,000 cap, and the
    Index told the reader *"196 of 467 rows written; 271 not in this file. Narrow the
    filters"* about a sheet that held everything.

    **A truncation warning that is always on is one nobody reads the day a real one appears.**
    """
    out = workbook._pivot_team_stats(_melted(in_scope=64))
    assert out["rows_in_scope"].iloc[0] == len(out) == 2


def test_a_sheet_that_HIT_the_cap_still_reports_itself_truncated():
    """✅ AND THE FIX MUST NOT DISARM THE WARNING. The cap bit if and only if the melted read
    came back AT the cap — that is the only signal `limit` gives."""
    out = workbook._pivot_team_stats(_melted(in_scope=workbook.ROW_CAP))
    assert out["rows_in_scope"].iloc[0] == workbook.ROW_CAP
    assert out["rows_in_scope"].iloc[0] > len(out), "the sheet must still read as truncated"


@pytest.mark.parametrize("melted,pivoted,expect", [
    (100, 10, 10), (workbook.ROW_CAP, 200, workbook.ROW_CAP),
    (workbook.ROW_CAP + 1, 200, workbook.ROW_CAP + 1), (0, 0, 0),
])
def test_the_rows_in_scope_rule_at_and_around_the_cap(melted, pivoted, expect):
    assert workbook._pivoted_rows_in_scope(melted, pivoted) == expect


def test_the_player_pivots_use_the_same_rule():
    """One rule, both pivots — or the two shapes drift and only one gets fixed next time."""
    assert "_pivoted_rows_in_scope(in_scope, len(out))" in SOURCE
    assert SOURCE.count("_pivoted_rows_in_scope(in_scope, len(out))") == 2


# ── the declaration cannot disagree with the pivot ─────────────────────────────────────────

def test_one_list_drives_both_the_pivot_and_the_column_declaration():
    """⚠️ THE PLAYER SHEETS PASS THEIR STATISTIC LIST TWICE — to the pivot and to `columns`.
    Here both are generated from `TEAM_STAT_NAMES`, so they cannot disagree."""
    declared = [field for field, _ in _sheet().columns]
    assert declared[:4] == ["season", "school", "conference", "classification"]
    assert declared[4:] == list(workbook.TEAM_STAT_NAMES)


def test_the_sheet_actually_carries_the_pivot():
    """🚨 A GAP A STAGED BREAK FOUND. Removing `augment=_pivot_team_stats` from the sheet left
    every other test green — they all exercised the FUNCTION and none asserted the sheet was
    wired to it. The sheet would have shipped melted, with 36 declared headers over 11
    columns of data."""
    assert _sheet().augment is not None, "the Team Stats sheet no longer pivots"
    out = _sheet().augment(_melted())
    assert len(out) == 2 and "school" in out.columns


def test_the_statistic_count_is_pinned_at_what_serving_holds():
    """⚠️ THE LIST DRIVES BOTH THE PIVOT AND THE DECLARATION, so dropping a name from it
    keeps them consistent with each other and silently narrows the sheet — another break that
    came back green. 📊 32 is measured: `select distinct stat_base_name from srv_team_stats
    where stat_scope = 'team'` returned 32 for every season from 2023 to 2026."""
    assert len(workbook.TEAM_STAT_NAMES) == 32, (
        f"{len(workbook.TEAM_STAT_NAMES)} statistics declared; live serving holds 32. If CFBD "
        f"has genuinely changed the set, re-measure and move this number deliberately.")
    assert len(set(workbook.TEAM_STAT_NAMES)) == 32, "a statistic is declared twice"


def test_the_headers_are_proper_case_including_the_acronym():
    """✅ MARC RULED ON PROPER CASE 2026-09-24: *"I like the Proper Case."*
    ⚠️ `TDs` is the one a naive camelCase split breaks — `Interception T Ds`."""
    assert workbook._team_stat_header("netPassingYards") == "Net Passing Yards"
    assert workbook._team_stat_header("interceptionTDs") == "Interception TDs"
    assert workbook._team_stat_header("games") == "Games"
    for _field, header in _sheet().columns:
        assert "T Ds" not in header, header


def test_the_sheet_still_reads_exactly_one_serving_view():
    """PART 3 — the Index says *"Source | cfdb serving layer; every sheet is one serving
    view"*, and its table's own column is *Serving view*. **That is a PROVENANCE claim**, and
    a reshape in the writer does not break it: this sheet still reads `srv_team_stats` and
    nothing else. It was already true of the ten pivoted player sheets."""
    assert _sheet().view == "srv_team_stats"
    # ⚠️ ASKED OF THE SHEET'S OWN SQL, NOT OF THE FILE. The first draft counted
    # `"from srv_team_stats"` across `workbook.py` and expected 1; it is 2, because a COMMENT
    # in this round records the query that measured the statistic list. **A grep counts
    # matches, not queries** (R-859 / §2.2.1c.1) — and the question here is whether this
    # sheet reads one relation, which its own SQL answers exactly.
    import re
    relations = set(re.findall(r"\bfrom\s+([a-z_][a-z0-9_]*)", _sheet().sql, re.I))
    assert relations == {"srv_team_stats"}, relations
    # ⚠️ AND A COMMA-JOIN IS A SECOND RELATION THAT `from (\w+)` CANNOT SEE — a staged break
    # adding `, srv_team_overview` left this green, because the capture stops at the comma.
    # G-2 forbids it outright, so the clause after the relation is checked too.
    after = _sheet().sql.lower().split("from srv_team_stats", 1)[1].split("where", 1)[0]
    assert "," not in after and " join " not in after, (
        f"the sheet reads more than one relation: {after.strip()!r}")


def test_the_melted_columns_are_still_selected_even_though_they_are_no_longer_columns():
    """The pivot reads `stat_base_name` and `stat_value`, and a later round adding the rank
    twin needs `rank_desc` already in the frame."""
    sql = _sheet().sql
    for field in ("stat_base_name", "stat_value", "rank_desc"):
        assert field in sql, field
    declared = [f for f, _ in _sheet().columns]
    for field in ("stat_base_name", "stat_name", "stat_value", "percentile"):
        assert field not in declared, f"{field} is still a declared column"


@pytest.mark.parametrize("name", ["_pivot_team_stats", "TEAM_STAT_NAMES",
                                  "_team_stat_header", "_pivoted_rows_in_scope"])
def test_the_names_this_file_relies_on_exist(name):
    """R-2353: a test naming something that does not exist is worse than silence."""
    assert hasattr(workbook, name)
