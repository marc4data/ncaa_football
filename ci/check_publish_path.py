r"""THE RED LIGHT STOPS THE LINE — §2.2.3, as a check rather than as a memory.

> **§2.2.3:** *"A red publish path stops feature work in both sessions until it is green."*

🚨 **THAT RULE HAS NOW BEEN BROKEN THREE TIMES, MOST RECENTLY BY ITS OWN AUTHOR** — Cowork
merged A227 into a red publish path on 2026-09-24. B154's judgement, which this round accepts:
*"A rule broken by its own author three times is not a discipline problem, it is evidence that
the rule needs a mechanism or should be deleted."*

📊 **AND THE 09-24 STOPPAGE WAS FOUND BY ACCIDENT** — the register's own words: *"Found because
it appeared as a sixth check run on A227's own merge commit."* **This makes the accident
deliberate.**

## WHY THIS READS THE DROPLET AND NOT THE SWITCH'S LAST RUN (cfdb-main-R-3107)

The obvious cheap design is to ask the GitHub API for the last `Dead-man's switch` conclusion.
📊 **MEASURED OVER 562 HOURS (2026-09-01 to 09-24), FROM THE ACTIONS API:** the `*/20` cron
asked for **1,686** runs and GitHub delivered **154** — 9%. Gaps between delivered runs: median
**212 minutes**, mean 220, **max 534**. **90% of gaps exceed two hours; 64 of 153 exceed four.**

🚨 **A GATE BUILT ON THAT IS STALE BY A MEDIAN OF 3.5 HOURS AND BY AS MUCH AS 8.9.** It would
block merges over a fault already fixed, and pass merges into a path that went red hours ago —
which is the opposite of what it is for. **So the gate reads the heartbeat ITSELF, live, over
the same restricted SSH forced command the switch uses.** Freshness: whatever the PR costs.

⚠️ **THE KEY IS A FORCED COMMAND THAT CAN ONLY PRINT HEARTBEAT AGES** — it cannot open a
shell, run anything else, or reach Docker (`deploy/cfdb_heartbeat.sh`). So running it from a CI
job is the exposure the switch already has, not a new one. **Reading `srv_system_health` or
`raw.raw_dbt_test_result` was rejected for the opposite reason: CI reaches no database today —
its only `PG_HOST` is the dbt job's own throwaway localhost — and giving a PUBLIC repo's CI
warehouse credentials to run a merge gate is a new secret surface for no extra freshness.**

## WHAT "RED" MEANS HERE, AND IT IS NARROWER THAN THE SWITCH'S

`ci/check_heartbeats.py` is the ALARM: it reports everything, including outcome lines about
what the site is missing. **This is a GATE, and a gate that fires on everything gets
overridden every time, which is the same as not existing.** So it fires on exactly §2.2.3's
own definition — **a publish that has not completed in its cadence's window** — plus a failed
task or assertion on a DAG that carries a publish.

⚠️ **AN OUTCOME LINE DOES NOT BLOCK A MERGE.** *"Last night's games have no box scores"* is a
real defect and is the switch's job to shout about; it is not "the publish path is red", and
conflating them is how a gate loses its meaning.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.check_heartbeats import (CADENCES, describe, fetch_payload,   # noqa: E402
                                 parse_payload)

# The cadences that carry a publish. §2.2.3 names `publish_to_serving` and
# `publish_distributions`; these are the two DAG cadences those tasks sit on, plus the three
# weekly ones, which also publish.
#
# ⚠️ READ FROM `CADENCES` RATHER THAN RESTATED, so a budget changed in one place cannot leave
# the gate testing a different number from the alarm (R-574).
PUBLISH_CADENCES = ("scores_refresh", "lines_snapshot",
                    "weekly_results", "weekly_pregame", "weekly_midweek")

# 🚨 THE OVERRIDE IS MANDATORY, NOT A NICETY — A230 WOULD HAVE BEEN BLOCKED BY THIS GATE.
# The round that FIXES a red publish path has to be mergeable while the path is red, or the
# gate makes the outage permanent.
#
# ⚠️ A COMMIT TRAILER RATHER THAN A LABEL, AND THE REASON IS THE TRACE. A label can be added
# to merge and removed afterwards, leaving a green PR and no record that the gate was ever
# bypassed — "an override that leaves no trace is a gate that quietly stops existing". A
# trailer is in the commit message, in `git log`, permanently, and it carries its own reason.
OVERRIDE_TRAILER = "Publish-path-override:"

GREEN, RED, UNDETERMINED = "GREEN", "RED", "UNDETERMINED"


def verdict(payload: str) -> tuple:
    """`(state, reasons)` for one heartbeat payload. Pure — no SSH, no clock, no network.

    🚨 AN EMPTY PAYLOAD IS `UNDETERMINED`, NEVER `GREEN` (R-2254). A parser that reads zero
    cadences out of a payload has learned nothing, and "no faults found" from a reader that
    found nothing at all is the exact shape of a vacuous pass. **The gate insists on hearing
    an answer about every publish cadence it knows.**
    """
    ages, failures, failed_tests, _outcomes = parse_payload(payload)

    if not ages:
        return UNDETERMINED, [
            "the monitor returned no heartbeat at all — it reported "
            f"{len(payload.splitlines())} line(s) and none of them was a cadence. This is not "
            "a green pipeline; it is a reading that did not happen."]

    reasons, seen = [], []
    for name in PUBLISH_CADENCES:
        cadence, budget = CADENCES[name]
        if name not in ages:
            reasons.append(f"{name} ({cadence}) has NEVER BEAT — the monitor knows the "
                           f"cadence and has no beat for it")
            continue
        seen.append(name)
        age = ages[name]
        if age > budget:
            reasons.append(f"{name} ({cadence}) last published {describe(age)} ago, past its "
                           f"{describe(budget)} budget")

    # 🚨 A FAILED TASK IS KNOWABLE THE MOMENT IT HAPPENS; ABSENCE TAKES HOURS. On 09-24 the
    # assertion went red at 06:43Z and the *cadence* did not go stale for hours after — so a
    # gate that watched only staleness would have let the whole morning's merges through.
    for task, age in sorted(failures.items()):
        reasons.append(f"a gated task has exhausted its retries: {task}, last failed "
                       f"{describe(age)} ago — anything downstream of it, including the "
                       f"publish, did not run")
    for name, (count, age) in sorted(failed_tests.items()):
        reasons.append(f"a dbt assertion is failing: {name} on {count} row(s), last failed "
                       f"{describe(age)} ago — `dbt_test` gates `publish` (§2.3)")

    if not seen:
        return UNDETERMINED, ["the monitor answered, and not about any publish cadence"] + reasons
    return (RED if reasons else GREEN), reasons


def override_reason(commit_messages: str):
    """The trailer's reason, or None. Case-insensitive on the key, never on the reason."""
    for line in commit_messages.splitlines():
        head, sep, rest = line.strip().partition(":")
        if sep and head.strip().lower() == OVERRIDE_TRAILER[:-1].lower():
            return rest.strip() or "(no reason given)"
    return None


