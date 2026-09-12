"""Matchup's two looks: before the game and after it (R-503).

⚠️ THE DEFECT THIS FILE EXISTS FOR IS THE DEFAULT-TAB INVERSION, and it is the one nothing
else could catch. A completed game that opens on the before tab renders perfectly: every
panel is correct, every number is true, the tab bar works, and clicking through gets you to
the drives. It is simply the wrong look — and "wrong look" is invisible to a query checker,
to flake8 and to every other test in this suite. So
`test_a_completed_game_opens_on_the_after_tab` was written first, the default was inverted on
purpose, and it was watched go red before being put back.

WHY TABS AT ALL, AND WHY NOT `st.tabs`:

  R-283, from Marc, on Scores: "Clicking a sort while on Against The Line or Box Score resets
  the user to the Game Results tab." `st.tabs` keeps its selection client-side and never
  touches the URL. This page reuses scores.py's anchor pattern rather than coining a second
  way to do the same thing.

  ⚠️ And anchors are LAZY, which matters more here. `st.tabs` renders every tab eagerly and
  only switches display, so it would multiply a cost this page already pays.
  `test_only_the_active_tabs_panels_run` is that guarantee, asserted rather than assumed:
  measured against live serving, a completed game went from five queries per render to two.

⚠️ THE PANELS ARE RECORDED, NOT RENDERED. This file is about WHICH panels run and WHERE; what
each one draws is covered by test_matchup_yardage, test_matchup_market_card and
test_matchup_drives, which call those panels directly. Recording is also what makes the lazy
assertion possible at all — a panel that never runs draws nothing, and "drew nothing" is
indistinguishable from "drew an Empty state" if you only look at the output.
"""
import html
import ast
import re
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_harness  # noqa: E402

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()

# Every panel the page had before this round, and the one B074 added. ⚠️ THE POINT OF THE
# LIST IS THAT NOTHING FELL OFF DURING THE MOVE: a panel silently dropped while being
# reassigned is the defect this round was most likely to ship, and A074 found a whole class
# of panel that nothing had ever exercised.
# ⚠️ `_weather` LEFT THIS LIST IN R-527 AND THAT IS A DELIBERATE REMOVAL, NOT A DROP. Marc
# asked for the weather "in a tight/concise element in the game header", so the standalone
# panel is gone and `_conditions` renders it inside `_game_header` — which is ABOVE the tab
# bar and therefore not a panel at all. tests/test_matchup_header.py holds the two
# assertions that travelled with it.
# ⚠️ `_market` AND `_line_movement` BECAME ONE PANEL IN R-519 — Marc: "Taking up WAY too
# much space. Develop a card that we can drop in somewhere to cover both." Two names left this
# list and one arrived; the list's whole purpose is that such a change is visible here.
# ⚠️ R-596: `_market_card` AND `_model` SHARE A ROW NOW and are called by `_market_and_model`,
# so the TAB names one panel where it used to name two. Marc: "Model — move to the right of
# Market, so they share the same row." Both still exist and both still carry their own
# states.section; only who calls them changed.
ALL_PANELS = ("_market_and_model", "_series", "_yardage",
              "_travel", "_post_game", "_leaders", "_drives")


def _stub_streamlit():
    captured = []

    def recorder(kind):
        def call(*args, **kwargs):
            captured.append((kind, " ".join(str(a) for a in args)))
        return call

    stub = types.ModuleType("streamlit")
    for name in ("subheader", "caption", "markdown", "write", "info", "warning", "error"):
        setattr(stub, name, recorder(name))

    class _Col:
        def metric(self, label, value, help=None):
            captured.append(("metric", f"{label} {value}"))

        def markdown(self, *args, **kwargs):
            captured.append(("markdown", " ".join(str(a) for a in args)))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    stub.columns = lambda n, **k: [_Col() for _ in range(n if isinstance(n, int) else len(n))]
    stub.button = lambda *a, **k: False
    stub.empty = lambda *a, **k: _Col()
    stub.text_input = lambda *a, **k: ""
    stub.query_params = {}

    def cache(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda fn: fn

    stub.cache_data = stub.cache_resource = cache
    stub.session_state = {}
    return stub, captured


# lib.params is here and it is not optional: it holds its own `import streamlit`, so without
# reloading it `params.get("tab")` reads the REAL streamlit's query params and every URL case
# below silently tests the default instead.
_RELOAD = ("lib.states", "lib.table", "lib.identity", "lib.shell", "lib.params",
           "views.matchup")


def _reload_all():
    import importlib
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))


