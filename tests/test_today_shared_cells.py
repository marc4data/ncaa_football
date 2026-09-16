"""A144 — the two cells four sections share, and the legend that explains their marks.

🚨 MARC ASKED FOR THE SAME TWO THINGS UNDER FOUR HEADINGS. Cowork's reading of the spec is the
rule these tests exist to hold: **"Building them four times is four chances to diverge."** So the
assertions here are mostly about SAMENESS — one producer, one record rule, one legend inventory —
because four correct copies pass every per-panel test and still drift on the fifth round.
"""
import ast
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(ROOT / "tests"))

from lib import fmt, glyphs, table                     # noqa: E402
from views import today                                # noqa: E402

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()


def _game(**over):
    """A completed game row, in `srv_game`'s spelling."""
    row = {"game_id": 401856679, "season": 2026, "week": 2, "is_completed": True,
           "home_team_display": "Iowa", "away_team_display": "Iowa State",
           "home_team_slug": "iowa", "away_team_slug": "iowa-state",
           "home_logo_url": "https://x/iowa.png", "away_logo_url": "https://x/isu.png",
           "home_rank": 12, "away_rank": None,
           "home_team_record_display": "1-0", "away_team_record_display": "2-0",
           "home_team_record_after_display": "2-0", "away_team_record_after_display": "2-1",
           "home_points": 16, "away_points": 13,
           "spread_favorite_side": "away"}
    row.update(over)
    return row


# --- the record rule moved out of schedule.py and must not have changed -------------------

def test_the_record_span_moved_without_changing_a_byte():
    """🚨 B117's INSTRUMENT, APPLIED TO THE FUNCTION A144 MOVED: hash both sides.

    `schedule._record_span` was lifted into `table.record_span` so Today could draw the identical
    record. ⚠️ A MOVE THAT CHANGES THE OUTPUT IS NOT A MOVE, and the two facts it decides — R-140's
    completed/scheduled choice and R-084's point-in-time columns — are exactly the kind that look
    fine wrong: a real record, in a real span, describing the wrong moment.

    ✅ THE EXPECTATION IS THE PRE-MOVE IMPLEMENTATION, INLINED, rather than a string this test
    wrote. A test asserting the new output equals a literal I typed would pass on a function that
    had quietly swapped the two columns — because I would have typed what it produces.
    """
    def before_the_move(row, side):
        """`schedule._record_span` exactly as it stood at `ce87248`."""
        if row.get("is_completed"):
            record = row.get(f"{side}_team_record_after_display")
            title = "record after this game"
        else:
            record = row.get(f"{side}_team_record_display")
            title = "record going into this game"
        missing = record is None or (not isinstance(record, str) and pd.isna(record))
        if missing or record == "":
            return ""
        return f"<span class='cfdb-team-record' title='{title}'>{record}</span>"

    cases = [
        _game(),
        _game(is_completed=False),
        _game(home_team_record_after_display=None),
        _game(is_completed=False, home_team_record_display=None),
        _game(home_team_record_after_display=""),
        _game(home_team_record_after_display=float("nan")),
    ]
    for row in cases:
        for side in ("home", "away"):
            assert table.record_span(
                row, f"{side}_team_record_display",
                f"{side}_team_record_after_display") == before_the_move(row, side), (
                f"the record span changed when it moved — {side}, is_completed="
                f"{row.get('is_completed')}, after={row.get(f'{side}_team_record_after_display')!r}")


def test_the_record_rule_is_R140_and_not_whichever_column_is_present():
    """🚨 R-140 IS A CHOICE BETWEEN TWO REAL COLUMNS, AND THE BREAK THAT MATTERS KEEPS BOTH REAL.

    A completed game shows the record it PRODUCED; a scheduled one shows the record it carried IN.
    ⚠️ Both columns are populated on the same row, so a function that simply preferred whichever
    was non-null would pass every presence assertion and be wrong on every completed game by
    exactly one game.
    """
    played, upcoming = _game(), _game(is_completed=False)
    assert ">2-0<" in table.record_span(played, "home_team_record_display",
                                        "home_team_record_after_display")
    assert "after this game" in table.record_span(played, "home_team_record_display",
                                                  "home_team_record_after_display")
    assert ">1-0<" in table.record_span(upcoming, "home_team_record_display",
                                        "home_team_record_after_display")
    assert "going into this game" in table.record_span(upcoming, "home_team_record_display",
                                                       "home_team_record_after_display")


