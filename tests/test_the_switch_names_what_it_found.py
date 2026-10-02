"""The dead-man's switch must never fail silently.

A278 · cfdb-main-R-4651.

🚨 **MEASURED FROM THE RUN MARC PASTED ON 2026-10-02:**

    ok  lines_snapshot (every 4 hours): last beat 2h 58m ago, budget 9h 0m
    …
    UNPLAYERED 2 FBS game(s) final with no player box score on the site — oldest 14h 59m, week(s) w5
    Error: Process completed with exit code 1.

**Not one `::error::` line.** `unboxed_now` is inside the condition that returns 1, but the
annotation block below it covered `stale`/`missing`, `failures` and `failed_tests` and nothing
else — so an OUTCOME failure exited 1 with a blank GitHub run summary and an email that named
nothing. The only way to learn what fired was to open the log.

## WHY THIS FILE ASSERTS AN INVARIANT RATHER THAN A LIST OF CASES

The named cases below are the ones that exist today, and a list of cases is exactly what went
stale: `OUTCOME_LINES` grew from one entry to five and the annotation block never followed.
**`test_no_exit_1_is_ever_silent` walks a product of input shapes and asserts the property —
if `main` returns 1 it printed at least one `::error::`.** A sixth outcome line, or a seventh
failure mode, is covered the day it is added rather than the day someone remembers this file.

⚠️ **IT DOES NOT ASSERT WHAT COUNTS AS A FAILURE.** Every outcome check exists because the site
was wrong and nothing said so; this round changed what the alarm SAYS, not what it fires on.
"""
import importlib.util
import itertools
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "check_heartbeats", ROOT / "ci" / "check_heartbeats.py")
switch = importlib.util.module_from_spec(_spec)
sys.modules["check_heartbeats"] = switch
_spec.loader.exec_module(switch)


def _healthy():
    """Every cadence fresh, nothing failed, every outcome head present and zero."""
    ages = {name: 60 for name in switch.CADENCES}
    outcomes = {head: (0, 0, "-") for head in switch.OUTCOME_LINES}
    return ages, {}, {}, outcomes


def run(monkeypatch, capsys, state):
    monkeypatch.setattr(switch, "read_ages", lambda host: state)
    code = switch.main(["cfdb_monitor@example"])
    out = capsys.readouterr().out
    return code, out, [ln for ln in out.splitlines() if ln.startswith("::error::")]


# ── the baseline, because every assertion below is a difference from it ───────────────────

def test_a_healthy_pipeline_exits_zero_and_annotates_nothing(monkeypatch, capsys):
    code, out, errors = run(monkeypatch, capsys, _healthy())
    assert code == 0, out
    assert errors == []
    assert "cadences beating within budget" in out


# ── the incident this round was written from ──────────────────────────────────────────────

def test_the_unplayered_incident_names_itself(monkeypatch, capsys):
    """🚨 THE EXACT SHAPE OF THE RUN MARC PASTED: healthy cadences, one outcome line."""
    ages, failures, failed_tests, outcomes = _healthy()
    outcomes["unplayered"] = (2, 53940, "w5")
    code, out, errors = run(monkeypatch, capsys, (ages, failures, failed_tests, outcomes))

    assert code == 1
    assert errors, "the run Marc pasted exited 1 and annotated NOTHING — that is the defect"
    joined = "\n".join(errors)
    assert "UNPLAYERED" in joined
    assert "2 FBS game(s)" in joined, "the count a reader needs is missing"
    assert "14h 59m" in joined, "the oldest age is missing"
    assert "w5" in joined, "the week is missing"


def test_a_content_gap_says_the_pipeline_is_beating(monkeypatch, capsys):
    """⚠️ THE HALF MARC ACTUALLY NEEDED. "The pipeline stopped" and "a feed is late" are
    different emergencies, and the reader should not have to reconstruct which one this is."""
    ages, failures, failed_tests, outcomes = _healthy()
    outcomes["unplayered"] = (2, 53940, "w5")
    _code, _out, errors = run(monkeypatch, capsys, (ages, failures, failed_tests, outcomes))
    assert any("BEATING" in e and "CONTENT gap" in e for e in errors), errors