@pytest.fixture
def page():
    """`body()` with streamlit captured, the database replaced and every panel recorded.

    ⚠️ IT PUTS THE MODULES BACK. Reloading lib.states against a stub binds the stub inside it
    for the rest of the session — test_matchup_drives learned that the hard way and six
    unrelated tests failed. monkeypatch cannot undo it either: its sys.modules restore runs
    after this teardown, so the swap and the restore are both done by hand.
    """
    real = sys.modules.get("streamlit")
    stub, captured = _stub_streamlit()
    sys.modules["streamlit"] = stub
    _reload_all()
    matchup = sys.modules["views.matchup"]
    called = []

    def run(game=None, **url):
        """Render `body()` for one game with the given `?` parameters."""
        captured.clear()
        called.clear()
        row = _game(**(game or {}))
        stub.query_params = dict({"game_id": str(row["game_id"])},
                                 **{k: str(v) for k, v in url.items()})
        matchup.query = lambda sql, params=None: pd.DataFrame([row])
        for name in ALL_PANELS:
            setattr(matchup, name, (lambda n: lambda *a, **k: called.append(n))(name))
        matchup.body(None)
        # 🚨 R-610. AN ERROR STATE IS NOT A PASSING STATE — B091's `deltas or {}` raised,
        # `states.section` drew a card, and this suite stayed green on a dead panel.
        render_harness.assert_no_error_card(captured, "the page body")
        return list(captured), list(called)

    yield run, matchup

    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    _reload_all()


def _game(**overrides):
    """One srv_game row's worth of what body() and the tab machinery read."""
    row = {"game_id": 401752754, "season": 2025, "season_type": "regular", "week": 10,
           "home_team": "Auburn", "away_team": "Kentucky",
           "home_team_id": 2, "away_team_id": 96,
           "is_completed": True, "start_date": pd.Timestamp("2025-11-01T19:00:00Z"),
           "as_of_ts": pd.Timestamp("2026-09-09T12:00:00Z")}
    row.update(overrides)
    return row


def _text(entries):
    return " ".join(
        re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()
        for _, body in entries)


def _bar(entries):
    """The tab bar's raw markup, or "" if no bar was drawn."""
    return " ".join(b for kind, b in entries if kind == "markdown" and "cfdb-tabbar" in b)


# --- the default, which is the whole of "two different looks" ------------------------------

def test_a_completed_game_opens_on_the_after_tab(page):
    """⚠️ THE ASSERTION THIS FILE EXISTS FOR.

    Verified by inverting it: making `_active_tab` fall back to the before tab for a played
    game leaves every panel correct and the page perfectly renderable, and fails only here.
    """
    run, _ = page
    _, called = run({"is_completed": True})
    assert called == ["_post_game", "_leaders", "_drives"], \
        f"a completed game did not open on the after tab — it ran {called}"


def test_a_scheduled_game_opens_on_the_before_tab(page):
    run, _ = page
    _, called = run({"is_completed": False})
    assert "_drives" not in called, "a game that has not kicked off rendered its drives"
    assert "_market_and_model" in called


# --- an unplayed game has NO after tab, not an empty one -----------------------------------

def test_a_scheduled_game_renders_no_after_tab_at_all(page):
    """The post-game spec's own line: "Empty is a state with a reason; an absent tab for an
    unplayed game is simply correct." Asserted on the BAR, not on the body — an empty tab
    whose label is still offered is exactly the thing this rejects."""
    run, matchup = page
    entries, _ = run({"is_completed": False})
    after_label = dict((slug, label) for slug, label, _p in matchup.TABS)[matchup.AFTER]
    assert after_label not in _text(entries), \
        "an unplayed game offered a tab for something that has not happened"
    assert "tab=after" not in _bar(entries)


def test_a_played_game_keeps_the_after_tab_even_where_cfdb_holds_nothing(page):
    """The opposite case, and Empty is right for it. Drives are collected from 2024 onward,
    so a 1999 game shows the tab with one Empty block: the question applies, and the answer
    is that we do not hold it."""
    run, _ = page
    entries, called = run({"is_completed": True, "season": 1999, "game_id": 62718})
    assert called == ["_post_game", "_leaders", "_drives"]
    assert "After the game" in _text(entries)


# --- the URL asking for something that does not apply --------------------------------------

def test_after_tab_requested_on_a_scheduled_game_falls_back_and_does_not_raise(page):
    """A real link someone sends on a Friday and opens on a Sunday, and a hand-edited URL."""
    run, _ = page
    entries, called = run({"is_completed": False}, tab="after")
    assert "_drives" not in called, "a scheduled game rendered the post-game tab on request"
    assert "_market_and_model" in called
    assert "Something went wrong" not in _text(entries)


