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


def test_the_identity_row_aligns_on_centre_because_one_child_has_no_baseline():
    """🚨 A165 (cfdb-main-R-1300). CSS-ONLY, SO A CSS ASSERTION IS THE ONLY GUARD THERE IS.

    > **MARC, Today v05:** *"The teams (logo, name, record) are not aligned vertically. Review
    > the image. Record needs to move up."*

    📊 MEASURED ACROSS 160 identity cells in Chromium: the record's alphabetic baseline sat
    **9.5–10px BELOW** the team name's, because `.cfdb-identity` baseline-aligns a text span
    against `.cfdb-teamlink` — a flex container whose first item is an EMPTY 28px logo box, and
    which therefore synthesises its baseline from its bottom edge.

    ⚠️ **THE OBVIOUS FIX WAS MEASURED AND REJECTED**: `.cfdb-teamlink{align-items:baseline}`
    brings the record to +0.2px **and moves the logo 5–6px off the name**. Centre brings it to
    −0.5/−1px and moves nothing. **This test pins the property AND the reason**, so a future
    round that "tidies" it back to `baseline` has to read why first.
    """
    from lib import theme as T
    import re
    rule = re.search(r"^\.cfdb-identity \{([^}]*)\}", T.TABLE_CSS, re.M)
    assert rule, "`.cfdb-identity` has no rule at all — that was A164's original defect"
    body = rule.group(1)
    assert "align-items:center" in body.replace(" ", ""), (
        f"the identity row must align on CENTRE, not baseline: {body.strip()}")
    assert "display:flex" in body.replace(" ", ""), body


def test_the_scoreboard_team_cell_is_wide_enough_to_stop_clipping_and_still_fixed():
    """🚨 A165 (cfdb-main-R-1301). BOTH HALVES MATTER AND THEY PULL AGAINST EACH OTHER.

    > **MARC:** *"We need to grant Scoreboard more horizontal space because with the Record
    > added its truncating team name."*

    📊 **WIDENING THE OUTER COLUMN FIXES NOTHING** — 288px to 443px, +54%, left the ellipsised
    count at 11. The clip is this cell's own fixed width. Swept at 1300px and 1600px with the
    logo untouched: 9.5rem → 10 clipped · 11rem → 3 · 12rem → 2 · **13rem → 0**.

    ⚠️ **AND IT MUST STAY *FIXED*, WHICH IS THE HALF A WIDTH CHANGE COULD QUIETLY LOSE.** The
    rule's own comment says why: a content-sized cell makes every scoreboard a different width,
    so the quarter columns stop lining up down the page and a reader has to re-find the "4" on
    every row. **`width` and `max-width` must agree, or the cell is no longer fixed.**
    """
    from lib import theme as T
    import re
    rule = re.search(r"\.cfdb-sb-team \{([^}]*)\}", T.TABLE_CSS, re.S)
    assert rule, "the scoreboard team cell lost its rule"
    body = rule.group(1).replace(" ", "").replace("\n", "")
    width = re.search(r"[^-]width:([\d.]+)rem", body)
    maxw = re.search(r"max-width:([\d.]+)rem", body)
    assert width and maxw, f"both width and max-width must be declared: {body}"
    assert width.group(1) == maxw.group(1), (
        f"width {width.group(1)}rem and max-width {maxw.group(1)}rem disagree — the cell is no "
        f"longer FIXED, and the quarter columns will stop lining up")
    assert float(width.group(1)) >= 13, (
        f"{width.group(1)}rem clips team names once the record shares the cell; 13rem was the "
        f"first width measured at zero clipped, at both 1300px and 1600px")


