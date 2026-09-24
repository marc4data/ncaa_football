"""Marc's ATS section on Matchup · Before the game (B152).

> **MARC, v16:** *"Will also want an ATS section."*

WHAT THIS EXISTS TO CATCH, and it is not the layout. **The section answers *did THIS team cover*,
which `srv_game_team` publishes at team-game grain — `covered_final`, `spread_final`,
`ats_margin_final`, all three 100% populated on completed FBS team-games.** Two things could
quietly make it lie:

1. 🚨 **READING THE GAME-GRAIN COLUMN INSTEAD.** `srv_game.favorite_covered` answers *did the
   FAVOURITE cover*, which is a different question, and turning it into this one needs to know
   which side this team was on — a join, not a page expression (§4.2.1). ⚠️ **It would render
   perfectly and be wrong for exactly the underdogs.**
2. 🚨 **COMPUTING A RECORD.** An as-of ATS record IS published — `srv_team_overview` and
   `srv_standings` both carry `ats_record_display` — but **one row per team-SEASON, the FULL
   season**, so showing one here is cfdb-wta-R-1000 and computing one here is §4.2.1. **This
   section publishes no rate at all, and the tests below assert that absence rather than trust
   it.**
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_harness  # noqa: E402
from lib import table as table_lib  # noqa: E402

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()

AWAY, HOME = 333, 2390


def _matchup():
    import importlib
    return importlib.import_module("views.matchup")


def _code_of(func: str) -> str:
    """One function's CODE, with its docstring and every comment stripped.

    🚨 **R-2260, AND B149 PROVED IT ON ITSELF ONE FILE OVER:** two of its assertions first
    searched the raw body and matched the panel's own COMMENTS, which say `srv_game_team` while
    doing nothing of the kind. **A guard that reads prose as code is the defect it exists to
    catch**, and this panel's comments name `favorite_covered`, `srv_standings` and
    `ats_record_display` precisely because it does NOT read them.
    """
    body = SOURCE.split(f"def {func}(")[1].split("\ndef ")[0]
    body = body.split('"""', 2)[-1] if body.count('"""') >= 2 else body
    return "\n".join(
        line for line in body.split("\n") if not line.strip().startswith("#"))


def _caption_expression_of(func: str) -> str:
    """Just the `caption = (...)` expression of one panel, comments stripped.

    ⚠️ **NARROWER THAN `_code_of` ON PURPOSE.** The question *does the caption name the
    relation* is about the sentence the reader sees, and both panels legitimately name
    `srv_game_team` one line earlier — in `states.section(...)`, which is what renders the
    human dataset label the raw name was duplicating.
    """
    code = _code_of(func)
    assert "caption = (" in code, f"{func} no longer builds a caption expression"
    tail = code.split("caption = (", 1)[1]
    return tail.split("table.render", 1)[0]


def _game(**over):
    row = {
        "game_id": 401752766, "season": 2025, "season_type": "regular",
        "game_date": "2025-10-04",
        "home_team_id": HOME, "away_team_id": AWAY,
        "home_team": "Baylor", "away_team": "Oklahoma State",
        "home_team_slug": "baylor", "away_team_slug": "oklahoma-state",
    }
    row.update(over)
    return pd.Series(row)


def _calendar_row(team_id, week, **over):
    """One team-game, carrying every column `_CALENDAR_COLUMNS` selects that this panel reads."""
    row = {
        "team_id": team_id, "week": week, "game_date": f"2025-09-{week:02d}",
        "is_home": True, "opponent_abbreviation": f"OP{week}",
        "opponent_team_display": f"Opponent {week}", "opponent_rank": None,
        "opponent_classification": "fbs",
        "record_before_display": "1-0", "points_for": 31, "points_against": 17,
        "has_box_score": True,
        "spread_final": -7.5, "covered_final": "yes", "ats_margin_final": 6.5,
    }
    row.update(over)
    return row


@pytest.fixture
def panel():
    """`_ats_so_far` with streamlit captured and the calendar query replaced.

    ⚠️ **IT PUTS THE MODULES BACK, AND `streamlit_stubbed` IS THE THING THAT DOES IT** — both
    halves, `sys.modules` and the parent-package attribute (A101). Rolling a stub by hand here
    is what left `test_matchup_yardage.py` outside B092's guard.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (stub, captured, _charts):
        matchup = importlib.reload(importlib.import_module("views.matchup"))
        seen = {}

        def run(rows, game=None, team=None):
            """`team` is kept ONLY so a test can prove the parameter changes nothing."""
            captured.clear()
            seen.clear()
            seen["queries"] = []

            def fake_query(sql, params=None):
                seen["queries"].append(sql)
                return pd.DataFrame(rows)

            matchup.query = fake_query
            stub.query_params = {} if team is None else {"team": team}
            matchup._ats_so_far(game if game is not None else _game())
            return render_harness.body_html(captured)

        yield run, seen, matchup


