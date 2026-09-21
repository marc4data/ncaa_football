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
    monkeypatch.setattr(chk, "read_ages", lambda _h: (fresh, {}, {}, None))
    assert chk.main(["host"]) == 1
    out = capsys.readouterr().out
    assert "STALE" in out and "scores_refresh" in out
    assert "Silence is not success" in out


def test_a_cadence_that_never_beat_is_not_silently_ok(monkeypatch, capsys):
    """A missing key reads as "no news". It is the opposite."""
    monkeypatch.setattr(
        chk, "read_ages",
        lambda _h: ({n: 60 for n in chk.CADENCES if n != "weekly_results"}, {}, {}, None))
    assert chk.main(["host"]) == 1
    assert "NEVER BEAT" in capsys.readouterr().out


def test_all_fresh_passes(monkeypatch, capsys):
    monkeypatch.setattr(chk, "read_ages", lambda _h: ({n: 60 for n in chk.CADENCES}, {}, {}, None))
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
    ages, failures, failed_tests, _unboxed = module.read_ages("host")
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
    ages, failures, failed_tests, _unboxed = module.read_ages("host")
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
    assert heartbeat.PING_TIMEOUT_SECONDS <= 15, (
        "a heartbeat that hangs delays the DAG it is reporting on")


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


def test_the_watcher_and_the_forced_command_agree_on_the_failure_format(monkeypatch):
    """Round-trip: feed the parser exactly what the script's SQL produces.

    🚨 R-633. `monkeypatch`, NOT `module.subprocess.run = …`, AND THE DIFFERENCE COST A ROUND.
    `module.subprocess` IS the global subprocess module — there is one object — so assigning to
    its `run` mutated it for every test that ran afterwards, and the `del subprocess` that used
    to sit at the end of this function deleted a LOCAL NAME and undid nothing.

    A094's negative test PASSED ALONE AND FAILED IN THE SUITE, reporting that its check had
    never been invoked: it had called this stub instead. Two files then defended against the
    leak by hand. `monkeypatch` makes pytest undo it, which is what lets those defences go.
    """
    module = _watcher()
    line = "failed|cfbd_scores_refresh.dbt_test|8100"

    class Done:
        returncode, stdout, stderr = 0, line + "\n", ""

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: Done())
    _, failures, _, _unboxed = module.read_ages("host")
    assert failures == {"cfbd_scores_refresh.dbt_test": 8100}


def test_a_monitor_that_cannot_see_failures_says_so_rather_than_reporting_none(monkeypatch):
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

    # R-633. monkeypatch, for the reason written at the other patch site in this file.
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: Done())
    _, failures, _, _unboxed = module.read_ages("host")
    assert "MONITOR.cannot_read_airflow_metadata" in failures


def _failure_sql():
    """The failure query, lifted out of the shell script so the test runs the real thing."""
    from pathlib import Path as _Path
    script = (_Path(__file__).resolve().parents[1]
              / "deploy" / "cfdb_heartbeat.sh").read_text()
    import re as _re
    # A180: the columns are qualified now — the query joins `dag` to exclude paused and
    # deleted DAGs, which makes a bare `dag_id` ambiguous.
    match = _re.search(r"select 'failed\|'.*?order by ranked\.dag_id, ranked\.task_id",
                       script, _re.S)
    assert match, "the failure query moved or changed shape"
    return match.group()


# A synthetic clock. `end_date` has to increase with time for `order by end_date desc` to
# mean "most recent first" — storing "minutes ago" inverts it, which is a mistake that makes
# the query look broken while the test is what is wrong.
NOW_MINUTES = 100_000