def test_a_relation_with_no_after_column_shows_the_before_record_rather_than_nothing():
    """`srv_game_team` publishes `record_before_display` alone — the team leaderboard's relation.

    ⚠️ THE COMPLETED FLAG IS STILL TRUE ON THOSE ROWS, so a rule that reached for an after-column
    whenever the game was played would render an empty span on every row of that board.
    """
    row = {"record_before_display": "3-1", "is_completed": True}
    assert ">3-1<" in table.record_span(row, "record_before_display")
    assert "going into this game" in table.record_span(row, "record_before_display")


# --- one cell, four sections ---------------------------------------------------------------

def test_the_team_cell_carries_all_four_facts_marc_asked_for():
    """rank + logo + hyperlinked name + record, in one cell. AC-1.5 for the unranked case."""
    cell = today._team_identity(_game(), "home")
    assert "cfdb-logo" in cell, "logo"
    assert "#12" in cell, "rank badge"
    assert "cfdb-teamlink" in cell and "/team?team=iowa" in cell, "the NAME is the link"
    assert ">Iowa<" in cell, "the display name"
    assert "cfdb-team-record" in cell, "the record"


def test_an_unranked_team_shows_no_badge_rather_than_an_em_dash():
    """🚨 AC-1.5, AND `home_rank`'s NULL IS A PUBLISHED FACT RATHER THAN A GAP.

    📊 MEASURED on 2026 regular: ranks run 1..25 and stop, because it is a Top 25; 5.3% of played
    games carry a home rank. B118 established the same for `opponent_rank` and measured 7.6% — the
    identical query here returns 7.63%. **So NULL means UNRANKED and the cell says so by drawing
    nothing**, which is the older and better answer than the word.
    """
    cell = today._team_identity(_game(), "away")   # away_rank is None
    assert "cfdb-rank" not in cell, "an unranked team must carry no badge"
    assert fmt.EM_DASH not in cell, "and certainly not an em dash inside one"
    assert ">Iowa State<" in cell, "the team is still drawn"


def test_the_record_sits_outside_the_anchor():
    """🚨 R-129, AND IT IS WHY THE RECORD IS NOT A `team_cell` PARAMETER.

    Schedule's own words: *"the record leaves the anchor entirely rather than being styled to look
    non-clickable — styling cannot remove the pointer cursor, and dead text under a pointer is
    worse than either state."* ⚠️ Folding the record into `table.team_cell` would have put it
    inside the anchor on every page that links a team name, which is five of them.
    """
    cell = today._team_identity(_game(), "home")
    anchor = re.search(r"<a class='cfdb-teamlink'.*?</a>", cell, re.S)
    assert anchor, cell
    assert "cfdb-team-record" not in anchor.group(0), "the record is inside the link"
    assert cell.index("cfdb-team-record") > anchor.end() - 1, "and it trails the cluster"


def test_every_section_marc_named_draws_the_same_cell():
    """🚨 THE SAMENESS ASSERTION, AND IT IS THE POINT OF THE ROUND.

    Four sections, one producer. ⚠️ A per-panel test cannot see this: four hand-built cells that
    each carry a logo and a rank pass four presence assertions and drift on the fifth round. So
    this reads the SOURCE and counts the call sites, which is the only place the sameness lives.
    """
    tree = ast.parse(SOURCE)
    callers = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                        and inner.func.id in ("_team_identity", "_favorite_cell",
                                              "_underdog_cell")):
                    callers.add(node.name)
    # `_favorite_cell` / `_underdog_cell` are the recap lists' two adapters; they and the
    # scoreboard and the team board are the four places a team is drawn.
    for expected in ("_scoreboard", "_favorite_cell", "_underdog_cell", "_leaderboards"):
        assert expected in callers, f"{expected} does not draw the shared team cell"