# ── the two ways this section could lie ─────────────────────────────────────────────────────

def test_THE_SECTION_ANSWERS_DID_THIS_TEAM_COVER_not_did_the_favorite_cover():
    """🚨 **PART 0's GATE, ASSERTED.** `covered_final` is published at TEAM-game grain, so *did
    this team cover* is a read. `favorite_covered` is game grain and answers a different
    question; converting it needs which side this team was on — **a join, not a page
    expression** (§4.2.1).

    ⚠️ **THE PAIRS ARE PINNED, NOT THE COUNT** (B149's R-744 lesson): swapping the field under
    a label keeps five columns and would come back GREEN against a count.
    """
    cols = _matchup()._ats_table_columns()
    assert [(c.label, c.field) for c in cols] == [
        ("Wk", "week"),
        ("Opponent", "opponent"),
        ("Spread", "spread_final"),
        ("ATS", "covered_final"),
        ("vs Spread", "ats_margin_final"),
    ], "a column's label and its field no longer agree"
    code = _code_of("_ats_so_far") + _code_of("_ats_covered") + _code_of("_ats_table_columns")
    for game_grain in ("favorite_covered", "spread_favorite_side", "spread_at_close"):
        assert game_grain not in code, (
            f"the section reads {game_grain!r}, which is game grain: it answers whether the "
            f"FAVORITE covered, not whether THIS team did, and the two differ for every "
            f"underdog")


def test_THE_SECTION_PUBLISHES_NO_ATS_RECORD_because_the_published_one_is_the_full_season():
    """🚨 **THE ROUND'S REAL FINDING, HELD AS A TEST.** `srv_team_overview.ats_record_display`
    and `srv_standings.ats_record_display` are **one row per team-season** — 684 rows for 684
    teams in 2026 — so they are the FULL season record. ⚠️ **On *Before the game* that is
    cfdb-wta-R-1000**, the leak Marc found live, and **computing an as-of one here is §4.2.1**:
    a record is precisely a quantity with a second consumer.

    ✅ **So the absence is asserted, not assumed** — including the arithmetic that would build
    one quietly.
    """
    code = _code_of("_ats_so_far") + _code_of("_ats_covered") + _code_of("_ats_table_columns")
    for published in ("srv_team_overview", "srv_standings", "ats_record_display",
                      "ats_wins", "ats_losses", "ats_pushes"):
        assert published not in code, (
            f"the section reads {published!r}; those are team-SEASON grain, so on the "
            f"before-the-game tab they are the whole season's record (cfdb-wta-R-1000)")
    # 🚨 **AND NO RECORD IS BUILT HERE EITHER.** A count of covers is one `==` and a `.sum()`
    # away, and it would look right while disagreeing with the published full-season record one
    # click away. **The property, not a list of spellings** (R-2260).
    for building in (".sum()", ".value_counts(", ".mean()", "fmt.percent"):
        assert building not in code, (
            f"the section calls {building!r}, which is how a record or a rate gets computed "
            f"in the page (§4.2.1)")


# ── the four states, and which absence an absence is ────────────────────────────────────────

def test_A_PUSH_IS_NOT_A_COVER_and_an_absent_line_is_not_a_push():
    """🚨 **FOUR STATES AT TEAM GRAIN AND THEY MUST READ DIFFERENTLY.** 📊 Measured on 2025+:
    `yes` 1,979 · `no` 1,979 · `push` 54 (every one with `ats_margin_final` exactly 0.0) ·
    `pending` 142 (none completed) · null 10,866 (every one a game with no published line).

    ⚠️ **AND `no_favorite` DOES NOT OCCUR HERE** — the prompt's five-state framing is
    `srv_game.favorite_covered`'s. A pick'em has no favorite, but *did this team cover* is
    still well-formed, and the two pick'em team-games on record answer it `yes` and `no`.
    """
    ats = _matchup()
    labels = {state: ats._ats_covered({"covered_final": state})
              for state in ("yes", "no", "push", "pending")}
    assert len(set(labels.values())) == 4, (
        f"two of the four published states render the same words: {labels}")
    assert labels["push"] != labels["yes"], "a push reads as a cover"
    assert labels["push"] != labels["no"], "a push reads as a failure to cover"
    # null is a game with NO PUBLISHED LINE, which is a different fact from a push (AC-G.11)
    for absent in (None, float("nan"), ""):
        assert ats._ats_covered({"covered_final": absent}) == ats.fmt.EM_DASH, (
            f"an absent verdict ({absent!r}) does not render as an em dash, so a game with no "
            f"line is indistinguishable from one with a result")