def _run_failure_sql(rows, sql=None, dags=None):
    """Execute it against sqlite over synthetic task_instance rows.

    `rows` are (dag, task, state, minutes_ago) and are converted to an increasing clock here.

    Two Postgres-isms are swapped out — the interval literal and `extract(epoch ...)::bigint`
    — and NOTHING ELSE. The defect this guards was entirely in the ranking, so the ranking
    runs unmodified: `row_number() over (partition by dag_id, task_id order by end_date
    desc)` and the `recency = 1` that reads it.
    """
    import re as _re
    import sqlite3
    statement = sql or _failure_sql()
    # A180: the window is eight days now (11,520 minutes), sized to the slowest DAG's weekly
    # cadence rather than the two-hourly one's retries. See the script's own comment.
    statement = statement.replace(
        "end_date > now() - interval '8 days'", f"end_date > {NOW_MINUTES - 8 * 24 * 60}")
    statement = _re.sub(
        r"floor\(extract\(epoch from \(now\(\) - ranked\.end_date\)\)\)::bigint",
        # PARENTHESISED. In SQLite `||` binds TIGHTER than `*`, so a bare multiplication
        # parses as `('failed|…' || end_date) * 60` and every row collapses to the number 0 —
        # which reads as the query returning nothing rather than the substitution being wrong.
        f"(({NOW_MINUTES} - ranked.end_date) * 60)", statement)
    connection = sqlite3.connect(":memory:")
    connection.execute("create table task_instance "
                       "(dag_id text, task_id text, state text, end_date int)")
    connection.executemany(
        "insert into task_instance values (?,?,?,?)",
        [(d, t, st, NOW_MINUTES - ago) for d, t, st, ago in rows])
    # A180: the query joins `dag`, so the fixture needs one. Every dag in `rows` is live and
    # unpaused unless `dags` says otherwise — {dag_id: (is_paused, is_stale)}.
    connection.execute("create table dag (dag_id text, is_paused int, is_stale int)")
    named = {d for d, _t, _s, _a in rows}
    connection.executemany(
        "insert into dag values (?,?,?)",
        [(d, *(dags or {}).get(d, (0, 0))) for d in sorted(named)])
    return [r[0] for r in connection.execute(statement)]


def test_a_task_that_failed_and_then_recovered_is_not_reported():
    """"HAS FAILED" IS NOT "IS FAILING", AND THE FIRST VERSION COULD NOT TELL THEM APART.

    It reported any failure inside the six-hour window whatever happened afterwards, so a
    task that failed once and succeeded on the next run stayed on the alarm for six hours. On
    2026-09-04 that put three healthy tasks up at once — a distribution test fixed twenty
    minutes earlier, a scores dbt_test with eight successes behind it, and a build from
    fourteen hours before.

    An alarm that is always on is the same failure as an alarm that never fires: this
    project's "silence is not success" entry was written after four days of unnoticed
    downtime, and a permanently-red board is how the NEXT four days go unnoticed.

    NEGATIVE-TESTED IN THE SAME FUNCTION — drop `recency = 1` and the recovered task comes
    back, which is the behaviour that shipped.
    """
    rows = [
        # failed, then recovered — must be silent
        ("lines", "dbt_test", "failed", 130),
        ("lines", "dbt_test", "success", 10),
        # succeeded, then broke — must be reported
        ("scores", "publish", "success", 200),
        ("scores", "publish", "failed", 20),
        # failed and has not run since — still broken, still reported
        ("sync", "to_databricks", "failed", 300),
        # never failed
        ("weekly", "load", "success", 45),
    ]
    reported = _run_failure_sql(rows)
    assert reported == ["failed|scores.publish|1200", "failed|sync.to_databricks|18000"], \
        reported

    broken = _failure_sql().replace("where ranked.recency = 1 and ranked.state = 'failed'",
                                    "where ranked.state = 'failed'")
    assert broken != _failure_sql(), "the recency filter was not found to remove"
    without = _run_failure_sql(rows, broken)
    assert any("lines.dbt_test" in line for line in without), (
        "removing `recency = 1` did not resurrect the recovered task, so it is not what "
        "suppresses it")


def test_a_failure_outside_the_window_is_not_reported():
    """The window still BOUNDS it, and A180 kept that on purpose.

    ⚠️ Reporting the newest state for all time would match "nothing has shown it recovered"
    most literally and would also keep a RENAMED task on the alarm forever — an always-on
    alarm, which this file's own comments call the same failure wearing the opposite mask. A
    finite window lets a task that no longer exists age out.

    A180 moved it 6 hours -> 8 days, sized to the slowest DAG (weekly) plus a day of slack.
    """
    day = 24 * 60
    assert _run_failure_sql([("old", "task", "failed", 9 * day)]) == []
    assert _run_failure_sql([("recent", "task", "failed", 7 * day)]) == \
        ["failed|recent.task|604800"]


# === the ASSERTION, not just the task — R-698 ==============================================

