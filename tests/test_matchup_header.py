"""The Matchup game header: nine columns, and the things that fold into them (R-518/R-520/R-527).

Marc: "We need to formalize the elements on the page, similar to how we did on
Schedule/stacked." This is the first element built under the preview spec's §0 layout law —
columns, not sections; away on the LEFT — and everything placed below it inherits that.

WHAT THIS FILE EXISTS TO CATCH, in the order the risks actually rank:

 1. 🚨 THE TWO SIDES TRADING PLACES. A header that renders the home team in the away column
    is the R-544 class: every fact on the page is true and the page is wrong. B081 proved
    the obvious assertion does not catch it — a sign check passed against inverted code, and
    "two different names appear somewhere" passes against a swap. So every side assertion
    here is POSITIONAL: cell 1 is the away team's cell, cell 7 is the home team's, and the
    test reads the cell rather than the page.

 2. ⚠️ AN ELEMENT THAT RESERVES SPACE FOR SOMETHING IT DOES NOT HAVE. B075 measured that
    weather forecasts exist only about a week out — 253 of 303 week-2 games, and ZERO for
    weeks 4 through 8 — so for most of a season the conditions element has nothing to say.
    It must collapse to NOTHING, and "nothing" is asserted as the absence of a placeholder,
    not merely the absence of a temperature.

 3. ⚠️ A POST-GAME ELEMENT ON A PRE-GAME PAGE. The winner glyph is absent before kickoff,
    not empty — B075's rule for the after tab, one element smaller.

THE CELLS ARE READ BY INDEX AND THAT IS THE POINT. `_game_header` writes exactly nine
markdown blocks, one per column, in the order the spec names them. Reading cell 3 and cell 6
is what makes "the glyph points at the winner's score" a testable claim rather than a hope.

⚠️ THE STUB RAISES ON ANY STREAMLIT METHOD IT DOES NOT PROVIDE — A087's `HarnessGap`
discipline, and R-480 is open precisely because nothing in the repo does this durably yet.
A085's scratch harness silently returned a recorder for every attribute, so a missing stub
method was indistinguishable from a page defect. `HarnessGap` derives from BaseException so
that `states.section`'s `except Exception` cannot swallow it.

THE FIXTURE IS A REAL ROW, read back from srv_game for game 401754591 (Clemson at
Louisville, week 12 2025) — a one-point win for the AWAY side over a ranked home side, which
is what makes the scores, the records and the rank slot all worth asserting positionally. Cases the real row does not
cover (a rank, overtime, a tie) are overrides on it rather than invented rows. If a rendered
figure disagrees with a fixture, the fixture is wrong.
"""
import html
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_harness  # noqa: E402

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()


