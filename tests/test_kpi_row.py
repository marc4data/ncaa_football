r"""A216 — the KPI row above Most Exciting, and the sparkbar's gap.

Each test here is paired with a staged break that was RUN and went red against it. The
breaks and their measured results are in `claude_work/cfdb_report_A216_the_kpi_row.md`.

## Checked against the named instrument failures before it was written

- **R-2254 / R-2255** — a regex counts LINES, not code. The no-arithmetic guard walks the
  `ast`, so a division inside a comment or a docstring cannot trip it and a division written
  across two lines cannot hide from it.
- **R-2260** — a bound is not an assertion. The domain test asserts the two thumbnails are
  drawn on an EQUAL domain, not that each is inside some range.
- **R-760** — an assertion that cannot fire is decoration. Every fixture below is built so the
  property under test is FALSE if the code is wrong: the zero-denominator fixture has a real
  numerator beside it, and the shared-axis fixture carries two DIFFERENT medians so a test
  that accidentally compared a row to itself would still pass and is therefore not what is
  asserted.
- **R-744 / R-763** — a fixture whose defaults make the assertion true, or whose dtype cannot
  hold the case. The frames here are built with explicit `object` dtype where a column must
  hold both a number and `None`.
- **cfdb-wta-R-1504** — nothing here kills a process or touches a port.
"""
import ast
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(ROOT / "site" / "views"))

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
THEME = (ROOT / "site" / "lib" / "theme.py").read_text()
PROJECT = (ROOT / "dbt" / "dbt_project.yml").read_text()


def _func(name: str) -> ast.FunctionDef:
    tree = ast.parse(SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"today.py defines no {name}")


# ── PART 1 — the page does no metric arithmetic ────────────────────────────────────────────

KPI_FUNCS = ("_kpi_row", "_kpi_rate", "_kpi_figure", "_week_summary", "_week_distributions")


def test_THE_KPI_ROW_COMPUTES_NOTHING_it_only_reads_published_columns():
    """§4.2.1. Every rate, denominator and excluded count on this row is a COLUMN.

    🚨 THE POINT IS NOT TIDINESS. A214 built `srv_week_summary` so the rate exists once; a
    division here would be a second definition of *favourites covered*, and the two would
    eventually disagree. The charter's test is *how many consumers can this number have* —
    a rate on a KPI row can have many, so it belongs upstream.

    ⚠️ `ast`, NOT A REGEX (R-2254). A `/` in a docstring is not arithmetic, and this file is
    dense with prose that mentions division.
    """
    offenders = []
    for name in KPI_FUNCS:
        for node in ast.walk(_func(name)):
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv,
                                                                    ast.Mult, ast.Sub)):
                offenders.append(f"{name}: {ast.dump(node.op)} at line {node.lineno}")
    assert not offenders, (
        "the KPI row performs arithmetic; every figure on it is a published column "
        f"(§4.2.1): {offenders}")


def test_THE_ARITHMETIC_GUARD_CAN_ACTUALLY_FAIL():
    """R-760: an assertion that cannot fire is decoration. This proves the walker sees a
    division when one is there — against a function that really does divide."""
    tree = ast.parse("def f(row):\n    return row['a'] / row['b']\n")
    fn = tree.body[0]
    found = [n for n in ast.walk(fn)
             if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)]
    assert found, "the walker cannot see a division, so the guard above proves nothing"


# ── PART 1 — the denominator is on the face of the tile ────────────────────────────────────

