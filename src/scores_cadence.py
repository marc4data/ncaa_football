"""When a scores refresh should actually run.

The problem: cfbd_results_refresh is Sunday, cfbd_pregame_refresh is Tuesday, and
cfbd_midweek_results is Thursday at 12:00 UTC — ten hours BEFORE Thursday's 22:00 kickoffs.
So the twenty games of 27 August would sit on the site marked "scheduled" until Sunday the
30th, and Scores is the most-visited surface on any sports site during a game week.

The fix is not another fixed day. It is a DAG scheduled at a fine cadence whose every run
asks this module whether there is anything to collect.

WHY THIS GATE IS DATA-DRIVEN AND THE LINES GATE IS NOT. `should_snapshot` asks only
"are we in the season", because a betting line moves whether or not a game is being played
— an idle Tuesday still has price movement worth sampling. Scores are different: they only
change while games are finishing. A calendar rule would have to encode which days college
football is played on, and that is exactly the assumption that produced the Tuesday-night
gap the third weekly DAG exists to close. The schedule already knows when games are; asking
it is cheaper and cannot go stale.

    a game kicked off within the settle window   -> proceed, results are landing
    a game is STILL not final, kicked off <36h   -> proceed, it is delayed or suspended
    the daily safety-net hour                    -> proceed, catches late stat corrections
    otherwise, in season                         -> skip
    out of season                                -> the safety-net hour only

WHY THE SECOND BRANCH EXISTS. The settle window assumes a game ends within a few hours of
starting, and late-August football in the southeast does not always oblige: a lightning delay
is routine, and a game SUSPENDED on Thursday and resumed on Friday afternoon keeps its
Thursday kickoff timestamp. Eighteen hours later the settle window has long since shut, so
the finished game would sit unpublished until Sunday — the exact failure this module exists
to prevent, arriving through the one door the kickoff clock does not watch.

So the second branch asks a different question. Not "did a game start recently" but "is a
game we already know about still unfinished". It closes on its own the moment the game
finals, so it cannot loop.

Cost. One refresh is TWO requests — /games for the week in play and the one before it — so
running it every two hours through a game weekend costs about seventy requests a week
against a 75,000/month quota. A full results_refresh is 31 requests and re-fetches plays,
drives, box scores and PPA, none of which change between Saturday night and Sunday morning.
Being cheap is what makes it frequent; the heavy refresh stays weekly.

Safe mid-slate, which is what lets it be frequent at all: CFBD reports `completed: false`
for a game in progress, so a live game stays out of the completed set rather than being
recorded as final at whatever the score was when we asked.

The decision is a pure function of (now, config, hours_since_last_kickoff), so it is tested
without Airflow, a database or a clock — the same shape as `lines_cadence.should_snapshot`,
and it reuses that module's config file because the season window is the same season.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.lines_cadence import CadenceConfig, Decision

# How long after a kickoff results are still worth collecting. Generous on purpose: a
# college football game runs about three and a half hours, a late West-Coast kickoff can run
# past five, and CFBD does not publish a final the instant the whistle goes. Eight hours
# covers the tail without keeping the gate open through a quiet Tuesday.
SETTLE_HOURS = 8

# One run a day proceeds regardless, in and out of season. Stat corrections land days later,
# and a gate with no unconditional path is a gate that silently stops collecting the moment
# its condition is wrong.
SAFETY_NET_HOUR_UTC = 12

# How long after kickoff an UNFINISHED game keeps the gate open. Covers a suspended game
# resumed the following afternoon, which is the case SETTLE_HOURS cannot see.
#
# THIS BOUND IS THE CIRCUIT BREAKER, not a detail. A postponed game is `completed = false`
# with a past kickoff forever, so without an upper bound one of them would hold the gate open
# permanently. At 36 hours the worst a game that never finals can cost is 18 runs — 36
# requests, once, and then it falls out of the window whether or not it was ever played.
UNFINISHED_HOURS = 36


@dataclass(frozen=True)
class ScoresDecision(Decision):
    """Same shape as the lines decision, so both DAGs log identically."""


def should_refresh_scores(now_utc: datetime,
                          config: CadenceConfig,
                          hours_since_last_kickoff: Optional[float] = None,
                          unfinished_recent: Optional[int] = None,
                          unbuilt_predictions: Optional[int] = None,
                          settle_hours: int = SETTLE_HOURS) -> Decision:
    """Decide whether this run should fetch the game spine.

    Both data inputs are passed in rather than queried so this stays pure. None means the
    caller could not determine it — a database that will not answer must not silently stop
    the pipeline, so that case falls through to the safety net rather than skipping.

    `unfinished_recent` is a COUNT, not a boolean, so the logged reason can say how many
    games are holding the gate open. "1 game unfinished" and "14 games unfinished" are a
    lightning delay and a broken load respectively, and the log should be able to tell them
    apart without a second query.

    🚨 `unbuilt_predictions` IS A290 (cfdb-main-R-5013), AND IT EXISTS BECAUSE THIS GATE
    ANSWERED THE WRONG QUESTION FOR A WHOLE SEASON.
    =========================================================================================
    Every branch below asks *is there anything to FETCH*, and the answer short-circuits
    `dbt_run`, `dbt_test` and `publish_to_serving` as well — which cost no CFBD quota and are
    the only way anything reaches the site.

    📊 MEASURED 2026-10-28: week 9's forecasts landed in `raw.raw_model_prediction` at
    16:43:36Z. The daily unconditional run is 12:00 UTC (`SAFETY_NET_HOUR_UTC`) and had passed
    4.7 hours earlier, so the 14:00, 16:00, 18:00, 20:00 and 22:00 runs all took
    `nothing_settling` and skipped the build. **`fct_prediction` held 0 rows for week 9 while
    weeks 5-8 were all present, and every heartbeat was green** — because `heartbeat` carries
    `trigger_rule=NONE_FAILED` and beats on a deliberate skip (§2.3, A264's cfdb-main-R-4109).

    ⚠️ THE FIX IS NOT "BUILD UNCONDITIONALLY". That would run a 39-model closure twelve times
    a day year-round for nothing, and A285 bought the warehouse-write pool precisely because
    concurrent builds were already costing Sunday's publish. **So this is a COUNT of work the
    warehouse has but has not built**, passed in like the other two, and it opens the gate only
    when there is something to open it for.

    ⚠️ AND IT IS A COUNT RATHER THAN A BOOLEAN FOR THE SAME REASON `unfinished_recent` IS:
    "1 week unbuilt" is this morning's load and "4 weeks unbuilt" is a pipeline that has been
    skipping since the start of the month, and the log should separate them without a second
    query.
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    today = now_utc.date()
    start, end = config.window_start, config.window_end
    in_season = start <= today <= end

    if in_season and hours_since_last_kickoff is not None \
            and 0 <= hours_since_last_kickoff <= settle_hours:
        return ScoresDecision(
            proceed=True,
            branch="settling",
            reason=(f"a game kicked off {hours_since_last_kickoff:.1f}h ago, inside the "
                    f"{settle_hours}h settle window — results are landing now"),
        )

    # A GAME WE ALREADY KNOW ABOUT IS STILL NOT FINAL. Distinct from the branch above, and
    # deliberately so: that one asks whether a game started recently, this one asks whether
    # one has finished. A Thursday game suspended for weather and resumed Friday afternoon
    # is invisible to the kickoff clock and obvious to this.
    if in_season and unfinished_recent:
        return ScoresDecision(
            proceed=True,
            branch="unfinished",
            reason=(f"{unfinished_recent} game(s) kicked off within the last "
                    f"{UNFINISHED_HOURS}h and are still not final — delayed, suspended or "
                    f"simply not yet published, and none of those resolve by waiting for "
                    f"Sunday"),
        )

    # 🚨 A290. THERE IS BUILT WORK WAITING, SO THE BUILD HALF MUST RUN EVEN THOUGH THERE IS
    # NOTHING TO FETCH. This sits BELOW the two fetch reasons on purpose: when a game is
    # settling the gate is already open and `settling` is the more useful line in the log.
    # It sits ABOVE the fail-open and the safety net because an unbuilt forecast is a KNOWN
    # fact, not an unknown one, and it should not have to wait for 12:00 UTC to be noticed.
    if in_season and unbuilt_predictions:
        return ScoresDecision(
            proceed=True,
            branch="unbuilt_predictions",
            reason=(f"{unbuilt_predictions} week(s) of forecasts are in raw and not yet in "
                    f"fct_prediction — nothing to fetch, but the build half must run or the "
                    f"site never sees them (cfdb-main-R-5013)"),
        )

    # FAIL OPEN, IN SEASON. If the schedule could not be read we cannot tell whether games
    # are settling, and the two answers cost very different amounts: fetching when we did
    # not need to is two API calls against a 75,000/month quota, while skipping through a
    # game weekend because Postgres blipped leaves yesterday's results showing as upcoming.
    # An earlier version skipped here, which contradicted this module's own docstring — the
    # kind of gap that only shows up when the branches are enumerated and read back.
    if in_season and hours_since_last_kickoff is None:
        return ScoresDecision(
            proceed=True,
            branch="unknown_fail_open",
            reason=("in season and the schedule could not be read, so whether games are "
                    "settling is unknown — proceeding, because two wasted requests cost "
                    "less than a stale scoreboard"),
        )

    if now_utc.hour == SAFETY_NET_HOUR_UTC:
        return ScoresDecision(
            proceed=True,
            branch="safety_net",
            reason=(f"{SAFETY_NET_HOUR_UTC:02d}:00 UTC daily run proceeds regardless — "
                    f"stat corrections land days after a game, and a gate with no "
                    f"unconditional path stops collecting the moment its condition is wrong"),
        )

    if not in_season:
        return ScoresDecision(
            proceed=False,
            branch="off_season_skip",
            reason=(f"{today} is outside the active window {start}..{end} and it is "
                    f"{now_utc.hour:02d}:00 UTC, not the daily {SAFETY_NET_HOUR_UTC:02d}:00"),
        )

    since = ("no kickoff found" if hours_since_last_kickoff is None
             else f"last kickoff {hours_since_last_kickoff:.1f}h ago")
    return ScoresDecision(
        proceed=False,
        branch="nothing_settling",
        reason=(f"in season, but {since}, no game unfinished inside "
                f"{UNFINISHED_HOURS}h and no unbuilt forecasts — outside the "
                f"{settle_hours}h settle window and not the daily "
                f"{SAFETY_NET_HOUR_UTC:02d}:00 run"),
    )


@dataclass(frozen=True)
class ScheduleState:
    """What the schedule says right now: both gate inputs, from one read.

    They are returned together rather than fetched separately because they share a failure
    mode. `should_refresh_scores` treats a null `hours_since_last_kickoff` as "the database
    would not answer" and fails open on it; that inference is only sound if the other input
    could not have succeeded independently. One connection, one query, one answer about
    whether we could see the schedule at all.
    """

    hours_since_last_kickoff: Optional[float] = None
    unfinished_recent: Optional[int] = None


def unbuilt_prediction_weeks() -> Optional[int]:
    """How many (season, week) forecasts sit in `raw` that `fct_prediction` has not built.

    🚨 A290 (cfdb-main-R-5013). THE GATE INPUT THAT WOULD HAVE SAVED WEEK 9.

    ⚠️ IT COMPARES THE TWO ENDS OF THE CHAIN, NOT A FILE ON DISK. A detector keyed on "is
    there a new CSV" could not see today's failure at all — the file had loaded fine, hours
    earlier; what had not happened was the BUILD. So the question is asked of the warehouse
    both times, and the gap between the two answers IS the fault.

    ⚠️ RETURNS None ON ANY FAILURE, matching `schedule_state`'s contract exactly: the caller
    treats null as "cannot tell", which falls through to the existing branches rather than
    wedging the gate open or shut on a database blip. **A gate input that can hang the
    pipeline when Postgres hiccups is worse than the gap it closes.**

    ⚠️ AND IT IS DELIBERATELY NOT FILTERED TO THE CURRENT WEEK. A forecast for ANY week that
    raw holds and the mart does not is unbuilt work, and bounding it to "this week" is how
    week 6's silence would have survived the detector that was supposed to catch it.
    """
    try:
        from src.load_raw_to_postgres import get_conn
        connection = get_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    with raw_weeks as (
                        select distinct (payload->>'season')::int  as season,
                                        (payload->>'week')::int    as week
                        from raw.raw_model_prediction
                        where payload->>'season' ~ '^[0-9]+$'
                          and payload->>'week'   ~ '^[0-9]+$'
                    ),
                    built as (
                        select distinct season, week from marts.fct_prediction
                    )
                    select count(*) from raw_weeks r
                    where not exists (select 1 from built b
                                      where b.season = r.season and b.week = r.week)
                    """
                )
                row = cursor.fetchone()
                return int(row[0]) if row and row[0] is not None else 0
        finally:
            connection.close()
    except Exception as error:                                   # noqa: BLE001
        print(f"unbuilt_prediction_weeks: could not read ({error}) — returning None so the "
              f"gate falls through to its other branches")
        return None


def schedule_state(now_utc: Optional[datetime] = None,
                   unfinished_hours: int = UNFINISHED_HOURS) -> ScheduleState:
    """Read the schedule for both gate inputs.

    Reads the SCHEDULE, which is known weeks ahead and does not depend on the refresh this
    gate is deciding about — so a stale results table cannot make the gate stop collecting
    results, which would be a satisfying loop to debug at 2am in November.

    The unfinished count is the one place the gate does read `is_completed`, and it is safe
    in the same way: a stale `false` opens the gate rather than closing it, so the failure
    direction is a wasted request instead of a missing score.

    Returns an empty state on any failure. The caller treats null as "cannot tell", which
    falls through to fail-open in season rather than skipping.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    window_start = now_utc - timedelta(hours=unfinished_hours)
    try:
        from src.load_raw_to_postgres import get_conn
        connection = get_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        max(start_date) filter (where start_date <= %s),
                        count(*) filter (where not is_completed
                                           and start_date <= %s
                                           and start_date >= %s)
                    from marts.fct_game
                    """,
                    (now_utc, now_utc, window_start))
                latest, unfinished = cursor.fetchone()
        finally:
            connection.close()
    except Exception as exc:                                       # noqa: BLE001
        print(f"could not read the schedule ({exc}); falling through to the safety net")
        return ScheduleState()

    hours = None
    if latest is not None:
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        hours = (now_utc - latest).total_seconds() / 3600.0
    return ScheduleState(hours_since_last_kickoff=hours,
                         unfinished_recent=int(unfinished or 0))
