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


# ── THE OUTCOME LINES: what the site is missing, as opposed to what the pipeline did ───────
#
# Each entry is `<head>: (LABEL, what a non-zero count means to a reader)`. The monitor emits
# `<head>|<count>|<oldest seconds>|<weeks>`, or `<head>|MONITOR.<why>|0|-` when it cannot read
# published serving at all.
#
# 🚨 EVERY ONE OF THESE WAS ADDED AFTER THE SITE WAS WRONG AND NOTHING SAID SO. `unboxed` after
# a full slate was absent for a day (A182); `unplayered` after the team half was fixed and three
# of four leaderboards stayed empty (A184); `undriven` and `uncurved` after A185 measured that
# drives and the curve were still a day late by design.
OUTCOME_LINES = {
    "unboxed": ("UNBOXED",
                "FBS team-game(s) final with no box score on the site"),
    "unplayered": ("UNPLAYERED",
                   "FBS game(s) final with no player box score on the site — Today's player "
                   "leaderboards are empty for those games"),
    "undriven": ("UNDRIVEN",
                 "FBS game(s) final with no drives on the site — Matchup's drive panel is "
                 "empty for those games"),
    "uncurved": ("UNCURVED",
                 "FBS game(s) final with no win-probability curve on the site — Matchup's "
                 "Win % chart and Today's sparklines are empty for those games"),
    # 🚨 A249 (cfdb-main-R-3472). THE FIFTH, AND IT IS WHAT MAKES `game/box/advanced` SAFE TO
    # DECOUPLE. That endpoint's failure no longer fails the weekly run (`Endpoint.optional`),
    # so the gap it can now leave has to be seen by something. ⚠️ A team-game, not a game:
    # `srv_game_team` is the grain, and one side of a fixture can have its advanced box while
    # the other does not.
    "unadvanced": ("UNADVANCED",
                   "FBS team-game(s) final with no advanced box score on the site — Matchup's "
                   "Advanced panel and the player-usage dots are empty for those team-games"),
}


def fetch_payload(host: str) -> str:
    """The forced command's raw output. Raises if the host is unreachable.

    🚨 A232 (cfdb-main-R-3107). SPLIT OUT OF `read_ages` SO THE PARSER CAN BE TESTED WITHOUT
    AN SSH SESSION. `ci/check_publish_path.py` gates merges on this payload, and a gate whose
    only test path is "make production look broken" is a gate nobody exercises.
    ⚠️ The existing switch tests monkeypatch `read_ages` WHOLESALE, so before this split
    **nothing in the suite had ever run the parser at all** — the shapes it knows were
    asserted only by the one production caller.
    """
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
         "-o", f"ConnectTimeout={SSH_TIMEOUT_SECONDS}", host, "heartbeat"],
        capture_output=True, text=True, timeout=SSH_TIMEOUT_SECONDS * 2)
    if result.returncode != 0:
        raise RuntimeError(
            f"could not read heartbeats from {host} (exit {result.returncode}): "
            f"{result.stderr.strip()[:400]}")
    return result.stdout


def read_ages(host: str) -> dict:
    """name -> seconds since last beat, via the forced command. Raises if unreachable."""
    return parse_payload(fetch_payload(host))


