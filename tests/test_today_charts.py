"""A190 — the two charts: the scatter's hover, its distance table, and the poll scoreboard.

⚠️ THESE ARE THE ASSERTIONS THAT CAN BE MADE WITHOUT A BROWSER OR A WAREHOUSE. CI has
neither, so the geometry and the live hover are proved by `ci/measure_*` and by renders
recorded in the report; what lives here is the logic those pictures cannot pin down — which
quadrant qualifies, where the centre is, and what each of the three absences renders as.
"""
import math
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                   # noqa: E402

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
MODEL = (ROOT / "dbt" / "models" / "serving" / "srv_rankings.sql").read_text()


def _rows(skew=True):
    """Nine teams on a 3x3 grid of (allowed, gained), plus one deliberate outlier.

    ⚠️ THE GRID IS DELIBERATE: medians land on 200 allowed and 400 gained, so every team's
    quadrant is decidable by eye and the expected distances are exact.

    🚨 AND THE OUTLIER IS WHAT MAKES THE MEDIAN TESTABLE AT ALL — R-843. On the bare
    symmetric grid the MEAN and the MEDIAN are both (200, 400), so a staged break swapping
    `statistics.median` for `statistics.fmean` came back GREEN on the median test: the pinned
    value did not move under the break. One extreme team drags the mean well off the median
    and leaves the median where it was, which is the whole point of preferring it.
    """
    out = []
    for allowed in (100, 200, 300):
        for gained in (300, 400, 500):
            out.append({"team": f"a{allowed}g{gained}", "x": float(allowed),
                        "y": float(gained), "games": 3})
    if skew:
        out.append({"team": "outlier", "x": 2000.0, "y": 2000.0, "games": 3})
    return out


def test_the_medians_are_the_ones_the_chart_draws():
    """🚨 ONE SOURCE. The table measures from the intersection the reader can SEE.

    Marc asked for distance from *"the intersection of the 2 means or medians showing the
    dotted line"*. If the table computed its own centre the two could drift apart and the
    table would be measuring from somewhere the chart does not draw — R-645's class.
    """
    import statistics

    rows = _rows()
    mid_x, mid_y, n_x, n_y = today._scatter_medians(rows)
    assert (mid_x, mid_y) == (200.0, 400.0)
    assert (n_x, n_y) == (10, 10)

    # 🚨 THE ASSERTION THAT ACTUALLY DISTINGUISHES A MEDIAN FROM A MEAN. Without the outlier
    # the two are identical on this fixture and a `median -> fmean` break passes untouched.
    mean_x = statistics.fmean([r["x"] for r in rows])
    assert mean_x != mid_x, "the fixture must separate the mean from the median (R-843)"
    assert mid_x == 200.0, (
        f"the centre must be the MEDIAN the chart draws, not the mean ({mean_x:.1f}) — "
        f"the table measures from the dotted lines the reader can see")
    assert today._scatter_medians([]) is None, "an empty frame has no centre, not a zero one"


def test_only_the_top_right_quadrant_is_ranked_and_the_inequality_is_the_right_way_round():
    """🚨 THE AXIS RUNS RIGHT-TO-LEFT, SO "BETTER" ON X IS **LESS**.

    A176 transposed this chart: x is yards ALLOWED and fewer is better, so the top-right
    quadrant is `y > median AND x < median`. ⚠️ **Getting that inequality backwards ranks the
    WORST teams while looking entirely plausible** — the table would still be full, still be
    ordered, and still be wrong. That is why it is asserted rather than eyeballed.
    """
    ranked, centre = today._distance_ranking(_rows(), limit=10)
    assert centre == (200.0, 400.0)
    teams = {row["team"] for _distance, row in ranked}

    # better than the median on BOTH axes: allowed 100 (< 200) and gained 500 (> 400)
    assert "a100g500" in teams, "the strongest team must be ranked"
    # the mirror image must NOT be
    assert "a300g300" not in teams, (
        "a team worse than the median on both axes is in the BOTTOM-LEFT quadrant; if it is "
        "here the inequality is inverted and the table is ranking the weakest teams")
    # and neither may a team that is better on only one axis
    assert "a100g400" not in teams and "a200g500" not in teams, (
        "the quadrant requires better than the median on BOTH axes, not either")
    assert teams == {"a100g500"}, teams


def test_the_distance_is_the_hypotenuse_in_yards_per_game():
    """> **MARC:** *"the longest hypotenuse."* Both axes are already yards per game, so no
    scaling is applied — a normalised distance would be a different, unstated statistic."""
    rows = _rows() + [{"team": "far", "x": 100.0, "y": 500.0, "games": 3}]
    ranked, _centre = today._distance_ranking(rows, limit=10)
    distance, row = ranked[0]
    assert row["team"] in ("far", "a100g500")
    assert distance == pytest.approx(math.hypot(100.0, 100.0)), (
        "distance must be sqrt(dx^2 + dy^2) over the raw yards, unscaled")


