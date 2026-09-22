"""A198 — the SLATE: one row per game, time across the x-axis, where to watch on each row.

⚠️ THE GATE ITSELF IS TESTED IN `test_today_looking_forward.py`. A198 adds no second gate —
the SLATE is drawn inside A196's branch, from A196's frame — so what is asserted here is the
drawing: which day a game lands on, what happens when the kickoff or the network is unknown,
and that the instant is converted exactly once.
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from lib import fmt                                       # noqa: E402
from views import today                                   # noqa: E402


class _SlateScope:
    """A201: `_slate` takes the scope now, because Marc's Matchup column needs `scope.link`."""
    season, season_type, week, conference, division = 2026, "regular", 4, None, "fbs"

    def link(self, page, **kw):
        bits = "&".join(f"{k}={v}" for k, v in kw.items())
        return f"/{page}?{bits}" if bits else f"/{page}"


SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
THEME = (ROOT / "site" / "lib" / "theme.py").read_text()


def _game(**over):
    """One high-value game. `start_date` carries its offset, as `srv_game` publishes it."""
    row = {
        "game_id": 1,
        "start_date": pd.Timestamp("2026-09-26T16:00:00Z"),   # 9:00 AM Pacific
        "game_date": pd.Timestamp("2026-09-26").date(),
        "kickoff_time_known": True,
        "away_team_display": "Texas", "home_team_display": "Tennessee",
        "network_abbreviation": "ABC", "network": "ABC Sports",
        "spread_current": 5.5,
        "is_top25_matchup": True, "is_undefeated_entering": False,
    }
    row.update(over)
    return row


def _frame(*rows):
    return pd.DataFrame(list(rows) or [_game()])


def test_the_instant_is_converted_once_and_lands_on_pacific_time():
    """🚨 R-643: THE LAST TIME SOMETHING CONVERTED THIS TWICE, EVERY KICKOFF ON THE SITE WAS
    FOUR HOURS EARLY FOR A SEASON.

    `srv_game.start_date` is an instant carrying its own offset. `fmt._local` is the one
    conversion and it RAISES on a naive value rather than guessing. ⚠️ **A double conversion
    does not look wrong — it looks like an earlier kickoff**, which on a run sheet is the
    worst possible failure and the easiest to miss.
    """
    timed, untimed = today._slate_rows(_frame())
    assert not untimed
    (day, entries), = timed.items()
    local, _row = entries[0]

    assert local.hour == 9 and local.minute == 0, (
        f"16:00Z is 9:00 AM Pacific; got {local:%H:%M} — a second conversion would move it")
    assert str(local.tzinfo) == fmt.display_timezone()
    assert day == "Saturday, Sep 26"


def test_two_kickoffs_on_different_local_days_are_grouped_separately():
    """⚠️ THE DAY IS THE **LOCAL** DAY. A Saturday-evening Pacific kickoff is already Sunday in
    UTC, so grouping on the raw instant would file it under the wrong heading — and the
    heading is the one thing a run sheet has to get right."""
    late = _game(game_id=2, start_date=pd.Timestamp("2026-09-27T03:00:00Z"),
                 away_team_display="Utah", home_team_display="Arizona")
    timed, _untimed = today._slate_rows(_frame(_game(), late))
    assert sorted(timed) == ["Saturday, Sep 26"], (
        f"03:00Z Sunday is 8:00 PM Pacific SATURDAY; got {sorted(timed)}")
    assert len(timed["Saturday, Sep 26"]) == 2


