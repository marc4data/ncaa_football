"""Team page — page 8. One team, tabs, everything cfdb knows this season.

AC-8.2 is the criterion this page proves: a blocked TAB does not block the PAGE. Overview
and Schedule render fully; Ratings, Roster and Trends name what they wait on. The pattern
was written for Roster and now earns its keep three times.
"""
import streamlit as st

import pandas as pd

from lib import fmt, identity, params, shell, states, table
from lib.query import query
from lib.table import Col


# ── THE UNIT SPLIT, AS DATA (A172, cfdb-main-R-1650) ──────────────────────────────────────
#
# > **MARC, v07:** *"Roster — table format Columns, split by offense, defense, special teams —
# > Number, Name, Position, Ht, Wt, Class, Hometown"*
#
# 🚨 THERE IS NO UNIT COLUMN. `position` is the only thing `srv_team_roster` publishes, so the
# split is a VOCABULARY decision rather than a lookup — Marc approved this map
# (cfdb-main-R-1421) and it lives here, once, as a literal.
#
# 🚨 ENUMERATED, NOT MATCHED — B136's rule. A `startswith` would sort `DB` and `DL` correctly
# today by luck and break on the first new abbreviation; a substring test on `S` would swallow
# every position containing the letter. **The map is data and the grouping is driven from it.**
ROSTER_UNITS = (
    ("Offense",       ("OL", "WR", "RB", "TE", "QB", "OT", "G", "C", "FB")),
    ("Defense",       ("LB", "DL", "DB", "S", "CB", "DE", "DT", "EDGE", "NT")),
    ("Special teams", ("PK", "LS", "P")),
)
UNLISTED_UNIT = "Unlisted"

_UNIT_BY_POSITION = {position: unit for unit, positions in ROSTER_UNITS
                     for position in positions}


def roster_unit(position) -> str:
    """Which section a roster row belongs in. Total — every row lands somewhere.

    🚨 TWO DIFFERENT ABSENCES ARE DELIBERATELY MERGED HERE, AND THE MERGE IS STATED RATHER THAN
    SILENT (AC-G.11). A NULL position is *cfdb holds no position field for this player*; the
    literal string `?` is *the source published that it does not know*. **The distinction is the
    SOURCE's, not the reader's** — a roster does not become more useful for splitting "unknown"
    into two headings — so both read `Unlisted`.

    🚨 AND AN UNMAPPED VALUE MUST NOT VANISH. `EDGE` and `NT` were added by the source after
    this map was first written; the next one will be too. An unknown abbreviation lands in
    `Unlisted`, where it shows up as a NUMBER a reader can see, rather than being filtered out
    of every section and disappearing from the roster entirely — which is cfdb-wta-R-1192's
    defect, and is why this is a PARTITION rather than four filters.

    📊 MEASURED ON LIVE PUBLISHED SERVING, all 83,985 rows: Offense 38,286 · Defense 36,841 ·
    Special teams 4,995 · Unlisted 3,863 (4.60%). The four sum to the total exactly.
    ⚠️ Live carries two values the sample analysis did not — `ATH` (5 rows) and `KR` (1) — and
    both currently land in `Unlisted`. `KR` is plainly a special-teams position; extending the
    map is a football judgement and therefore Marc's, so A172 reported it rather than taking it.
    """
    if position is None or (isinstance(position, float) and pd.isna(position)):
        return UNLISTED_UNIT
    return _UNIT_BY_POSITION.get(str(position).strip(), UNLISTED_UNIT)