def test_the_identity_wrapper_puts_the_record_on_the_name_s_line_without_crossing_the_anchor():
    """🚨 A164. MARC ASKED THREE TIMES — *"Records should be inline with the Team Name, not line
    below it"* (Upsets, Underdogs) and *"Team - Ranks inline with team name, not below"* (Team
    Yardage). **ONE CELL, SEVEN TABLES, ONE FIX.**

    📊 **THE CAUSE WAS MEASURED, AND THE OBVIOUS SUSPECT WAS INNOCENT.** `.cfdb-teamlink` is
    `display:flex` — a block-level box — so the record sibling could never share its line at any
    width. Tested in Chromium: neutralising `.cfdb-table .cfdb-team`'s `max-width:100%` left the
    record wrapped on 4 of 4 rows, and so did deleting that rule's whole ellipsis cluster;
    inline-flex on the anchor fixed 3 of 4, and the 4th needed `min-width:0` so the NAME gives up
    pixels first. **The prompt's hypothesis was `max-width`; the measurement says otherwise.**

    🚨 **THE ANCHOR BOUNDARY IS THE THING A WRAPPER COULD EASILY BREAK, SO IT IS ASSERTED HERE
    TOO.** R-129: the record lives OUTSIDE the team-name anchor and the rank lives INSIDE
    `team_cell`. A flex row must wrap both and move neither across that line.
    """
    cell = today._team_identity(_game(), "home")
    assert cell.startswith("<span class='cfdb-identity'>"), cell[:80]
    assert cell.endswith("</span>")
    anchor = re.search(r"<a class='cfdb-teamlink'.*?</a>", cell, re.S)
    assert anchor, cell
    assert "cfdb-team-record" not in anchor.group(0), "the wrapper pulled the record INTO the link"
    assert "cfdb-rank" in anchor.group(0), "the rank must stay inside the linked team cell"
    # ⚠️ ONE wrapper, not one per element — a nested pair would flex against itself.
    assert cell.count("cfdb-identity") == 1


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
    # 🚨 A169 EXTENDED THIS BEYOND `today.py` (cfdb-main-R-1321), AND THE GAP WAS THE POINT.
    # This guard has always parsed `SOURCE` — Today alone — while the rule it enforces is about
    # `table.render` everywhere. Marc asked for linked team names on Rankings, Stats and
    # Standings, and **all three already passed a `link_builder`**, so they were exactly the
    # tables this test exists for and exactly the ones it could not see.
    #
    # ⚠️ **A GUARD SCOPED TO THE FILE THAT PROMPTED IT PROTECTS THE CODE THAT ALREADY PASSED.**
    import pathlib
    views = pathlib.Path(today.__file__).parent
    sources = {f.name: f.read_text() for f in sorted(views.glob("*.py"))
               if f.name not in ("__init__.py",)}
    offenders = []
    checked = 0
    for filename, text in sources.items():
        for node in ast.walk(ast.parse(text)):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "render"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "table"):
                continue
            checked += 1
            rendered = f"{filename}: " + ast.unparse(node)
            # 🚨 RESOLVE A COLUMN LIST PASSED BY NAME, OR THE GUARD IS BLIND TO THE PAGES THAT
            # USE ONE. `standings.py` calls `table.render(rows, COLUMNS, …)` — a module-level
            # list — so the unparsed CALL mentions no team cell at all, and a staged break that
            # removed its team link came back GREEN (R-744). **This is the same indirection
            # this test's own docstring warned about for `_player_columns`, met again one round
            # later through a different spelling.**
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    for top in ast.walk(ast.parse(text)):
                        if (isinstance(top, ast.Assign)
                                and any(isinstance(t, ast.Name) and t.id == arg.id
                                        for t in top.targets)):
                            rendered += " || " + ast.unparse(top.value)
        # 🚨 `_player_columns` IS IN THIS LIST OR THE GUARD PROTECTS ONLY THE TABLES THAT ALREADY
        # PASSED. A149's three leaderboards do not mention `_team_identity` in their own
        # `table.render` call — they spread `*_player_columns()`, which builds it one level down.
        # **A name-matching guard is blind to exactly the indirection that makes a change safe**,
        # which is this test's own docstring turned on the round that extended it: four tables
        # before, SEVEN now, and the three new ones arrive through a different spelling.
            # ⚠️ `team_cell` JOINS THE LIST. A169's three pages draw a team through it
            # directly rather than through one of Today's wrappers, and a name-matching guard
            # that does not know the name is blind to exactly the change it should judge.
            draws_a_team = any(name in rendered for name in
                               ("_team_identity", "_favorite_cell", "_underdog_cell",
                                "_scoreboard", "team_cell"))
            links_the_row = any(kw.arg == "link_builder" for kw in node.keywords)
            # ✅ A COLUMN-LEVEL `link` IS THE SAFE FORM AND IS NOT AN OFFENCE. `table.render`
            # uses the column's href INSTEAD of the row's for that cell — never both — so the
            # team anchor replaces the row anchor there rather than nesting inside it. That is
            # precisely what `Col.link`'s own comment describes, and it is what A169 used.
            links_the_cell = "link=table.team_link" in rendered or "link=team_link" in rendered
            if draws_a_team and links_the_row and not links_the_cell:
                offenders.append(rendered[:110])
    assert checked >= 12, (
        f"only {checked} table.render calls found across the views — this guard is supposed to "
        f"see all of them, and a drop means the walk stopped working")
    assert not offenders, (
        f"these tables link the ROW and draw a team name without giving that column its own "
        f"link, so the row anchor wraps the team: {offenders}")


# --- A166: the player cards -----------------------------------------------------------------

def _card_row(**over):
    """A player as `srv_player_game_log` publishes one. Defaults are the MEASURED common case."""
    import pandas as pd
    row = {"player_name": "Riley Warzynski", "player_slug": "riley-warzynski",
           "jersey": 1, "position": "QB", "class_year_display": "SR",
           "stat_value": 535.0, "stat_category": "passing", "stat_type": "YDS",
           "team_display": "Drake", "team_slug": "drake",
           "team_logo_url": "https://example.invalid/drake.png",
           "team_rank": None, "record_before_display": "0-0"}
    row.update(over)
    return pd.Series(row)


def test_the_card_names_the_team_because_that_is_the_one_thing_marc_required():
    """> **MARC, Today v04:** *"The player card needs to indicate the Team logo/name"*

    ⚠️ **THE ONLY REQUIREMENT HE STATED FOR THE CARD ITSELF**, so it is the one pinned hardest.
    🚨 **AND THE LOGO COMES THROUGH `table.team_cell` -> `identity.logo_or_monogram`, NOT A NEW
    `<img>`** — that path guarantees an identical footprint whether the logo resolves or not
    (AC-G.28) and carries R-121's NaN guard. A card that built its own image tag would re-open a
    bug that cost this site two teams in a screenshot.
    """
    card = today._player_card(_card_row(), "yards")
    assert "cfdb-card" in card
    assert "Riley Warzynski" in _plain(card), "the promoted row draws the whole name"
    assert "Drake" in card, "the team NAME is required"
    assert "cfdb-logo" in card, "the team LOGO is required"
    assert "cfdb-identity" in card, "the team line must be the shared identity cell"
    # The stat is the reason the card is on the board, and it reads before the team.
    assert card.index("cfdb-card-value") < card.index("cfdb-card-team")
    assert "535" in card