def test_a_game_with_no_known_kickoff_gets_no_bar_at_all():
    """🚨 A BAR AT A PLACEHOLDER TIME IS A FABRICATED SLOT ON A RUN SHEET.

    📊 THE STATE IS REAL BUT HAS NO 2026 INSTANCE — `kickoff_time_known` is false on 702 rows
    in 2000 and on **0 of 71 week-4 games**, 0 across all of 2026. So it is exercised here by
    a fixture rather than by the live page, and A198's report says so rather than implying the
    branch was seen working in production.
    """
    unknown = _game(game_id=3, kickoff_time_known=False,
                    away_team_display="Duke", home_team_display="Syracuse")
    timed, untimed = today._slate_rows(_frame(_game(), unknown))
    assert sum(len(v) for v in timed.values()) == 1
    assert sum(len(v) for v in untimed.values()) == 1

    html = today._slate(_frame(unknown), esc=lambda s: str(s), scope=_SlateScope())
    assert "cfdb-slate-bar" not in html, "an unannounced kickoff must not be drawn as a bar"
    assert "time TBA" in html and "Duke at Syracuse" in html


@pytest.mark.parametrize("abbr,full,expected", [
    ("ABC", "ABC Sports", "ABC"),
    (None, "ABC Sports", "ABC Sports"),
    (None, None, "TBA"),
    (float("nan"), float("nan"), "TBA"),
])
def test_the_network_falls_back_to_tba_and_never_to_blank(abbr, full, expected):
    """> **MARC:** *"No network yet → 'TBA', never blank."*

    ⚠️ AND `pd.isna`, NOT TRUTHINESS — `NaN` is truthy (A191), so a missing network would
    render the string `nan` on a run sheet rather than falling through to TBA.
    """
    html = today._slate(_frame(_game(network_abbreviation=abbr, network=full)),
                        scope=_SlateScope(),
                        esc=lambda s: str(s))
    # ⚠️ A201 MOVED THE NETWORK OFF THE BAR AND INTO THE TV COLUMN. Marc asked for a TV
    # column, and printing it in both places is the duplication the prompt forbade.
    networks = re.findall(r"cfdb-slate-tv'>([^<]*)<", html)
    assert networks == [expected], networks
    assert "nan" not in html.lower()


def test_the_bar_length_is_the_stated_allowance_and_the_caption_says_so():
    """⚠️ CFBD PUBLISHES NO END TIME. A bar that looked measured and was not would be worse
    than no bar, so the length is one constant and the caption names it as an allowance."""
    assert today._SLATE_GAME_MINUTES == 210
    assert "not a measured end time" in SOURCE
    assert "CFBD does not" in SOURCE and "publish" in SOURCE


def test_the_bar_spans_kickoff_to_kickoff_plus_the_allowance():
    """The geometry, asserted rather than eyeballed.

    ⚠️ A204 MADE THE BAR AN HTML BOX POSITIONED IN PERCENT, so the assertion is the same fact
    in a third set of coordinates (A198 drew px in one SVG per day, A201 units in one SVG per
    row). A 9:00 start on a 9a axis begins at 0%, and the bar is the allowance wide on that
    day's own scale — 210 minutes of a 4-hour axis is 87.5%.
    """
    html = today._slate(_frame(_game()), esc=lambda s: str(s), scope=_SlateScope())
    bar = re.search(r"cfdb-slate-bar[^']*' style='left:([\d.]+)%;width:([\d.]+)%", html)
    assert bar, html[:400]
    left, width = float(bar.group(1)), float(bar.group(2))
    assert left == pytest.approx(0.0), "the first kickoff of the day starts at the left edge"
    assert width == pytest.approx(100 * 210 / (4 * 60), rel=0.01), width


def test_the_bar_carries_the_outline_marc_asked_for():
    """> **MARC, v13:** *"Give the bars a thin medium graph outline to make them pop a bit."*

    ⚠️ A201 NEEDED `vector-effect='non-scaling-stroke'` because its bar was an SVG rect
    stretched horizontally. A204's bar is an HTML box, so a 1px border is 1px on all four
    sides by construction — the workaround went with the thing that needed it.
    """
    rule = THEME[THEME.index(".cfdb-slate .cfdb-slate-bar {"):]
    rule = rule[:rule.index("}")]
    assert "border:1px solid" in rule
    assert "box-sizing:border-box" in rule, (
        "without it the border would widen the bar and shift its right edge off the scale")