def body(page) -> None:
    seasons = query("select distinct season from srv_team_overview order by season desc limit 200")
    options = seasons["season"].tolist()
    season = params.get("season") or (options[0] if options else None)
    teams = query("""select team_slug, team_display from srv_team_overview
                     where season = :season order by team_display limit 1200""",
                  {"season": season})
    if teams.empty:
        states.empty("A team profile would be here.", f"No teams for season {season}.")
        return

    slugs = teams["team_slug"].tolist()
    current = params.get("team")
    # The URL may carry a display name from an older link; resolve it rather than 404.
    if current not in slugs:
        match = teams[teams["team_display"].str.lower() == str(current).lower()]
        current = match["team_slug"].iloc[0] if not match.empty else slugs[0]

    with st.sidebar:
        season = st.selectbox("Season", options,
                              index=options.index(season) if season in options else 0)
        label = st.selectbox("Team", teams["team_display"].tolist(),
                             index=slugs.index(current) if current in slugs else 0)
    current = teams[teams["team_display"] == label]["team_slug"].iloc[0]
    params.set_params(season=season, team=current)

    overview = query("""
        select season, team_slug, team_display, mascot, conference, division,
               classification, logo_url, color_on_light, color_on_dark, color_source,
               wins, losses, record_display, conference_record_display, conference_standing,
               ats_record_display, ats_as_favorite_display, ats_as_underdog_display,
               games_played, points_for, points_against, yards_for, yards_allowed,
               turnover_margin, games_with_box_score, as_of_ts
        from srv_team_overview
        where season = :season and team_slug = :team
        limit 1
    """, {"season": season, "team": current})

    if overview.empty:
        states.empty("This team's profile would be here.",
                     f"No record for {label} in {season}.")
        return

    row = overview.iloc[0]
    _identity_header(row)
    table.as_of_caption(overview)

    tabs = st.tabs(["Overview", "Schedule", "Ratings", "Roster", "Trends"])
    with tabs[0]:
        _overview(row)
    with tabs[1]:
        _schedule_tab(season, row.get("team_slug"), row.get("team_display"))
    with tabs[2]:
        _ratings(season, row.get("team_display"))
    with tabs[3]:
        # 🚨 A172 (cfdb-main-R-1654). THE ROSTER TAB SAID "NOT BUILT YET" WHILE THE ROSTER WAS
        # RENDERING ONE TAB TO THE LEFT, UNDER THE GAME LOG.
        #
        # 📊 Measured on the live page before this round touched it: `tabs[3]` drew
        # `states.degraded("dim_athlete", "Rosters need the athlete dimension and the player
        # facts.")` — and `_roster` was called from `tabs[1]`, where it drew 119 players for
        # Ohio State 2026. **A reader who clicked the tab named Roster was told the feature did
        # not exist; the feature was two inches lower on a different tab.**
        #
        # ⚠️ AND THE FILE ALREADY KNEW: eight lines below, the Trends tab carries *"a site that
        # explains why it cannot do something it CAN now do teaches the reader to stop looking,
        # which is a worse failure than saying nothing."* Written for Elo on 2026-09-02, true of
        # the Roster tab ever since. **A comment recording a trap does not prevent the trap
        # (R-768); only rendering the page and reading it does.**
        #
        # ✅ The degraded card is GONE rather than reworded — the thing it waits on has arrived.
        _roster(season, row.get("team_slug"))
    with tabs[4]:
        # THE DATA EXISTS NOW. This tab said, until 2026-09-02, that Elo "has only been
        # fetched by season" and that a weekly series needed a backfill. Both statements
        # were true when written and are false today, by our own work — and a site that
        # explains why it cannot do something it CAN now do teaches the reader to stop
        # looking, which is a worse failure than saying nothing.
        #
        # What changed: /games has carried home_pregame_elo, home_postgame_elo and their
        # away counterparts all along. A rating per team per GAME is a rating per team per
        # WEEK, so fct_team_rating_week needed no API call at all. Coverage, FBS-only:
        # 100% for 2023-2025, 99.9% for 2022, 93-97% back to 2014.
        #
        # STILL DEGRADED, BUT FOR A DIFFERENT AND SMALLER REASON: the chart is not built.
        # That is a page to design, not a blocker to clear, and designing it here would be
        # designing a page nobody has reviewed.
        states.degraded(
            # R-500. "The data for this is now in the warehouse" — so it is built, and the
            # default title said the opposite of the sentence beneath it.
            title="Built, not shown here yet",
            missing_object="weekly rating history",
            explanation=(
                "The data for this is now in the warehouse: fct_team_rating_week carries a "
                "pregame and postgame Elo per team per week, covering every FBS team from "
                "2014 and essentially all of them from 2022. What is missing is the chart "
                "itself, not the ratings behind it."),
            scheduled="the Trends chart, once the Team page is reviewed")


