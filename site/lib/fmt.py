"""Numbers, nulls and time. Formatting only — never arithmetic (G-3).

AC-G.30 to AC-G.35. Precision is fixed PER COLUMN, not per value, so a column of figures
compares vertically: `7` renders `7.0` where its column is 1 dp.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

EM_DASH = "—"

# The display timezone is CONFIGURED, not constant. Every time on the site — kickoffs, line
# snapshots, and the as-of stamp — is rendered in it, and the zone abbreviation always
# travels with the number.
#
# That last part is load-bearing rather than decorative. The site publishes Pacific while
# ESPN and CBS publish Eastern, so a reader comparing tabs WILL see different numbers for
# the same kickoff. "7:30 PM PDT" is unambiguous; "7:30 PM" is a trap.
#
# One resolution point, so viewer-local after Week 0 changes how this value is obtained
# rather than every call site that formats a time.
DEFAULT_TIMEZONE = "America/Los_Angeles"


@lru_cache(maxsize=1)
def display_timezone() -> str:
    try:
        config = json.loads(
            (Path(__file__).resolve().parent / "site_config.json").read_text())
        return config.get("display_timezone") or DEFAULT_TIMEZONE
    except Exception:                                              # noqa: BLE001
        # A missing config must not make every timestamp on the site unreadable.
        return DEFAULT_TIMEZONE


def _local(ts):
    """A timestamp in the display zone, tolerant of naive input.

    Values arrive tz-aware from Postgres; a naive one is treated as UTC rather than
    rejected, because a naive datetime is what a hand-built test frame produces and
    crashing the page over it would be the wrong trade.
    """
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    return stamp.tz_convert(display_timezone())


# Fixed precision by column meaning, per AC-G.31.
#
# ORDER IS THE RULE, and it is specificity rather than length. `margin_mae` contains both
# "margin" and "mae"; it is an MAE. `absolute_margin_error` contains "margin" and "error";
# it is an error. Matching the longest keyword picks "margin" for both and is wrong — which
# the tests caught. The measurement type wins over the quantity being measured.
PRECISION = (
    ("probability", 3),
    ("epa", 3), ("ppa", 3),
    ("mae", 2), ("error", 2), ("rating", 2),
    ("pct", 1), ("percent", 1), ("rate", 1),
    ("spread", 1), ("margin", 1), ("line", 1), ("edge", 1),
    ("total", 1), ("over_under", 1), ("differential", 1),
)


def precision_for(column: str) -> int:
    """First match wins, in specificity order. See the note on PRECISION."""
    name = column.lower()
    for key, dp in PRECISION:
        if key in name:
            return dp
    return 1


def number(value, column: str = "", dp: Optional[int] = None) -> str:
    """A number, or an em dash for null.

    AC-G.32: null renders `—` and zero renders `0`, and the two must never be confused. A
    zero is a measurement; a null is the absence of one.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NaT:
        return EM_DASH
    try:
        if pd.isna(value):
            return EM_DASH
    except (TypeError, ValueError):
        pass
    width = dp if dp is not None else precision_for(column)
    try:
        return f"{float(value):,.{width}f}"
    except (TypeError, ValueError):
        return str(value)


def signed(value, column: str = "", dp: Optional[int] = None) -> str:
    """A signed number, so a home-negative spread reads unambiguously."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return EM_DASH
    text = number(value, column, dp)
    return f"+{text}" if float(value) > 0 else text


def with_n(value, n, column: str = "") -> str:
    """A rate and its sample size, together.

    AC-G.33: a hit rate without an `n` is a defect, not a style choice. 17.9% on n=11 is
    noise wearing a big number, and the only defence is rendering the two adjacently.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return EM_DASH
    return f"{number(value, column)} (n={int(n):,})" if n is not None and not pd.isna(n) \
        else number(value, column)


def local_time(ts) -> str:
    """AC-G.34: display in the configured zone, with the abbreviation shown.

    Renamed from `eastern`, which stopped being true the moment the site moved to Pacific.
    A function whose name asserts something false is the class this project keeps finding —
    fct_team_week_rating asserted a grain no source had, and this asserted a zone.

    The column it reads is still `start_date_et`, a dbt conversion, so the app owns no
    timezone RULE — only which zone it renders in, which is config.
    """
    if ts is None or pd.isna(ts):
        return EM_DASH
    return _local(ts).strftime("%b %-d, %Y, %-I:%M %p %Z")


def clock(ts) -> str:
    """Time only, with the zone. For a table already grouped by day.

    The long form wrapped onto two lines in a narrow kickoff column and repeated a date the
    day header had already given. "7:30 PM PDT" is the whole of what that cell adds.
    """
    if ts is None or pd.isna(ts):
        return EM_DASH
    return _local(ts).strftime("%-I:%M %p %Z")


def day(ts) -> str:
    """A date as "Aug 20, 2026".

    A DATE IS NOT CONVERTED. `game_date` is a date column, not an instant, and running it
    through a timezone conversion turns midnight UTC into 5pm the previous day — shifting
    every game back by one. This project has already lost 66,496 games to exactly that,
    which is why the era logic in mart_team_schedule exists.

    A value carrying a real time of day is converted; a bare date is rendered as it is.
    """
    if ts is None or pd.isna(ts):
        return EM_DASH
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is None and stamp.normalize() == stamp:
        return stamp.strftime("%b %-d, %Y")
    return _local(stamp).strftime("%b %-d, %Y")


def relative_age(ts, now=None) -> str:
    """How long ago, in the largest unit that does not round the answer away.

    HOURS RUN TO 48, NOT TO 24, and that is the whole point of this function. A stamp
    44 hours old rolling over to "2 days ago" rounds away the number the reader needs: on a
    live Saturday the difference between 20 hours and 44 hours is the difference between
    "yesterday's refresh" and "we missed one". Days only start once the hour count has
    stopped being informative.

    A future timestamp reads as "just now" rather than a negative age. Clock skew between
    the warehouse and the web host is a real few-seconds effect, and "in -3 seconds" is a
    worse answer than a harmless rounding to the present.
    """
    stamp = _local(ts)
    now = _local(now) if now is not None else pd.Timestamp.now(tz=display_timezone())
    seconds = (now - stamp).total_seconds()

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 48 * 3600:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def as_of(ts, now=None) -> str:
    """AC-G.35, in the display zone rather than UTC, absolute AND relative.

    The as-of stamp answers "how current is this", and a reader who has to convert from UTC
    to answer it will not bother. Storage stays UTC; only the rendering moves.

    BOTH FORMS, NEVER ONE. "as of Aug 27, 8:00 AM PDT" at 44 hours old is technically true
    and reads as fine, which is the definition of the problem — an absolute time is only
    stale relative to a clock the reader has to consult. "44 hours ago" is what they
    actually read. The absolute time stays because it is what someone cross-checks against
    a CFBD page or a broadcast, and a relative age alone cannot be checked against anything.
    """
    if ts is None or pd.isna(ts):
        return "as of — (freshness unavailable)"
    return (f"as of {_local(ts).strftime('%b %-d, %Y, %-I:%M %p %Z')}"
            f" · {relative_age(ts, now)}")