@pytest.fixture
def header():
    """`_game_header` with streamlit captured and the weather query answered from a fixture.

    🚨 THE EIGHTH FILE (R-615), AND B092's CENSUS WAS WRONG ABOUT IT TWICE. It reported this
    file as a harness user; `render_harness` appeared only inside a DOCSTRING at the bottom —
    it was never imported. And B092 claimed "all eight of B's panel fixtures" call
    `assert_no_error_card`: this file had ZERO, so the game header has had no R-610 guard at
    all. The move adds it.

    ⚠️ THE RESTORE THIS DOCSTRING DESCRIBES BY HAND IS `streamlit_stubbed`'s JOB, and it does
    both halves — sys.modules AND the parent-package attribute (A101).
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
        matchup = importlib.reload(importlib.import_module("views.matchup"))
        seen = {}

        def run(row=None, forecast=None):
            """`forecast` is what srv_game_weather returns: None for no row at all."""
            captured.clear()
            seen.clear()
            seen["queries"] = []

            def fake_query(sql, params=None):
                seen["queries"].append((sql, params or {}))
                return pd.DataFrame([forecast] if forecast else [])

            matchup.query = fake_query
            matchup._game_header(pd.Series(_row(**(row or {}))))
            # 🚨 R-610. An Error state is not a passing state — and this file never had the
            # call, so the header could have died on its first line with 45 tests green.
            render_harness.assert_no_error_card(captured, "the game header")
            return list(captured), dict(seen)

        yield run


@pytest.fixture
def blurb():
    """`_series`, the head-to-head one-liner. On the shared harness since R-615."""
    import importlib
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
        matchup = importlib.reload(importlib.import_module("views.matchup"))

        def run(**overrides):
            captured.clear()
            matchup._series(pd.Series(_row(**overrides)))
            render_harness.assert_no_error_card(captured, "the series blurb")
            return " ".join(captured)

        yield run


def _row(**overrides):
    """One srv_game row, read back from game 401754591 — Clemson at Louisville, wk12 2025."""
    row = {
        "game_id": 401754591,
        "season": 2025, "week": 12, "season_type": "regular",
        "is_completed": True,
        "away_team": "Clemson", "home_team": "Louisville",
        "away_abbreviation": "CLEM", "home_abbreviation": "LOU",
        "away_logo_url": None, "home_logo_url": None,
        # Clemson won 20-19 at Louisville, who were ranked #19; Clemson were unranked.
        "away_points": 20, "home_points": 19,
        "away_rank": None, "home_rank": 19,
        "away_team_record_display": "4-5", "home_team_record_display": "7-2",
        "start_date": pd.Timestamp("2025-11-14 19:30:00", tz="UTC"),
        "venue_display": "L&N Federal Credit Union Stadium",
        "is_neutral_site": False, "is_indoors": False,
        "spread": -1.5, "over_under": 51.0, "spread_favorite_side": "home",
        "away_q1": 3, "away_q2": 7, "away_q3": 3, "away_q4": 7,
        "home_q1": 3, "home_q2": 6, "home_q3": 10, "home_q4": 0,
        "away_overtime_points": 0, "home_overtime_points": 0,
        "away_periods": 4, "home_periods": 4,
        "series_games": 9, "series_away_team_wins": 8, "series_home_team_wins": 1,
        "series_ties": 0, "series_first_season": 2014, "series_last_season": 2024,
    }
    row.update(overrides)
    return row


FORECAST = {"game_id": 401754591, "temperature_f": 48.0, "wind_speed_mph": 7.0,
            "wind_direction_compass": "NW", "weather_condition": "Clear"}

# The nine columns, by index, in the order spec §1 names them.
AWAY_LOGO, AWAY_TEAM, AWAY_SCORE, AWAY_GLYPH = 0, 1, 2, 3
DETAILS = 4
HOME_GLYPH, HOME_SCORE, HOME_TEAM, HOME_LOGO = 5, 6, 7, 8


def _plain(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


# --- the shape ---------------------------------------------------------------------------------

def test_the_header_is_exactly_nine_columns(header):
    """Spec §1. Nine, in order, every time — a header that drew eight would still look fine."""
    cells, _ = header()
    assert len(cells) == 9, f"the header drew {len(cells)} cells, not nine"


def test_the_harness_raises_rather_than_no_opping_an_unknown_streamlit_call():
    """⚠️ THE INSTRUMENT IS TESTED BEFORE THE THING IT MEASURES.

    A085's harness returned a recorder for any attribute, so a missing stub method was
    indistinguishable from a page defect and §6 was satisfied by a broken instrument.

    ✅ R-615 POINTED THIS AT THE SHARED HARNESS RATHER THAN DELETING IT. It used to build this
    file's own stub and assert against this file's own `HarnessGap`; both are gone, and
    `tests/test_render_harness.py` already owns the two assertions in full —
    `test_an_unknown_streamlit_method_raises_LOUDLY` and
    `test_except_Exception_CANNOT_swallow_a_harness_gap`.

    🚨 SO WHY KEEP IT: the claim this file needs is that the stub IT uses is loud, and after
    the move that is the shared one. Deleting the test would have dropped the only line in
    this file saying so, and R-639's rule is that a test which stops being collected is an
    instrument that stopped measuring. This is two lines and it is the join.
    """
    stub, _captured, _charts = render_harness.build()
    with pytest.raises(render_harness.HarnessGap) as caught:
        stub.balloons()
    assert "st.balloons()" in str(caught.value)
    assert not issubclass(render_harness.HarnessGap, Exception), \
        "HarnessGap derives from Exception, so `states.section` would swallow it"


# --- 🚨 the two sides, positionally -------------------------------------------------------------

def test_the_away_team_is_in_the_AWAY_column_and_the_home_team_in_the_HOME_one(header):
    """🚨 THE R-544 CLASS, AND B081 PROVED THE OBVIOUS TEST DOES NOT CATCH IT.

    Both team names appear in the header whichever way round they are drawn, so "Clemson is
    on the page" passes against a swap. This reads the CELL: index 1 is the away column and
    index 7 is the home column, per spec §1's ordering.
    """
    cells, _ = header()
    assert "Clemson" in cells[AWAY_TEAM], "the away column is not carrying the away team"
    assert "Louisville" not in cells[AWAY_TEAM], "the home team is in the away column"
    assert "Louisville" in cells[HOME_TEAM], "the home column is not carrying the home team"
    assert "Clemson" not in cells[HOME_TEAM], "the away team is in the home column"


def test_each_score_sits_beside_its_own_team(header):
    """The scores are 20 and 19 — one apart, both plausible either way round.

    ⚠️ A swap here is invisible to any assertion that reads the whole header, which is why
    the away score is read out of cell 2 and the home score out of cell 6.
    """
    cells, _ = header()
    assert "20" in cells[AWAY_SCORE] and "19" not in cells[AWAY_SCORE]
    assert "19" in cells[HOME_SCORE] and "20" not in cells[HOME_SCORE]


def test_the_records_follow_their_own_teams(header):
    """4-5 and 7-2 are as swappable as the scores, and mean the opposite thing if traded."""
    cells, _ = header()
    assert "4-5" in cells[AWAY_TEAM] and "7-2" not in cells[AWAY_TEAM]
    assert "7-2" in cells[HOME_TEAM] and "4-5" not in cells[HOME_TEAM]


# --- the winner glyph --------------------------------------------------------------------------

def test_the_glyph_points_at_the_winner_and_only_the_winner(header):
    """Clemson won 20-19 on the road, so the AWAY glyph draws and the home one does not.

    ⚠️ The arrow points OUTWARD toward the score it belongs to: the away glyph sits to the
    right of the away score and points left; the home glyph sits to the left of the home
    score and points right. A glyph pointing the wrong way credits the wrong team.
    """
    cells, _ = header()
    assert "◀" in cells[AWAY_GLYPH], "the winner drew no glyph, or the wrong one"
    assert cells[HOME_GLYPH] == "", "the losing side drew a winner glyph"


def test_the_glyph_follows_the_result_when_the_HOME_team_wins(header):
    """The other direction, because a marker exercised one way is half tested."""
    cells, _ = header(row={"away_points": 3, "home_points": 30})
    assert "▶" in cells[HOME_GLYPH], "the home winner drew no glyph"
    assert cells[AWAY_GLYPH] == "", "the losing away side drew a glyph"


def test_a_TIE_gives_neither_side_a_glyph(header):
    """Asking who WON rather than who did not lose is what makes a tie draw nothing."""
    cells, _ = header(row={"away_points": 17, "home_points": 17})
    assert cells[AWAY_GLYPH] == "" and cells[HOME_GLYPH] == ""


def test_an_unplayed_game_has_NO_glyph_on_either_side(header):
    """⚠️ ABSENT, NOT EMPTY. B075's rule for the after tab, one element smaller: a post-game
    marker on a pre-game page does not render a placeholder pointing at nothing.

    🚨 THE SECOND CASE IS THE ONE THAT ASSERTS THE RULE, AND THE FIRST DRAFT OF THIS TEST
    HAD ONLY THE FIRST. With both scores null the null-guard returns early, so deleting the
    `is_completed` check entirely left this test GREEN — measured, by staging exactly that
    break. A row that is not final but already carries a lead is what isolates the check,
    and it is a real state: srv_game holds 1,609 games that are not completed, six of them
    carrying points.
    """
    for row in ({"is_completed": False, "away_points": None, "home_points": None},
                {"is_completed": False, "away_points": 21, "home_points": 7}):
        cells, _ = header(row=row)
        assert cells[AWAY_GLYPH] == "", f"a winner glyph was drawn for {row}"
        assert cells[HOME_GLYPH] == "", f"a winner glyph was drawn for {row}"


def test_an_unplayed_game_shows_no_score_rather_than_zero(header):
    """Two zeroes is a real result — a scoreless tie — and drawing one for a game that has
    not kicked off asserts something false."""
    cells, _ = header(row={"is_completed": False, "away_points": None, "home_points": None})
    assert cells[AWAY_SCORE] == "" and cells[HOME_SCORE] == ""


# --- the rank slot -----------------------------------------------------------------------------

def test_the_rank_shows_on_the_ranked_side_only(header):
    """291 of 3,831 games in 2025 carry a rank on either side, so one-sided is the common
    case rather than the edge one."""
    cells, _ = header()
    assert "#19" in cells[HOME_TEAM], "the ranked side lost its rank"
    assert "#" not in cells[AWAY_TEAM], "an unranked team was given a rank slot"


def test_an_unranked_game_carries_no_rank_markup_at_all(header):
    cells, _ = header(row={"away_rank": None, "home_rank": None})
    assert "#" not in cells[AWAY_TEAM] and "#" not in cells[HOME_TEAM]


# --- the columns that do not exist yet (R-577) ---------------------------------------------------

def test_the_header_omits_the_mascot_and_split_record_CLEANLY_while_they_are_absent(header):
    """🚨 NEITHER COLUMN IS ON srv_game TODAY — measured against information_schema.

    The header must not render an empty span, a stray comma or a dangling separator where
    they will go. This is the state every reader sees today, so it is the state most worth
    asserting.
    """
    cells, _ = header()
    assert _plain(cells[AWAY_TEAM]) == "Clemson 4-5"
    assert _plain(cells[HOME_TEAM]) == "#19 Louisville 7-2"


def test_the_header_RENDERS_them_the_day_they_arrive(header):
    """⚠️ THE OTHER HALF OF THE SAME PROMISE, and the reason the column names live in one
    dict. R-577 is session A's round; this proves the page is already waiting for it rather
    than needing a second round of its own.

    ⚠️ If A ships different column names, THIS TEST FAILS and names the contract — which is
    the point. It is the cheapest possible handshake between two sessions' rounds.
    """
    cells, _ = header(row={"away_mascot": "Tigers", "home_mascot": "Cardinals",
                           "away_team_away_record_display": "2-3",
                           "home_team_home_record_display": "5-1"})
    assert _plain(cells[AWAY_TEAM]) == "Clemson Tigers 4-5, 2-3 away"
    assert _plain(cells[HOME_TEAM]) == "#19 Louisville Cardinals 7-2, 5-1 home"


# --- ⚠️ the weather, and the absence that must cost nothing --------------------------------------

def test_a_game_with_no_forecast_reserves_NO_SPACE_for_one(header):
    """🚨 THE ASSERTION PART 2 EXISTS FOR. B075: forecasts appear about a week out — 253 of
    303 week-2 games, and ZERO for weeks 4 through 8 — so on most previews this element has
    nothing to say and a reserved slot would be dead space on every one of them.

    ⚠️ ASSERTED AS THE ABSENCE OF A PLACEHOLDER, not merely of a temperature. An empty
    `<div></div>` passes "no degrees sign appears" while still occupying a line.
    """
    cells, _ = header(row={"is_completed": False}, forecast=None)
    details = cells[DETAILS]
    assert "Forecast" not in details and "°F" not in details
    assert "<div></div>" not in details, "the header drew an empty slot for the forecast"
    assert "·  ·" not in _plain(details), "a separator was left with nothing between"


def test_the_weather_renders_inline_with_an_icon_and_no_label(header):
    """R-595. Marc: "Forecast, don't need to include the word 'forecast'. Add the icon that
    matches to Condition."

    ⚠️ B082 ADDED THAT WORD ON PURPOSE — "a temperature with no tense reads as a
    measurement" — and Marc has overruled it. The tense still holds structurally: this line is
    drawn ONLY before kickoff, because a completed game's details column is the scoreboard.
    """
    cells, _ = header(row={"is_completed": False}, forecast=FORECAST)
    details = _plain(cells[DETAILS])
    assert "Forecast" not in details, "the label Marc asked to remove is still there"
    assert "48°F" in details
    assert "☀️ Clear" in details, f"the condition icon is missing: {details}"


def test_wind_BELOW_the_floor_is_not_shown(header):
    """⚠️ Marc: "Only show wind_mph field value if >10". The fixture's 7 mph is below
    it, and 1,873 of 7,108 readings clear the floor — silence is the common case by design."""
    cells, _ = header(row={"is_completed": False}, forecast=FORECAST)
    assert "mph" not in _plain(cells[DETAILS])


def test_wind_ABOVE_the_floor_is_shown_in_Marcs_form(header):
    """His format, and R-604 CHANGED IT — he wrote the first version and then saw it.

    B085 built `[<wind_mph> mph <wind icon>]` from his words. Looking at it he said: "the wind
    glyph should just be wind blowing sideways. The tornado glyph means something different to
    Midwest folks. Don't put brackets around the wind. Don't include decimal point for wind."

    \U0001f4a8 DASH SYMBOL is drawn as a curled gust on several platforms; \U0001f32c WIND FACE
    is literally wind blowing sideways and belongs to no weather-warning vocabulary. 🚨 That
    half is a CORRECTNESS point, not a preference — a tornado on a football preview in the
    Midwest is a confident false statement.
    """
    gusty = dict(FORECAST, wind_speed_mph=18.0)
    details = _plain(header(row={"is_completed": False}, forecast=gusty)[0][DETAILS])
    assert "18 mph NW \U0001f32c" in details, \
        f"the wind chip is not in Marc's form: {details}"
    assert "[" not in details and "]" not in details, \
        f"the wind kept its brackets: {details}"
    assert "\U0001f4a8" not in details, "the gust/tornado glyph is still being drawn"


def test_wind_carries_NO_decimal_even_when_the_reading_has_one(header):
    """"Don't include decimal point for wind." 10.9 and 11 are the same afternoon, and the
    reading is a decimal in the column — 1,923 of them clear the floor."""
    gusty = dict(FORECAST, wind_speed_mph=10.9)
    details = _plain(header(row={"is_completed": False}, forecast=gusty)[0][DETAILS])
    assert "11 mph" in details, f"the wind was not rounded to whole mph: {details}"
    assert "10.9" not in details, f"the wind kept its decimal: {details}"


def test_the_floor_is_exclusive_so_exactly_ten_stays_quiet(header):
    """"if >10" is strict, and a boundary is where a threshold gets fudged."""
    ten = dict(FORECAST, wind_speed_mph=10.0)
    assert "mph" not in _plain(header(row={"is_completed": False}, forecast=ten)[0][DETAILS])
    over = dict(FORECAST, wind_speed_mph=10.5)
    assert "mph" in _plain(header(row={"is_completed": False}, forecast=over)[0][DETAILS])


def test_an_UNMAPPED_condition_falls_back_to_the_WORD_not_a_near_enough_icon(header):
    """🚨 A WRONG ICON IS A CONFIDENT FALSE STATEMENT about the weather at a game, and
    CFBD owns this vocabulary — it can add a value tomorrow this map has never seen. The word
    is merely less pretty; a sun on a hailstorm is wrong."""
    odd = dict(FORECAST, weather_condition="Volcanic Ash")
    details = _plain(header(row={"is_completed": False}, forecast=odd)[0][DETAILS])
    assert "Volcanic Ash" in details
    for icon in ("☀️", "☁️", "🌧️"):
        assert icon not in details, "an unmapped condition was given a guessed icon"


def test_every_condition_in_the_data_has_an_icon():
    """The map was written FROM the data, so it should cover it.

    ⚠️ A statement about today's 17 values, not a promise about tomorrow's — which is
    why the fallback above exists and is tested separately.
    """
    from views import matchup
    for condition in ("Clear", "Fair", "Cloudy", "Overcast", "Fog", "Light Rain",
                      "Rain Shower", "Rain", "Heavy Rain", "Heavy Rain Shower",
                      "Thunderstorm", "Snowfall", "Light Snowfall", "Heavy Snowfall",
                      "Sleet", "Heavy Sleet", "Heavy Sleet Shower"):
        assert condition.lower() in matchup._CONDITION_ICON, \
            f"{condition!r} appears in srv_game_weather and has no icon"


def test_the_stadium_sits_ABOVE_the_weather(header):
    """R-595, Marc's order. Positional: both strings are present either way round."""
    details = _plain(header(row={"is_completed": False}, forecast=FORECAST)[0][DETAILS])
    assert details.index("L&N Federal Credit Union Stadium") < details.index("48°F"), \
        f"the weather was drawn above the stadium: {details}"


