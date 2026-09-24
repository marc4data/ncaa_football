r"""A215 — Poll Movement becomes Tracking Top 25 Changes, and moves.

> **MARC, v14:** *"Poll Movement - better title is something like Tracking Top 25 Changes. Move
> the text blurb to be above the graph. Move the graph between Against the Market and Week's
> Movers"*

📊 THE LOOKING BACK TAB'S SECTION ORDER, READ OFF THE EMITTED HEADINGS:

    before   Most Exciting · How the Week Went Against the Market · The Week's Movers ·
             Offense and Defense, per Game · Leaderboards · Poll Movement
    after    Most Exciting · How the Week Went Against the Market ·
             **Tracking Top 25 Changes** · The Week's Movers ·
             Offense and Defense, per Game · Leaderboards

⚠️ **"Against the Market" IS THE SECOND HALF OF `_recap`, NOT A PANEL OF ITS OWN** — `_recap`
emits "Most Exciting" and then "How the Week Went Against the Market". So *between* it and the
movers is between `_recap` and `_movers`, which is where `_bump` now sits.

🚨 **THE ORDER IS ASSERTED FROM WHAT THE PANELS EMIT, NOT FROM THE `TABS` TUPLE.** A tuple is a
list the test would be reading back to itself; the headings are what a reader sees. This is
A209's `test_the_slate_still_renders_what_a207_shipped` pattern — pin the sequence.

⚠️ AND THE STUB IS IMPORTED FROM `test_today_page` RATHER THAN COPIED. A second copy of a stub
is a copy that drifts, which is the failure this project has paid for repeatedly; the one
addition is `altair_chart`, which that file's stub never needed.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_today_page import _reload_all, _stub_streamlit                   # noqa: E402

TODAY_SRC = (ROOT / "site" / "views" / "today.py").read_text()

NEW_TITLE = "Tracking Top 25 Changes"
OLD_TITLE = "Poll Movement"


class _Scope:
    season, week, season_type, conference, division = 2026, 1, "regular", None, "fbs"

    def describe(self):
        return "2026 wk1"

    def link(self, page_name, **k):
        return "#"


def _frame() -> pd.DataFrame:
    """One row wide enough for every Looking Back panel — the same trick `test_today_page`
    uses, because the panels differ in which columns they reach for, not in where they
    get them."""
    return pd.DataFrame([{
        "game_id": 1, "season": 2026, "week": 1, "season_type": "regular",
        "poll_name": "AP Top 25", "team_display": "Home", "rank": 5,
        "opponent": "Away", "conference": "Big Ten",
        "total_yards": 400, "rushing_yards": 150, "passing_yards": 250,
        "games_counted": 9, "total_yards_for_per_game": 430.5,
        "total_yards_allowed_per_game": 312.25,
        "player_name": "Player One", "player_slug": "p1", "player_id": "1", "team": "Home",
        "stat_category": "rushing", "stat_type": "YDS", "stat_value": 120,
        "home_abbreviation": "HOME", "away_abbreviation": "AWAY",
        "line_spread_largest_excursion": -6.0, "line_spread_move_from_open": -3.0,
        "line_total_largest_excursion": 4.0, "line_total_move_from_open": 1.5,
        "line_market_implied_win_probability_largest_excursion": 6.78,
        "line_market_implied_win_probability_move_from_open": 2.10,
        "line_snapshot_count": 94, "line_movement_spans_snapshot_gap": True,
        "line_movement_provider_key": "draftkings",
        "play_number": 1, "period": 1, "is_overtime": False,
        "home_win_probability": 0.62, "elapsed_from_kickoff_seconds": 120,
        "overtime_period": None, "overtime_axis_offset_periods": None,
        "win_probability_curve_reaches_final_score": True,
        # the bump chart's own columns — the team colours it strokes each line with, and the
        # two scoreboard strings A190 put on the hover
        "color_on_light": "#0C2340", "color_on_dark": "#AE9142",
        "team_slug": "home", "team_logo_url": None, "team_rank": 5,
        "scoreboard": "W 21-14", "scoreboard_opponent": "at Away",
        "points_for": 21, "points_against": 14, "is_completed": True,
        "record_before_display": "1-0",
        # Most Exciting's ordering keys and the market lists' columns
        "scoreboard_lead_changes_fourth_quarter": 3,
        "mean_distance_from_even_fourth_quarter_onward": 4.2,
        "favorite": "Home", "underdog": "Away", "spread": -3.5, "fav_margin": 7,
        "ats": 3.5, "fav_win_prob": 0.62, "beat": 0.5, "score": "21-14",
        "matchup": "Away at Home", "total": 45.5, "total_points": 35,
        "home_team_display": "Home", "away_team_display": "Away",
        "home_points": 21, "away_points": 14,
        "start_date": pd.Timestamp("2026-09-05T19:00:00Z"),
        "game_date": pd.Timestamp("2026-09-05").date(),
        "venue": "Stadium", "home_logo_url": None, "away_logo_url": None,
        "home_slug": "home", "away_slug": "away",
        "home_rank": 5, "away_rank": None, "is_fbs_game": True,
        "as_of_ts": pd.Timestamp("2026-09-06T10:00:00Z"),
        "n": 1,
        "team_id": 0,
        "percentile_population": 0,
        "total_yards_allowed_percentile": 0,
        "total_yards_for_percentile": 0,
        "logo_url": 0,
        "ap_rank": 0,
        "favorite_definitions_disagree": 0,
        "market_implied_away_win_probability": 0.5,
        "spread_current": 0,
        "spread_at_close": 0,
        "actual_margin": 0,
        "spread_favorite_side": 0,
    }])


@pytest.fixture
def stubbed():
    """The page bound to a recording stub, and Streamlit put back by hand afterwards.

    ⚠️ THE RESTORE IS BY HAND BECAUSE monkeypatch's `sys.modules` undo runs AFTER fixture
    teardown — a module reloaded against the stub would stay bound to it for the rest of the
    session, which is R-665 and cost six unrelated tests once already.
    """
    site_path = str(ROOT / "site")
    added = site_path not in sys.path
    if added:
        sys.path.insert(0, site_path)
    saved = sys.modules.get("streamlit")
    stub, calls = _stub_streamlit()
    # the one thing test_today_page's stub never needed: the chart call, which PART 2 is about
    stub.altair_chart = lambda *a, **k: calls.append(("altair_chart", None))

    # 🚨 AND COLUMNS THAT ARE USABLE, because `_profile` unpacks what `st.columns` returns and
    # the borrowed stub returns `None` — `TypeError: cannot unpack non-iterable NoneType` at
    # `today.py:3149`. ⚠️ `test_today_page`'s own loop never noticed: it asserts only that a
    # panel rendered SOMETHING, and an error card is something. **This file asserts the ORDER
    # of the headings, so a panel that draws a card instead of a heading would silently shorten
    # the sequence** — which is why `_assert_no_error_card` exists and why this is here.
    class _Slot:
        """A column that records into the same list the module-level stub writes to."""

        def __getattr__(self, name):
            return getattr(stub, name)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _columns(spec, **k):
        calls.append(("columns", None))
        n = spec if isinstance(spec, int) else len(spec)
        return [_Slot() for _ in range(n)]

    stub.columns = _columns
    stub.container = lambda *a, **k: _Slot()
    stub.expander = lambda *a, **k: _Slot()
    stub.empty = lambda *a, **k: _Slot()
    # `lib/params.py` reads the URL through this; the borrowed stub has no runtime behind it
    stub.query_params = {}
    sys.modules["streamlit"] = stub
    try:
        _reload_all()
        page = sys.modules["views.today"]
        assert page.st is stub, "views.today is not talking to the stub — the reload failed"
        page.query = lambda *a, **k: _frame()
        yield page, calls
    finally:
        if saved is not None:
            sys.modules["streamlit"] = saved
        else:                                                   # pragma: no cover
            sys.modules.pop("streamlit", None)
        _reload_all()
        if added:
            sys.path.remove(site_path)


def _headings(calls) -> list:
    return [arg for name, arg in calls if name == "subheader"]


def _assert_no_error_card(calls, what: str) -> None:
    """🚨 `states.section` CATCHES EVERYTHING AND DRAWS A CARD, so a panel that raised looks
    exactly like a panel that rendered — and an order assertion over a swallowed exception
    asserts nothing at all.

    📊 THIS CAUGHT ITSELF ON THE FIRST RUN: the fixture frame was missing `color_on_light`,
    `_bump` raised a KeyError at `today.py:3852`, and the emitted kinds were
    `['subheader', 'markdown', 'radio', 'markdown']` — a clean-looking list with no chart in
    it. **Without this the tests would have been red for the wrong reason, or green over a
    broken panel.** R-758's third mode, in the harness rather than in the code.
    """
    drawn = " ".join(str(arg) for _kind, arg in calls if arg is not None)
    # ⚠️ THE ERROR CARD ONLY, NOT EVERY STATE CARD. The first version keyed on
    # `cfdb-state-body`, which `states.empty` also emits — and a one-row fixture legitimately
    # draws "No player box scores for 2026 wk1" on the touchdown board. **An Empty state is
    # the panel working**; an Error state is the panel having raised. Keying on the class
    # conflated them and failed a correct render.
    assert "Something went wrong" not in drawn, (
        f"{what} rendered an ERROR state rather than its content — "
        f"re-run with CFDB_TRACE_STATES=1 to see what it raised")


# ── PART 1: the title ─────────────────────────────────────────────────────────────────

def test_the_section_is_titled_tracking_top_25_changes(stubbed):
    """> **MARC:** *"better title is something like Tracking Top 25 Changes."*

    ⚠️ HIS WORDS AS WRITTEN. *"something like"* is him leaving room, and the room is easier to
    use from a rendered page than from a proposal.
    """
    page, calls = stubbed
    page._bump(_Scope(), 10)
    _assert_no_error_card(calls, "_bump")
    assert NEW_TITLE in _headings(calls), (
        f"the section's heading never reached the stub; recorded: {_headings(calls)}")


def test_a215_title_obeys_the_title_case_rule(stubbed):
    """⚠️ A211 SET THE RULE AND THIS CONFIRMS IT RATHER THAN ASSUMING IT. `title_case`
    capitalises the first and last word always and leaves an already-mixed-case word alone —
    "Top 25" is neither a minor word nor an initialism, so nothing here is a special case."""
    page, _calls = stubbed
    assert page.fmt.title_case("Tracking Top 25 changes") == NEW_TITLE


def test_the_old_title_is_rendered_nowhere_on_the_tab(stubbed):
    """🚨 A RENAME THAT REACHES THE HEADING AND NOT ITS NEIGHBOURS IS HOW A SITE STARTS CALLING
    ONE THING TWO NAMES. This renders EVERY Looking Back panel and looks at every string that
    reached the stub, not just the heading.

    ⚠️ IT ASSERTS ON WHAT IS RENDERED, NEVER ON WHAT IS IN THE FILE (A217's R-2624). `today.py`
    still contains the words "Poll Movement" — inside Marc's own quoted request, which must
    stay verbatim (§2.2.1e) — so a source-text assertion would be red on correct code.
    """
    page, calls = stubbed
    for name in dict.fromkeys(n for _s, _l, panels in page.TABS for n in panels):
        getattr(page, name)(_Scope(), 10)
    rendered = " ".join(str(arg) for _kind, arg in calls if arg is not None)
    assert OLD_TITLE.lower() not in rendered.lower(), (
        f"{OLD_TITLE!r} is still drawn somewhere on the tab")


# ── PART 2: the blurb above the graph ─────────────────────────────────────────────────

def test_the_blurb_is_drawn_before_the_chart(stubbed):
    """> **MARC:** *"Move the text blurb to be above the graph."*

    🚨 PROVEN BY THE EMITTED ORDER. The caption and the chart are two calls on one stub, and
    which came first is the whole claim — a screenshot would show it and could not assert it.
    """
    page, calls = stubbed
    page._bump(_Scope(), 10)
    _assert_no_error_card(calls, "_bump")
    kinds = [kind for kind, _arg in calls]
    assert "altair_chart" in kinds, f"the chart never rendered; recorded: {kinds}"
    assert "caption" in kinds, f"the blurb never rendered; recorded: {kinds}"
    assert kinds.index("caption") < kinds.index("altair_chart"), (
        f"the blurb is still below the chart: {kinds}")


def test_the_blurb_is_still_a_caption(stubbed):
    """⚠️ ONLY ITS POSITION MOVED. Promoting it to body text because it moved up the page
    would be a second change wearing the first one's clothes — and `st.caption` is what makes
    it small and dim, which is what an explanation under a heading should be."""
    page, calls = stubbed
    page._bump(_Scope(), 10)
    _assert_no_error_card(calls, "_bump")
    blurb = [arg for kind, arg in calls
             if kind == "caption" and arg and "Rank 1 is at the top" in str(arg)]
    assert blurb, "the chart's explanatory text is no longer a caption"


# ── PART 3: the section order ─────────────────────────────────────────────────────────

EXPECTED_ORDER = [
    "Most Exciting",
    "How the Week Went Against the Market",
    NEW_TITLE,
    "The Week's Movers",
    "Offense and Defense, per Game",
    "Leaderboards",
]


def test_the_poll_chart_sits_between_the_market_and_the_movers(stubbed):
    """> **MARC:** *"Move the graph between Against the Market and Week's Movers."*

    🚨 THE WHOLE TAB, IN EMITTED ORDER — not the three that moved. An order is a fact about the
    page, and pinning only the moved sections would let the others drift underneath.
    """
    page, calls = stubbed
    for name in page.TABS[0][2]:
        getattr(page, name)(_Scope(), 10)
        _assert_no_error_card(calls, name)
    assert _headings(calls) == EXPECTED_ORDER, (
        f"the Looking Back order is not what Marc asked for.\n"
        f"  got      {_headings(calls)}\n  expected {EXPECTED_ORDER}")


def test_the_market_comes_before_the_chart_and_the_movers_after(stubbed):
    """⚠️ THE RELATION MARC NAMED, ASSERTED DIRECTLY. If a later round adds a section between
    them, the list above changes and this still says what the requirement was."""
    page, calls = stubbed
    for name in page.TABS[0][2]:
        getattr(page, name)(_Scope(), 10)
        _assert_no_error_card(calls, name)
    seen = _headings(calls)
    market = seen.index("How the Week Went Against the Market")
    chart = seen.index(NEW_TITLE)
    movers = seen.index("The Week's Movers")
    assert market < chart < movers, (
        f"the chart must sit between the market and the movers: {seen}")


def test_the_sections_parts_travel_together(stubbed):
    """⚠️ A SECTION IS A HEADING, A BLURB, A CHART AND ITS DATASET LINE. Moving the heading and
    leaving the chart behind is the failure this guards: every part is emitted by `_bump`, so
    all of it moves when `TABS` moves, and nothing of it is emitted by a neighbour."""
    page, calls = stubbed
    page._movers(_Scope(), 10)
    movers_only = [k for k, _a in calls]
    assert "altair_chart" not in movers_only, (
        "the poll chart is being drawn by _movers — the section's parts have been split")
    calls.clear()
    page._bump(_Scope(), 10)
    _assert_no_error_card(calls, "_bump")
    kinds = [k for k, _a in calls]
    for part in ("subheader", "caption", "altair_chart"):
        assert part in kinds, f"_bump no longer emits its {part} — the section has been split"


def test_the_panel_name_is_still_registered(stubbed):
    """🚨 THE REORDER MUST NOT DROP A PANEL. `TABS` is the only thing that calls these, so a
    name lost in a tuple edit is a section that silently stops rendering."""
    page, _calls = stubbed
    back = page.TABS[0][2]
    # 🚨 A216 ADDED `_kpi_row` AT THE FRONT — Marc's KPI strip, *above Most Exciting*. The
    # set moves when a panel is added and that is a round, not a failure; what this test
    # protects is that no EXISTING name silently disappears in a tuple edit, and A215's own
    # ordering assertions below still pin `_recap` before `_bump` before `_movers`.
    assert set(back) == {"_kpi_row", "_recap", "_bump", "_movers", "_profile",
                         "_leaderboards"}, back
    assert back[0] == "_kpi_row", \
        "the KPI row is the first thing on Looking Back, which is what 'above Most " \
        "Exciting' means — Most Exciting is the first half of _recap"
    assert len(back) == len(set(back)), f"a panel is named twice: {back}"
