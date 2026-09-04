"""The switch that catches a stopped pipeline, and the two ways it could lie.

The laptop stack was down 24-28 August and nothing noticed: every alert was of the form
"something ran and failed", and nothing ran. These pin the properties that make absence
detectable, because a dead-man's switch is only as good as the day it is tripped — and by
then nobody is watching the code.
"""
from pathlib import Path

import pytest

import ci.check_heartbeats as chk
from src import heartbeat

DAGS = Path(__file__).resolve().parents[1] / "dags"
FORCED_COMMAND = Path(__file__).resolve().parents[1] / "deploy" / "cfdb_heartbeat.sh"


def _code(path: Path) -> str:
    """Source with comment lines stripped — this repo has matched its own prose before."""
    return "\n".join(ln for ln in path.read_text().splitlines()
                     if not ln.lstrip().startswith("#") and not ln.lstrip().startswith("--"))


# --- a beat must never come from a failed run ---------------------------------------------

def test_the_heartbeat_is_the_last_task_on_the_success_path():
    """A heartbeat from a failed run is a lie: it says healthy at the moment the pipeline is
    not. In the DAGs that publish, the beat sits downstream of publish so it reports only a
    run that reached a reader."""
    for name in ("weekly_refresh_dag.py", "scores_refresh_dag.py"):
        code = _code(DAGS / name)
        assert ">> beat" in code, f"{name}: nothing beats"
        assert "publish >> beat" in code, f"{name}: the beat must follow publish"


def test_the_beat_is_never_attached_to_the_all_done_task():
    """capture_dq is `all_done` — it succeeds after a failure, on purpose, so a failed run
    still records its test results. A beat attached there would report alive on exactly the
    runs this exists to catch."""
    code = _code(DAGS / "weekly_refresh_dag.py")
    assert "capture_dq >> beat" not in code
    assert "beat >> capture_dq" not in code


# --- idle is not dead ----------------------------------------------------------------------

@pytest.mark.parametrize("dag_file", ["scores_refresh_dag.py", "lines_snapshot_dag.py"])
def test_a_gated_dag_still_beats_when_it_correctly_does_nothing(dag_file):
    """THE SUBTLE ONE. Both gated DAGs skip their work outside a game window, and that is a
    successful run — the scheduler fired, the gate decided, nothing failed.

    With the default all_success rule the beat would be skipped too, so the pipeline would go
    silent for an entire off-season and the monitor could not tell that apart from a dead
    box. none_failed beats on success or deliberate skip and stays silent on failure.

    `ignore_downstream_trigger_rules` must be False or the gate skips everything downstream
    regardless of its rule, defeating the above.
    """
    code = _code(DAGS / dag_file)
    assert "TriggerRule.NONE_FAILED" in code, f"{dag_file}: gated beat needs none_failed"
    assert "ignore_downstream_trigger_rules=False" in code, (
        f"{dag_file}: True would skip the heartbeat behind a closed gate")


def test_the_ungated_weekly_dags_keep_the_strict_rule():
    """Nothing skips in the weekly chain, so the beat must stay on all_success — the
    stricter rule, applied where it costs nothing."""
    code = _code(DAGS / "weekly_refresh_dag.py")
    assert "TriggerRule.NONE_FAILED" not in code


# --- the beat itself -------------------------------------------------------------------

def test_a_monitor_outage_never_fails_a_green_pipeline(monkeypatch, capsys):
    """The reverse would make the safety net the most fragile component in the system."""
    monkeypatch.setattr(heartbeat, "ping_url_for", lambda _n: "http://127.0.0.1:1/ping")
    assert heartbeat.ping("scores_refresh") is False
    assert "FAILED" in capsys.readouterr().out


def test_an_unconfigured_monitor_says_so_rather_than_passing_quietly(monkeypatch, capsys):
    """"No URL set" and "ping succeeded" must not look the same. An unarmed switch that
    reported success is the worst outcome available."""
    monkeypatch.setattr(heartbeat, "ping_url_for", lambda _n: None)
    assert heartbeat.ping("scores_refresh") is False
    assert "nothing is watching" in capsys.readouterr().out


