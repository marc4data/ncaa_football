"""Team identity: chrome, never encoding (§0.6, AC-G.24 to AC-G.29).

Two hard rules, both easy to break under deadline pressure and both the difference between
a data site and a misleading one:

  1. Colour identifies a team; it never carries a value. A bar whose fill is a team colour
     invites the reader to compare colours, which mean nothing.
  2. Contrast is computed in dbt, never here. dim_team ships color_on_light and
     color_on_dark already solved for WCAG; the app reads them.
"""
import math
from typing import Optional


FALLBACK = "#6b7280"


def text_on(row, dark_theme: bool = False) -> str:
    """The contrast-safe text colour for this team's own colour.

    AC-G.26. There is deliberately no contrast maths in this module — if a colour is
    missing, the neutral fallback is used rather than something computed here.
    """
    if row is None:
        return FALLBACK
    key = "color_on_dark" if dark_theme else "color_on_light"
    value = row.get(key) if hasattr(row, "get") else None
    return value or FALLBACK


def accent_style(row, dark_theme: bool = False) -> str:
    """A left accent rule — the only place a team colour is allowed to appear (AC-G.25)."""
    return f"border-left:4px solid {text_on(row, dark_theme)};padding-left:.6rem"


def logo_or_monogram(logo_url: Optional[str], display_name: str,
                     size_px: int = 28, color: str = FALLBACK) -> str:
    """A logo, or a monogram at the IDENTICAL footprint (AC-G.28).

    Same box either way, so a missing logo does not shift the layout, and no broken-image
    glyph is ever rendered. Logos come from our own cache; nothing is hotlinked (AC-G.27).
    """
    # R-121. `if logo_url:` WAS THE BUG, AND IT IS THE NaN ONE AGAIN.
    #
    # read_sql gives a NULL in an object column as float('nan'), and NaN IS TRUTHY. So a team
    # with no logo took the image branch and f-string interpolated the float, emitting
    # `<img src='nan'>` — a relative URL that 404s against the app's own host and paints the
    # browser's broken-image box. Exactly what AC-G.28 and the line below it promise never
    # happens, on the two teams Cowork spotted in a screenshot.
    #
    # This is the same defect as `r.get("network_abbreviation") or ""` in the stacked view,
    # which cost fifteen of fifty-nine cards and is why `_text()` exists. That fix was made in
    # the view; this module never got the guard, so every page rendering a team carried it.
    missing = logo_url is None or (isinstance(logo_url, float) and math.isnan(logo_url))
    if not missing and str(logo_url).strip():
        # alt is EMPTY on purpose. The team name is rendered immediately beside this, so
        # the image is decorative — and a non-empty alt means a CDN failure paints the name
        # a second time next to a broken-image glyph.
        #
        # THE MONOGRAM BEHIND IT IS THE CLIENT-SIDE HALF of R-121. Streamlit's sanitiser
        # strips event handlers, so `onerror` is not available — verified, not assumed. A
        # background on the wrapper is the fallback that survives: if the file 404s later the
        # img paints nothing over it and the reader sees the same grey disc a null gives.
        return (f"<span class='cfdb-logo-box' "
                f"style='width:{size_px}px;height:{size_px}px'>"
                f"<img class='cfdb-logo' src='{logo_url}' alt='' "
                f"style='width:{size_px}px;height:{size_px}px'></span>")
    # NO INITIALS. The monogram used to render "OD" beside "Ohio Dominican", which reads as
    # the name twice — Marc flagged it on three teams across two passes. The box stays so a
    # missing logo does not shift the row (AC-G.28 is about FOOTPRINT), but it is empty:
    # the name is right there, and one affordance means one thing.
    return (f"<span class='cfdb-monogram-empty' aria-hidden='true' "
            f"style='width:{size_px}px;height:{size_px}px'></span>")


# The colour ladder's rungs, as dim_team actually emits them. `primary` and `alternate` are
# the team's own brand colours; `adjusted` and `fallback` are cfdb's, and only those two are
# debt worth flagging.
SOURCED_RUNGS = ("primary", "alternate")


def color_source_hint(row) -> str:
    """AC-7.2: a defaulted colour must be identifiable, or it becomes invisible debt.

    THE GUARD WAS AGAINST A VALUE THAT NEVER OCCURS. It skipped `"brand"`, and dim_team
    emits primary / alternate / adjusted / fallback — so the hint rendered on all 34,061
    rows, including the 29,903 using the team's own primary colour. An indicator that fires
    on everything indicates nothing, which is the monogram fallback again: something that
    appears to be working precisely because it never discriminates.

    Not rendered on the Teams index any more regardless — see the note there. This stays
    correct for the data-quality surfaces, where a builder is the reader.
    """
    source = row.get("color_source") if hasattr(row, "get") else None
    if not source or source in SOURCED_RUNGS:
        return ""
    return f"<span class='cfdb-hint' title='colour {source} rather than sourced'>◦</span>"
