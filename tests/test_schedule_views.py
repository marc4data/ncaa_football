"""The Schedule page's two renderings. R-043.

These exercise the RENDERERS against frames built here, not against a database. The bug they
exist for was not a query bug: the stacked view rendered fifteen of fifty-nine games and
stopped, because a null in an object column is NaN, NaN is truthy, and `nan or ""` is nan.
It failed inside states.section, which caught it and drew an Error state — so there was no
exception to catch, no error to assert on, and every existing test passed.
"""
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
        home_team_record_display="8-2",
        away_team_slug="auburn", away_team_display="Auburn", away_abbreviation="AUB",
        away_logo_url=None, away_conference="SEC", away_points=17, away_rank=None,
        away_team_record_display="5-5",
        venue_display="Bryant-Denny", network="ESPN", network_abbreviation="ESPN",
        is_neutral_site=False, is_conference_game=True, is_completed=True, winner="Alabama",
        spread_current=-7.5, total_current=52.5, predicted_margin=-6.0,
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


def test_a_long_team_name_falls_back_to_its_abbreviation():
    """R-085: a character threshold, applied identically everywhere."""
    long_name = "Middle Tennessee State"
    assert len(long_name) > schedule.TEAM_NAME_MAX
    row = _row(home_team_display=long_name, home_abbreviation="MTSU")
    assert schedule._team_name(row, "home") == "MTSU"
    assert schedule._team_name(_row(), "home") == "Alabama"


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
    neutral = game.format(_row(is_neutral_site=True))
    plain = game.format(_row(is_neutral_site=False))
    assert schedule.NEUTRAL_GLYPH in neutral
    assert schedule.NEUTRAL_GLYPH not in plain
    # Both renderings still offer the matchup, which is the destination the column is for.
    for rendered in (neutral, plain):
        assert schedule.table.DETAILS_GLYPH in rendered
    assert game.link(_row()) is not None


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


def test_the_team_row_has_exactly_one_flex_child():
    """R-105, AND THE ONLY ASSERTION THAT CATCHES IT.

    `.cfdb-gamecard-row` is a flex container. The bug was not a margin: `team_cell` returns
    SEVERAL sibling spans and `_team_with_record` appends another, so the row had four or
    five children and `space-between` distributed every one of them across ~1,400px. Marc's
    screenshot showed logo hard left, name adrift near the centre, record right of centre,
    score hard right.

    Counting children is what distinguishes the fix from the plausible non-fix. A version
    that only removed `justify-content` from the CSS leaves five children in the row and
    passes any test asserting on classes or on the rendered text; it fails this one.
    """
    parser = _Children()
    parser.feed(schedule._team_row(_row(), "away", _Scope()))
    assert parser.direct == 1, "the wrapper is the fix; margins were never the problem"


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


def test_the_card_carries_a_kickoff_time():
    """R-108. The card had none at all."""
    import re
    card = _card()
    assert "cfdb-gamecard-time" in card
    # Asserted as a SHAPE, not as "7:00". `fmt.clock` converts to the reader's local zone,
    # so a literal makes this test pass or fail on the machine's TZ rather than on the code.
    shown = re.search(r"cfdb-gamecard-time'>([^<]+)<", card).group(1)
    assert re.fullmatch(r"\d{1,2}:\d{2} [AP]M \w+", shown), shown


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
    assert "cfdb-linescore" in card
    assert "cfdb-market" not in card


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
    assert "cfdb-linescore" not in card
    assert "not recorded" not in card
    assert "cfdb-market" in card
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

def test_the_score_moved_into_the_box_score_with_a_header_and_abbreviations():
    """R-109. The separate bold points block stated the same two numbers a second time once
    quarters existed, and stated them in only one place when they did not."""
    card = _card()
    assert "cfdb-gamecard-pts" not in card, "the separate points block is gone"
    assert f"<th title='Total'>{schedule.TOTAL_HEADER}</th>" in card, "the column is headed"
    assert "cfdb-ls-total" in card
    assert ">31<" in card and ">17<" in card, "the final score is still on the card"
    assert ">ALA<" in card and ">AUB<" in card, "row labels are abbreviations"
    assert ">Alabama<" not in card.split("cfdb-linescore")[1], "not the full name in the table"


def test_the_box_score_keeps_the_overtime_column_behaviour():
    card = _card(home_periods=5, away_periods=5, home_overtime_points=7,
                 away_overtime_points=0)
    assert "<th>OT</th>" in card
    assert "cfdb-ls-ot" in card
    assert "<th>OT</th>" not in _card(), "regulation games do not invent the column"


def test_the_winner_is_marked_in_the_stacked_view_too():
    """R-113. North Carolina won 15-10 and nothing on the card said so. The same three
    states and the same width reservation as R-100, or the totals stop aligning."""
    card = _card()
    assert schedule.WINNER_GLYPH in card
    assert card.count("cfdb-ls-mark") == 3, "a column for it in the header and both rows"
    assert "cfdb-winner-spacer" in card, "reserved on the losing row"


# --- R-110 / R-015: the grid, and one geometry for the page ------------------------------

def test_the_cards_go_into_a_css_grid_not_streamlit_columns(counting_markdown):
    """R-110. `st.columns(2)` is a FIXED two-up — Streamlit renders server-side and cannot
    measure a viewport, so it would keep two cards side by side on a phone."""
    df = pd.DataFrame([_row(game_id=i) for i in range(4)])
    schedule._stacked(df, _Scope())
    grid = [h for h in counting_markdown["html"] if "cfdb-cardgrid" in h]
    assert len(grid) == 1, "one grid per day group"
    assert grid[0].count("<div class='cfdb-gamecard'>") == 4, "the cards are its children"