def test_an_unknown_tab_slug_falls_back_and_does_not_raise(page):
    """scores.py already treats a hand-edited `?tab=` as noise, not a request (AC-G.11)."""
    run, _ = page
    entries, called = run({"is_completed": True}, tab="box-score-please")
    assert called == ["_post_game", "_leaders", "_drives"], "an unknown slug did not fall back to this game's own look"
    assert "Something went wrong" not in _text(entries)


def test_the_url_can_still_ask_for_the_other_tab(page):
    """The fallbacks must not have made the tab bar decorative."""
    run, _ = page
    _, called = run({"is_completed": True}, tab="before")
    assert "_drives" not in called and "_market_and_model" in called


# --- the lazy guarantee, which is the reason for anchors over st.tabs ----------------------

def test_only_the_active_tabs_panels_run(page):
    """⚠️ `st.tabs` renders every tab eagerly. If this test cannot be written against the
    pattern, the pattern is wrong. Measured against live serving: five queries per render
    before this round, two for a completed game after it."""
    run, matchup = page
    for slug, _label, panels in matchup.TABS:
        _, called = run({"is_completed": True}, tab=slug)
        assert called == list(panels), \
            f"tab {slug!r} ran {called}, not exactly its own panels"


# --- nothing fell off the page during the move ---------------------------------------------

def test_every_panel_is_assigned_to_exactly_one_tab(page):
    """⚠️ A PANEL SILENTLY DROPPED DURING A MOVE IS THIS ROUND'S MOST LIKELY DEFECT."""
    _, matchup = page
    assigned = [name for _slug, _label, panels in matchup.TABS for name in panels]
    assert sorted(assigned) == sorted(ALL_PANELS), \
        f"panels lost or duplicated in the split: {sorted(assigned)}"
    assert len(assigned) == len(set(assigned)), "a panel is on both tabs"


def test_every_named_panel_actually_resolves_to_a_function(page):
    """⚠️ THE COST OF NAMING PANELS INSTEAD OF REFERENCING THEM. Names are resolved out of the
    module at call time — which is what makes the lazy guarantee testable — and the price is
    that a typo in TABS is a KeyError at render rather than at import. The fixture patches
    only the names it knows, so it cannot catch that; this asserts against the real module."""
    _, matchup = page
    for _slug, _label, panels in matchup.TABS:
        for name in panels:
            resolved = vars(matchup).get(name)
            assert callable(resolved), f"TABS names {name!r}, which is not a function here"
            # ⚠️ __name__, not merely callable: the fixture's recorders are callable too, so
            # a bare callable check would quietly pass on a patched module and prove nothing.
            assert getattr(resolved, "__name__", None) == name, \
                f"{name!r} resolved to something other than the real panel"


def test_a_completed_game_still_reaches_every_panel_across_the_two_tabs(page):
    run, matchup = page
    reached = []
    for slug, _label, _panels in matchup.TABS:
        reached += run({"is_completed": True}, tab=slug)[1]
    assert sorted(reached) == sorted(ALL_PANELS)


def test_the_game_header_stays_above_the_tab_bar(page):
    """It is the identity of the page, not a panel — and it already carries Final or
    Scheduled and the score.

    ⚠️ Renamed from `_the_scoreline_` in R-518: `_scoreline` became `_game_header` and a test
    named for a function that no longer exists is the drift this project keeps removing."""
    run, _ = page
    entries, _ = run({"is_completed": True})
    bodies = [b for _, b in entries]
    bar = next(i for i, b in enumerate(bodies) if "cfdb-tabbar" in b)
    assert any("Final" in b for b in bodies[:bar]), \
        "the scoreline did not render above the tab bar"


# --- R-283: the tab lives in the URL --------------------------------------------------------

def test_the_tab_bar_is_anchors_carrying_the_slug_in_the_url(page):
    run, _ = page
    bar = _bar(run({"is_completed": True})[0])
    assert "<a " in bar and "cfdb-tab" in bar, "the tab bar is not anchors"
    assert "tab=before" in bar and "tab=after" in bar
    assert "target='_self'" in bar


def test_a_deep_link_preserves_the_tab(page):
    """R-283's actual fix: `params.link_here` carries every KNOWN parameter, and `tab` is
    one. A sort or filter link therefore keeps the tab with no change to either."""
    run, _ = page
    run({"is_completed": True}, tab="before")
    from lib import params
    assert "tab" in params.KNOWN, "the tab would be dropped from every link on the page"
    href = params.link_here(week=11)
    assert "tab=before" in href and "week=11" in href
    assert "game_id=401752754" in href, "the deep link lost the game it is about"


def test_the_tab_bar_is_not_drawn_when_there_is_nothing_to_choose(page):
    """A control offering a single destination is a control that does nothing — the rule the
    tab bar's own CSS comment in lib/theme.py was written against."""
    run, _ = page
    assert _bar(run({"is_completed": False})[0]) == ""
    assert _bar(run({"is_completed": True})[0]) != ""