def _identity_header(row) -> None:
    """AC-8.6: the colour band uses the contrast-safe text colour from dim_team.
    The app computes no contrast — it reads what dbt already solved."""
    logo = identity.logo_or_monogram(row.get("logo_url"), row.get("team_display"), 44)
    text_colour = identity.text_on(row)
    st.markdown(
        f"<div style='{identity.accent_style(row)};display:flex;align-items:center;"
        f"gap:.7rem;margin:.3rem 0 1rem'>{logo}"
        f"<div><div style='font-size:1.35rem;font-weight:600;color:{text_colour}'>"
        f"{row.get('team_display')}</div>"
        f"<div style='opacity:.7;font-size:.88rem'>{row.get('mascot') or ''} · "
        f"{row.get('conference') or 'Independent'}</div></div></div>",
        unsafe_allow_html=True)


def _kpi_banner(row) -> None:
    """R-002. Season totals across the top of Overview.

    Marc marked this M! in the first feedback pass and it went three rounds without being
    scheduled — the most overdue item in the register.

    AC-G.33 governs every figure here, and this is the highest-visibility surface on the
    site so it is the worst place to get composition wrong. We have shipped that defect
    once: an ATS percentage rendered beside n=567 when it was computed over 553. Every
    component correct, the assembly lying. So each yardage figure carries the number of
    games its box scores actually came from, which is NOT games_played — box scores are
    `recent` scope and a 2025 team has them for about half its season.

    A team-season with nothing played renders em dashes, not zeros. Same rule as R-005.
    """
    box = row.get("games_with_box_score")
    box_n = int(box) if box is not None and not pd.isna(box) else 0

    cells = st.columns(5)
    cells[0].metric("Points for", fmt.number(row.get("points_for"), "", 0))
    cells[1].metric("Points against", fmt.number(row.get("points_against"), "", 0))
    cells[2].metric("Total yards", fmt.number(row.get("yards_for"), "", 0))
    cells[3].metric("Yards allowed", fmt.number(row.get("yards_allowed"), "", 0))
    cells[4].metric("Turnover margin", fmt.signed(row.get("turnover_margin"), "", 0))

    if box_n == 0:
        st.caption(
            "Points are complete for every game. **Yardage and turnovers are not shown: no "
            "box score has been recorded for this team-season.** CFBD publishes game "
            "statistics from 2024 onward.")
    elif box_n < int(row.get("games_played") or 0):
        st.caption(
            f"Points cover all {int(row.get('games_played') or 0)} games. **Yardage and "
            f"turnovers cover {box_n} of them** — box scores are only published for some "
            f"games, so these totals are not a full season.")
    else:
        st.caption(f"All figures over {box_n} games.")


def _overview(row) -> None:
    _kpi_banner(row)
    st.divider()
    cols = st.columns(4)
    # AC-5.3 / AC-G.2: records are pre-formatted strings from the view, never assembled here.
    cols[0].metric("Record", row.get("record_display") or "—")
    cols[1].metric("Conference", row.get("conference_record_display") or "—")
    cols[2].metric("Conf. standing", int(row["conference_standing"])
                   if row.get("conference_standing") == row.get("conference_standing")
                   and row.get("conference_standing") is not None else "—")
    cols[3].metric("ATS", row.get("ats_record_display") or "—")
    st.caption(f"ATS as favorite {row.get('ats_as_favorite_display') or '—'} · "
               f"as underdog {row.get('ats_as_underdog_display') or '—'}")


