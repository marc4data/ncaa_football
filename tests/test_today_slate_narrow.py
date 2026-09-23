"""A209 — the SLATE puts two columns away where they cannot all fit, and says which.

> **MARC, 2026-09-22**, asked whether columns could hide when narrow and come back when wide:
> *"YES, make this happen, with the fix to have column say it's hidden."*

⚠️ THIS REVERSES NOTHING FROM A204, where he said *"Add Weather and O/U. The width of the graph
is not as important as including all the data points"*. At full width every column still shows.
This is the narrow case, which he had not been shown when he said that.

📊 MEASURED IN CHROMIUM ON A208's HEAD AND AGAIN AFTER, sidebar open, one day block:

    viewport  container   before: table/overflow   after: table/overflow   put away
    1440      980         980 /   0                980 /   0               —
    1280      820         940 / 120                820 /   0               O/U · Wx
    1180      720         940 / 220                820 / 100               O/U · Wx
    1100      640         940 / 300                820 / 180               O/U · Wx
    1024      564         940 / 376                820 / 256               O/U · Wx

🚨 THE TWO BOUNDARIES ARE DIFFERENT NUMBERS AND THAT IS THE ROUND'S MAIN FINDING. The columns
go away below **940** — the width at which all eight stop fitting — and with them away the
table does not overflow until **820**. Between those two the reader must be told about the
columns and must NOT be told the row scrolls, because it does not.

📊 AND THE HEADER STAYED WITH ITS BODY: the worst `th`/`td` left-edge offset measured **0.00px**
at all five widths, in both themes. That is the assertion this file exists for — a column
offset by one looks like correct data.
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(ROOT))

from ci.page_url import default_key, page_url, registered_keys   # noqa: E402
from lib import table                                            # noqa: E402
from views import today                                          # noqa: E402

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()


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


def slate(*rows):
    return today._slate(pd.DataFrame(list(rows)), esc=str, scope=_Scope())


def narrow_block(html: str) -> str:
    """The generated `@container` block that collapses the two columns.

    🚨 ANCHORED ON THE BOUNDARY IT DECLARES, not on `<style>`: the SLATE emits TWO style
    blocks — the note's reveal rules and this — and taking the first would have asserted
    against the wrong one. A selector is not a substring and neither is a `<style>` tag.
    """
    marker = f"@container (max-width:{today._SLATE_MIN_PX - 1}px){{.cfdb-slate-table"
    assert marker in html, "no narrow-width block keyed to the SLATE's own minimum"
    start = html.index(marker)
    return html[start:html.index("</style>", start)]


# ── PART 1: the numbers are derived, not chosen ───────────────────────────────────────

def test_the_narrow_numbers_come_from_the_wide_ones():
    """🚨 NOT A CONSTANT COMPARED WITH ITSELF. Every narrow number is arithmetic on
    `_SLATE_COL_PX` and `_SLATE_MIN_PX`, so changing a column width moves all of them and
    there is nothing to keep in step."""
    assert today._SLATE_HIDE_AT == (3, 4), "O/U and Wx, and Marc authorised no more"
    assert today._SLATE_GANTT_MIN_PX == today._SLATE_MIN_PX - sum(today._SLATE_COL_PX)
    put_away_px = sum(today._SLATE_COL_PX[i] for i in today._SLATE_HIDE_AT)
    assert today._SLATE_NARROW_FIXED_PX == sum(today._SLATE_COL_PX) - put_away_px
    assert (today._SLATE_NARROW_MIN_PX
            == today._SLATE_NARROW_FIXED_PX + today._SLATE_GANTT_MIN_PX)
    # and the narrow minimum really is smaller, or the whole exercise buys nothing
    assert today._SLATE_NARROW_MIN_PX < today._SLATE_MIN_PX
    assert today._SLATE_MIN_PX - today._SLATE_NARROW_MIN_PX == put_away_px


def test_the_two_boundaries_are_different_numbers():
    """🚨 THE FINDING. *Hide below 940* and *stops overflowing at 820* are not one width.

    ⚠️ Hiding only below 820 would do NOTHING at 1280 — container 820, where the gantt is the
    only thing cut and 120px of column is exactly what it needs. Claiming the row scrolls all
    the way up to 940 would put a scroll note over a table that does not scroll, which is the
    defect A208 exists to prevent.
    """
    html = slate(_game())
    reveal = int(re.search(r"\.cfdb-scrollnote\[data-min='(\d+)'\]", html).group(1))
    assert reveal == today._SLATE_MIN_PX
    scroll_rule = re.search(
        r"@container \(max-width:(\d+)px\)\{\.cfdb-scrollnote\[data-min='\d+'\] "
        r"\.cfdb-scrollnote-scroll", html)
    assert scroll_rule, "no rule reveals the scroll clause at its own boundary"
    assert int(scroll_rule.group(1)) == today._SLATE_NARROW_MIN_PX - 1


def test_the_axis_stays_above_its_own_label_floor_at_the_narrow_minimum():
    """📊 MEASURED, not assumed: the widest hour label is 16.47px and adjacent labels sit
    0.13227 of the axis apart, so the axis needs 154.8px for a 4px gap. It gets 178 at the
    floor. ⚠️ A minimum that squeezed the axis under that would pile the hour labels up, which
    is the failure `_SLATE_MIN_PX` was introduced to prevent in the first place."""
    widest_label_px, centre_fraction, readable_gap_px = 16.47, 0.13227, 4.0
    floor = (widest_label_px + readable_gap_px) / centre_fraction
    assert today._SLATE_GANTT_MIN_PX > floor, (
        f"the gantt keeps {today._SLATE_GANTT_MIN_PX}px but its labels need {floor:.1f}px")


# ── PART 2: they hide, they come back, and nothing else moves ─────────────────────────

def test_the_two_columns_and_only_those_two_carry_the_collapse_class():
    """⚠️ THE `<col>` AND BOTH CELLS, OR THE COLLAPSE REACHES ONE AND NOT THE OTHERS."""
    html = slate(_game())
    assert html.count("<col class='cfdb-slate-away'") == len(today._SLATE_HIDE_AT)
    assert len(re.findall(r"<th class='[^']*cfdb-slate-away", html)) == 2
    assert len(re.findall(r"<td class='[^']*cfdb-slate-away", html)) == 2
    # the labels carrying it are exactly the two Marc authorised
    labelled = re.findall(r"<th class='[^']*cfdb-slate-away'>([^<]+)</th>", html)
    assert labelled == list(today._SLATE_PUT_AWAY), labelled


def test_the_header_and_the_body_collapse_by_the_same_rule():
    """🚨 A HEADER THAT HIDES WHILE ITS BODY CELL DOES NOT SHIFTS EVERY COLUMN IN THE ROW, AND
    IT LOOKS LIKE CORRECT DATA. One selector list covers `th` and `td` together, so they cannot
    diverge — and the cells COLLAPSE rather than `display:none`, because `table-layout:fixed`
    maps the Nth cell to the Nth `<col>` and removing two would hand the gantt `Why`'s 54px.
    📊 Measured in the browser: worst `th`/`td` offset 0.00px at all five widths, both themes.
    """
    block = narrow_block(slate(_game()))
    cells = re.search(r"\.cfdb-slate-table th\.cfdb-slate-away,"
                      r"\.cfdb-slate-table td\.cfdb-slate-away\{([^}]*)\}", block)
    assert cells, f"th and td must collapse in ONE rule; block was {block!r}"
    for declaration in ("width:0", "padding-left:0", "padding-right:0", "visibility:hidden"):
        assert declaration in cells.group(1), declaration
    # 🚨 AND `display:none` MUST NOT BE THE MECHANISM — that is the column-shifting defect.
    assert "display:none" not in cells.group(1)
    assert "col.cfdb-slate-away{width:0 !important}" in block, (
        "the `<col>` width is an inline style; only `!important` beats it")


def test_the_gridline_layer_moves_with_the_columns():
    """🚨 FORGETTING THIS WOULD HAVE BEEN INVISIBLE IN EVERY OTHER ASSERTION. The hour lines are
    a layer inset by the fixed columns' total; with two collapsed that total is 120px smaller,
    and the lines would have stood 120px right of the hours they mark — a chart that is WRONG
    rather than one that is broken. 📊 Measured: `left` reads 762px wide, 642px narrow, and
    equals the drawn fixed-column total at all five widths."""
    block = narrow_block(slate(_game()))
    assert f".cfdb-slate-grid{{left:{today._SLATE_NARROW_FIXED_PX}px !important}}" in block
    # the wide value is the one the element carries inline
    assert f"style='left:{sum(today._SLATE_COL_PX)}px'" in slate(_game())


def test_the_table_minimum_drops_to_the_narrow_one():
    block = narrow_block(slate(_game()))
    assert f".cfdb-slate-table{{min-width:{today._SLATE_NARROW_MIN_PX}px !important}}" in block
    assert f"style='min-width:{today._SLATE_MIN_PX}px'" in slate(_game())


def test_both_day_blocks_collapse_identically():
    """⚠️ TWO TABLES, ONE BOUNDARY. A rule that fired on one and not the other would be worse
    than no rule — and the collapse is a CLASS on the section's own stylesheet block, so the
    two cannot diverge. This asserts they carry the same classes in the same places."""
    fri = _game(game_id=1, start_date=pd.Timestamp("2026-09-26T00:00:00Z"))
    sat = _game(game_id=2, start_date=pd.Timestamp("2026-09-26T19:30:00Z"))
    html = slate(fri, sat)
    assert html.count("<table class='cfdb-table cfdb-slate-table'") == 2
    assert html.count("<col class='cfdb-slate-away'") == 4, "two per table"
    assert len(re.findall(r"<th class='[^']*cfdb-slate-away", html)) == 4
    # ONE generated block for both, so there is one boundary and not two
    assert html.count(f"@container (max-width:{today._SLATE_MIN_PX - 1}px)"
                      f"{{.cfdb-slate-table") == 1


def test_above_the_boundary_nothing_is_put_away():
    """✅ A204's DECISION IS UNTOUCHED AT FULL WIDTH. 📊 Measured at 1440: container 980, table
    980, overflow 0, nine columns drawn, note `display:none` — A208's numbers exactly."""
    html = slate(_game())
    # the collapse is inside a container query and nowhere else: no unconditional rule
    assert "cfdb-slate-away{width:0" not in THEME, (
        "the collapse must be conditional on the width, never in the base stylesheet")
    assert ".cfdb-slate-putaway { display:none; }" in THEME, "hidden by default"
    # every one of the eight labels is still emitted
    heads = re.findall(r"<th[^>]*>(?:<div[^>]*>)?([A-Za-z/]+)", html)
    for label in ("Away", "Home", "Spread", "O/U", "Wx", "TV", "Game", "Why"):
        assert label in heads, (label, heads)


