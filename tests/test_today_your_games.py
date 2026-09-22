"""A199 — the games a reader adds to Looking Forward themselves.

> **MARC, v12:** *"a text input box on the bottom of the nav bar that would allow end-user to
> paste games they want included on Looking Forward Schedule and SLATE."*

⚠️ THIS IS THE ONE PLACE ON THE SITE WHERE READER TEXT REACHES A QUERY, so the parsing is
tested hardest: only integers come out, and they reach SQL as a bound array rather than as
text. Everything else — prose, a URL to somewhere else, an injection-shaped string — is an
unreadable line, which is a state the reader is told about rather than one that fails.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                   # noqa: E402


class _SlateScope:
    """A201: `_slate` takes the scope now, because Marc's Matchup column needs `scope.link`."""
    season, season_type, week, conference, division = 2026, "regular", 4, None, "fbs"

    def link(self, page, **kw):
        bits = "&".join(f"{k}={v}" for k, v in kw.items())
        return f"/{page}?{bits}" if bits else f"/{page}"


SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
SHARED = (ROOT / "site" / "lib" / "schedule_table.py").read_text()
PARAMS = (ROOT / "site" / "lib" / "params.py").read_text()


def test_bare_ids_in_any_arrangement():
    assert today._parse_game_ids("401866418")[0] == [401866418]
    assert today._parse_game_ids("401866418\n401856685")[0] == [401866418, 401856685]
    assert today._parse_game_ids("401866418, 401856685")[0] == [401866418, 401856685]
    assert today._parse_game_ids("401866418 401856685")[0] == [401866418, 401856685]


def test_a_matchup_url_gives_up_its_game_id():
    """> **MARC:** *"I can use the matchup url querystring to extract the game_id."*

    ⚠️ THE PARAMETER NAME IS MATCHUP'S OWN, read from `matchup.py` rather than assumed — it is
    `params.get("game_id")` there.
    """
    url = "https://cfdb.example/matchup?game_id=401866418&season=2026&week=4"
    assert today._parse_game_ids(url)[0] == [401866418]
    # mixed with a bare id, and with the season number sitting right beside it
    mixed = f"{url}\n401856685"
    assert today._parse_game_ids(mixed)[0] == [401866418, 401856685], (
        "a URL contributes ONE id — `season=2026` must not be read as a game")


def test_the_same_game_twice_is_one_game():
    """A reader who pastes a URL and then its id should not see the row twice."""
    ids, unreadable, _ = today._parse_game_ids(
        "401866418\nhttps://x/matchup?game_id=401866418\n401866418")
    assert ids == [401866418]
    assert unreadable == []


@pytest.mark.parametrize("text", [
    "1; drop table games",
    "select * from srv_game",
    "'; delete from srv_game; --",
    "not a game at all",
    "https://example.com/other?team=georgia",
])
def test_text_that_is_not_a_game_yields_no_id_and_is_reported(text):
    """🚨 ONLY INTEGERS COME OUT, AND THE INJECTION-SHAPED CASE IS NOT SPECIAL.

    ⚠️ `1; drop table games` contains no bare-integer TOKEN — `1;` is not one — so it yields
    nothing and is reported as an unreadable line, exactly like prose. The safety does not
    come from spotting SQL; it comes from never emitting anything but `int`.
    """
    ids, unreadable, _ = today._parse_game_ids(text)
    assert ids == []
    assert unreadable == [1]


def test_an_over_long_paste_is_capped_and_says_so():
    """⚠️ TRUNCATION MUST BE ANNOUNCED. A silently shorter list is the defect AC-G.11 exists
    for — the reader would believe every game he pasted is on the page."""
    ids, _unreadable, truncated = today._parse_game_ids(
        "\n".join(str(400000000 + i) for i in range(200)))
    assert truncated is True
    assert len(ids) == today._LF_MAX_IDS

    long_text = "4018664180 " * 500
    assert len(long_text) > today._LF_MAX_CHARS
    assert today._parse_game_ids(long_text)[2] is True


def test_the_line_number_is_the_readers_line_not_a_token_index():
    """A line is what the reader can see and point at."""
    ids, unreadable, _ = today._parse_game_ids(
        "401866418\nrubbish here\n401856685\nmore rubbish")
    assert ids == [401866418, 401856685]
    assert unreadable == [2, 4]


def test_the_feedback_reports_added_missing_and_unreadable_separately():
    """AC-G.11: three different things happened, and they are three different statements."""
    note = today._looking_forward_feedback(
        4, asked=[1, 2, 3], found_ids={1, 2}, unreadable=[3], truncated=False)
    assert "Added 2" in note
    assert "1 not a week-4 game (3)" in note
    assert "1 line unreadable (line 3)" in note


