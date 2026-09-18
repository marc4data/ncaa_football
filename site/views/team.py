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
        _game_log(season, row.get('team_display'))
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


def _opponent(row) -> str:
    """AC-8.3 in one cell: "@ Ohio State" away, "Ohio State" home, "vs Ohio State" neutral.

    A neutral site is neither, and marking it "vs" rather than leaving it bare is the
    difference between a bowl game and a home game on a schedule read at a glance.
    """
    name = row.get("opponent") or fmt.EM_DASH
    if row.get("is_neutral_site"):
        return f"vs {name}"
    return f"@ {name}" if str(row.get("venue_role") or "").lower() == "away" else name


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


def _game_log(season, team_display) -> None:
    with states.section("srv_team_game_log"):
        df = query("""
            select week, game_id, game_date, opponent, opponent_conference, venue_role,
                   is_neutral_site, result, points_for, points_against, margin,
                   is_completed, as_of_ts
            from srv_team_game_log
            where season = :season and team = :team_display
            order by game_date, week
            limit 60
        """, {"season": season, "team_display": team_display})
        states.render_or_state(
            df, "srv_team_game_log",
            "This team's games would be listed here.",
            "No games recorded for this team-season.",
            renderer=lambda d: table.render(d, [
                Col("week", "Wk", "num", dp=0),
                Col("game_date", "Date", "date"),
                # "@ Opponent" rather than an H/A column. The universal convention in every
                # printed schedule, and it saves a column on a table that needed the width.
                Col("opponent", "Opponent", render=_opponent),
                Col("result", "Result"),
                Col("points_for", "PF", "num", dp=0),
                Col("points_against", "PA", "num", dp=0),
                # AC-8.3: oriented to the SUBJECT team, not to home.
                Col("margin", "Margin", "signed", dp=0),
            ], caption="",
                # AC-8.7: game log rows click through to the Matchup.
                link_builder=lambda r: params.link("matchup", game_id=r["game_id"],
                                                   season=season)))


# Marc's column order, verbatim: "Number, Name, Position, Ht, Wt, Class, Hometown".
#
# 🚨 THE HEIGHT COLUMN SORTS ON A DIFFERENT FIELD FROM THE ONE IT SHOWS, AND THAT IS THE WHOLE
# REASON IT IS WRITTEN THIS WAY. `height_display` is a STRING like `6-3`, so a column sorting on
# it puts `6-10` before `6-3` — lexical order on a number that is not one. `table.render` sorts
# on the Col's own `field`, so the field is `height_inches` (an integer) and `render` draws
# `height_display`. ⚠️ The next reader will otherwise assume the two are the same column.
ROSTER_COLUMNS = [
    Col("jersey", "#", "num", dp=0),
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
    st.subheader("Roster")
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
                st.markdown(f"<h4 class='cfdb-roster-unit'>{unit}</h4>",
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
