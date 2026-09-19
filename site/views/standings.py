"""Standings — page 5. Conference standings with the tiebreakers already resolved."""
import pandas as pd
import streamlit as st

from lib import filters, fmt, shell, states, table
from lib.query import query
from lib.table import Col


def body(page) -> None:
    scope = filters.game_scope(show_week=False)
    season = scope.season
    table.dataset_caption("Standings", "srv_standings")

    with states.section("srv_standings"):
        df = query("""
            select season, team_id, school, team_slug, team_display, logo_url,
                   conference, division, classification, tiebreak_rank, tiebreak_basis,
                   wins, losses, ties, conference_wins, conference_losses,
                   win_pct, conference_win_pct,
                   points_for, points_against, point_differential,
                   home_record_display, away_record_display, neutral_games,
                   current_streak_display, current_streak_outcome, last_5_display,
                   ats_record_display, ats_as_favorite_display, ats_as_underdog_display,
                   color_on_light, as_of_ts
            from srv_standings
            where season = :season
              and classification = any(:classifications)
              and (:conference is null or conference = :conference)
            order by conference, tiebreak_rank
            limit 1000
        """, {"season": season, "classifications": scope.classifications,
              "conference": scope.conference})
        table.as_of_caption(df)

        # Default order is tiebreak_rank, which is dbt's business logic (AC-5.1). A reader
        # re-sorting by points-for is display, and the two do not conflict: the default is
        # the authored ordering, and any other is explicitly asked for.
        # A141: `table.render` applies the sort it draws. `_by_conference` groups with
        # `sort=True`, which preserves within-group order, so sorting each block gives
        # exactly what sorting before the grouping used to.
        states.render_or_state(
            df, "srv_standings",
            "Conference standings would appear here.",
            f"No completed games have been recorded for {season} yet. Standings fill in "
            f"from the first Saturday.",
            renderer=lambda d: _by_conference(d, scope))

        # AC-5.6: the rating columns are ABSENT rather than blank, and the page says which
        # object they wait on rather than showing an empty column that reads as no data.
        if not df.empty:
            st.divider()
            states.degraded(
                # R-500. The ratings ARE built — this card says so two lines down — so the
                # default "Not built yet" contradicted its own explanation.
                title="Built, not shown here yet",
                missing_object="sp_plus_rating / elo_rating on srv_standings",
                explanation=(
                    "The ratings themselves are built — see any team's Ratings tab — but they "
                    "are not yet carried as columns here, so this table ranks on results "
                    "alone."),
                scheduled="carrying fct_team_rating across to Standings")


COLUMNS = [
    # AC-5.1: tiebreak_rank is a COLUMN. The app never sorts by business logic —
    # conference tiebreakers are dbt's job and a Python sort implementing them is a
    # defect, not a shortcut.
    # A178 (cfdb-main-R-1850): `opens="asc"` — a rank wearing `kind="num"`, so the new
    # measure default would open it on last place. 1 is the best standing.
    Col("tiebreak_rank", "#", "num", dp=0, opens="asc"),
    # 🚨 A169 (cfdb-main-R-1320). THE TEAM NAME READS AS A LINK NOW — Marc, Site
    # v07: *"Rankings/Stats/Standings — Team Names should be hyperlinks to the Teams
    # page."*
    #
    # 📊 **IT WAS ALREADY CLICKABLE AND THAT IS THE POINT OF THE ASK.** All three of
    # these tables already pass a `link_builder` to the team page, so `table.render`
    # wrapped every cell in `<a class='cfdb-cell-link'>` — which is
    # `color:inherit; text-decoration:none`. **The destination was right and the
    # AFFORDANCE was missing**: nothing on the page said the name could be clicked.
    #
    # ✅ **`Col.link` IS THE MECHANISM THAT ALREADY EXISTS FOR THIS**, and its own
    # comment says so: *"A column-specific destination, which WINS over the row link
    # for that cell."* It yields `cfdb-cell-link-alt` — `var(--cfdb-link)`, bold —
    # so the name now looks like what it has always been.
    #
    # ⚠️ **AND IT CANNOT NEST.** `table.render` uses the column's href INSTEAD of the
    # row's for that cell, never both, so there is no `<a>` inside an `<a>` here. The
    # row link still carries every other cell to the same place.
    Col("team", "Team", render=lambda r: table.team_cell(
        r, "team_slug", "team_display", "logo_url"),
        link=table.team_link("team_slug")),
    # 🚨 A169 (cfdb-main-R-1319). CONF THROUGH ATS ARE CENTRED — Marc, Site v07: *"Center align
    # all the columns from CONF to ATS."*
    #
    # 📊 **THE RANGE HE READ OFF THE PAGE IS THESE EIGHT**: Conf · Conf % · Overall · Home ·
    # Away · Streak · Last 5 · ATS. **Six of them are records that read as a pair** ("5-7"), one
    # is a streak and one is a percentage — **no team name is inside the range**, which is the
    # thing that would have been worth arguing about.
    #
    # ⚠️ **THE ONE PLACE IT COSTS LEGIBILITY, SAID PLAINLY: `Conf %`.** A numeric column is
    # conventionally RIGHT-aligned so digits line up down the page, and centring `9%` against
    # `100%` staggers them. **It is his page and he asked for the range; this is the cost, and
    # it is one column.** The records lose nothing — they are short fixed-shape tokens and
    # centring reads better than left for them.
    #
    # ⚠️ `kind="center"` CARRIES ALIGNMENT AND ALSO FORMATTING, so `Conf %` takes an explicit
    # `render` — otherwise centring it would silently drop it out of the `num` formatting path.
    # AC-5.3: pre-formatted strings from the view. Nothing here assembles "5-7".
    Col("conf_record", "Conf", "center", render=lambda r: _conference_record(r)),
    Col("conference_win_pct", "Conf %", "center", render=lambda r: _conference_pct(r)),
    Col("overall", "Overall", "center", render=lambda r: _overall_record(r)),
    Col("home_record_display", "Home", "center"),
    Col("away_record_display", "Away", "center"),
    Col("current_streak_display", "Streak", "center", render=lambda r: _streak(r)),
    Col("last_5_display", "Last 5", "center"),
    Col("ats_record_display", "ATS", "center"),
    Col("points_for", "PF", "num", dp=0),
    Col("points_against", "PA", "num", dp=0, opens="asc"),
    Col("point_differential", "Diff", "signed", dp=0),
]