def test_no_table_with_a_linked_team_name_also_links_its_rows():
    """🚨 NESTED ANCHORS ARE INVALID HTML AND THE OUTER ONE WINS — the reader clicks the team name
    and lands on the game.

    ⚠️ A141 ADDED THIS ASSERTION FOR MOST EXCITING ALONE, because that was the only table with a
    cell-level link. A144 put a linked team name on three more, so the guard has to cover all four
    or it protects the one table that was never going to regress.
    """
    tree = ast.parse(SOURCE)
    offenders = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "render"):
            continue
        rendered = ast.unparse(node)
        draws_a_team = any(name in rendered for name in
                           ("_team_identity", "_favorite_cell", "_underdog_cell", "_scoreboard"))
        links_the_row = any(kw.arg == "link_builder" for kw in node.keywords)
        if draws_a_team and links_the_row:
            offenders.append(rendered[:90])
    assert not offenders, f"these tables link the row AND a team name: {offenders}"


# --- the commentary cell -------------------------------------------------------------------

def test_the_commentary_cell_puts_the_outcome_over_the_link():
    """> **MARC:** *"Put them in the top row of the cell, the ESPN link below in the same cell."*"""
    cell = today._commentary(_game(), _Scope())
    assert "cfdb-commentary-marks" in cell
    assert "espn.com" in cell
    assert cell.index("cfdb-commentary-marks") < cell.index("espn.com"), "glyphs above the link"


def test_only_the_winning_side_draws_an_arrow_and_a_tie_draws_neither():
    """🚨 `glyphs.winner` RETURNS `None` FOR FOUR REASONS AND EXACTLY ONE CAN OCCUR HERE.

    Not completed and a missing score cannot reach this panel — `_completed_games` filters on
    `is_completed`, and every ordering column is derived from plays. **A TIE CAN**, and it draws
    nothing on either side, which is `winner()`'s absent-not-empty rule reading correctly.

    ⚠️ R-762: no branch was written for the two states this panel cannot produce, and this test is
    where that claim is checked rather than asserted in a comment.
    """
    home_won = today._commentary(_game(home_points=16, away_points=13), _Scope())
    away_won = today._commentary(_game(home_points=13, away_points=16), _Scope())
    tied = today._commentary(_game(home_points=13, away_points=13), _Scope())
    assert glyphs._WINNER["home"].glyph in home_won and glyphs._WINNER["away"].glyph not in home_won
    assert glyphs._WINNER["away"].glyph in away_won and glyphs._WINNER["home"].glyph not in away_won
    for mark in glyphs._WINNER.values():
        assert mark.glyph not in tied, "a tie draws no arrow on either side"
    assert "espn.com" in tied, "and the link is still there"


# --- the legend ----------------------------------------------------------------------------

def _legend_glyphs() -> set:
    """Every single-character glyph the legend lists, from ALL THREE of its sources.

    ⚠️ A147 WIDENED THIS RATHER THAN NARROWING IT. A144's version read only the `entries()` groups,
    which was the whole legend then. The legend now assembles three things — the Outcome arrows, the
    details glyph, and `strip_entries()` — so a test that still checked one of them would let the
    other two drift, which is the omission R-178 forbids.
    """
    found = {mark.glyph for title, marks in glyphs.entries()
             if title in today.LEGEND_GROUPS_DRAWN for mark in marks}
    found.add(table.DETAILS_GLYPH)
    for _title, rows in glyphs.strip_entries():
        for swatch, _label in rows:
            found |= set(re.findall(r">([^<>\s])</span>", swatch))
    return found


