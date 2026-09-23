"""A208 — every wide table on the site says it scrolls, at its OWN boundary.

📊 THE FOUR `.cfdb-scroll` WRAPPERS, ENUMERATED BEFORE ANYTHING MOVED. A207 named three and
two of them were wrong; this is the measured list:

    page     table                      emitted by                   boundary
    Scores   the results table          table.render(scroll=True)    sum of its px layout
    Today    Most Exciting              table.render(scroll=True)    sum of its px layout
    Today    Furthest from the median   today._distance_table        _FAR_MIN_PX   = 320
    Today    the SLATE (one per day)    today._slate                 _SLATE_MIN_PX = 940

⚠️ SCHEDULE'S LIST AND THE ODDS BOARD ARE NOT AMONG THEM, though A207's report and two shipped
comments said so. Both call `table.render` without `scroll=True` and emit no wrapper at all —
nothing on those pages overflows into a box, so nothing there needs a note.

🚨 ONE HARD-CODED 939 COULD ONLY EVER BE RIGHT FOR ONE TABLE. A note that appears above a table
with nothing past its edge is worse than no note, because it teaches a reader to ignore it — so
the boundary travels with the table and the stylesheet holds only the shape.
"""
import ast
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from lib import table                                       # noqa: E402
from lib.table import Col                                   # noqa: E402
from views import today                                     # noqa: E402

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()
WRAPPER = "<div class='cfdb-scroll'>"


def rule(selector: str) -> str:
    """The declaration block for a selector, ANCHORED AT A LINE START.

    🚨 A SELECTOR IS NOT A SUBSTRING (A207's R-2260, and it cost that round a green break).
    `THEME.index(".cfdb-scroll {")` also matches inside `.cfdb-slate .cfdb-scroll {`, and
    `"::-webkit-scrollbar" in THEME` is satisfied by `-track` and `-thumb`. Every stylesheet
    assertion in this file goes through here or through an anchored regex.
    """
    m = re.search(rf"^{re.escape(selector)}", THEME, re.M)
    assert m, f"no rule starting a line with {selector!r}"
    return THEME[m.start():THEME.index("}", m.start())]


def _render(**kw) -> str:
    """The markup `table.render` would write, captured rather than displayed."""
    captured = []
    real_markdown, real_caption = table.st.markdown, table.st.caption
    table.st.markdown = lambda markup, **_: captured.append(markup)
    table.st.caption = lambda *a, **k: None
    try:
        table.render(pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}),
                     [Col("a", "A", kind="int"), Col("b", "B")], sortable=False, **kw)
    finally:
        table.st.markdown, table.st.caption = real_markdown, real_caption
    assert captured, "render wrote nothing"
    return captured[-1]


# ── the enumeration holds ─────────────────────────────────────────────────────────────

def test_every_scroll_wrapper_is_emitted_beside_a_note():
    """🚨 THE GUARD AGAINST A FIFTH WRAPPER APPEARING WITHOUT ONE.

    A203 fixed one table, A207 fixed another, and neither generalised — three instances of one
    class in five rounds. The way that happens a fourth time is a new `<div class='cfdb-scroll'>`
    written by hand somewhere this file does not look, so this looks at every function on the
    site that writes one.
    """
    offenders = []
    for path in sorted((ROOT / "site").rglob("*.py")):
        source = path.read_text()
        if WRAPPER not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = ast.get_source_segment(source, node) or ""
            if WRAPPER in body and "scroll_note" not in body and node.name != "scroll_box":
                offenders.append(f"{path.relative_to(ROOT)}::{node.name}")
    assert not offenders, (
        "a scroller with no note — a reader cannot tell these tables scroll: "
        + ", ".join(offenders))


