"""Metric definitions the app READS and never restates.

A threshold is part of a metric definition and lives in `dbt/dbt_project.yml`, because dbt
owns transforms and metric definitions. The app needs the same numbers to LABEL what dbt
computed, and the two must never be typed out twice.

THEY WERE, TWICE OVER. `views/schedule.py` carried "Upset by 7+" and "Upset by 14+" as string
literals from R-141 until 2026-09-04, and `lib/workbook.py` grew a reader of its own. Neither
was checked against the warehouse, and the page's numbers were WRONG BY ONE at both ends:
srv_game classifies with a strict `>`, so a 7-point win is level 1 and a 14-point win is level
2. 138 completed games carried a level the legend contradicted. The data was never wrong; only
the labels were, which is worse, because nothing breaks visibly.

THE FIRST FIX WAS A STOPGAP AND SAID SO. It read `dbt_project.yml` from disk, which cannot
work inside the site image: `deploy/docker-compose.yml` builds with `context: ./site`, so the
repo root is outside the build context and the deployed page ran on the fallback — correct by
coincidence, and silently stale the day a var changed. That was the THIRD collision with the
same boundary, after `.streamlit/config.toml` and `lib/lines_cadence.json`. `ci/check_site_paths.py`
now guards it (R-225).

THIS IS THE REAL FIX. `srv_game` carries `upset_margin_big` and `upset_margin_blowout` as
columns (R-224), exactly as it already carries `training_week_floor`. Every caller reads a row
it was fetching anyway: no file access, no fallback, correct in the container by construction,
and `dbt run` after changing a var moves every label at once.

`DEFAULTS` exists only for callers with no frame in hand — a unit test, an empty result. It is
not a fallback path in production, and `from_frame` says so when it uses one.
"""
from typing import Optional, Tuple

import pandas as pd

# The values shipped in dbt_project.yml. Present so a caller with no data still renders
# something coherent rather than crashing; NEVER the source of truth.
DEFAULTS: Tuple[int, int] = (7, 14)

BIG_COLUMN = "upset_margin_big"
BLOWOUT_COLUMN = "upset_margin_blowout"


def from_frame(df: Optional[pd.DataFrame]) -> Tuple[int, int]:
    """The upset thresholds carried by this frame, or the shipped defaults.

    Reads the first non-null value rather than asserting the column is constant. It IS
    constant — every row of srv_game carries the same two numbers — but a page that raised
    because one row was null would be trading a wrong label for a blank screen, which is a bad
    trade for a legend.
    """
    if df is None or getattr(df, "empty", True):
        return DEFAULTS
    out = []
    for column, fallback in ((BIG_COLUMN, DEFAULTS[0]), (BLOWOUT_COLUMN, DEFAULTS[1])):
        if column not in df.columns:
            out.append(fallback)
            continue
        values = df[column].dropna()
        out.append(int(values.iloc[0]) if len(values) else fallback)
    return out[0], out[1]


def upset_ranges(big: int, blowout: int) -> Tuple[str, str, str]:
    """The three margins, as bare phrases. The one place the ARITHMETIC lives.

    The boundary is EXCLUSIVE — `> big` is level 2 — so level 1 reads "or fewer" and the
    middle band starts one point above. Getting that wrong by one is what shipped for months.
    """
    return (f"{big} or fewer", f"{big + 1}–{blowout}", f"more than {blowout}")


def upset_bands(big: int, blowout: int) -> Tuple[str, str, str]:
    """The page's legend labels: compact, because the popover column is narrow."""
    first, middle, _ = upset_ranges(big, blowout)
    return (f"Upset by {first}", f"Upset by {middle}", f"Upset by {blowout + 1}+")


def upset_criteria(big: int, blowout: int) -> Tuple[str, str, str]:
    """The workbook's phrasing: prose, because a spreadsheet legend has a whole column and a
    reader who may never have seen the site.

    TWO PHRASINGS, ONE SET OF NUMBERS. That is the split worth keeping: the surfaces are
    allowed to word it for their own space, and neither is allowed to know 7 or 14.
    """
    return tuple(f"the underdog won by {phrase}"
                 for phrase in upset_ranges(big, blowout))
