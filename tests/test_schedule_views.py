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
    def link(self, page, **kwargs):
        return "/x"


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
    assert schedule.DOME_GLYPH in cell
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
    order = sql[sql.index("order by game_date"):sql.index("limit 400")]
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
    assert "cfdb-gc-market" in card
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
    for css in ("cfdb-gamecard", "cfdb-gc-team", "cfdb-gc-mid", "cfdb-gc-market",
                "cfdb-gc-tot", "cfdb-gamecard-meta"):
        assert css in documented, f".{css} renders a region of the card and has no name"