def test_a_last_weeks_id_is_reported_rather_than_silently_dropped():
    """🚨 WHAT HAPPENS TO AN `lf=` FROM LAST WEEK AFTER THE WEEK ROLLS OVER.

    The link keeps working and the box says the game is not a week-N game. ⚠️ Dropping it
    quietly would leave a bookmarked link showing fewer games every week with no explanation.
    """
    note = today._looking_forward_feedback(
        4, asked=[401856687], found_ids=set(), unreadable=[], truncated=False)
    assert "Added 0" in note
    assert "not a week-4 game (401856687)" in note


def test_nothing_pasted_says_nothing():
    assert today._looking_forward_feedback(4, [], set(), [], False) == ""
    assert today._parse_game_ids("") == ([], [], False)
    assert today._parse_game_ids(None) == ([], [], False)


def test_the_ids_reach_sql_as_a_bound_array_and_never_as_text():
    """🚨 THE ONE PLACE READER TEXT REACHES A QUERY.

    ⚠️ And it is ONE query, not two merged in the page — §4.2.1. The added games widen the
    existing predicate rather than arriving from a second read whose ordering the page would
    then have to reconcile.
    """
    assert "game_id = any(:also_ids)" in SHARED
    assert '"also_ids": list(also_ids or [])' in SHARED
    # no f-string or concatenation anywhere near the id list
    body = SHARED[SHARED.index("def rows("):]
    body = body[:body.index("\n\n\n")] if "\n\n\n" in body else body
    assert "also_ids}" not in body and "+ str(also_ids" not in body, (
        "the ids must be bound, never formatted into the SQL string")
    # and the page passes them through rather than filtering afterwards
    # ⚠️ `_high_value_reason` was the old end marker and A205 deleted it with the list.
    page = SOURCE[SOURCE.index("def _high_value_games("):SOURCE.index("def _looking_forward(")]
    assert "also_ids=also_ids" in page


def test_the_parameter_is_registered_or_it_would_vanish_on_the_next_click():
    """🚨 `link_here()` AND `current()` BOTH FILTER TO `KNOWN`.

    An unregistered parameter is dropped the moment the reader sorts a column or moves a
    filter. `params.py`'s own note records that exact bug for `player`/`q`: read without being
    registered, so "sorting or changing any filter silently deselected the player you were
    looking at".
    """
    from lib import params
    assert "lf" in params.KNOWN
    assert "lf" in params.SLUG_PARAMS, (
        "a comma-separated id list is a free-form string, not an int or an enum")
    assert "lf" not in params.INT_PARAMS, (
        "INT_PARAMS would int() the whole list and raise BadParam on the first comma")


def test_the_url_carries_the_list_and_the_box_is_seeded_from_it():
    """The round trip: box → `lf=` → reload → same list."""
    body = SOURCE[SOURCE.index("def _looking_forward_box("):
                  SOURCE.index("def _looking_forward_feedback(")]
    assert 'params.get("lf")' in body, "the box is seeded from the URL"
    assert 'params.set_params(lf=' in body, "typing updates the URL"
    assert 'if key not in st.session_state' in body, (
        "the URL seeds the box ONCE; re-seeding every run would fight the reader's typing")
    # the URL holds the PARSED ids, so a reload cannot resurrect unreadable text
    assert '",".join(str(i) for i in ids)' in body


def test_an_added_game_carries_its_own_tag_and_keeps_any_rule_tags():
    """⚠️ A GAME CAN BE BOTH. Showing only "Added by you" would hide why it qualifies on its
    own; showing only the rule would hide that he asked for it.

    🚨 A205 REMOVED THE LIST, so the question is asked of `_slate_reason_text` — the one place
    the reason words now live, read by the SLATE's marks and its hovers alike.
    """
    both = today._slate_reason_text(
        {"is_top25_matchup": True, "is_undefeated_entering": False, "is_added_by_you": True})
    assert both == "Top 25 · Added by you"

    only_added = today._slate_reason_text(
        {"is_top25_matchup": False, "is_undefeated_entering": False, "is_added_by_you": True})
    assert only_added == "Added by you"


def test_the_added_flag_is_computed_in_the_page_and_not_published():
    """🚨 THE ONE PLACE §4.2.1 FALLS THE OTHER WAY, AND WHY.

    "Which games are high-value" is a definition the whole site could share, so it is a
    column. "Which games did THIS reader paste into THIS URL" has exactly one consumer — this
    render, for this viewer — and could not be a published column without storing viewer
    state server-side, which is the thing this design deliberately avoids.
    """
    assert "is_added_by_you" not in (ROOT / "dbt" / "models" / "serving"
                                     / "srv_game.sql").read_text()
    assert "is_added_by_you=games[" in SOURCE


# ── the gate, and what the reader's ids do on either side of it ────────────────────────

