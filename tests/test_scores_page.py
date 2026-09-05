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

def test_the_tabs_and_the_hidden_set_partition_the_sheet_exactly():
    """R-279. THE RULE CHANGED AND THE TEST HAD TO CHANGE WITH IT, IN THE HARDER DIRECTION.

    It used to be "every sheet column appears on exactly one tab" — Marc's "include all the
    columns". He then asked for six of them to leave the web interface and stay in the file,
    so that assertion is no longer true and cannot simply be relaxed to "at most one": that
    would let a column vanish by accident, which is what the original existed to prevent.

    A PARTITION IS WHAT KEEPS IT IMPOSSIBLE. Every sheet column is on a tab or explicitly
    hidden with a reason, never both and never neither — so a new column must be assigned or
    declared, and forgetting it fails here.
    """
    everything = {field for field, _ in workbook.SCORES_COLUMNS}
    union, twice = set(), []
    for _slug, _label, blocks in scores.TABS:
        own = set(scores.tab_fields(blocks)) - set(scores.FROZEN)
        twice += sorted(union & own)
        union |= own
    shown = union | set(scores.FROZEN)
    hidden = set(scores.HIDDEN_ON_PAGE)

    assert twice == [], twice
    assert not (shown & hidden), sorted(shown & hidden)
    assert shown | hidden == everything, {
        "in neither": sorted(everything - shown - hidden),
        "not a sheet column": sorted((shown | hidden) - everything)}
    assert len(everything) == 151

    # Every hidden column carries a REASON, because "hidden" without one is indistinguishable
    # from "forgotten" the next time somebody reads the list.
    for field, why in scores.HIDDEN_ON_PAGE.items():
        assert why and len(why) > 12, (field, why)

    # And the export-only column is hidden by definition, not by coincidence.
    assert "matchup_url" in hidden


def test_the_tabs_are_built_from_the_blocks_not_from_a_copied_list():
    """A second list of field names would be a second thing to maintain, and it would drift
    the first time a column joined a band. The mapping is tab label -> block name."""
    assert "workbook.SCORES_BLOCKS" in SOURCE
    block_names = {name for name, _ in workbook.SCORES_BLOCKS}
    named = {b for _slug, _label, blocks in scores.TABS for b in blocks}
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
                 if workbook.SCORES_CATEGORY[f] == "Ancillary"
                 and f not in scores.HIDDEN_ON_PAGE]
    assert game_results[-len(ancillary):] == ancillary, "ancillary is not at the far right"


def test_the_frozen_block_leads_every_tab_in_the_same_order():
    """"The identifying rows should be frozen and hold consistent with several different
    tabs." Same four, same order, first on all six — a frozen block that moved between tabs
    would be worse than none."""
    assert scores.FROZEN == ("game_no", "game_date", "team_rank", "team",
                             "record_before_display", "points_for", "won")
    for _slug, _label, blocks in scores.TABS:
        assert scores.tab_fields(blocks)[:len(scores.FROZEN)] == list(scores.FROZEN)
    # Rank immediately before the team it qualifies, record immediately after.
    assert scores.FROZEN.index("team_rank") + 1 == scores.FROZEN.index("team")
    assert scores.FROZEN.index("team") + 1 == scores.FROZEN.index("record_before_display")


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


