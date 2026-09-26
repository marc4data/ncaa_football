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


def test_the_two_score_tiles_are_drawn_on_ONE_domain():
    """🚨 A235 (cfdb-main-R-3029). THE SPLIT IS EXACTLY WHAT PUTS THE SHARED AXIS AT RISK.

    > **MARC, v18:** *"Winning vs Losing Score - Break this into 2 KPI's."*

    Rescaled to its own maximum a losing-score distribution looks very like a winning one; the
    whole reason to show them together is that the winning distribution sits visibly to the
    RIGHT. While they were two thumbnails in ONE tile that was obvious on inspection. **As two
    separate tiles, two different scales would look completely fine and be silently wrong.**

    ⚠️ `assert_an_axis_group_shares_one_domain` PINS THIS UPSTREAM AND CANNOT SEE THIS PAGE —
    it asserts the two metrics' published bounds agree, not that the page draws them that way.
    This is the half that had no guard: the property is asserted THROUGH THE RENDERER, on the
    exact call the two tiles make, so a round that passed a per-tile `frame` or let one tile
    fall back to its own extremes goes red here.

    ⚠️ THE TWO FIXTURES CARRY DIFFERENT MEDIANS (38 and 17), so this cannot pass by comparing a
    row with itself — and the assertion is EQUALITY of the drawn geometry, not each being
    inside some range (R-2260).
    """
    import re
    import today
    win, lose = _dist("winning_points", 38), _dist("losing_points", 17)
    assert float(win["p50"]) != float(lose["p50"]), "the fixtures are the same picture"
    # 🚨 THROUGH THE PAGE'S OWN HELPER, NOT THROUGH A CALL THIS TEST COMPOSES (R-768). If the
    # page changes the arguments it renders with, this test changes with it.
    a, b = today._kpi_chart(win, "winning_points"), today._kpi_chart(lose, "losing_points")
    geom = lambda svg: re.search(r"viewBox='([^']+)'", svg).group(1)      # noqa: E731
    assert geom(a) == geom(b), "the two score tiles are drawn on different domains"

    # AND THE SHARED DOMAIN IS DOING WORK, not agreeing by accident: with equal bounds and
    # different data the two MEDIAN RULES must land at different x. If they coincided, the
    # renderer would be ignoring the row and the equality above would be worthless.
    assert (float(win["bin_min"]), float(win["bin_max"])) == \
           (float(lose["bin_min"]), float(lose["bin_max"]))
    # ⚠️ A243: THE HISTOGRAM'S MEDIAN TICK (`stroke-opacity='0.95'`) IS GONE WITH THE BARS. The
    # box's own bold rule is now the only median mark, and it is what this reads.
    median_x = lambda svg: re.search(                                     # noqa: E731
        r"<line x1='([\d.]+)'[^>]*stroke-width='2'", svg).group(1)
    assert median_x(a) != median_x(b), (
        "both medians are at the same x on a shared axis — the chart is not reading the row")


def test_THE_KPI_ROW_ACTUALLY_ASKS_FOR_AN_AXIS():
    """🚨 A STAGED BREAK FOUND THIS GAP IN A235 AND A237 HAD TO REWRITE IT WITHOUT WEAKENING IT.

    > **MARC, v18:** *"an x-axis with labels in the box-whisker diagram."*
    > **MARC, 2026-09-25:** *"Don't need to include the values for the tickmarks, just the ticks."*

    ⚠️ **THE OLD ASSERTION WAS `<text>` ELEMENTS EXIST, AND MARC'S NEW AXIS HAS NONE.** Deleting
    it would have let the axis vanish with nothing red — which is the exact failure A235 wrote it
    to prevent, one requirement later. **So it asserts on the TICK MARKS instead**, which is what
    the axis is made of now, and it still points at the PAGE's own call rather than at the module
    (R-768).
    """
    import re
    import today
    svg = today._kpi_chart(_dist("winning_points", 38), "winning_points")
    ticks = re.findall(r"<line[^>]*stroke-opacity='\.45'", svg)
    assert ticks, (
        "the KPI charts draw no axis tick marks. Marc asked for an x-axis of ticks; the page is "
        "asking distribution.panel() for TICK_NONE.")
    # 🚨 AND THE RULER IS A RULER: marks on MULTIPLES of the step, not steps from the left edge.
    # On an axis starting at 14 the first mark is 15. Two tiles side by side is exactly where a
    # ruler whose marks mean different values would show.
    xs = sorted(float(m) for m in
                re.findall(r"<line x1='([\d.]+)'[^>]*stroke-opacity='\.45'", svg))
    assert len(xs) >= 2, f"a ruler needs more than one mark: {xs}"
    # ⚠️ TOLERANCE 0.1px, AND IT IS THE `:.1f` IN THE EMITTED COORDINATE RATHER THAN SLACK IN
    # THE RULE. A 45-point axis over 140px puts the true spacing at 11.864px, which rounds to an
    # alternating 11.8 / 11.9 — a strict equality here fails on the printing, not on the geometry.
    # Two coordinates each rounded to one decimal can differ by at most 0.1, so the bound is that
    # plus float dust. A ruler that was genuinely uneven would be out by whole pixels.
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    assert max(gaps) - min(gaps) <= 0.1 + 1e-9, \
        f"the tick marks are not evenly spaced: {gaps}"