# ── PART 3: the row says what it put away ─────────────────────────────────────────────

def test_the_note_names_the_columns_it_put_away():
    """> **MARC:** *"with the fix to have column say it's hidden."*

    🚨 A COLUMN THAT VANISHES SILENTLY IS THE SAME DEFECT AS ONE CLIPPED OFF-SCREEN (AC-G.11).
    """
    html = slate(_game())
    clause = re.search(r"<span class='cfdb-slate-putaway'>([^<]+)</span>", html)
    assert clause, "no put-away clause"
    said = clause.group(1)
    for name in today._SLATE_PUT_AWAY:
        assert name in said, (name, said)
    # 📋 and it says the number is not lost, only the column
    assert "matchup" in said.lower()
    # ⚠️ it must not name a column that is still visible at the width it appears
    for still_shown in ("Away", "Home", "Spread", "TV", "Why"):
        assert still_shown not in said, f"{still_shown} is still drawn at that width"


def test_the_put_away_names_come_from_the_columns_that_actually_hide():
    """🚨 ONE SOURCE, OR THE NOTE CAN NAME A COLUMN THAT DID NOT MOVE. The sentence is built
    from `_SLATE_PUT_AWAY`; these are the labels of the columns `_SLATE_HIDE_AT` collapses."""
    html = slate(_game())
    labelled = re.findall(r"<th class='[^']*cfdb-slate-away'>([^<]+)</th>", html)
    assert labelled == list(today._SLATE_PUT_AWAY), (labelled, today._SLATE_PUT_AWAY)