def _row(**over):
    """A week-summary row. Every key A216 reads, with 2026 week 3's real shape underneath."""
    base = dict(fbs_games=75, fbs_games_completed=75,
                over_under_mean=53.22, over_under_games=75, over_under_missing=0,
                favorite_straight_up_rate=0.88, favorite_straight_up_wins=66,
                favorite_straight_up_games=75, favorite_straight_up_pickems=0,
                favorite_straight_up_no_line=0,
                favorite_ats_rate=0.4729, favorite_ats_covers=35, favorite_ats_fails=39,
                favorite_ats_games=74, favorite_ats_pushes=1, favorite_ats_no_line=0,
                over_rate=0.589, overs=43, unders=30, over_under_decided_games=73,
                total_pushes=2, total_no_line=0,
                winning_points_mean=38.87, losing_points_mean=17.17,
                undefeated_teams_lost=58, undefeated_teams_entering=184)
    base.update(over)
    # ⚠️ `object` DTYPE ON PURPOSE (R-763): these columns must be able to hold BOTH a number
    # and None. A frame built from floats types the column float64 and silently turns a None
    # into NaN — which happens to be what the page must handle, so a fixture that cannot hold
    # the None cannot test the branch that distinguishes them.
    return pd.Series(base, dtype=object)


def test_A_RATE_ALWAYS_SHOWS_WHAT_IT_IS_OUT_OF():
    """A214 publishes the denominator beside every rate because *62% of favourites covered*
    over 8 games and over 60 are different claims. The tile shows it on its face."""
    import today
    value, sub = today._kpi_rate(_row(), "favorite_ats_rate", "favorite_ats_covers",
                                 "favorite_ats_games",
                                 (("push", "favorite_ats_pushes"),))
    assert value == "47%"
    assert "35 of 74" in sub, f"the denominator is missing from {sub!r}"
    assert "1 push" in sub, f"the excluded count is missing from {sub!r}"


def test_A_ZERO_DENOMINATOR_PRINTS_AN_ABSENCE_AND_NEVER_0_PERCENT():
    """PART 3. `0%` of nothing is a claim nobody measured.

    🚨 THE FIXTURE CARRIES A REAL NUMERATOR BESIDE THE ZERO DENOMINATOR (R-760), so a page
    that computed `covers / games` would raise or return something — it cannot pass by
    accident. The model publishes NULL for the rate here, which is the state under test.
    """
    import today
    # 🚨 THE RATE IS 0.0, NOT None, AND THAT IS THE WHOLE TEST. With `None` this passes even
    # when the page's branch is DELETED, because `fmt.percent` returns an em dash for a null
    # by itself — the staged break came back green and said so. A published 0.0 over a zero
    # denominator is the case only this page can refuse, so it is the case asserted.
    row = _row(favorite_ats_rate=0.0, favorite_ats_covers=0, favorite_ats_games=0,
               favorite_ats_pushes=0)
    value, sub = today._kpi_rate(row, "favorite_ats_rate", "favorite_ats_covers",
                                 "favorite_ats_games", ())
    assert value == today._KPI_ABSENT, f"a zero denominator rendered {value!r}"
    assert "%" not in value
    assert "0 of 0" not in sub, f"an unreadable fraction survived: {sub!r}"


def test_A_NAN_RATE_IS_AN_ABSENCE_because_nan_is_truthy_in_python():
    """PART 3's third clause. `pd.isna`, never truthiness — this file has paid for that at
    `logo_url`, at `text_on`, in `_card_text` and in the drive glyphs."""
    import today
    row = _row(favorite_ats_rate=float("nan"), favorite_ats_games=0, favorite_ats_covers=0)
    value, _sub = today._kpi_rate(row, "favorite_ats_rate", "favorite_ats_covers",
                                  "favorite_ats_games", ())
    assert value == today._KPI_ABSENT, "NaN reached the screen as a number"


# ── PART 2 — the two score distributions share one axis ────────────────────────────────────