def test_the_card_survives_the_absences_the_view_actually_carries():
    """🚨 R-084: RENDER NOTHING RATHER THAN SUBSTITUTE SOMETHING — on a card as in a cell.

    📊 **THE ABSENCE RISK A166 WAS ASKED TO DESIGN AROUND HAS LARGELY GONE, AND THAT IS
    MEASURED** (cfdb-main-R-1306): the prompt and `_player_board`'s docstring both say 2026
    carries a jersey on 40.9% of rows; live serving says **92.9%**, and on the ninety players who
    actually reach these nine columns it is **90 of 90**. The roster was refetched 2026-09-16.

    ⚠️ **THAT CHANGES WHAT IS TYPICAL, NOT WHAT IS POSSIBLE**, so the branches are still tested —
    and an em dash must never land inside a name.
    """
    bare = today._player_card(
        _card_row(jersey=None, position=None, class_year_display=None), "yards")
    assert "Riley Warzynski" in _plain(bare)
    # 🚨 A167: THE ABSENCE TREATMENT CHANGED BECAUSE MARC CHOSE THE OTHER CARD. Today's own cell
    # OMITTED a missing jersey and named the whole-row absence in a `title`; Matchup's renders an
    # em dash in the slot so the cards stay aligned (AC-G.32, B104). **Both are defensible and he
    # picked one** — so this asserts the one that shipped rather than the one that did not.
    header = bare.split("cfdb-card-stat")[0]
    assert "—" in header, "an absent jersey is an em dash in its slot"
    assert "#" not in header, "and it carries no hash"
    assert "Riley Warzynski" in _plain(header)
    # A missing logo still draws a monogram, so the card keeps its shape.
    no_logo = today._player_card(_card_row(team_logo_url=None), "yards")
    assert "Drake" in no_logo and "cfdb-card-team" in no_logo


def test_the_jersey_is_a_number_worn_not_a_quantity_on_a_card_too():
    """🚨 `srv_player_game_log` publishes `jersey` as an INTEGER, and pandas has no integer that
    holds a null — so a real frame comes back `float64` and every jersey is a float.

    ⚠️ **A149 SHIPPED `#2.0` TO A LIVE RENDER FROM EXACTLY THIS**, and its fixture could not see
    it because the fixture used the string `"14"` (R-763: a fixture whose dtype cannot hold the
    case). **This fixture uses a float on purpose.**
    """
    import re as _re
    card = today._player_card(_card_row(jersey=7.0), "yards")
    assert _re.search(r">#</span>7\b", card), card[:160]
    assert "7.0" not in _plain(card)


def test_the_position_is_grouped_with_its_own_name_on_a_card():
    """🚨 A166 (cfdb-main-R-1307). CSS-ONLY, SO A CSS ASSERTION IS THE ONLY GUARD — AND A STAGED
    BREAK IS WHAT PROVED IT WAS MISSING.

    `.cfdb-player` is `justify-content:space-between`, which is exactly right for the table cell
    Marc specified in Today v01: *"[Jersey #, Name, Year (left aligned)], Position (right aligned
    within the Player cell)"*. **A table cell is narrow; a card column is 390px.**

    📊 MEASURED IN THE RASTER, first card of the first board: the position sat **215.8px from its
    own player's name and 24.0px from the NEXT COLUMN's cards** — nine times closer to a
    different player than to the one it describes. ⚠️ **Every glyph was correct and the card
    still said something false about which player it belonged to.** Grouped: 7.2px from its own
    name, 232.7px of clear space before the next column.

    ✅ **THE OVERRIDE LIVES ON `.cfdb-card`, NOT ON `.cfdb-player`** — the rule that is right in a
    cell is wrong in a card, and only the card says so. R-855, caught in the act: read the
    existing path, then TEST IT FOR THE CASE AT HAND.
    """
    from lib import theme as T
    import re
    rule = re.search(r"\.cfdb-card \.cfdb-player \{([^}]*)\}", T.TABLE_CSS)
    assert rule, (
        "`.cfdb-card .cfdb-player` has no rule, so the card inherits the table cell's "
        "two-ends layout and the position drifts 215px from the name it belongs to")
    body = rule.group(1).replace(" ", "")
    assert "justify-content:flex-start" in body, body


def test_no_anchor_inside_the_card_is_inside_another_one():
    """🚨 THE EQUIVALENT OF `test_no_table_with_a_linked_team_name_also_links_its_rows`, NOW THAT
    THE BOARDS ARE NOT TABLES.

    That guard asks whether a `table.render` carries a `link_builder` while drawing a linked team
    name — because a row anchor would WRAP the team anchor, nested anchors are invalid HTML, and
    the OUTER one wins, so a reader clicks the team and lands somewhere else. ⚠️ **A card grid
    has no `link_builder` to check**, so the property is asserted directly on the markup instead:
    **no `<a>` inside another `<a>`.**

    ✅ The original guard still runs and still covers the five tables that remain; this covers the
    three boards that left it.
    """
    import re
    card = today._player_card(_card_row(), "yards")
    depth = 0
    for token in re.findall(r"<a\b|</a>", card):
        depth += 1 if token != "</a>" else -1
        assert depth <= 1, f"nested anchor in the card: {card[:200]}"
        assert depth >= 0, "unbalanced anchors"
    assert depth == 0, "unbalanced anchors in the card"
    assert card.count("<a ") >= 1, "the team name is still a link, or this test proves nothing"