def parse_payload(text: str) -> tuple:
    """`(ages, failures, failed_tests, outcomes)` from the forced command's output."""
    ages, failures, failed_tests, outcomes = {}, {}, {}, {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        head, _, rest = line.partition("|")
        # 🚨 `failed_test|<name>|<failures>|<seconds ago>` — R-412's payload, WHICH NOTHING READ
        # UNTIL R-698. cfdb_heartbeat.sh has emitted this line since R-412 so that an alert could
        # name the ASSERTION instead of only the task. This parser knew two shapes and not this
        # one, so `head` fell through to the heartbeat branch below, `int("assert_...|1|6583")`
        # raised ValueError, and the line was silently discarded.
        #
        # ⚠️ THE COST, MEASURED: on 2026-09-11 `assert_every_serving_row_names_its_team` began
        # failing at 17:36 PDT and the scores publish stopped with it. The switch fired at 23:28
        # with four error lines and NOT ONE named the test — the name was in the payload the whole
        # time. A109 read it out of raw.raw_dbt_test_result by hand instead.
        # 🚨 `unboxed|<count>|<oldest seconds>|<weeks>` — A182 (cfdb-main-R-1866), THE OUTCOME
        # LINE, and it is the only one that speaks about the SITE rather than the pipeline.
        # Every other signal here says the machinery ran; this says whether a reader can see
        # last night's games. It was added because the 2026-09-19 slate was absent for over a
        # day while every machinery check read green.
        #
        # ⚠️ PARSED BEFORE THE HEARTBEAT BRANCH, for the reason R-698 records one paragraph
        # down: an unknown `head` falls through to `int(rest)`, raises ValueError, and the line
        # is silently DISCARDED. A payload nothing reads is worse than no payload, because it
        # looks like coverage.
        # 🚨 THE PLAYER HALF (A184, cfdb-main-R-1906). PARSED IN THE SAME BRANCH AS `unboxed`
        # AND BEFORE THE HEARTBEAT BRANCH, for R-698's reason: an unknown `head` falls through
        # to `int(rest)`, raises ValueError, and the line is silently discarded. A payload
        # nothing reads is worse than no payload, because it looks like coverage — and this is
        # the second line added to this parser for exactly that reason.
        # 🚨 ONE BRANCH FOR EVERY OUTCOME LINE — A185 (cfdb-main-R-1915). There were two
        # hand-written branches here and this round would have added two more, each a copy of
        # the last with a different noun. **That shape is how R-698 happened**: an unknown
        # `head` falls through to `int(rest)` below, raises ValueError, and the line is
        # silently discarded — a payload nothing reads, which looks exactly like coverage.
        #
        # ✅ `OUTCOME_LINES` is now the single place a new check is registered, and
        # `test_every_outcome_line_the_monitor_emits_is_parsed_here` reads the deployed shell
        # script and fails if the script emits a line this dict does not know. Adding a check
        # to the monitor and forgetting the watcher is no longer possible quietly.
        if head.strip() in OUTCOME_LINES:
            count, _, tail = rest.partition("|")
            age, _, weeks = tail.partition("|")
            # THE MONITOR SAYING IT CANNOT SEE IS ITSELF AN ALARM, NOT A LINE TO DISCARD.
            # `int('MONITOR.cannot_read_published_serving')` raises; the first draft of the
            # `unboxed` branch swallowed exactly that and reported a clean run.
            if count.strip().startswith("MONITOR."):
                outcomes[head.strip()] = (-1, 0, count.strip())
                continue
            try:
                outcomes[head.strip()] = (int(count), int(age), weeks.strip() or "-")
            except ValueError:
                pass
            continue
        if head.strip() == "failed_test":
            name, _, tail = rest.partition("|")
            count, _, age = tail.partition("|")
            try:
                failed_tests[name.strip()] = (int(count), int(age))
            except ValueError:
                continue
            continue
        # `failed|<dag>.<task>|<seconds ago>` — a different shape from a heartbeat line, and
        # deliberately so: a monitor running against an older forced command sees a name it
        # has no budget for and says so, rather than mis-reading a failure as a cadence.
        if head.strip() == "failed":
            task, _, age = rest.partition("|")
            try:
                failures[task.strip()] = int(age)
            except ValueError:
                continue
            continue
        try:
            ages[head.strip()] = int(rest)
        except ValueError:
            continue
    return ages, failures, failed_tests, outcomes


def describe(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


def main(argv=None) -> int:
    host = (argv or sys.argv[1:] or ["cfdb_monitor@localhost"])[0]

    try:
        ages, failures, failed_tests, outcomes = read_ages(host)
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

    # A FAILED TASK IS KNOWABLE THE MOMENT IT HAPPENS; ABSENCE TAKES HOURS.
    #
    # On 2026-09-04 `dbt_test` began failing at 02:27. The scores heartbeat did not cross its
    # five-hour budget until 05:07, and this watcher's own cadence — nominally two-hourly,
    # measured at 3.1 to 6.8 hours — pushed detection past eleven hours. The pipeline had
    # been publishing nothing since midnight and nothing said so.
    #
    # Reading failures directly turns that into one watcher run. It is reported as an ERROR
    # rather than a note because a failed task in a gated pipeline is not a transient: the
    # DAG has already exhausted its own retries by the time this sees it.
    for task, age in sorted(failures.items()):
        print(f"  FAILED  {task}: last failed {describe(age)} ago")

    # WHICH ASSERTION, NOT JUST WHICH TASK. `dbt_test` runs a selector, so the task name cannot
    # say what broke — that is the whole reason cfdb_heartbeat.sh sends the test name.
    for name, (count, age) in sorted(failed_tests.items()):
        print(f"  FAILED  {name}: {count} row(s), last failed {describe(age)} ago")

    # 🚨 THE OUTCOME LINES, REPORTED FIRST AMONG THE FAULTS BECAUSE THEY ARE THE ONLY ONES A
    # READER WOULD NOTICE. Everything above says the machinery ran; these say whether last
    # night's games are actually on the site.
    for head, (label, meaning) in OUTCOME_LINES.items():
        value = outcomes.get(head)
        if value is None:
            # 🚨 A MISSING LINE IS BLIND, NOT QUIET — A185 (cfdb-main-R-1878). The monitor
            # emits every outcome line unconditionally now, `<head>|0|0|-` included, so an
            # absent one means the forced command on the droplet is an older copy that does
            # not run this check at all. **Reading that as "nothing to report" is exactly the
            # silence-is-not-success failure**, and it is indistinguishable from a clean site
            # unless the watcher insists on hearing the answer.
            print(f"  BLIND   the {head} check reported nothing — the deployed forced command "
                  f"does not emit this line, so it cannot tell you whether the site is current")
        elif value[0] == -1:
            print(f"  BLIND   the {head} check could not read published serving "
                  f"({value[2]}) — it cannot tell you whether the site is current")
        elif value[0]:
            count, age, weeks = value
            print(f"  {label} {count} {meaning} — oldest {describe(age)}, week(s) {weeks}")

    unknown = sorted(set(ages) - set(CADENCES))
    if unknown:
        # Not a failure: a new DAG that beats before anyone adds it here is better than one
        # that does not beat at all. Worth saying so it gets a budget.
        print(f"\n  note: beating but unmonitored — {', '.join(unknown)}")

    # ══════════════════════════════════════════════════════════════════════════════════════
    # 🚨 A281 (cfdb-main-R-4740) — PAGE AND DIGEST, SPLIT INSIDE THE FUNCTION THAT ALREADY
    # KNOWS THE DIFFERENCE
    # ══════════════════════════════════════════════════════════════════════════════════════
    #
    # > **MARC, 2026-10-02:** *"I'm getting alarms and you are saying things look great… That's
    # > misdirection and misinformation… It's a time suck and productivity killer."*
    # > **2026-10-03:** *"Deadman's switch failure AGAIN."*
    #
    # 📊 `unboxed_now` was built from THREE different facts and all three returned 1:
    #
    #   a head ABSENT from `outcomes`  → the forced command is an older copy — the check
    #                                    CANNOT RUN                              🚨 BLIND
    #   `value[0] == -1`, `MONITOR.<why>` → it could not read published serving   🚨 BLIND
    #   `value[0] > 0`                  → the site is missing content a reader
    #                                     would notice                           📋 GAP
    #
    # ✅ BLIND STILL FAILS THE RUN. A monitor that cannot see is worse than no monitor, and it
    # is a drop-everything event: it is indistinguishable from a clean site unless the watcher
    # insists on hearing the answer (A185, cfdb-main-R-1878).
    #
    # ✅ A GAP NO LONGER FAILS THE RUN. 🚨 THE MECHANISM IS THE WHOLE POINT: GitHub emails on a
    # FAILED run. A run that exits 0 sends nothing, and `::notice::` still puts the line in the
    # run summary — so the SIGNAL IS KEPT AND THE INTERRUPT IS REMOVED. That is
    # `cfdb_alerting_strategy.md` §4's PAGE/DIGEST split, with no second workflow, no settings
    # change and no new credential.
    #
    # ⚠️ WHAT IT COSTS, STATED RATHER THAN DISCOVERED: a real content gap stops emailing too.
    # That is deliberate — these checks were red ≈59 hours a week by construction, and an
    # alarm that is red most of the week is not detection, it is wallpaper. A280 gives the
    # signal a true threshold; this gives it a channel that does not interrupt.
    blind = [head for head in OUTCOME_LINES
             if head not in outcomes or (outcomes[head] and outcomes[head][0] == -1)]
    gaps = [head for head in OUTCOME_LINES
            if head in outcomes and outcomes[head] and outcomes[head][0] > 0]

    # 🚨 THE PAGE SET IS THE EXIT CODE, AND NOTHING ELSE IS. Everything in it means the
    # pipeline is down, stuck, or unwatchable.
    page = bool(stale or missing or failures or failed_tests or blind)

    if page or gaps:
        print()
        # 🚨 A278 (cfdb-main-R-4651). AN ALARM THAT NAMES NOTHING MAKES THE READER DO THE
        # TRIAGE, WHICH IS THE OPPOSITE OF WHAT AN ALARM IS FOR.
        #
        # 📊 MEASURED FROM THE RUN MARC PASTED ON 2026-10-02: five cadences inside budget, no
        # failed task, no failed assertion, one `UNPLAYERED 2` line — and the process exited 1
        # with **not one `::error::` in the output**. GitHub's run summary was blank and the
        # email named nothing, so the only way to learn what fired was to open the log and read
        # it. ⚠️ That is cfdb-main-R-673's shape thirteen rounds on, and Marc's reply was
        # "AGAIN!!!".
        #
        # ✅ THE CONTEXT LINE GOES FIRST, AND IT IS THE HALF THAT WAS ACTUALLY MISSING. When
        # every cadence is beating, the distinction between "the pipeline stopped" and "the
        # pipeline is fine and a feed is late" is the whole triage, and a reader should not
        # have to reconstruct it. It is only printed when it is TRUE — a run with a stale beat
        # says nothing of the kind.
        # ⚠️ THE CONTEXT LINE IS A NOTICE WHEN NOTHING FAILED, AND IT SAYS SO. It used to be
        # printed as `::error::` even on a run where nothing was wrong — that is the line Marc
        # quoted back twice.
        if not page:
            print(f"::notice::the pipeline is BEATING — all {len(ok)} cadences inside budget, "
                  f"no failed task and no failed assertion. Something the site should be "
                  f"showing is late; the line below says what. No action is needed unless it "
                  f"is still here tomorrow.")
        for line in stale + missing:
            print(f"::error::heartbeat absent — {line}")
        for task, age in sorted(failures.items()):
            print(f"::error::task failed — {task}, {describe(age)} ago. A gated DAG has "
                  f"exhausted its retries; anything downstream of it, including the publish, "
                  f"did not run.")
        for name, (count, age) in sorted(failed_tests.items()):
            print(f"::error::dbt test failed — {name}, {count} row(s), {describe(age)} ago. "
                  f"This is the ASSERTION rather than the task: anything downstream of the "
                  f"test, including the publish, did not run.")
        # 🚨 THE THREE SILENT EXITS. `unboxed_now` is true in three different ways and NONE of
        # them annotated anything before this round:
        #
        #   1. a real non-zero count — the site is missing something a reader would notice;
        #   2. `MONITOR.<why>` (`count == -1`) — the forced command could not read published
        #      serving, so the check could not run at all;
        #   3. a head absent from `outcomes` entirely — the deployed forced command is an older
        #      copy that does not emit this line (A185, cfdb-main-R-1878).
        #
        # ⚠️ 2 AND 3 ARE BLINDNESS RATHER THAN A GAP, and they are annotated as such: "the check
        # could not answer" and "the site is missing data" are different facts and collapsing
        # them would make the louder one hide the quieter.
        # 🚨 BLIND IS AN ERROR AND A GAP IS A NOTICE — the two are different facts and only one
        # of them is an emergency. Collapsing them is what made every content gap read as an
        # outage.
        for head, (label, meaning) in OUTCOME_LINES.items():
            value = outcomes.get(head)
            if value is None:
                print(f"::error::BLIND — the {head} check reported nothing. The forced command "
                      f"on the droplet does not emit this line, so nothing can tell you "
                      f"whether the site is current for it.")
            elif value[0] == -1:
                print(f"::error::BLIND — the {head} check could not read published serving "
                      f"({value[2]}). It cannot tell you whether the site is current.")
            elif value[0]:
                count, age, weeks = value
                print(f"::notice::{label} — {count} {meaning}. Oldest {describe(age)}, "
                      f"week(s) {weeks}.")
        if stale or missing:
            print("::error::the pipeline has stopped emitting on at least one cadence. "
                  "Silence is not success.")
        if page:
            return 1

    if gaps:
        print(f"\n{len(ok)} cadences beating within budget, no failed tasks or assertions in "
              f"the window. {len(gaps)} content gap(s) noted above — reported, not paged.")
    else:
        print(f"\nAll {len(ok)} cadences beating within budget, no failed tasks or assertions "
              f"in the window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