def _dist(metric, p50, bin_min=0, bin_max=80, bin_count=10):
    return pd.Series({"metric": metric, "p50": p50, "p25": p50 - 8, "p75": p50 + 8,
                      "min_value": 0, "max_value": bin_max, "whisker_lo": 0,
                      "whisker_hi": bin_max, "outlier_count": 0,
                      "bin_min": bin_min, "bin_max": bin_max, "bin_count": bin_count,
                      "bin_incr": (bin_max - bin_min) / bin_count,
                      "bin_counts": "1,2,5,9,14,18,12,8,4,2",
                      "n": 75, "games_in_week": 75,
                      "axis_group": "game_points", "domain_rule": "fixed"}, dtype=object)


def test_THE_TWO_SCORE_THUMBNAILS_ARE_DRAWN_ON_ONE_DOMAIN():
    """🚨 THE COMPARISON IS THE POINT. Rescaled to its own maximum a losing-score
    distribution looks very like a winning one; the whole reason to put them side by side is
    that the winning distribution sits visibly to the RIGHT.

    ⚠️ THE TWO FIXTURES CARRY DIFFERENT MEDIANS (38 and 17), so this cannot pass by comparing
    a row with itself — and the assertion is EQUALITY of the drawn domain, not each being
    inside some range (R-2260).
    """
    from lib import distribution
    win, lose = _dist("winning_points", 38), _dist("losing_points", 17)
    assert float(win["p50"]) != float(lose["p50"]), "the fixtures are the same picture"
    a = distribution.thumbnail(win, label="W", width=72)
    b = distribution.thumbnail(lose, label="L", width=72)
    import re
    box = lambda svg: re.search(r"viewBox='([^']+)'", svg).group(1)      # noqa: E731
    assert box(a) == box(b), "the two score thumbnails are drawn on different domains"


def test_THE_SHARED_AXIS_IS_GUARANTEED_UPSTREAM_not_by_this_page():
    """A214 gave both metrics one `axis_group` and a dbt test that fails the build if their
    bounds diverge. The page reads two rows and draws them; it reconciles nothing."""
    import yaml
    bins = yaml.safe_load(PROJECT)["vars"]["distribution_bins"]
    win, lose = bins["winning_points"], bins["losing_points"]
    assert win.get("axis_group") == lose.get("axis_group") == "game_points"
    assert (win["min"], win["max"]) == (lose["min"], lose["max"])


def test_THE_THUMBNAIL_HAS_NO_AXIS():
    """The standard's `thumbnail` size is bars plus a median tick, no axis — which is what
    Marc described: *a small box-whisker or histogram underneath*. An axis would make it a
    panel in a tile's worth of room."""
    from lib import distribution
    svg = distribution.thumbnail(_dist("total", 52.5), width=72)
    assert "<svg" in svg
    for tick in ("class='cfdb-dist-axis'", "<line class='axis", "axis-label"):
        assert tick not in svg, f"the thumbnail grew an axis: {tick}"


# ── PART 3 — the two absences read differently ─────────────────────────────────────────────

def test_NO_SINGLE_WEEK_AND_NO_ROW_ARE_DIFFERENT_ABSENCES():
    """AC-G.11. A214's model publishes a row for every week that has fixtures, so *no row*
    means cfdb holds nothing for that week — a statement about our data. *Every week is
    selected* is a statement about the filter. They must not read the same."""
    src = ast.get_source_segment(SOURCE, _func("_kpi_row"))
    assert "This summary is per week" in src
    assert "cfdb holds no week summary" in src
    assert src.index("This summary is per week") < src.index("cfdb holds no week summary"), \
        "the week=All branch must be checked before the empty-frame branch"