def test_an_empty_quadrant_says_so_rather_than_drawing_an_empty_table():
    """AC-G.11: a conference filter can leave nobody better than the median on both axes."""
    flat = [{"team": f"t{i}", "x": 200.0, "y": 400.0, "games": 3} for i in range(5)]
    ranked, _centre = today._distance_ranking(flat, limit=10)
    assert ranked == [], "nobody is strictly better than the median here"
    html = today._distance_table(ranked, None, len(flat))
    assert "No team in this scope is better" in html
    assert "cfdb-far-row" not in html


def test_the_table_header_says_the_rank_is_not_the_ap_rank():
    """🚨 A "#" COLUMN BESIDE TEAM LOGOS ON A PAGE THAT ALSO DRAWS AP POLLS READS AS THE AP
    RANK. This panel's own hover shows the AP rank two inches away, so the distance rank has
    to disclaim itself — a true-looking label on a different number is §4.3's worst form."""
    ranked, centre = today._distance_ranking(_rows(), limit=10)
    html = today._distance_table(ranked, centre, 9)
    assert "not the AP rank" in html


@pytest.mark.parametrize("value,expected", [
    (0.9853, "p99"), (1.0, "p100"), (0.0, "p0"), (None, ""), (float("nan"), ""),
])
def test_the_percentile_is_scaled_from_the_published_fraction(value, expected):
    """🚨 THE COLUMN IS A FRACTION IN [0, 1], AND THE FIRST DRAFT SHIPPED `p1` FOR THE BEST
    OFFENCE IN THE COUNTRY.

    Caught in the render, not the code: Georgia's hover read `p1` at 576.5 yards gained per
    game, second most of 138. `int(round(0.99))` is 1. ⚠️ It would have read as a plausible
    number — in range, next to a team genuinely at one extreme, and exactly backwards.
    """
    row = {"team": "T", "x": 1.0, "y": 2.0, "games": 1,
           "total_yards_for_percentile": value, "total_yards_allowed_percentile": value,
           "logo_url": None, "record_before_display": None, "percentile_population": 138,
           "rank": None, "opponent": None}
    html = today._scatter_hotspot(row, 0.5, 0.5, lambda s: str(s))
    if expected:
        assert f"<i>{expected}</i>" in html, html
    else:
        assert "<i>p" not in html, "an absent percentile must render nothing, not p0"


def test_an_unranked_team_says_unranked_rather_than_printing_nan():
    """🚨 `ap_rank` IS NULL FOR 113 OF 138 TEAMS AND `NaN` IS TRUTHY (A191).

    `if rank` is true for a NaN, so a truthiness test would print `#nan` as a rank on every
    unranked team — which is the defect A191 spent a round removing from the Week average row.
    """
    base = {"team": "T", "x": 1.0, "y": 2.0, "games": 1, "logo_url": None,
            "record_before_display": None, "percentile_population": None,
            "total_yards_for_percentile": None, "total_yards_allowed_percentile": None,
            "opponent": None}
    unranked = today._scatter_hotspot({**base, "rank": float("nan")}, 0.5, 0.5, str)
    assert "unranked" in unranked and "nan" not in unranked.lower()
    ranked = today._scatter_hotspot({**base, "rank": 7}, 0.5, 0.5, str)
    assert "#7" in ranked and "unranked" not in ranked


def test_the_tooltip_flips_away_from_the_edge_it_would_be_clipped_by():
    """CSS cannot ask where its element sits, so the side is computed from the point."""
    base = {"team": "T", "x": 1.0, "y": 2.0, "games": 1, "logo_url": None, "rank": None,
            "record_before_display": None, "percentile_population": None,
            "total_yards_for_percentile": None, "total_yards_allowed_percentile": None,
            "opponent": None}
    assert "data-side='right'" in today._scatter_hotspot(base, 0.1, 0.5, str)
    assert "data-side='left'" in today._scatter_hotspot(base, 0.9, 0.5, str)
    assert "data-vert='up'" in today._scatter_hotspot(base, 0.5, 0.05, str)


def test_the_hover_is_focusable_so_it_works_on_a_tap_and_a_keyboard():
    """🚨 `:hover` ALONE IS A MOUSE-ONLY FEATURE. Streamlit strips `<script>`, so the tooltip
    is CSS-only — `tabindex` plus `:focus-within` is what makes it reachable otherwise."""
    base = {"team": "T", "x": 1.0, "y": 2.0, "games": 1, "logo_url": None, "rank": None,
            "record_before_display": None, "percentile_population": None,
            "total_yards_for_percentile": None, "total_yards_allowed_percentile": None,
            "opponent": None}
    assert "tabindex='0'" in today._scatter_hotspot(base, 0.5, 0.5, str)
    theme = (ROOT / "site" / "lib" / "theme.py").read_text()
    assert ".cfdb-sc-hot:focus-within .cfdb-sc-tip" in theme