def test_the_watcher_parses_the_failed_test_line(monkeypatch):
    """R-412 BUILT THIS PAYLOAD AND NOTHING EVER READ IT. R-698.

    `cfdb_heartbeat.sh` has emitted `failed_test|<name>|<failures>|<age>` since R-412, whose
    entire purpose was that an alert could name the ASSERTION rather than only the task —
    `dbt_test` runs a selector, so the task name structurally cannot say what broke.

    The watcher knew two shapes and not this one. `head` was `failed_test`, which is not
    `failed`, so it fell through to the heartbeat branch, `int("assert_...|1|6583")` raised
    ValueError, and the line was silently discarded.

    MEASURED COST: on 2026-09-11 `assert_every_serving_row_names_its_team` began failing at
    17:36 PDT and the scores publish stopped with it. The switch fired at 23:28 with four
    error lines and not one named the test. A109 read it out of the warehouse by hand.
    """
    module = _watcher()
    _fake_ssh(monkeypatch, module,
              "scores_refresh|600\n"
              "failed_test|assert_every_serving_row_names_its_team|1|6583\n")
    ages, failures, failed_tests, _unboxed = module.read_ages("host")
    assert ages == {"scores_refresh": 600}
    assert failures == {}
    assert failed_tests == {"assert_every_serving_row_names_its_team": (1, 6583)}


def test_a_failed_assertion_fails_the_watcher_and_names_itself(monkeypatch, capsys):
    """Every beat fresh and the publish dead — the exact shape of 2026-09-11 evening."""
    module = _watcher()
    fresh = "\n".join(f"{name}|60" for name in module.CADENCES)
    _fake_ssh(monkeypatch, module,
              fresh + "\nfailed_test|assert_every_serving_row_names_its_team|1|6583\n")
    assert module.main(["host"]) == 1
    printed = capsys.readouterr().out
    assert "assert_every_serving_row_names_its_team" in printed, (
        "the alert must name the assertion; naming the task is what R-412 set out to fix")
    assert "1 row(s)" in printed, "how many rows failed is the difference between a typo and a gap"
    assert "did not run" in printed, "it must say what the failure COST"


def test_the_forced_command_and_the_watcher_agree_on_the_failed_test_shape():
    """THE GUARD THAT WAS MISSING, AND ITS ABSENCE IS WHY THIS SURVIVED TO PRODUCTION.

    `test_the_forced_command_reports_failures_in_the_shape_the_watcher_parses` already pins the
    `failed|` contract — and stopped there. R-412 added a SECOND payload with a different
    prefix and no test tied the two ends of it together, so the script emitted a line the
    watcher threw away and everything looked green.

    The script and the checker deploy separately — shell to the droplet by scp, checker on
    GitHub — so the shapes can only be held together by a test.
    """
    from pathlib import Path as _Path
    root = _Path(__file__).resolve().parents[1]
    script = (root / "deploy" / "cfdb_heartbeat.sh").read_text()
    code = "\n".join(ln for ln in script.splitlines() if not ln.lstrip().startswith("#"))
    assert "'failed_test|'" in code, (
        "the forced command no longer emits the per-test payload; the alert would go back to "
        "naming only the task, which is what R-412 existed to fix")

    watcher = (root / "ci" / "check_heartbeats.py").read_text()
    assert '"failed_test"' in watcher, (
        "the watcher does not parse the payload the script sends; this is exactly the gap "
        "R-698 closed, and it cost a twelve-hour game-day publish outage")


# === A180: the alarm must not forget a WEEKLY failure (cfdb-main-R-1861) ====================

