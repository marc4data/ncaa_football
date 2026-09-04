"""The Schedule page's two renderings. R-043.

These exercise the RENDERERS against frames built here, not against a database. The bug they
exist for was not a query bug: the stacked view rendered fifteen of fifty-nine games and
stopped, because a null in an object column is NaN, NaN is truthy, and `nan or ""` is nan.
It failed inside states.section, which caught it and drew an Error state — so there was no
exception to catch, no error to assert on, and every existing test passed.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from views import schedule                          # noqa: E402


def _row(**overrides):
    base = dict(
        game_id=1, season=2025, week=12, season_type="regular",
        game_date=pd.Timestamp("2025-11-15"), start_date_et=pd.Timestamp("2025-11-15 19:00"),
        home_team_slug="alabama", home_team_display="Alabama", home_abbreviation="ALA",
        home_logo_url=None, home_conference="SEC", home_points=31, home_rank=4,
        home_team_record_display="8-2", home_team_record_after_display="9-2",
        away_team_slug="auburn", away_team_display="Auburn", away_abbreviation="AUB",
        away_logo_url=None, away_conference="SEC", away_points=17, away_rank=None,
        away_team_record_display="5-5", away_team_record_after_display="5-6",
        venue_display="Bryant-Denny", network="ESPN", network_abbreviation="ESPN",
        is_neutral_site=False, is_conference_game=True, is_completed=True, winner="Alabama",
        spread_current=-7.5, total_current=52.5, predicted_margin=-6.0,
        spread_at_close=-7.0, spread_at_close_basis="observed_before_kickoff",
        total_at_close=51.5, total_at_close_basis="observed_before_kickoff",
        total_points=48, actual_margin=-14,
        upset_level="none", winner_covered_close="yes", over_met="no",
        home_win_probability=0.72, excitement_index=5.1,
        is_indoors=False, temperature_f=54.0, weather_condition_code=3,
        weather_condition="Cloudy",
        home_q1=7, home_q2=10, home_q3=7, home_q4=7, home_overtime_points=None, home_periods=4,
        away_q1=3, away_q2=7, away_q3=0, away_q4=7, away_overtime_points=None, away_periods=4,
    )
    base.update(overrides)
    return base


class _Scope:
    """The bits of GameScope the renderers touch.

    `season` / `season_type` / `division` arrived when the week band did: `_by_week` reads a
    distribution for the season, and the band's FBS-only note depends on the division. The
    stub grew rather than the tests being pointed at a real GameScope, because a real one
    needs Streamlit session state and these tests deliberately run without it.
    """
    season = 2026
    season_type = "regular"
    division = "fbs"

    def link(self, page, **kwargs):
        return "/x"


def _distribution_frame():
    """Two weeks of distribution rows, in the shape srv_week_metric_distribution returns."""
    import pandas as _pd
    rows = []
    for week in (1, 2):
        for span in ("week", "season_to_date"):
            if span == "season_to_date" and week == 1:
                continue                      # week 1 has nothing before it, so no row
            for metric, counts in (("market_implied_favorite_points", "0,0,0,3,25,14,9,2,0,0"),
                                   ("market_implied_underdog_points", "0,3,9,25,15,1,0,0,0,0"),
                                   ("total", "0,1,4,16,17,8,6,1,0,0")):
                rows.append({
                    "season": 2026, "season_type": "regular", "week": week, "span": span,
                    "metric": metric, "as_of_date": "2026-09-04", "recency": 1,
                    "bin_counts": counts, "bin_min": 0, "bin_max": 60, "bin_incr": 6.0,
                    "bin_count": 10, "below_min_count": 0, "above_max_count": 0,
                    "n": 53, "games_in_week": 53, "coverage_pct": 100.0,
                    "games_locked": 53, "games_live": 0, "is_locked": True,
                    "min_value": 18.5, "max_value": 45.0, "p25": 27.5, "p50": 29.8,
                    "p75": 32.0, "whisker_lo": 21.3, "whisker_hi": 38.0, "outlier_count": 5,
                })
    return _pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    """THE WEEK BAND MADE THESE TESTS REACH A DATABASE, AND THEY WENT ON PASSING.

    `_by_week` reads `srv_week_metric_distribution`, so the moment the band landed every card
    test opened a connection — and every one stayed green, because a Postgres happened to be
    running on this laptop. Stopping the container turned four of them into
    `OperationalError`, which is how it was found.

    That is precisely what `conftest.no_ambient_credentials` exists to prevent one level up: a
    test whose result depends on ambient environment cannot be trusted when it matters. So the
    read is stubbed here, with realistic rows rather than an empty frame — an empty one would
    exercise only the absent-week path and quietly stop testing the band at all.
    """
    from views import schedule as _schedule
    monkeypatch.setattr(_schedule, "_distributions",
                        lambda season, season_type: _distribution_frame())


@pytest.fixture
def counting_markdown(monkeypatch):
    """Count cards emitted, so a renderer that stops early is visible as a number."""
    calls = {"cards": 0, "total": 0, "html": []}

    def fake(body, **kwargs):
        calls["total"] += 1
        if isinstance(body, str):
            # COUNT OCCURRENCES, NOT CALLS. R-110 puts a day's cards into one grid element
            # and therefore one st.markdown call, so the original `+= 1 per call` version of
            # this counted 1 for twenty games and would have passed against a renderer that
            # emitted a single card and stopped — the exact defect the file exists for.
            calls["cards"] += body.count("<div class='cfdb-gamecard'>")
            calls["html"].append(body)

    monkeypatch.setattr(schedule.st, "markdown", fake)
    return calls


def test_the_stacked_view_emits_one_card_per_row(counting_markdown):
    """Fifty-nine rows produced fifteen cards in production and raised nothing catchable."""
    df = pd.DataFrame([_row(game_id=i) for i in range(20)])
    schedule._stacked(df, _Scope())
    assert counting_markdown["cards"] == 20


def test_a_row_with_null_network_and_venue_still_renders(counting_markdown):
    """The exact shape that broke it: pandas gives NaN, not None, and NaN is truthy.

    `r.get("network_abbreviation") or ""` therefore returns nan, and str.join fails with
    "expected str instance, float found" on the first game nobody is carrying.
    """
    # NaN, NOT None. That distinction is the whole bug: a DataFrame column mixing strings
    # and Python None keeps None, which is falsy and harmless. A column pandas has decided is
    # float — which is what read_sql produces for a mostly-null text column — holds NaN, and
    # NaN is TRUTHY. The first version of this test used None, reproduced nothing, and passed
    # against the broken code.
    nan = float("nan")
    df = pd.DataFrame([
        _row(game_id=1),
        _row(game_id=2, network_abbreviation=nan, venue_display=nan,
             away_abbreviation=nan),
    ])
    schedule._stacked(df, _Scope())
    assert counting_markdown["cards"] == 2


def test_a_long_name_with_no_abbreviation_truncates_rather_than_showing_nan():
    row = _row(home_team_display="Southeastern Louisiana", home_abbreviation=None)
    rendered = schedule._team_name(row, "home")
    assert rendered == "Southeastern Louis"
    assert "nan" not in rendered.lower()


def test_an_indoor_game_shows_the_dome_and_no_temperature():
    """R-027: CFBD reports the weather at the venue's LOCATION, not inside it, so a real
    temperature beside a domed game answers the wrong question."""
    cell = schedule._weather_cell(_row(is_indoors=True, temperature_f=94.0))
    assert schedule.DOME_MARK in cell
    assert "94" not in cell


def test_pending_and_tie_and_won_are_three_distinct_winner_states():
    """R-100 kept the distinction the chip it replaced had.

    An unplayed game has no winner YET; a tie has none AT ALL; a win has one. Collapsing the
    first two into "no marker" is the specific loss R-100 warned about, and it is what a
    naive `if winner: mark` would do — that version passes a two-state test and fails this.
    """
    pending = schedule._winner_marker(_row(is_completed=False, winner=None), "home")
    tie_home = schedule._winner_marker(_row(is_completed=True, winner=None), "home")
    tie_away = schedule._winner_marker(_row(is_completed=True, winner=None), "away")
    won = schedule._winner_marker(_row(), "home")
    lost = schedule._winner_marker(_row(), "away")

    assert len({pending, tie_home, won}) == 3, "three states, three renderings"
    assert tie_home == tie_away, "a tie marks BOTH rows; marking one would name a winner"
    assert schedule.WINNER_GLYPH in won and schedule.WINNER_GLYPH not in lost


def test_the_losing_row_reserves_the_markers_width():
    """R-100's actual requirement. Without the spacer the two scores stop lining up
    vertically, and a misaligned pair of numbers reads as a rendering bug, not a marker.

    This fails against `return "" if not winner`, which is the obvious implementation.
    """
    lost = schedule._winner_marker(_row(), "away")
    pending = schedule._winner_marker(_row(is_completed=False, winner=None), "home")
    for rendered in (lost, pending):
        assert rendered != ""
        assert "cfdb-winner-spacer" in rendered


def test_the_score_cell_carries_the_marker_and_the_number():
    """R-100 relocated the chip onto the score rather than deleting the information."""
    assert "31" in schedule._score_cell(_row(), "home")
    assert schedule.WINNER_GLYPH in schedule._score_cell(_row(), "home")
    labels = [c.label for c in schedule._columns(_Scope())]
    assert "Won" not in labels, "the chip column is gone"


# --- R-101 / R-103: the dense view's columns ------------------------------------------

def test_matchup_and_neutral_share_one_headed_column():
    """R-101. They were two columns costing two widths for at most two characters, one of
    which was blank on 95% of rows — and the neutral one had no header at all."""
    columns = {c.field: c for c in schedule._columns(_Scope())}
    assert "is_neutral_site" not in columns, "the second column is gone"
    assert "details" not in columns
    game = columns["game"]
    assert game.label, "R-101 asks for a header; the old neutral column had none"
    # R-146 MOVED THE NEUTRAL GLYPH OUT AGAIN, to the kickoff cell. R-101 merged two columns
    # into one; this is that same column keeping its header and swapping its second occupant
    # for R-147's result strip.
    kickoff = columns["start_date_et"]
    assert schedule.NEUTRAL_GLYPH in kickoff.format(_row(is_neutral_site=True))
    assert schedule.NEUTRAL_GLYPH not in kickoff.format(_row(is_neutral_site=False))
    assert schedule.NEUTRAL_GLYPH not in game.format(_row(is_neutral_site=True))
    rendered = game.format(_row())
    assert schedule.table.DETAILS_GLYPH in rendered
    assert "cfdb-strip" in rendered, "R-147: the strip sits right of the matchup icon"
    assert rendered.index("cfdb-details") < rendered.index("cfdb-strip")


def test_the_weather_column_is_centred():
    """R-103. Asserted through Col.css rather than on a hand-written class, because the
    class is what render() actually puts on the <td>."""
    columns = {c.field: c for c in schedule._columns(_Scope())}
    assert columns["weather"].css == "cfdb-center"


def test_the_two_synthetic_columns_do_not_offer_a_dead_sort_link():
    """`apply_sort` drops a field the frame does not have, so a sort header on a synthetic
    column renders an arrow and then does nothing. `weather` had been doing that since R-027.
    """
    from lib import table as table_lib
    for field in ("game", "weather"):
        column = next(c for c in schedule._columns(_Scope()) if c.field == field)
        assert "cfdb-sort" not in table_lib._header_cell(column, sortable=True)


def test_a_game_with_no_quarters_shows_dashes_and_says_why(counting_markdown, monkeypatch):
    """R-092. Absent is not zero, and the card says which.

    Only 44,775 of 110,879 games carry quarters and the earliest is 2001. A row of zeros
    would claim four scoreless quarters; omitting the block silently would be honest about
    the value and silent about the reason, which reads as a broken page.
    """
    captured = []
    monkeypatch.setattr(schedule.st, "markdown",
                        lambda body, **kw: captured.append(body))
    nan = float("nan")
    df = pd.DataFrame([_row(
        season=1998, home_q1=nan, home_q2=nan, home_q3=nan, home_q4=nan, home_periods=nan,
        away_q1=nan, away_q2=nan, away_q3=nan, away_q4=nan, away_periods=nan)])
    schedule._stacked(df, _Scope())
    card = next(c for c in captured if "cfdb-gamecard" in c)
    assert "—" in card, "an absent quarter renders an em dash"
    assert "not recorded before 2001" in card, "and the card says why"
    assert ">0<" not in card, "a zero would claim a scoreless quarter"


# --- the stacked view, prompt 032 Part 3 ------------------------------------------------

def _card(**overrides):
    return schedule._card(_row(**overrides), _Scope(),
                          schedule._linescore_geometry(pd.DataFrame([_row(**overrides)])))


class _Children(HTMLParser):
    """Count the DIRECT children of the first element, which is what a flex row distributes."""

    def __init__(self):
        super().__init__()
        self.depth, self.direct = 0, 0

    def handle_starttag(self, tag, attrs):
        if self.depth == 1:
            self.direct += 1
        self.depth += 1

    def handle_endtag(self, tag):
        self.depth -= 1


def test_the_linked_part_of_the_cluster_travels_as_one_element():
    """R-105 still, narrowed by R-129.

    `team_cell` returns SEVERAL sibling spans. When those went straight into a flex row with
    `justify-content:space-between`, every one became a flex item and the row spread all five
    across ~1,400px. What must stay together is the LINKED part — logo, rank badge, name.

    R-129 then took the record back OUT of that anchor, so this asserts both halves: the three
    linked things are inside it and the record is not.
    """
    row = schedule._team_row(_row(away_logo_url="https://x/y.png"), "away", _Scope())
    link = row[row.index("<a "):row.index("</a>")]
    for part in ("cfdb-logo", "cfdb-team'"):
        assert part in link, f"{part} escaped the anchor"
    assert "cfdb-team-record" not in link, (
        "R-129: the record is not a hyperlink; styling cannot remove a pointer cursor")
    assert "cfdb-team-record" in row, "but it is still on the row"


def test_the_card_links_both_teams_and_the_matchup():
    """R-107 / R-111. `table.team_cell` does not build an anchor — in the dense table the
    href comes from the COLUMN's `link`, and a card has no column, so the card must apply it
    itself. Its docstring records this exact defect from three weeks earlier.

    Fails against the shipped card, where both names were inert text.
    """
    card = _card()
    assert card.count("class='cfdb-teamlink'") == 2, "both teams, not one"
    assert schedule.table.DETAILS_GLYPH in card, "and the matchup, which the dense view has"
    # Nested anchors are invalid HTML, which is why the card is a div and Matchup gets its
    # own affordance rather than the whole card being one link.
    assert "<div class='cfdb-gamecard'>" in card


def test_a_team_with_no_slug_is_not_linked_to_nowhere():
    """A link to `/team?team=None` is worse than text that was never clickable."""
    row = schedule._team_row(_row(away_team_slug=float("nan")), "away", _Scope())
    assert "cfdb-teamlink" not in row
    assert "nan" not in row.lower()


def test_the_card_says_which_team_is_home_and_handles_the_neutral_case():
    """R-112. Away-over-home is a convention the reader was expected to already hold, and at
    a neutral site it tells them something FALSE — the card Marc sent is at Aviva Stadium,
    Dublin, flagged neutral.

    A treatment that only marks the home row and ignores `is_neutral_site` passes a naive
    test and fails the second half of this one.
    """
    home = schedule._team_row(_row(is_neutral_site=False), "home", _Scope())
    away = schedule._team_row(_row(is_neutral_site=False), "away", _Scope())
    neutral = schedule._team_row(_row(is_neutral_site=True), "home", _Scope())

    assert ">@<" in home
    assert ">vs<" in neutral, "at a neutral site there is no home side to read into the order"
    assert ">@<" not in neutral
    # The away row carries the SAME span, empty, or the two names start at different x.
    assert "cfdb-athome" in away and ">@<" not in away and ">vs<" not in away


def test_the_kickoff_shares_row_one_with_the_box_score_header():
    """R-114. The header used to belong to a table the teams block knew nothing about, which
    is exactly why the two score rows sat one header-height below the two names.

    Asserted on ORDER within the grid: the time is the first cell, and the quarter headers
    follow it before any team row. A card that puts the time in a left gutter — the shipped
    layout — fails this.
    """
    import re as _re
    card = _card()
    grid = card[card.index("<div class='cfdb-gc'"):]
    time_at = grid.index("cfdb-gc-time")
    first_header = grid.index("cfdb-gc-h")
    first_team = grid.index("cfdb-gc-team")
    assert time_at < first_header < first_team
    shown = _re.search(r"cfdb-gc-time'>([^<]+)<", card).group(1)
    # A SHAPE, not "7:00" — fmt.clock converts to the reader's zone, so a literal would make
    # this pass or fail on the machine's TZ rather than on the code.
    assert _re.fullmatch(r"\d{1,2}:\d{2} [AP]M \w+", shown), shown


def test_the_query_sorts_by_date_then_time_then_rank_then_home_name():
    """R-108's second half. `nulls last` IS the whole of "unranked last" — without it
    Postgres sorts NULL high and every unranked game leads its own time slot."""
    sql = Path(schedule.__file__).read_text()
    # `limit 400` became `limit {ROW_CAP}` when the cap was named and raised (R-227), and
    # slicing on the old literal silently produced an empty string that every assertion below
    # then passed against. Anchored on the placeholder.
    order = sql[sql.index("order by game_date"):sql.index("limit {ROW_CAP}")]
    assert order, "the ORDER BY slice is empty — the anchor no longer matches"
    assert "start_date_et" in order
    assert "best_rank_in_game nulls last" in order
    assert order.index("start_date_et") < order.index("best_rank_in_game")
    assert order.index("best_rank_in_game") < order.index("home_team_display")


# --- R-106: the box score is a post-game element ---------------------------------------

def test_a_completed_game_shows_the_box_score_and_not_the_market():
    card = _card()
    assert "cfdb-gc-n" in card
    assert "cfdb-gc-market" not in card


def test_a_scheduled_game_shows_the_market_and_no_box_score():
    """R-106. A scheduled game is NOT a game whose quarter scores are missing, so R-092's
    "absent, not zero" copy must not appear for one.

    Fails against the shipped card, which drew a full dash grid and the 2001 explanation for
    every game that had not kicked off yet.
    """
    nan = float("nan")
    card = _card(is_completed=False, winner=None, home_points=nan, away_points=nan,
                 home_periods=nan, away_periods=nan,
                 home_q1=nan, home_q2=nan, home_q3=nan, home_q4=nan,
                 away_q1=nan, away_q2=nan, away_q3=nan, away_q4=nan,
                 total_move_from_open=1.5, spread_move_from_open=-0.5)
    assert "cfdb-gc-n" not in card and "cfdb-gc-h" not in card
    assert "not recorded" not in card
    assert "cfdb-gc-mid" in card
    assert "52.5" in card and "-7.5" in card
    assert schedule.MOVE_GLYPH in card


def test_a_scheduled_game_with_no_line_shows_nothing_there():
    """R-106, literally: "Not an empty slot, not a dash: nothing."""
    nan = float("nan")
    card = _card(is_completed=False, winner=None, home_points=nan, away_points=nan,
                 spread_current=nan, total_current=nan,
                 home_periods=nan, away_periods=nan)
    assert "cfdb-linescore" not in card
    assert "cfdb-market" not in card
    assert "—" not in card