def test_the_scoreboard_distinguishes_its_three_absences():
    """🚨 THREE ABSENCES, AND THEY ARE NOT THE SAME ONE (AC-G.11).

    ⚠️ AND EVERY TEST IS `pd.isna`, NOT TRUTHINESS. `NaN` is truthy, so `if points` is true
    for an unplayed game — and **0 is falsy**, so a shutout would render as "not yet played".
    Truthiness fails at both ends.
    """
    frame = pd.DataFrame([
        {"explained_by_game_week": None, "game_away_display": None,
         "game_away_record_after": None, "game_away_points": None,
         "game_home_display": None, "game_home_record_after": None,
         "game_home_points": None},
        {"explained_by_game_week": 3.0, "game_away_display": "A",
         "game_away_record_after": "1-1", "game_away_points": None,
         "game_home_display": "B", "game_home_record_after": "2-0",
         "game_home_points": None},
        {"explained_by_game_week": 3.0, "game_away_display": "Ohio State",
         "game_away_record_after": "1-1", "game_away_points": 0,
         "game_home_display": "Texas", "game_home_record_after": "2-0",
         "game_home_points": 24},
    ])
    out = today._scoreboard_lines(frame)
    assert out["scoreboard_away"].tolist() == [
        "No game", "Week 3 — not yet played", "Ohio State (1-1)  0"]
    assert out["scoreboard_home"].tolist() == ["", "", "Texas (2-0)  24"]
    assert "nan" not in " ".join(out["scoreboard_away"]).lower()


def test_the_poll_join_is_pinned_to_one_game_per_team_week():
    """🚨 fct_game_team IS **NOT** UNIQUE ON (season, season_type, week, team_id).

    2,093 duplicate groups exist — every postseason game carries week 1, and a team can play
    twice in a week (Abilene Christian played Lamar AND Texas Tech in 2026 week 1). Measured
    against the warehouse, the unguarded join multiplies **76** poll rows; guarded, **0**.
    """
    assert "row_number() over (" in MODEL and "and eg.rn = 1" in MODEL, (
        "the explaining-game join must pick exactly one row per team-week")
    assert "order by gt.game_date desc, gt.game_id desc" in MODEL, (
        "the pick must be deterministic — the last game of the week, ties broken on id")
    test_sql = (ROOT / "dbt" / "tests"
                / "assert_a_poll_row_is_not_multiplied_by_its_explaining_game.sql").read_text()
    assert "having count(*) > 1" in test_sql


def test_the_poll_week_is_offset_by_one_from_the_game_week():
    """🚨 POLL WEEK N REFLECTS GAME WEEK N-1, AND OFF BY ONE SHOWS THE WRONG GAME EVERY TIME.

    Established from the data (poll release dates are not in the warehouse, R-1848): on 2026
    AP, 3 of 3 ranked teams that lost in game week 2 fell in poll week 3, and after week 3
    four fell and one dropped out of poll week 4. The competing alignment was tested and
    refuted — under it those five would have fallen in poll week 3, and 5 of 5 held or rose.
    """
    assert "eg.week = r.week - 1" in MODEL, (
        "the explaining game is the week BEFORE the poll; r.week would attach a game the "
        "poll was published before")
    assert "rw_t.week = r.week - 1" in MODEL and "rw_o.week = r.week - 1" in MODEL, (
        "the records must come from the same week as the game they follow")


def test_the_page_does_not_join_to_get_any_of_this():
    """§4.2.1. Streamlit is single-table SELECT + WHERE; the join is in dbt."""
    body = SOURCE[SOURCE.index("def _rankings("):SOURCE.index("def _win_probability_curves(")]
    # ⚠️ NOT `[0]` — that is the DOCSTRING. The first triple-quoted block in this function is
    # prose, and picking it made this assertion read the docstring and fail on a correct file.
    blocks = [b for b in re.findall(r'"""(.*?)"""', body, re.S) if "select" in b.lower()]
    assert len(blocks) == 1, f"expected one query in _rankings, found {len(blocks)}"
    sql = blocks[0]
    assert "join" not in sql.lower(), "the rankings query must stay single-table"
    assert "from srv_rankings" in sql
    for column in ("explained_by_game_week", "game_away_display", "game_home_points"):
        assert column in sql, f"{column} must be selected, not derived in the page"
