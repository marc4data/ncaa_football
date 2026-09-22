"""A207 — every SLATE column is reachable, and the page says so when some are off-screen.

📊 MEASURED IN A BROWSER, sidebar open, on the code A205 shipped:

    width   container   table   overflow   scrollbar drawn   columns past the edge
    1440    980         980     0          —                 none
    1280    820         940     120        0px               the gantt
    1100    640         940     300        0px               TV · Game · Why · the gantt
    1024    564         940     376        0px               Wx · TV · Game · Why · the gantt

🚨 THE SCROLLBAR WAS 0px AT EVERY WIDTH. `overflow-x:auto` says content exists beyond the box;
it says nothing about whether a reader can TELL. macOS draws overlay scrollbars that appear
only while scrolling, so the content was reachable and **nothing announced it** — a different
defect from unreachable, and a worse one to ship (AC-G.11).

⚠️ AND A STYLED `::-webkit-scrollbar` COULD NOT BE PROVEN. With the rule in the page and
`scrollbar-width:thin` computing, `offsetHeight - clientHeight` stayed **0**. The styling is
kept for the platforms that honour it; **the thing the reader depends on is the note**, which
is a container query on the layout rather than a guess about the browser.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                    # noqa: E402

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
THEME = (ROOT / "site" / "lib" / "theme.py").read_text()


class _Scope:
    season = 2026

    def link(self, page, **kw):
        bits = "&".join(f"{k}={v}" for k, v in kw.items())
        return f"/{page}?{bits}" if bits else f"/{page}"


def _game(**kw):
    import pandas as pd
    row = {"game_id": 1, "start_date": pd.Timestamp("2026-09-26T19:30:00Z"),
           "away_team_display": "Oklahoma", "home_team_display": "Georgia",
           "away_team_slug": "oklahoma", "home_team_slug": "georgia",
           "away_rank": float("nan"), "home_rank": 2.0,
           "away_logo_url": "https://cdn.example/a.png",
           "home_logo_url": "https://cdn.example/h.png",
           "network_abbreviation": "ESPN", "spread_current": -13.5,
           "total_current": 44.5, "kickoff_time_known": True, "is_completed": False,
           "is_top25_matchup": False, "is_undefeated_entering": False,
           "is_added_by_you": False}
    row.update(kw)
    return row


def slate(*rows):
    import pandas as pd
    return today._slate(pd.DataFrame(list(rows)), esc=lambda t: str(t), scope=_Scope())


def code_of(name: str) -> str:
    tree = ast.parse(SOURCE)

    def find(nodes):
        for node in nodes:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
            found = find(getattr(node, "body", []))
            if found is not None:
                return found
        return None

    node = find(tree.body)
    assert node is not None, f"no function {name!r}"
    body = node.body
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return "\n".join(ast.get_source_segment(SOURCE, n) for n in body)


def rule(selector: str) -> str:
    """The declaration block for a selector, ANCHORED AT A LINE START.

    🚨 `THEME.index(".cfdb-scroll {")` finds the substring inside `.cfdb-slate .cfdb-scroll {`
    and returns the WRONG rule — which is how the first run of this file asserted
    `overflow-x:auto` against the scrollbar-styling block. A selector is not a substring.
    """
    m = re.search(rf"^{re.escape(selector)}", THEME, re.M)
    assert m, f"no rule starting a line with {selector!r}"
    return THEME[m.start():THEME.index("}", m.start())]


# ── PART 1: reachable, and announced ──────────────────────────────────────────────────

def test_the_table_is_inside_a_scroller_so_no_column_is_unreachable():
    """A column a reader cannot get to is not a narrow layout, it is missing data."""
    html = slate(_game())
    assert "cfdb-scroll" in html
    assert html.index("cfdb-scroll") < html.index("<table"), "the scroller wraps the table"
    assert "overflow-x:auto" in rule(".cfdb-scroll {")


def test_the_scroll_note_is_emitted_for_every_slate():
    html = slate(_game())
    assert "cfdb-slate-scrollnote" in html
    assert "Scroll the table sideways" in html
    # it sits above the day blocks, where a reader meets it before the cut-off table
    assert html.index("cfdb-slate-scrollnote") < html.index("cfdb-slate-day")


def test_the_note_is_hidden_by_default_and_revealed_by_the_container_query():
    """🚨 HIDDEN BY DEFAULT, REVEALED BY THE QUERY — never the other way round.

    ⚠️ If container queries were unsupported, the fallback must be the note showing at every
    width (mildly redundant) rather than a table that silently hides five columns. A rule that
    HID it in the query would fail open in exactly the wrong direction.
    """
    base = rule(".cfdb-slate-scrollnote {")
    assert "display:none" in base
    query = THEME[THEME.index("@container (max-width:"):]
    query = query[:query.index("}", query.index("{", query.index("{") + 1)) + 1]
    assert "cfdb-slate-scrollnote" in query and "display:flex" in query


def test_the_query_boundary_is_the_tables_own_minimum():
    """🚨 TWO INDEPENDENT NUMBERS IN THE STYLESHEET, COMPARED — not a constant against itself.

    The note must appear at exactly the width past which something goes out of reach, which is
    the table's `min-width`. 📊 940px is 762px of fixed columns plus 178px of axis.
    """
    min_w = int(re.search(r"\.cfdb-slate-table \{[^}]*min-width:(\d+)px",
                          THEME).group(1))
    boundary = int(re.search(r"@container \(max-width: ?(\d+)px\)", THEME).group(1))
    assert boundary == min_w - 1, (
        f"the note appears below {boundary + 1}px but the table needs {min_w}px")


def test_the_scrollbar_is_styled_even_though_it_could_not_be_proven_drawn():
    """⚠️ KEPT, AND NOT RELIED ON. 📊 With this rule in the page and `scrollbar-width:thin`
    computing, `offsetHeight - clientHeight` measured **0px at every width** in this browser —
    an overlay scrollbar. It helps where the platform honours it; the note is what the reader
    depends on."""
    # 🚨 THE HEIGHT RULE SPECIFICALLY. `"::-webkit-scrollbar" in THEME` is satisfied by
    # `::-webkit-scrollbar-track` and `-thumb`, so a break deleting the only rule that gives
    # the bar a SIZE came back GREEN — the same substring trap that let a renamed column pass
    # in A204.
    assert re.search(r"::-webkit-scrollbar \{[^}]*height:\d+px", THEME), (
        "the bar needs a height, or the track and thumb style nothing")
    assert "scrollbar-width: thin" in rule(".cfdb-slate .cfdb-scroll {")


def test_both_day_blocks_get_the_same_treatment():
    """⚠️ FRIDAY AND SATURDAY ARE TWO SEPARATE TABLES and must agree column-for-column."""
    import pandas as pd
    fri = _game(game_id=1, start_date=pd.Timestamp("2026-09-26T00:00:00Z"))
    sat = _game(game_id=2, start_date=pd.Timestamp("2026-09-26T19:30:00Z"))
    html = slate(fri, sat)
    assert html.count("cfdb-slate-table") == 2, "two day blocks"
    assert html.count("cfdb-scroll") == 2, "each inside its own scroller"
    # ⚠️ `... or True` MAKES AN ASSERTION UNFAILABLE, and the first draft of this test had
    # one (R-760). The question is whether the two blocks carry the SAME columns.
    heads = re.findall(r"<thead><tr>(.*?)</tr></thead>", html, re.S)
    assert len(heads) == 2, heads
    # the column SET is identical in both
    labels = [re.findall(r"<th[^>]*>([A-Za-z/ ]*)</th>", h) for h in heads]
    assert labels[0] == labels[1], labels


def test_the_minimum_width_keeps_the_axis_from_collapsing():
    """⚠️ THE GANTT IS THE REASON THE SLATE EXISTS. Without a minimum the graph column takes
    whatever is left, which at 1024 is nothing — a chart with no axis is worse than a chart
    you have to scroll to."""
    min_w = int(re.search(r"\.cfdb-slate-table \{[^}]*min-width:(\d+)px", THEME).group(1))
    fixed = sum(today._SLATE_COL_PX)
    assert min_w - fixed >= 150, (
        f"only {min_w - fixed}px left for the time axis after {fixed}px of fixed columns")


# ── PART 2: the how-to line gets its own line ─────────────────────────────────────────

def test_the_hint_is_its_own_caption_not_the_fourth_sentence_of_a_paragraph():
    """📊 A205 put it in the methodology caption and it was true and unread: that paragraph
    opens with kick-off times and bar arithmetic, and **a reader looking for "how do I add a
    game" does not read a methodology note to the end.**"""
    body = code_of("_looking_forward")
    # the methodology caption no longer carries it
    methodology = body[body.index("Kick-off times Pacific"):]
    methodology = methodology[:methodology.index("st.caption(_ADD_GAMES_HINT)")]
    assert "_ADD_GAMES_HINT" not in methodology, (
        "the hint must not be interpolated into the methodology sentence")
    # and it is a caption of its own
    assert "st.caption(_ADD_GAMES_HINT)" in body


def test_the_words_did_not_change():
    """⚠️ MARC ASKED ABOUT WHERE IT SITS, NOT WHAT IT SAYS."""
    hint = today._ADD_GAMES_HINT
    assert hint.startswith("To add a game, paste its id into")
    assert "at the bottom of the sidebar" in hint
    shown = re.search(r"game_id=(\d{6,})", hint)
    assert shown and shown.group(1) == today._ADD_GAMES_EXAMPLE