def test_INDOORS_is_stated_even_with_no_forecast_at_all(header):
    """⚠️ `is_indoors` IS NOT "NO WEATHER" (AC-G.11). A dome has a known answer, and it is a
    different statement from "we have no forecast".

    It is a column on srv_game, already on the row the page fetched, so the roof costs no
    query and is stated even when srv_game_weather holds nothing.
    """
    cells, _ = header(row={"is_completed": False, "is_indoors": True}, forecast=None)
    assert "Indoors" in _plain(cells[DETAILS])


def test_an_indoor_game_labels_its_readings_as_OUTSIDE(header):
    """CFBD reports the weather at the venue's LOCATION, not inside it, so a domed game
    carries ordinary outdoor numbers. Printing them bare would state something false."""
    cells, _ = header(row={"is_completed": False, "is_indoors": True}, forecast=FORECAST)
    details = _plain(cells[DETAILS])
    assert "Indoors" in details and "outside" in details


def test_the_weather_game_id_is_cast_before_it_reaches_the_database():
    """⚠️ RELOCATED FROM test_matchup_postgame.py IN R-527, ASSERTION UNCHANGED, because the
    element moved into the header and the lesson did not.

    Taking the srv_game row instead of a game_id means the value arrives as a numpy.int64
    out of the DataFrame rather than as the int params.get() casts, and psycopg2 cannot adapt
    one — "can't adapt type 'numpy.int64'". Every load raised into states.section and
    rendered the Error state, on EVERY game, while looking like a handled failure. The unit
    tests stub `query` and ci/check_page_queries binds its own parameters, so it was found
    only by rendering the real body() against live serving.
    """
    block = SOURCE[SOURCE.index("def _conditions("):SOURCE.index("def _line_score(")]
    assert 'int(row.get("game_id"))' in block, \
        "an un-cast numpy.int64 reaches psycopg2 and the header errors on every game"


