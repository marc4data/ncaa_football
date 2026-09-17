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


class NaiveTimestamp(TypeError):
    """A timestamp with no offset reached the formatter. R-643.

    ⚠️ Carries the value so an operator can see WHICH stamp, without the page showing it.
    """


def _local(ts):
    """A timestamp in the display zone. THE INPUT MUST CARRY ITS OWN OFFSET.

    🚨 THE TOLERANCE THAT USED TO BE HERE MIS-RENDERED EVERY KICKOFF ON THE SITE FOR A
    SEASON, AND IT WAS ADDED FOR TEST FIXTURES. The old comment said so in as many words:
    "a naive one is treated as UTC rather than rejected, because a naive datetime is what a
    hand-built test frame produces and crashing the page over it would be the wrong trade."
    ⚠️ The fixtures shared the assumption, so nothing caught it — and `srv_game.start_date_et`
    arrived naive on every page, was assumed UTC, and came out four hours early under EDT.

    ── WHY IT RAISES NOW, RATHER THAN GUESSING QUIETLY OR RENDERING AN ABSENCE ──────────────

    1. ⚠️ A NAIVE VALUE IS NO LONGER POSSIBLE FROM THE DATA. Measured 2026-09-11: serving
       held 43 timestamp columns and exactly TWO were naive — both `start_date_et`, both
       removed by R-643. The other 41, `as_of_ts` included, carry their offset. So a naive
       stamp reaching here now means a caller passed something that is not an instant, which
       is a defect in the code rather than a gap in the data.
    2. ⚠️ THE ABSENCE PATH ALREADY EXISTS AND THIS IS NOT IT. Every public caller returns
       EM_DASH for None/NaT (AC-G.32). Rendering that here as well would say "we have no
       kickoff for this game" when what happened is "someone handed the formatter the wrong
       type" — two different facts under one dash.
    3. 🚨 GUESSING LOUDLY IS STILL A WRONG TIME RENDERED AS A RIGHT ONE. A warning on stderr
       does not reach the reader, and the reader is the one being misled.
    4. ✅ A RAISE IS CONTAINED, WHICH IS WHY IT IS AFFORDABLE. `states.section` turns a
       renderer exception into a state that names no internal (AC-G.9), so one panel degrades
       honestly instead of the whole page falling over — and `CFDB_TRACE_STATES=1` gives the
       operator the type and the failing line. A reader never sees a traceback either way.

    ⚠️ A BARE DATE IS NOT AN INSTANT AND MUST NOT REACH HERE. `day()` handles that case above,
    deliberately, because converting midnight shifts a game back a calendar day — the defect
    that once cost this project 66,496 games.
    """
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is None:
        raise NaiveTimestamp(
            f"a timestamp with no timezone reached fmt._local: {stamp!r}. Serving publishes "
            f"instants; a naive value is a caller passing the wrong thing, and guessing a "
            f"zone for it is what rendered every kickoff four hours early (R-643).")
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
    # R-555. A Brier score is a mean SQUARED error on a 0–1 probability, so it lives in the
    # third decimal the way the probabilities it scores do. It reached this table by falling
    # through to the old default of 1, where .184 and .238 both rendered "0.2" — the column
    # was published at a precision that could not separate a good model from a poor one.
    ("brier", 3),
    ("mae", 2), ("error", 2), ("rating", 2),
    ("pct", 1), ("percent", 1), ("rate", 1),
    # 🚨 A154. TWO METRICS THE 0-DEFAULT FLATTENS, FOUND BY POINTING `box()`'s AXIS LABELS AT THIS
    # TABLE — Marc, v18: *"Don't use decimal points when displaying Yards … Exception is YDS/CARRY
    # (#.#)"*. His rule is right and keyed on the right thing; these two simply never reached here
    # before, because the chart forced `dp=1` on everything and nothing asked the column.
    #
    # 📊 MEASURED on `srv_game_team_metric_distribution_through_prior_week`:
    #     offense_explosiveness   0.378 … 2.737, median 1.245   -> at 0 dp: "0", "1", "3"
    #     offense_power_success   0.000 … 1.000, median 0.750   -> at 0 dp: "0" or "1", nothing else
    # **A 0–1 rate rendered at zero decimals carries no information at all.**
    #
    # ⚠️ `power_success` TAKES 1 TO MATCH EVERY OTHER RATE IN THIS TABLE rather than inventing a
    # second convention for the same kind of quantity; `explosiveness` takes 2 because it is a
    # ratio around 1.2 where the first decimal alone would bucket most of the league together.
    ("explosiveness", 2), ("power_success", 1),
    # ⚠️ R-555. `total_yards` MUST PRECEDE `total`, and this is the specificity rule in the
    # note above doing real work rather than describing itself. "total" is here for the
    # BETTING total — an over/under is 54.5 and needs its half-point. Yardage is a count, and
    # with the default now 0 the substring match would have been the only thing left holding
    # `total_yards` at one decimal: today's Team yardage board would have printed Total 412.0
    # beside Rush 187 and Pass 225. The column is not a total, it is a total OF something.
    ("total_yards", 0), ("passing_yards", 0), ("rushing_yards", 0),
    # ⚠️ R-559. `("yards", 1)` STOOD HERE UNTIL B079 AND IS GONE BECAUSE ITS REASON IS.
    # A085 flipped the fallback to 0 and matchup.py was passing the BARE LITERAL 'yards' for
    # per-game averages, so the only signal reaching this table was the word itself and B's
    # page would have rendered 154.4 as 154. A does not own matchup.py (§3 rule 3.1), so the
    # shared module held B's page harmless instead of reaching across. B079 passed the real
    # column at both call sites; nothing in `site/` passes a bare 'yards' any more, verified
    # before this line came out. The three explicit yard keys above stay: they are Today's
    # box-score columns and they are genuinely counts.
    ("spread", 1), ("margin", 1), ("line", 1), ("edge", 1),
    # R-555. The bare literal `'move'` that schedule.py passes for line movement. It relied on
    # the old default and a spread moves in half-points, so the flip would have rounded every
    # movement glyph to a whole number — "+2.5" reading as "+2".
    ("move", 1),
    ("total", 1), ("over_under", 1), ("differential", 1),
)