def test_the_theme_tokens_are_live_rather_than_resolved_from_anywhere():
    """TWO EARLIER ATTEMPTS ASKED THE WRONG SOURCE AND BOTH WERE VISIBLY WRONG.

      prefers-color-scheme  reports what the OPERATING SYSTEM prefers. A reader on a dark
                            system who switches the app to Light gets a light page painted
                            with dark cells — Marc: "the color and banding is pretty jacked
                            up."
      st.context.theme      reports what the app is rendering, but only when Python next
                            runs. The theme repaints immediately and the tokens lagged a
                            rerun, so some frozen cells kept the old colour until a tab
                            change forced another pass — Marc: "misses some of the Frozen
                            columns... requires a reload."

    Streamlit sets `color-scheme` on its container from the ACTIVE theme, so CSS system
    colours follow it in the same frame. Nothing to synchronise, nothing to go stale.

    A TRANSPARENT sticky cell is still the failure being prevented — it shows the scrolled
    content sliding underneath — so the tokens must resolve to a real colour, not to
    `transparent` or `inherit`.
    """
    css = theme.TABLE_CSS
    assert "--cfdb-sticky-bg: Canvas" in css
    for token in ("--cfdb-band-bg", "--cfdb-hover-bg", "--cfdb-muted", "--cfdb-rule"):
        assert f"{token}:" in css, token
        line = css[css.index(f"{token}:"):]
        line = line[:line.index(";")]
        assert "Canvas" in line, f"{token} is not derived from the live page colour: {line}"
        assert "transparent" not in line and "inherit" not in line

    # The dark media block must NOT redefine them — a value there would override the live
    # one with a guess about the operating system, which is the defect it used to contain.
    dark = css[css.index("@media (prefers-color-scheme: dark)"):]
    for token in ("--cfdb-sticky-bg", "--cfdb-band-bg", "--cfdb-hover-bg", "--cfdb-muted"):
        assert f"{token}:" not in dark, f"{token} is guessed from the OS again"

    # And no Python is in the loop.
    assert not hasattr(theme, "THEME_TOKENS")
    assert not hasattr(theme, "resolved_theme_css")
    # PARSED, NOT GREPPED. The stale source is named in two comments on purpose — one of
    # them inside the CSS string, where a `#` filter cannot see it — and recording why it was
    # wrong is worth more than the assertion's convenience. An AST walk asks the only
    # question that matters: does anything EXECUTE it.
    import ast
    tree = ast.parse(Path(theme.__file__).read_text())
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr == "theme"
             and isinstance(n.value, ast.Attribute) and n.value.attr == "context"]
    assert not reads, "theme.py reads st.context.theme again — it lags a rerun"

    assert "background:var(--cfdb-sticky-bg)" in css
    assert "tr:hover td.cfdb-sticky { background:var(--cfdb-hover-bg)" in css


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


# --- round 2 ---------------------------------------------------------------------------------

def test_the_page_asks_for_completed_games_and_the_sheet_does_not():
    """R-278. The divergence is a bound parameter on ONE statement, not a second query."""
    assert '"completed_only": True' in SOURCE
    assert ":completed_only" in scores.SCORES_SHEET.sql


def test_a_numeric_column_carries_a_comma_exactly_when_the_sheet_does():
    """R-280. THE PROPERTY, OVER EVERY NUMERIC COLUMN AT ONCE.

    Spot-checking `season` would have passed the day `game_id` broke. The page's rendered
    string must contain a comma if and only if the sheet's number format for that field
    contains `#,##0` — which asserts the two surfaces agree about all of them together.
    """
    sheet = scores.SCORES_SHEET
    checked = 0
    for field, _label in workbook.SCORES_COLUMNS:
        fmt = workbook.number_format(field, sheet.decimals, sheet.integer_fields,
                                     sheet.site_precision)
        if not fmt.startswith(("0", "#,##0", "+#")):
            continue
        kind, dp = scores._kind(field, pd.Series([1234567], dtype="int64"))
        if kind not in ("plain", "num", "signed"):
            continue
        rendered = Col(field, "x", kind, dp=dp).format({field: 1234567})
        sheet_groups = "#,##0" in fmt
        assert ("," in rendered) == sheet_groups, (
            f"{field}: page {rendered!r}, sheet format {fmt!r}")
        checked += 1
    assert checked > 100, checked

    # The two that were wrong, named so the regression is legible.
    assert Col("season", "Season", "plain", dp=0).format({"season": 2025}) == "2025"
    assert Col("game_id", "Game id", "plain", dp=0).format(
        {"game_id": 401752817}) == "401752817"


def test_the_comma_test_can_fail(monkeypatch):
    """Negative test for the loop above: collapse the split back and it must go red."""
    original = scores._kind
    monkeypatch.setattr(scores, "_kind",
                        lambda f, s: ("num", 0) if original(f, s)[0] == "plain"
                        else original(f, s))
    with __import__("pytest").raises(AssertionError):
        test_a_numeric_column_carries_a_comma_exactly_when_the_sheet_does()