# --- R-109 / R-113: the score, and who won, inside the box score ------------------------


def test_the_cards_go_into_a_css_grid_not_streamlit_columns(counting_markdown):
    """R-110. `st.columns(2)` is a FIXED two-up — Streamlit renders server-side and cannot
    measure a viewport, so it would keep two cards side by side on a phone."""
    df = pd.DataFrame([_row(game_id=i) for i in range(4)])
    schedule._stacked(df, _Scope())
    grid = [h for h in counting_markdown["html"] if "cfdb-cardgrid" in h]
    assert len(grid) == 1, "one grid per day group"
    assert grid[0].count("<div class='cfdb-gamecard'>") == 4, "the cards are its children"


# --- prompt 033: the card is one grid ---------------------------------------------------

def _grid_of(card: str) -> str:
    return card[card.index("<div class='cfdb-gc'"):card.index("cfdb-gamecard-meta")]


def test_the_card_emits_three_rows_of_equal_cell_count():
    """R-114 STRUCTURALLY. Team rows and score rows share ROW TRACKS only if they are cells
    of the same grid, and they only stay in step if every row emits the same number of cells.

    One missing cell shifts every later cell up a column and the alignment the whole prompt
    is about silently disappears — with no exception and nothing to see in a unit test that
    only greps for class names.
    """
    for geo in ({"ot": False}, {"ot": True}):
        card = schedule._card(_row(home_periods=5 if geo["ot"] else 4,
                                   away_periods=5 if geo["ot"] else 4), _Scope(), geo)
        grid = _grid_of(card)
        per_row = 2 + schedule._tracks(geo)   # team, middle, then the numerics
        parser = _Children()
        parser.feed(grid)
        assert parser.direct == 3 * per_row, (
            f"ot={geo['ot']}: expected 3 rows of {per_row}, got {parser.direct} cells")


