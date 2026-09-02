"""Schedule — page 2.

GRAIN IS ONE ROW PER GAME (AC-2.1). This is the inversion the spec once carried backwards:
a count on srv_game equals the game count for the filtered scope, never twice it, because
the view reads fct_game rather than fct_game_team.

TWO VIEWS, AS TABS (R-043). Dense is the table; Stacked is the card. Tabs rather than a
toggle because a tab is URL-addressable through st.query_params and a toggle is not — the
same finding that shaped the rest of the site's navigation. Both read the SAME single
relation and the same frame; the stacked view is a different rendering, not a second query.
"""
import pandas as pd
import streamlit as st

from lib import chips, filters, fmt, params, shell, states, table
from lib.query import query
from lib.table import Col

VIEWS = {"dense": "Dense", "stacked": "Stacked"}

# R-085. A CHARACTER COUNT, NOT A WRAP PREDICTION.
#
# "Would this wrap" depends on rendered width, which is not knowable server-side and would
# behave differently on two screens. A threshold on the display name is deterministic: the
# same row abbreviates identically everywhere.
#
# 18 is chosen against the data rather than by eye — it abbreviates the genuinely long names
# ("Middle Tennessee State", "Southeastern Louisiana") while leaving the ones a reader
# expects to see spelled out ("Oklahoma State", 14; "Northwestern", 12) alone.
TEAM_NAME_MAX = 18

# R-027. The 18 condition codes CFBD actually sends, mapped to a small set. Nothing here is
# invented: every code below was observed in the data, and code 0 arrives with a blank label
# and is treated as unknown rather than as clear weather.
WEATHER_GLYPH = {
    1: "☀", 2: "☀",                      # Clear, Fair
    3: "☁", 4: "☁",                      # Cloudy, Overcast
    5: "≋",                               # Fog
    7: "☂", 8: "☂", 9: "☂", 17: "☂", 18: "☂",   # rain, all intensities
    12: "❄", 13: "❄", 20: "❄",           # sleet
    14: "❄", 15: "❄", 16: "❄",           # snow
    25: "⚡",                              # Thunderstorm
}
DOME_GLYPH = "⌂"
NEUTRAL_GLYPH = "◇"

# R-100 / R-113. THE SAME GLYPH THE SCORES PAGE ALREADY USES.
#
# Prompt 032 wrote this as ◀. `scores.py` has shipped ▸ against the same `.cfdb-winner`
# class since it was built, and R-100's own wording is "a relocation, not a new component".
# Two pages marking a winner with two different characters is a worse outcome than a
# one-character deviation from the prose, so this reuses the component whole. It also points
# INTO the number it precedes rather than away from it.
WINNER_GLYPH = "▸"
# A tie is completed AND has no winner, which is not the same fact as "not played yet". The
# chip this replaced kept those apart and so does this: nothing on either row means pending,
# `=` on BOTH rows means level, ▸ on one row means won.
TIE_GLYPH = "="

# R-104's fields, rendered. Δ rather than ▷: the direction is already carried by the sign,
# and a directional glyph beside a negative number is two cues that can disagree.
MOVE_GLYPH = "Δ"

# R-109. One letter for the score column of a box score, chosen once so a box score on any
# future page uses the same one. T for Total.
TOTAL_HEADER = "T"


def _rows(season: int, week, season_type: str, conference,
          division: str = 'fbs') -> pd.DataFrame:
    sql = """
        select game_id, season, week, season_type, start_date_et, game_date,
               home_team_slug, home_team_display, home_abbreviation, home_logo_url,
               home_conference, home_points, home_rank, home_team_record_display,
               away_team_slug, away_team_display, away_abbreviation, away_logo_url,
               away_conference, away_points, away_rank, away_team_record_display,
               venue_display, network, network_abbreviation, is_neutral_site,
               is_conference_game, is_completed, winner, best_rank_in_game,
               spread_current, total_current, predicted_margin, home_win_probability,
               spread_move_from_open, total_move_from_open,
               excitement_index,
               is_indoors, temperature_f, weather_condition_code, weather_condition,
               home_q1, home_q2, home_q3, home_q4, home_overtime_points, home_periods,
               away_q1, away_q2, away_q3, away_q4, away_overtime_points, away_periods,
               as_of_ts
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          -- FBS spine: EITHER team FBS, defaulted rather than hardcoded, so
          -- 'All divisions' in the filter bar genuinely widens it.
          and (:division = 'all' or is_fbs_game)
          and (:conf is null or home_conference = :conf or away_conference = :conf)
        -- R-108. Date, then kickoff, then the best rank ON THE FIELD, then the home name.
        -- The rank only ever breaks a tie between games kicking at the same minute, which
        -- is exactly where a reader wants the ranked matchup first. `nulls last` is the
        -- whole of "unranked last" — without it Postgres sorts NULL high and every unranked
        -- game leads its own time slot.
        order by game_date, start_date_et, best_rank_in_game nulls last,
                 home_team_display, game_id
        limit 400
    """
    return query(sql, {"season": season, "week": week, "season_type": season_type,
                       "conf": conference, "division": division})