def test_it_is_one_line_with_two_clauses_not_two_notes():
    """✅ ONE NOTE ELEMENT. 📊 Measured: at container 820 the put-away clause reads `block` and
    the scroll clause `none`; at 720 and below both read `block`; at 980 the note itself is
    `none`. Two notes would be two sentences where one belongs."""
    html = slate(_game())
    assert html.count("<div class='cfdb-scrollnote'") == 1
    note = html[html.index("<div class='cfdb-scrollnote'"):]
    note = note[:note.index("</div>") + 6]
    assert "cfdb-slate-putaway" in note and "cfdb-scrollnote-scroll" in note
    # the shared sentence still has exactly one home
    assert table.SCROLL_NOTE in note
    assert sum(path.read_text().count("Scroll the table sideways")
               for path in sorted((ROOT / "site").rglob("*.py"))) == 1


def test_the_scroll_clause_is_hidden_by_default_and_revealed_by_its_own_query():
    """⚠️ HIDDEN BY DEFAULT, BOTH CLAUSES. With no container-query support the reader gets a
    note that never appears rather than one that is always on and false half the time."""
    assert ".cfdb-scrollnote-scroll { display:none; }" in THEME
    assert not re.search(r"^@container[^{]*\{[^}]*cfdb-scrollnote-scroll", THEME, re.M), (
        "the reveal is the page's, keyed to that table's own boundary")