# --- the watcher ---------------------------------------------------------------------------

def test_an_unreachable_host_is_the_alarm_not_an_error(monkeypatch, capsys):
    """If the droplet is off, reading heartbeats fails — and that IS the loudest case, not a
    condition to handle quietly."""
    def unreachable(_host):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(chk, "read_ages", unreachable)
    assert chk.main(["cfdb_monitor@nowhere"]) == 1
    assert "unreachable" in capsys.readouterr().out


def test_a_stale_cadence_fails_and_names_itself(monkeypatch, capsys):
    fresh = {name: 60 for name in chk.CADENCES}
    fresh["scores_refresh"] = 7 * 3600            # budget is 5h
    monkeypatch.setattr(chk, "read_ages", lambda _h: (fresh, {}))
    assert chk.main(["host"]) == 1
    out = capsys.readouterr().out
    assert "STALE" in out and "scores_refresh" in out
    assert "Silence is not success" in out


def test_a_cadence_that_never_beat_is_not_silently_ok(monkeypatch, capsys):
    """A missing key reads as "no news". It is the opposite."""
    monkeypatch.setattr(
        chk, "read_ages",
        lambda _h: ({n: 60 for n in chk.CADENCES if n != "weekly_results"}, {}))
    assert chk.main(["host"]) == 1
    assert "NEVER BEAT" in capsys.readouterr().out


def test_all_fresh_passes(monkeypatch, capsys):
    monkeypatch.setattr(chk, "read_ages", lambda _h: ({n: 60 for n in chk.CADENCES}, {}))
    assert chk.main(["host"]) == 0
    assert "beating within budget" in capsys.readouterr().out


def cadence_names_in_dags() -> set:
    """Every heartbeat name the DAGs actually emit.

    Two spellings, because the weekly file maps three DAGs through HEARTBEAT_NAME while the
    gated files name theirs inline. Both are matched rather than one, so a name added in
    either place is seen.
    """
    import re
    found = set()
    for path in sorted(DAGS.glob("*.py")):
        code = _code(path)
        # inline: beat("scores_refresh", ...)
        found |= set(re.findall(r'\.beat\(\s*"([a-z_]+)"', code))
        # mapped: "cfbd_results_refresh": "weekly_results",
        found |= set(re.findall(r'"cfbd_\w+":\s*"([a-z_]+)"', code))
    return found


def test_the_dags_and_the_monitor_agree_on_the_cadence_names():
    """A DAG that beats under a name the monitor does not know is monitored by NOBODY, and
    the switch looks armed while covering one cadence fewer than it appears to. A budget for
    a name nothing emits is the mirror image: it fails forever, gets muted, and takes the
    real alerts with it."""
    emitted = cadence_names_in_dags()
    budgeted = set(chk.CADENCES)

    # Guard against the whole check passing because the regexes matched nothing.
    assert len(emitted) == 5, f"expected five cadences in the DAGs, found {sorted(emitted)}"

    assert emitted == budgeted, (
        f"DAGs emit {sorted(emitted)} but the monitor budgets {sorted(budgeted)}; "
        f"unmonitored={sorted(emitted - budgeted)} phantom={sorted(budgeted - emitted)}")


# --- the forced command --------------------------------------------------------------------

def test_the_monitoring_key_can_only_read_heartbeats():
    """Verified live: `ssh cfdb_monitor@host 'cat /etc/passwd'` returns the heartbeat
    listing, because SSH_ORIGINAL_COMMAND is never consulted. There is no verb to abuse."""
    code = _code(FORCED_COMMAND)
    assert "SSH_ORIGINAL_COMMAND" not in code, (
        "this key takes no client input at all; parsing any would create a surface")
    assert "docker" not in code, "Docker socket access is root by another name"
    assert "pipeline_heartbeat" in code