def test_the_alarm_still_reports_a_weekly_failure_seven_hours_later():
    """🚨 A179's INCIDENT, REPLAYED. THIS IS THE BUG, AND IT SHIPPED GREEN.

    📊 `cfbd_results_refresh` is WEEKLY — `"0 12 * * 0"`, Sunday 12:00 UTC. On 2026-09-20 its
    `fetch` failed at 12:48:38 after three attempts; `load_to_postgres`, `dbt_run`,
    `dbt_catalogue`, `dbt_test`, `publish_to_serving` and `heartbeat` all sat at
    `upstream_failed`, and **nothing ran after it**. The switch reported GREEN from 19:41 —
    fifty-three minutes after the failure left the six-hour window — on a pipeline that had
    published nothing and would not run again for seven days.

    ✅ THE OLD QUERY IS SHOWN GREEN ON THIS EXACT TIMELINE FIRST, because a test that only
    proves the new behaviour cannot show that the behaviour CHANGED (register rule 10).

    ⚠️ AND THE SECOND HALF IS THE ONE A LONGER WINDOW MAKES NECESSARY: over eight days a DAG
    can be paused or deleted, and a failure from one nobody runs any more is noise. The join
    to `dag` is what drops those, and it is asserted here rather than assumed.
    """
    seven_hours = 7 * 60
    timeline = [("cfbd_results_refresh", "fetch", "failed", seven_hours)]

    # ── the bug, reproduced on the query as it was ──────────────────────────────────────
    # The window is substituted straight to sqlite's clock here — six hours, as it was — so
    # the helper's own 8-day replacement finds nothing and leaves this one alone.
    old_query = _failure_sql().replace("end_date > now() - interval '8 days'",
                                       f"end_date > {NOW_MINUTES - 360}")
    assert old_query != _failure_sql(), "the window literal was not found to narrow"
    old_style = _run_failure_sql(timeline, sql=old_query)
    assert old_style == [], (
        "the six-hour window was supposed to LOSE this failure — if it reports it, this "
        "test is no longer reproducing A179's incident")

    # ── and the fix ─────────────────────────────────────────────────────────────────────
    assert _run_failure_sql(timeline) == ["failed|cfbd_results_refresh.fetch|25200"], (
        "a weekly task that failed seven hours ago, with nothing run since, is still broken")

    # Still reported the day before its next scheduled run, which is the point of eight days.
    assert _run_failure_sql(
        [("cfbd_results_refresh", "fetch", "failed", 6 * 24 * 60)]) != []

    # ── a paused or deleted DAG is noise, not an alarm ──────────────────────────────────
    assert _run_failure_sql(timeline, dags={"cfbd_results_refresh": (1, 0)}) == [], \
        "a PAUSED dag's failure must not sit on the alarm"
    assert _run_failure_sql(timeline, dags={"cfbd_results_refresh": (0, 1)}) == [], \
        "a STALE dag — its file is gone — must not sit on the alarm"

    # ⚠️ And recovery still silences it, which the longer window must not have broken.
    assert _run_failure_sql([
        ("cfbd_results_refresh", "fetch", "failed", seven_hours),
        ("cfbd_results_refresh", "fetch", "success", 30),
    ]) == []


def test_every_scheduled_dag_runs_more_often_than_the_alarm_forgets():
    """🚨 THE WINDOW IS A CONSTANT AND THE CADENCES ARE NOT — so this is the guard that keeps
    them in agreement, and it is the reason A180 chose one window over a window per DAG.

    📊 Five of the eight scheduled DAGs have a cadence longer than the old six hours: two
    daily and three weekly. A DAG added tomorrow on a fortnightly schedule would be invisible
    to the alarm between runs, and nothing else in this repository would say so.
    """
    import re as _re
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[1]
    window = _re.search(r"end_date > now\(\) - interval '(\d+) (days|hours)'",
                        (root / "deploy" / "cfdb_heartbeat.sh").read_text())
    assert window, "the failure window moved or changed shape"
    hours = int(window.group(1)) * (24 if window.group(2) == "days" else 1)

    # cron -> the longest gap between two runs, for the shapes this project actually uses.
    def longest_gap_hours(cron):
        minute, hour, _dom, _mon, dow = cron.split()
        if hour.startswith("*/"):
            return int(hour[2:])
        if dow != "*":                      # a named weekday: once a week
            return 7 * 24
        return 24                           # a fixed hour every day

    schedules = {}
    for path in (root / "dags").glob("*_dag.py"):
        text = path.read_text()
        for cron in _re.findall(r'"(\d+ [\d*/]+ \* \* [\d*]+)"', text):
            schedules[f"{path.name}:{cron}"] = longest_gap_hours(cron)
    assert schedules, "no schedules were found — this test is reading the wrong thing"

    too_slow = {k: v for k, v in schedules.items() if v >= hours}
    assert not too_slow, (
        f"these DAGs run less often than the alarm's {hours}h window, so a failure would "
        f"scroll out of view before the next run could clear it: {too_slow}")


# === A182: the OUTCOME line — are finished games on the site? (cfdb-main-R-1866) ============