def test_AN_UNKNOWN_STATE_IS_SHOWN_rather_than_silently_relabelled():
    """⚠️ **A FIFTH STATE UPSTREAM MUST NOT ARRIVE AS ONE OF THE FOUR.** §2.5's family: a value
    the page has never seen is not the same as an absence, and mapping it to *No* would read as
    a measured verdict.
    """
    assert _matchup()._ats_covered({"covered_final": "no_favorite"}) == "no_favorite"


# ── the bound, the caption, the sign, the place ──────────────────────────────────────────────

def test_IT_READS_THE_BOUNDED_CALENDAR_rather_than_opening_its_own_read():
    """🚨 **cfdb-wta-R-1000.** `_game_calendar` carries `game_date < :before`; a fresh
    `srv_game_team` read would not, and would list games that have not happened on a page about
    a game that has not happened.
    """
    code = _code_of("_ats_so_far")
    assert "_game_calendar(" in code, "the section no longer reads the bounded calendar"
    assert "from srv_game_team" not in code, (
        "the section opened its own `srv_game_team` read; the calendar already fetches both "
        "teams in one bounded query (G-2: one read, two renderings)")


def test_THE_SECTION_ADDS_NO_SECOND_QUERY(panel):
    """📊 **B149 joined seven stat columns to the read that was already happening; this round
    joined three. Asserted by COUNTING THE QUERIES THE PANEL ISSUES**, because the source check
    above cannot see a read that goes through a helper.
    """
    run, seen, _matchup_mod = panel
    run([_calendar_row(AWAY, w) for w in (1, 2)] + [_calendar_row(HOME, w) for w in (1, 2)])
    assert len(seen["queries"]) == 1, (
        f"the section issued {len(seen['queries'])} queries; it must read the calendar once "
        f"and nothing else: {seen['queries']}")
    assert "game_date < :before" in seen["queries"][0], (
        "the one query the section issues has no leakage bound on it")


def test_THE_CAPTION_STATES_ITS_DENOMINATOR_and_names_the_season(panel):
    """🚨 **A214's RULE — *a percentage with an unstated denominator is AC-G.11 wearing a
    number*.** ✅ **This section publishes no percentage, so the caption's job is the counts:
    how many of the games before this one carried a published line.**

    ⚠️ **AND IT SAYS WHICH SEASON**, because *before this one* is meaningless without it.
    """
    run, _seen, _m = panel
    html = run([_calendar_row(AWAY, 1),
                _calendar_row(AWAY, 2, spread_final=None, covered_final=None,
                              ats_margin_final=None),
                _calendar_row(AWAY, 3)],
               )
    assert "3 of 3" not in html, "the caption counts a game with no line as though it had one"
    assert "2 of 3 games before this one carried a published line" in html, (
        f"the caption does not state both the numerator and its denominator: {html[-800:]}")
    assert "1 had no line and shows an em dash" in html, (
        "the caption does not say what happened to the game with no line")
    assert "2025 season" in html, f"the caption does not name the season: {html[-800:]}"