# --- what this round deliberately did NOT build ---------------------------------------------

def test_no_post_game_content_was_stubbed(page):
    """B070's standing rule: a front-end round behind the data round, and NO STUB either.

    ⚠️ THIS ASSERTION WAS AMENDED IN B076, NOT WEAKENED, AND THE AMENDMENT IS THE POINT.
    B075 wrote it as "srv_game_team, srv_player_game_log and srv_player_stats appear nowhere",
    because in B075 the post-game tab was deliberately empty. B076 built the box score, so
    the srv_game_team half has been SATISFIED rather than removed — it is now asserted as
    read exactly once, which is the stronger claim (§1.1: one read, two renderings).

    The other two are still asserted absent, and that is not housekeeping: R-506 was BLOCKED.
    Nothing in serving ranks players within a game, so a leaders panel cannot be built without
    a data change, and B070's rule says no stub either. If either name appears here before a
    serving view carries game-grain ranks, something was computed in the page.
    """
    # ⚠️ COUNTED OVER THE WHOLE SOURCE, COMMENTS INCLUDED, AND THAT IS THE STRICT READING
    # KEPT ON PURPOSE — a prose mention of `from srv_game_team` fails this, and the one in
    # _leaders was reworded rather than the assertion being narrowed to code.
    #
    # ⚠️ THE WORD BOUNDARY IS A FIX, NOT A LOOSENING, AND B077 FOUND IT THE HARD WAY.
    # B076 wrote `count("from srv_game_team")`, which also matches `from
    # srv_game_team_leader` — so the moment A080's ranked object was read, an assertion about
    # ONE relation started counting two. It read as precise and never was. `\b` makes it
    # mean what its message always claimed.
    # ⚠️ AMENDED IN B091, AND LIKE B076's AMENDMENT IT IS STRICTER RATHER THAN LOOSER.
    #
    # B076 turned "appears nowhere" into "read exactly once" when it built the box score.
    # R-686 then gave the yardage panel a SECOND, legitimate reader: A106's three deltas live
    # on srv_game_team at game x team grain, the figures beside them are week grain on
    # srv_team_week, and the two panels sit on DIFFERENT TABS. Folding them into one read
    # would couple the before tab to the after tab to satisfy a count.
    #
    # 🚨 SO THE COUNT BECAME A MAP. "Exactly one read in the file" said nothing about WHERE;
    # this says which function may read it and how many times each — so a third reader, or the
    # box score quietly splitting back into two, both fail, and neither could before.
    reads = {}
    for node in ast.walk(ast.parse(SOURCE)):
        if isinstance(node, ast.FunctionDef):
            body = ast.get_source_segment(SOURCE, node) or ""
            found = len(re.findall(r"from srv_game_team\b", body))
            if found:
                reads[node.name] = found
    assert reads == {"_post_game": 1, "_game_team_rows": 1}, (
        f"srv_game_team is read somewhere new, or the box score split back into two reads "
        f"(G-2, one read two renderings): {reads}")
    assert len(re.findall(r"from srv_game_team_leader\b", SOURCE)) == 1, \
        "the leaders panel must be one read too (R-511)"
    # ⚠️ THE srv_player_* BAN USED TO BE REPEATED HERE AND HAS MOVED, NOT GONE. It now lives
    # ONCE, in test_matchup_postgame.test_the_ranking_is_read_and_never_computed_in_the_page,
    # where it is strictly STRONGER: that version strips comments and docstrings with ast
    # before testing, and asserts the positive — that srv_game_team_leader IS read — beside
    # it. This copy was the plain-substring form, and B077's _leaders docstring names both
    # views to record WHY neither could answer the question. A ban on a name must be a ban on
    # reading it, not on explaining it, so the duplicate went and the better one stayed.
    # ⚠️ CODE LINES ONLY. The module explains at length WHY it is not st.tabs, so a bare
    # substring test fails on its own reasoning — which is a test asserting that the comment
    # is absent rather than that the call is.
    code = "\n".join(line for line in SOURCE.splitlines()
                     if not line.lstrip().startswith("#"))
    assert "st.tabs(" not in code, "st.tabs loses the tab on every link (R-283)"


def test_the_split_is_two_tabs_named_for_when_not_what(page):
    """Marc killed subject-based grouping on 2026-09-08 and named the state split himself."""
    _, matchup = page
    assert len(matchup.TABS) == 2, "a third tab is the framework Marc vetoed"
    labels = " ".join(label for _s, label, _p in matchup.TABS).lower()
    for subject in ("overview", "conditions", "market", "context", "sequence", "stats"):
        assert subject not in labels, f"tab named for a subject, not a state: {subject!r}"