def test_the_other_three_wrappers_read_exactly_as_a208_shipped():
    """✅ `show_at` OMITTED MEANS ONE BOUNDARY, so Scores, Most Exciting and the distance table
    are unchanged: both rules fire at the same width and the line reads the same."""
    plain = table.scroll_note(360)
    boundaries = re.findall(r"@container \(max-width:(\d+)px\)", plain)
    assert boundaries == ["359", "359"], boundaries
    assert table.SCROLL_NOTE in plain
    assert "cfdb-slate-putaway" not in plain, "the put-away clause is the SLATE's alone"


# ── PART 4: the harness stops photographing a dialog ──────────────────────────────────

def test_the_default_page_is_requested_at_the_root():
    """🚨 EVERY `Today` CROP A208 TOOK HAS A STREAMLIT "Page not found" MODAL ACROSS IT.

    📊 `site/app.py` registers Today with `url_path="today"` AND `default=True`. Streamlit
    serves the default page at the app root, so `/today` is not a route: it 404s, draws the
    dialog, and falls back to the default page — which IS Today. Measured in Chromium: `/today`
    → 2 dialogs and the fallback text; `/` and `/scores` → none.

    ⚠️ AND IT IS NOT A LIVE DEFECT. Nothing in `site/` builds a link to `/today`; the harness
    was the only caller.
    """
    assert default_key() == "today"
    assert page_url("today") == "/"
    assert page_url("scores") == "/scores"


def test_exactly_one_page_is_the_default():
    """🚨 REGISTER RULE 10's CLASS. *"18 of 18 pages render"* once came from a harness that set
    `?page=<key>` while `st.navigation` routes on `url_path`, so all eighteen runs rendered the
    same default page. A second default, or none, makes `page_url` silently wrong for every
    page — so it is asserted rather than assumed."""
    app = (ROOT / "site" / "app.py").read_text()
    assert len(re.findall(r"default\s*=\s*\(", app)) == 1
    assert re.search(r"url_path\s*=\s*p\.key", app), "non-default pages route on their key"


def test_every_registered_page_resolves_to_exactly_one_url():
    """⚠️ AND NO TWO PAGES SHARE A URL, which is what would make a crop ambiguous again."""
    keys = registered_keys()
    assert len(keys) >= 18, keys
    urls = [page_url(k) for k in keys]
    assert len(set(urls)) == len(urls), "two pages resolve to one URL"
    assert urls.count("/") == 1, "exactly one page answers at the root"