def test_THE_CAPTION_DOES_NOT_NAME_THE_RELATION_because_the_section_header_already_does(panel):
    """📊 **PART 3.1, AND IT APPLIES TO BOTH SECTIONS.** B149's caption read *"9 games played
    before this one. Source: srv_game_team, 2025."* while the line above it already rendered
    the site's own dataset label through `states.section("srv_game_team", dataset=…)`, linked to
    the Data Dictionary. ⚠️ **So the raw relation name was both a duplicate and a break with the
    convention** — this round dropped it from B149's caption and never wrote it into this one.
    """
    run, _seen, matchup = panel
    html = run([_calendar_row(AWAY, w) for w in (1, 2)])
    # 🚨 **SCOPED TO THE `<caption>`, AND THE FIRST VERSION WAS NOT — IT SEARCHED THE WHOLE
    # PANEL AND WENT RED ON `states.section`'s OWN DATA DICTIONARY LINK**,
    # `?table=srv_game_team`, which is the mechanism this test exists to keep. ⚠️ **An
    # instrument pointed at the wrong box** (R-859's family), caught by staging nothing more
    # than the passing case.
    captions = [part.split("</caption>")[0]
                for part in html.split("<caption")[1:]]
    assert captions, "the table draws no caption at all"
    for caption in captions:
        assert "srv_" not in caption, f"the caption prints a relation name: {caption}"
        assert "Source:" not in caption, "the caption reintroduced the raw source line"
    # ✅ AND THE HUMAN LABEL IS THE THING THAT SHOULD SAY IT, ONCE, WHERE THE SITE PUTS IT
    assert "?table=srv_game_team" in html, (
        "the section no longer links its dataset to the Data Dictionary, which is the "
        "convention the raw name was duplicating")
    # ✅ **AND THE SAME FOR B149's, WHICH IS THE CAPTION COWORK ACTUALLY FOUND.** 🚨 **SCOPED
    # TO THE CAPTION EXPRESSION, NOT THE FUNCTION** — the second version of this assertion read
    # the whole stripped body and went red on the panel's own
    # `states.section("srv_game_team", …)`, the very call that makes the raw name redundant.
    # **Two instruments in one test pointed at the wrong box; both were found by running it.**
    assert "srv_" not in _caption_expression_of("_season_so_far"), (
        "the season table's caption names the relation again; `states.section` already renders "
        "the site's dataset label for it")
    assert 'states.section("srv_game_team"' in SOURCE, (
        "the panels no longer declare their dataset, which is what renders the human label")
    assert "srv_game_team" in matchup.DATASETS, "the dataset label is not registered"


def test_THE_SPREAD_SIGN_IS_THE_MARKETS_and_is_not_flipped(panel):
    """📊 **VERIFIED ON 2025 WEEK 3: Baylor faced `spread_final` −52.0 against Samford** — so a
    negative number is the points THIS team was laying. ⚠️ **A flip would render plausibly and
    invert every row**, which is why the drawn cell is asserted rather than the column list.
    """
    run, _seen, _m = panel
    html = run([_calendar_row(AWAY, 1, spread_final=-52.0, ats_margin_final=14.0)],
               )
    assert "-52" in html or "−52" in html, (
        f"the laid spread does not draw as a negative number: {html[-800:]}")
    assert ">+52" not in html, "the spread's sign was flipped, so a favorite reads as a dog"


def test_THE_SECTION_SITS_AFTER_THE_SEASON_TABLE_and_before_travel_and_rest():
    """⚠️ **THE WHOLE *Before the game* ORDER IS PINNED, NOT JUST THIS PANEL'S NEIGHBOURS.**
    A count cannot see a swap and an adjacency cannot see a reordering two slots away.

    ✅ **WHY HERE:** the section reads the same bounded calendar as the season table and shares
    its `?team=` toggle, so the two tables follow one choice and sit together; *Travel and Rest*
    stays last as the page's closing logistics note.
    """
    tabs = _matchup().TABS
    before = next(panels for slug, _label, panels in tabs if slug == "before")
    assert before == ("_series", "_market_and_model", "_yardage", "_season_so_far",
                      "_ats_so_far", "_travel"), (
        f"the before-the-game section order moved: {before}")


def test_THERE_IS_NO_TOGGLE_and_both_teams_are_drawn_away_first(panel):
    """🚨 **v17 (cfdb-wta-R-2911).** Marc: *"Remove the tab and put them side by side (Away on
    the left, Home on the right)."*

    ⚠️ **ASSERTED ON THE RENDERED PANEL, NOT BY GREPPING FOR THE ABSENT STRING** — *a
    substring is not a rule* (R-2260), and "the source no longer says `cfdb-tabbar`" would
    also pass on a panel that drew nothing at all. **This asserts what IS there**: two teams,
    away before home, in one render.
    """
    run, _seen, _m = panel
    rows = [_calendar_row(AWAY, 1, opponent_team_display="Away Opponent"),
            _calendar_row(HOME, 1, opponent_team_display="Home Opponent")]
    html = run(rows)
    assert "cfdb-tabbar" not in html, "the section still draws a tab bar"
    assert "Away Opponent" in html and "Home Opponent" in html, (
        "both teams are not drawn in one render, which is the whole of Marc's ask")
    assert html.index("Oklahoma State") < html.index("Baylor"), (
        "home is drawn before away; Marc asked for away on the left")


