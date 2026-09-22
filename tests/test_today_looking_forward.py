"""A196 — Looking Forward: the gate, the rules' reasons, and the table it borrows.

⚠️ THE RULES THEMSELVES ARE ASSERTED IN dbt, NOT HERE. `is_high_value` and its two reasons are
published on `srv_game` because "which games matter" is a definition (§4.2.1), so the tests
that re-derive them live beside the model. What this file holds is everything the PAGE decides:
when the section opens, what it says when it does not, and that it renders Schedule's table
rather than one of its own.
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                    # noqa: E402

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
SCHEDULE = (ROOT / "site" / "views" / "schedule.py").read_text()
SHARED = (ROOT / "site" / "lib" / "schedule_table.py").read_text()


class _Scope:
    season, season_type, week, conference, division = 2026, "regular", 3, None, "fbs"

    def link(self, page, **kw):
        return f"/{page}"

    def describe(self):
        return "2026 week 3"


def _run(monkeypatch, answers, week=4):
    """Drive the real `_looking_forward` with stubbed reads, capturing what it wrote."""
    import contextlib
    import importlib
    written = []

    class _Quiet:
        def markdown(self, body, *a, **k):
            written.append(("markdown", str(body)))

        def caption(self, body, *a, **k):
            written.append(("caption", str(body)))

        def subheader(self, body, *a, **k):
            written.append(("subheader", str(body)))

        def info(self, body, *a, **k):
            written.append(("info", str(body)))

        def columns(self, spec, **k):
            return [self] * (spec if isinstance(spec, int) else len(spec))

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
    monkeypatch.setattr(page, "_week_is_final", lambda scope, w: answers["final"])
    monkeypatch.setattr(page, "_poll_is_out", lambda scope, w: answers["poll"])
    monkeypatch.setattr(page, "_high_value_games",
                        lambda scope, w: answers.get("games", pd.DataFrame()))
    rendered = {}

    def render_or_state(frame, view, *a, **k):
        rendered["frame"] = frame
        rendered["empty_message"] = a[1] if len(a) > 1 else None
    monkeypatch.setattr(page.states, "render_or_state", render_or_state)
    page._looking_forward(_Scope(), 25)
    return written, rendered


def test_the_gate_opens_only_when_both_conditions_are_met(monkeypatch):
    """🚨 MARC'S TIMING IS A DATA GATE, NOT A CLOCK.

    > *"It has to be live after Saturday games are complete and the next week of rankings is
    > available."*

    Two conditions, and the section must not open on either alone. ⚠️ **Opening on one would
    be the worst outcome**: a table built from last week's poll looks exactly like a correct
    one, which is why this is asserted in all four combinations rather than only the happy one.
    """
    for final, poll, opens in [(True, True, True), (True, False, False),
                               (False, True, False), (False, False, False)]:
        written, rendered = _run(monkeypatch, {"final": final, "poll": poll})
        kinds = {k for k, _ in written}
        if opens:
            assert "info" not in kinds, (final, poll, written)
            assert "frame" in rendered, "the gate opened but nothing was rendered"
        else:
            assert "info" in kinds, f"no splash with final={final} poll={poll}"
            assert "frame" not in rendered, (
                "a closed gate must render no table at all — not an empty one, and "
                "certainly not last week's")


def test_the_splash_names_the_week_and_which_condition_is_pending(monkeypatch):
    """> **MARC:** *"Can put up a splash note that it will be populated after Rankings come
    out."*

    ⚠️ "COMING SOON" WOULD LEAVE A READER UNABLE TO TELL A PIPELINE FAILURE FROM A TUESDAY.
    The note names the week and says which of the two conditions is still outstanding.
    """
    # ⚠️ THE ASSERTION IS ON THE PENDING LIST, NOT THE WHOLE NOTE. The note's fixed sentence
    # always names both conditions — that is what tells the reader what it is waiting for —
    # so searching the whole string for "AP Top 25" matches the explanation rather than the
    # status. A first draft did exactly that and failed on correct copy.
    def pending_of(note):
        return note.split("Still pending:", 1)[1]

    written, _ = _run(monkeypatch, {"final": True, "poll": False})
    note = next(b for k, b in written if k == "info")
    assert "week 4" in note and "week 3" in note
    assert "AP Top 25 for week 4 is not out yet" in pending_of(note)
    assert "not final" not in pending_of(note), "it must not report a condition that IS met"

    written, _ = _run(monkeypatch, {"final": False, "poll": True})
    note = next(b for k, b in written if k == "info")
    assert "week 3 is not final yet" in pending_of(note)
    assert "AP Top 25" not in pending_of(note)

    written, _ = _run(monkeypatch, {"final": False, "poll": False})
    note = next(b for k, b in written if k == "info")
    assert "week 3 is not final yet" in pending_of(note)
    assert "AP Top 25 for week 4 is not out yet" in pending_of(note)


def test_the_heading_names_the_upcoming_week_and_the_caption_disowns_the_filter(monkeypatch):
    """⚠️ THE SECTION IGNORES THE PAGE'S WEEK FILTER ON PURPOSE, SO IT SAYS SO.

    A reader looking back at week 2 still wants the upcoming week's games. A panel that
    silently ignores a control the reader just moved is worse than one that never offered it.
    """
    written, _ = _run(monkeypatch, {"final": True, "poll": True})
    head = next(b for k, b in written if k == "subheader")
    assert head == "Looking forward · week 4"
    caption = " ".join(b for k, b in written if k == "caption")
    assert "does not follow the week filter" in caption


def test_the_end_of_the_regular_season_is_its_own_state(monkeypatch):
    """AC-G.11: "every week has been played" is not the same absence as "the gate is shut"."""
    written, rendered = _run(monkeypatch, {"final": True, "poll": True}, week=None)
    said = " ".join(b for _k, b in written)
    assert "has been played" in said
    assert "frame" not in rendered
    assert not any(k == "info" for k, _ in written), (
        "the season being over is not a pending condition — it will never resolve")


def test_the_empty_state_names_the_week_rather_than_drawing_a_blank_table(monkeypatch):
    written, rendered = _run(monkeypatch, {"final": True, "poll": True})
    assert "No games in week 4 meet the high-value rules yet." == rendered["empty_message"]


@pytest.mark.parametrize("top25,undef,expected", [
    (True, False, ["Top 25 matchup"]),
    (False, True, ["Undefeated · close line"]),
    (True, True, ["Top 25 matchup", "Undefeated · close line"]),
    (False, False, []),
])
def test_the_reason_tag_reads_the_flags_and_shows_both_when_both_fire(top25, undef, expected):
    """⚠️ BOTH RULES CAN FIRE ON ONE GAME, AND SHOWING ONLY THE FIRST WOULD MAKE THE SECOND
    LOOK NARROWER THAN IT IS. 2 of the 8 qualifying week-4 games carry both tags."""
    html = today._high_value_reason({"is_top25_matchup": top25, "is_undefeated_close": undef})
    tags = re.findall(r"cfdb-why-tag'>([^<]+)<", html)
    assert tags == expected
    if not expected:
        assert html == ""


def test_the_page_adds_no_rule_of_its_own():
    """§4.2.1. The page filters on a published flag; it does not decide what is high-value."""
    body = SOURCE[SOURCE.index("def _high_value_games("):SOURCE.index("def _looking_forward(")]
    for forbidden in ("rank is not None", "< 4", "abs(", "losses"):
        assert forbidden not in body, (
            f"{forbidden!r} in the page means a rule has leaked out of dbt")
    assert "high_value_only=True" in body


def test_looking_forward_renders_schedules_table_rather_than_a_copy_of_it():
    """🚨 MARC ASKED FOR "THE SAME LAYOUT AS SCHEDULE", AND THE SAME LAYOUT MEANS THE SAME CODE.

    A copy is two tables that agree until one of them changes. `lib/schedule_table.py` holds
    the columns AND the query now, and both pages call it — a view may not import another view.

    ⚠️ AND THE QUERY MATTERS AS MUCH AS THE COLUMNS. A196 first hand-wrote a parallel SELECT
    for Today and guessed two column names wrong (`venue_name`, `weather`); the page raised
    `UndefinedColumn` into `states.section` and drew one error card — a handled failure that
    looks considered. There is one query now, so the opportunity is gone rather than the bug.
    """
    assert "schedule_table.columns(scope)" in SOURCE
    assert "schedule_table.rows(" in SOURCE
    assert "def columns(" in SHARED and "def rows(" in SHARED
    # Schedule keeps aliases so its own call sites, including the stacked card's six, are
    # untouched — that is what makes "the look cannot have changed" checkable.
    assert "_rows = schedule_table.rows" in SCHEDULE
    assert "_columns = schedule_table.columns" in SCHEDULE
    # and Today must not import the view
    assert "from views import schedule" not in SOURCE
    assert "import schedule\n" not in SOURCE


def test_the_stale_game_grace_is_named_and_bounded():
    """🚨 ONE CANCELLED GAME MUST NOT HOLD THE GATE SHUT ALL SEASON.

    📊 Measured across the corpus: exactly one FBS game has a passed kickoff and no
    completion — App State vs Liberty, 2024 week 5, **724 days past**, the Hurricane Helene
    cancellation. Read literally ("every game whose kickoff has passed is completed"), it
    would have jammed 2024 week 6 permanently.
    """
    assert today._STALE_GAME_DAYS == 7
    body = SOURCE[SOURCE.index("def _week_is_final("):SOURCE.index("def _poll_is_out(")]
    assert "start_date < now()" in body, "a future kickoff cannot block the gate"
    assert "make_interval(days => :grace)" in body, (
        "a game older than the grace window is abandoned, not pending")


def test_the_poll_gate_asks_for_the_upcoming_weeks_poll_not_the_previous_ones():
    """🚨 A190's ALIGNMENT: poll week W is published BEFORE game week W.

    So "the new poll" for upcoming game week W is poll week **W**. ⚠️ Asking for W-1 would
    open the gate a week early with last week's ranks — and the table would look entirely
    normal, which is why this is asserted rather than trusted.

    🚨 AND THE ASSERTION IS PARSED, NOT SUBSTRING-MATCHED, BECAUSE THE FIRST VERSION COULD NOT
    FAIL. It read `'"week": int(week)' in body`, and a staged break writing `int(week) - 1`
    still CONTAINS that substring — so the break came back GREEN while the gate asked for the
    wrong poll. R-843's shape exactly: the pinned value did not move under the break.
    """
    import ast

    tree = ast.parse(SOURCE)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_poll_is_out")
    week_values = [ast.unparse(v)
                   for d in ast.walk(fn) if isinstance(d, ast.Dict)
                   for k, v in zip(d.keys, d.values)
                   if isinstance(k, ast.Constant) and k.value == "week"]
    assert week_values == ["int(week)"], (
        f"the poll gate must ask for the UPCOMING week's poll, got {week_values}")