def precision_for(column: str) -> int:
    """First match wins, in specificity order. See the note on PRECISION.

    R-555. THE DEFAULT IS 0, AND A DECIMAL IS THE EXCEPTION. Marc: "numbers default to #.#
    precision, but most should really be #. Should swap default to #, and make #.# the
    exception." He was reading the mechanism correctly — `Col(kind="num")` with no `dp=`
    lands here, and most of what does is a count, a yard, a rank or a score.

    ⚠️ THE FLIP IS ONLY SAFE BECAUSE THE TABLE ABOVE ABSORBED WHAT USED TO RELY ON THE
    FALLBACK. Fourteen call sites across nine columns reached the old `return 1`; the census
    is in the A085 report. Two of them NEEDED their decimal and are now keyed explicitly
    (`move`, and `brier` which needed three rather than one), and one column was being held
    at a decimal by a substring collision that the flip exposed (`total_yards` matching
    `total`). The rest — lead changes, ranks, poll points, box-score yardage, tackles — are
    integers and were only ever showing ".0".
    """
    name = column.lower()
    for key, dp in PRECISION:
        if key in name:
            return dp
    return 0


def text(value) -> str:
    """A cell value as a string, or "". MOVED HERE FROM `schedule.py` BY A147.

    🚨 `value or ""` IS NOT THIS, AND THE DIFFERENCE COST THE STACKED VIEW FIFTEEN ROWS. pandas
    returns NaN for a null in an object column, NaN is TRUTHY, so `nan or ""` evaluates to nan —
    which then fails a str.join with "expected str instance, float found". The view rendered the
    first fifteen games and died on the sixteenth, where the network was null.

    ⚠️ It failed inside `states.section`, which caught it and rendered an Error state, so there was
    no exception to see and no test to fail. **It was found by counting cards against rows.**

    ⚠️ IT MOVED BECAUSE A SECOND CALLER ARRIVED, NOT TO TIDY UP. `lib/glyphs.py` needs exactly this
    NaN-safe conversion for the result strip's three stored values, and writing it there would have
    been two implementations of one rule — which is what this project pays for repeatedly. `fmt` is
    the right home: it is a value-to-string normaliser, which is what this module is for.
    ⚠️ `schedule._text` REMAINS as a one-line delegation, because its eight call sites read better
    with the local name and renaming them would move bytes on a page this round must not change.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


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


def percent(value, dp: int = 1) -> str:
    """A 0–1 proportion as `##.#%`. A144.

    > **MARC**, on Biggest Upsets: *"Market gave them should be ##.#%"*

    🚨 §4.2.1 PUTS THIS ON THE RIGHT SIDE OF THE DISPLAY-ONLY LINE EXPLICITLY, and it is worth
    naming because a `* 100` in `site/` is exactly what R-611 trained everyone to stop at:
    *"scaling ONE column by a CONSTANT WRITTEN IN THE CODE — ×100 for a percent, :.1% —
    RENDERING."* The test the charter gives is how many consumers the number can have, and this
    one has none: it returns a string.

    ⚠️ IT IS A FUNCTION BECAUSE THE SITE HAD NO PERCENT SHAPE AND WAS ABOUT TO GET ITS SECOND
    INLINE ONE. `today.py`'s win-probability label already carries `f"{final * 100:.0f}%"`; a
    second literal in a `Col` would have been two spellings of one convention, drifting from the
    day they were written. **This is the one place a proportion becomes a percentage.**

    ⚠️ AC-G.32 IS INHERITED RATHER THAN RESTATED: null renders an em dash and zero renders `0.0%`,
    because the null check is `number()`'s and this defers to it.
    """
    if not _is_number(value):
        return EM_DASH
    return f"{number(float(value) * 100.0, dp=dp)}%"


def _is_number(value) -> bool:
    """Whether a proportion is there to scale.

    ⚠️ AN UNPARSEABLE VALUE IS AN EM DASH HERE, WHICH IS NARROWER THAN `number()`'s OWN FALLBACK
    AND DELIBERATELY SO. `number("x")` returns `"x"` — reasonable for a free-text column — but a
    percentage of a non-number is not a percentage, and `"x%"` would be a unit asserted over a
    value that has none.
    """
    try:
        return not pd.isna(value) and float(value) == float(value)
    except (TypeError, ValueError):
        return False


def signed(value, column: str = "", dp: Optional[int] = None) -> str:
    """A signed number, so a home-negative spread reads unambiguously."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return EM_DASH
    text = number(value, column, dp)
    return f"+{text}" if float(value) > 0 else text


def with_n(value, n, column: str = "") -> str:
    """A rate and its sample size, together.

    AC-G.33: a hit rate without an `n` is a defect, not a style choice. 17.9% on n=11 is
    noise wearing a big number, and the only defense is rendering the two adjacently.
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

    ⚠️ IT READS `start_date`, THE TZ-AWARE INSTANT, AND THE APP NOW OWNS THE WHOLE
    CONVERSION — one conversion, in one place. It used to read `start_date_et`, which dbt had
    already localized to Eastern and stripped of its offset, and converting that again is
    R-643: every kickoff four hours early, all season.
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