def test_the_wrapper_count_is_the_four_this_round_measured():
    """⚠️ A COUNT THAT MOVES IS NOT A FAILURE, IT IS A ROUND. 📊 Two hand-built wrappers in
    `today.py` (the SLATE and the distance table) plus the one inside `table.scroll_box`,
    which serves Scores and Most Exciting. A fifth means someone has a table this file's
    enumeration does not describe."""
    written = {p.relative_to(ROOT).as_posix(): p.read_text().count(WRAPPER)
               for p in sorted((ROOT / "site").rglob("*.py"))
               if WRAPPER in p.read_text()}
    assert written == {"site/lib/table.py": 1, "site/views/today.py": 2}, written


# ── the boundary is the table's own ───────────────────────────────────────────────────

def test_the_boundary_is_one_pixel_under_the_tables_own_minimum():
    """🚨 NOT A CONSTANT COMPARED WITH ITSELF. Two different minimums produce two different
    queries, so a hard-coded 939 anywhere in this path fails here rather than shipping a note
    that is right for the SLATE and wrong for everything else."""
    for minimum in (320, 940, 1412):
        markup = table.scroll_note(minimum)
        assert f"data-min='{minimum}'" in markup
        found = int(re.search(r"@container \(max-width:(\d+)px\)", markup).group(1))
        assert found == minimum - 1, (minimum, found)


def test_the_query_is_keyed_to_its_own_note_and_not_to_every_note():
    """⚠️ TWO BOXES ON ONE PAGE HAVE TWO BOUNDARIES. Today draws three — Most Exciting, the
    distance table and the SLATE — and an unkeyed rule would reveal all of them at whichever
    width came first."""
    narrow, wide = table.scroll_note(320), table.scroll_note(940)
    assert "[data-min='320']" in narrow and "[data-min='940']" not in narrow
    assert "[data-min='940']" in wide and "[data-min='320']" not in wide


def test_a_table_that_cannot_know_its_width_gets_no_note():
    """🚨 A GUESSED BOUNDARY IS HOW A NOTE APPEARS WHERE NOTHING IS HIDDEN.

    ⚠️ A wrapper with nothing past its edge must show NO note at any width. A percentage layout
    is a share of whatever it is given and `auto` is settled by the browser, so neither has an
    intrinsic width to compare a container against — and the honest answer is silence.
    """
    assert table.scroll_minimum(["40%", "60%"]) is None
    assert table.scroll_minimum(None) is None
    assert table.scroll_minimum([]) is None
    assert table.scroll_minimum(["120px", "auto"]) is None
    assert table.scroll_minimum(["120px", "240px"]) == 360
    assert "cfdb-scrollnote" not in table.scroll_box("<table></table>", None)
    assert WRAPPER in table.scroll_box("<table></table>", None), "it still scrolls"


def test_render_draws_the_note_for_a_pixel_layout_and_not_otherwise():
    """📊 THE TWO WRAPPERS THAT COME THROUGH `render`: Scores and Most Exciting both pass an
    all-pixel layout, which is the same question `exact` already asks one line above."""
    pixels = _render(layout=["120px", "240px"], scroll=True)
    assert "cfdb-scrollbox" in pixels and "data-min='360'" in pixels
    shares = _render(layout=["40%", "60%"], scroll=True)
    assert "cfdb-scrollnote" not in shares and WRAPPER in shares
    assert "cfdb-scroll" not in _render(layout=["120px", "240px"]), "no wrapper without scroll"


def test_the_two_hand_built_tables_carry_their_minimum_and_their_note_from_one_number():
    """⚠️ ONE DEFINITION PER TABLE. A207 wrote 940 into the stylesheet AND into a container
    query and held them together with a test that they agreed — which is a test that they had
    not drifted yet. The minimum is Python's now and the table carries it inline."""
    slate = today._slate(pd.DataFrame([_game()]), esc=str, scope=_Scope())
    assert f"style='min-width:{today._SLATE_MIN_PX}px'" in slate
    assert f"data-min='{today._SLATE_MIN_PX}'" in slate

    far = today._distance_table(
        [(12.3, {"team": "Mississippi State", "team_slug": "mississippi-state",
                 "x": 300.0, "y": 420.0, "logo_url": None,
                 "record_before_display": "2-0"})],
        (310.0, 400.0), 133, scope=_Scope())
    assert f"style='min-width:{today._FAR_MIN_PX}px'" in far
    assert f"data-min='{today._FAR_MIN_PX}'" in far
    # 🚨 AND THEY ARE DIFFERENT NUMBERS, which is the whole point of the round.
    assert today._SLATE_MIN_PX != today._FAR_MIN_PX


