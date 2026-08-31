"""The scores gate, enumerated.

Written as a table of scenarios rather than one assertion per branch because the thing that
went wrong in the first version was a gap BETWEEN branches — an unreachable database in
season skipped, contradicting the module's own docstring — and a gap is only visible when
the cases are listed side by side.
"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.lines_cadence import CadenceConfig            # noqa: E402
from src.scores_cadence import should_refresh_scores   # noqa: E402

CONFIG = CadenceConfig(season=2026, first_game_date=date(2026, 8, 27), lead_days=7,
                       season_end_date=date(2027, 1, 27))


def at(y, m, d, h):
    return datetime(y, m, d, h, tzinfo=timezone.utc)


@pytest.mark.parametrize("label,now,since,unfinished,proceed,branch", [
    # THE SUSPENDED GAME, which is the whole reason the second branch exists. A Thursday
    # 22:00 kickoff halted for lightning and resumed Friday afternoon keeps its Thursday
    # timestamp, so the kickoff clock says 18 hours and the settle window shut long ago.
    ("thursday game still unfinished on friday afternoon",
     at(2026, 8, 28, 16), 18.0, 1, True, "unfinished"),
    # And it closes on its own the moment the game finals — same clock, nothing unfinished.
    ("same hour once the game has finaled",
     at(2026, 8, 28, 16), 18.0, 0, False, "nothing_settling"),
    # The bound is the circuit breaker: past 36h a game that never finals stops counting.
    # The caller is what applies the window, so from the gate's side this is simply zero.
    ("a postponed game older than the window no longer counts",
     at(2026, 8, 30, 16), 60.0, 0, False, "nothing_settling"),
    # Out of season an unfinished game is not a reason to spend a request.
    ("unfinished game out of season", at(2026, 6, 4, 6), 18.0, 1, False,
     "off_season_skip"),
])
def test_the_unfinished_branch(label, now, since, unfinished, proceed, branch):
    decision = should_refresh_scores(now, CONFIG, since, unfinished_recent=unfinished)
    assert decision.proceed is proceed, f"{label}: {decision.reason}"
    assert decision.branch == branch, f"{label}: {decision.reason}"


def test_settling_wins_over_unfinished_so_the_reason_is_the_more_specific_one():
    """Both can be true at once during a live slate. The log should say "results are
    landing", not "something is unfinished" — the first is the normal case and the second
    is the exception, and a gate that reports the exception every Saturday trains the
    reader to ignore it."""
    decision = should_refresh_scores(at(2026, 8, 28, 2), CONFIG, 3.0, unfinished_recent=5)
    assert decision.branch == "settling"


def test_an_unreadable_database_still_fails_open_rather_than_reading_zero():
    """A null count is "cannot tell", not "nothing unfinished". Both inputs come from one
    read in schedule_state precisely so this inference is sound."""
    decision = should_refresh_scores(at(2026, 10, 6, 6), CONFIG, None, unfinished_recent=None)
    assert decision.proceed and decision.branch == "unknown_fail_open"


@pytest.mark.parametrize("label,now,since,proceed,branch", [
    # The opening weekend, which is the whole reason this DAG exists. Thursday's games kick
    # at 22:00 UTC, ten hours AFTER cfbd_midweek_results has already run.
    ("thursday night results, 3h after kickoff",
     at(2026, 8, 28, 2), 3.0, True, "settling"),
    ("saturday night results, 5h after kickoff",
     at(2026, 8, 30, 4), 5.0, True, "settling"),
    ("friday afternoon, 19h since the last kickoff",
     at(2026, 8, 28, 18), 19.0, False, "nothing_settling"),

    # A quiet week in October: nothing played since Saturday.
    ("quiet tuesday", at(2026, 10, 6, 6), 60.0, False, "nothing_settling"),
    ("quiet tuesday at the safety-net hour",
     at(2026, 10, 6, 12), 60.0, True, "safety_net"),

    # Out of season the gate collapses to one run a day.
    ("june, off hour", at(2026, 6, 4, 6), 900.0, False, "off_season_skip"),
    ("june, safety-net hour", at(2026, 6, 4, 12), 900.0, True, "safety_net"),

    # FAIL OPEN. Two wasted requests cost less than a stale scoreboard.
    ("in season, schedule unreadable", at(2026, 10, 6, 6), None, True,
     "unknown_fail_open"),
    # Out of season the same unknown is not worth a request.
    ("off season, schedule unreadable", at(2026, 6, 4, 6), None, False,
     "off_season_skip"),
])
def test_gate_branches(label, now, since, proceed, branch):
    decision = should_refresh_scores(now, CONFIG, since)
    assert decision.proceed is proceed, f"{label}: {decision.reason}"
    assert decision.branch == branch, f"{label}: {decision.reason}"


def test_every_decision_explains_itself():
    """A skip that cannot say why is indistinguishable from a broken DAG in March."""
    for since in (2.0, 60.0, None):
        decision = should_refresh_scores(at(2026, 10, 6, 6), CONFIG, since)
        assert len(decision.reason) > 40


def test_a_naive_datetime_is_treated_as_utc_not_rejected():
    """Airflow hands the logical date over in several shapes."""
    naive = datetime(2026, 10, 6, 12)
    assert should_refresh_scores(naive, CONFIG, 60.0).proceed


def test_a_kickoff_in_the_future_does_not_open_the_gate():
    """A negative age means the schedule moved or the clock is wrong. Neither is a
    reason to start collecting results for a game that has not been played."""
    decision = should_refresh_scores(at(2026, 10, 6, 6), CONFIG, -5.0)
    assert not decision.proceed