# --- the query budget --------------------------------------------------------------------------

def test_the_header_asks_for_the_forecast_ONCE_before_kickoff(header):
    """The weather query MOVED into the header; it was not added to the page. The standalone
    panel left the before tab in the same commit, so the page's count is unchanged."""
    _, seen = header(row={"is_completed": False}, forecast=FORECAST)
    assert len(seen["queries"]) == 1
    assert "srv_game_weather" in seen["queries"][0][0]


def test_a_COMPLETED_game_costs_the_header_no_query_at_all(header):
    """⚠️ THE HALF THAT KEEPS THE MOVE HONEST. The removed panel only ever ran on the before
    tab, so if the header fetched weather after kickoff too, the after tab would have gained
    a query that nothing on it had before."""
    _, seen = header(row={"is_completed": True})
    assert seen["queries"] == [], "the header queried srv_game_weather on a completed game"


def test_the_forecast_query_reads_one_relation_and_computes_nothing(header):
    """G-1/G-2/G-3, asserted on the SQL the header actually issued."""
    _, seen = header(row={"is_completed": False}, forecast=FORECAST)
    sql = seen["queries"][0][0].lower()
    assert sql.count(" from ") == 1
    for banned in ("join", "group by", "sum(", "avg(", "rank(", "over ("):
        assert banned not in sql, f"the header's query contains `{banned}`"