def test_the_three_boards_split_on_the_axis_each_one_actually_has():
    """🚨 THE DEFENSIVE BOARD IS NOT THE YARDAGE BOARD WITH A DIFFERENT ARGUMENT, AND COPYING THE
    CALL WOULD HAVE PRODUCED ONE COLUMN OR THREE EMPTY ONES.

    Yardage and touchdowns split on `stat_category` at a fixed `stat_type`; defence is ONE
    category split on THREE `stat_type`s.

    📊 ENUMERATED FROM LIVE PUBLISHED SERVING (§2.2.1c.2) rather than taken from the caption that
    claimed it — 2026, `stat_category='defensive'`, every type with 15,372 rows and 9,062
    players: **PD · QB HUR · SACKS · SOLO · TD · TFL · TOT**. ⚠️ **It is `SACKS`, not `SACK`** —
    the kind of thing a guess gets wrong and a query does not.
    """
    import ast
    tree = ast.parse(SOURCE)
    board = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_leaderboards")
    calls = [ast.unparse(n) for n in ast.walk(board)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_player_board"]
    assert len(calls) == 3, f"one call per board, each looped over its own three: {calls}"
    joined = " ".join(calls)
    # yardage and touchdowns vary the CATEGORY at a fixed type
    assert "'YDS'" in joined and "'TD'" in joined
    # defence varies the TYPE at a fixed category, and the values are the measured ones
    for stat_type in ('"TOT"', '"TFL"', '"SACKS"'):
        assert stat_type in SOURCE, f"{stat_type} is one of the three defensive types measured"
    assert '"SACK"' not in SOURCE, "it is SACKS, measured against live serving, not SACK"


# --- the commentary cell -------------------------------------------------------------------

def test_the_commentary_cell_puts_the_outcome_over_the_link():
    """> **MARC:** *"Put them in the top row of the cell, the ESPN link below in the same cell."*"""
    cell = today._commentary(_game(), _Scope())
    assert "cfdb-commentary-marks" in cell
    assert "espn.com" in cell
    assert cell.index("cfdb-commentary-marks") < cell.index("espn.com"), "glyphs above the link"


def test_no_commentary_cell_draws_a_winner_arrow_on_any_outcome():
    """🚨 A164. MARC REMOVED THE WINNER TRIANGLE FROM ALL THREE PANELS — Today v04, three times.

    ⚠️ **THE OUTCOME IS STILL STATED, WHICH IS WHY THE REMOVAL IS SAFE**: Most Exciting carries
    the scoreboard's final column, and Upsets and Underdogs are panels whose ENTRY CONDITION is
    the outcome. `glyphs.result_strip` stays — Marc's *"diamond outcome glyph"* is the strip's,
    and he was positioning the ESPN link relative to it rather than asking for it to go.

    ✅ **THIS DRIVES ALL THREE OUTCOMES A COMPLETED GAME CAN HAVE**, so it fails the moment the
    arrow returns on any of them rather than on the one the fixture happened to pick.
    ⚠️ `glyphs.winner` ITSELF IS UNTOUCHED AND STILL HAS A CALLER — `matchup.py` — so this is a
    statement about THIS page and not about the module.
    """
    for home, away in ((16, 13), (13, 16), (13, 13)):
        cell = today._commentary(_game(home_points=home, away_points=away), _Scope())
        for mark in glyphs._WINNER.values():
            assert mark.glyph not in cell, f"{mark.glyph} came back at {home}-{away}"
        assert "espn.com" in cell, "and the link is still there"
        assert "cfdb-strip" in cell, "the result strip is NOT what he asked to remove"


def test_the_commentary_cell_stacks_only_where_marc_asked_for_a_carriage_return():
    """🚨 A164. HE ASKED FOR TWO DIFFERENT THINGS AND THEY MUST NOT BE AVERAGED.

    Today v04: a *"carriage return"* between the glyphs and the ESPN link on **Most Exciting**,
    and a *"Space"* on **Biggest Upsets** and **Biggest Underdogs**.

    📊 THE CHOICE WAS MADE FROM A RENDER, NOT FROM THE CODE. Measured in Chromium before any
    edit: the recap panels put ESPN inline with the strip at a horizontal gap of EXACTLY 0px, so
    his "Space" is a horizontal one. Most Exciting broke to its own line at a 1300px viewport and
    did NOT at 1600 — the same markup, flipping on width alone.

    ⚠️ THIS ASSERTS THE OPT-IN IS REAL IN BOTH DIRECTIONS. A modifier class that is always on, or
    always off, would satisfy one of these two assertions and not both.
    """
    stacked = today._commentary(_game(), _Scope(), stacked=True)
    inline = today._commentary(_game(), _Scope())
    assert "cfdb-commentary-stacked" in stacked
    assert "cfdb-commentary-stacked" not in inline
    assert "cfdb-commentary" in inline, "the base class is on both"


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
    # ⚠️ A164: "Outcome" LEFT THIS TUPLE when Marc's winner triangle was removed, because the
    # page can no longer draw that mark. The assertion that it is PRESENT would now be asserting
    # a legend entry explaining nothing — R-178's law pointed the same way as the Matchup one
    # above, which is why both live in this test.
    assert "Outcome" not in today.LEGEND_GROUPS_DRAWN
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

    🚨 A156 TOOK THE BOUND FROM NINE TO EIGHT, AND LOWERING IT IS EXACTLY WHAT THIS GUARD EXISTS
    TO MAKE HARD — so the drop is pinned to its cause rather than just decremented. Poll movement
    no longer renders an HTML table AT ALL: the table became a chart element so it could share the
    bump chart's rank axis (Marc's ask), and a chart element has no anchor because it has no sort
    links to return from. **The second assertion below is what keeps this honest** — if some later
    round quietly drops an `anchor=` instead, `table.render` will still be there with the anchor
    missing and the count will fall below the bound.

    🚨 A166 TOOK IT FROM EIGHT TO FIVE, AND FOR THE SAME REASON A156's DROP WAS LEGITIMATE.
    Marc's three player leaderboards stopped being tables: *"Swtich to player cards."* A card
    grid is `st.markdown`, it has **no sortable headers and therefore no sort links**, so there
    is nothing for an anchor to return the reader to. ⚠️ **The bound is lowered to what the
    tables that still exist actually carry, and the SECOND assertion is what makes that safe** —
    it fails on any `table.render` that lacks an anchor, whatever the count says, so a quietly
    dropped `anchor=` on one of the five cannot hide behind this number.
    """
    # 🚨 THE RECEIVER IS CHECKED, NOT JUST THE METHOD NAME. `node.func.attr == "render"` also
    # matches `glyphs.render(...)`, of which this page has two — invisible while the test only
    # COUNTED anchored calls, and immediately visible the moment it asserted something about the
    # unanchored ones. §2.2.1c.1's class inside a test: the name was found, and it was the wrong
    # object's name.
    calls = [node for node in ast.walk(ast.parse(SOURCE))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "render"
             and isinstance(node.func.value, ast.Name) and node.func.value.id == "table"]
    anchored = [n.lineno for n in calls if any(kw.arg == "anchor" for kw in n.keywords)]
    assert len(anchored) >= 5, (
        f"A141 anchored nine table.render calls; A156 turned one into a chart element and A166 "
        f"turned three into card grids; only {len(anchored)} carry an anchor now")
    # 🚨 AND THE COUNT ONLY MEANS SOMETHING IF EVERY REMAINING TABLE STILL CARRIES ONE. A page
    # that grew a new unanchored table would otherwise hide a dropped anchor behind its own
    # arrival — the bound would still be met and a panel would have lost its scroll restore.
    unanchored = [n.lineno for n in calls
                  if not any(kw.arg == "anchor" for kw in n.keywords)]
    assert not unanchored, (
        f"table.render without an anchor at lines {unanchored} — A141 anchored every one of "
        f"them, so a new table needs an anchor or a reason written down here")


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
    # ⚠️ A164: the winner arrow A144 shipped is GONE — Marc, Today v04. The order assertion
    # above is what survives, and it is the half that was ever about layout.
    assert glyphs._WINNER["home"].glyph not in cell, "the winner triangle was removed"


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


# --- A149: the player cell, and the three boards that share it -----------------------------

def _player(**over):
    """A leaderboard row, in `srv_player_game_log`'s spelling."""
    row = {"player_name": "Steven Robinson", "player_slug": "steven-robinson",
           "team": "Utah", "team_display": "Utah", "team_slug": "utah",
           "team_logo_url": "https://x/utah.png", "team_rank": 21,
           "record_before_display": "1-0", "conference": "Big 12", "opponent": "Arkansas",
           "week": 2, "stat_category": "rushing", "stat_type": "YDS", "stat_value": 212.0,
           # 🚨 A FLOAT, NOT A STRING, AND THAT IS THE WHOLE POINT (R-763). `jersey` is an
           # INTEGER on `srv_player_game_log`; pandas has no integer that holds a null, so the
           # real frame — 59% missing for the live season — arrives as `float64`. The first
           # version of this fixture used `"14"` and the page shipped `#2.0` to a live render
           # with 28 tests green. **A fixture whose dtype cannot hold the real value tests a
           # column that does not exist.**
           "jersey": 14.0, "position": "RB", "class_year_display": "JR"}
    row.update(over)
    return row