def test_every_tab_survives_a_sort_and_a_reset(monkeypatch):
    """R-283. ALL SIX, NOT ONE — five of them are the ones that were broken.

    The tab is a URL parameter and `params.link_here` preserves every known parameter, so
    the sort links and the reset link carry it without either knowing it exists. That is the
    fix being structural rather than a helper somebody has to remember.
    """
    from lib import params
    for slug, _label, _blocks in scores.TABS:
        current = {"tab": slug, "season": "2025", "week": "2"}
        monkeypatch.setattr(params.st, "query_params", dict(current))

        sort_href = params.link_here(sort="total_yards", order="desc")
        assert f"tab={slug}" in sort_href, sort_href
        assert "sort=total_yards" in sort_href

        reset_href = params.link_here(sort=None, order=None)
        assert f"tab={slug}" in reset_href, reset_href
        assert "sort=" not in reset_href and "order=" not in reset_href
        assert "season=2025" in reset_href, "the reset threw away the scope"


def test_an_unknown_tab_falls_back_rather_than_raising(monkeypatch):
    """A hand-edited `?tab=` is noise, not a request (AC-G.11)."""
    monkeypatch.setattr(scores.params, "get", lambda k: "nonsense" if k == "tab" else None)
    assert scores._active_tab() == scores.TABS[0]
    monkeypatch.setattr(scores.params, "get", lambda k: "offense" if k == "tab" else None)
    assert scores._active_tab()[1] == "Offense"


def test_the_team_cell_draws_a_logo_and_only_badges_a_ranked_team():
    """R-284. Through `table.team_cell`, which already obeys AC-1.5 — an unranked team shows
    NO badge, not an em dash in one. A second team cell would not."""
    ranked = table.team_cell({"team": "Auburn", "team_slug": "auburn",
                              "team_logo_url": "https://x/a.png", "team_rank": 7},
                             "team_slug", "team", "team_logo_url", "team_rank")
    assert "cfdb-rank" in ranked and "#7" in ranked and "<img" in ranked

    unranked = table.team_cell({"team": "Rice", "team_slug": "rice",
                                "team_logo_url": None, "team_rank": None},
                               "team_slug", "team", "team_logo_url", "team_rank")
    assert "cfdb-rank" not in unranked, "an unranked team was badged"
    assert "Rice" in unranked


def test_the_team_link_refuses_to_point_nowhere():
    """R-287. 996 anchors, 1 distinct href, 0 carrying a team. `team_link` returns None where
    the slug is missing — the page hand-rolled the href instead, and `params.link` silently
    DROPS a None parameter, so what came back was a syntactically perfect URL missing the one
    thing it exists to carry."""
    builder = table.team_link("team_slug")
    assert builder({"team_slug": None, "season": 2025}) is None
    assert builder({"team_slug": "auburn", "season": 2025}) is not None
    # CODE, NOT PROSE. The comment beside the fix quotes the broken call, and quoting the
    # bug where the fix lives is worth more than the assertion's convenience.
    code = "\n".join(line for line in SOURCE.splitlines()
                     if not line.lstrip().startswith("#"))
    assert "team_link(" in code
    assert 'scope.link("team"' not in code, "the hand-built team href is back"


def test_the_matchup_affordance_is_visible_and_not_in_the_scrolling_region():
    """R-288. The links were correct and had no cue but a pointer cursor, which a touch
    device never shows. The glyph sits at the right edge of the FROZEN block — appended to
    the scrolling columns it would be 8,322px from the team name on Offense."""
    assert "details_col" in SOURCE
    assert "columns.insert(len(FROZEN)" in SOURCE
    assert "sticky=len(FROZEN) + 1" in SOURCE


def test_the_header_wraps_instead_of_widening_its_column():
    """R-282. The label used to set a FLOOR under the width, so a long header widened its
    column rather than wrapping inside it — backwards from the ask. R-217 already ruled on
    this for the workbook; the page, built second, did not inherit it."""
    frame = pd.DataFrame({"x": [1, 2]})
    wide = [Col("x", "A Very Long Header Indeed", "num")]
    seeded = table.column_layout(frame, wide, unit="px", seed_from_label=True)
    unseeded = table.column_layout(frame, wide, unit="px", seed_from_label=False)
    assert int(unseeded[0][:-2]) < int(seeded[0][:-2]), (seeded, unseeded)

    # And the height is COMPUTED from the wrap that width forces, not chosen.
    assert table.header_lines(wide, unseeded) > table.header_lines(wide, seeded)
    assert table.header_lines(wide, ["4000px"]) == 1
    assert table.header_lines(wide, unseeded) <= table.HEADER_LINE_CAP