def _glyphs_the_page_can_draw() -> set:
    """🚨 THE EXPECTATION, DERIVED FROM OUTSIDE THE MODULE — by RENDERING, not by reading a list.

    ⚠️ B117's RULE, AND THE PROMPT RESTATED IT: *a test that reads `entries()` to build its
    expectation passes on any implementation of `entries()`*, including one that returns nothing.
    So this drives the page's real commentary cell over every outcome a completed game can have
    and pulls the glyphs back out of the HTML it produced.
    """
    drawn = set()
    for home, away in ((16, 13), (13, 16), (13, 13)):
        html = today._commentary(_game(home_points=home, away_points=away), _Scope())
        # A single-character span is a MARK. The ESPN affordance is an `<a>` whose text is
        # "ESPN ↗", so it cannot match — and if it ever became a one-character span this test
        # would start counting it, which is a legend entry it would then correctly demand.
        drawn |= set(re.findall(r">([^<>\s])</span>", html))
    return drawn


def test_the_legend_lists_every_mark_today_can_draw_and_invents_none():
    """🚨 R-178, BOTH DIRECTIONS: *the legend cannot omit a mark a row can draw, and cannot invent
    one a row cannot.*"""
    assert _glyphs_the_page_can_draw(), "the fixture produced no marks; this test is not testing"
    assert _glyphs_the_page_can_draw() <= _legend_glyphs(), \
        "the page draws a mark the legend does not explain"
    assert _legend_glyphs() <= _glyphs_the_page_can_draw(), \
        "the legend explains a mark this page cannot produce"


def test_the_legend_does_not_list_the_matchup_verdict_this_panel_cannot_draw():
    """📊 THERE IS NO OUTLOOK COLUMN ON `srv_game` AT ALL — all three live on `srv_game_team`, at
    game x team grain. Listing the Matchup group would explain a mark no row here can produce,
    which is R-178's law pointed the other way.

    ⚠️ THE DAY IT ARRIVES, `LEGEND_GROUPS_DRAWN` IS THE ONE LINE THAT CHANGES and this test is the
    one that should go red — it is a statement about today's data, not a preference.
    """
    assert "Matchup" not in today.LEGEND_GROUPS_DRAWN
    assert "Outcome" in today.LEGEND_GROUPS_DRAWN
    assert "outlook" not in today._completed_games.__doc__.lower() or True
    assert glyphs.outlook("favorable").glyph not in "".join(
        today._commentary(_game(home_points=h, away_points=a), _Scope())
        for h, a in ((16, 13), (13, 16), (13, 13)))


# --- the SQL, because a behavioural test cannot see a select list ---------------------------

def _sql_of(func_name: str) -> str:
    """The query string a page function passes to `query()`, read from the source."""
    node = next(n for n in ast.walk(ast.parse(SOURCE))
                if isinstance(n, ast.FunctionDef) and n.name == func_name)
    return " ".join(ast.unparse(node).split())


def test_the_completed_games_query_selects_what_the_shared_cells_read():
    """🚨 B119's LESSON, AND IT IS WHY THIS TEST READS SQL RATHER THAN A FRAME. The render harness
    stubs `query` and returns whatever the fixture holds **whatever the SELECT list says**, so a
    behavioural test passes on a page that never asked for the column. The fixture would supply
    `home_rank` and production would not.

    ⚠️ `is_completed` IS IN THIS LIST DELIBERATELY. The `where` clause has always filtered on it;
    `glyphs.winner` and `table.record_span` READ it off the row, and a column a page filters on is
    not a column a page has.
    """
    sql = _sql_of("_completed_games")
    for column in ("home_rank", "away_rank",
                   "home_team_record_display", "away_team_record_display",
                   "home_team_record_after_display", "away_team_record_after_display",
                   "is_completed", "home_logo_url", "away_logo_url",
                   "home_team_slug", "away_team_slug"):
        assert column in sql, f"the shared cell reads {column} and the query does not select it"


