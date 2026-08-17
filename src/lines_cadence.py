"""When a betting-line snapshot should actually run.

The problem this solves: CFBD's `/lines` returns only the opening and current line, with
nothing in between. Intraday movement exists **only if we sampled it**, and once a game
kicks off it can never be recovered. Closing Line Value — the fastest honest read on
whether a model has edge — is built entirely from that history.

So the cadence needs to be fine during the season and cheap outside it. The obvious
implementation is to change the DAG's schedule twice a year, and that is exactly what this
avoids: a seasonal schedule edit is a runtime-path change twice a year, and one August it
will be forgotten.

Instead the DAG is scheduled permanently at the finest cadence — `0 */4 * * *` UTC, six
runs a day — and each run asks this module whether to proceed:

    inside the active window   -> every run proceeds        (4-hourly)
    outside it                 -> only the 00:00 UTC run    (daily)

Net effect is season-aware cadence with no schedule change, ever. Between seasons the only
maintenance is three dates in `config/lines_cadence.json`.

The decision is a pure function of (now, config) so it can be tested without Airflow, a
database, or a clock. It returns a `Decision` rather than a bare bool because a skip must
be explainable: a short-circuit that skips silently is indistinguishable from a broken DAG
when you look at it in March.
"""
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(
    os.getenv("LINES_CADENCE_CONFIG", "/opt/airflow/project/config/lines_cadence.json")
)

# The hour that runs off-season. With a `0 */4 * * *` schedule the runs land at
# 00/04/08/12/16/20 UTC, so allowing only hour 0 yields exactly one run per day.
OFF_SEASON_HOUR_UTC = 0


@dataclass(frozen=True)
class CadenceConfig:
    """The three dates that define a season, plus the lead time before it."""

    season: int
    first_game_date: date
    lead_days: int
    season_end_date: date

    @property
    def window_start(self) -> date:
        """When fine-grained sampling begins: lead_days before the first game."""
        return self.first_game_date - timedelta(days=self.lead_days)

    @property
    def window_end(self) -> date:
        return self.season_end_date


@dataclass(frozen=True)
class Decision:
    """Whether to snapshot, and why — the reason is what gets logged."""

    proceed: bool
    branch: str
    reason: str

    def __bool__(self) -> bool:
        return self.proceed


def load_config(path: Optional[Path] = None) -> CadenceConfig:
    """Read the cadence window from disk.

    Config lives in a file rather than in the DAG so that changing a season's dates is a
    reviewable, version-controlled edit — and so this module stays a pure function of its
    inputs, testable without touching the filesystem at all.
    """
    path = path or CONFIG_PATH
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return CadenceConfig(
        season=int(raw["season"]),
        first_game_date=date.fromisoformat(raw["first_game_date"]),
        lead_days=int(raw["lead_days"]),
        season_end_date=date.fromisoformat(raw["season_end_date"]),
    )


def should_snapshot(now_utc: datetime, config: CadenceConfig) -> Decision:
    """Decide whether this run should take a snapshot.

    Pure: no clock, no I/O, no Airflow. `now_utc` is expected to be timezone-aware UTC;
    a naive datetime is treated as UTC rather than rejected, because Airflow hands the
    logical date over in several shapes depending on how the task is invoked.
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    today = now_utc.date()
    start, end = config.window_start, config.window_end

    if start <= today <= end:
        return Decision(
            proceed=True,
            branch="in_season",
            reason=(
                f"{today} is inside the active window {start}..{end} "
                f"(season {config.season}, first game {config.first_game_date}, "
                f"lead {config.lead_days}d) — sampling every 4 hours"
            ),
        )

    if now_utc.hour == OFF_SEASON_HOUR_UTC:
        return Decision(
            proceed=True,
            branch="off_season_daily",
            reason=(
                f"{today} is outside the active window {start}..{end}; this is the "
                f"{OFF_SEASON_HOUR_UTC:02d}:00 UTC run, so it proceeds — daily cadence"
            ),
        )

    return Decision(
        proceed=False,
        branch="off_season_skip",
        reason=(
            f"{today} is outside the active window {start}..{end} and it is "
            f"{now_utc.hour:02d}:00 UTC, not {OFF_SEASON_HOUR_UTC:02d}:00 — skipping to "
            f"hold off-season cadence at daily"
        ),
    )