# --- the post-game scoreboard ------------------------------------------------------------------

def test_the_scoreboard_carries_the_quarters_and_the_final(header):
    """Spec §1: the details column becomes the scoreboard after the game."""
    details = _plain(header()[0][DETAILS])
    assert "Final" in details
    # Clemson 3 7 3 7 = 20; Louisville 3 6 10 0 = 19. Read as whole rows, because a
    # scoreboard that transposed two quarters would still contain every digit.
    assert "CLEM 3 7 3 7 20" in details, f"the away line score is wrong: {details}"
    assert "LOU 3 6 10 0 19" in details, f"the home line score is wrong: {details}"


def test_the_scoreboard_has_no_OT_column_when_there_was_no_overtime(header):
    """109 of 2025's completed games went to overtime. The other 3,722 must not carry an
    empty OT column."""
    assert "OT" not in _plain(header()[0][DETAILS])


def test_the_scoreboard_gains_an_OT_column_when_there_WAS_overtime(header):
    cells, _ = header(row={"away_overtime_points": 7, "home_overtime_points": 3,
                           "away_periods": 5, "home_periods": 5})
    assert "OT" in _plain(cells[DETAILS])


def test_a_completed_game_with_no_line_score_draws_no_table_of_dashes(header):
    """3,805 of 3,831 carry a first quarter, so the absence is rare rather than impossible."""
    cells, _ = header(row={f"{s}_q{q}": None for s in ("away", "home") for q in (1, 2, 3, 4)})
    details = _plain(cells[DETAILS])
    assert "Final" in details, "the scoreboard vanished along with its line score"
    assert "—" not in details


