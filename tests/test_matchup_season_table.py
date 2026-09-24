"""Marc's per-team season table on Matchup · Before the game (B149).

> **MARC, v15:** *"Between Offense vs Defense and Travel and Rest, add a table for each teams
> schedule w/high-level stats for each team. There are going to be enough stats that probably
> need to make it a tab that allows end-user to toggle between the teams."*

WHAT THIS EXISTS TO CATCH. The panel reads `_game_calendar`, which is BOUNDED to games that
kicked off before this matchup (cfdb-wta-R-1000). A round that gives it its own unbounded read
would put the rest of the season on a *Before the game* tab and look entirely healthy doing it —
that is the defect Marc found live, and the guard below is the thing that can see it come back.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import table as table_lib  # noqa: E402

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()


def _matchup():
    import importlib
    return importlib.import_module("views.matchup")


def _code_of(func: str) -> str:
    """One function's CODE, with its docstring and every comment stripped.

    🚨 **R-2260: A SUBSTRING IS NOT A RULE — AND THIS FILE PROVED IT ON ITSELF.** Two of the
    assertions below first searched the raw body and matched the panel's own COMMENTS, which
    say the words `scroll_note(` and `srv_game_team` while doing neither. **A guard that reads
    prose as code is the same defect it is written to catch.**
    """
    body = SOURCE.split(f"def {func}(")[1].split("\ndef ")[0]
    body = body.split('"""', 2)[-1] if body.count('"""') >= 2 else body
    return "\n".join(
        line for line in body.split("\n") if not line.strip().startswith("#"))


def test_THE_PANEL_SITS_BETWEEN_OFFENCE_VS_DEFENCE_AND_TRAVEL():
    """Marc placed it: *"Between Offense vs Defense and Travel and Rest"*.

    ⚠️ **B152 PUT THE MARKET SECTION BETWEEN THIS TABLE AND *Travel and Rest*, SO MARC'S
    PLACEMENT IS NOW HELD AS AN ORDERING RATHER THAN AS AN ADJACENCY** (cfdb-wta-R-2906).
    ✅ **The half that carries his instruction is unchanged and still exact**: this table
    immediately follows *Offense vs Defense*, and it still sits before *Travel and Rest*.
    🚨 **The `i + 1` clause is not loosened to nothing** — it names the panel that took the
    slot, so a round that drops something else in here turns this red and has to say why.
    """
    tabs = _matchup().TABS
    before = next(panels for slug, _label, panels in tabs if slug == "before")
    assert "_season_so_far" in before, f"the panel is not on the before tab: {before}"
    i = before.index("_season_so_far")
    assert before[i - 1] == "_yardage", f"it does not follow Offense vs Defense: {before}"
    assert before[i + 1] == "_ats_so_far", (
        f"the panel after the season table is no longer B152's market section: {before}")
    assert i < before.index("_travel"), (
        f"it no longer precedes Travel and rest: {before}")


def test_IT_READS_THE_BOUNDED_CALENDAR_rather_than_opening_its_own_read():
    """🚨 **THE LEAKAGE BOUND IS THE WHOLE REASON THIS PANEL DOES NOT HAVE ITS OWN QUERY.**

    `_game_calendar` carries `game_date < :before` — cfdb-wta-R-1000, the defect Marc found on
    the live site: *"this is the Today / Before the Game. It shouldn't present data that
    transpired during the game."* ⚠️ **A fresh `srv_game_team` read would have shipped without
    it**, listing the whole season on a page about an upcoming game.

    ✅ Asserted on the SOURCE because the harness stubs `query` and would answer any SQL with a
    fixture frame — the same reason `test_select_list` exists (B124's break 4).
    """
    code = _code_of("_season_so_far")
    assert "_game_calendar(" in code, (
        "the panel no longer reads `_game_calendar`, so its leakage bound is gone")
    assert "from srv_game_team" not in code, (
        "the panel opened its own `srv_game_team` read; the calendar already fetches both "
        "teams in one bounded query (G-2: one read, two renderings)")


def test_THE_TOGGLE_IS_NOT_ST_TABS_because_that_loses_the_tab_on_every_link():
    """🚨 **R-283, AND IT HAS A TEST ON THE OTHER SIDE TOO.** `st.tabs` loses the tab on every
    link, which is why the page's own Before/After bar is anchors carrying the choice in the
    URL. ⚠️ **It also renders BOTH panes**, so two eighteen-column tables would be built on
    every load to show one.

    ✅ The toggle reuses `params.link_here(team=…)` — and `team` was **already** in
    `params.KNOWN`, so the round needed no `site/lib/` edit (session A's file, §3.2.2).
    """
    code = _code_of("_season_so_far")
    assert "st.tabs(" not in code, "the season table uses st.tabs, which R-283 forbids here"
    assert "link_here(team=" in code, (
        "the toggle does not carry its choice in the URL, so a link resets it")
    from lib import params
    assert "team" in params.KNOWN, (
        "`team` left params.KNOWN, so the toggle's links would be stripped")


def test_TOUCHDOWNS_IS_NAMED_AS_ABSENT_and_never_derived_from_points():
    """🚨 **THE SIXTEENTH STAT MARC ASKED FOR IS NOT PUBLISHED.** Searched all 243 columns of
    `srv_game_team` for `touchdown|_td|td_`: none.

    ⚠️ **AND IT MUST NOT BE COMPUTED FROM POINTS.** Points include field goals, safeties and
    two-point conversions, so a derived touchdown count would be **wrong and would look right**
    — which is worse than an absence that says so (AC-G.11).
    """
    note = _matchup()._SEASON_TD_NOTE
    assert "ouchdown" in note, f"the note does not name touchdowns: {note!r}"
    assert "field goal" in note.lower(), (
        "the note does not say WHY points cannot stand in for touchdowns")
    # 🚨 **THE FIRST VERSION LISTED LITERAL SPELLINGS AND CAME BACK GREEN** (R-744): the break
    # wrote `played["points_for"] / 7`, which contains none of them. **A substring is not a
    # rule** (R-2260) — so this asserts the PROPERTY: the panel performs no arithmetic on the
    # scoring columns at all, however it is spelled.
    code = _code_of("_season_so_far")
    for line in code.split("\n"):
        if "points_for" not in line and "points_against" not in line:
            continue
        for op in ("/", "*", "+", "-"):
            assert op not in line, (
                f"the panel does arithmetic on a scoring column, which is how a touchdown "
                f"count gets derived from points: {line.strip()!r}")


def test_EVERY_COLUMN_READS_A_PUBLISHED_FIELD_and_none_is_summed_in_the_page():
    """🚨 §4.2.1. **`cumulative_ppa_overall_total` IS ALREADY A PUBLISHED RUNNING TOTAL.**
    A running sum computed here would be arithmetic ACROSS ROWS — the breach the charter exists
    to prevent — and it would agree with the published column often enough to look right.
    """
    cols = _matchup()._season_table_columns()
    # 🚨 **THE PAIRS ARE PINNED, NOT THE COUNT — AND A STAGED BREAK IS WHY.** Swapping
    # `total_yards_allowed` for `total_yards` under the label `Yds Allw` kept eighteen columns
    # and came back GREEN against the first version of this test (R-744). **A count cannot see
    # a swap**, which is `test_select_list`'s own lesson arriving one file over.
    assert [(c.label, c.field) for c in cols] == [
        ("Wk", "week"), ("Opponent", "opponent"), ("Result", "result"),
        ("1st Dn", "first_downs"), ("Yards", "total_yards"),
        ("Rush", "rushing_yards"), ("Pass", "passing_yards"),
        ("TO", "turnovers"), ("Pen Yds", "penalty_yards"),
        ("PPA", "offense_ppa"),
        ("Rush PPA", "offense_rushing_plays_total_ppa"),
        ("Pass PPA", "offense_passing_plays_total_ppa"),
        ("Cum PPA", "cumulative_ppa_overall_total"),
        ("Success", "offense_success_rate"), ("Expl", "offense_explosiveness"),
        ("Yds Allw", "total_yards_allowed"), ("Pass Allw", "passing_yards_allowed"),
        ("Rush Allw", "rushing_yards_allowed"),
    ], "a column's label and its field no longer agree"
    fields = [c.field for c in cols]
    assert "cumulative_ppa_overall_total" in fields, "the published running total is not read"
    code = _code_of("_season_so_far")
    for summing in (".cumsum(", ".sum()", "expanding("):
        assert summing not in code, (
            f"the panel calls {summing!r} — the cumulative column is READ, never accumulated")
    # every column either names a field or renders from the row; none invents a number
    assert len(cols) == 18, f"expected 18 columns, got {len(cols)}"


def test_THE_LAYOUT_IS_ALL_PIXELS_so_the_scroll_note_has_a_boundary():
    """🚨 **A TABLE WITH NO DECLARED MINIMUM DRAWS NO NOTE AT ALL**, and that is the state the
    first version of this panel shipped in: it emitted `scroll_note` ITSELF, outside the
    `.cfdb-scrollbox`, where a CONTAINER query can never fire. 📊 Measured at 1600 with the
    sidebar open: the table drew **1275px inside a 1140px box** with the note hidden.

    ✅ `render(scroll=True, layout=…)` owns the affordance — A208's, not a second one
    (cfdb-wta-R-2703).
    """
    layout = _matchup()._SEASON_LAYOUT
    assert len(layout) == len(_matchup()._season_table_columns()), (
        "the layout and the column list have different lengths, so the widths are off by one")
    assert all(w.endswith("px") for w in layout), (
        "a non-pixel width makes `scroll_minimum` return None and the note disappears")
    assert table_lib.scroll_minimum(layout) == 1274, (
        f"the declared minimum moved to {table_lib.scroll_minimum(layout)}; if that is "
        f"deliberate, re-measure the drawn width in a browser and say so")
    code = _code_of("_season_so_far")
    # 🚨 **AND THE CALL MUST ACTUALLY PASS IT.** Deleting `layout=` from the render leaves this
    # constant perfectly correct and the table with no declared minimum — the first version of
    # this test inspected only the constant and came back GREEN (R-744).
    assert "layout=_SEASON_LAYOUT" in code, (
        "the render call no longer passes the layout, so `scroll_minimum` gets None and the "
        "scroll note vanishes while `_SEASON_LAYOUT` still looks right")
    assert "scroll=True" in code, "the table is no longer inside A208's shared scroll wrapper"
    assert "scroll_note(" not in code, (
        "the panel emits its own scroll note again — `render` already does, inside the "
        "container the note's query reads")
