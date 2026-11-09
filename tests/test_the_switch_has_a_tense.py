"""The dead-man's switch says whether a fault is live. A293 · cfdb-main-R-5104.

Each message used to be accurate and none carried a tense: "last failed 2d ago" read the same
for a cadence that had retried and failed and one that had not been scheduled since. These
stage each pair through the real parser and the real `main`, and assert the pair reads
DIFFERENTLY — a guard seen in only one state is a claim (R-760 / R-843).
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "check_heartbeats_tense", ROOT / "ci" / "check_heartbeats.py")
switch = importlib.util.module_from_spec(_spec)
sys.modules["check_heartbeats_tense"] = switch
_spec.loader.exec_module(switch)

DAY, HOUR = 86400, 3600
OUTCOMES = [f"{head}|0|0|-" for head in switch.OUTCOME_LINES]
FRESH = {name: 60 for name in switch.CADENCES}


def payload(*extra, ages=None):
    beats = [f"{name}|{age}" for name, age in {**FRESH, **(ages or {})}.items()]
    return "\n".join(beats + OUTCOMES + list(extra)) + "\n"


def report(monkeypatch, capsys, text):
    monkeypatch.setattr(switch, "fetch_payload", lambda host: text)
    code = switch.main(["cfdb_monitor@example"])
    return code, capsys.readouterr().out


FAILED = "failed|cfbd_scores_refresh.dbt_test|10800"     # 3h ago


def test_failed_then_succeeded_differs_from_failed_then_nothing(monkeypatch, capsys):
    """The two facts the prompt names: "succeeded 1h ago" and "has not run since"."""
    recovered = f"dag_run|cfbd_scores_refresh|{HOUR}|{HOUR}|0|{HOUR}"
    # The only run started 4h ago: that is the run which failed, ending 3h ago.
    nothing = f"dag_run|cfbd_scores_refresh|{20 * HOUR}|{4 * HOUR}|0|{HOUR}"

    code_a, a = report(monkeypatch, capsys, payload(FAILED, recovered))
    code_b, b = report(monkeypatch, capsys, payload(FAILED, nothing))

    assert "SUCCEEDED SINCE" in a and "HAS NOT RUN SINCE" not in a, a
    assert "HAS NOT RUN SINCE" in b and "SUCCEEDED SINCE" not in b, b
    assert "next scheduled in 1h 0m" in b
    # Tense, not volume: both still page.
    assert code_a == code_b == 1


def test_the_run_that_failed_does_not_count_as_having_run_since(monkeypatch, capsys):
    """🚨 A run ends after its own failed task. Comparing END times would call this "ran again".

    Its START is older than the failure, which is what makes the comparison honest.
    """
    same_run = "dag_run|cfbd_scores_refresh|-|10830|0|3600"
    _code, out = report(monkeypatch, capsys, payload("failed|cfbd_scores_refresh.dbt_test|10800",
                                                     same_run))
    assert "HAS NOT RUN SINCE" in out and "STILL FAILING" not in out, out


def test_a_cadence_that_retried_and_failed_is_still_failing(monkeypatch, capsys):
    retried = f"dag_run|cfbd_scores_refresh|{9 * DAY}|{HOUR}|0|{HOUR}"
    _code, out = report(monkeypatch, capsys, payload(FAILED, retried))
    assert "STILL FAILING" in out, out
    assert "started 1h 0m ago" in out


def test_a_run_in_progress_is_said_rather_than_read_as_no_run(monkeypatch, capsys):
    running = f"dag_run|cfbd_scores_refresh|{9 * DAY}|{4 * HOUR}|1|{HOUR}"
    _code, out = report(monkeypatch, capsys, payload(FAILED, running))
    assert "a run of its cadence is in progress" in out, out


def test_a_stale_beat_with_no_opportunity_differs_from_one_that_had_one(monkeypatch, capsys):
    """The Sunday DAG that missed Sunday against the one failing every two hours."""
    stale = {"weekly_pregame": 10 * DAY}
    no_chance = f"dag_run|cfbd_pregame_refresh|{10 * DAY + 60}|{10 * DAY + 60}|0|{2 * DAY}"
    had_chance = f"dag_run|cfbd_pregame_refresh|{10 * DAY + 60}|{2 * DAY}|0|{5 * DAY}"

    code_a, a = report(monkeypatch, capsys, payload(no_chance, ages=stale))
    code_b, b = report(monkeypatch, capsys, payload(had_chance, ages=stale))

    assert "HAS HAD NO CHANCE" in a and "next scheduled in 2d 0h" in a, a
    assert "HAS HAD A CHANCE" in b and "HAS HAD NO CHANCE" not in b, b
    assert code_a == code_b == 1


def test_an_older_forced_command_says_the_tense_is_unknown(monkeypatch, capsys):
    """The window between merge and deploy: a new watcher reading an old script."""
    _code, out = report(monkeypatch, capsys, payload(FAILED, ages={"weekly_pregame": 10 * DAY}))
    assert "whether its cadence has run since is unknown" in out, out
    assert "whether it has had a chance to run since is unknown" in out, out


def test_the_annotation_carries_the_tense_because_that_is_what_the_email_shows(monkeypatch,
                                                                               capsys):
    recovered = f"dag_run|cfbd_scores_refresh|{HOUR}|{HOUR}|0|{HOUR}"
    _code, out = report(monkeypatch, capsys, payload(FAILED, recovered))
    errors = [line for line in out.splitlines() if line.startswith("::error::task failed")]
    assert errors and "SUCCEEDED SINCE" in errors[0], out


def test_the_run_line_does_not_disturb_the_gates_four_part_reading():
    """`ci/check_publish_path.py` unpacks exactly four, and an unknown head must not become
    a cadence."""
    reading = switch.parse_payload(payload(f"dag_run|cfbd_scores_refresh|-|{HOUR}|1|-"))
    ages, failures, failed_tests, outcomes = reading
    assert set(ages) == set(switch.CADENCES)
    assert reading.runs == {"cfbd_scores_refresh": (None, HOUR, True, None)}


def test_a_blind_run_query_is_not_read_as_a_dag():
    reading = switch.parse_payload(payload("dag_run|MONITOR.cannot_read_airflow_metadata|-|-|0|-"))
    assert reading.runs == {}


def test_the_forced_command_emits_the_shape_the_watcher_parses():
    script = (ROOT / "deploy" / "cfdb_heartbeat.sh").read_text()
    assert "select 'dag_run|'" in script
    assert 'echo "dag_run|MONITOR.' in script


def test_every_cadence_names_the_dag_that_beats_it():
    """A hand-written map drifts, so it is held equal to the DAG files."""
    assert set(switch.HEARTBEAT_DAG) == set(switch.CADENCES)
    weekly = dict(
        (beat, dag) for dag, beat in re.findall(
            r'"(cfbd_\w+)":\s*"([a-z_]+)"',
            (ROOT / "dags" / "weekly_refresh_dag.py").read_text()))
    for beat, dag in weekly.items():
        assert switch.HEARTBEAT_DAG[beat] == dag
    for beat, file_name in (("scores_refresh", "scores_refresh_dag.py"),
                            ("lines_snapshot", "lines_snapshot_dag.py")):
        code = (ROOT / "dags" / file_name).read_text()
        assert f'dag_id="{switch.HEARTBEAT_DAG[beat]}"' in code