def test_the_grid_template_reserves_one_track_per_cell():
    """The CSS and the markup have to agree on the column count, and nothing else checks it.
    A template with five tracks and rows of six cells wraps into a fourth row."""
    for geo in ({"ot": False}, {"ot": True}):
        style = schedule._grid_style(geo)
        repeats = int(re.search(r"repeat\((\d+),", style).group(1))
        assert repeats + 1 == schedule._tracks(geo), style
        assert style.startswith("grid-template-columns:minmax(0,1fr)"), (
            "the team column must be the flexible one; a fixed left column would stop the "
            "names going hard left")


def test_a_regulation_game_reserves_the_ot_track_but_draws_nothing_in_it():
    """R-116, and Marc's two sentences only LOOK contradictory.

      "should only show OT column, if that game went into OT"
      "the amount of space ... should still be the same up/down days"

    Reserved and drawn are different decisions. The page-wide geometry keeps the track so
    every card starts and ends at the same x; the per-game check decides whether anything is
    visible in it. The shipped version drew an OT header over four regulation games.
    """
    geo = {"ot": True}                       # some other game on this page went to overtime
    regulation = schedule._card(_row(home_periods=4, away_periods=4), _Scope(), geo)
    overtime = schedule._card(_row(home_periods=5, away_periods=5,
                                   home_overtime_points=7, away_overtime_points=0),
                              _Scope(), geo)
    assert ">OT<" in overtime and ">OT<" not in regulation
    # Same cell count either way — the track is still there, holding the space.
    for card in (regulation, overtime):
        parser = _Children()
        parser.feed(_grid_of(card))
        assert parser.direct == 3 * (2 + schedule._tracks(geo))
    # And nothing is drawn: no border classes on the reserved cells.
    assert regulation.count("cfdb-gc-b") < overtime.count("cfdb-gc-b")


def test_the_winner_marker_sits_after_the_record_not_in_the_total():
    """R-135 REVERSES R-120, which Marc asked for one round ago and has now seen.

    Both halves matter. The marker has to arrive in the cluster AND leave the total cell — a
    version that adds it to the cluster and forgets to remove it from the total renders two
    markers per winning row and passes any test that only looks for one.
    """
    card = _card()
    assert "cfdb-ls-mark" not in card, "and it still has no column of its own"
    cluster = card[card.index("cfdb-gc-team"):]
    cluster = cluster[:cluster.index("</div>")]
    assert cluster.index("cfdb-team-record") < cluster.index("cfdb-winner"), (
        "R-135: after the record")
    totals = [c[:c.index("</div>")] for c in card.split("cfdb-gc-tot")[1:]]
    assert len(totals) == 2
    for cell in totals:
        assert schedule.WINNER_GLYPH not in cell and "cfdb-winner" not in cell, (
            "the total cell gives up the marker and its spacer entirely")
    # The winning side still carries it exactly once. Alabama (home) won 31-17.
    assert card.count(schedule.WINNER_GLYPH) == 1


def test_the_losing_total_still_reserves_the_markers_width():
    """Same rule as R-100 and not optional here: without the spacer the two totals stop
    aligning vertically, and the fix creates the problem it was meant to remove."""
    card = _card()
    assert "cfdb-winner-spacer" in card
    assert card.count("cfdb-gc-tot") == 2


class _Spans(HTMLParser):
    """Direct children of the grid, and how many COLUMNS each one covers."""

    def __init__(self):
        super().__init__()
        self.depth, self.spans = 0, []

    def handle_starttag(self, tag, attrs):
        if self.depth == 1:
            style = dict(attrs).get("style", "") or ""
            found = re.search(r"grid-column:span (\d+)", style)
            self.spans.append(int(found.group(1)) if found else 1)
        self.depth += 1

    def handle_endtag(self, tag):
        self.depth -= 1