def test_a_stale_beat_does_not_claim_the_pipeline_is_beating(monkeypatch, capsys):
    """🚨 THE CONTEXT LINE IS ONLY TRUE SOMETIMES, so it is only printed sometimes. A run with
    a dead cadence that announced "the pipeline is BEATING" would be worse than silence."""
    ages, failures, failed_tests, outcomes = _healthy()
    ages["scores_refresh"] = 99 * 3600
    outcomes["unplayered"] = (2, 53940, "w5")
    _code, _out, errors = run(monkeypatch, capsys, (ages, failures, failed_tests, outcomes))
    assert not any("BEATING" in e for e in errors), errors
    assert any("heartbeat absent" in e for e in errors), errors


# ── the two silent exits that are BLINDNESS rather than a gap ─────────────────────────────

def test_a_monitor_that_cannot_read_serving_says_so(monkeypatch, capsys):
    """`<head>|MONITOR.<why>|0|-` parses to a count of -1, which is TRUTHY — so it already
    exited 1, and said nothing."""
    ages, failures, failed_tests, outcomes = _healthy()
    outcomes["unplayered"] = (-1, 0, "MONITOR.cannot_read_published_serving")
    code, _out, errors = run(monkeypatch, capsys, (ages, failures, failed_tests, outcomes))
    assert code == 1
    assert any("BLIND" in e and "could not read published serving" in e for e in errors), errors


def test_a_missing_outcome_head_says_the_droplet_is_running_an_older_command(
        monkeypatch, capsys):
    """A185 (cfdb-main-R-1878): an absent line is BLIND, not quiet — and it is
    indistinguishable from a clean site unless the watcher insists on hearing the answer."""
    ages, failures, failed_tests, outcomes = _healthy()
    del outcomes["unplayered"]
    code, _out, errors = run(monkeypatch, capsys, (ages, failures, failed_tests, outcomes))
    assert code == 1
    assert any("BLIND" in e and "reported nothing" in e for e in errors), errors


# ── the paths that already annotated, pinned so a refactor cannot drop them ───────────────

@pytest.mark.parametrize("mutate,needle", [
    (lambda s: s[0].__setitem__("scores_refresh", 99 * 3600), "heartbeat absent"),
    (lambda s: s[0].pop("weekly_results"), "heartbeat absent"),
    (lambda s: s[1].__setitem__("cfbd_scores_refresh.dbt_test", 7200), "task failed"),
    (lambda s: s[2].__setitem__("assert_x", (4, 7200)), "dbt test failed"),
])
def test_the_paths_that_already_annotated_still_do(monkeypatch, capsys, mutate, needle):
    state = _healthy()
    mutate(state)
    code, _out, errors = run(monkeypatch, capsys, state)
    assert code == 1
    assert any(needle in e for e in errors), errors


# ── 🚨 THE INVARIANT ──────────────────────────────────────────────────────────────────────

def test_no_exit_1_is_ever_silent(monkeypatch, capsys):
    """🚨 IF `main` RETURNS 1 IT PRINTED AT LEAST ONE `::error::`. Always.

    The case list above will grow — `OUTCOME_LINES` went from one entry to five and the
    annotation block never followed, which is the whole defect. This walks a product of input
    shapes instead, so a new failure mode is covered the day it is added.
    """
    head = next(iter(switch.OUTCOME_LINES))
    perturbations = [
        ("healthy", lambda s: None),
        ("stale", lambda s: s[0].__setitem__("scores_refresh", 99 * 3600)),
        ("never-beat", lambda s: s[0].pop("weekly_pregame", None)),
        ("failed-task", lambda s: s[1].__setitem__("some.task", 3600)),
        ("failed-test", lambda s: s[2].__setitem__("assert_y", (1, 3600))),
        ("outcome-count", lambda s: s[3].__setitem__(head, (3, 7200, "w5"))),
        ("outcome-blind", lambda s: s[3].__setitem__(head, (-1, 0, "MONITOR.why"))),
        ("outcome-absent", lambda s: s[3].pop(head, None)),
    ]
    checked = 0
    for combination in itertools.chain.from_iterable(
            itertools.combinations(perturbations, n) for n in (1, 2, 3)):
        state = _healthy()
        for _name, mutate in combination:
            mutate(state)
        code, out, errors = run(monkeypatch, capsys, state)
        checked += 1
        if code == 1:
            assert errors, (
                "the switch exited 1 and printed no ::error:: — GitHub's summary would be "
                f"blank and the email would name nothing. Inputs: "
                f"{[n for n, _ in combination]}\n{out}")
    # R-760: every assertion above is satisfied by an empty walk.
    assert checked >= 90, f"only {checked} input shapes exercised"
