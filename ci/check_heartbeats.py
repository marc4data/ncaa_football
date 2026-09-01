"""The dead-man's switch: alert when a heartbeat stops arriving.

RUNS ON GITHUB ACTIONS, NOT ON THE DROPLET, and that placement is the whole design. Every
check this project had before ran on the machine it was checking, so when the laptop stack
was down from 24 to 28 August nothing noticed — the watcher was off too. A monitor that
shares fate with the thing it monitors is not a monitor.

GitHub Actions was chosen over a hosted check service (healthchecks.io, Cronitor, Dead Man's
Snitch). Cost is the same — all are free at this size — but Actions needs no new account, no
new credential to rotate, and it already runs this repository's CI, so its failure emails go
somewhere Marc already reads. The trade is that a GitHub outage silences the monitor; that is
acceptable for a check whose job is catching multi-day silence, and it is visible rather than
silent because the workflow run itself would be missing.

HOW IT REACHES THE HEARTBEATS. An SSH forced command (deploy/cfdb_heartbeat.sh) that can do
exactly one thing: print name|age pairs. The key cannot open a shell, cannot run any other
command, and cannot reach Docker. If the droplet is unreachable at all, this script fails —
which is not an error to be handled but the alarm itself, and the loudest case there is.

THRESHOLDS LIVE HERE, NOT ON THE DROPLET. A box that is off cannot tell you its thresholds
changed, so cadence policy belongs with the watcher.
"""
import subprocess
import sys

# Expected cadence per heartbeat, and the age at which absence means something is wrong.
#
# Each budget is the schedule interval plus room for one missed run plus the run's own
# duration — deliberately loose. A dead-man's switch that cries wolf gets muted, and a muted
# switch is worse than none because it looks like coverage. These catch "stopped for a day",
# which is the failure that actually happened, not "was forty minutes late".
CADENCES = {
    # every 2 hours, gated — beats on a deliberate skip too, so the clock never stops
    "scores_refresh": ("every 2 hours", 5 * 3600),
    # every 4 hours, gated, same
    "lines_snapshot": ("every 4 hours", 9 * 3600),
    # Sunday 12:00 UTC
    "weekly_results": ("Sundays", 8 * 24 * 3600),
    # Tuesday 12:00 UTC
    "weekly_pregame": ("Tuesdays", 8 * 24 * 3600),
    # Thursday 12:00 UTC
    "weekly_midweek": ("Thursdays", 8 * 24 * 3600),
}

SSH_TIMEOUT_SECONDS = 60


def read_ages(host: str) -> dict:
    """name -> seconds since last beat, via the forced command. Raises if unreachable."""
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
         "-o", f"ConnectTimeout={SSH_TIMEOUT_SECONDS}", host, "heartbeat"],
        capture_output=True, text=True, timeout=SSH_TIMEOUT_SECONDS * 2)
    if result.returncode != 0:
        raise RuntimeError(
            f"could not read heartbeats from {host} (exit {result.returncode}): "
            f"{result.stderr.strip()[:400]}")
    ages = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        name, _, age = line.partition("|")
        try:
            ages[name.strip()] = int(age)
        except ValueError:
            continue
    return ages


def describe(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


def main(argv=None) -> int:
    host = (argv or sys.argv[1:] or ["cfdb_monitor@localhost"])[0]

    try:
        ages = read_ages(host)
    except Exception as error:                                           # noqa: BLE001
        # THE DROPLET BEING UNREACHABLE IS THE ALARM, not a reason to exit quietly.
        print(f"::error::the pipeline host is unreachable — {error}")
        return 1

    stale, missing, ok = [], [], []
    for name, (cadence, budget) in sorted(CADENCES.items()):
        if name not in ages:
            missing.append(f"{name} ({cadence}): NEVER BEAT")
            continue
        age = ages[name]
        (ok if age <= budget else stale).append(
            f"{name} ({cadence}): last beat {describe(age)} ago, budget {describe(budget)}")

    for line in ok:
        print(f"  ok      {line}")
    for line in stale:
        print(f"  STALE   {line}")
    for line in missing:
        print(f"  MISSING {line}")

    unknown = sorted(set(ages) - set(CADENCES))
    if unknown:
        # Not a failure: a new DAG that beats before anyone adds it here is better than one
        # that does not beat at all. Worth saying so it gets a budget.
        print(f"\n  note: beating but unmonitored — {', '.join(unknown)}")

    if stale or missing:
        print()
        for line in stale + missing:
            print(f"::error::heartbeat absent — {line}")
        print("::error::the pipeline has stopped emitting on at least one cadence. "
              "Silence is not success.")
        return 1

    print(f"\nAll {len(ok)} cadences beating within budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