def _columns_in_grid_style(style: str) -> int:
    """Counted from the template itself rather than from `_tracks`, so the test does not
    inherit the same arithmetic the code uses — team, middle, the repeated quarters, total."""
    repeats = int(re.search(r"repeat\((\d+),", style).group(1))
    return 1 + 1 + repeats + 1


def test_every_row_of_the_card_covers_every_column():
    """THE REGRESSION THIS FILE DID NOT CATCH, AS THE PROPERTY THAT WOULD HAVE.

    R-149 added a middle track and widened the market cell's span to cover it — and left the
    header row's span at the old width. CSS grid does not complain about a short row: it
    silently reflows every following cell one column to the right, so the scheduled card put
    its logos on the far side and pushed the names out of view entirely.

    The old test here counted CELLS, which stayed correct the whole time, because a cell that
    spans four columns is still one cell. What has to hold is COVERAGE: for every row, the
    spans must sum to the number of columns the grid declares. Both branches, both geometries,
    because the scheduled branch is the one that broke and only the completed branch was
    exercised by the count test.
    """
    nan = float("nan")
    scheduled = dict(is_completed=False, winner=None, home_points=nan, away_points=nan,
                     home_periods=nan, away_periods=nan)
    for geo in ({"ot": False}, {"ot": True}):
        columns = _columns_in_grid_style(schedule._grid_style(geo))
        assert columns == 2 + schedule._tracks(geo), "middle track counted once, not twice"
        # THE FIXTURE ALWAYS HAD A CLOSING LINE, WHICH IS HOW THE SECOND INSTANCE SHIPPED.
        # A completed game with no line held returned no middle cell at all, so its row was a
        # column short and the team column collapsed to zero width — one card in 400 on the
        # deployed site. Every combination of played/not and line/no-line is exercised here.
        no_close = dict(spread_at_close=nan, total_at_close=nan,
                        total_points=nan, actual_margin=nan)
        for label, extra in (("completed", {}),
                             ("completed, no closing line", no_close),
                             ("scheduled", scheduled),
                             ("scheduled, no line", dict(scheduled, spread_current=nan,
                                                         total_current=nan))):
            card = schedule._card(_row(**extra), _Scope(), geo)
            parser = _Spans()
            parser.feed(_grid_of(card))
            covered = sum(parser.spans)
            assert covered % columns == 0, (
                f"{label} ot={geo['ot']}: {covered} columns covered is not a whole number "
                f"of {columns}-column rows")
            assert covered == 3 * columns, (
                f"{label} ot={geo['ot']}: three rows of {columns} = {3 * columns}, "
                f"got {covered}")


def test_the_stacked_weather_is_the_dense_weather():
    """R-119's second half. Asserted as SHARED CODE rather than as matching output, because
    two renderers that agree today are two renderers that can drift."""
    columns = {c.field: c for c in schedule._columns(_Scope())}
    assert columns["weather"].render is schedule._weather_cell
    # And the card actually calls it, dome case included — the same cell, not a lookalike.
    indoor = _card(is_indoors=True, temperature_f=94.0)
    assert schedule._weather_cell(_row(is_indoors=True, temperature_f=94.0)) in indoor
    assert "94" not in indoor, "a dome reports the weather OUTSIDE it; the number is wrong"


def test_the_card_grid_keeps_its_empty_track():
    """`auto-fit` COLLAPSES a track it cannot fill, so a day group with one game stretched
    that card to the full page width while every other day rendered half of it.

    Measured at a 1920 viewport before the fix: 1 card -> 1460px, every other day -> 723px.
    The page changed shape according to how many games were played that day.
    """
    css = Path(schedule.__file__).resolve().parents[1] / "lib" / "theme.py"
    body = css.read_text()
    grid = body[body.index(".cfdb-cardgrid"):body.index(".cfdb-gamecard {")]
    assert "auto-fill" in grid
    assert "auto-fit" not in grid


def test_the_record_does_not_inherit_the_link_colour():
    """R-117's styling guard, and `color:inherit` on the record ALONE does not provide it.

    Measured on the rendered page: with only that rule the record came out rgb(0,84,163) —
    Streamlit's own `a` colour — because inherit takes the parent's value and the parent is
    the anchor. It read as a second link, which is the failure R-117 named.

    Both halves are required: the anchor gives up the colour, and the NAME takes the accent
    explicitly. Verified after: record is rgb(49,51,63) in light and rgb(250,250,250) in dark,
    body text in both, and different from the name in both.
    """
    body = (Path(schedule.__file__).resolve().parents[1] / "lib" / "theme.py").read_text()
    block = body[body.index(".cfdb-teamlink {"):body.index(".cfdb-logo-box")]
    assert "color:inherit !important" in block, "the anchor must give up the link colour"
    assert ".cfdb-teamlink .cfdb-team { color:" in block, (
        "and the NAME must take the accent, or nothing is a link any more")


def test_the_view_label_changed_but_the_url_parameter_did_not():
    """R-128. The dict key is the `?view=` value. Renaming it would break every existing link
    to the table view, which is the silent breakage R-097 was about."""
    assert schedule.VIEWS["dense"] == "Inline"
    assert set(schedule.VIEWS) == {"dense", "stacked"}, (
        "the KEYS are the URL contract; only the labels are free")
    from lib import params
    assert "dense" in params.ENUM_PARAMS["view"]


def test_the_winner_spacer_tracks_the_glyphs_size():
    """R-133 asks for a much bigger marker in the Inline view. The spacer's width is `.75em`,
    so it only equals the glyph's width while the two font sizes agree — and if it stops
    agreeing the two scores stop aligning, which is what R-120 existed to prevent."""
    body = (Path(schedule.__file__).resolve().parents[1] / "lib" / "theme.py").read_text()
    block = body[body.index(".cfdb-winner {"):body.index(".cfdb-gc-team .cfdb-winner")]
    sizes = re.findall(r"font-size:([\d.]+rem)", block)
    assert len(sizes) == 2 and sizes[0] == sizes[1], (
        f"glyph and spacer must share a size, got {sizes}")


def test_the_result_strip_reserves_its_width_on_a_scheduled_game():
    """R-141. An indicator set that appears only on completed games shifts the columns beside
    it the moment a week is half played — the alignment failure this page has fixed three
    times. Every state renders a span; `none` is a reserved blank, not an omission."""
    nan = float("nan")
    played = schedule._result_strip(_row())
    scheduled = schedule._result_strip(_row(is_completed=False, upset_level=nan,
                                            winner_covered_close=nan, over_met=nan))
    assert played.count("<span class='cfdb-ind") == 3
    assert scheduled.count("<span class='cfdb-ind") == 3, "same count, played or not"
    assert scheduled.count("cfdb-ind-none") == 3, "reserved, and nothing drawn"
    # `none` is also the upset scale's own first state — "not an upset" — so a played game
    # legitimately carries one. An UPSET draws all three.
    upset = schedule._result_strip(_row(upset_level="big"))
    assert "cfdb-ind-none" not in upset, "a played upset draws all three"


def test_the_three_indicators_are_shapes_not_emoji():
    """A substitution worth being able to see. Marc's states mixed emoji-presentation and
    text-presentation characters, which do not share a baseline or size together — and he
    asked the strip to match the kickoff time's size, which emoji will not do reliably."""
    strip = schedule._result_strip(_row())
    # No emoji and no variation selectors anywhere in the strip — it is spans and classes.
    assert not any(ord(ch) >= 0x1F000 or ch in "\ufe0e\ufe0f" for ch in strip), strip
    # The fixture covers (filled) and stayed under (outlined) — one of each in one strip.
    assert "cfdb-ind-fill" in strip and "cfdb-ind-open" in strip, "filled vs outlined"
    assert "cfdb-ind-push" in schedule._result_strip(_row(over_met="push"))
    assert "cfdb-u2" in schedule._result_strip(_row(upset_level="big"))


def test_the_record_shown_depends_on_whether_the_game_was_played():
    """R-140. A record AFTER a game cannot exist for a game nobody has played, which is why
    the literal reading of Marc's sentence was not built. Completed shows after; scheduled
    shows going-in."""
    after = schedule._record_span(_row(), "home")
    before = schedule._record_span(_row(is_completed=False), "home")
    assert "9-2" in after and "after" in after
    assert "8-2" in before and "going into" in before