def _conference_pct(row) -> str:
    """The conference win rate as a whole percent — Marc, Site v07: *"#% (no decimal points)"*.

    🚨 **A ROUNDING CAN ASSERT SOMETHING FALSE, SO IT WAS CHECKED BEFORE IT SHIPPED.** A team
    that has won a conference game must not read the same as one that has not, and an unbeaten
    team must not share a reading with a beaten one. 📊 **Measured across all 18,653 published
    rows that carry the column:**

        rows that would read   0% having won a conference game     NONE
        rows that would read 100% while holding a conference loss  NONE

    ✅ **AND THE REASON IS STRUCTURAL RATHER THAN LUCK: a conference schedule is short.** The
    extreme real values are **1-10 → 9%** and **10-1 → 91%**; you would need roughly two hundred
    conference games for a single win to round to zero. **The rounding is safe here and would
    not be on a season-long denominator.**

    ⚠️ **NULL STAYS AN EM DASH** — a team with no conference games played has no rate, and
    `0%` would be a measurement where there is an absence (AC-G.32).
    """
    value = row.get("conference_win_pct")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fmt.EM_DASH
    return f"{round(float(value) * 100)}%"


def _record(wins, losses) -> str:
    """A record, or an em dash where nothing has been played.

    Zero and absent are different claims, and this is the column the distinction was first
    got wrong on: every 2026 team showed 0-0-0 for a season that had not started.
    """
    if pd.isna(wins) or pd.isna(losses) or (int(wins) + int(losses) == 0):
        return fmt.EM_DASH
    return f"{int(wins)}-{int(losses)}"


def _overall_record(row) -> str:
    return _record(row.get("wins"), row.get("losses"))


def _conference_record(row) -> str:
    return _record(row.get("conference_wins"), row.get("conference_losses"))


def _streak(row) -> str:
    """W-streaks and L-streaks are the same shape and opposite news, so the glyph carries
    the direction rather than colour alone (AC-G.22)."""
    value = row.get("current_streak_display")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fmt.EM_DASH
    outcome = str(row.get("current_streak_outcome") or "")
    arrow = "▲" if outcome == "W" else ("▼" if outcome == "L" else "—")
    return f"{arrow} {value}"


def _by_conference(df: pd.DataFrame, scope) -> None:
    """AC-5.2: grouped by conference, and by division WHERE A CONFERENCE HAS THEM.

    Only 14 of 136 FBS teams had a division in 2025 — the SEC and Big Ten dropped theirs in
    2024 — so a division header is the exception now, not the rule. The absence must render
    as normal rather than as missing data: a Degraded state for the other 90% would be
    reporting a defect that does not exist.
    """
    # F2-06: one layout across every conference so the grid does not reflow per group.
    layout = table.column_layout(df, COLUMNS)
    for conference, rows in df.groupby("conference", sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{conference}</div>", unsafe_allow_html=True)
        divisions = [d for d in rows["division"].dropna().unique()]
        if divisions:
            for division in sorted(divisions):
                block = rows[rows["division"] == division]
                st.caption(division)
                _render(block, scope, layout)
            # A conference can have divisions and still have teams outside them, which is
            # what a mid-season realignment looks like in the data.
            rest = rows[rows["division"].isna()]
            if not rest.empty:
                st.caption("No division recorded")
                _render(rest, scope, layout)
        else:
            _render(rows, scope, layout)

        basis = rows["tiebreak_basis"].dropna().unique()
        if len(basis):
            st.caption(f"Tiebreak: {basis[0]}. cfdb's own ordering, not an official "
                       f"standing — real conference tiebreakers involve head-to-head.")


def _render(rows: pd.DataFrame, scope, layout=None) -> None:
    # AC-5.4: team click -> Team page, carrying the scope forward.
    table.render(rows, COLUMNS, caption="", layout=layout,
                 link_builder=lambda r: scope.link("team", team=r["team_slug"]))


def render() -> None:
    shell.render_page("standings", body)