def test_THE_TICK_RULER_COUNTS_FROM_ZERO_NOT_FROM_THE_LEFT_EDGE():
    """🚨 MARC SAID *"counting from a baseline of 0, so 5, 10, 15, etc"* — A MODULUS.

    ⚠️ IT ONLY BECAME OBSERVABLE BECAUSE A237 ALSO NARROWED THE AXIS. While the axis started at
    `bin_min` (0 for both score metrics) a ruler counting from the left edge and one counting
    from zero were the SAME PICTURE, and a test could not tell them apart. **On an axis starting
    at 14 they differ by 4px, and this pins the difference.**
    """
    import re
    from lib import distribution
    row = _dist("winning_points", 38)
    width, lo, hi, step = 140, 14.0, 59.0, 5.0
    svg = distribution.panel(row, width=width, height=28, ticks=distribution.TICK_STEP,
                             tick_step=step, head=False, stats=False, axis=(lo, hi))
    xs = sorted(float(m) for m in
                re.findall(r"<line x1='([\d.]+)'[^>]*stroke-opacity='\.45'", svg))
    assert xs, "no tick marks were drawn"
    # every mark must sit at a multiple of the step, converted back to a value
    values = [lo + x / width * (hi - lo) for x in xs]
    # the same `:.1f` rounding, carried back into value units: 0.05px over this axis is 0.016
    # of a point, so 0.05 is two orders of magnitude clear of the defect being pinned (a ruler
    # counting from the left edge would put the first mark 1.0 out, at 14).
    for v in values:
        assert abs(v / step - round(v / step)) < 0.05, (
            f"a tick landed at {v:.3f}, which is not a multiple of {step:g} — the ruler is "
            f"counting from the left edge instead of from zero")
    assert abs(values[0] - 15.0) < 0.05, (
        f"the first tick on an axis starting at {lo:g} must be 15, not {values[0]:.2f}")