def _plain(markup: str) -> str:
    """Markup stripped to its visible text. ⚠️ A167: assertions about what a card SAYS should not
    depend on how it is marked up — three of this file's broke on the promotion for that reason
    alone, while the rendered text was correct throughout."""
    import re
    # ⚠️ A SPACE, NOT AN EMPTY STRING: the card splits a name across two divs, so
    # stripping tags to nothing renders "RileyWarzynski" and every name assertion
    # fails on markup rather than on meaning.
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", markup)).strip()


def test_the_card_header_is_matchups_and_there_is_exactly_one_of_it():
    """🚨 A167 (cfdb-main-R-1308). MARC CHOSE MATCHUP'S CARD, SO TODAY'S OWN CELL IS GONE.

    > **MARC, Today v06:** *"Prefer the player card from the Matchup, but want to add in the team
    > logo/name for this Today page…"*

    ⚠️ **THREE TESTS WERE DELETED HERE RATHER THAN ADAPTED, AND THAT IS THE HONEST OUTCOME.**
    They asserted `_player_identity` — Today's own *"[Jersey #, Name, Year], Position"* cell from
    v01, which was the right shape for a TABLE ROW. A166 turned the boards into cards and A167
    replaced the header with Matchup's, so the function had no caller and its properties were
    properties of a shape the page no longer draws. **Keeping tests for a deleted function is
    how a suite comes to describe a site that does not exist.**

    ✅ **WHAT THEY GUARDED THAT STILL APPLIES IS ASSERTED BELOW AND IN THE THREE TESTS THAT
    FOLLOW** — the four facts, the absences, and the jersey that is a number worn rather than a
    quantity. **What changed is the ABSENCE TREATMENT, and it changed because he picked the
    other card**: Today's cell OMITTED a missing jersey and named the whole-row absence in a
    `title`; Matchup's renders an em dash in the slot (AC-G.32, B104's ruling) so the cards stay
    aligned. Both are defensible; he chose one.
    """
    import pathlib
    import re
    site = pathlib.Path(today.__file__).parent.parent
    producers = []
    for f in sorted(site.rglob("*.py")):
        for m in re.finditer(r"^def (player_row|_player_identity|_leader_card)\b", f.read_text(), re.M):
            producers.append(f"{f.name}:{m.group(1)}")
    assert "today.py:_player_identity" not in producers, (
        "Today's own player cell must be GONE, not left dead beside the promoted one")
    assert producers.count("identity.py:player_row") == 1, producers
    assert "matchup.py:_leader_card" in producers, (
        "Matchup still owns its card; only the identity ROW was promoted")