def _ratings(season, team_display) -> None:
    """B1. Five rating systems, with projections marked as projections.

    The distinction is the whole reason this tab is not just five numbers: in weeks 1 to 4
    the only ratings that exist are SP+ and FPI, and both are FORECASTS. Elo, SRS and PPA
    are computed from results and have nothing to compute from. Rendering all five in the
    same styling would imply a preseason projection and a measured rating are the same kind
    of claim, which is the defect the backtest warning on Model Performance exists to
    prevent, one page over.
    """
    with states.section("srv_team_rating"):
        df = query("""
            select rating_system, rating_system_display, display_order,
                   rating, rating_rank, rating_rank_computed, rating_percentile,
                   rating_population,
                   offense_rating, defense_rating, special_teams_rating,
                   strength_of_schedule, second_order_wins,
                   rating_scope, is_projection, completed_games_at_rating,
                   rating_basis_note, as_of_ts
            from srv_team_rating
            where season = :season and school = :team_display
            order by display_order
            limit 20
        """, {"season": season, "team_display": team_display})

        if df.empty:
            states.empty(
                "Team ratings would be here.",
                f"No rating system has published a figure for this team in {season}.")
            return

        if df["is_projection"].any():
            st.info(
                "**These are preseason projections, not measurements.** No game has been "
                "played yet, so SP+ and FPI are forecasting the season rather than "
                "describing it. Elo, SRS and PPA are computed from results and appear once "
                "games are played.")

        table.render(df, [
            Col("rating_system_display", "System"),
            Col("rating", "Rating", "num"),
            Col("rank", "Rank", render=_rating_rank),
            Col("rating_percentile", "Percentile", render=_percentile),
            Col("offense_rating", "Offense", "num"),
            Col("defense_rating", "Defense", "num"),
            Col("basis", "Basis", render=lambda r: "Projection" if r.get("is_projection")
                else f"{int(r.get('completed_games_at_rating') or 0)} games"),
        ], caption="srv_team_rating")
        table.as_of_caption(df)

        notes = df["rating_basis_note"].dropna().unique()
        for note in notes:
            st.caption(str(note))


def _rating_rank(row) -> str:
    """CFBD's own rank where it publishes one, ours otherwise, and the difference is said
    rather than hidden — Elo and PPA publish no ranking, so those are cfdb's ordering."""
    published = row.get("rating_rank")
    if published is not None and not pd.isna(published):
        return f"{int(published)}"
    computed = row.get("rating_rank_computed")
    if computed is None or pd.isna(computed):
        return fmt.EM_DASH
    return f"{int(computed)}*"


def _percentile(row) -> str:
    """AC-G.33: the percentile carries the population it was computed against.

    That population MOVES. SP+ covers 139 teams today and Elo covers none; when Elo appears
    mid-season it may cover a different set again. "82nd percentile" means something
    different over 139 teams than over 265, and only the n makes that legible.
    """
    value = row.get("rating_percentile")
    if value is None or pd.isna(value):
        return fmt.EM_DASH
    population = row.get("rating_population")
    suffix = (f" of {int(population)}"
              if population is not None and not pd.isna(population) else "")
    return f"{float(value) * 100:.0f}%{suffix}"


# 🚨 A174 (cfdb-main-R-1705). TWO SECTIONS, TWO RELATIONS, AND THE RELATIONS FOLLOW THE LAYOUTS
# MARC NAMED RATHER THAN THE OTHER WAY ROUND.
#
# > **MARC, v07:** *"Schedule tab — Layout from Scores/Schedule page, but 2 continuous sections.
# > Completed games use Score layout. Future games use Schedule layout"*
#
# 📊 THE GATING MEASUREMENT, against `information_schema` on live published serving, because the
# tab this replaced read a THIRD relation and no layout's inputs are all in one place:
#
#     srv_team_game_log   42 cols   the score half only — NO upset/cover/over, NO spread,
#                                   NO opponent slug, logo or rank, NO is_home
#     srv_game_team      242 cols   the Scores page's own view. Score half + opponent identity
#                                   + ranks + is_home. ✅ COMPLETE for the completed section
#     srv_game           184 cols   the Schedule page's own view. Both sides' identity, every
#                                   spread, `over_under`, venue. ✅ COMPLETE for the upcoming one
#
# ✅ SO EACH SECTION READS THE RELATION ITS OWN SOURCE PAGE READS. That is one relation per
# query (G-2) and no join — two SECTIONS are two tables, not one table stitched from two reads.
# ⚠️ AND `srv_team_game_log` IS NOT THE POORER CHOICE BY ACCIDENT: it is a BOX-SCORE log, and
# its 42 columns are yardage and turnovers this tab does not show. Nothing here regresses; the
# view keeps its own job.
#
# 🚨 THE TOTAL IS `over_under`, NOT `over_under_close`. The first sweep looked for the latter and
# reported it missing from all three relations, which would have been a finding about a column
# that does not exist under that name.

