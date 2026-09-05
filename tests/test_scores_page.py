"""The stacked Scores page: tabs, freezing, banding, sorting (R-267 to R-270).

The page is one row per team per game, which is what makes it a scoreboard — there is no
pivot here and no pairing logic, and the moment anything reshapes the frame that is the bug.
Most of these tests are about the ways that could stop being true.
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from lib import table, theme, workbook            # noqa: E402
from lib.table import Col                         # noqa: E402
from views import scores                          # noqa: E402

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "scores.py").read_text()


# --- the tabs cover the sheet, exactly once ------------------------------------------------

def test_every_export_column_appears_on_exactly_one_tab():
    """Marc's "if it's possible include all the columns in the Excel output", as one
    assertion. Both halves matter: a column on two tabs is a reader comparing two copies, and
    a column on none is silently absent from the site while present in the file.

    The frozen four are excluded from the once-only half because they are on every tab
    deliberately — that is what "hold consistent with several different tabs" means.
    """
    everything = {field for field, _ in workbook.SCORES_COLUMNS}
    union, twice = set(), []
    for _label, blocks in scores.TABS:
        own = set(scores.tab_fields(blocks)) - set(scores.FROZEN)
        twice += sorted(union & own)
        union |= own

    assert twice == [], twice
    assert union | set(scores.FROZEN) == everything, {
        "on no tab": sorted(everything - (union | set(scores.FROZEN))),
        "on a tab but not the sheet": sorted((union | set(scores.FROZEN)) - everything)}
    assert len(everything) == 144


def test_the_tabs_are_built_from_the_blocks_not_from_a_copied_list():
    """A second list of field names would be a second thing to maintain, and it would drift
    the first time a column joined a band. The mapping is tab label -> block name."""
    assert "workbook.SCORES_BLOCKS" in SOURCE
    block_names = {name for name, _ in workbook.SCORES_BLOCKS}
    named = {b for _label, blocks in scores.TABS for b in blocks}
    assert named == block_names, named ^ block_names


def test_six_tabs_cover_seven_bands_and_ancillary_rides_with_game():
    """Marc named six tabs, then split a seventh band out of Game a day later and did not add
    a tab. The colour is workbook presentation, the tab is site presentation, and the shared
    thing is the block structure rather than the label — so the ancillary keys sit at the far
    right of Game Results for the same reason they sit at the far right of the sheet.
    """
    assert len(scores.TABS) == 6
    assert len(workbook.SCORES_BLOCKS) == 7
    game_results = scores.tab_fields(("Game", "Ancillary"))
    ancillary = [f for f, _ in workbook.SCORES_COLUMNS
                 if workbook.SCORES_CATEGORY[f] == "Ancillary"]
    assert game_results[-len(ancillary):] == ancillary, "ancillary is not at the far right"


def test_the_frozen_four_lead_every_tab_in_the_same_order():
    """"The identifying rows should be frozen and hold consistent with several different
    tabs." Same four, same order, first on all six — a frozen block that moved between tabs
    would be worse than none."""
    assert scores.FROZEN == ("game_no", "game_date", "team", "points_for")
    for _label, blocks in scores.TABS:
        assert scores.tab_fields(blocks)[:4] == list(scores.FROZEN)


# --- the default sort, and what a user sort does to it -------------------------------------

def _frame(rows):
    return pd.DataFrame(rows)


def test_a_user_sort_stacks_on_the_default_rather_than_replacing_it(monkeypatch):
    """`apply_sort` uses a stable mergesort, so sorting the already-ordered frame by one
    column keeps the compound default as the tiebreak — "total yards descending, ties broken
    chronologically, away above home" for free.

    Sorting by a CONSTANT column is the sharp version of that: every row ties, so a stable
    sort must hand back the original order untouched. An unstable one would shuffle it.
    """
    from lib import params
    frame = _frame([{"game_no": n // 2 + 1, "flat": 1, "seq": n} for n in range(12)])
    columns = [Col("flat", "Flat", "num"), Col("seq", "Seq", "num")]

    monkeypatch.setattr(params, "get", lambda k: {"sort": "flat", "order": "asc"}.get(k))
    monkeypatch.setattr(table.params, "get", lambda k: {"sort": "flat",
                                                        "order": "asc"}.get(k))
    assert list(table.apply_sort(frame, columns)["seq"]) == list(range(12))


def test_no_sort_leaves_the_frame_exactly_as_the_query_returned_it(monkeypatch):
    """The compound default IS the query's ORDER BY — season, regular-before-postseason,
    week, date, game, away-then-home. Re-implementing it in Python would be a second
    definition of "default", which is the drift this project keeps paying for, so the default
    is "leave the frame alone" and this is what says so."""
    from lib import params
    monkeypatch.setattr(params, "get", lambda _k: None)
    monkeypatch.setattr(table.params, "get", lambda _k: None)
    frame = _frame([{"seq": n} for n in (3, 1, 2)])
    assert list(table.apply_sort(frame, [Col("seq", "Seq", "num")])["seq"]) == [3, 1, 2]


def test_the_reset_link_appears_only_when_a_sort_is_active(monkeypatch):
    """A control that does nothing is the dead-link problem R-178 was about."""
    emitted = []
    monkeypatch.setattr(scores.st, "markdown", lambda html, **k: emitted.append(html))

    monkeypatch.setattr(scores.params, "get", lambda _k: None)
    scores._reset_link()
    assert emitted == [], "offered a reset with nothing to reset"

    monkeypatch.setattr(scores.params, "get",
                        lambda k: "total_yards" if k == "sort" else None)
    monkeypatch.setattr(scores.params, "link_here",
                        lambda **kw: "?season=2025" if kw == {"sort": None, "order": None}
                        else "WRONG")
    scores._reset_link()
    assert len(emitted) == 1
    assert "?season=2025" in emitted[0], "the reset does not clear sort and order"
    assert "Default sort" in emitted[0], "labelled for what it does, not 'Reset'"


# --- banding, and the cap that must not halve a game ---------------------------------------

def test_the_band_shades_runs_of_one_game_not_a_parity():
    """R-257 refused position-based banding in EXCEL because the reader re-sorts after we are
    gone. On the site we render after sorting, so position is knowable and the honest rule is
    the one Excel could not have.

    Parity would be wrong here in a specific way: under a user sort it would tint two
    unrelated rows whose game numbers happened to share a parity, which is a claim that they
    belong together. Runs degrade to an ordinary zebra stripe instead, which is honest.
    """
    frame = _frame([{"game_no": n} for n in (1, 1, 2, 2, 3, 3)])
    band = scores._band(frame)
    marks = [bool(band(row)) for _, row in frame.iterrows()]
    assert marks == [True, True, False, False, True, True], marks

    # Scattered by a user sort: consecutive-equal runs, not parity. Rows 0 and 1 are one run
    # even though 3 and 1 have the same parity, and the two 2s are separated.
    scattered = _frame([{"game_no": n} for n in (3, 3, 2, 1, 1, 2)])
    band = scores._band(scattered)
    assert [bool(band(r)) for _, r in scattered.iterrows()] == \
        [True, True, False, True, True, False]


def test_the_row_cap_never_cuts_a_game_in_half():
    """A cap landing between a game's two rows leaves a team with no opponent on the last
    line — the pairing breaking silently, which reads as missing data."""
    frame = _frame([{"game_no": n // 2 + 1} for n in range(20)])
    assert scores._pairs_only(frame, 5) == 4, "an odd cap must round down to a whole game"
    assert scores._pairs_only(frame, 6) == 6, "an even cap on whole games is already fine"
    assert scores._pairs_only(frame, 40) == 40, "nothing to trim when everything fits"


# --- the scroll architecture ----------------------------------------------------------------

def test_a_scrolling_table_is_sized_by_its_columns_not_by_its_container():
    """`width:100%` plus a percentage colgroup CANNOT overflow — thirty-nine columns compress
    until unreadable and there is nothing wider than the viewport to scroll. This is the
    architecture half of R-269, and it is the part most likely to look done and not be."""
    css = theme.TABLE_CSS
    assert ".cfdb-scroll" in css and "overflow-x:auto" in css
    assert ".cfdb-table-wide" in css and "max-content" in css
    # The base table keeps width:100% — seventeen other pages want it.
    assert ".cfdb-table { width:100%" in css


def test_the_frozen_columns_are_sticky_with_real_offsets():
    """`position:sticky` cannot go on a <col>, so it goes on every th and td, and each needs
    the sum of the widths to its left. Without the offsets they all pin to 0 and stack on top
    of one another, which looks like a rendering bug."""
    captured = {}
    frame = _frame([{"a": 1, "b": 2, "c": 3}])
    columns = [Col("a", "A", "num"), Col("b", "B", "num"), Col("c", "C", "num")]

    import streamlit as st
    original = st.markdown
    st.markdown = lambda html, **k: captured.setdefault("html", html)
    try:
        table.render(frame, columns, layout=["60px", "80px", "100px"],
                     scroll=True, sticky=2)
    finally:
        st.markdown = original

    html = captured["html"]
    assert "cfdb-scroll" in html and "cfdb-table-wide" in html
    assert "left:0px" in html and "left:60px" in html
    assert "left:140px" not in html, "the third column must not be sticky"
    assert html.count("cfdb-sticky-edge") >= 2, "the frozen block needs a visible edge"


def test_sticky_is_ignored_rather_than_half_applied_without_pixel_widths():
    """A percentage layout gives no offsets to compute. Pinning every frozen column to 0
    would stack them, so the request is dropped instead."""
    captured = {}
    import streamlit as st
    original = st.markdown
    st.markdown = lambda html, **k: captured.setdefault("html", html)
    try:
        table.render(_frame([{"a": 1, "b": 2}]), [Col("a", "A"), Col("b", "B")],
                     layout=["50%", "50%"], scroll=True, sticky=2)
    finally:
        st.markdown = original
    assert "cfdb-sticky" not in captured["html"]


def test_the_sticky_background_is_a_token_with_a_value_in_both_themes():
    """A TRANSPARENT sticky cell shows the scrolled content sliding underneath it — the
    classic failure, and it reads as a rendering bug rather than a missing colour. A
    hardcoded #fff is a white stripe down a dark page, which is the same mistake wearing the
    other hat."""
    css = theme.TABLE_CSS
    assert "--cfdb-sticky-bg:#ffffff" in css
    dark = css[css.index("@media (prefers-color-scheme: dark)"):]
    assert "--cfdb-sticky-bg:" in dark, "no dark value — the frozen columns go white"
    assert "background:var(--cfdb-sticky-bg)" in css
    # The row hover is translucent and would let the scrolled content through, so the frozen
    # cells get an opaque equivalent in each theme.
    assert "tr:hover td.cfdb-sticky" in css
    assert "tr:hover td.cfdb-sticky" in dark


def test_the_other_pages_are_untouched_by_the_scroll_flag():
    """Seventeen callers want width:100% and no sticky. Both new arguments default off, so
    adding them cannot have changed a single existing page."""
    import inspect
    signature = inspect.signature(table.render)
    assert signature.parameters["scroll"].default is False
    assert signature.parameters["sticky"].default == 0
    assert signature.parameters["row_class"].default is None
    assert inspect.signature(table.column_layout).parameters["unit"].default == "%"


# --- the page does not reshape the frame ----------------------------------------------------

def test_the_page_reads_the_export_sheets_own_statement():
    """Same scope filters, same compound ORDER BY, same game_no. A page and a workbook that
    disagree about what "the Scores data" is would be the drift this project keeps paying
    for; there is one statement, so they cannot."""
    assert scores.SCORES_SHEET.name == "Scores"
    assert scores.SCORES_SHEET.view == "srv_game_team"
    assert "SCORES_SHEET.sql" in SOURCE

    # EXACTLY ONE OTHER QUERY IS ALLOWED, and it answers a different question. `_unsettled`
    # reads srv_game to say "three games are in progress" — a claim about games that are NOT
    # in the table, which srv_game_team cannot make because a game with no result has no row
    # worth showing. A second query for the SCORES DATA would be the drift; this is not that.
    statements = re.findall(r'query\("""\s*(select\b)', SOURCE, re.IGNORECASE)
    assert len(statements) == 1, (
        f"{len(statements)} inline queries on this page — the scores data comes from the "
        f"sheet's statement, and only the slate caption may ask anything else")
    assert "from srv_game\n" in SOURCE or "from srv_game " in SOURCE


def test_nothing_on_the_page_pivots_or_pairs():
    """The stacking IS the grain. A pivot here would be rebuilding what the query already
    returns, and would be the first place the two rows could disagree."""
    code = "\n".join(line for line in SOURCE.splitlines()
                     if not line.lstrip().startswith("#"))
    for reshape in (".pivot", ".unstack", ".merge(", "groupby"):
        assert reshape not in code, f"{reshape} on a page whose grain is the point"