def test_the_kickoff_is_labelled_inside_the_bar_and_flush_left():
    """> **MARC, v13 addition 2:** *"label each bar with the start time (should be inside the
    > bar and aligned to the far left)"*

    ⚠️ AND IT CLIPS RATHER THAN OVERFLOWING: a bar too narrow to hold the label loses it
    instead of spilling into the column before it.
    """
    html = today._slate(_frame(_game()), esc=lambda s: str(s), scope=_SlateScope())
    assert "cfdb-slate-clock" in html
    # the label sits INSIDE the bar element, not beside it
    bar = html[html.index("cfdb-slate-bar"):]
    assert bar.index("cfdb-slate-clock") < bar.index("</div>")
    rule = THEME[THEME.index(".cfdb-slate .cfdb-slate-bar {"):]
    assert "overflow:hidden" in rule[:rule.index("}")]


def test_the_hour_lines_run_behind_the_whole_day_rather_than_inside_each_row():
    """> **MARC, v13 addition 2:** *"can the vertical bars/ticks for the time go the full
    > vertical distance of the chart instead of breaking with each row? it's weird look.
    > Distracting. Only need vertical lines on the hour."*

    🚨 PER-ROW LINES CANNOT BE CONTINUOUS. Every row contributes its own cell padding and
    border, so a line drawn inside the row restarts at each one — which is the break Marc saw.
    The layer is absolutely positioned behind the day's table and inset by the fixed columns.
    """
    html = today._slate(_frame(_game()), esc=lambda s: str(s), scope=_SlateScope())
    assert "cfdb-slate-grid" in html
    # the layer is a sibling of the table, not a child of any row
    assert html.index("cfdb-slate-grid") < html.index("<table")
    assert f"left:{sum(today._SLATE_COL_PX)}px" in html
    # hours only — one line per hour of the span, and no half-hours
    # ⚠️ THE LAST TICK IS ANCHORED BY ITS RIGHT EDGE (a 1px box at left:100% overflowed the
    # layer by exactly one pixel), so counting only `left:` would miss it and report four.
    lines = html.count("<i style=")
    assert lines == 5, f"9a..1p inclusive is five hourly lines, got {lines}"
    assert "<i style='right:0'></i>" in html, "the last tick is anchored right"


def test_the_slate_is_drawn_inside_the_gate_and_from_the_same_frame():
    """🚨 ONE GATE, NOT TWO. > **MARC:** the SLATE goes below the Schedule layout.

    ⚠️ A second gate could disagree with the first — the splash showing above a drawn slate,
    or a slate built from a different week than the table. It is drawn in the same branch,
    from the same `games` frame, after the table.
    """
    body = SOURCE[SOURCE.index("def _looking_forward("):]
    body = body[:body.index("\n\ndef ")]
    # ⚠️ A205 MADE THE SLATE THE SECTION, so it is `render_or_state`'s renderer now and is
    # handed the frame as `rows` rather than reading `games` directly. The property this test
    # is about is unchanged: ONE frame, drawn once, inside the gate.
    assert body.count("_slate(rows") == 1, "the slate draws the frame it is given"
    assert body.count("_high_value_games(") == 1, "and that frame comes from one query"
    # it must sit AFTER the table render and INSIDE the branch that draws it
    assert body.index("states.render_or_state") < body.index("_slate(rows")
    for early_return in ("return\n", ):
        assert body.index("_slate(rows") > body.rindex(early_return), (
            "the slate must be below every gate return, or it can draw under the splash")


def test_an_empty_frame_draws_no_axis():
    """AC-G.11: the section's existing stated empty stands; an empty axis would be decoration
    implying a slate exists."""
    assert today._slate(pd.DataFrame(), esc=str, scope=_SlateScope()) == ""
    assert today._slate(None, esc=str, scope=_SlateScope()) == ""