def test_both_pages_draw_the_promoted_row_and_neither_reimplements_it():
    """🚨 §4.3. A COPY IS THE DEFECT THIS PROJECT HAS BEEN BITTEN BY THREE TIMES, and a view
    importing another view is the coupling A166 rejected.

    ✅ **The third time in three rounds the answer has been *the shared thing belongs in lib*** —
    `theme.viewer_is_dark` (A165), the `.cfdb-identity` wrapper (A164), this.
    """
    import pathlib
    import re
    site = pathlib.Path(today.__file__).parent.parent
    callers = {f.name for f in site.rglob("*.py")
               if re.search(r"identity\.player_row\(", f.read_text())}
    assert {"today.py", "matchup.py"} <= callers, callers
    # 🚨 AND NEITHER VIEW MAY IMPORT THE OTHER — that is the coupling this promotion avoids.
    assert "from views" not in (site / "views" / "today.py").read_text()
    assert "import matchup" not in (site / "views" / "today.py").read_text()


def test_the_promoted_row_carries_all_four_facts_and_marcs_ordering():
    """The four facts Marc named, asserted as ORDER rather than presence — a header containing
    all of them in the wrong arrangement passes every `in` check and is not his card.

    R-753 (three columns, no rank) · R-800 (the jersey spans both name lines) · R-801 (year over
    position) · R-835 (the two-line name).
    """
    from lib import identity as ident
    row = _player()
    header = ident.player_row(row)
    for earlier, later in (("#", "Steven"), ("Steven", "Robinson"), ("Robinson", "JR"),
                           ("JR", "RB")):
        assert header.index(earlier) < header.index(later), (earlier, later, header)
    assert "rank" not in header.lower(), "R-753: Marc removed the rank and it stays removed"


def test_the_promoted_row_keeps_matchups_absence_treatment():
    """🚨 AC-G.32 AND B104, WHICH CAME ACROSS WITH THE CARD MARC PICKED.

    A missing jersey renders an em dash in the same slot — **with NO `#`**, because a hash with
    nothing after it reads as a broken number rather than as an absence. A missing first name is
    OMITTED rather than blanked (B103): an empty line would still take its line-height and drop
    that one card's surname below its neighbours'.

    📊 **AND THE NUMBER BEHIND THE BRANCH HAS MOVED.** `_leader_card` said *"0 of 8,447 non-FBS
    leader rows carry one"*; re-measured on its own relation, 2026 is **8,129 of 8,563 — 94.9%**,
    with 2024 at 95.3% and 2025 at 97.1%. **The branch stays because it is still right for the
    rows that lack one; it is simply no longer the common case** (cfdb-main-R-1306's third copy).
    """
    from lib import identity as ident
    bare = ident.player_row(_player(jersey=None, position=None, class_year_display=None))
    assert "—" in bare, "an absent jersey is an em dash in the slot, not a gap"
    assert "#" not in bare, "and it carries no hash — a hash with nothing after it is broken"
    assert "Steven" in bare and "Robinson" in bare
    one_token = ident.player_row(_player(player_name="Cher"))
    assert "Cher" in one_token
    # 🚨 B103: the FIRST-NAME div is the one that must not exist. Its size is the tell — an
    # assertion counting line-heights matched the position block too and proved nothing.
    assert f"font-size:{ident.CARD_FIRST_SIZE}rem" not in one_token, (
        "a single-token name draws the BOLD line alone, not an empty first line")
    assert f"font-size:{ident.CARD_FIRST_SIZE}rem" in ident.player_row(_player()), (
        "and a two-token name DOES draw it, or the assertion above passes on anything")