def test_every_card_on_the_page_shares_one_box_score_geometry():
    """R-015 FOR THE STACKED VIEW, which is where it was never done.

    `_dense` has computed `column_layout` once outside the day loop since it was built. The
    cards had no equivalent: each `.cfdb-linescore` auto-sized to its own contents, so a card
    with an OT column was wider than the one beside it and the row labels started at a
    different x on every card. In R-110's two-up grid that reads as broken alignment.

    THIS IS THE TEST THAT DISTINGUISHES SHARED FROM PER-CARD. The frame below deliberately
    mixes an overtime game, a regulation game and a five-character abbreviation — exactly the
    three things that make per-card sizing diverge. Computing the geometry inside the card
    loop passes every other test in this file and fails this one.
    """
    df = pd.DataFrame([
        _row(game_id=1, home_periods=5, away_periods=5, home_overtime_points=7),
        _row(game_id=2),
        _row(game_id=3, home_abbreviation="MTSU", home_team_display="Middle Tennessee"),
    ])
    geo = schedule._linescore_geometry(df)
    cards = [schedule._card(r, _Scope(), geo) for _, r in df.iterrows()]
    colgroups = {c[c.index("<colgroup>"):c.index("</colgroup>")] for c in cards}
    assert len(colgroups) == 1, f"cards disagree about their own geometry: {colgroups}"
    # And the shared shape was decided by the whole page, not by whichever card came first.
    assert geo["ot"] is True, "one overtime game on the page gives every card the column"
    assert geo["label_ch"] == 4, "the widest abbreviation on the page sizes the label column"
    assert all("<th>OT</th>" in c for c in cards)


def test_a_regulation_game_leaves_its_overtime_cell_blank_rather_than_zero():
    """The cost of the shared column, paid honestly. There were no overtime points; a 0 would
    claim a scoreless overtime that was never played."""
    df = pd.DataFrame([_row(game_id=1, home_periods=5, away_periods=5,
                            home_overtime_points=7, away_overtime_points=0),
                       _row(game_id=2)])
    geo = schedule._linescore_geometry(df)
    regulation = schedule._card(df.iloc[1], _Scope(), geo)
    assert "cfdb-ls-ot" not in regulation
    assert "<td></td>" in regulation


def test_the_winner_marker_precedes_the_total_in_both_views():
    """One page must not mark a winner in two directions.

    The marker is a RIGHT-pointing glyph, so it has to sit before the number it describes.
    The first version of the box score put its column last, which pointed it away from the
    total while the dense view pointed into the score — on the same page, in the same week.
    """
    card = _card()
    linescore = card[card.index("<table class='cfdb-linescore'"):]
    assert linescore.index("cfdb-ls-mark") < linescore.index("cfdb-ls-total")
    dense = schedule._score_cell(_row(), "home")
    assert dense.index(schedule.WINNER_GLYPH) < dense.index("31")


def test_the_market_block_is_the_same_width_whether_or_not_the_line_moved():
    """R-015's principle in the pre-kick state. Without a fixed layout the block sizes itself
    to its contents, so a card with no move renders a narrower box than the one beside it and
    the two O/U numbers sit at different x."""
    nan = float("nan")
    base = dict(is_completed=False, winner=None, home_points=nan, away_points=nan,
                home_periods=nan, away_periods=nan)
    moved = _card(**base, total_move_from_open=1.5, spread_move_from_open=-0.5)
    still = _card(**base, total_move_from_open=nan, spread_move_from_open=nan)
    for card in (moved, still):
        assert card.count("<colgroup>") == 1
        # "<col " with the space — "<colgroup>" itself matches a bare "<col".
        assert card[card.index("<colgroup>"):card.index("</colgroup>")].count("<col ") == 3
    # And the still card reserves the move cell rather than dropping the column.
    assert still.count("<td>") >= 2


def test_the_box_score_states_its_own_width_rather_than_letting_content_decide():
    """`table-layout:fixed` distributes a KNOWN width by the colgroup; with `width:auto` the
    browser still runs a content pass to decide what that width is.

    Measured on the rendered page before this: every numeric column was identical across all
    sixty cards and the label column ranged from 31px to 46px, because the label is the only
    cell whose content varies. Asserting the colgroup alone passes against that.
    """
    geo_regulation = {"ot": False, "label_ch": 4}
    geo_overtime = {"ot": True, "label_ch": 4}
    label = schedule._ls_label_em(geo_regulation)
    assert float(schedule._ls_width(geo_regulation).rstrip("em")) == \
        pytest.approx(label + 4 * 2.6 + 3 + 1.2)
    assert float(schedule._ls_width(geo_overtime).rstrip("em")) == \
        pytest.approx(label + 5 * 2.6 + 3 + 1.2), "the OT column is in the sum"
    card = _card()
    table_tag = card[card.index("<table class='cfdb-linescore'"):]
    assert "style='width:" in table_tag[:120]


def test_the_box_score_label_is_sized_in_em_not_in_the_width_of_a_zero():
    """`ch` is the advance width of "0"; these labels are UPPERCASE text in a PROPORTIONAL
    face, and the cell also carries padding the column has to cover.

    Measured with the `ch` version: 30px of column against 45px of content for "NMSU", so
    every abbreviation on every card was ellipsis-clipped — invisible in a screenshot, which
    is why it took a measurement to find. A four-character label needs more than four times
    the width of a digit.
    """
    card = _card()
    colgroup = card[card.index("<colgroup>"):card.index("</colgroup>")]
    assert "ch" not in colgroup, "ch under-sizes uppercase proportional text"
    assert schedule._ls_label_em({"ot": False, "label_ch": 4}) > 3.5