# --- the pre-game details ----------------------------------------------------------------------

def test_the_preview_details_carry_time_line_total_and_venue(header):
    cells, _ = header(row={"is_completed": False}, forecast=None)
    details = _plain(cells[DETAILS])
    assert "LOU -1.5" in details, "the spread is not stated from the home perspective"
    assert "O/U 51.0" in details
    assert "L&N Federal Credit Union Stadium" in details


def test_a_neutral_site_says_so(header):
    cells, _ = header(row={"is_completed": False, "is_neutral_site": True}, forecast=None)
    assert "neutral site" in _plain(cells[DETAILS])


def test_a_game_with_no_line_still_draws_its_time_and_venue(header):
    """Most of 110,634 games were never priced. The details column is not a market panel."""
    cells, _ = header(row={"is_completed": False, "spread": None, "over_under": None},
                      forecast=None)
    details = _plain(cells[DETAILS])
    assert "L&N Federal Credit Union Stadium" in details
    assert "O/U" not in details


# --- R-520: head to head as a blurb ------------------------------------------------------------

def test_the_series_blurb_puts_each_count_with_its_OWN_team(blurb):
    """🚨 THE SAME INVERSION RISK AS THE HEADER, in a sentence rather than a layout.

    8 and 1 are both plausible for either side. srv_game.sql's own comment warns that
    deriving the away side by subtraction credits every tie to the away team — so the model
    carries `series_away_team_wins` and this reads it. Asserted by ADJACENCY: the number
    must follow its own team's name.
    """
    text = _plain(blurb())
    assert re.search(r"Clemson 8\b", text), "the away team's series count is not beside it"
    assert re.search(r"Louisville 1\b", text), "the home team's series count is not beside it"