def test_THE_URL_PARAMETER_NO_LONGER_CHANGES_WHAT_IS_DRAWN(panel):
    """🚨 **THE TOGGLE IS GONE, SO `?team=` MUST BE INERT HERE — AND INERT IS A CLAIM.**

    ⚠️ **B152 SHARED ONE `?team=` BETWEEN THIS PANEL AND THE SEASON TABLE.** A round that
    deleted the tab bar and left the filter behind would render one team and look, from the
    source, exactly like a round that had done this properly.

    ✅ **`params.get("team")` IS NOT ORPHANED BY THE DELETION** — `site/views/team.py` reads
    it as the Team page's own slug — **and `params.KNOWN` is session A's file, untouched.**
    """
    run, _seen, _m = panel
    rows = [_calendar_row(AWAY, 1, opponent_team_display="Away Opponent"),
            _calendar_row(HOME, 1, opponent_team_display="Home Opponent")]
    neutral = run(rows)
    for slug in ("baylor", "oklahoma-state", "not-a-team"):
        assert run(rows, team=slug) == neutral, (
            f"?team={slug} changed what the section drew, so a filter survived the toggle")


def test_THE_PAIR_IS_A_WRAPPING_ROW_OF_TWO_FIXED_WIDTH_COLUMNS():
    """📊 **THE BREAKPOINT IS THE TABLE'S OWN WIDTH, AND THIS PINS THE MECHANISM THAT MAKES
    IT ONE.** The table draws 453px; a pair needs 453 + gap + 453. **Two fixed-width children
    in a wrapping flex row wrap when the container cannot hold both** — so the stack point
    follows the measurement instead of a viewport number, and the sidebar moving the content
    box by ~460px cannot desynchronise it.

    ⚠️ **WHAT THIS TEST CANNOT DO IS PROVE THE WRAP HAPPENS.** Flex layout is the browser's;
    the round measured it at 1600 / 1440 / 1300 / 1024 and published the numbers. **This
    asserts only that the three things the wrap depends on are still passed.**
    """
    code = _code_of("_ats_so_far")
    assert "horizontal=True" in code and "wrap=True" in code, (
        "the pair is no longer a wrapping horizontal container, so it cannot stack")
    assert "width=_ATS_PAIR" in code, (
        "the columns no longer carry a fixed width, so there is nothing for the wrap to "
        "measure against and the two tables will shrink instead of stacking")
    assert _matchup()._ATS_PAIR_WIDTH == 453, (
        "the pair width no longer matches the table's measured drawn width; if the table "
        "moved, re-measure it in a browser and move this with it")
    assert "st.tabs(" not in code, "the section uses st.tabs, which R-283 forbids on this page"
    assert "link_here(team=" not in code, (
        "the toggle is back: a link here is a full page reload, which is the thing v17 "
        "removed (cfdb-wta-R-2853)")


def test_THE_LAYOUT_IS_ALL_PIXELS_and_the_render_call_passes_it():
    """📊 **452px of declared width — the reason this is its own section rather than three more
    columns on B149's table**, which already draws 1275px in a 1140px box.

    🚨 **AND THE CALL MUST PASS IT** (B149's R-744): deleting `layout=` leaves the constant
    perfectly correct and the table with no declared minimum, so the scroll note vanishes.
    """
    matchup = _matchup()
    layout = matchup._ATS_LAYOUT
    assert len(layout) == len(matchup._ats_table_columns()), (
        "the layout and the column list are different lengths, so the widths are off by one")
    assert all(w.endswith("px") for w in layout), (
        "a non-pixel width makes `scroll_minimum` return None and the note disappears")
    assert table_lib.scroll_minimum(layout) == 452, (
        f"the declared minimum moved to {table_lib.scroll_minimum(layout)}; if that is "
        f"deliberate, re-measure the drawn width in a browser and say so")
    code = _code_of("_ats_so_far")
    assert "layout=_ATS_LAYOUT" in code, (
        "the render call no longer passes the layout, so `scroll_minimum` gets None while "
        "`_ATS_LAYOUT` still looks right")
    assert "scroll=True" in code, "the table is no longer inside A208's shared scroll wrapper"
    assert "scroll_note(" not in code, (
        "the section emits its own scroll note; `render` already does, inside the container "
        "whose width the note's query reads")


def test_A_TEAM_WITH_NO_GAMES_BEFORE_THIS_ONE_SAYS_SO(panel):
    """⚠️ **WEEK 1 IS THE CASE THIS SECTION EXISTS FOR AND THE ONE WITH NOTHING TO SHOW.** The
    market has a line from the opening week, where a model prediction does not — but *before
    this one* is empty in week 1, and an empty table is not an answer (AC-G.11).
    """
    run, _seen, _m = panel
    html = run([_calendar_row(HOME, 1)])
    assert "first game of the season" in html, (
        f"a team with no prior games draws no named absence: {html[-800:]}")
