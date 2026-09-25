"""The merge gate that makes §2.2.3 mechanical — A232.

> **§2.2.3:** *"A red publish path stops feature work in both sessions until it is green."*

🚨 **THAT RULE HAS BEEN BROKEN THREE TIMES, THE LAST TIME BY ITS OWN AUTHOR**, and the 09-24
stoppage was found by accident — it surfaced as a sixth check run on A227's merge commit.

⚠️ **EVERY TEST HERE FEEDS THE GATE A SYNTHETIC PAYLOAD.** That is the answer to *"build a way
to test it that does not depend on making production look broken"*: the gate's decision is a
pure function of the monitor's output, and `--payload-file` is the seam. Nothing in this file
opens an SSH session, and nothing needs the pipeline to be in any particular state.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ci.check_publish_path import (CADENCES, GREEN, OVERRIDE_TRAILER,   # noqa: E402
                                   PUBLISH_CADENCES, RED, UNDETERMINED,
                                   override_reason, verdict)

# A payload with every publish cadence fresh, in the monitor's own line shapes.
FRESH = "\n".join([
    "scores_refresh|1800",
    "lines_snapshot|3600",
    "weekly_results|86400",
    "weekly_pregame|86400",
    "weekly_midweek|86400",
    "unboxed|0|0|-",
    "unplayered|0|0|-",
    "undriven|0|0|-",
    "uncurved|0|0|-",
])


def test_a_fresh_pipeline_is_green():
    state, reasons = verdict(FRESH)
    assert state == GREEN, reasons
    assert reasons == []


@pytest.mark.parametrize("name", PUBLISH_CADENCES)
def test_any_publish_cadence_past_its_budget_is_red(name):
    """📊 THE BUDGET IS READ FROM `CADENCES`, NOT RESTATED HERE (R-574). A budget changed in
    the alarm and not in the gate would leave the two testing different numbers, silently."""
    _cadence, budget = CADENCES[name]
    stale = FRESH.replace(f"{name}|", "").replace("\n\n", "\n")
    stale = stale + f"\n{name}|{budget + 60}"
    state, reasons = verdict(stale)
    assert state == RED, reasons
    assert any(name in r for r in reasons), reasons


def test_a_failed_gated_task_is_red_even_while_every_cadence_is_still_fresh():
    """🚨 THIS IS THE 09-24 CASE AND IT IS WHY STALENESS ALONE IS NOT ENOUGH.

    The assertion went red at 06:43Z. The cadences did not cross their budgets for hours
    afterwards, so a gate watching only staleness would have passed every merge that morning
    — including the one that actually happened.
    """
    state, reasons = verdict(FRESH + "\nfailed|cfbd_lines_snapshot.dbt_test_distributions|300")
    assert state == RED
    assert any("dbt_test_distributions" in r for r in reasons), reasons


def test_the_09_24_stoppage_would_have_been_caught():
    """A REPLAY, LABELLED AS ONE — built from what A230 measured, not read from that day.

    The three lines the switch printed on 2026-09-24:
        FAILED  cfbd_lines_snapshot.dbt_test_distributions
        FAILED  cfbd_midweek_results.dbt_test
        FAILED  assert_distribution_whiskers_stay_inside_the_data: 44 row(s)
    """
    payload = FRESH + "\n".join([
        "", "failed|cfbd_lines_snapshot.dbt_test_distributions|60",
        "failed|cfbd_midweek_results.dbt_test|22080",
        "failed_test|assert_distribution_whiskers_stay_inside_the_data|44|60"])
    state, reasons = verdict(payload)
    assert state == RED
    # It must name WHICH signal and WHEN — a bare failure is what this replaces.
    joined = " ".join(reasons)
    assert "assert_distribution_whiskers_stay_inside_the_data" in joined
    assert "44 row(s)" in joined
    assert "6h" in joined, f"the age of the older failure is not reported: {joined}"


def test_an_outcome_line_alone_does_not_block_a_merge():
    """⚠️ THE GATE IS NARROWER THAN THE ALARM, DELIBERATELY.

    *"Last night's games have no box scores"* is a real defect and the switch's job to shout
    about. It is not "the publish path is red". **A gate that fires on everything gets
    overridden every time, which is the same as not existing.**
    """
    state, _ = verdict(FRESH.replace("unboxed|0|0|-", "unboxed|12|7200|wk3"))
    assert state == GREEN


@pytest.mark.parametrize("payload", ["", "   ", "hello\nworld", "MONITOR.unreachable"])
def test_a_payload_with_no_cadence_is_undetermined_and_never_green(payload):
    """🚨 R-2254 — AN EMPTY COLLECTION IS NOT A PASS.

    A parser that read zero cadences has learned nothing. Reporting "no faults found" from a
    reader that found nothing at all is the vacuous pass this project keeps paying for, and
    here it would be a green check on a PR while the gate measured precisely nothing.
    """
    state, reasons = verdict(payload)
    assert state == UNDETERMINED, reasons
    assert reasons, "an undetermined verdict with no reason tells the reader nothing"


def test_the_three_states_are_distinguishable_from_one_another():
    """AC-G.11: an absence must say WHICH absence it is. Green, red and unreadable are three
    different facts about the pipeline and a reader of the check must never have to guess."""
    assert len({GREEN, RED, UNDETERMINED}) == 3
    green, _ = verdict(FRESH)
    red, red_why = verdict(FRESH + "\nfailed|some_dag.dbt_test|60")
    unk, unk_why = verdict("")
    assert green != red != unk and green != unk
    assert "could not" in unk_why[0] or "did not happen" in unk_why[0], unk_why
    assert "retries" in red_why[0] or "failing" in red_why[0], red_why


# ── the override ──────────────────────────────────────────────────────────────────────────

def test_the_override_is_a_commit_trailer_and_carries_its_reason():
    """🚨 A230 WOULD HAVE BEEN BLOCKED BY THIS GATE. A round that FIXES the red path has to be
    mergeable while the path is red, or the gate makes the outage permanent."""
    assert override_reason(
        f"A230: fix it\n\n{OVERRIDE_TRAILER} this round fixes the red path\n"
    ) == "this round fixes the red path"


def test_an_ordinary_commit_does_not_override_anything():
    assert override_reason("A231: the week in one row\n\nCo-Authored-By: someone\n") is None
    assert override_reason("") is None


def test_the_trailer_is_matched_as_a_trailer_and_not_as_a_substring():
    """⚠️ R-2260 — A SUBSTRING IS NOT A RULE. A commit that DISCUSSES the override in prose
    must not thereby perform one, or every report-writing commit disarms the gate."""
    assert override_reason(
        f"A232: build the gate\n\nThe override is a `{OVERRIDE_TRAILER} <reason>` trailer.\n"
    ) is None
    assert override_reason("Mentioning Publish-path-override in the middle of a line") is None


def test_the_override_reports_itself_rather_than_passing_silently():
    """An override that leaves no trace is a gate that quietly stops existing."""
    source = (ROOT / "ci" / "check_publish_path.py").read_text()
    body = source[source.index("if override:"):]
    assert "::warning::" in body[:400], "an override must annotate the run, not pass quietly"
    assert "Reason:" in body[:400], "the override must print WHY"


# ── the gate as a program ─────────────────────────────────────────────────────────────────

def _run(*args, cwd=ROOT):
    return subprocess.run([sys.executable, "ci/check_publish_path.py", *args],
                          cwd=cwd, capture_output=True, text=True, timeout=120)


def test_the_program_exits_zero_on_green(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text(FRESH)
    done = _run("--payload-file", str(f), "--base", "HEAD")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "publish path: GREEN" in done.stdout


def test_the_program_exits_non_zero_on_red_and_names_the_fault(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text(FRESH + "\nfailed_test|assert_something|7|900")
    done = _run("--payload-file", str(f), "--base", "HEAD")
    assert done.returncode == 1, done.stdout
    assert "publish path: RED" in done.stdout
    assert "assert_something" in done.stdout
    assert "::error::" in done.stdout


def test_the_program_fails_CLOSED_when_it_cannot_read_the_state(tmp_path):
    """🚨 FAIL-CLOSED, AND THE OVERRIDE IS THE REASON IT IS AFFORDABLE.

    Fail-open means the gate silently stops protecting on exactly the days something else is
    also wrong — the failure mode this whole round exists to close. Fail-closed would be the
    wrong trade if proceeding were expensive; it is one trailer on one commit, which leaves a
    permanent record of who decided to proceed and why.
    """
    f = tmp_path / "p.txt"
    f.write_text("")
    done = _run("--payload-file", str(f), "--base", "HEAD")
    assert done.returncode == 1, done.stdout
    assert "publish path: UNDETERMINED" in done.stdout
    # and it must not be mistaken for red
    assert "UNREADABLE" in done.stdout and "is RED" not in done.stdout


def test_an_unconfigured_host_is_undetermined_rather_than_green():
    """A gate whose secret is missing and which passes anyway is worse than no gate: the
    check is on the PR, it is green, and it is measuring nothing."""
    done = subprocess.run([sys.executable, "ci/check_publish_path.py", "--base", "HEAD"],
                          cwd=ROOT, capture_output=True, text=True, timeout=120,
                          env={"PATH": "/usr/bin:/bin", "MONITOR_HOST": ""})
    assert done.returncode == 1, done.stdout
    assert "UNDETERMINED" in done.stdout


def test_the_gate_reads_the_alarms_budgets_rather_than_carrying_its_own():
    """R-574 in the shape that actually bites: two copies of a number, free to disagree."""
    for name in PUBLISH_CADENCES:
        assert name in CADENCES, f"{name} is not a cadence the monitor knows about"


# ── the gate must not become a fifth thing that can be wrong without anyone knowing ───────

@pytest.fixture(scope="module")
def ci_workflow():
    import yaml
    return yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())


def test_the_gate_actually_runs_on_every_pull_request(ci_workflow):
    """🚨 A CHECK THAT IS NOT WIRED IS A CHECK THAT IS ALWAYS GREEN — by absence.

    The whole point of this round is a signal nobody has to remember to look at. If the job
    were dropped from `ci.yml`, every PR would go green with no publish-path check at all and
    nothing would say so — which is the 09-24 failure with an extra step.
    """
    assert "publish-path" in ci_workflow["jobs"], "the gate job is gone from ci.yml"
    # `on: pull_request:` parses to None when it carries only `branches:`; what matters is
    # that the trigger is present at all.
    triggers = ci_workflow[True] if True in ci_workflow else ci_workflow["on"]
    assert "pull_request" in triggers


def test_the_gate_job_checks_out_deep_enough_to_read_the_override(ci_workflow):
    """⚠️ `fetch-depth: 0` IS LOAD-BEARING. The override is a trailer read from
    `origin/main..HEAD`; a shallow clone has no `origin/main`, so the gate would fall back to
    HEAD alone and miss a trailer on an earlier commit of the branch — an override that
    silently does not work is worse than none, because the author believes they overrode."""
    steps = ci_workflow["jobs"]["publish-path"]["steps"]
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout.get("with", {}).get("fetch-depth") == 0


def test_a_missing_secret_does_not_short_circuit_the_gate_to_green(ci_workflow):
    """🚨 THE KEY-INSTALL STEP MUST NOT `exit 1` AND MUST NOT SKIP THE GATE.

    The dead-man's switch fails outright when its secrets are unset, which is right for an
    alarm. Here it would turn the missing-secret case into a RED that looks like a broken
    pipeline, and skipping the gate would turn it into a GREEN that measured nothing.
    **It has to reach the gate and be reported as UNDETERMINED.**
    """
    steps = ci_workflow["jobs"]["publish-path"]["steps"]
    install = next(s for s in steps if "Install the monitoring key" in str(s.get("name", "")))
    assert "exit 0" in install["run"], (
        "a missing secret must fall through to the gate, which reports UNDETERMINED")
    gate = steps[-1]
    assert "check_publish_path.py" in gate["run"]
    assert "if" not in gate, "the gate step must not be conditional on the secret existing"


def test_the_check_name_is_the_one_branch_protection_would_select(ci_workflow):
    """⚠️ BRANCH PROTECTION IS A GITHUB SETTING, NOT A FILE — this round ships the check and
    cannot ship the enforcement. The name is what Marc selects in that setting, so renaming
    the job silently detaches it from the protection rule."""
    assert ci_workflow["jobs"]["publish-path"]["name"] == "Publish path is green"


def test_a_green_verdict_shows_what_it_looked_at(tmp_path):
    """🚨 "SILENCE IS NOT SUCCESS" APPLIES TO THIS GATE'S OWN OUTPUT.

    A green check whose log says only "GREEN" reads, to a human, exactly like a green check
    that read nothing — and this round exists because a signal nobody looked at was treated
    as fine. `verdict` already guarantees an empty parse is UNDETERMINED; this makes the same
    fact visible to whoever opens the run.
    """
    f = tmp_path / "p.txt"
    f.write_text(FRESH)
    done = _run("--payload-file", str(f), "--base", "HEAD")
    assert done.returncode == 0
    for name in PUBLISH_CADENCES:
        assert name in done.stdout, f"a green run does not say it checked {name}"
    assert f"{len(PUBLISH_CADENCES)} of {len(PUBLISH_CADENCES)}" in done.stdout