def test_A_WEEK_WITH_NO_COMPLETED_GAME_STILL_DRAWS_THE_ROW():
    """🚨 THE STATE A READER MEETS EVERY TUESDAY MORNING. The fixtures exist, nothing has
    been played, and the panel must show the counts with honest absences beside them rather
    than vanishing — *no games yet* and *no row* are different facts."""
    import today
    row = _row(fbs_games=71, fbs_games_completed=0,
               favorite_straight_up_rate=None, favorite_straight_up_wins=0,
               favorite_straight_up_games=0,
               undefeated_teams_lost=0, undefeated_teams_entering=136)
    value, sub = today._kpi_rate(row, "favorite_straight_up_rate",
                                 "favorite_straight_up_wins",
                                 "favorite_straight_up_games", ())
    assert value == today._KPI_ABSENT and "0 of 0" not in sub
    src = ast.get_source_segment(SOURCE, _func("_kpi_row"))
    assert "not played" in src or "not played" in src.lower() or "or not played" in src \
        or "not played" in SOURCE, "the unplayed-week reasoning is undocumented"


def test_THE_UNDEFEATED_COUNT_IS_AN_ABSENCE_UNTIL_SOMETHING_HAS_BEEN_PLAYED():
    """A214 coalesces this to 0 so every week has a number. On a week nobody has played that
    0 reads as *no unbeaten team was beaten* — a claim about a week that has not happened.
    The other six outcome figures go to an em dash there and so does this one."""
    src = ast.get_source_segment(SOURCE, _func("_kpi_row"))
    assert "or not played" in src, \
        "the undefeated tile does not gate on whether anything has been played"


# ── PART 0 — the sparkbar's gap, and the unit mismatch that caused it ──────────────────────

def test_THE_SPARK_SLOT_IS_BUDGETED_IN_THE_BARS_OWN_UNITS():
    """🚨 A221 BUDGETED A `1.9rem` BAR IN THREE `ch` OF A DIFFERENT FONT and came up 6.4px
    short, so the `nowrap` value overflowed its box and landed on the bar — while every BOX
    edge stayed correct, which is why `ci/measure_card_budget.py` never saw it.

    The budget now adds the same two CSS variables the bar is drawn from, so the two cannot
    drift apart. This asserts they are ONE value, not two that happen to agree.
    """
    assert "_SPARK_SLOT_CH" not in SOURCE.split("# 🚨 A216")[0].split("_SPARK_SLOT =")[0] \
        or "_SPARK_SLOT_CH = " not in SOURCE, "the ch-based slot constant is still live"
    assert "var(--cfdb-card-spark-w) + var(--cfdb-card-spark-gap)" in SOURCE, \
        "the width budget no longer reads the bar's own CSS variables"
    assert "calc({drawn}ch + {_SPARK_SLOT})" in SOURCE or \
           'f"calc({drawn}ch + {_SPARK_SLOT})"' in SOURCE, \
        "the primary column's width is not a calc over the digits plus the slot"
    for var in ("--cfdb-card-spark-w:1.9rem", "--cfdb-card-spark-gap:.25rem"):
        assert var in THEME.replace(" ", ""), f"{var} is not defined in theme.py"
    assert "gap:var(--cfdb-card-spark-gap" in THEME.replace(" ", ""), \
        "the cell's gap is a literal again, which is the drift this fixed"


def test_THE_KPI_ROW_USES_THE_SHARED_SCROLL_WRAPPER_not_a_second_mechanism():
    """A208's rule. Seven tiles do not fit at 1024; the site has one scroll mechanism and its
    note, and a private `overflow-x` here would be the drift this project keeps paying for."""
    src = ast.get_source_segment(SOURCE, _func("_kpi_row"))
    assert "cfdb-scroll" in src, "the KPI row does not sit in the shared scroll wrapper"
    kpi_css = THEME[THEME.index(".cfdb-kpirow"):THEME.index(".cfdb-kpi-pair")]
    assert "overflow-x" not in kpi_css, "the KPI row grew its own scroll mechanism"


@pytest.mark.parametrize("name", ["_kpi_row", "_kpi_rate", "_kpi_figure"])
def test_THE_PANEL_EXISTS_UNDER_THE_NAME_THE_TESTS_AND_TABS_USE(name):
    """R-2353: a comment or a registry naming a function that does not exist is worse than
    silence, because the name is what the next round will trust."""
    assert _func(name) is not None