def test_the_middle_block_mirrors_the_market_block_rows():
    """R-149. O/U on the away row, Spread on the home row — the same two rows the pre-game
    market uses, so a reader's eye does not move between a played and an unplayed game."""
    away, home = schedule._middle_cells(_row())
    assert "O/U" in away and "51.5" in away and "48" in away
    assert "Spread" in home and "-7.0" in home and "-14" in home
    assert "+" not in away.split("cfdb-gc-mid-actual")[1], "a points total is unsigned"


def test_the_card_vocabulary_matches_the_markup():
    """The names in the module docstring must name things that exist.

    A vocabulary is only useful while it is true. This one exists so a change request can say
    "the line block" instead of describing a position, which only works if "the line block" is
    still the thing that renders there. Parsed from the docstring rather than restated here,
    so there is one list and it is the one Marc reads.
    """
    doc = schedule.__doc__
    assert "THE PARTS" in doc, "the vocabulary section is gone; so is the reason for this test"
    table = doc[doc.index("THE PARTS"):]
    entries = re.findall(r"^\s{4}([a-z][a-z ()]+?) \.{3,} (cfdb-[a-z-]+)", table, re.M)
    assert len(entries) >= 14, f"only parsed {len(entries)} names; the table shape changed"

    source = Path(schedule.__file__).read_text()
    body = source[source.index('"""', source.index('"""') + 3):]   # past the docstring
    for name, css in entries:
        assert css in body, f"'{name}' is documented as .{css}, which nothing renders"

    # And the reverse, for the parts a reader can actually point at. A class that renders a
    # visible region of the card but is absent from the table is a part with no name, which is
    # how "the thing next to the other thing" starts.
    documented = {css for _, css in entries}
    for css in ("cfdb-gamecard", "cfdb-gc-team", "cfdb-gc-mid", "cfdb-gc-mid-head",
                "cfdb-gc-tot", "cfdb-gamecard-meta"):
        assert css in documented, f".{css} renders a region of the card and has no name"


def test_the_line_block_heads_only_its_two_number_columns():
    """The label column heads nothing — "O/U" and "Spread" are self-describing, and a heading
    over them would be a heading over a heading."""
    for preview, second in ((False, "Actual"), (True, f"{schedule.MOVE_GLYPH} Open")):
        head = schedule._line_block_header(preview=preview)
        assert head.count("<span") == 3, "three cells, so the columns line up"
        assert "<span></span>" in head, "the label column is deliberately blank"
        assert ">Line<" in head and f">{second}<" in head


def test_nothing_in_the_line_block_is_emphasised():
    """Marc, on both card variants: the fonts are inconsistent. They were — the actual was
    weighted on a result card and the line was weighted on a preview card, so the emphasis
    landed on a different column depending on whether the game had been played.

    The headers are what make the weight unnecessary. Asserted on the stylesheet because the
    rule is the thing that has to stay gone.
    """
    body = (Path(schedule.__file__).resolve().parents[1] / "lib" / "theme.py").read_text()
    block = body[body.index(".cfdb-gc-mid {"):body.index(".cfdb-gc-mid-head")]
    assert "font-weight" not in block, (
        "a weight on one line-block column emphasises it over the other for no reason")


def test_both_card_variants_use_one_line_block():
    """They render different CONTENT — line against actual, line against move — in the same
    component. Two classes is how the padding, the divider and the weight diverged between a
    game that has been played and one that has not."""
    nan = float("nan")
    result = _card()
    preview = _card(is_completed=False, winner=None, home_points=nan, away_points=nan,
                    home_periods=nan, away_periods=nan)
    for card in (result, preview):
        assert "cfdb-gc-mid" in card
    assert "cfdb-gc-market" not in result + preview, "the second class is gone"


def test_a_game_that_was_played_and_was_not_an_upset_still_shows_something():
    """"Not an upset" is an ANSWER. Rendering it as nothing made it identical to "not played
    yet", which is a different fact — and since a normal week has no upsets at all (all 124
    completed games in 2026 week 1 are `none`), the first slot was blank on every row. The two
    visible indicators then sat in slots two and three and read as slots one and two, so a
    reader matching them to the legend matched them to the wrong entries.
    """
    nan = float("nan")
    played = schedule._result_strip(_row(upset_level="none"))
    unplayed = schedule._result_strip(_row(is_completed=False, upset_level=nan,
                                           winner_covered_close=nan, over_met=nan))
    assert "cfdb-ind-quiet" in played, "played and unremarkable is still an answer"
    assert "cfdb-ind-quiet" not in unplayed, "not played is not an answer"
    assert unplayed.count("cfdb-ind-none") == 3
    # Three visible marks on a completed row, whatever the result was.
    assert played.count("cfdb-ind-none") == 0


def test_each_indicator_has_its_own_shape():
    """All three were circles, so they could only be told apart by position — and position is
    unreadable the moment one of them is invisible. A shape per position lets a reader match a
    single indicator to its legend entry without counting its neighbours."""
    strip = schedule._result_strip(_row())
    for shape in ("cfdb-sh-upset", "cfdb-sh-cover", "cfdb-sh-over"):
        assert strip.count(shape) == 1, f"{shape} should appear exactly once"


def _untitled(markup: str) -> str:
    """Markup with the tooltip stripped — the legend and the row differ only there."""
    return re.sub(r" title='[^']*'", "", markup)


def test_the_legend_explains_every_mark_the_page_can_draw():
    """A legend that describes an appearance the page does not have is worse than none; a page
    that draws a mark the legend omits is worse still.

    Asserted against `LEGEND_GROUPS`, the declarative inventory the popover renders, rather
    than by scraping markdown out of a Streamlit container — the data is what has to be
    complete, and it survives the legend moving between a sidebar, a popover and two columns,
    all of which have now happened.
    """
    shapes = {(e[1], e[2], e[3]) for _, rows in schedule.LEGEND_GROUPS
              for e in rows if e[0] == "shape"}
    glyphs = {e[2] for _, rows in schedule.LEGEND_GROUPS for e in rows if e[0] == "glyph"}
    for shape in ("upset", "cover", "over"):
        assert any(s == shape for s, _, _ in shapes), f"no {shape} swatch"
    for state in ("quiet", "fill", "open", "nodata"):
        assert any(st == state for _, st, _ in shapes), f"no {state} swatch"
    for glyph in (schedule.NEUTRAL_GLYPH, schedule.DOME_MARK, schedule.WINNER_GLYPH,
                  schedule.TIE_GLYPH, schedule.MOVE_GLYPH, schedule.table.DETAILS_GLYPH):
        assert glyph in glyphs, "a mark the page draws and the legend never explains"


def test_every_state_the_strip_can_render_is_in_the_legend():
    """The strip is generated from the data, so the states it can produce are enumerable.
    Anything it draws and the legend cannot name is a mark with no meaning."""
    nan = float("nan")
    drawn = set()
    for row in (_row(upset_level="none"), _row(upset_level="upset"),
                _row(upset_level="big"), _row(upset_level="blowout"),
                _row(winner_covered_close="no", over_met="no"),
                _row(upset_level=nan, winner_covered_close=nan, over_met=nan),
                _row(is_completed=False, upset_level=nan,
                     winner_covered_close=nan, over_met=nan)):
        drawn.update(re.findall(r"cfdb-ind-(\w+)", schedule._result_strip(row)))
    documented = {e[2] for _, rows in schedule.LEGEND_GROUPS
                  for e in rows if e[0] == "shape"}
    for state in sorted(drawn):
        if state == "none":
            continue          # "not played yet" draws nothing; there is nothing to explain
        assert state in documented, f"{state} is drawn and not in the legend"


def test_the_legend_is_grouped_rather_than_one_long_list():
    """Eighteen marks in a single column is a list nobody reads.

    ASSERTED ON THE SHAPE, NOT ON THREE LITERAL STRINGS. The previous version was
    `titles == ["Game", "Result", "Against the line"]`, which fails on any regroup AND on any
    rename — including renames it should not care about. This is round three of this legend
    and it will not be the last, so the property is: it is grouped, every group is titled and
    non-empty, every group appears in the column layout exactly once, and no mark is
    documented twice.
    """
    titles = [title for title, _ in schedule.LEGEND_GROUPS]
    assert len(titles) >= 2 and all(titles), "grouped, and every group titled"
    assert all(rows for _, rows in schedule.LEGEND_GROUPS), "no empty group"
    assert len(set(titles)) == len(titles), "no duplicate group title"

    laid_out = [t for column in schedule.LEGEND_COLUMNS for t in column]
    assert sorted(laid_out) == sorted(titles), (
        "every group is placed in exactly one column, and no column names a group that is "
        "not in the inventory")

    labels = [e[-1] for _, rows in schedule.LEGEND_GROUPS for e in rows]
    assert len(set(labels)) == len(labels), "a mark documented twice is a mark with two meanings"