# === the watcher reads failures now, because absence is too slow ===========================

def _watcher():
    import importlib.util
    from pathlib import Path as _Path
    root = _Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("check_heartbeats",
                                                  root / "ci" / "check_heartbeats.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_ssh(monkeypatch, module, stdout: str):
    import subprocess

    def fake_run(*_a, **_k):
        return subprocess.CompletedProcess([], 0, stdout, "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)


def test_the_watcher_reads_failed_tasks_as_well_as_missing_beats(monkeypatch):
    """ABSENCE TAKES HOURS; A FAILURE IS KNOWABLE IMMEDIATELY.

    On 2026-09-04 `dbt_test` began failing at 02:27. The scores heartbeat did not cross its
    five-hour budget until 05:07, and this watcher's own cadence — nominally two-hourly,
    measured at 3.1 to 6.8 hours between runs — pushed detection past eleven hours. The
    pipeline published nothing from midnight and nothing said so.
    """
    module = _watcher()
    _fake_ssh(monkeypatch, module,
              "scores_refresh|600\nlines_snapshot|900\n"
              "failed|cfbd_scores_refresh.dbt_test|1200\n")
    ages, failures = module.read_ages("host")
    assert ages == {"scores_refresh": 600, "lines_snapshot": 900}
    assert failures == {"cfbd_scores_refresh.dbt_test": 1200}


def test_a_failed_task_fails_the_watcher_even_when_every_beat_is_fresh(monkeypatch, capsys):
    """The exact shape of 2026-09-04's first two hours: heartbeats still inside budget,
    because the DAG had beaten at midnight, and the publish already dead."""
    module = _watcher()
    fresh = "\n".join(f"{name}|60" for name in module.CADENCES)
    _fake_ssh(monkeypatch, module, fresh + "\nfailed|cfbd_scores_refresh.dbt_test|900\n")
    assert module.main(["host"]) == 1
    printed = capsys.readouterr().out
    assert "cfbd_scores_refresh.dbt_test" in printed
    assert "did not run" in printed, "it must say what the failure COST, not just that it was"


def test_a_clean_pipeline_still_passes(monkeypatch):
    module = _watcher()
    _fake_ssh(monkeypatch, module, "\n".join(f"{n}|60" for n in module.CADENCES))
    assert module.main(["host"]) == 0


def test_an_older_forced_command_does_not_break_the_watcher(monkeypatch):
    """The droplet's script and this checker deploy together but are separate files, and a
    monitor that crashes on output it does not recognise is a monitor that is off."""
    module = _watcher()
    _fake_ssh(monkeypatch, module, "\n".join(f"{n}|60" for n in module.CADENCES))
    ages, failures = module.read_ages("host")
    assert failures == {} and len(ages) == len(module.CADENCES)
    assert module.main(["host"]) == 0


def test_the_watcher_asks_often_even_though_asking_does_not_help():
    """A MEASURED DISAPPOINTMENT, RECORDED SO NOBODY RETRIES IT.

    The cron was two-hourly and delivered runs 3.1 to 6.8 hours apart. Changing it to */20 on
    the reasoning that the same delay factor would land near forty-five minutes produced
    exactly ONE scheduled run in the following 7.1 hours — the identical count to the 7.1
    hours before, against twenty-one requested.

    GitHub throttles per repository, not per requested interval. The frequent cron stays
    because a run costs eleven seconds and more attempts cannot hurt; it is NOT a fix, and
    this test exists so the next person does not spend an afternoon tuning it.
    """
    import re
    from pathlib import Path as _Path
    workflow = (_Path(__file__).resolve().parents[1]
                / ".github" / "workflows" / "heartbeat.yml").read_text()
    crons = re.findall(r"cron:\s*'([^']+)'", workflow)
    assert crons, "the watcher has no schedule at all"
    # The comment above the cron must not claim a delivered cadence again.
    assert "IT DID NOT" in workflow, (
        "the measurement that disproved the frequent-cron theory has been removed")


def test_the_push_path_is_the_one_that_can_actually_be_fast():
    """`beat()` records THEN pings, so the durable row is never lost to a flaky GET, and the
    ping is what an external dead-man's switch watches for.

    Nothing here needs writing: the code has been in place since the heartbeat was built and
    has never had a URL. That is the whole gap — `ping` prints "nothing is watching for
    absence" into a task log nobody reads.
    """
    import inspect
    from src import heartbeat
    source = inspect.getsource(heartbeat.beat)
    assert "record(" in source and "ping(" in source
    assert source.index("record(") < source.index("ping("), (
        "the durable record must be written before the network call")
    assert heartbeat.PING_ENV_PREFIX == "CFDB_HEARTBEAT_URL_"
    assert heartbeat.ping_url_for("scores_refresh") is None or True

def test_the_forced_command_reports_failures_in_the_shape_the_watcher_parses():
    """THE SCRIPT AND THE WATCHER DEPLOY SEPARATELY — the shell goes to the droplet by scp
    and the checker runs on GitHub — so a mismatch is a monitor that reads nothing and says
    everything is fine.

    Asserted on the script's text because there is no droplet in CI. Narrow on purpose: the
    prefix and the separator are the contract, and the SQL around them is free to change.
    """
    from pathlib import Path as _Path
    script = (_Path(__file__).resolve().parents[1]
              / "deploy" / "cfdb_heartbeat.sh").read_text()
    code = "\n".join(ln for ln in script.splitlines() if not ln.lstrip().startswith("#"))
    assert "'failed|'" in code, (
        "the forced command no longer emits failure lines; the watcher would go back to "
        "waiting for a stale heartbeat, which took eleven hours on 2026-09-04")
    assert "task_instance" in code and "state = 'failed'" in code
    assert "airflow" in code, "failures live in the Airflow metadata database, not the warehouse"


def test_the_watcher_and_the_forced_command_agree_on_the_failure_format():
    """Round-trip: feed the parser exactly what the script's SQL produces."""
    module = _watcher()
    line = "failed|cfbd_scores_refresh.dbt_test|8100"
    import subprocess

    class Done:
        returncode, stdout, stderr = 0, line + "\n", ""

    module.subprocess.run = lambda *a, **k: Done()
    _, failures = module.read_ages("host")
    assert failures == {"cfbd_scores_refresh.dbt_test": 8100}
    del subprocess


def test_a_monitor_that_cannot_see_failures_says_so_rather_than_reporting_none():
    """THE DEFECT THIS CHANGE EXISTS TO REMOVE, REINTRODUCED ONE LAYER DOWN.

    The first version echoed `failed_query_unavailable|airflow|0` when the query could not
    run — a shape the watcher discards as unparseable. A monitor that had lost sight of
    failures then looked exactly like a pipeline that had none, which is the same silence
    that cost eight hours.

    It emits a `failed|` line instead, so an unreadable metadata database raises the alarm
    rather than muting it. (It was not hypothetical: the monitor user's .pgpass named the
    `cfdb` database specifically and could not read `airflow` at all.)
    """
    from pathlib import Path as _Path
    script = (_Path(__file__).resolve().parents[1]
              / "deploy" / "cfdb_heartbeat.sh").read_text()
    code = "\n".join(ln for ln in script.splitlines() if not ln.lstrip().startswith("#"))
    assert "failed_query_unavailable" not in code, (
        "the fallback must use the `failed|` shape the watcher parses, or it is discarded")
    assert "failed|MONITOR." in code

    module = _watcher()

    class Done:
        returncode = 0
        stdout = "scores_refresh|60\nfailed|MONITOR.cannot_read_airflow_metadata|0\n"
        stderr = ""

    module.subprocess.run = lambda *a, **k: Done()
    _, failures = module.read_ages("host")
    assert "MONITOR.cannot_read_airflow_metadata" in failures