def _schedule_tab(season, team_slug, team_display) -> None:
    """Completed games above, upcoming below — one scroll, no tabs, no expander.

    🚨 EACH SECTION'S ABSENCE IS ITS OWN (AC-G.11), AND THE THREE SHAPES ARE REAL:
    a team before week 1 has **no completed section**, not an empty one; a team whose season
    has ended has **no upcoming section**; a bowl-bound team in December has both. **A heading
    over nothing says neither**, which is B103's ruling and A172's `Unlisted` rule one tab over.

    ⚠️ NO MARK ON THIS TAB NEEDS A LEGEND, AND THAT IS A DECISION (R-178). The Scores layout
    draws none — `srv_game_team` does not publish `upset_level`, `winner_covered_close` or
    `over_met`, which is why the Scores PAGE has no result strip either. The upcoming section
    shows `@`/`vs`, which is text a reader already knows rather than a glyph needing a key.
    ✅ **So the Team page gains no legend**: the alternative was importing Today's, and a legend
    explaining marks this tab cannot draw is the defect R-178 forbids in the other direction.
    """
    st.subheader(fmt.title_case("Schedule"))

    # 🚨 A174 (cfdb-main-R-1708). BOTH FRAMES ARE BOUND BEFORE EITHER SECTION RUNS, AND THE
    # CALIBRATION RENDER IS WHAT FOUND WHY. `states.section` CATCHES a raise and draws a card,
    # so when the completed query failed, `played` was never assigned — and the second
    # section's own `played.empty` check then raised `UnboundLocalError` and drew a SECOND
    # card. **One section's failure was corrupting the other**, which is AC-8.2's rule — *a
    # blocked TAB does not block the PAGE* — at section grain.
    #
    # ⚠️ IT WOULD NEVER APPEAR IN A HEALTHY RENDER, which is exactly why §6.1's calibration
    # step exists: it broke the first query on purpose and the cascade showed up as 2 error
    # cards where 1 was expected.
    played = upcoming = pd.DataFrame()

    with states.section("srv_game_team"):
        played = query("""
            select week, game_id, game_date, opponent, opponent_team_slug,
                   opponent_logo_url, opponent_rank, opponent_conference,
                   is_home, is_neutral_site, result, points_for, points_against, margin,
                   is_completed, as_of_ts
            from srv_game_team
            where season = :season and team_slug = :team_slug and is_completed
            order by game_date, week
            limit 60
        """, {"season": season, "team_slug": team_slug})
        if not played.empty:
            st.markdown(f"<h4 class='cfdb-roster-unit'>"
                        f"{fmt.title_case('Completed')}</h4>",
                        unsafe_allow_html=True)
            table.as_of_caption(played)
            table.render(played, [
                Col("week", "Wk", "num", dp=0),
                Col("game_date", "Date", "date"),
                # "@ Opponent" rather than an H/A column — the convention in every printed
                # schedule, and it saves a column. ⚠️ A174 REPLACED `_opponent`, which read the
                # game log's `venue_role`; `srv_game_team` spells the same fact `is_home`, and
                # the old helper had no other caller so it went rather than becoming dead code.
                Col("opponent", "Opponent", render=_opponent_cell),
                Col("result", "Result"),
                # The labels are the Scores page's own, taken from `workbook.SCORES_COLUMNS`
                # — the ONE declaration that page and its sheet both read (AC-15.8). A third
                # spelling of "Pts for" is exactly R-177's drift.
                Col("points_for", "Pts for", "num", dp=0),
                Col("points_against", "Pts against", "num", dp=0, opens="asc"),
                # AC-8.3: oriented to the SUBJECT team, not to home.
                Col("margin", "Margin", "signed", dp=0),
            ], caption="",
                link_builder=lambda r: params.link("matchup", game_id=r["game_id"],
                                                   season=season))

    with states.section("srv_game"):
        upcoming = query("""
            select week, game_id, start_date, venue, is_neutral_site,
                   home_team_slug, away_team_slug, home_team_display, away_team_display,
                   home_rank, away_rank, spread_at_close, spread_current, over_under,
                   network_abbreviation, is_completed, as_of_ts
            from srv_game
            where season = :season and not is_completed
              and (home_team_slug = :team_slug or away_team_slug = :team_slug)
            order by start_date, week
            limit 60
        """, {"season": season, "team_slug": team_slug})
        if not upcoming.empty:
            st.markdown(f"<h4 class='cfdb-roster-unit'>"
                        f"{fmt.title_case('Upcoming')}</h4>",
                        unsafe_allow_html=True)
            table.as_of_caption(upcoming)
            table.render(upcoming, [
                Col("week", "Wk", "num", dp=0),
                Col("start_date", "Date", "date"),
                Col("home_team_slug", "Opponent",
                    render=lambda r: _upcoming_opponent(r, team_slug)),
                # The market, as the Schedule page words it. A spread is the HOME side's
                # number on both pages; it is not re-oriented here, and the column says so
                # rather than a reader having to know.
                Col("spread_at_close", "Spread (home)", "signed", dp=1),
                Col("over_under", "Total", "num", dp=1),
                Col("network_abbreviation", "TV"),
            ], caption="",
                link_builder=lambda r: params.link("matchup", game_id=r["game_id"],
                                                   season=season))

        # 🚨 BOTH EMPTY IS THE ONLY STATE THAT NEEDS A CARD, and it is a different sentence
        # from either section being absent. A team with games played and none left is not
        # missing anything.
        if played.empty and upcoming.empty:
            states.empty(
                "This team's schedule would be here.",
                f"No games recorded for {team_display} in {season}.")