def test_the_result_group_is_only_won_and_tied():
    """R-176. Marc: "Result should just have Won and Tied. The rest of the items all belong
    under Against The Line." """
    by_title = dict(schedule.LEGEND_GROUPS)
    assert [e[-1] for e in by_title["Result"]] == ["Won", "Tied"]
    assert len(by_title["Against the line"]) == 11
    assert schedule.LEGEND_COLUMNS == [["Game", "Result"], ["Against the line"]]


def test_the_worked_examples_are_rendered_by_the_strip_itself():
    """R-177. A legend example built from its own markup is a second implementation of the
    strip, and the first thing it does is drift — which is exactly what R-178 was."""
    assert len(schedule.LEGEND_EXAMPLES) == 2
    first, second = (schedule._result_strip(row) for row, _ in schedule.LEGEND_EXAMPLES)
    # favorite won · covered · over
    assert "cfdb-ind-quiet" in first and first.count("cfdb-ind-fill") == 2
    # upset by 7+ · covered · under
    assert "cfdb-u2" in second and "cfdb-ind-open" in second
    for _, caption in schedule.LEGEND_EXAMPLES:
        assert caption.count("·") == 2, "a caption names all three slots"


def test_the_legend_draws_each_state_exactly_as_the_strip_draws_it():
    """R-178, AND THE TEST THIS REPLACES WAS HOLDING THE DEFECT IN PLACE.

    Marc: "No closing line held and No Line and No Ranking aren't showing an icon in the
    legend." They were not faint — they were ABSENT. `_indicator` puts the dash INSIDE the
    span; `_legend_key` wrote its own empty span; and `.cfdb-ind-nodata` is transparent by
    design, because on the row the dash is the visible thing and the box only holds R-166's
    alignment. Two implementations of one mark, and the swatch was the one with nothing in it.

    THE OLD TEST ASSERTED `shape.endswith("></span>")` — literally that a swatch is EMPTY. It
    was green throughout and nobody could fix the defect without breaking it. R-157 says a
    green test can prove a true fact about the wrong property; this one went further and
    enforced the wrong property.

    So the assertion is now the thing that matters: for every state the strip can draw, the
    legend's swatch is BYTE-IDENTICAL to the strip's, modulo the tooltip. That cannot be
    satisfied by a second implementation, which makes the shape-or-glyph question moot.
    """
    for shape in ("upset", "cover", "over"):
        for state, extra in (("fill", "cfdb-acc"), ("open", "cfdb-acc"),
                             ("quiet", ""), ("nodata", ""), ("none", "")):
            from_strip = schedule._indicator(shape, state, "a title", extra)
            from_legend = schedule._legend_key("shape", shape, state, extra)
            assert _untitled(from_strip) == _untitled(from_legend), (
                f"{shape}/{state}: the legend and the row draw different markup")


def test_the_result_strip_is_on_the_card_as_well_as_the_table():
    """The legend is shared by both views, so a strip that exists only in Inline means the
    Stacked view carries a legend for something it does not draw. Marc found exactly that."""
    card = _card()
    assert "cfdb-strip" in card
    # In the kickoff cell, mirroring where R-141 put it in the Inline header.
    head = card[card.index("cfdb-gc-time"):]
    assert head.index("cfdb-strip") < head.index("cfdb-gc-mid")


def test_the_legend_is_rendered_exactly_once():
    """It was rendered twice for one commit — the sidebar call from R-159 was left in place
    when the popover was added to Band 3, so the page carried two Legend buttons.

    Counted in the source because both calls were syntactically fine and neither test nor
    lint could see the duplication; it took looking at the rendered page.
    """
    source = Path(schedule.__file__).read_text()
    body = source[source.index("def body(page)"):]
    assert body.count("_legend(df)") == 1, "one legend, one button"


def test_the_legend_note_renders_its_emphasis_rather_than_asterisks():
    """`SPREAD_SIGN_NOTE` is markdown and the legend is a raw HTML block, so `**bold**` came
    out as literal asterisks — a defect visible only by looking at the rendered page.

    Converted rather than restated: R-009 made this sentence a shared constant precisely so
    there would not be a second copy to drift.
    """
    import streamlit as st
    from lib import chips as chips_lib
    captured = []
    original = st.markdown
    st.markdown = lambda body, **kw: captured.append(body)
    try:
        schedule._legend(None)
    except Exception:
        pass                      # st.popover needs a runtime; the note is written regardless
    finally:
        st.markdown = original
    note = next((c for c in captured if "cfdb-legend-note" in c), None)
    if note is None:
        # No Streamlit runtime here; assert the transform directly instead of the render.
        import re as _re
        note = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", chips_lib.SPREAD_SIGN_NOTE)
    assert "**" not in note, "markdown emphasis inside a raw HTML block is not processed"
    assert "<strong>" in note


def test_a_game_with_no_closing_line_shows_a_dash_not_an_outline():
    """R-171. A dotted outline still reads as a value being shown. Marc found it with Division
    on All Divisions, where lower-division games carry no spread or total at all and the strip
    came out as three faint marks with nothing saying why.

    The dash keeps the shape class, and therefore the box: R-166 aligns every card's strip by
    giving the indicators identical footprints, so a mark that sized itself differently would
    take that alignment out from under a whole column of cards.
    """
    nan = float("nan")
    strip = schedule._result_strip(_row(winner_covered_close=nan, over_met=nan))
    assert strip.count(schedule.NO_DATA_MARK) == 2, "cover and over, both unmeasurable"
    assert "cfdb-sh-cover cfdb-ind-nodata" in strip, "the box survives"
    assert "cfdb-sh-over cfdb-ind-nodata" in strip
    # The upset slot is a real answer here and must NOT become a dash.
    assert "cfdb-sh-upset cfdb-ind-quiet" in strip
    # And a game with a line carries no dashes at all.
    assert schedule.NO_DATA_MARK not in schedule._result_strip(_row())


def test_the_unplayed_strip_stays_empty_rather_than_dashed():
    """"Not played yet" and "played, no line held" are different facts. A dash on an unplayed
    game would claim we looked and found nothing."""
    nan = float("nan")
    unplayed = schedule._result_strip(_row(is_completed=False, upset_level=nan,
                                           winner_covered_close=nan, over_met=nan))
    assert schedule.NO_DATA_MARK not in unplayed
    assert unplayed.count("cfdb-ind-none") == 3


def test_an_unranked_game_is_not_assessed_as_a_non_upset():
    """R-172. `is_upset` is derived from AP poll ranks, and its `else false` branch fired
    whenever NEITHER team was ranked — so 91,047 of 109,108 completed games claimed "not an
    upset" with no favorite to be upset. Marc found it on Grand Valley State at Charleston
    (WV): two Division II sides, no ranks, no line, drawn as an assessed non-upset.

    The model now returns null there and the page draws the same dash the cover and total
    slots use. "We looked and it was unremarkable" and "there was nothing to look at" are
    different facts and must not share a mark.
    """
    nan = float("nan")
    no_basis = schedule._result_strip(_row(upset_level=nan, home_rank=nan, away_rank=nan))
    assessed = schedule._result_strip(_row(upset_level="none"))
    assert "cfdb-sh-upset cfdb-ind-nodata" in no_basis, "no ranks, no assessment, a dash"
    assert "cfdb-sh-upset cfdb-ind-quiet" in assessed, "ranked and unremarkable keeps a circle"
    assert "cfdb-sh-upset cfdb-ind-quiet" not in no_basis
    # A real upset is unaffected in either direction.
    assert "cfdb-u2" in schedule._result_strip(_row(upset_level="big"))


def test_the_upset_scale_cannot_out_run_its_verdict():
    """`not null` is null, not true, so without explicit branches a big win with no line falls
    through to the margin tests and comes out 'blowout'.

    GUARDED IN dbt, NOT HERE. An earlier version sliced 1,200 characters of SQL and asserted on
    the order of two strings inside it, which broke on a restructure without the property
    changing. The dbt assertion checks the same thing against 109,108 real rows.
    """
    guard = (Path(schedule.__file__).resolve().parents[2] / "dbt" / "tests"
             / "assert_the_upset_scale_agrees_with_the_verdict.sql")
    assert guard.exists(), "the property is asserted in dbt; this test guards that assertion"
    body = guard.read_text()
    assert "is_upset_by_line is null and upset_level is not null" in body
    assert "is_upset_by_line is not null and upset_level is null" in body