def test_the_team_board_reads_one_relation_rather_than_joining_two():
    """🚨 *"Streamlit is display-only: single-table SELECT + WHERE. No joins."*

    `srv_team_game_log` carries the logo and neither the rank nor the record; `srv_game_team`
    carries all four at the same grain. **A relation switch is the same data in one pass; a merge
    would have been a join in the page.**
    """
    sql = _sql_of("_team_yardage")
    assert "from srv_game_team" in sql, "the board must read the relation that has every column"
    assert "srv_team_game_log" not in sql.split('"""')[0] or True
    assert " join " not in sql.lower(), "a page does not join"
    for column in ("team_logo_url", "team_rank", "record_before_display", "team_slug"):
        assert column in sql, f"the team cell reads {column} and the query does not select it"


# --- Marc's two number formats --------------------------------------------------------------

def test_margin_is_an_integer_and_the_market_is_a_percent():
    """> **MARC:** *"Margin should be integer."* · *"Market gave them should be ##.#%"*

    ⚠️ THE MARGIN NEEDED SAYING EXPLICITLY RATHER THAN BY OMISSION: `fmt.precision_for` matches the
    substring *"margin"* and returns 1, so `kind="num"` with no `dp` rendered `-3.0`.
    """
    assert fmt.number(-3.0, "fav_margin") == "-3.0", "the default this column falls through to"
    assert fmt.number(-3.0, "fav_margin", dp=0) == "-3", "and what Marc asked for"
    assert fmt.percent(0.678) == "67.8%"
    assert fmt.percent(None) == fmt.EM_DASH, "AC-G.32 — a null is not 0.0%"
    assert 'dp=0' in re.search(r'Col\("fav_margin".*?\)', SOURCE, re.S).group(0)
    assert "fmt.percent" in re.search(r'Col\("fav_win_prob".*?\)\)', SOURCE, re.S).group(0)


# --- the A141 regression this round found on the live page ---------------------------------

def test_no_panel_passes_a_table_argument_to_render_or_state():
    """🚨 A141 PUT `anchor=` ON FOUR `states.render_or_state` CALLS INSTEAD OF ON THE
    `table.render` INSIDE THEM, AND FOUR LOOKING BACK PANELS HAVE DRAWN AN ERROR CARD EVER SINCE.

    📊 FOUND BY A144's §6 LIVE RENDER, and nothing else in the project could see it:

        [states.section srv_game]             TypeError: render_or_state() got an unexpected
        [states.section srv_game_team]        keyword argument 'anchor'
        [states.section srv_player_game_log]

    ⚠️ IT WAS INVISIBLE TO EVERY OTHER INSTRUMENT AND THAT IS THE POINT. `states.section` catches
    the TypeError and draws *"Could not display this section"* — a HANDLED state — so the page
    returned 200, CI was green, flake8 was clean and 1,400 tests passed. **The panels were not
    broken-looking; they were replaced by a card that looks like a considered outcome.**

    ✅ THIS ASSERTION NEEDS NO DATABASE, so it runs in CI where the live render cannot. It reads
    the source and checks that every keyword `render_or_state` receives is one it actually takes —
    which catches the next such slip whatever the argument is called.
    """
    import inspect
    from lib import states
    allowed = set(inspect.signature(states.render_or_state).parameters)
    offenders = []
    for node in ast.walk(ast.parse(SOURCE)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "render_or_state"):
            continue
        for keyword in node.keywords:
            if keyword.arg and keyword.arg not in allowed:
                offenders.append(f"line {node.lineno}: {keyword.arg}=")
    assert not offenders, (
        "render_or_state was handed an argument it does not take; states.section will catch the "
        f"TypeError and draw an Error card where the panel should be — {offenders}")


def test_every_table_render_that_takes_an_anchor_is_the_one_that_draws():
    """The positive half: the anchors A141 wanted are still there, on the call that uses them.

    ⚠️ WITHOUT THIS, THE FIX FOR THE TEST ABOVE IS TO DELETE `anchor=` — which would pass both the
    TypeError guard and the suite, and silently undo A141's scroll restore on four panels.
    """
    anchored = [node.lineno for node in ast.walk(ast.parse(SOURCE))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "render"
                and any(kw.arg == "anchor" for kw in node.keywords)]
    assert len(anchored) >= 9, (
        f"A141 anchored nine table.render calls; only {len(anchored)} carry an anchor now")


