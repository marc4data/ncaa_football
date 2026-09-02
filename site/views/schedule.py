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

from lib import chips, filters, params, shell, states, table
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


def _rows(season: int, week, season_type: str, conference,
          division: str = 'fbs') -> pd.DataFrame:
    sql = """
        select game_id, season, week, season_type, start_date_et, game_date,
               home_team_slug, home_team_display, home_abbreviation, home_logo_url,
               home_conference, home_points, home_rank, home_team_record_display,
               away_team_slug, away_team_display, away_abbreviation, away_logo_url,
               away_conference, away_points, away_rank, away_team_record_display,
               venue_display, network, network_abbreviation, is_neutral_site,
               is_conference_game, is_completed, winner,
               spread_current, total_current, predicted_margin, home_win_probability,
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
        order by start_date_et, game_id
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


def _team_name(row, side: str) -> str:
    """Display name, abbreviated past the threshold. R-085."""
    name = _text(row.get(f"{side}_team_display")) or "—"
    if len(name) > TEAM_NAME_MAX:
        # An abbreviation can be null for a team absent from /teams, so fall back to a
        # truncation rather than to NaN.
        return _text(row.get(f"{side}_abbreviation")) or name[:TEAM_NAME_MAX]
    return name


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
    if record is None or (isinstance(record, float) and pd.isna(record)):
        return base
    return f"{base}<span class='cfdb-team-record'>{record}</span>"


def _winner_cell(row) -> str:
    """R-029. Who won, without the reader subtracting two numbers.

    `winner` is computed in dbt and carries the team NAME; the chip shows the abbreviated
    form so the column stays narrow. Pending is distinct from a tie: an unplayed game has no
    winner yet, and a tie has no winner at all — collapsing those into one grey box is the
    mistake cover_chip_html already refuses to make.
    """
    if not row.get("is_completed"):
        return chips.chip_html("w", "—", "not yet played")
    winner = row.get("winner")
    if winner is None or (isinstance(winner, float) and pd.isna(winner)):
        return chips.chip_html("w", "Tie", "the game ended level")
    side = "home" if winner == row.get("home_team_display") else "away"
    return chips.chip_html("y", _team_name(row, side), f"{winner} won")


def _weather_cell(row) -> str:
    """R-027. Icon plus temperature — EXCEPT indoors, where there is no temperature to give.

    CFBD reports the weather at the venue's LOCATION, not inside it, so a domed game carries
    ordinary outdoor readings. Rendering "94°F" beside a game played under a roof is a true
    number answering the wrong question, so the dome glyph stands alone.
    """
    if row.get("is_indoors"):
        return f"<span class='cfdb-wx' title='indoor venue'>{DOME_GLYPH}</span>"
    temp = row.get("temperature_f")
    if temp is None or pd.isna(temp):
        return ""
    code = row.get("weather_condition_code")
    glyph = WEATHER_GLYPH.get(int(code)) if code is not None and not pd.isna(code) else None
    label = row.get("weather_condition") or "conditions not recorded"
    return (f"<span class='cfdb-wx' title='{label}'>"
            f"{glyph or ''} {float(temp):.0f}°F</span>")


def _columns(scope) -> list:
    return [
        # AC-2.5: the row goes to the game, the team NAME goes to the team.
        Col("start_date_et", "Kickoff", "time"),
        Col("away", "Away", render=lambda r: _team_with_record(r, "away"),
            link=lambda r: scope.link("team", team=r.get("away_team_slug"))),
        Col("away_points", "", "num", dp=0),
        Col("home", "Home", render=lambda r: _team_with_record(r, "home"),
            link=lambda r: scope.link("team", team=r.get("home_team_slug"))),
        Col("home_points", "", "num", dp=0),
        # R-029.
        Col("winner", "Won", render=_winner_cell),
        Col("spread_current", "Spread", "signed"),
        # R-087. O/U, reconciled with Odds Board so one field has one name site-wide.
        Col("total_current", "O/U", "num"),
        # R-086. RENAMED RATHER THAN WRAPPED. A two-line header raises the height of every
        # column header for one column's benefit, and "Pred" is already the site's shorthand
        # for a model number — the sign note directly above the table explains the sign.
        Col("predicted_margin", "Pred", "signed"),
        # R-027.
        Col("weather", "Wx", render=_weather_cell),
        Col("network_abbreviation", "TV"),
        # R-026. ICON ALONE, NO TEXT LABEL AND NO HEADER WORD.
        #
        # A DELIBERATE EXCEPTION to the site's glyph+label convention, decided by Marc
        # against a small known user base and logged in the decision log with its reason.
        # It is not an oversight and it is not to be "fixed" back to glyph+label.
        Col("is_neutral_site", "",
            render=lambda r: ("<span title='neutral site'>◇</span>"
                              if r.get("is_neutral_site") else "")),
        table.details_col(lambda r: scope.link("matchup", game_id=r["game_id"])),
    ]


# --- the two views --------------------------------------------------------------------

def _dense(df: pd.DataFrame, scope) -> None:
    """AC-2.2: grouped by day, kickoff order within a day, with day headers."""
    layout = table.column_layout(df, _columns(scope))
    for day, rows in df.groupby(df["game_date"], sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{pd.Timestamp(day):%A %d %B %Y}</div>",
                    unsafe_allow_html=True)
        table.render(rows, _columns(scope), caption="", layout=layout,
                     link_builder=lambda r: scope.link("matchup", game_id=r["game_id"]))


def _line_score(row, side: str) -> str:
    """Quarter-by-quarter for one side, or nothing.

    Line scores exist from 2001 and are absent on 60% of rows — CFBD sends an empty array for
    most of history. An empty cell is the honest rendering; a row of zeros would claim a
    shutout in four quarters.
    """
    periods = row.get(f"{side}_periods")
    if periods is None or pd.isna(periods):
        return ""
    cells = []
    for q in (1, 2, 3, 4):
        v = row.get(f"{side}_q{q}")
        cells.append(f"<td>{'' if v is None or pd.isna(v) else int(v)}</td>")
    overtime = row.get(f"{side}_overtime_points")
    if periods and int(periods) > 4:
        cells.append(f"<td class='cfdb-ls-ot'>"
                     f"{0 if overtime is None or pd.isna(overtime) else int(overtime)}</td>")
    return "".join(cells)


def _stacked(df: pd.DataFrame, scope) -> None:
    """Away over home, details to the right. R-043.

    Built from the same frame as the dense view — no second query and no app-side join, which
    is the single-relation rule and also why the two views cannot disagree with each other.
    """
    for day, rows in df.groupby(df["game_date"], sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{pd.Timestamp(day):%A %d %B %Y}</div>",
                    unsafe_allow_html=True)
        for _, r in rows.iterrows():
            ot = r.get("home_periods") is not None and not pd.isna(r.get("home_periods")) \
                and int(r.get("home_periods") or 0) > 4
            header = "".join(f"<th>{q}</th>" for q in ("1", "2", "3", "4")) + \
                     ("<th>OT</th>" if ot else "")
            away_ls, home_ls = _line_score(r, "away"), _line_score(r, "home")
            if away_ls:
                score_block = (
                    f"<table class='cfdb-linescore'><tr><th></th>{header}</tr>"
                    f"<tr><td class='cfdb-ls-team'>{_team_name(r, 'away')}</td>{away_ls}</tr>"
                    f"<tr><td class='cfdb-ls-team'>{_team_name(r, 'home')}</td>{home_ls}</tr>"
                    f"</table>")
            else:
                # R-092. ABSENT, NOT ZERO — and the card says WHICH.
                #
                # Only 44,775 of 110,879 games carry quarters: 64,254 hold an empty array and
                # 1,850 hold JSON null, and the earliest is 2001. Modern seasons are
                # effectively complete (3,805 of 3,831 in 2025), so the gap is historical.
                #
                # A row of zeros would claim four scoreless quarters, which is the
                # null-not-zero rule this project has fixed three times elsewhere. Omitting
                # the block silently would be honest about the value and silent about the
                # reason, which leaves a reader wondering whether the page is broken.
                season = r.get("season")
                why = ("Quarter scores are not recorded before 2001."
                       if season is not None and not pd.isna(season) and int(season) < 2001
                       else "No quarter scores recorded for this game.")
                score_block = (f"<table class='cfdb-linescore'><tr><th></th>{header}</tr>"
                               f"<tr><td class='cfdb-ls-team'>"
                               f"{_team_name(r, 'away')}</td><td>—</td><td>—</td>"
                               f"<td>—</td><td>—</td></tr>"
                               f"<tr><td class='cfdb-ls-team'>"
                               f"{_team_name(r, 'home')}</td><td>—</td><td>—</td>"
                               f"<td>—</td><td>—</td></tr></table>"
                               f"<div class='cfdb-ls-why'>{why}</div>")
            detail = " · ".join(x for x in [
                _weather_cell(r),
                _text(r.get("network_abbreviation")),
                ("◇ neutral site" if r.get("is_neutral_site") else ""),
                _text(r.get("venue_display")),
            ] if x)
            st.markdown(
                f"<div class='cfdb-gamecard'>"
                f"  <div class='cfdb-gamecard-teams'>"
                f"    <div class='cfdb-gamecard-row'>{_team_with_record(r, 'away')}"
                f"      <span class='cfdb-gamecard-pts'>"
                f"{'' if pd.isna(r.get('away_points')) else int(r['away_points'])}</span></div>"
                f"    <div class='cfdb-gamecard-row'>{_team_with_record(r, 'home')}"
                f"      <span class='cfdb-gamecard-pts'>"
                f"{'' if pd.isna(r.get('home_points')) else int(r['home_points'])}</span></div>"
                f"  </div>"
                f"  <div class='cfdb-gamecard-detail'>{score_block}"
                f"    <div class='cfdb-gamecard-meta'>{detail}</div></div>"
                f"</div>", unsafe_allow_html=True)


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

        states.render_or_state(
            df, "srv_game",
            "The week's games would be listed here.",
            f"No games match {scope.describe()}.",
            renderer=lambda d: (_stacked(d, scope) if chosen == "stacked"
                                else _dense(d, scope)),
            fix_label="Clear filters", fix=filters.clear)


def render() -> None:
    shell.render_page("schedule", body)