def _opponent_cell(row) -> str:
    """"@ Opponent" for a road game, "Opponent" at home, "vs Opponent" on a neutral field.

    ⚠️ A174: the job the deleted `_opponent` did off the game log's `venue_role`, reading
    `srv_game_team`'s `is_home` instead. Two helpers rather than one that guesses which column
    it was handed — that indirection is what has beaten a guard twice in this project.
    """
    name = row.get("opponent")
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return fmt.EM_DASH
    if row.get("is_neutral_site"):
        return f"vs {name}"
    return str(name) if row.get("is_home") else f"@ {name}"


def _upcoming_opponent(row, team_slug) -> str:
    """The other side of a scheduled game, from `srv_game`'s two-sided row.

    ⚠️ THIS IS A SELECTION, NOT A COMPUTATION. It picks one of two PUBLISHED columns using a
    published key — the same shape the opponent cell has always had — rather than deriving a
    quantity, so §4.2.1 is not engaged. **A team-perspective NUMBER would be a different
    matter and is why `srv_game_team` exists**; this section shows no such number.
    """
    at_home = row.get("home_team_slug") == team_slug
    name = row.get("away_team_display") if at_home else row.get("home_team_display")
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return fmt.EM_DASH
    if row.get("is_neutral_site"):
        return f"vs {name}"
    return str(name) if at_home else f"@ {name}"


# Marc's column order, verbatim: "Number, Name, Position, Ht, Wt, Class, Hometown".
#
# 🚨 THE HEIGHT COLUMN SORTS ON A DIFFERENT FIELD FROM THE ONE IT SHOWS, AND THAT IS THE WHOLE
# REASON IT IS WRITTEN THIS WAY. `height_display` is a STRING like `6-3`, so a column sorting on
# it puts `6-10` before `6-3` — lexical order on a number that is not one. `table.render` sorts
# on the Col's own `field`, so the field is `height_inches` (an integer) and `render` draws
# `height_display`. ⚠️ The next reader will otherwise assume the two are the same column.
ROSTER_COLUMNS = [
    # A178 (cfdb-main-R-1851): `opens="asc"` — a jersey is an IDENTIFIER wearing
    # `kind="num"`. There is no "best" #99, and opening on one would be a
    # roster sorted from the back.
    Col("jersey", "#", "num", dp=0, opens="asc"),
    Col("full_name", "Name"),
    Col("position", "Pos"),
    Col("height_inches", "Ht",
        render=lambda r: fmt.EM_DASH if r.get("height_display") is None
        or (isinstance(r.get("height_display"), float) and pd.isna(r.get("height_display")))
        else str(r.get("height_display"))),
    Col("weight_pounds", "Wt", "num", dp=0),
    Col("class_year_display", "Class"),
    Col("hometown_display", "Hometown"),
]