def test_the_slate_still_renders_what_a207_shipped():
    """🚨 THE GENERALISATION MUST NOT CHANGE THE THING IT WAS SUPPOSED TO PRESERVE.

    📊 Measured in a browser after the move, sidebar open, and it reproduces A207's table to
    the pixel: container 980 / table 980 / overflow 0 / note `display:none` at 1440, and
    640 / 940 / 300 / `display:flex` at 1100. ⚠️ This asserts the ORDER of the emitted parts,
    which is what a reader sees: the note, then the legend, then each day and its scroller.
    """
    html = today._slate(pd.DataFrame([_game()]), esc=str, scope=_Scope())
    order = ["cfdb-slate cfdb-scrollbox", "cfdb-scrollnote", "cfdb-slate-key",
             "cfdb-slate-day", WRAPPER, "cfdb-slate-grid", "cfdb-slate-table"]
    found = [html.index(piece) for piece in order]
    assert found == sorted(found), dict(zip(order, found))
    # the retired SLATE-scoped names are gone, not renamed alongside the new ones
    assert "cfdb-slate-scrollnote" not in html
    # one note, one style rule, one scroller per day block
    assert html.count("<style>") == 1


def test_an_empty_distance_table_says_nothing_about_scrolling():
    """AC-G.11: the empty state is a real state and it has nothing past its edge."""
    empty = today._distance_table([], None, 0, scope=_Scope())
    assert "cfdb-scrollnote" not in empty and "cfdb-scroll" not in empty
    assert "No team in this scope" in empty


# ── the sentence is true at every width it appears ────────────────────────────────────

def test_the_note_names_nothing_that_changes_with_the_width():
    """🚨 A SENTENCE WHOSE JOB IS TO SAY WHAT IS OUT OF REACH MUST BE TRUE WHERE IT APPEARS.

    📊 A207 shipped *"…for the network, the matchup link and the time chart"* against a hidden
    set that its own measurement says is three different sets: the gantt at 1280; Game, Why and
    the gantt at 1100; Wx, TV, Game, Why and the gantt at 1024. It over-claimed at two widths
    and under-claimed at the third. ⚠️ Python cannot see the viewport, so a per-width sentence
    means three notes behind three queries — for a reader who is about to scroll and find out.
    """
    note = table.SCROLL_NOTE
    assert "Scroll the table sideways" in note
    named = [word for word in ("network", "matchup link", "time chart", "Wx", "TV", "O/U",
                               "Game", "Why", "gantt") if word in note]
    assert not named, f"the note names a column whose visibility changes with the width: {named}"
    # and it is one sentence, not a list that grew back
    assert note.count(".") == 1, note


def test_one_definition_of_the_sentence_reaches_every_table():
    """⚠️ FOUR WRAPPERS, ONE SENTENCE. A second literal is a second thing to keep in step."""
    written = sum(path.read_text().count("Scroll the table sideways")
                  for path in sorted((ROOT / "site").rglob("*.py")))
    assert written == 1, "the sentence has one home, `table.SCROLL_NOTE`"


# ── the stylesheet stops claiming something the last round disproved ──────────────────

def test_the_stylesheet_hides_the_note_and_reveals_it_nowhere():
    """🚨 HIDDEN BY DEFAULT. With no container-query support the reader gets a note that never
    appears — under-informative — rather than one that is always on, which is worse: a note a
    reader learns to ignore is a note that cannot warn them."""
    assert "display:none" in rule(".cfdb-scrollnote {")
    assert not re.search(r"^@container[^{]*\{[^}]*cfdb-scrollnote", THEME, re.M), (
        "the reveal is the page's, keyed to one table's boundary")
    assert "container-type:inline-size" in rule(".cfdb-scrollbox {")