def commit_messages(base: str = "origin/main") -> str:
    """Every commit message on this branch that is not on `base`.

    ⚠️ FALLS BACK TO HEAD ALONE rather than raising: in a shallow clone `base` may not exist,
    and a gate that crashes on its own convenience lookup is a gate that blocks everything.
    """
    for args in ([f"{base}..HEAD"], ["-1"]):
        try:
            done = subprocess.run(["git", "log", "--format=%B", *args],
                                  capture_output=True, text=True, timeout=30)
            if done.returncode == 0 and done.stdout.strip():
                return done.stdout
        except Exception:                                           # noqa: BLE001
            continue
    return ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", nargs="?", default=os.environ.get("MONITOR_HOST", ""))
    parser.add_argument("--payload-file", help="read the payload from a file instead of SSH; "
                                               "this is how the gate is tested")
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args(argv)

    if args.payload_file:
        payload, source = Path(args.payload_file).read_text(), args.payload_file
    elif not args.host:
        # 🚨 NOT CONFIGURED IS UNDETERMINED, NOT GREEN. A gate whose secret is missing and
        # which passes anyway is worse than no gate: the check is on the PR, it is green, and
        # it is measuring nothing.
        payload, source = None, "(no host configured)"
    else:
        source = "the pipeline host"
        try:
            payload = fetch_payload(args.host)
        except Exception as error:                                  # noqa: BLE001
            payload = None
            source = f"unreachable: {str(error)[:200]}"

    if payload is None:
        state, reasons = UNDETERMINED, [f"the publish path could not be read — {source}"]
    else:
        state, reasons = verdict(payload)

    override = override_reason(commit_messages(args.base))

    print(f"publish path: {state}")
    for line in reasons:
        print(f"  - {line}")

    if state == GREEN:
        print("::notice::The publish path is green. Read live from the pipeline host, not "
              "from the dead-man's switch's last scheduled run.")
        return 0

    # 🚨 FAIL-CLOSED ON UNDETERMINED, AND THE REASONING IS THE OVERRIDE.
    #
    # Fail-open means the gate silently stops protecting on exactly the days something else
    # is also wrong, and nobody notices — which is the failure mode this whole round exists
    # to close. Fail-closed on an unrelated outage would block all work, and that WOULD be
    # the wrong trade **if proceeding were expensive**. It is not: one trailer on one commit,
    # which leaves a permanent record of who decided to proceed and why.
    #
    # ⚠️ AND THE TWO STATES STAY DISTINGUISHABLE (AC-G.11): they print different words, carry
    # different annotations, and an override names which one it overrode. A reader of this
    # check never has to guess whether the path was red or merely unreadable.
    label = "RED" if state == RED else "UNREADABLE"
    if override:
        print(f"::warning::PUBLISH PATH {label} — OVERRIDDEN. Reason: {override}")
        print(f"::warning::The override is a `{OVERRIDE_TRAILER}` trailer on a commit in this "
              f"branch, so it stays in `git log` after the PR is merged.")
        return 0

    print(f"::error::The publish path is {label}, so this PR does not merge (§2.2.3). "
          f"To merge anyway — which is correct for a round that FIXES the publish path — add "
          f"a `{OVERRIDE_TRAILER} <reason>` trailer to a commit on this branch.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