def test_the_blurb_is_one_line_and_not_a_section(blurb):
    """Marc asked for a text blurb close to the top, not a full section."""
    text = _plain(blurb())
    assert "Head to head" in text
    assert "9 meetings" in text
    assert "2014 to 2024" in text


def test_teams_that_have_NEVER_MET_are_not_reported_as_nil_nil(blurb):
    """⚠️ A series of no games is not 0-0. Two teams who have never played and two teams who
    have split evenly are different statements."""
    text = _plain(blurb(series_games=0))
    assert "never met" in text
    assert "0" not in text, "a first meeting was rendered as a scoreline"


def test_ties_are_counted_rather_than_folded_into_a_win_column(blurb):
    """College football had no overtime before 1996, so ties are real and countable."""
    text = _plain(blurb(series_games=10, series_ties=1))
    assert "1 tie" in text


def test_a_single_meeting_reads_as_one_meeting(blurb):
    text = _plain(blurb(series_games=1, series_away_team_wins=1, series_home_team_wins=0))
    assert "1 meeting" in text and "1 meetings" not in text


# --- 🚨 R-591: the columns the header reads must actually be SELECTED ---------------------------

# Every srv_game column `_game_header` and its helpers read off the row. A name here that is
# missing from `matchup.COLUMNS` is a `row.get()` that returns None on every real page load.
#
# ⚠️ SCOPED TO THE HEADER ON PURPOSE, exactly as B083 scoped the card's version. `row.get()` is
# also used on team-week rows, drive rows and leader rows in this module, so a blanket "every
# row.get name is in COLUMNS" check would report false positives on four other panels. The
# site-wide version is R-623 and it is session A's.
_HEADER_COLUMNS = (
    "game_id", "is_completed", "start_date",
    "home_team", "away_team", "home_abbreviation", "away_abbreviation",
    "home_logo_url", "away_logo_url", "home_points", "away_points",
    "home_rank", "away_rank",
    "home_team_record_display", "away_team_record_display",
    "home_mascot", "away_mascot",
    "home_team_home_record_display", "away_team_away_record_display",
    "venue_display", "is_neutral_site", "is_indoors",
    "spread", "over_under",
    "home_q1", "home_q2", "home_q3", "home_q4",
    "away_q1", "away_q2", "away_q3", "away_q4",
    "home_overtime_points", "away_overtime_points",
    "series_games", "series_away_team_wins", "series_home_team_wins", "series_ties",
    "series_first_season", "series_last_season",
)