def _roster(season, team_slug) -> None:
    """The roster, from srv_team_roster, split into units (A172, cfdb-main-R-1650).

    Rosters are `recent` scope — 2024 onward — so a 2019 team page has none. The Empty state
    says which, because "no roster recorded" and "we do not collect rosters for that season"
    are different statements and only one of them is true here.

    🚨 FOUR SECTIONS, AND `Unlisted` APPEARS ONLY IF IT HAS ROWS. An empty `Unlisted` heading on
    a fully-listed roster is a hole reserved for something that does not exist — B103's ruling
    on the omitted first name, and AC-G.11's rule that an absence must say which absence it is.
    A heading with nothing under it says neither.

    ⚠️ THE PLAYER NAME IS NOT A LINK, AND THE REASON IS NOT THE ONE THE PROMPT GAVE.
    A172's prompt said to drop it because *"there is no player page"* — **there is**, and this
    function used to link to it: `players.py:81` reads `params.get("player")` and queries
    `srv_player_stats` by `player_slug`. 📊 **The real reason is coverage, measured on live
    serving: only 38.89% of 2026 roster players have a row in `srv_player_stats`** (2025 45.38%,
    2024 56.84%). **So for the current season three names in five led to a page with nothing on
    it**, which is the "link to nowhere" `table.team_link` already refuses to build.

    ✅ THE FIX WORTH HAVING IS A PUBLISHED FLAG, NOT A JOIN. The site reads one relation per
    query (G-2), so this page cannot ask whether a player has stats; a `has_player_stats`
    boolean on `srv_team_roster` would let the name link for the players it resolves for and
    stay plain for the rest. That is a dbt round, and it is named in A172's report.
    """
    st.subheader(fmt.title_case("Roster"))
    with states.section("srv_team_roster"):
        df = query("""
            select full_name, position, jersey, class_year_display,
                   height_display, height_inches, weight_pounds, hometown_display, as_of_ts
            from srv_team_roster
            where season = :season and team_slug = :team_slug
            order by position, jersey
            limit 250
        """, {"season": season, "team_slug": team_slug})

        def sections(frame):
            """⚠️ THIS WRITES; IT DOES NOT RETURN MARKUP. `table.render` renders to Streamlit
            and returns None — the first draft concatenated its result into a heading and got
            `TypeError: can only concatenate str (not "NoneType") to str`, caught by
            `states.section` and drawn as a handled error card. **Which is A141's shape exactly:
            the page returned 200, one section had died, and it looked considered.** It was
            found by §6.1's error-card count on the very first render, which is what that count
            is for.
            """
            # The unit is derived ONCE, here, and every section reads it — so the four groups
            # are a partition of the frame rather than four independent filters that could
            # between them drop a row or claim one twice.
            frame = frame.copy()
            frame["unit"] = frame["position"].map(roster_unit)
            for unit in [name for name, _ in ROSTER_UNITS] + [UNLISTED_UNIT]:
                block = frame[frame["unit"] == unit]
                if block.empty:
                    # A unit with nobody in it is left out for the same reason Unlisted is:
                    # a team with no listed kickers has no Special teams heading, rather than
                    # an empty one that reads as a rendering failure.
                    continue
                st.markdown(f"<h4 class='cfdb-roster-unit'>"
                            f"{fmt.title_case(unit)}</h4>",
                            unsafe_allow_html=True)
                table.render(block, ROSTER_COLUMNS, caption="")

        states.render_or_state(
            df, "srv_team_roster",
            "This team's roster would be here.",
            f"Rosters are collected from 2024 onward, so there is none for {season}."
            if season < 2024 else "No roster recorded for this team-season.",
            renderer=sections)


def render() -> None:
    shell.render_page("team", body)