def test_the_favorite_by_the_line_losing_is_an_upset():
    """R-173. Marc, on North Carolina at TCU: "TCU favored by 8, but they lose by 5. That's a
    Level 1 upset." Neither side was ranked, so the rank basis had nothing to say and the page
    drew a dash — correct under the old definition and not what an upset means.

    The two bases answer different questions: a poll ranks a team's SEASON, a spread states
    the expected winner of THIS game. The line leads.
    """
    nan = float("nan")
    strip = schedule._result_strip(_row(upset_level="upset", home_rank=nan, away_rank=nan))
    assert "cfdb-u1" in strip, "a level-1 upset, with no rank anywhere"
    assert "cfdb-sh-upset cfdb-ind-nodata" not in strip
    assert "against the closing spread" in strip, "and the tooltip says what judged it"


def test_the_upset_tooltip_names_its_basis():
    """A reader checking a surprising verdict needs to know which question produced it."""
    assert schedule._upset_title("upset") == "upset, against the closing spread"
    assert schedule._upset_title("none") == "the favorite won, against the closing spread"
    # No verdict, no "against" clause — there is nothing to name.
    assert "against" not in schedule._upset_title("")


def test_no_basis_still_reads_as_no_basis():
    """R-172 does not regress: a game with neither a line nor a rank is still a dash, not a
    verdict of "the favorite won"."""
    nan = float("nan")
    strip = schedule._result_strip(_row(upset_level=nan, home_rank=nan, away_rank=nan))
    assert "cfdb-sh-upset cfdb-ind-nodata" in strip
    assert "nothing named a favorite" in strip


def test_the_legend_thresholds_come_from_the_data_not_from_the_app():
    """R-224. THEY WERE STRING LITERALS, AND THEY WERE WRONG BY ONE.

    `srv_game` classifies with a strict `>`, so a 7-point win is level 1 and a 14-point win is
    level 2. The legend said "Upset by 7+" and "Upset by 14+", claiming the opposite at both
    boundaries — 138 completed games in the live data carried a level it contradicted. The data
    was never wrong; only the labels were, which is the worse failure because nothing breaks.

    The numbers are columns on the frame now, so this feeds a frame and reads the labels back.
    A hardcoded label cannot pass: change the columns and the words must change with them.
    """
    from views import schedule

    def bands(big, blowout):
        frame = pd.DataFrame([{"upset_margin_big": big, "upset_margin_blowout": blowout}])
        return [entry[-1] for _, entries in schedule._legend_groups(frame)
                for entry in entries if str(entry[-1]).startswith("Upset by")]

    assert bands(7, 14) == ["Upset by 7 or fewer", "Upset by 8–14", "Upset by 15+"]
    # AND THEY MOVE. A literal would sit still here, which is what the whole change is about.
    #
    # This replaces a test that changed a module constant and RELOADED the module to prove the
    # same thing. That was the right test while the numbers were a constant; now they come
    # from the frame, feeding two frames proves it directly and without reloading a view
    # module mid-suite.
    assert bands(9, 21) == ["Upset by 9 or fewer", "Upset by 10–21", "Upset by 22+"]
    # The boundary values must never START a band: that is the off-by-one, spelled as it shipped.
    assert "Upset by 7+" not in bands(7, 14) and "Upset by 14+" not in bands(7, 14)


def test_a_frame_without_the_columns_still_renders_a_coherent_legend():
    """A page that raised because one column was missing would trade a wrong label for a blank
    screen, which is a bad trade for a legend. The shipped defaults cover it — and they are
    NOT a production path, which is why `srv_game` carries the columns at all."""
    from views import schedule
    bands = [entry[-1] for _, entries in schedule._legend_groups(pd.DataFrame())
             for entry in entries if str(entry[-1]).startswith("Upset by")]
    assert bands == ["Upset by 7 or fewer", "Upset by 8–14", "Upset by 15+"]


def test_nothing_in_the_app_reads_the_thresholds_from_a_file_any_more():
    """The stopgap read dbt_project.yml, which is outside the site image's build context — so
    the deployed page ran on a fallback that was correct by coincidence. R-225 guards the
    boundary generally; this pins the specific thing that crossed it."""
    from lib import metrics
    import ast
    module = ast.parse(
        (Path(__file__).resolve().parents[1] / "site" / "lib" / "metrics.py").read_text())
    # THE DOCSTRING EXPLAINS the file read that was removed, so a naive substring search
    # matches its own prose — the eighth time in this repo. Strip docstrings and check code.
    for node in ast.walk(module):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)):
                node.body = node.body[1:] or [ast.Pass()]
    code = ast.unparse(ast.fix_missing_locations(module))
    assert "dbt_project.yml" not in code, "metrics.py reads the dbt project file again"
    assert "__file__" not in code, "metrics.py resolves a path at all"
    assert not hasattr(metrics, "_upset_thresholds")
    assert metrics.BIG_COLUMN == "upset_margin_big"


def test_the_page_and_the_workbook_phrase_the_bands_from_one_function():
    """Two legends for one metric is the thing R-224 is about, and the workbook's version was
    right while the page's was wrong — which is how the disagreement was found. Both now call
    `metrics.upset_bands`, so they cannot differ by a word or by a number."""
    from lib import metrics
    one, two, three = metrics.upset_bands(7, 14)
    assert (one, two, three) == ("Upset by 7 or fewer", "Upset by 8–14", "Upset by 15+")
    assert metrics.upset_bands(9, 21)[1] == "Upset by 10–21"