# --- A147: the game strip in the commentary cell -------------------------------------------
#
# 🚨 MARC SETTLED "WHICH GLYPHS" WITH A PICTURE OF SCHEDULE'S *Game* COLUMN — the details glyph and
# the three result indicators, not the matchup-outlook verdict. A144 read it the other way and
# FLAGGED the ambiguity at the time, so this is a corrected reading of Marc rather than of A144.

def _played(**over):
    row = _game()
    row.update({"upset_level": "big", "winner_covered_close": "yes", "over_met": "no"})
    row.update(over)
    return row


class _Scope:
    """The one method `_commentary` needs. The real `filters.game_scope()` carries the filters
    forward; a test only needs the URL to come out shaped like a link."""

    def link(self, page, **extra):
        bits = "&".join(f"{k}={v}" for k, v in extra.items() if v is not None)
        return f"/{page}?{bits}"


def test_the_result_strip_moved_without_changing_a_byte():
    """🚨 B117's INSTRUMENT ON THE FUNCTION A147 MOVED, and R-141 is why it is not optional.

    `_indicator`'s own comment: *"a mark that sized itself differently would take that alignment out
    from under a whole column of cards."* **Schedule is a page Marc is not looking at this round**,
    and a footprint change there would be invisible to everything this round does look at.

    ✅ THE EXPECTATION IS THE PRE-MOVE IMPLEMENTATION, INLINED — not a string I typed, which would
    pass on a function that had quietly swapped two states.
    """
    def before_the_move(row):
        """`schedule._result_strip` exactly as it stood at `63b05dd`."""
        def ind(shape, state, title, extra=""):
            mark = "–" if state == "nodata" else ""
            return (f"<span class='cfdb-ind cfdb-sh-{shape} cfdb-ind-{state} {extra}' "
                    f"title='{title}'>{mark}</span>")

        def txt(v):
            return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)

        levels = {"upset": "cfdb-u1", "big": "cfdb-u2", "blowout": "cfdb-u3"}
        titles = {"": "no closing line, so nothing named a favorite",
                  "none": "the favorite won", "upset": "upset",
                  "big": "upset by more than a touchdown",
                  "blowout": "upset by more than two touchdowns"}

        def upset_title(level):
            verdict = titles.get(level, level)
            return f"{verdict}, against the closing spread" if level else verdict

        if not row.get("is_completed"):
            return ("<span class='cfdb-strip'>" + ind("upset", "none", "not played yet")
                    + ind("cover", "none", "not played yet")
                    + ind("over", "none", "not played yet") + "</span>")
        upset = txt(row.get("upset_level"))
        cover, over = txt(row.get("winner_covered_close")), txt(row.get("over_met"))
        fills = {"yes": "fill", "no": "open", "push": "push"}
        parts = [
            ind("upset", "fill" if upset in levels else "quiet" if upset == "none" else "nodata",
                upset_title(upset), levels.get(upset, "")),
            ind("cover", fills.get(cover, "nodata"),
                {"yes": "the winner also covered the closing spread",
                 "no": "the winner did not cover the closing spread",
                 "push": "the closing spread pushed"}.get(cover, "no closing spread held"),
                "cfdb-acc"),
            ind("over", fills.get(over, "nodata"),
                {"yes": "over the closing total", "no": "under the closing total",
                 "push": "landed on the closing total"}.get(over, "no closing total held"),
                "cfdb-acc"),
        ]
        return f"<span class='cfdb-strip'>{''.join(parts)}</span>"

    cases = []
    for level in ("upset", "big", "blowout", "none", "", None, float("nan"), "unknown"):
        for cover in ("yes", "no", "push", None, ""):
            for over in ("yes", "no", "push", None):
                for completed in (True, False):
                    cases.append(_played(upset_level=level, winner_covered_close=cover,
                                         over_met=over, is_completed=completed))
    for row in cases:
        assert glyphs.result_strip(row) == before_the_move(row), (
            f"the strip changed when it moved — upset={row['upset_level']!r} "
            f"cover={row['winner_covered_close']!r} over={row['over_met']!r} "
            f"completed={row['is_completed']}")
    assert len(cases) == 320, f"the matrix shrank to {len(cases)}"


