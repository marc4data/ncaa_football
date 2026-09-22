"""Identity: how the site says WHO something is — a team, and since A167 a player too.

Two hard rules about team colour, both easy to break under deadline pressure and both the
difference between a data site and a misleading one:

  1. Colour identifies a team; it never carries a value. A bar whose fill is a team colour
     invites the reader to compare colours, which mean nothing.
  2. Contrast is computed in dbt, never here. dim_team ships color_on_light and
     color_on_dark already solved for WCAG; the app reads them.

⚠️ A167 ADDED THE PLAYER CARD'S IDENTITY ROW AT THE BOTTOM OF THIS FILE, because Marc asked for
Matchup's card on Today and the two pages must not each own a copy of it. The module's subject
did not change — it is still "how an entity is presented" — it gained a second kind of entity.
"""
import html
import math
from typing import Optional

import pandas as pd


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


def accent_color(row, prefix: str = "") -> str:
    """ONE team colour as a finished CSS string, BOTH variants, resolved by the browser.

    🚨 A171 (cfdb-main-R-1601). PROMOTED FROM `matchup.py:_accent`, WHOSE OWN DOCSTRING SAYS
    IT IS "written HERE and nowhere else" — and which lives in session B's file, so Today
    could not call it and would have had to write the second copy that docstring warns about.
    §3 rule 3.1: the shared module ships the function; **B consumes it on its own round**, and
    until it does, `matchup.py:_accent` is a duplicate that this one is the successor to.

    ⚠️ `text_on(row)` ALONE IS NOT THE ANSWER AND B109 MEASURED WHY (R-855). It defaults to
    the ON-LIGHT variant, which renders `rgb(0,0,0)` against a `rgb(14,17,23)` page —
    invisible — for the **18.6% of teams that publish `#000000` there.**

    ✅ `light-dark()` follows the `color-scheme` property Streamlit sets, so the BROWSER
    resolves it: correct on a mid-session theme flip, with no Python in the loop. That works
    in inline SVG and in CSS; it does NOT work inside a Vega spec, which rejects the string
    and falls back to `#ddd` (B135/B136, cfdb-main-R-1236). **Use this for markup, never for
    a Vega mark.**

    `prefix` reads a SIDE off a wide game row — `home_color_on_light` / `home_color_on_dark`
    for `prefix="home"`. Unprefixed, it reads a narrow row that already carries the pair.

    ⚠️ AND IT GUARDS NaN, WHICH `text_on` DOES NOT. `read_sql` gives a NULL colour as
    `float('nan')`, and `value or FALLBACK` keeps it because **NaN is truthy** — the R-121
    defect, one layer along. A NaN reaching an SVG `fill` is an invalid colour the browser
    drops silently. Measured on the 1,898 games this chart can draw: **0 nulls in either
    theme**, so this is a guard against the case rather than a fix for a live one.
    """
    def one(dark: bool) -> str:
        key = f"{prefix}_color_on_dark" if dark else f"{prefix}_color_on_light"
        key = key.lstrip("_")
        value = row.get(key) if (row is not None and hasattr(row, "get")) else None
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return FALLBACK
        return str(value).strip() or FALLBACK
    return f"light-dark({one(False)}, {one(True)})"


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
    return f"<span class='cfdb-hint' title='color {source} rather than sourced'>◦</span>"


# ── THE PLAYER CARD'S IDENTITY ROW ─────────────────────────────────────────────────────────
#
# 🚨 A167 PROMOTED THIS OUT OF `matchup.py` (cfdb-main-R-1308), AND MARC IS WHY.
#
# > **MARC, Today v06:** *"Prefer the player card from the Matchup, but want to add in the team
# > logo/name for this Today page b/c there's no context about what team they play for on the
# > Today page."*
#
# ⚠️ **HE IS REVERSING A DECISION A166 MADE ON INSTRUCTION.** That round's prompt said of this
# card *"Read it for its proportions; do not import from it and do not edit it"*, and the round
# obeyed and built a different shape. **He has seen both and prefers the one he was not given.**
#
# ✅ **SO THE SHARED VOCABULARY MOVES TO `lib/` RATHER THAN BEING COPIED OR IMPORTED ACROSS
# VIEWS.** Copying is §4.3's drift; a view importing another view couples two pages. This is the
# third time in three rounds the answer has been *the shared thing belongs in lib*
# (`theme.viewer_is_dark`, A165; the `.cfdb-identity` wrapper, A164), and `identity.py` is the
# module named for exactly this question — it already owns `logo_or_monogram` and `text_on`.
#
# 🚨 **ONLY THE IDENTITY ROW MOVED. THE KPI GRID AND THE USAGE DOTS DID NOT** — Matchup's card
# carries three stat slots and a usage frame Today has neither of. **A promotion that dragged
# those across would have made Today depend on columns it does not select.**
#
# ⚠️ **THIS CARRIES TEN ROUNDS OF MARC'S OWN CORRECTIONS AND NONE OF THEM MAY REGRESS** —
# R-753 (three columns, no rank), R-800 (jersey 2x, filling both name lines), R-801 (year over
# position, the surname's treatment on the position), R-806 and R-848 (the `#` as a RATIO of the
# jersey, .5 -> .62), R-835 (the two-line name), B103 (a missing first name is OMITTED, not
# blanked), B104 (the em-dash jersey), B107 (the sizes, measured by counting truncations).
# **The values below are those measurements; they are not taste and they are not round numbers.**

