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
    median_x = lambda svg: re.search(                                     # noqa: E731
        r"<line x1='([\d.]+)'[^>]*stroke-opacity='0.95'", svg).group(1)
    assert median_x(a) != median_x(b), (
        "both medians are at the same x on a shared axis — the chart is not reading the row")


def test_THE_KPI_ROW_ACTUALLY_ASKS_FOR_AN_AXIS():
    """🚨 A STAGED BREAK FOUND THIS GAP AND IT IS THE POINT OF STAGING THEM.

    > **MARC, v18:** *"Might need more vertical real estate to include an x-axis with labels in
    > the box-whisker diagram."*

    `tests/test_distribution_axis_labels.py` proves `panel()` CAN draw an axis. **Changing the
    page's own call to `ticks=TICK_NONE` left all 37 tests green** — the axis Marc asked for
    would have vanished from the site with nothing red, because every axis test was pointed at
    the module and none at the caller. This is the caller.
    """
    import re
    import today
    svg = today._kpi_chart(_dist("winning_points", 38), "winning_points")
    labels = re.findall(r"<text[^>]*>([^<]*)</text>", svg)
    assert labels, (
        "the KPI charts draw no axis labels. Marc asked for an x-axis with labels; the page "
        "is asking distribution.panel() for TICK_NONE.")
    assert all(re.fullmatch(r"-?[\d.]+", t) for t in labels), \
        f"the axis is emitting something that is not a number: {labels}"


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
    assert metrics == ["total", "winning_points", "losing_points"], \
        f"the charted tiles changed: {metrics}"


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
_KPI_LABELS = ("FBS games", "Avg closing O/U", "Winning score", "Losing score",
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
