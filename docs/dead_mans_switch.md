# The dead-man's switch

**Silence is not success.** The laptop stack was down from 24 to 28 August 2026 and nobody
noticed for four days. Every alert this project had was of the form *something ran and
failed* — and nothing ran, so nothing failed, so nothing alerted. Four days of a dead
pipeline looked exactly like four quiet days.

Alerting cannot fire when nothing runs. The only construction that catches a stopped pipeline
is the inverse: the pipeline states it is alive on a known cadence, and something **outside
it** complains when that statement stops.

## The three pieces

| Piece | Where | What it does |
|---|---|---|
| `src/heartbeat.py` | in the pipeline | writes `ops.pipeline_heartbeat` and pings an optional URL |
| `deploy/cfdb_heartbeat.sh` | droplet, `/usr/local/bin/` | SSH forced command; prints `name\|age` and nothing else |
| `.github/workflows/heartbeat.yml` | GitHub Actions | reads the ages every two hours, fails when one is stale |

The monitor runs on GitHub because **a monitor that shares fate with the thing it monitors is
not a monitor**. Every check that could have caught the August outage was running on the
machine that was off.

## Cadences and budgets

Thresholds live in `ci/check_heartbeats.py`, with the watcher — a box that is off cannot tell
you its thresholds changed.

| Heartbeat | Cadence | Budget |
|---|---|---|
| `scores_refresh` | every 2 hours, gated | 5 hours |
| `lines_snapshot` | every 4 hours, gated | 9 hours |
| `weekly_results` | Sundays 12:00 UTC | 8 days |
| `weekly_pregame` | Tuesdays 12:00 UTC | 8 days |
| `weekly_midweek` | Thursdays 12:00 UTC | 8 days |

Budgets are deliberately loose — schedule interval plus a missed run plus the run's duration.
**A switch that cries wolf gets muted, and a muted switch is worse than none, because it
looks like coverage.** These catch "stopped for a day", which is the failure that happened.

## Two things that are easy to get wrong

**On success only.** A heartbeat from a failed run is a lie: it says healthy at the moment
the pipeline is not. Every beat is the last task on the success path, downstream of publish.
It is deliberately *not* downstream of `capture_dq`, which uses `all_done` and therefore
succeeds after a failure — attaching the beat there would make it say "alive" on exactly the
runs it exists to catch.

**Idle is not dead.** The scores and lines DAGs are gated, so a correct run outside a game
window does no work. Their heartbeats use `TriggerRule.NONE_FAILED` and their gates use
`ignore_downstream_trigger_rules=False`, so a deliberate skip still beats and a failure still
does not. Without this the pipeline would go silent all off-season and the monitor could not
tell that apart from a dead box.

## Rotating or revoking the key

The monitoring key is an SSH forced command that can only print heartbeat ages — it cannot
open a shell, run any other command, or reach Docker. Verified: `ssh cfdb_monitor@host 'cat
/etc/passwd'` returns the heartbeat listing, because client input is ignored entirely.

To revoke: delete `/home/cfdb_monitor/.ssh/authorized_keys` on the droplet. To rotate:
generate a new pair, replace that file, and `gh secret set CFDB_MONITOR_SSH_KEY`.

Two repository secrets arm it: `CFDB_MONITOR_SSH_KEY` and `CFDB_MONITOR_HOST`. Without both,
the workflow fails loudly rather than passing vacuously — an unarmed switch that reported
success would be the worst outcome available.

## The test that counts

Recorded in `docs/decision_log.md`. Deliberately silencing a cadence and watching the alarm
arrive is the only evidence that any of this works; a switch nobody has tripped is a switch
nobody knows is connected.