def _run(monkeypatch, *, gate_open, pasted=(401866418,), games=None, week=4):
    """Drive the REAL `_looking_forward` with the box stubbed to "the reader pasted this".

    ⚠️ IT INVOKES THE PAGE RATHER THAN REPRODUCING IT (R-768). A test that builds its own
    frame, filters it and asserts the result asserts that pandas filters.
    """
    import contextlib
    import importlib
    import pandas as pd
    written, seen = [], {}

    class _Quiet:
        def markdown(self, body, *a, **k):
            written.append(("markdown", str(body)))

        def caption(self, body, *a, **k):
            written.append(("caption", str(body)))

        def info(self, body, *a, **k):
            written.append(("info", str(body)))

        def subheader(self, body, *a, **k):
            written.append(("subheader", str(body)))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __getattr__(self, name):
            return lambda *a, **k: None

    page = importlib.reload(importlib.import_module("views.today"))
    monkeypatch.setattr(page, "st", _Quiet())
    monkeypatch.setattr(page.states, "section", lambda *a, **k: contextlib.nullcontext())
    monkeypatch.setattr(page, "_upcoming_game_week", lambda scope: week)
    # ⚠️ A204 added a cutoff dropdown beside the section. These tests are about
    # the gate and the pasted ids, so it is stubbed to the default; the control
    # itself is asserted in `test_today_close_cut.py`.
    monkeypatch.setattr(page, "_close_cut_control", lambda: 4)
    monkeypatch.setattr(page, "_looking_forward_box",
                        lambda scope, w: (list(pasted), [], False))
    monkeypatch.setattr(page, "_week_is_final", lambda scope, w: gate_open)
    monkeypatch.setattr(page, "_poll_is_out", lambda scope, w: gate_open)

    def high_value(scope, w, also_ids=None, close_cut=4):
        seen["also_ids"] = also_ids
        return games if games is not None else pd.DataFrame()
    monkeypatch.setattr(page, "_high_value_games", high_value)

    def render_or_state(frame, view, *a, **k):
        seen["frame"] = frame
    monkeypatch.setattr(page.states, "render_or_state", render_or_state)

    class _Scope:
        season, season_type, week, conference, division = 2026, "regular", 3, None, "fbs"

        def link(self, page, **kw):
            return f"/{page}"
    page._looking_forward(_Scope(), 25)
    return written, seen


def test_with_the_gate_closed_nothing_is_drawn_and_the_box_says_so(monkeypatch):
    """🚨 THE GATE STILL RULES (A196). One gate, not two.

    ⚠️ The BOX is still drawn — a reader lines games up before the week opens, and a control
    that vanishes exactly when he is planning would be strange. What the gate decides is
    whether anything is RENDERED from it.
    """
    written, seen = _run(monkeypatch, gate_open=False)
    assert "frame" not in seen, "the gate was shut and a table was rendered anyway"
    assert "also_ids" not in seen, "the gate was shut and the games query ran anyway"
    assert any(k == "info" for k, _ in written), "no splash note"
    assert any("will show here once week 4 opens" in body
               for k, body in written if k == "caption"), written


def test_with_the_gate_open_the_pasted_ids_reach_the_one_query(monkeypatch):
    """§4.2.1: ONE relation, ONE read. The added games widen the existing predicate."""
    import pandas as pd
    frame = pd.DataFrame([
        {"game_id": 401866418, "is_top25_matchup": True, "is_undefeated_entering": False},
        {"game_id": 401856700, "is_top25_matchup": False, "is_undefeated_entering": False},
    ])
    _written, seen = _run(monkeypatch, gate_open=True, pasted=(401856700,), games=frame)
    assert seen["also_ids"] == [401856700]
    rendered = seen["frame"]
    assert list(rendered["is_added_by_you"]) == [False, True], (
        "the tag must mark the game the reader asked for and only that one")


def test_an_added_game_says_why_it_is_on_the_slate_too():
    """⚠️ THE LIST AND THE SLATE ARE TWO VIEWS OF ONE FRAME.

    A game that carries "Added by you" in the table and NOTHING in the chart's hover makes a
    reader wonder which of the two is wrong. 🚨 Found by this round's own browser render, not
    by reading the code — the tooltip is the one place a defect sits in plain sight.
    """
    import pandas as pd
    row = {"game_id": 401856700, "start_date": pd.Timestamp("2026-09-26T19:30:00Z"),   # 12:30 PM Pacific
           "away_team_display": "Oklahoma", "home_team_display": "Georgia",
           "network_abbreviation": "ESPN", "spread_current": -13.5,
           "kickoff_time_known": True,
           "is_top25_matchup": False, "is_undefeated_entering": False, "is_added_by_you": True}
    svg = today._slate(pd.DataFrame([row]), esc=lambda t: t, scope=_SlateScope())
    assert "Added by you" in svg, svg[:400]