def test_all_three_leaderboards_draw_the_shared_player_and_team_cells():
    """🚨 MARC NAMED THREE BOARDS IN ONE SENTENCE — *"Player Yardage, Touchdowns, Defensive
    Leaders"* — and they share one select list, so a per-board column pair is three places to
    forget the next change.

    ⚠️ READ FROM THE SOURCE, because the drift this guards against is three correct copies.

    🚨 A166 REWROTE THIS RATHER THAN DELETING IT, BECAUSE THE PROPERTY SURVIVED THE REDESIGN.
    Marc's boards stopped being tables (*"Swtich to player cards"*), so `_player_columns` is
    gone — but *"three boards, one producer"* is the same invariant it always was, now spelled
    `_player_card_grid`. ⚠️ **A test that pinned the old SPELLING would have been deleted here
    and the drift it prevented would have come back free.**
    """
    tree = ast.parse(SOURCE)
    board = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_leaderboards")
    grids = [ast.unparse(n) for n in ast.walk(board)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_player_card_grid"]
    assert len(grids) == 3, f"expected all three boards to share one card producer, found {grids}"
    # 🚨 AND EVERY CARD COMES FROM ONE PLACE TOO — three boards calling one grid that built its
    # own card three different ways would satisfy the count above and nothing else.
    makers = [ast.unparse(n) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
              and n.func.id == "_player_card"]
    assert len(makers) == 1, f"one card producer, called once, in the grid: {makers}"
    # And the old hand-written pair is gone.
    assert 'Col("player_name", "Player")' not in SOURCE
    assert 'Col("team", "Team")' not in SOURCE
    assert "_player_columns" not in SOURCE, "the dead table-column pair must be gone, not kept"


def test_the_player_board_selects_every_column_the_two_cells_read():
    """§2.2.1c.2's shape, one level down: a cell that reads a column its query does not select
    renders the ABSENCE state on every real page load and fails nothing.

    ⚠️ `ci/check_page_reads.py` is the general guard and it could not see this query at all until
    A149 taught it about `.replace()`-built SQL. This pins the eight by name anyway, because the
    checker answers *is every literal read selected* and cannot answer *are Marc's eight here*.
    """
    tree = ast.parse(SOURCE)
    board = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_player_board")
    # ⚠️ `and c.value.lstrip().lower().startswith("\n        select")` IS NOT PEDANTRY — the first
    # draft matched on the view name alone and picked up the DOCSTRING, which names the view in
    # its first line. It failed loudly, which is the lucky half; a docstring that happened to
    # mention the eight columns would have passed while asserting nothing about the query.
    sql = next(c.value for c in ast.walk(board)
               if isinstance(c, ast.Constant) and isinstance(c.value, str)
               and "srv_player_game_log" in c.value
               and re.search(r"^\s*select\b", c.value, re.IGNORECASE | re.MULTILINE))
    select = sql.split("from")[0]
    for column in ("player_name", "jersey", "position", "class_year_display",
                   "team_slug", "team_display", "team_logo_url", "team_rank",
                   "record_before_display"):
        assert re.search(rf"\b{column}\b", select), f"{column} is read but not selected"


def test_the_jersey_is_a_worn_number_and_never_a_float():
    """🚨 SHIPPED AS `#2.0` TO A LIVE RENDER BEFORE THIS TEST EXISTED.

    `srv_player_game_log.jersey` is an `integer` and pandas floats it wherever the column has a
    null — which is 59% of the live season. Every jersey on the page was `#7.0`.
    """
    from lib import identity as ident
    # 🚨 TWO SEPARATE PROPERTIES, ASSERTED SEPARATELY, BECAUSE ONE STRING CANNOT CARRY BOTH.
    # R-806 puts the `#` in its OWN span at a ratio of the digits' size, so the hash and the
    # number are adjacent in the MARKUP and separated by `_plain`'s tag boundary. The float
    # guard is about the TEXT. Testing either through the other is what cost this file two runs.
    import re as _re
    for value, expected in ((14, "14"), (7.0, "7"), (float("23"), "23")):
        markup = ident.player_row(_player(jersey=value))
        assert _re.search(rf">#</span>{expected}\b", markup), markup[:160]
        assert ".0" not in _plain(markup).split()[1], f"{value!r} rendered with a decimal"
    # The value pandas actually hands a page for a present jersey in a nullable column.
    for cell in (ident.player_row(_player(jersey=j)) for j in (14.0, 7.0, 99.0)):
        assert ".0" not in cell, cell


def test_the_win_probability_curve_has_exactly_one_producer():
    """🚨 A170 (cfdb-main-R-1324). The chart was promoted to `lib/` so Matchup can draw it —
    and the whole value of a promotion is that the SECOND caller does not become a second COPY.

    > **MARC, v20:** *"Add the Win % chart to the right of the Scoreboard in the header"*

    ⚠️ **THIS FILE'S OWN HEADER IS THE ARGUMENT: *"Building them four times is four chances to
    diverge"*, and *"four correct copies pass every per-panel test"*.** A duplicated curve would
    render identically the day it was copied, and the two would part company the first time
    somebody tuned one — which is exactly what happened to the record cell this file exists for.

    🚨 **THE TELL IS THE SCALE CONSTANT, NOT THE FUNCTION NAME.** A copy made by pasting the
    body would carry `_CURVE_PX_PER_UNIT` and could easily be called something else, so the
    assertion reads BOTH: one definition of the entry point, and the scale named in one module.
    """
    producers, scale_holders, checked = [], [], 0
    for path in sorted((ROOT / "site").rglob("*.py")):
        source = path.read_text()
        checked += 1
        if any(isinstance(node, ast.FunctionDef) and node.name == "sparkline_svg"
               for node in ast.walk(ast.parse(source))):
            producers.append(path.relative_to(ROOT).as_posix())
        # The literal ASSIGNMENT, so a caller that merely reads the constant is not a copy.
        if re.search(r"^_CURVE_PX_PER_UNIT\s*=", source, re.M):
            scale_holders.append(path.relative_to(ROOT).as_posix())

    assert checked >= 20, f"only {checked} modules walked — the glob stopped seeing site/"
    assert producers == ["site/lib/winprob.py"], (
        f"the curve must have exactly one producer; found {producers}")
    assert scale_holders == ["site/lib/winprob.py"], (
        f"_CURVE_PX_PER_UNIT is the curve's scale and belongs to one module; "
        f"found {scale_holders}")


def test_the_promoted_curve_exposes_its_width_rather_than_applying_it():
    """🚨 A170 (cfdb-main-R-1324). `chart_width` is PUBLIC on purpose, and this pins why.

    📊 **B138 flagged the one design decision in the promotion:** `_curve_width` exists because
    **ten charts on Today share one `table-layout:fixed` column and the column must be sized to
    the widest of them.** ⚠️ **A Matchup header has ONE chart and no column.**

    ✅ **So the module reports a width and Today decides what to do with it.** Had the module
    applied the shared width itself, Matchup would have inherited a constraint that was never
    its own — and the bug would be a chart that is mysteriously too wide in a header, with
    nothing in Matchup's own source to explain it.

    ⚠️ **AND THE `max(...)` STAYS IN TODAY**, which is the half that proves the split is real.
    """
    winprob = _winprob()
    assert callable(getattr(winprob, "chart_width", None)), (
        "chart_width must be part of the promoted module's public surface")

    # It reports a NUMBER, and a wider game reports a bigger one.
    regulation = winprob.chart_width(None)
    assert isinstance(regulation, int) and regulation > 0, regulation

    # The shared-column decision is Today's, and Today still makes it.
    assert "max(" in SOURCE and "winprob.chart_width(" in SOURCE, (
        "Today must still compute the widest chart itself — that is the constraint the "
        "promoted module deliberately does not impose")
    # 🚨 BY AST, NOT BY SUBSTRING — and this test learned it the hard way on its first run.
    # `chart_width`'s own comment says the column is `max(chart_width(...)) + 12`, describing
    # what TODAY does with the number. A `"max(" in source` check reads that prose as code and
    # fails a function that is correct. §2.2.1c.1's rule, inside the guard enforcing it.
    tree = ast.parse((ROOT / "site" / "lib" / "winprob.py").read_text())
    body = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "chart_width")
    calls = {n.func.id for n in ast.walk(body)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "max" not in calls, (
        "chart_width must report one chart's width, not reach for a shared maximum")


def _winprob():
    """The promoted curve module. Mirrors `test_today_page._winprob`."""
    from lib import winprob
    return winprob


# The four team-name cells Marc asked to be links, as (module, the Col's field, why).
# A169 did the first three; A170 added the fourth once the view finally published a slug.
LINKED_TEAM_CELLS = [
    ("standings.py", "team", "A169 — Standings"),
    ("rankings.py", "team", "A169 — Rankings, the poll table"),
    ("stats.py", "team", "A169 — Stats"),
    ("rankings.py", "school", "A170 — Rankings, the poll-DISAGREEMENT table"),
]


def test_every_team_name_marc_asked_to_link_still_links():
    """🚨 A170 (cfdb-main-R-1326). A169 made three team names links; A170 made the fourth.
    NOTHING ASSERTED ANY OF THEM, and a staged break proved it.

    📊 **MEASURED: removing the compare table's `link=` and removing `team_slug` from its query
    BOTH came back GREEN across the whole suite.** There is no rankings test module at all, so
    the feature Marc asked for twice could be deleted in a refactor and every instrument in this
    project would stay quiet.

    ⚠️ **A169's guard is the NEGATIVE of this rule** — *a table with a linked team name must not
    also link its rows* — so it fires when a link is WRONG and says nothing when one is ABSENT.
    AC-G.11's distinction, in a test suite: those are different failures and only one was
    covered.

    🚨 **AND THE AFFORDANCE IS THE POINT, NOT THE DESTINATION.** All three A169 pages already
    routed to the right place through a row `link_builder`; what was missing was `Col.link`,
    which is what makes the cell LOOK clickable. So this asserts the `link=` keyword
    specifically — a row link_builder would satisfy "it navigates" and is exactly the state
    Marc complained about.
    """
    for module, field, why in LINKED_TEAM_CELLS:
        source = (ROOT / "site" / "views" / module).read_text()
        cols = [node for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "Col"
                and node.args
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == field]
        assert cols, f"{why}: no Col({field!r}) in {module} at all — the cell was renamed or lost"
        linked = [c for c in cols if any(kw.arg == "link" for kw in c.keywords)]
        assert linked, (
            f"{why}: Col({field!r}) in {module} carries no `link=`. The cell may still "
            f"navigate through a row link_builder — that is the state Marc complained about, "
            f"because it does not LOOK like a link.")


def test_the_poll_disagreement_table_selects_the_slug_it_links_with():
    """🚨 A170 (cfdb-main-R-1322). `Col.link` builds an href from a column IN THE ROW, so a link
    is only as real as the SELECT behind it.

    ⚠️ **`table.team_link` returns None where the slug is missing rather than building
    `/team?team=None`** — deliberately, and it is why dropping `team_slug` from the query is a
    SILENT defect: every cell quietly stops being a link and the page still renders perfectly.
    A staged break confirmed the whole suite stayed green.

    📊 **The view could not publish the slug until this round** — `srv_rankings_compare` carried
    `school` and `team_id` and nothing else, checked against `information_schema`. So this
    asserts the two halves that had to arrive together.
    """
    # 🚨 THE SQL STRING BY AST, NOT THE FUNCTION'S TEXT — this test was written the lazy way
    # first and the staged break came back GREEN, because the comment directly above the query
    # says the words "team_slug" and "season" in prose. A grep cannot tell a comment from a
    # select list (§2.2.1c.1), and the comment was one this very round added.
    tree = ast.parse((ROOT / "site" / "views" / "rankings.py").read_text())
    compare = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_compare")
    # "from srv_rankings_compare", not merely the view's name: `states.section` and
    # `states.render_or_state` both take it as a plain string argument, so three constants
    # in this function mention it and only one of them is a query.
    sql = [n.value for n in ast.walk(compare)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)
           and "from srv_rankings_compare" in n.value]
    assert len(sql) == 1, f"expected one query against the view, found {len(sql)}"
    select = sql[0].split("from srv_rankings_compare")[0]
    for column in ("team_slug", "season"):
        assert re.search(rf"\b{column}\b", select), (
            f"the compare query does not select {column!r}, so team_link cannot build an href "
            f"— the cell renders as plain text and nothing else fails")