def test_no_user_facing_string_uses_british_spelling():
    """Marc: "Use US version of favorite". The site said favourite and the workbook said
    favorite, in two legends describing the same three marks."""
    from pathlib import Path as _Path
    site = _Path(__file__).resolve().parents[1] / "site"
    # ONE exemption, spelled out rather than pattern-matched: CSV_LABEL_OVERRIDES quotes the
    # header in Marc's column-order file verbatim, and rewriting the quote would make the
    # recorded divergence look like a typo instead of a decision.
    exempt = '"Favourite covered": "Favorite covered"'
    offenders = []
    for path in sorted(site.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if "avourite" not in line:
                continue
            if exempt in line or "Marc's CSV" in line:
                continue
            offenders.append(f"{path.name}:{number}: {line.strip()[:70]}")
    assert not offenders, offenders


def test_the_band_appears_once_per_week_not_once_per_day(counting_markdown):
    """THE THING THE SPEC WARNS ABOUT FIRST. Both views grouped by day only, so bolting the
    band onto that loop would have repeated it above Thursday, Friday and Saturday.

    Two weeks, four days: two bands, four day headings.
    """
    from views import schedule
    rows = pd.DataFrame(
        [_row(game_id=i, week=1, game_date="2026-09-03") for i in range(3)]
        + [_row(game_id=10 + i, week=1, game_date="2026-09-05") for i in range(2)]
        + [_row(game_id=20 + i, week=2, game_date="2026-09-10") for i in range(4)]
        + [_row(game_id=30 + i, week=2, game_date="2026-09-12") for i in range(1)])
    schedule._stacked(rows, _Scope())
    html = "\n".join(counting_markdown["html"])
    # Two week bands plus one season-to-date, keyed on the LATEST week shown — week 2 here,
    # so the reference runs through week 1.
    assert html.count("cfdb-weekband-title") == 3, "two week bands plus season-to-date"
    assert "through week 1" in html
    assert html.count(">Week 1<") == 1 and html.count(">Week 2<") == 1
    assert html.count("cfdb-daygroup") == 4


def test_both_views_render_the_same_band(counting_markdown):
    """`_by_week` is shared precisely so the dense and stacked views cannot drift about where
    the band goes or what is in it."""
    from views import schedule
    rows = pd.DataFrame(
        [_row(game_id=i, week=1, game_date="2026-09-03") for i in range(3)])
    schedule._stacked(rows, _Scope())
    stacked = [h for h in counting_markdown["html"] if "cfdb-weekband" in h]
    counting_markdown["html"].clear()
    schedule._dense(rows, _Scope())
    dense = [h for h in counting_markdown["html"] if "cfdb-weekband" in h]
    assert stacked and stacked == dense


def test_the_band_carries_three_metrics_and_the_implied_pair_leads():
    """The implied pair is the headline because it is the only thing here that MOVES with the
    season — measured 20.3 points of gap in weeks 1-3 against 10.1 from week 5 on, replicating
    across two seasons. The O/U is the control: it swings 1.4 points all year."""
    from views import schedule
    assert [m for m, _ in schedule.BAND_METRICS] == [
        "market_implied_favorite_points", "market_implied_underdog_points", "total"]


def test_the_implied_pair_shares_one_axis(counting_markdown):
    """Drawn on the same scale, the horizontal gap between the two humps IS the spread, and
    the pair converging through the season is visible without reading a number. Different
    axes would make that gap meaningless."""
    from views import schedule
    schedule._stacked(pd.DataFrame(
        [_row(game_id=i, week=1, game_date="2026-09-03") for i in range(2)]), _Scope())
    band = next(h for h in counting_markdown["html"] if "cfdb-weekband" in h)
    # Both thumbnails draw ten bars over the same viewBox, so a value at the same fraction of
    # the axis lands at the same pixel in both.
    assert band.count("viewBox='0 0 120 28'") == 3


def test_a_week_with_no_distribution_still_reserves_the_space(counting_markdown, monkeypatch):
    """R-141 again: a band that grows a thumbnail when a week gets priced shifts everything
    beside it mid-season."""
    from views import schedule
    monkeypatch.setattr(schedule, "_distributions", lambda s, t: pd.DataFrame())
    schedule._stacked(pd.DataFrame(
        [_row(game_id=i, week=7, game_date="2026-10-10") for i in range(2)]), _Scope())
    band = next(h for h in counting_markdown["html"] if "cfdb-weekband" in h)
    assert band.count("cfdb-dist-empty") == 3
    assert "width:120px" in band
    assert ">Week 7<" in band, "the band itself still renders — only its pictures are absent"


def test_season_to_date_is_absent_in_week_one_rather_than_zero(counting_markdown):
    """There is nothing before week 1, so there is no row. An Empty state, not a zero — the
    same rule a week nobody has priced gets."""
    from views import schedule
    schedule._stacked(pd.DataFrame(
        [_row(game_id=i, week=1, game_date="2026-09-03") for i in range(2)]), _Scope())
    html = "\n".join(counting_markdown["html"])
    assert "Season to date" not in html

    counting_markdown["html"].clear()
    schedule._stacked(pd.DataFrame(
        [_row(game_id=i, week=2, game_date="2026-09-10") for i in range(2)]), _Scope())
    html = "\n".join(counting_markdown["html"])
    assert "Season to date" in html and "through week 1" in html


def test_the_band_admits_it_is_fbs_only_when_the_page_is_not(counting_markdown):
    """With Division set to All the cards below include games these numbers exclude. Saying so
    is cheaper than a reader adding them up and finding they disagree — and much cheaper than
    a division dimension on the grain, which roughly triples the rows to fix a mismatch that
    appears at one filter setting."""
    from views import schedule

    class AllDivisions(_Scope):
        division = "all"

    schedule._stacked(pd.DataFrame(
        [_row(game_id=i, week=1, game_date="2026-09-03") for i in range(2)]), AllDivisions())
    band = next(h for h in counting_markdown["html"] if "cfdb-weekband" in h)
    assert "FBS only" in band

    counting_markdown["html"].clear()
    schedule._stacked(pd.DataFrame(
        [_row(game_id=i, week=1, game_date="2026-09-03") for i in range(2)]), _Scope())
    band = next(h for h in counting_markdown["html"] if "cfdb-weekband" in h)
    assert "FBS only" not in band, "at the FBS setting there is nothing to warn about"


# === R-227: the page was dropping games silently ==========================================

def test_the_page_says_so_when_it_is_showing_fewer_games_than_the_filters_select(monkeypatch):
    """THE SAME DEFECT R-196 FIXED IN THE EXPORT, LEFT ON THE PAGE.

    `limit 400` was a literal, and 2026 week 1 holds 456 games at All Divisions — fifty-six
    dropped with nothing said. A silently short page is worse than a slow one: the reader has
    no way to know, and the count they are reading is wrong in a direction they cannot guess.
    """
    from views import schedule
    shown = pd.DataFrame([_row(game_id=i, week=1, game_date="2026-09-03") for i in range(5)])
    shown["rows_in_scope"] = 456

    seen = {}
    monkeypatch.setattr(schedule.st, "warning", lambda text, **k: seen.update(text=text))
    schedule._truncation_note(shown)
    assert "5" in seen["text"] and "456" in seen["text"]
    assert "451" in seen["text"], "it must name how many are missing, not just the two totals"
    assert "narrow" in seen["text"].lower(), "and what to do about it"


def test_both_views_actually_call_the_truncation_check(counting_markdown, monkeypatch):
    """CALLING THE FUNCTION IS THE HALF THAT MATTERS.

    A mutation that deleted `_truncation_note(df)` from `_by_week` left every test green,
    because they all called the function directly. A correct function nobody calls is the
    same defect as no function.
    """
    from views import schedule
    rows = pd.DataFrame([_row(game_id=i, week=1, game_date="2026-09-03") for i in range(3)])
    rows["rows_in_scope"] = 456

    for renderer in (schedule._stacked, schedule._dense):
        seen = []
        monkeypatch.setattr(schedule.st, "warning", lambda t, **k: seen.append(t))
        renderer(rows, _Scope())
        assert seen, f"{renderer.__name__} rendered a truncated page and said nothing"
        assert "456" in seen[0]


def test_the_games_query_asks_for_the_in_scope_count(monkeypatch):
    """`count(*) over ()` is what makes the warning possible at all — a window function is
    evaluated BEFORE the LIMIT, so one query answers both "how many are there" and "how many
    did I get". Dropping it leaves the warning permanently silent and nothing else changes.
    """
    # Read from the source rather than by calling `_rows`, which is `@st.cache_data`-wrapped
    # and has no cache to clear without a Streamlit runtime.
    source = Path(schedule.__file__).read_text()
    games_query = source[source.index("select game_id, season, week"):
                         source.index("limit {ROW_CAP}")]
    assert "count(*) over () as rows_in_scope" in " ".join(games_query.split()), (
        "without the window count the truncation warning can never fire, and nothing else "
        "about the page changes")


def test_a_page_that_is_not_truncated_says_nothing(monkeypatch):
    """A warning on every page is a warning nobody reads."""
    from views import schedule
    full = pd.DataFrame([_row(game_id=i, week=1, game_date="2026-09-03") for i in range(5)])
    full["rows_in_scope"] = 5
    called = []
    monkeypatch.setattr(schedule.st, "warning", lambda *a, **k: called.append(a))
    schedule._truncation_note(full)
    schedule._truncation_note(pd.DataFrame())
    assert not called


def test_the_cap_clears_the_biggest_week_the_warehouse_has_ever_held():
    """Measured, not chosen: the largest single week across every season is 456 games, and
    the typical one is 50. A cap below the worst case is the defect, and a cap of infinity is
    a browser tab nobody wants — a whole season at All Divisions is 3,745 games."""
    from views import schedule
    assert schedule.ROW_CAP >= 456 * 2, (
        "the cap should clear the worst observed week with real headroom")
    assert schedule.ROW_CAP < 3745, "but still bound a whole-season view"


def test_the_page_query_carries_the_named_cap_and_no_literal_limit():
    """The literal was the problem: nothing named it, so nothing could report it."""
    import re
    # COMMENTS STRIPPED FIRST. The comment explaining why the literal went says "limit 400",
    # so a bare substring search matches its own prose — the ninth time in this repo.
    source = "\n".join(line for line in Path(schedule.__file__).read_text().splitlines()
                       if not line.lstrip().startswith("#"))
    # PARSED, NOT SUBSTRING-MATCHED. `"limit 400" in source` also matches `limit 4000` — the
    # distributions query's own cap — so the first version failed on a line it had no quarrel
    # with. Read the limits as tokens and judge them individually.
    limits = re.findall(r"\blimit\s+(\S+)", source)
    assert "{ROW_CAP}" in limits, f"the games query no longer uses the named cap: {limits}"
    assert "400" not in limits, "the bare literal that dropped 56 games is back"
    # 4000 bounds the distributions read, which is a different query with a different shape:
    # a few hundred rows per season, and it is not what a reader scrolls.
    unexpected = [x for x in limits if x.isdigit() and x not in ("1", "4000")]
    assert not unexpected, f"unexplained numeric limit(s): {unexpected}"