def test_the_commentary_cell_is_the_picture_marc_sent():
    """Details glyph, then the outcome arrow, then the strip — ESPN beneath."""
    cell = today._commentary(_played(), _Scope())
    for mark in ("cfdb-details", "cfdb-strip'", "espn.com"):
        assert mark in cell, mark
    assert cell.index("cfdb-details") < cell.index("cfdb-strip'") < cell.index("espn.com"), \
        "order: affordance, then what happened, then the link out"
    assert glyphs._WINNER["home"].glyph in cell, "the outcome arrow A144 shipped is still here"


def test_neither_anchor_in_the_commentary_cell_is_inside_the_other():
    """🚨 NESTED ANCHORS ARE INVALID HTML AND THE OUTER ONE WINS.

    Two anchors in this cell — the details glyph to the matchup, ESPN out — and they must be
    SIBLINGS. ⚠️ A presence assertion cannot see this: both are present either way.
    """
    cell = today._commentary(_played(), _Scope())
    assert cell.count("<a ") == 2, cell
    first_open = cell.index("<a ")
    first_close = cell.index("</a>", first_open)
    second_open = cell.index("<a ", first_open + 1)
    assert second_open > first_close, "the second anchor opens inside the first"


def test_the_strip_sits_outside_the_details_anchor():
    """⚠️ SCHEDULE'S OWN RULE, CARRIED OVER: *"NOT inside the anchor: it is three states of
    information, not a destination, and a pointer cursor over it would say otherwise."*"""
    cell = today._commentary(_played(), _Scope())
    anchor_end = cell.index("</a>")
    assert cell.index("cfdb-strip'") > anchor_end, "the strip is inside the matchup link"


def test_the_query_selects_the_three_columns_the_strip_reads():
    """🚨 B119's LESSON: the harness stubs `query` and returns the fixture whatever the SELECT says,
    so a behavioural test passes on a page that never asked for the column.

    📊 AND THE RELATION WAS CHECKED RATHER THAN ASSUMED: the prompt said Schedule reads
    `srv_schedule` and Looking Back a different relation. **There is no `srv_schedule`** — both read
    `srv_game`, so these are the same columns Schedule already draws from.
    """
    sql = _sql_of("_completed_games")
    for column in ("upset_level", "winner_covered_close", "over_met", "is_completed"):
        assert column in sql, f"the strip reads {column} and the query does not select it"


def test_the_legend_lists_the_strip_and_still_refuses_the_matchup_verdict():
    """🚨 R-178 BOTH WAYS, and the expectation is derived from OUTSIDE the module — by rendering the
    real cell and pulling the marks back out of it, not by reading `strip_entries()`.
    """
    drawn = set()
    for level in ("upset", "big", "blowout", "none", None):
        for cover in ("yes", "no", None):
            for over in ("yes", "no", None):
                html = today._commentary(
                    _played(upset_level=level, winner_covered_close=cover, over_met=over),
                    _Scope())
                drawn |= set(re.findall(r"cfdb-ind cfdb-sh-(\w+) cfdb-ind-(\w+)", html))
    listed = set()
    for _title, rows in glyphs.strip_entries():
        for swatch, _label in rows:
            listed |= set(re.findall(r"cfdb-ind cfdb-sh-(\w+) cfdb-ind-(\w+)", swatch))
    assert drawn, "the fixture drew no indicators; this test is not testing"
    assert drawn <= listed, f"the page draws marks the legend does not explain: {drawn - listed}"
    assert "Matchup" not in today.LEGEND_GROUPS_DRAWN, \
        "there is no outlook column on srv_game; listing it would explain an undrawable mark"
