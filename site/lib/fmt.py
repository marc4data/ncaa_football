"""Numbers, nulls and time. Formatting only — never arithmetic (G-3).

AC-G.30 to AC-G.35. Precision is fixed PER COLUMN, not per value, so a column of figures
compares vertically: `7` renders `7.0` where its column is 1 dp.
"""
from typing import Optional

import pandas as pd

EM_DASH = "—"

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


def eastern(ts) -> str:
    """AC-G.34: display Eastern with the zone shown. Storage stays UTC.

    The conversion itself is done in dbt (`start_date_et`); this only formats what arrives,
    so the app never owns a timezone rule.
    """
    if ts is None or pd.isna(ts):
        return EM_DASH
    stamp = pd.Timestamp(ts)
    return stamp.strftime("%a %d %b %Y, %-I:%M %p ET")


def as_of(ts) -> str:
    if ts is None or pd.isna(ts):
        return "as of — (freshness unavailable)"
    return f"as of {pd.Timestamp(ts).strftime('%d %b %Y %H:%M')} UTC"