# --- shared cell renderers ------------------------------------------------------------

def _text(value) -> str:
    """A cell value as a string, or "".

    `value or ""` IS NOT THIS, and the difference cost the stacked view fifteen rows. pandas
    returns NaN for a null in an object column, NaN is TRUTHY, so `nan or ""` evaluates to
    nan — which then fails a str.join with "expected str instance, float found". The view
    rendered the first fifteen games and died on the sixteenth, where the network was null.

    It failed inside states.section, which caught it and rendered an Error state, so there
    was no exception to see and no test to fail. It was found by counting cards against rows.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _missing(value) -> bool:
    """Null in either of the two shapes a serving row hands back."""
    return value is None or (isinstance(value, float) and pd.isna(value))


def _team_name(row, side: str) -> str:
    """Display name, abbreviated past the threshold. R-085."""
    name = _text(row.get(f"{side}_team_display")) or "—"
    if len(name) > TEAM_NAME_MAX:
        # An abbreviation can be null for a team absent from /teams, so fall back to a
        # truncation rather than to NaN.
        return _text(row.get(f"{side}_abbreviation")) or name[:TEAM_NAME_MAX]
    return name


def _team_abbrev(row, side: str) -> str:
    """The BOUNDED label for a box-score row. R-109, and the reason R-015 is tractable here.

    "North Carolina" against "TCU" is a 14-character swing in the first column of the box
    score, and with `table-layout:fixed` a shared colgroup has to be sized for the worst
    case on the page. The abbreviation caps that swing at three or four characters, so the
    one geometry computed for the whole page fits every card without truncating any of them.
    """
    return _text(row.get(f"{side}_abbreviation")) or _team_name(row, side)


def _team_with_record(row, side: str) -> str:
    """Team cell with the record beside the name, smaller and regular weight. R-088.

    The record is the one LEADING INTO this game's week, from fct_team_record_week — not the
    season-final record, which is what fct_team_record would give and which would show 11-2
    beside a game played in September.

    Renders NOTHING when the record is absent rather than substituting the season figure. A
    record that is wrong for the week is worse than a missing one, which is the whole reason
    R-084 exists.
    """
    base = table.team_cell(row, f"{side}_team_slug", f"{side}_team_display",
                           f"{side}_logo_url", f"{side}_rank")
    # Swap the display name for the abbreviated form where it is over the threshold.
    display = row.get(f"{side}_team_display")
    short = _team_name(row, side)
    if display and short != str(display):
        base = base.replace(f">{display}<", f">{short}<")
    record = row.get(f"{side}_team_record_display")
    if _missing(record):
        return base
    return f"{base}<span class='cfdb-team-record'>{record}</span>"


def _winner_side(row):
    """"home", "away", "tie", or None for a game not yet played. R-029, unchanged in fact.

    `winner` is computed in dbt and carries the team NAME. Pending is distinct from a tie:
    an unplayed game has no winner YET, and a tie has no winner AT ALL. Collapsing those into
    one blank is the mistake the chip this replaced already refused to make.
    """
    if not row.get("is_completed"):
        return None
    winner = row.get("winner")
    if _missing(winner):
        return "tie"
    return "home" if winner == row.get("home_team_display") else "away"


def _winner_marker(row, side: str) -> str:
    """R-100 / R-113. The marker, and the SPACE FOR THE MARKER on the row that lacks it.

    If only the winning row carried a character the two scores would no longer line up
    vertically, and a misaligned pair of numbers reads as a rendering bug rather than as a
    marker. `.cfdb-winner-spacer` is a fixed-width empty inline-block, already used by the
    Scores page for exactly this.

    A glyph rather than a colour, so the result survives greyscale and a colour-blind reader
    (AC-G.22).
    """
    state = _winner_side(row)
    if state == "tie":
        return f"<span class='cfdb-winner' title='the game ended level'>{TIE_GLYPH}</span>"
    if state == side:
        return f"<span class='cfdb-winner' title='won'>{WINNER_GLYPH}</span>"
    return "<span class='cfdb-winner-spacer'></span>"


def _score_cell(row, side: str) -> str:
    """R-100. The winner marker moved onto the score it describes.

    It used to be its own "Won" column holding a chip with a team name in it — a full column
    of width to restate something the two numbers beside it already implied, and the name was
    a third rendering of a team already named twice on the row.
    """
    return _winner_marker(row, side) + fmt.number(row.get(f"{side}_points"),
                                                  f"{side}_points", 0)


def _weather_cell(row) -> str:
    """R-027. Icon plus temperature — EXCEPT indoors, where there is no temperature to give.

    CFBD reports the weather at the venue's LOCATION, not inside it, so a domed game carries
    ordinary outdoor readings. Rendering "94°F" beside a game played under a roof is a true
    number answering the wrong question, so the dome glyph stands alone.
    """
    if row.get("is_indoors"):
        return f"<span class='cfdb-wx' title='indoor venue'>{DOME_GLYPH}</span>"
    temp = row.get("temperature_f")
    if _missing(temp):
        return ""
    code = row.get("weather_condition_code")
    glyph = WEATHER_GLYPH.get(int(code)) if not _missing(code) else None
    label = row.get("weather_condition") or "conditions not recorded"
    return (f"<span class='cfdb-wx' title='{label}'>"
            f"{glyph or ''} {float(temp):.0f}°F</span>")


def _neutral_glyph(row) -> str:
    """R-026. ICON ALONE, NO TEXT LABEL.

    A DELIBERATE EXCEPTION to the site's glyph+label convention, decided by Marc against a
    small known user base and logged in the decision log with its reason. It is not an
    oversight and it is not to be "fixed" back to glyph+label. R-102's legend is what makes
    the exception defensible: the page explains the glyph once, at the top.
    """
    if not row.get("is_neutral_site"):
        return ""
    return f"<span class='cfdb-neutral' title='neutral site'>{NEUTRAL_GLYPH}</span>"


def _columns(scope) -> list:
    return [
        # AC-2.5: the row goes to the game, the team NAME goes to the team.
        Col("start_date_et", "Kickoff", "time"),
        Col("away", "Away", render=lambda r: _team_with_record(r, "away"),
            link=lambda r: scope.link("team", team=r.get("away_team_slug"))),
        # R-100. The "Won" chip column is gone; the marker rides the score.
        Col("away_points", "", "num", dp=0, render=lambda r: _score_cell(r, "away")),
        Col("home", "Home", render=lambda r: _team_with_record(r, "home"),
            link=lambda r: scope.link("team", team=r.get("home_team_slug"))),
        Col("home_points", "", "num", dp=0, render=lambda r: _score_cell(r, "home")),
        Col("spread_current", "Spread", "signed"),
        # R-087. O/U, reconciled with Odds Board so one field has one name site-wide.
        Col("total_current", "O/U", "num"),
        # R-086. RENAMED RATHER THAN WRAPPED. A two-line header raises the height of every
        # column header for one column's benefit, and "Pred" is already the site's shorthand
        # for a model number — the sign note directly above the table explains the sign.
        Col("predicted_margin", "Pred", "signed"),
        # R-027 / R-103.
        Col("weather", "Wx", "center", render=_weather_cell),
        Col("network_abbreviation", "TV"),
        # R-101. ONE COLUMN, WITH A HEADER, FOR BOTH GLYPHS.
        #
        # These were two columns — `table.details_col` and a headerless neutral-site glyph —
        # costing two column widths for at most two characters, one of which was blank on
        # 95% of rows. R-026's icon-only exception is about the ROW, not the header: a header
        # on the column is not the glyph+label pattern Marc declined.
        Col("game", "Game", "center",
            render=lambda r: (f"<span class='cfdb-details' title='Open the matchup'>"
                              f"{table.DETAILS_GLYPH}</span>" + _neutral_glyph(r)),
            link=lambda r: scope.link("matchup", game_id=r["game_id"])),
    ]


def _legend() -> None:
    """R-102. The glyphs, once, above both views.

    Above the tables and OUTSIDE the view branch, so it applies to whichever tab is showing
    rather than being written twice and drifting.
    """
    st.markdown(
        "<div class='cfdb-legend'>"
        f"<span>{table.DETAILS_GLYPH} matchup</span>"
        f"<span>{NEUTRAL_GLYPH} neutral site</span>"
        f"<span>{MOVE_GLYPH} change since the line opened</span>"
        f"<span>{WINNER_GLYPH} won &nbsp;·&nbsp; {TIE_GLYPH} tied</span>"
        "<span>@ at &nbsp;·&nbsp; vs neutral site</span>"
        "</div>", unsafe_allow_html=True)


# --- the two views --------------------------------------------------------------------

def _dense(df: pd.DataFrame, scope) -> None:
    """AC-2.2: grouped by day, kickoff order within a day, with day headers."""
    layout = table.column_layout(df, _columns(scope))
    for day, rows in df.groupby(df["game_date"], sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{pd.Timestamp(day):%A %d %B %Y}</div>",
                    unsafe_allow_html=True)
        table.render(rows, _columns(scope), caption="", layout=layout,
                     link_builder=lambda r: scope.link("matchup", game_id=r["game_id"]))


# --- the stacked view -----------------------------------------------------------------

def _has_periods(row, side: str) -> bool:
    periods = row.get(f"{side}_periods")
    return not _missing(periods)


def _linescore_geometry(df: pd.DataFrame) -> dict:
    """R-015 FOR THE STACKED VIEW: the box score's shape decided ONCE, for the whole page.

    The dense view has done this since it was built — `_dense` computes `column_layout`
    outside the day loop and hands the same widths to every day's table. The stacked view had
    no equivalent: every card's `.cfdb-linescore` auto-sized to its own contents, so a card
    with an OT column was wider than the one beside it and the row labels started at a
    different x on every card. In a two-up grid (R-110) that reads as broken alignment.

    Two facts are enough to fix it, and both must be taken over the whole frame rather than
    per card:

      ot        does ANY game on this page need an OT column. If one does, every card gets
                the column — blank, not zero, where the game ended in regulation. A blank
                cell is true (there were no overtime points); a 0 would claim a scoreless
                overtime that was never played.
      label_ch  the widest row label on the page, in characters. Abbreviations (R-109) keep
                this to three or four, which is why the shared width does not have to be
                sized for "Middle Tennessee State".

    Capped at 8 so one pathological abbreviation cannot widen every card on the page.
    """
    any_ot, label = False, 3
    for _, row in df.iterrows():
        for side in ("home", "away"):
            periods = row.get(f"{side}_periods")
            if not _missing(periods) and int(periods) > 4:
                any_ot = True
            label = max(label, len(_team_abbrev(row, side)))
    return {"ot": any_ot, "label_ch": min(label, 8)}


def _ls_colgroup(geo: dict) -> str:
    """The shared geometry as markup. `.cfdb-linescore` is `table-layout:fixed`, so these
    widths are honoured rather than treated as hints."""
    cols = [f"<col style='width:{geo['label_ch'] + 1}ch'>"]
    cols += ["<col style='width:2.6em'>"] * (5 if geo["ot"] else 4)
    cols.append("<col style='width:3em'>")      # the total, R-109
    cols.append("<col style='width:1.2em'>")    # the winner marker, R-113
    return "<colgroup>" + "".join(cols) + "</colgroup>"


def _ls_header(geo: dict) -> str:
    quarters = "".join(f"<th>{q}</th>" for q in (1, 2, 3, 4))
    overtime = "<th>OT</th>" if geo["ot"] else ""
    return (f"<tr><th></th>{quarters}{overtime}"
            f"<th title='Total'>{TOTAL_HEADER}</th>"
            f"<th class='cfdb-ls-mark'></th></tr>")


def _ls_row(row, side: str, geo: dict) -> str:
    """One team's line, ending in the final score and the winner marker.

    R-109 folded the score in here. It used to be a separate bold block on the left of the
    card, which meant the card stated the same two numbers in two places once quarters
    existed, and stated them in only one place when they did not.
    """
    has = _has_periods(row, side)
    cells = []
    for q in (1, 2, 3, 4):
        value = row.get(f"{side}_q{q}")
        # R-092: absent, not zero. A row of zeros would claim four scoreless quarters.
        cells.append(f"<td>{'—' if not has else ('' if _missing(value) else int(value))}</td>")
    if geo["ot"]:
        periods, overtime = row.get(f"{side}_periods"), row.get(f"{side}_overtime_points")
        if has and int(periods) > 4:
            cells.append(f"<td class='cfdb-ls-ot'>"
                         f"{0 if _missing(overtime) else int(overtime)}</td>")
        else:
            cells.append("<td></td>")
    points = row.get(f"{side}_points")
    cells.append(f"<td class='cfdb-ls-total'>"
                 f"{'' if _missing(points) else int(points)}</td>")
    cells.append(f"<td class='cfdb-ls-mark'>{_winner_marker(row, side)}</td>")
    return (f"<tr><td class='cfdb-ls-team'>{_team_abbrev(row, side)}</td>"
            f"{''.join(cells)}</tr>")


def _score_block(row, geo: dict) -> str:
    """The box score. R-106 gates this on `is_completed`, so it is never the pre-kick state."""
    why = ""
    if not _has_periods(row, "away") and not _has_periods(row, "home"):
        # R-092. ABSENT, NOT ZERO — and the card says WHICH.
        #
        # Only 44,775 of 110,879 games carry quarters: 64,254 hold an empty array and 1,850
        # hold JSON null, and the earliest is 2001. Modern seasons are effectively complete
        # (3,805 of 3,831 in 2025), so the gap is historical. Omitting the block silently
        # would be honest about the value and silent about the reason, which leaves a reader
        # wondering whether the page is broken.
        #
        # This copy is for a COMPLETED game whose quarters were never recorded. It is NOT the
        # pre-kick state and R-106 is what keeps it from being shown for one: a scheduled
        # game is not a game whose quarter scores are missing.
        season = row.get("season")
        text = ("Quarter scores are not recorded before 2001."
                if not _missing(season) and int(season) < 2001
                else "No quarter scores recorded for this game.")
        why = f"<div class='cfdb-ls-why'>{text}</div>"
    return (f"<table class='cfdb-linescore'>{_ls_colgroup(geo)}{_ls_header(geo)}"
            f"{_ls_row(row, 'away', geo)}{_ls_row(row, 'home', geo)}</table>{why}")


def _market_block(row) -> str:
    """R-106. What occupies the box-score's space BEFORE kickoff.

    Away row carries the total, home row the spread, so each number sits beside the team it
    is quoted against in the rows above. The move is R-104's field rendered — same field,
    same name as on Line Movement, whatever the header shows.

    A game with no line yet returns "" and the card shows NOTHING there. Not an empty slot,
    not a dash: a market that does not exist yet is not a missing value.
    """
    lines = []
    for label, value, move, kind in (
            ("O/U", row.get("total_current"), row.get("total_move_from_open"), "num"),
            ("Spread", row.get("spread_current"), row.get("spread_move_from_open"), "sign")):
        if _missing(value):
            continue
        shown = (fmt.signed(value, "spread_current") if kind == "sign"
                 else fmt.number(value, "total_current"))
        moved = ("" if _missing(move)
                 else f"<td class='cfdb-market-move'>{MOVE_GLYPH} "
                      f"{fmt.signed(move, 'move')}</td>")
        lines.append(f"<tr><td class='cfdb-market-label'>{label}</td><td>{shown}</td>"
                     f"{moved or '<td></td>'}</tr>")
    return f"<table class='cfdb-market'>{''.join(lines)}</table>" if lines else ""


def _team_row(row, side: str, scope) -> str:
    """R-105 / R-107 / R-112, all three of which live on this one line of the card.

    R-105 — THE WRAPPER. `table.team_cell()` returns SEVERAL sibling spans (logo, rank badge,
    name), and `_team_with_record` appends a fourth. Interpolating that straight into
    `.cfdb-gamecard-row`, which was `display:flex; justify-content:space-between`, made every
    span its own flex item and distributed all of them across 1,400px. The `.4rem` margins
    were being applied and then overwhelmed. `.cfdb-teamcluster` gives the row exactly one
    child, which is what makes the margins mean what they say.

    R-107 — THE CARD APPLIES THE LINK ITSELF. `team_cell` does not build an anchor; in the
    dense table the href comes from the COLUMN's `link`, and a card has no column. Its own
    docstring records that `slug_field` "was accepted and ignored for weeks, which is why
    every team name on the site was inert text" — this is that same defect in a new surface,
    so the card supplies the anchor rather than expecting the cell to carry one.

    R-112 — WHICH SIDE IS HOME. Away-over-home is a convention the reader was expected to
    already hold, and at a neutral site it tells them something false: the card Marc sent
    stacks North Carolina over TCU at Aviva Stadium, Dublin. The home row is marked `@`
    ("North Carolina at TCU") and, at a neutral site, `vs` — which says there is no home side
    to read into the order. The away row carries the same span, empty, so the two names still
    start at the same x.
    """
    if side == "home":
        neutral = row.get("is_neutral_site")
        glyph = "vs" if neutral else "@"
        title = ("neutral site — neither team is at home" if neutral
                 else f"at {_text(row.get('home_team_display'))}")
        marker = f"<span class='cfdb-athome' title='{title}'>{glyph}</span>"
    else:
        marker = "<span class='cfdb-athome'></span>"
    cluster = _team_with_record(row, side)
    slug = row.get(f"{side}_team_slug")
    if not _missing(slug):
        href = scope.link("team", team=slug)
        cluster = f"<a class='cfdb-teamlink' href='{href}' target='_self'>{cluster}</a>"
    return (f"<div class='cfdb-gamecard-row'>"
            f"<span class='cfdb-teamcluster'>{marker}{cluster}</span></div>")


def _card(row, scope, geo: dict) -> str:
    """One game.

    NOTE ON LINKS: the card is a <div>, not an <a>. The dense view makes the whole row a
    link, but here the team names are already anchors and <a> cannot nest, so Matchup gets
    its own explicit affordance in the meta line — the same glyph, and the same reasoning,
    as `table.details_col`.
    """
    detail = (_score_block(row, geo) if row.get("is_completed")
              else _market_block(row))
    matchup = (f"<a href='{scope.link('matchup', game_id=row['game_id'])}' target='_self' "
               f"title='Open the matchup'><span class='cfdb-details'>"
               f"{table.DETAILS_GLYPH}</span></a>")
    meta = " · ".join(x for x in [
        _weather_cell(row),
        _text(row.get("network_abbreviation")),
        (f"{NEUTRAL_GLYPH} neutral site" if row.get("is_neutral_site") else ""),
        _text(row.get("venue_display")),
    ] if x)
    return (
        f"<div class='cfdb-gamecard'>"
        f"  <div class='cfdb-gamecard-top'>"
        # R-108. The card had no kickoff time at all.
        f"    <div class='cfdb-gamecard-time'>{fmt.clock(row.get('start_date_et'))}</div>"
        f"    <div class='cfdb-gamecard-teams'>"
        f"{_team_row(row, 'away', scope)}{_team_row(row, 'home', scope)}"
        f"    </div>"
        f"    <div class='cfdb-gamecard-detail'>{detail}</div>"
        f"  </div>"
        f"  <div class='cfdb-gamecard-meta'>{meta}{' · ' if meta else ''}{matchup}</div>"
        f"</div>")


def _stacked(df: pd.DataFrame, scope) -> None:
    """Away over home, details to the right. R-043.

    Built from the same frame as the dense view — no second query and no app-side join, which
    is the single-relation rule and also why the two views cannot disagree with each other.

    R-110: the cards go into a CSS grid, not `st.columns`. Streamlit renders server-side and
    cannot measure a viewport, so `st.columns(2)` would be a fixed two-up that keeps two
    cards side by side on a phone; `auto-fit` + `minmax` lets the browser reflow on its own,
    with no JavaScript and no custom component. Day groups still head their own section.
    """
    geo = _linescore_geometry(df)          # R-015: once for the page, not once per card.
    for day, rows in df.groupby(df["game_date"], sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{pd.Timestamp(day):%A %d %B %Y}</div>",
                    unsafe_allow_html=True)
        cards = "".join(_card(r, scope, geo) for _, r in rows.iterrows())
        st.markdown(f"<div class='cfdb-cardgrid'>{cards}</div>", unsafe_allow_html=True)


def body(page) -> None:
    scope = filters.game_scope()
    table.dataset_caption("Schedule", "srv_game")
    chips.spread_sign_note()
    with states.section("srv_game"):
        df = _rows(scope.season, scope.week, scope.season_type, scope.conference,
                   scope.division)
        table.as_of_caption(df)
        df = table.apply_sort(df, _columns(scope))

        # R-043. The tab is the URL, so a link to the stacked view lands on the stacked view.
        keys = list(VIEWS)
        current = params.get("view")
        chosen = st.radio("View", keys, horizontal=True,
                          format_func=lambda k: VIEWS[k],
                          index=keys.index(current) if current in keys else 0,
                          label_visibility="collapsed")
        params.set_params(view=chosen)
        _legend()

        states.render_or_state(
            df, "srv_game",
            "The week's games would be listed here.",
            f"No games match {scope.describe()}.",
            renderer=lambda d: (_stacked(d, scope) if chosen == "stacked"
                                else _dense(d, scope)),
            fix_label="Clear filters", fix=filters.clear)


def render() -> None:
    shell.render_page("schedule", body)