def _selected():
    """The names `COLUMNS` actually produces.

    ⚠️ THIS WAS THE SECOND COPY OF A PARSE THAT COULD BE BLINDED BY A COMMENT (R-669). It read
    `COLUMNS.replace("\n", " ").split(",")`, byte-identical to the market card's, and the two
    would have had to be fixed twice. `tests/select_list.py` is the one implementation, the way
    `tests/render_harness.py` is for the Streamlit stub — and for the same reason: this project
    has re-implemented shared test machinery five times and paid for it each time.
    """
    from views import matchup
    import select_list
    return select_list.selected_names(matchup.COLUMNS)


def test_every_column_the_header_reads_is_actually_SELECTED():
    """🚨 THE SECOND INSTANCE OF A CLASS THAT HAS NOW BITTEN TWICE.

    B083 found the first: the market card read `favorite_definitions_disagree`, the SELECT
    never asked for it, and the disagreement caption was dead code on all 70 games it exists
    for. ⚠️ EVERY UNIT TEST PASSED, because `_row(**overrides)` supplies every key and so the
    fixture is MORE COMPLETE than the query. `ci/check_page_queries.py` cannot see this class
    at all — it executes the page's SQL, and a column the SQL never asks for is not in it.

    The header was the second instance and a quieter one: A092 shipped the mascot and the
    split record with exactly the names B082 predicted, the header has rendered them since
    B082, and they were invisible because nothing selected them.
    """
    missing = [c for c in _HEADER_COLUMNS if c not in _selected()]
    assert not missing, (
        f"the header reads these columns and the page does not select them, so they are None "
        f"on every load: {missing}")


def test_the_mascot_and_split_record_names_still_match_what_the_HEADER_asks_for():
    """⚠️ THE HANDSHAKE, ASSERTED FROM BOTH ENDS.

    `_MASCOT_COLUMN` and `_SPLIT_RECORD_COLUMN` are what the header reads; `COLUMNS` is what
    the page fetches. B082 could only assert the first half, because the columns did not
    exist. Now both halves are real and a rename on either side has to break something.
    """
    from views import matchup
    selected = _selected()
    for mapping in (matchup._MASCOT_COLUMN, matchup._SPLIT_RECORD_COLUMN):
        for side, column in mapping.items():
            assert column in selected, \
                f"the header reads {column!r} for the {side} side and COLUMNS omits it"


def test_wind_DIRECTION_is_shown_above_the_floor(header):
    """R-604's last quarter. Marc: "Do include Direction if it's >10 mph."

    ⚠️ COWORK SAID TWICE THAT THIS WAS BLOCKED ON A MODEL ROUND AND IT NEVER WAS.
    `wind_direction_compass` is on `srv_game_weather`, 7,358 of 7,358 rows carry it, and the
    header's query has selected it since B085 — the page simply never rendered it.
    """
    gusty = dict(FORECAST, wind_speed_mph=18.0, wind_direction_compass="SSW")
    details = _plain(header(row={"is_completed": False}, forecast=gusty)[0][DETAILS])
    assert "18 mph SSW" in details, f"the wind direction is missing: {details}"


def test_wind_direction_is_SILENT_below_the_floor_like_the_speed(header):
    """🚨 THE SAME FLOOR, AND THAT IS THE POINT RATHER THAN A CONVENIENCE. A direction with no
    wind behind it is noise on 5,435 of 7,358 readings — the floor exists because Marc asked
    for one, and a direction leaking out below it would reintroduce the clutter he removed."""
    calm = dict(FORECAST, wind_speed_mph=4.0, wind_direction_compass="NNE")
    details = _plain(header(row={"is_completed": False}, forecast=calm)[0][DETAILS])
    assert "NNE" not in details, f"the direction rendered below the floor: {details}"
    assert "mph" not in details, f"the speed rendered below the floor: {details}"
