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
    the daily safety-net hour                    -> proceed, catches late stat corrections
    otherwise, in season                         -> skip
    out of season                                -> the safety-net hour only

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
from datetime import datetime, timezone
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


@dataclass(frozen=True)
class ScoresDecision(Decision):
    """Same shape as the lines decision, so both DAGs log identically."""


def should_refresh_scores(now_utc: datetime,
                          config: CadenceConfig,
                          hours_since_last_kickoff: Optional[float] = None,
                          settle_hours: int = SETTLE_HOURS) -> Decision:
    """Decide whether this run should fetch the game spine.

    `hours_since_last_kickoff` is passed in rather than queried so this stays pure. None
    means the caller could not determine it — a database that will not answer must not
    silently stop the pipeline, so that case falls through to the safety net rather than
    skipping.
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
        reason=(f"in season, but {since} — outside the {settle_hours}h settle window and "
                f"not the daily {SAFETY_NET_HOUR_UTC:02d}:00 run"),
    )


def hours_since_last_kickoff(now_utc: Optional[datetime] = None) -> Optional[float]:
    """Hours since the most recent kickoff that has already happened.

    Reads the SCHEDULE, which is known weeks ahead and does not depend on the refresh this
    gate is deciding about — so a stale results table cannot make the gate stop collecting
    results, which would be a satisfying loop to debug at 2am in November.

    Returns None on any failure. The caller treats that as "cannot tell", which falls
    through to the safety net rather than skipping.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        from src.load_raw_to_postgres import get_conn
        connection = get_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select max(start_date) from marts.fct_game where start_date <= %s",
                    (now_utc,))
                latest = cursor.fetchone()[0]
        finally:
            connection.close()
    except Exception as exc:                                       # noqa: BLE001
        print(f"could not read the schedule ({exc}); falling through to the safety net")
        return None

    if latest is None:
        return None
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    return (now_utc - latest).total_seconds() / 3600.0