# 🚨 B107 MEASURED THESE BY RENDERING THREE COMPLETE SETS AT THE CARD'S REAL 150px AND COUNTING
# THE TRUNCATIONS — set C shipped at 0 of 10, against 2 and 3 for the alternatives. `.92` is a
# CEILING rather than a round number: `Sanders II` is the longest surname the game holds and
# needs 70.8px of a 72px column at that size, and truncates at `.95`. **The constant IS the
# measurement.** The full derivation stays in `matchup.py` beside the card that commissioned it.
CARD_JERSEY_SIZE = 1.15
CARD_LAST_SIZE = 0.92
CARD_FIRST_SIZE = 0.7
# R-848: the `#` is a RATIO of the jersey, in `em` not `rem`, so it follows whatever the jersey
# is set to and cannot drift if that constant moves. The RATIO went .5 -> .62; the jersey did not.
CARD_HASH_RATIO = 0.62


def split_name(value) -> tuple:
    """A player's name as (first line, bold line). 🚨 AN ASSUMPTION, NOT A FORMAT.

    `player_name` is ONE STRING; no view carries the parts. **First token as the first name and
    the remainder as the last** is the rule, and it renders *Emmett Mosley V* and *Ray Davis Jr.*
    the way a reader expects — the remainder keeps the suffix with the surname rather than
    stranding it on its own line.

    ⚠️ A SINGLE-TOKEN NAME HAS NO FIRST LINE AND RENDERS AS THE BOLD LINE ALONE. An empty first
    line would still occupy its line-height and shift that one card's header down relative to
    the others — a hole reserved for something that does not exist (AC-G.11).
    """
    parts = str(value or "?").split()
    if len(parts) < 2:
        return "", (parts[0] if parts else "?")
    return parts[0], " ".join(parts[1:])


def card_text(value) -> str:
    """A card field as text, with NULL meaning ABSENT rather than the string `nan`.

    🚨 `str(value or "")` DOES NOT DO THIS AND THAT IS THE WHOLE REASON THIS EXISTS: NaN is
    truthy, so the `or` never fires and the page prints `nan`. `pd.isna` is the only test that
    answers for None, NaN and NaT alike.
    """
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip()