def test_NEITHER_SCORE_TILE_RESHAPES_ITS_PUBLISHED_ROW():
    """🚨 THE OTHER BREAK THAT CAME BACK GREEN, AND THE ONE THE SPLIT EXISTS TO PREVENT.

    Giving the losing tile its own `bin_max` — two tiles, two scales, side by side — left every
    test passing. The renderer test above cannot see it: handed two rows that share bounds it
    correctly draws them on one domain, so it proves the RENDERER honest and says nothing about
    what the PAGE hands it (R-768 — a test whose subject it builds itself).

    ✅ SO THE CLAIM IS STRUCTURAL AND IT IS CHECKED ON THE PAGE'S OWN CALLS: each chart gets the
    published row, unmodified. A dict literal, a merge, a `.copy()` with an override — anything
    that is not `by_metric.get(<metric>)` — is the page reconciling scales, which is exactly
    what §4.2.1 and the upstream `axis_group` assertion exist to keep it out of.
    """
    calls = [node for node in ast.walk(_func("_kpi_row"))
             if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_kpi_chart"]
    assert len(calls) == 3, f"expected three charted tiles, found {len(calls)}"
    metrics = []
    for call in calls:
        arg = call.args[0]
        assert isinstance(arg, ast.Call) and getattr(arg.func, "attr", "") == "get", (
            f"a KPI chart is handed {ast.dump(arg)[:80]} rather than the published row. "
            f"The page must pass `by_metric.get(<metric>)` unmodified — reshaping it here is "
            f"the page reconciling two scales.")
        assert getattr(arg.func.value, "id", "") == "by_metric"
        assert len(arg.args) == 1 and isinstance(arg.args[0], ast.Constant)
        metrics.append(arg.args[0].value)
    # 🚨 A243 (cfdb-main-R-3323). THE ORDER IS MARC'S v20 AND IS PINNED BY VALUE.
    # > *"Reorder the cards to be Winning, Losing, then Closing O/U"*
    # ⚠️ Pinned here rather than in a test of its own because this already walks the charted
    # calls in page order — a second walker would be a second copy of the same question.
    assert metrics == ["winning_points", "losing_points", "total"], \
        f"the charted tiles are in the wrong order: {metrics}"


def test_the_two_score_tiles_are_NOT_drawn_on_one_domain_if_the_bounds_diverge():
    """🚨 R-843 — A PIN IS ONLY A PIN IF THE BREAK MOVES IT. The test above would pass on any
    renderer that ignored `bin_min`/`bin_max` entirely and always emitted the same viewBox.

    This stages that break: give the losing metric a DIFFERENT published domain, which is the
    exact condition `assert_an_axis_group_shares_one_domain` exists to prevent upstream, and
    confirm the page-level assertion goes red rather than shrugging.
    """
    from lib import distribution
    win = _dist("winning_points", 38)
    lose = _dist("losing_points", 17, bin_min=0, bin_max=40)
    assert float(win["bin_max"]) != float(lose["bin_max"]), "the staged break did not stage"

    # 🚨 THE OBSERVABLE CONSEQUENCE A READER WOULD BE MISLED BY: with diverging bounds, ONE
    # VALUE lands at two different places. 20 points is a quarter of the way along an 80-point
    # axis and half way along a 40-point one, and the two tiles sit side by side.
    assert distribution._value_to_x(20, win, 140) != distribution._value_to_x(20, lose, 140), (
        "the renderer puts one value at the same pixel on two different domains — it is not "
        "reading bin_min/bin_max, so the test above proves nothing")

    # ⚠️ AND THE POINT OF STAGING IT: the viewBox is `width x height`, so it is IDENTICAL under
    # this break. **The test above cannot catch a divergence on its own** — it catches a
    # renderer that ignores the row, which is a different and weaker claim. The bounds
    # themselves are guaranteed by `assert_an_axis_group_shares_one_domain` in dbt, and that
    # division of labour is recorded here so the next reader does not mistake one for the other.
    import re
    a, b = None, None
    for row in (win, lose):
        svg = distribution.panel(row, width=140, height=56,
                                 ticks=distribution.TICK_EXTREMES, head=False, stats=False)
        box = re.search(r"viewBox='([^']+)'", svg).group(1)
        a, b = (box, b) if row is win else (a, box)
    assert a == b, "viewBox is width x height and both are unchanged by the bounds"


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


def test_THE_UNDEFEATED_TILE_IS_GONE_AND_ITS_COLUMNS_ARE_STILL_PUBLISHED():
    """🚨 A235 (cfdb-main-R-3032). MARC: *"remove Undefeated but Lost kpi card on Today, that
    will free up the space needed for the histograms."*

    ⚠️ THE SECOND HALF IS THE HALF WORTH A TEST. The tile went; `undefeated_teams_lost` and
    `undefeated_teams_entering` stayed on `srv_week_summary`, so this is one commit to reverse
    and is NOT a §3.3 contract — no column was removed, only a reader. A round that "tidied up"
    by dropping the columns too would turn a reversible change into a dbt round, and nothing
    else in the suite would notice.
    """
    # 🚨 R-2260 — A SUBSTRING IS NOT A RULE, AND THIS TEST'S FIRST DRAFT PROVED IT. It searched
    # the function's SOURCE for "Undefeated" and went red on the COMMENT that explains why the
    # tile was removed. A233 paid for this exact shape one round ago. **The question is which
    # tiles the page DRAWS and which columns it READS**, and both are `ast` questions.
    labels = _labels_the_page_actually_draws()
    assert not [x for x in labels if "ndefeated" in x], \
        f"the undefeated tile is still being drawn: {labels}"
    reads = [node.args[0].value for node in ast.walk(_func("_kpi_row"))
             if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "get"
             and node.args and isinstance(node.args[0], ast.Constant)
             and isinstance(node.args[0].value, str)]
    assert not [c for c in reads if "undefeated" in c], \
        f"the page still reads the undefeated columns: {sorted(set(reads))}"
    model = (ROOT / "dbt/models/serving/srv_week_summary.sql").read_text()
    for column in ("undefeated_teams_lost", "undefeated_teams_entering"):
        assert column in model, (
            f"{column} was removed from srv_week_summary. A235 removed a READER, not a column "
            f"— dropping the column makes the tile's removal a contract step (§3.3) instead of "
            f"a one-commit reversal.")


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
    # ⚠️ A235: the slice used to end at `.cfdb-kpi-pair`, which this round DELETED along with
    # the tile that emitted it. An index anchor on a rule that no longer exists raises
    # ValueError and reads as a broken test rather than a broken page.
    kpi_css = THEME[THEME.index(".cfdb-kpirow"):THEME.index(".cfdb-kpi-label {")]
    assert "overflow-x" not in kpi_css, "the KPI row grew its own scroll mechanism"


@pytest.mark.parametrize("name", ["_kpi_row", "_kpi_rate", "_kpi_figure"])
def test_THE_PANEL_EXISTS_UNDER_THE_NAME_THE_TESTS_AND_TABS_USE(name):
    """R-2353: a comment or a registry naming a function that does not exist is worse than
    silence, because the name is what the next round will trust."""
    assert _func(name) is not None


# ══════════════════════════════════════════════════════════════════════════════════════════
# A231 — THE ROW SAYS WHAT IT IS, AND STOPS WRAPPING
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# > **MARC, v17:** *"The text blurb seems inaccurate. The KPI's are based on FBS. Doesn't seem
# > impacted by Division filter or Conference filter."* · *"It should consume the same width
# > as the Most Exciting table."* · *"'Undefeated Teams that Lost' wraps. Title can be reduced
# > to 'Undefeated but Lost'."* · *"Once the title wordwrap is fixed, KPI font has room to
# > grow."*

# The seven labels the page expects to draw, as DATA — the roster, not the subject.
# 🚨 A235 (cfdb-main-R-3028 · R-3030 · R-3032). THREE OF THESE SEVEN MOVED IN ONE ROUND, and
# the count stayed at seven: *Undefeated but lost* was REMOVED on Marc's instruction and
# *Winning vs losing score* SPLIT IN TWO, so he freed the WIDTH of one tile rather than a slot.
# 🚨 A239 (cfdb-main-R-3235). > **MARC, v19:** *"Winning Score and Losing Score titles should be
# prefixed with AVG."* 📊 And the widths did not move: A239 measured 927.3px at 1440, the same
# figure A235 and A237 measured — the THIRD round running to find that these tiles size on their
# SUB-LINE and not on their label. The length budget below is what keeps that honest.
_KPI_LABELS = ("FBS games", "Avg closing O/U", "Avg winning score", "Avg losing score",
               "Favorites won", "Favorites covered", "O/U \u2013 over %")


def _labels_the_page_actually_draws() -> list:
    """Every first argument to `_kpi_figure` inside `_kpi_row` — the labels that SHIP.

    🚨 READ FROM THE SOURCE, NOT FROM `_KPI_LABELS`. The budget test below exists to catch a
    label somebody LENGTHENS, and a version of it that iterated over the tuple above would
    have gone on passing while the page drew something else entirely — the test would be
    asserting that a constant in the test file is short. R-768's shape: the subject has to
    come from the thing under test.
    """
    found = []
    for node in ast.walk(_func("_kpi_row")):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_kpi_figure"
                and node.args and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            found.append(node.args[0].value)
    return found


def test_the_caption_says_NEITHER_filter_reaches_this_row():
    """🚨 MARC REPORTED BOTH FILTERS AND THE CAPTION NAMED ONLY ONE.

    📊 It is structural, not a wording slip: `srv_week_summary` publishes thirty columns and
    not one is a conference or a division — its grain is (season, season_type, week) — and
    `_week_summary`'s WHERE clause passes exactly those three. **Neither filter CAN reach
    this row**, and both selectors are on screen while a reader looks at it.

    ⚠️ THE CONFERENCE HALF IS THE MORE IMPORTANT ONE: a reader who has just narrowed to one
    conference is the reader most likely to believe these seven figures moved with it.
    """
    body = ast.get_source_segment(SOURCE, _func("_kpi_row")) or ""
    caption = body[body.index("st.caption("):]
    for word in ("Conference", "Division"):
        assert word in caption, f"the caption does not name the {word} filter"
    assert "Neither" in caption or "neither" in caption, (
        "the caption must say the filters do NOT apply, not merely mention them")


def test_the_caption_does_not_claim_both_teams_are_FBS():
    """📊 THE MODEL'S RULE IS *EITHER SIDE*, AND THE TWO DIFFER BY ENOUGH TO MATTER.

    Measured on 2026 week 12: either-side-FBS 70, both-sides-FBS 66, all games 130, and
    `fbs_games` published 70. A caption reading "FBS games" without qualification invites the
    stricter reading, which is wrong by four games in that week alone.
    """
    body = ast.get_source_segment(SOURCE, _func("_kpi_row")) or ""
    caption = body[body.index("st.caption("):body.index("tiles = []")]
    assert "either side" in caption, "the caption must state the either-side rule"


def test_no_kpi_label_is_long_enough_to_wrap():
    """🚨 THIS IS WHAT REPLACED A225's RESERVED SECOND LINE, AND IT IS THE POINT OF THE SWAP.

    A225 gave every label `min-height:3.2em` because one label wrapped and pushed its numeral
    17.4 CSS px below the other six. A231 shortened that label to Marc's own wording and made
    the tiles grow-only, so **no label's text wraps at 1600, 1440, 1300 or 1024 in either
    scheme** — measured on the text's own line boxes, not on the box height.

    ⚠️ THE RESERVE MADE THE NEXT FAILURE INVISIBLE. With it in place a longer label would
    simply have used the second line and nothing would have looked wrong, while that tile's
    numeral sat lower than the other six — which is precisely what happened and took a render
    to find. **Removing it makes the failure visible; this test makes it loud.**

    📊 THE BUDGET IS MEASURED, NOT CHOSEN. The tile caps at `max-width:11rem` = 176px, less
    `.65rem` of padding each side = 155.2px of text. At `.68rem` uppercase with `.03em`
    tracking the longest surviving label, "Winning vs losing score" (23 chars), renders inside
    that. 24 characters is the first length not verified to fit, so that is the line.
    """
    labels = _labels_the_page_actually_draws()
    # 🚨 R-760: a loop that iterates zero times reports success. The extractor must find all
    # seven, and they must be the seven this file knows about, or the budget checks nothing.
    assert len(labels) == 7, f"found {len(labels)} labels in _kpi_row, not 7: {labels}"
    assert set(labels) == set(_KPI_LABELS), (
        f"the page draws labels this test does not know about: "
        f"{sorted(set(labels) ^ set(_KPI_LABELS))}")
    for label in labels:
        assert len(label) <= 23, (
            f"{label!r} is {len(label)} characters; the widest tile holds 23 on one line, so "
            f"this wraps and pushes its numeral off the shared baseline. Shorten it, or "
            f"restore a reserved second line on .cfdb-kpi-label for every tile.")


def test_the_over_under_tile_cannot_be_read_as_score_arithmetic():
    """🚨 A235 (cfdb-main-R-3028). THE LABEL MISLED ITS OWN AUTHOR AND THAT IS THE DEFECT.

    > **MARC, v18:** *"Average Over/Under - is this the average(Home Score - Away Score) of the
    > Completed FBS games?"*

    📊 No. `srv_week_summary.sql` computes it as `avg(total_at_close)` — the average closing
    TOTAL the sportsbooks posted, with no score in it at all. **A label its own commissioner
    misreads is a defect, not a preference**, and this pins the fix by VALUE: the two market
    words have to be there, and the old wording has to be gone.

    ⚠️ AND IT CHECKS THE MODEL, NOT ONLY THE PAGE. If `over_under_mean` ever stopped being a
    market average the label would become wrong in the opposite direction, and the round that
    changed it would get a red test naming this one.
    """
    # ⚠️ THE LABELS THE PAGE DRAWS, NOT THE SOURCE TEXT (R-2260) — the old wording is quoted in
    # the comment above the tile, which is exactly where it belongs and exactly what a substring
    # search trips over.
    labels = _labels_the_page_actually_draws()
    assert "Avg closing O/U" in labels, \
        f"the over/under tile's label moved without this test: {labels}"
    assert "Average over/under" not in labels, "the misleading label is still on the page"
    # 📊 THE MODEL LINE THE LABEL IS ABOUT, READ FROM THE MODEL. Comments are stripped first,
    # because this file discusses `total_at_close` in prose and a substring is not a rule
    # (R-2260) — the claim is that the PUBLISHED EXPRESSION is a market average.
    model = (ROOT / "dbt/models/serving/srv_week_summary.sql").read_text()
    code = "\n".join(line.split("--")[0] for line in model.splitlines())
    built_from = [line.strip() for line in code.splitlines() if "over_under_mean" in line]
    assert built_from, "srv_week_summary no longer publishes over_under_mean"
    assert any("total_at_close" in line for line in built_from), (
        f"over_under_mean is no longer the average closing LINE — it is now {built_from!r}. "
        f"The tile's label says 'Avg closing O/U' because the number is the sportsbooks', "
        f"not a score; if the model changed, the label has to change with it.")


def test_the_over_percentage_tile_carries_marcs_own_string():
    """> **MARC, v18:** *"Went Over - change to O/U - OVER %"*

    ⚠️ SENTENCE CASE IN CODE, CAPS ON SCREEN. `.cfdb-kpi-label` carries
    `text-transform:uppercase`, so `O/U – over %` renders as `O/U – OVER %`, which is what he
    asked for. Writing it capitalised in source would make it the only label shouting in the
    file. **Pinned by value, because the point of the change is the string.**
    """
    labels = _labels_the_page_actually_draws()
    assert "O/U \u2013 over %" in labels, \
        f"the over-percentage label is not Marc's string: {labels}"
    assert "Went over" not in labels, "the old label is still there"


def test_the_tiles_grow_into_the_row_but_never_shrink_out_of_it():
    """🚨 `flex:1 0 auto` — AND BOTH DIGITS WERE DECIDED BY A MEASUREMENT.

    📊 `0 0 auto` (before): seven tiles summed to 864.1px inside a 980px box at 1440 and a
    1140px box at 1600 — the row could never fill either, which is what Marc asked for.
    📊 `1 1 auto`: fills correctly at 1440 and 1600, and at 1300 and 1024 the tiles shrink
    toward `min-width` and **four and five labels start wrapping** — reintroducing the exact
    defect this round removed.
    📊 `1 0 auto`: fills at 1440 and 1600 (tiles + gaps = 980.0 and 1140.0 exactly), keeps
    content width at 1300 and 1024, and wraps nothing at any of the four.
    """
    rule = THEME[THEME.index(".cfdb-kpi {"):]
    rule = rule[:rule.index("}")]
    assert "flex:1 0 auto" in rule, (
        "the tiles must grow into spare width and never shrink below their content")
    assert "min-width:6rem" in rule, "the scroll floor is what keeps a narrow row honest"


def test_the_label_reserves_no_second_line_any_more():
    """The reserve is gone and `test_no_kpi_label_is_long_enough_to_wrap` is what replaced it.
    If both this and that test were removed, a long label would silently break the baseline
    again — so this one asserts the CSS and that one asserts the cause."""
    rule = THEME[THEME.index(".cfdb-kpi-label {"):]
    rule = rule[:rule.index("}")]
    assert "min-height" not in rule, (
        "a reserved second line is 17.4px of empty space on every tile once no label wraps")


# ── A237 — four gaps that staged breaks found GREEN, each closed at the PAGE ────────────────

def test_ALL_THREE_CHARTS_SHARE_ONE_FIXED_FRAME():
    """🚨 A243 (cfdb-main-R-3321) REPLACES A237's VERSION OF THIS, AND THE PROPERTY GOT STRONGER.

    A237 computed the frame as the UNION of the two score metrics' whiskers and this test pinned
    that both tiles received the same object — because two correct calls with one metric each
    would be two correct calls that disagree.

    > **MARC, v20:** *"Standardize the x-axis for Closing, Winning, and Losing cards to run from
    > 0 to 70."* — and he chose **80** when offered headroom.

    ✅ **So the frame is now a CONSTANT shared by all three, including the O/U card, which never
    shared a scale with the other two.** ⚠️ The old test is not deleted, it is superseded: the
    thing it protected — *the cards can be compared to each other* — is what this asserts, over a
    wider set.
    """
    import today
    assert today._KPI_AXIS == (0.0, 80.0), (
        f"the fixed frame is {today._KPI_AXIS}; Marc chose 0-80")
    # no chart may be handed a frame of its own
    calls = [n for n in ast.walk(_func("_kpi_row"))
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_kpi_chart"]
    assert len(calls) == 3, f"expected three charted tiles, found {len(calls)}"
    for call in calls:
        assert len(call.args) == 2, (
            f"a KPI chart is passed {len(call.args)} arguments — a per-tile axis is back, and "
            f"three cards on three scales cannot be compared")
    import re
    from lib import distribution
    geom = lambda svg: re.search(r"viewBox='([^']+)'", svg).group(1)      # noqa: E731
    a = today._kpi_chart(_dist("winning_points", 38), "winning_points")
    b = today._kpi_chart(_dist("losing_points", 17), "losing_points")
    c = today._kpi_chart(_dist("total", 52), "total")
    assert geom(a) == geom(b) == geom(c), "the three charts are not drawn on one geometry"
    # and the frame really is 0-80, not whatever the rows happened to carry
    lo, hi = today._KPI_AXIS
    row = _dist("winning_points", 38)
    assert distribution.clamped_to_axis(lo, row, 140, today._KPI_AXIS)[0] == 0.0
    assert distribution.clamped_to_axis(hi, row, 140, today._KPI_AXIS)[0] == 140.0


def test_THE_BARS_MOVE_WITH_THE_AXIS_not_just_the_box():
    """🚨 THE SECOND GREEN BREAK. Reverting `_bars` to its even spread left the box and the ruler
    on the narrowed axis and the HISTOGRAM on the old one — two scales inside one SVG, which is
    the exact defect drawing them in a single element was supposed to make impossible.

    ⚠️ `wide != tight` IS NOT ENOUGH and that is what let it through: the box alone moving makes
    the strings differ. This compares the BAR geometry specifically.
    """
    import re
    from lib import distribution
    row = _dist("winning_points", 38)
    # 🚨 BARS ONLY, NOT EVERY `<rect>` — AND THE FIRST DRAFT OF THIS TEST GOT THAT WRONG, WHICH
    # IS WHY THE BREAK CAME BACK GREEN TWICE. A panel emits the box's p25-p75 rectangle as a
    # `<rect>` too, and THAT one moves with the axis whether or not the bars do — so a match on
    # `<rect` compared two lists that always differ and asserted nothing. R-859 inside the test
    # written to catch R-859's shape. The bars carry `fill-opacity='0.NN'` from a `:.2f`; the box
    # carries the literal `.22` and a `stroke`.
    bars = lambda svg: re.findall(  # noqa: E731
        r"<rect x='([\d.]+)' y='[\d.]+' width='([\d.]+)'[^>]*fill-opacity='0\.\d+'/>", svg)
    wide = bars(distribution.panel(row, width=140, height=28, head=False, stats=False))
    tight = bars(distribution.panel(row, width=140, height=28, head=False, stats=False,
                                    axis=(14.0, 59.0)))
    assert wide and tight, "no bars drawn (R-2254)"
    assert wide != tight, (
        "the histogram bars are identical with and without a narrowed axis — `_bars` is still "
        "spreading the published counts evenly, so the bars and the box are on two scales")


def test_THE_BOX_BAND_GREW_50_PERCENT_AND_THE_HISTOGRAM_IS_GONE():
    """> **MARC, v20:** *"Remove the histograms. Increase the vertical size of the box-whisker
    > chart (not the axis and tickmarks) by 50%."*

    🚨 SUPERSEDES A237's `..._HISTOGRAM_BAND_IS_HALVED`, which pinned `_KPI_CHART_H = 28`. There
    is no histogram band to pin any more, so the test pins what replaced it — **and the clause
    that must NOT move with it.**

    📊 Measured from the rendered SVG before the change: box band **12px** inside **140 x 55**.
    +50% is **18**, and the total becomes **0 + 18 + 15 = 33**.
    """
    import re
    import today
    from lib import distribution
    assert today._KPI_BOX_H == 18, (
        f"the box band is {today._KPI_BOX_H}; 12 + 50% is 18")
    svg = today._kpi_chart(_dist("winning_points", 38), "winning_points")
    total = int(re.search(r"viewBox='0 0 \d+ (\d+)'", svg).group(1))
    assert total == today._KPI_BOX_H + distribution.LABEL_BAND, (
        f"the chart is {total}px; box {today._KPI_BOX_H} + axis {distribution.LABEL_BAND} is "
        f"{today._KPI_BOX_H + distribution.LABEL_BAND} — something other than the box moved")
    # 🚨 "not the axis and tickmarks" — his words, so the axis is pinned NOT to have changed
    assert today._KPI_TICK_STEP == 5 and today._KPI_TICK_LABEL_STEP == 10
    assert distribution.LABEL_BAND == 15
    # and no bars survive
    bars = re.findall(r"<rect x='[\d.]+' y='[\d.]+' width='[\d.]+'[^>]*fill-opacity='0\.\d+'/>",
                      svg)
    assert not bars, f"{len(bars)} histogram bars are still drawn"
    # exactly ONE median mark — there were two before, the box rule and the histogram tick
    medians = re.findall(r"stroke-width='2'", svg) + re.findall(r"stroke-opacity='0.95'", svg)
    assert len(medians) == 1, f"{len(medians)} median marks; the histogram tick was duplicated"


def test_EVERY_CHARTED_TILE_CARRIES_ITS_p25_p50_p75():
    """> **MARC, 2026-09-25:** *"How about a tight table to the right KPI value that shows p25,
    > p50, p75."*

    🚨 THE FOURTH GREEN BREAK: emptying `_kpi_stats` removed the table from all three tiles and
    nothing went red. **Asserted at the page**, because the module-level test only proves the
    renderer CAN produce a table."""
    import today
    fn = _func("_kpi_row")
    stats_calls = [n for n in ast.walk(fn)
                   if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_kpi_stats"]
    assert len(stats_calls) == 3, (
        f"{len(stats_calls)} of the three charted tiles ask for a stats block")
    html = today._kpi_stats(_dist("winning_points", 38))
    assert html, "the stats block is empty for a row that has percentiles"
    for key in ("p25", "median", "p75"):
        assert f"<span>{key}</span>" in html, f"{key} is missing from the KPI stats block"
    assert "<span>min</span>" not in html and "<span>n</span>" not in html, (
        "the KPI stats block is showing rows Marc did not ask for; it is meant to be tight")
    assert today._kpi_stats(None) == "", "an absent row must render nothing, not a broken table"


# ── A239 — three gaps that staged breaks found GREEN ────────────────────────────────────────

def test_THE_AXIS_IS_LABELLED_ON_THE_EVEN_VALUES():
    """> **MARC, v19:** *"Label x-axis on the even values (10, 20, 30, etc)."*

    🚨 A STAGED BREAK CAME BACK GREEN: moving the label step from 10 to 5 put a number on every
    mark and nothing went red. **Pinned by VALUE**, like `_KPI_CHART_H`, because the point of the
    change IS the number — a test on "some label step" passes on the reading Marc did not ask
    for.

    ⚠️ AND THE TWO STEPS ARE PINNED AS A RELATIONSHIP, not just individually: the marks stay
    finer than the labels. A round that set them equal would satisfy both value checks and lose
    A237's ruler.
    """
    import today
    assert today._KPI_TICK_LABEL_STEP == 10, (
        f"the axis labels every {today._KPI_TICK_LABEL_STEP}, not the 10 Marc asked for")
    assert today._KPI_TICK_STEP == 5, "the tick marks moved off 5"
    assert today._KPI_TICK_LABEL_STEP > today._KPI_TICK_STEP, (
        "every mark now carries a number; Marc asked for marks every 5 and labels on the 10s")
    import re
    from lib import distribution
    svg = today._kpi_chart(_dist("winning_points", 38), "winning_points")
    labels = [float(t) for t in re.findall(r"<text[^>]*>([\d.]+)</text>", svg)]
    assert labels, "the axis drew no labels at all"
    for v in labels:
        assert abs(v / today._KPI_TICK_LABEL_STEP
                   - round(v / today._KPI_TICK_LABEL_STEP)) < 0.05, (
            f"a label landed at {v}, which is not a multiple of "
            f"{today._KPI_TICK_LABEL_STEP}")
    marks = re.findall(r"<line x1='[\d.]+'[^>]*stroke-opacity='\.45'", svg)
    assert len(marks) > len(labels), (
        f"{len(marks)} marks and {len(labels)} labels — the ruler is no finer than the labels")
    assert distribution.LABEL_BAND > distribution.TICK_BAND, \
        "the label band should cost more than a bare ruler; one of them moved"


def test_THE_STATS_BLOCK_IS_TOP_ALIGNED_WITH_THE_NUMERAL():
    """> **MARC, v19:** *"Move the p25, med, p75 up to be aligned with the top of the KPI # and
    > remove the wasted whitespace."*

    🚨 A STAGED BREAK CAME BACK GREEN: reverting to `align-items:baseline` put the block back
    where he asked it not to be, with nothing red. `baseline` sits the FIRST stat row on the
    numeral's baseline and pushes the other two below it — which is the wasted whitespace.
    """
    rule = THEME[THEME.index(".cfdb-kpi-head {"):]
    rule = rule[:rule.index("}")]
    assert "align-items:flex-start" in rule, (
        f"the stats block is not top-aligned with the numeral: {rule.strip()}")
    assert "align-items:baseline" not in rule
    stats = THEME[THEME.index(".cfdb-kpi-head .cfdb-dist-stats {"):]
    stats = stats[:stats.index("}")]
    assert "font-size:.64rem" in stats, (
        f"the stats font is not the one-increment-larger size: {stats.strip()}")


def test_A_CARRIED_DATASET_LABEL_NAMES_ITS_OWN_VIEW():
    """🚨 THE THIRD GREEN BREAK, AND IT IS THE SUBTLE ONE. `dataset_also` carries a
    `(label, table)` pair; pointing the LABEL at a different view than the TABLE produces a
    caption that links correctly and reads wrongly — a dataset line naming one thing and opening
    another.

    ⚠️ The test that checks the label "reaches the reader" walks the TABLE side, so it could not
    see this. Here the two halves are required to agree.
    """
    pairs = []
    for node in ast.walk(_func("_kpi_row")):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "section"):
            continue
        for kw in node.keywords:
            if kw.arg != "dataset_also":
                continue
            for element in getattr(kw.value, "elts", []):
                parts = getattr(element, "elts", [])
                assert len(parts) == 2, f"dataset_also takes (label, table) pairs: {parts}"
                pairs.append(parts)
    assert pairs, "the KPI row carries no additional dataset label (R-2254)"
    for label_node, table_node in pairs:
        assert isinstance(table_node, ast.Constant), "the table must be a literal"
        # the label must be DATASETS[<that same view>], not DATASETS[<something else>]
        assert isinstance(label_node, ast.Subscript), (
            f"the label for {table_node.value} is not read from DATASETS: "
            f"{ast.dump(label_node)[:90]}")
        assert getattr(label_node.value, "id", "") == "DATASETS"
        assert label_node.slice.value == table_node.value, (
            f"the caption labels {table_node.value!r} with "
            f"{label_node.slice.value!r}'s name — the line would link one view and name another")


def _week_distributions_sql() -> str:
    """The SQL literal `_week_distributions` actually runs, read from the `ast`.

    ⚠️ NOT A GREP OF THE MODULE (R-2260). `today.py` mentions `srv_week_metric_distribution` in
    a docstring, in a `DATASETS` key and in a `states.section` call, and none of those is the
    query. The one that reaches the database is the first argument of the `query(...)` call
    inside this function, so that is what is read.
    """
    for node in ast.walk(_func("_week_distributions")):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "query":
            first = node.args[0]
            assert isinstance(first, ast.Constant), "the query is not a literal"
            return first.value
    raise AssertionError("_week_distributions makes no query() call")


def _selected_columns(sql: str) -> set:
    """Every column name the select list names, parsed by sqlglot rather than split on commas."""
    import sqlglot
    from sqlglot import expressions as exp
    select = sqlglot.parse_one(sql, read="postgres")
    assert isinstance(select, exp.Select), f"not a SELECT: {type(select).__name__}"
    return {e.alias_or_name for e in select.expressions}


def test_THE_KPI_STATS_TABLE_ASKS_FOR_NOTHING_THIS_QUERY_DOES_NOT_SELECT():
    """🚨 A243 SHIPPED THIS DEFECT AND THE 1440 CROP IS WHAT FOUND IT.

    `_KPI_STATS` was widened to five rows and `_week_distributions` was left selecting three.
    `stats_table` reads `row.get(key)`, so `p05` and `p95` drew their honest en dash on all
    three charts — beside values that were in serving the whole time.

    ⚠️ EVERY OTHER INSTRUMENT SAID GREEN: the columns publish, nothing raised, the suite passed
    and the error-card count was zero. **A missing key is indistinguishable from a null one at
    the renderer**, which is exactly why the agreement has to be asserted at the two ends rather
    than observed in the middle.

    ✅ IT FIRES ON THE REAL BREAK: delete `p05` from the select list and this goes red naming it.
    ⚠️ And it is asserted at the SOURCE rather than through a render, deliberately — a render
    needs a database and CI has none, so a test that reaches for one skips exactly where it is
    most needed.
    """
    import today
    selected = _selected_columns(_week_distributions_sql())
    missing = [key for key in today._KPI_STATS if key not in selected]
    assert not missing, (
        f"the KPI tiles draw {missing} and `_week_distributions` does not select them — "
        f"`stats_table` would render an en dash for each. Selected: {sorted(selected)}")


def test_EVERY_KPI_STAT_IS_A_COLUMN_THE_PANEL_REGISTRY_KNOWS():
    """⚠️ THE OTHER END OF THE SAME AGREEMENT, AND IT IS NOT THE SAME TEST.

    `stats_table` keeps `PANEL_STATS`'s order and filters to the caller's keys, so a key that
    is in the SELECT LIST but not in the registry is silently dropped — the tile loses a row
    and nothing anywhere says so. R-2254: the filter returning fewer pairs is not a failure,
    it is an empty collection, and an empty collection is not a pass.
    """
    import today
    from lib import distribution
    known = {key for _, key in distribution.PANEL_STATS}
    unknown = [key for key in today._KPI_STATS if key not in known]
    assert not unknown, (
        f"{unknown} is asked for by `_KPI_STATS` and is not in `PANEL_STATS`, so "
        f"`stats_table` drops it without a word. Registry: {sorted(known)}")
