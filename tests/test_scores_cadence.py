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


# ── A290 (cfdb-main-R-5013): the gate asked "anything to FETCH" and skipped the BUILD ──────
#
# 📊 WHAT HAPPENED, MEASURED ON THE DROPLET 2026-10-28. Week 9's forecasts loaded into
# `raw.raw_model_prediction` at 16:43:36Z. `SAFETY_NET_HOUR_UTC` is 12, so the day's only
# unconditional run had passed 4.7 hours earlier, and the 14:00, 16:00, 18:00, 20:00 and
# 22:00 runs every one of them took `nothing_settling` and skipped `dbt_run`, `dbt_test` and
# `publish_to_serving`. `fct_prediction` held 0 rows for week 9 while weeks 5-8 were present.
#
# 🚨 AND EVERY HEARTBEAT WAS GREEN THROUGHOUT, because `heartbeat` carries
# `trigger_rule=NONE_FAILED` and beats on a deliberate skip — §2.3, A264's cfdb-main-R-4109:
# *"a stale beat IS a stopped publish; a FRESH beat is NOT a working publish."*
#
# ⚠️ These tests are the branch's two directions. The one that matters is the SECOND: a
# branch that always opens the gate would be a 39-model build twelve times a day, which is
# the load A285 bought the warehouse-write pool to stop.

@pytest.mark.parametrize("label,now,since,unfinished,unbuilt,proceed,branch", [
    # TODAY'S FAILURE, replayed. Nothing to fetch, forecasts waiting, gate must OPEN.
    ("week 9 loaded at 16:43 and nothing is settling",
     at(2026, 10, 28, 18), 40.0, 0, 1, True, "unbuilt_predictions"),
    # The count is a count: four unbuilt weeks is a different story from one and the reason
    # should be able to say so without a second query.
    ("a month of skipped builds reads as four, not as true",
     at(2026, 10, 28, 18), 40.0, 0, 4, True, "unbuilt_predictions"),
    # 🚨 THE DIRECTION THAT PROTECTS THE WAREHOUSE. Nothing unbuilt -> the gate still SHUTS,
    # so this change costs no routine builds at all.
    ("nothing unbuilt still skips, which is what keeps this cheap",
     at(2026, 10, 28, 18), 40.0, 0, 0, False, "nothing_settling"),
    # A database that will not answer must not wedge the gate either way (the module's own
    # rule for its other two inputs).
    ("an unreadable count falls through rather than opening or shutting",
     at(2026, 10, 28, 18), 40.0, 0, None, False, "nothing_settling"),
    # OUT OF SEASON an unbuilt forecast is not a reason to spend a build, and 12:00 is the
    # safety net's hour so this is deliberately 18:00.
    ("out of season it does not open the gate",
     at(2027, 3, 1, 18), None, 0, 3, False, "off_season_skip"),
    # A FETCH REASON STILL WINS, so the log keeps the more specific line.
    ("a settling game outranks it",
     at(2026, 10, 28, 18), 2.0, 0, 2, True, "settling"),
    ("an unfinished game outranks it",
     at(2026, 10, 28, 18), 40.0, 1, 2, True, "unfinished"),
])
def test_the_unbuilt_predictions_branch(label, now, since, unfinished, unbuilt,
                                        proceed, branch):
    decision = should_refresh_scores(now_utc=now, config=CONFIG,
                                     hours_since_last_kickoff=since,
                                     unfinished_recent=unfinished,
                                     unbuilt_predictions=unbuilt)
    assert decision.proceed is proceed, label
    assert decision.branch == branch, label


def test_the_skip_reason_no_longer_claims_there_is_nothing_to_do():
    """⚠️ §3.2.3 — the sentence ships. `nothing_settling` used to say only that no game was
    settling, which read as "nothing to do" and was false on 2026-10-28: there were 56
    forecasts waiting. The reason now names the third thing it checked."""
    decision = should_refresh_scores(now_utc=at(2026, 10, 28, 18), config=CONFIG,
                                     hours_since_last_kickoff=40.0, unfinished_recent=0,
                                     unbuilt_predictions=0)
    assert decision.branch == "nothing_settling"
    assert "unbuilt forecasts" in decision.reason, decision.reason


def test_the_new_branch_is_reachable_from_the_real_default_arguments():
    """🚨 R-760. A keyword-only input with a default of None is invisible to every existing
    caller, so this pins that the DAG's call site actually passes it — the branch could
    otherwise be correct, tested and never once evaluated in production."""
    import inspect
    from pathlib import Path
    dag = (Path(__file__).resolve().parents[1] / "dags" / "scores_refresh_dag.py").read_text()
    assert "unbuilt_predictions=unbuilt_prediction_weeks()" in dag, (
        "the scores DAG does not pass the unbuilt count, so the branch can never fire")
    assert "unbuilt_predictions" in inspect.signature(should_refresh_scores).parameters