def test_the_watcher_parses_the_unboxed_line_and_fails_on_it(monkeypatch, capsys):
    """🚨 A182. THE ONLY SIGNAL IN THIS SYSTEM THAT SPEAKS ABOUT THE SITE.

    > **MARC, 2026-09-20:** *"The data has to load and it has to be presented on the site. …
    > Saturday into Sunday is an unacceptable time to fail to load a full slate of game
    > results. Unacceptable."*

    📊 Every other line measures the machinery, and on 2026-09-19 every one of them read green
    while the whole slate was missing from the site for over a day. This replays that: 150 FBS
    team-games, oldest ~28 hours, week 3 — the real numbers A182 measured before the fix.

    ⚠️ AND IT MUST BE A FAILURE, NOT A NOTE. R-698's lesson is that a payload nothing acts on
    is worse than no payload, because it looks like coverage.
    """
    fresh = {name: 60 for name in chk.CADENCES}
    monkeypatch.setattr(chk, "read_ages",
                        lambda _h: (fresh, {}, {}, (150, 100_800, "w3")))
    assert chk.main(["host"]) == 1, "finished games missing from the site must FAIL the check"
    out = capsys.readouterr().out
    assert "UNBOXED 150" in out, out
    assert "week(s) w3" in out, "it must say WHICH weeks, not just how many (R-412)"


def test_the_unboxed_line_is_silent_when_the_site_is_current(monkeypatch, capsys):
    """⚠️ THE OTHER HALF, AND THE ONE THAT KEEPS THE ALARM CREDIBLE. An always-on alarm is the
    same failure as a silent one — this file argues that at length about the failure window —
    so a site with nothing outstanding must produce no line at all."""
    fresh = {name: 60 for name in chk.CADENCES}
    for payload in (None, (0, 0, "-")):
        monkeypatch.setattr(chk, "read_ages", lambda _h, p=payload: (fresh, {}, {}, p))
        assert chk.main(["host"]) == 0, payload
        assert "UNBOXED" not in capsys.readouterr().out


def test_an_older_forced_command_without_the_unboxed_line_still_parses(monkeypatch):
    """⚠️ THE DROPLET AND THE WATCHER DEPLOY SEPARATELY, so for a window the watcher is newer
    than the forced command. A missing line must read as "nothing to report", never as a crash
    — the same property the `failed_test` line needed when it was added."""
    lines = "scores_refresh|120\nlines_snapshot|300\n"
    import types as _types

    monkeypatch.setattr(chk.subprocess, "run",
                        lambda *a, **k: _types.SimpleNamespace(stdout=lines, returncode=0))
    ages, failures, failed_tests, unboxed = chk.read_ages("host")
    assert ages == {"scores_refresh": 120, "lines_snapshot": 300}
    assert unboxed is None and not failures and not failed_tests


def test_the_forced_command_emits_the_unboxed_line_against_published_serving():
    """🚨 THE QUERY MUST RUN AGAINST **PUBLISHED SERVING**, NOT THE WAREHOUSE, and that is the
    distinction this whole incident turned on: the warehouse holding the data and the site
    showing it are different facts (R-878, and again in A179's first reading).

    ⚠️ Asserted on the script's text because there is no droplet in CI — the same limit the
    other forced-command tests carry, and narrow on purpose.
    """
    from pathlib import Path as _Path

    script = (_Path(__file__).resolve().parents[1]
              / "deploy" / "cfdb_heartbeat.sh").read_text()
    code = "\n".join(ln for ln in script.splitlines() if not ln.lstrip().startswith("#"))

    assert "'unboxed|'" in code, "the forced command no longer emits the outcome line"
    assert "SERVING_PSQL" in code, (
        "the outcome query must use the serving connection, not the warehouse one — the "
        "warehouse having the data is not the site showing it")
    assert "has_box_score" in code and "has_box_advanced" in code
    assert "cannot_read_published_serving" in code, (
        "it must degrade LOUDLY, like the airflow query does — a monitor that cannot see is "
        "not a monitor reporting nothing wrong")
    # Current season only: 2023 and earlier legitimately have no box scores at all.
    assert "select max(season)" in code, (
        "without a season bound this fires on ~1,800 pre-2024 team-games forever, and an "
        "always-on alarm is the same failure as a silent one")