def test_the_scrollbar_styling_is_shared_rather_than_slate_scoped():
    """📊 A207 scoped it `.cfdb-slate .cfdb-scroll`, so three of the four wrappers got nothing.

    🚨 THE HEIGHT DECLARATION SPECIFICALLY, at a line start. `"::-webkit-scrollbar" in THEME`
    is satisfied by `-track` and `-thumb` — A207's break 6 came back green on exactly that.
    """
    assert "scrollbar-width: thin" in rule(".cfdb-scroll {")
    assert re.search(r"^\.cfdb-scroll::-webkit-scrollbar \{[^}]*height:\d+px", THEME, re.M)
    assert ".cfdb-slate .cfdb-scroll" not in THEME, "nothing scopes it to one table any more"


def test_the_stylesheet_no_longer_claims_the_bar_occupies_layout():
    """🚨 A207 MEASURED `offsetHeight - clientHeight` AT 0px AT EVERY WIDTH AND SHIPPED A
    COMMENT SAYING THE OPPOSITE — in `theme.py`, the one file both sessions rebase across.

    ⚠️ The abandoned approach's REASONING, left beside the styling it argued for: the next
    reader learns a mechanism this project measured as not working. The styling stays; the
    sentence goes.
    """
    assert "force a bar that OCCUPIES LAYOUT" not in THEME
    assert "becomes non-zero and the fix is measurable rather than assumed" not in THEME
    block = rule(".cfdb-scroll {")
    assert "0px at every width" in block, "say what was measured"
    assert "never PROVEN drawn" in block or "was never PROVEN" in block


def test_the_disproved_stacking_claim_is_gone_from_both_places_that_carried_it():
    """📊 A190 said a `min-width` makes a Streamlit column drop to its own line; A203 measured
    that false and wrote the correction — and left TWO copies of the claim in the file, one of
    them orphaned above a block it does not describe."""
    assert "drops to its own full-width\n   line beneath the chart" not in THEME
    assert ("The min-width is what makes the column drop below the chart on a narrow\n"
            "   viewport") not in THEME


def test_schedules_list_is_not_described_as_scrolling():
    """🚨 TWO SHIPPED COMMENTS SAID IT DID. 📊 `schedule.py` calls `table.render` without
    `scroll=True` and the string `cfdb-scroll` does not appear in it."""
    schedule = (ROOT / "site" / "views" / "schedule.py").read_text()
    assert "scroll=True" not in schedule and "cfdb-scroll" not in schedule
    assert "Schedule's list and A201's SLATE both do" not in THEME
    assert "Schedule's list and A201's SLATE already do" not in (
        (ROOT / "site" / "views" / "today.py").read_text())


# ── fixtures, kept at the bottom so the tests read first ──────────────────────────────

class _Scope:
    season = 2026

    def link(self, page, **kw):
        bits = "&".join(f"{k}={v}" for k, v in kw.items())
        return f"/{page}?{bits}" if bits else f"/{page}"


def _game(**kw):
    row = {"game_id": 1, "start_date": pd.Timestamp("2026-09-26T19:30:00Z"),
           "away_team_display": "Oklahoma", "home_team_display": "Georgia",
           "away_team_slug": "oklahoma", "home_team_slug": "georgia",
           "away_rank": float("nan"), "home_rank": 2.0,
           "away_logo_url": None, "home_logo_url": None,
           "network_abbreviation": "ESPN", "spread_current": -13.5,
           "total_current": 44.5, "kickoff_time_known": True, "is_completed": False,
           "is_top25_matchup": False, "is_undefeated_entering": False,
           "is_added_by_you": False}
    row.update(kw)
    return row