def test_the_scroll_box_has_a_height_and_a_sticky_header_with_a_layered_corner():
    """R-281. The container had NO height constraint — scrollHeight 6275 in a 917px window —
    so the horizontal bar sat about 5,300px below the fold.

    THE CORNER IS THE CELL NO ONE CHECKS. Frozen-left AND in the sticky header, it has to
    outrank both; at equal z-index it renders in DOM order and looks fine until a row scrolls
    under it.
    """
    css = theme.TABLE_CSS
    assert "max-height:" in css and "overflow-y:auto" in css
    assert "thead th { position:sticky" in css and "top:0" in css

    def layer(selector):
        block = css[css.index(selector):]
        return int(block[block.index("z-index:") + 8:].split(";")[0])

    body_frozen = layer(".cfdb-table th.cfdb-sticky, .cfdb-table td.cfdb-sticky")
    header_row = layer(".cfdb-scroll .cfdb-table thead th {")
    corner = layer(".cfdb-scroll .cfdb-table thead th.cfdb-sticky")
    assert corner > header_row > body_frozen, (corner, header_row, body_frozen)


def test_the_sticky_header_is_opaque_because_opacity_hides_nothing():
    """⚠ THE GHOSTING, AND ITS CAUSE WAS ONE INHERITED DECLARATION.

    `.cfdb-table th` carries `opacity:.65` — harmless while headers sat opaque against the
    page, and fatal once they became sticky, because OPACITY APPLIES TO THE WHOLE CELL,
    background included. A 65% header cannot hide anything sliding underneath it, so rows
    scrolled through their own column labels and the two sets of text overlapped.

    Marc: "Can we mute the fields when they slide behind. I find that more distracting than
    informative." The muting is done by COLOUR now, which does not make the cell see-through.
    """
    css = theme.TABLE_CSS
    header = css[css.index(".cfdb-scroll .cfdb-table thead th {"):]
    header = header[:header.index("}")]
    assert "opacity:1" in header, "the sticky header is translucent and will ghost"
    assert "background:var(--cfdb-sticky-bg)" in header
    assert "--cfdb-muted" in header, "muted by opacity again rather than by colour"

    # And the frozen body cells, for the same reason from the other direction.
    assert ".cfdb-scroll .cfdb-table td.cfdb-sticky { opacity:1; }" in css

    # The base rule that caused it is still there — it is right for a non-scrolling table,
    # and this asserts the override exists rather than that the cause was removed.
    assert "opacity:.65" in css


def test_the_tab_bar_has_rules_and_not_just_class_names():
    """It shipped as bare anchors: classes emitted, no CSS written, so six tabs rendered as a
    run of underlined links with no spacing. Marc: "The Tabs also regressed to just look like
    hyperlinks." """
    css = theme.TABLE_CSS
    assert ".cfdb-tabbar {" in css and ".cfdb-tab {" in css and ".cfdb-tab-on {" in css
    bar = css[css.index(".cfdb-tabbar {"):]
    assert "display:flex" in bar[:200]
    tab = css[css.index(".cfdb-tab {"):]
    assert "text-decoration:none" in tab[:260], "still reads as a hyperlink"


def test_an_unranked_team_renders_an_empty_cell_not_a_dash():
    """Marc: "NULL (empty) for Rank if it doesn't exist." Most teams are unranked, so a
    column of em dashes is a column of noise — and a dash reads as "we hold nothing", where
    the truth is "this team is not in the poll", which is a fact rather than a gap."""
    frame = pd.DataFrame([{"team_rank": 7.0}, {"team_rank": None}])
    cols = scores._columns(["team_rank"], frame, None)
    assert cols[0].format({"team_rank": 7.0}) == "7"
    assert cols[0].format({"team_rank": None}) == ""
    assert cols[0].format({"team_rank": float("nan")}) == ""


def test_the_page_names_the_poll_behind_the_rank_column():
    """A "#21" with no poll named is a number with no authority behind it, and fct_game joins
    exactly one poll on purpose — `poll_name = 'AP Top 25'`."""
    assert scores.RANK_POLL == "AP Top 25"
    assert "RANK_POLL" in SOURCE
    marts = (Path(__file__).resolve().parents[1] / "dbt" / "models" / "marts"
             / "fct_game.sql").read_text()
    assert f"poll_name = '{scores.RANK_POLL}'" in marts, (
        "the page names a poll the mart does not join")