def player_row(row, tie: str = "") -> str:
    """Jersey · two-line name · year over position — the card header Marc asked both pages for.

    `tie` is an optional marker appended to the position, because **Matchup carries
    `tied_players` and Today's view does not.** It is a parameter rather than a lookup so the
    promoted row does not read a column one of its two callers cannot supply (§2.5).

    ⚠️ **AC-G.32 ON THE JERSEY, AND THE NUMBER BEHIND IT HAS MOVED.** `_leader_card`'s docstring
    said *"0 of 8,447 non-FBS leader rows carry one, because the roster load covers 138 of 305
    teams (R-693)"*. 📊 **A167 re-measured that on the card's OWN relation,
    `srv_game_team_leader_in_this_game`: 8,563 rows for 2026 and 8,129 carry a jersey — 94.9%**,
    with 2024 at 95.3% and 2025 at 97.1%. **The roster was refetched on 2026-09-16** (A166,
    cfdb-main-R-1306), and this is the third copy of that stale figure to be corrected.
    ✅ **THE ABSENCE BRANCH STAYS**: it is still right for the rows that have no jersey — it is
    simply no longer the common case. A missing jersey renders as an em dash in the same slot,
    with NO `#`, because a hash with nothing after it reads as a broken number.
    """
    jersey = row.get("jersey")
    number = (f"<span style='font-size:{CARD_HASH_RATIO}em;opacity:.65'>#</span>{int(jersey)}"
              if pd.notna(jersey) else "—")
    first, last = split_name(row.get("player_name"))
    year = card_text(row.get("class_year_display"))
    position = card_text(row.get("position"))
    small = "font-size:.66rem;opacity:.6;line-height:1.1"
    strong = "font-weight:700;font-size:.78rem;line-height:1.15"
    # ⚠️ `min-width:0` ON EVERY FLEX CHILD THAT CAN OVERFLOW is what makes the ellipsis work at
    # all: without it a flex child refuses to shrink below its content and the name pushes the
    # year/position column off the card instead of truncating (the R-745 class).
    # ⚠️ `min-width:0` ON EVERY FLEX CHILD THAT CAN OVERFLOW is what makes the ellipsis work at
    # all: without it a flex child refuses to shrink below its content and the name pushes the
    # year/position column off the card instead of truncating (the R-745 class).
    #
    # 🚨 A192 (cfdb-main-R-2015): THESE FOUR STAY INLINE, AND THAT IS A DELIBERATE REVERSAL.
    # An inline `style=` beats every class selector, so Today's card cannot override them from
    # a stylesheet — it uses `!important`, which is the canonical case for it. **Moving them
    # into a class rule was tried first and is the tidier CSS**, but `tests/test_matchup_*.py`
    # locate the name by this very `text-overflow:ellipsis` string, and those are session B's
    # files (§3). A shared-module change that forces edits into the other session's tests is
    # R-729's shape exactly; two `!important`s in Today's own sheet cost less than crossing
    # that line, and leave Matchup's markup byte-identical to what its tests assert.
    clip = "min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
    # 🚨 A192 (cfdb-main-R-2011). THE PARTS CARRY CLASSES NOW, AND THEY ARE INERT HERE.
    #
    # 🚨 THE `class` ATTRIBUTE COMES AFTER `style`, AND THAT IS NOT FORMATTING. Session B's
    # tests do string surgery on this markup — `test_each_POSITION_HEADER_spans_BOTH_halves`
    # splits on the literal `<div style='display:flex`, and the yardage tests match
    # `text-overflow:ellipsis[^>]*>`. Putting the class first breaks those literals and
    # forces edits into another session's test files (§3, R-729). Appending instead leaves
    # every prefix they match byte-identical. **CSS does not care about attribute order.**
    #
    # Every piece of this row was an anonymous `<div style=…>`, so **nothing outside this
    # function could address any of it** — not a stylesheet, not a test, not a measurement.
    # A192 had to reach the last name to guarantee it is never truncated, and the only way in
    # was `who.firstElementChild.children[1].lastElementChild`, which is a fact about today's
    # nesting rather than about the name.
    #
    # ⚠️ CLASSES ONLY — NO STYLE MOVES HERE, DELIBERATELY. `matchup.py:2374` calls this
    # function and carries **zero** `cfdb-card*` rules, so Today can scope its own layout under
    # `.cfdb-card` and Matchup cannot be reached by it. That is the §3 rule-3.1 shape: the
    # shared module ships the hook, and each caller consumes it on its own page.
    name_block = (
        f"<div style='flex:1;{clip}' class='cfdb-player-name'>"
        # 🚨 THE FIRST NAME IS OMITTED, NOT BLANKED, WHEN THERE IS NONE — B103's ruling. An empty
        # first line would still take its line-height and drop that one card's surname below its
        # neighbours': a hole reserved for something that does not exist (AC-G.11).
        + (f"<div style='font-size:{CARD_FIRST_SIZE}rem;opacity:.6;line-height:1.15;"
           f"{clip}' class='cfdb-player-first'>"
           f"{html.escape(first)}</div>" if first else "")
        + f"<div style='font-weight:700;font-size:{CARD_LAST_SIZE}rem;line-height:1.15;"
          f"{clip}' class='cfdb-player-last'>{html.escape(last)}</div></div>")
    return (
        # 🚨 `align-items:center` IS MARC'S OWN ARGUMENT MADE MECHANICAL: the jersey spans the
        # two-line block, so it is centred against BOTH lines rather than sitting on the first.
        f"<div style='display:flex;align-items:stretch;gap:.4rem' class='cfdb-player-row'>"
        f"<div style='min-width:1.7rem;font-weight:700;font-size:{CARD_JERSEY_SIZE}rem;"
        f"line-height:1;display:flex;align-items:center' "
        f"class='cfdb-player-jersey'>{number}</div>"
        f"{name_block}"
        f"<div style='text-align:right;min-width:0' class='cfdb-player-meta'>"
        + (f"<div style='{small}'>{html.escape(year)}</div>" if year else "")
        + f"<div style='{strong};white-space:nowrap'>"
          f"{html.escape(position) if position else '—'}{tie}</div></div>"
        f"</div>")