def test_both_elo_columns_are_whole_numbers_with_a_thousands_separator():
    """Marc: "Both ELOs should be INT", then "Make ELO #,###".

    R-216's rule — a comma is for a quantity you might total — first put Elo with the LABELS,
    on the argument that a rating is not a count. Marc overruled it while reading the column,
    and the distinction the rule was reaching for turns out to be identifier vs magnitude: a
    season and a game id are names that happen to be numeric, an Elo is a magnitude you
    compare, and at four digits the group is what makes a column of them scannable.
    """
    sheet = scores.SCORES_SHEET
    for field in ("pregame_elo", "postgame_elo", "elo_delta"):
        assert workbook.number_format(field, sheet.decimals, sheet.integer_fields,
                                      sheet.site_precision) == "#,##0", field
        kind, dp = scores._kind(field, pd.Series([1543.62]))
        assert (kind, dp) == ("num", 0), (field, kind, dp)
    assert Col("pregame_elo", "x", "num", dp=0).format({"pregame_elo": 1543.62}) == "1,544"

    # And the identifiers keep the rule: a season is still not "2,025".
    for field in ("season", "game_id"):
        assert workbook.number_format(field, sheet.decimals, sheet.integer_fields,
                                      sheet.site_precision) == "0", field


def test_postgame_elo_is_in_the_file_and_not_on_the_page():
    """Marc: "I would suppress Postgame ELO in the web interface (keep in Excel)." The delta
    is what a reader wants from the pair and it sits beside the pregame rating, so the
    postgame value is one subtraction away and costs a column to show."""
    assert "postgame_elo" in scores.HIDDEN_ON_PAGE
    assert "postgame_elo" in {f for f, _ in workbook.SCORES_COLUMNS}
    on_a_tab = {f for _s, _l, b in scores.TABS for f in scores.tab_fields(b)}
    assert "postgame_elo" not in on_a_tab
    assert "elo_delta" in on_a_tab, "the delta has to be there if the rating is not"


def test_the_win_column_reuses_schedules_glyph_and_reads_the_result():
    """Marc: "can we add a Win column that has the glyph we use on Schedule."

    THE SAME COMPONENT, NOT A SECOND ONE. Two pages marking a winner with two different
    characters is worse than either character — R-100's "a relocation, not a new component".
    A glyph rather than a colour, so it survives greyscale and a colour-blind reader.

    And it is DERIVED FROM `result`, which is read from the view. Comparing the two scores is
    what disagreed with srv_game on 1 game in 295 the first time it met real data, and a tie
    is the case it gets wrong.
    """
    from views import schedule
    assert scores.WIN_GLYPHS["Yes"] == schedule.WINNER_GLYPH
    assert scores.WIN_GLYPHS["Tie"] == schedule.TIE_GLYPH

    sheet = scores.SCORES_SHEET
    assert sheet.value_for("won", {"result": "W"}) == "Yes"
    assert sheet.value_for("won", {"result": "L"}) == "No"
    assert sheet.value_for("won", {"result": "T"}) == "Tie"
    assert sheet.value_for("won", {"result": None}) is None

    frame = pd.DataFrame([{"won": "Yes"}, {"won": "No"}, {"won": "Tie"}])
    col = scores._columns(["won"], frame, None)[0]
    assert schedule.WINNER_GLYPH in col.format({"won": "Yes"})
    assert "cfdb-winner" in col.format({"won": "Yes"})
    # NOTHING on a loss: the marker's job is to find the winner in a stack of 166 rows, and a
    # second glyph meaning "not this one" is 83 more things to read.
    assert col.format({"won": "No"}) == ""
    assert schedule.TIE_GLYPH in col.format({"won": "Tie"})


def test_the_win_column_is_frozen_immediately_after_points_for():
    """Marc: "It should be right after PTS FOR and Frozen on the left." """
    assert scores.FROZEN[-1] == "won"
    assert scores.FROZEN[-2] == "points_for"
    sheet = scores.SCORES_SHEET
    order = [f for f, _ in sheet.columns]
    assert order[order.index("points_for") + 1] == "won"
