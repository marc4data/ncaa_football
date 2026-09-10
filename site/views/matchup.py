"""Matchup — page 10. One game, everything cfdb knows about it.

Four sections, and the interesting design problem is that they fail independently. A 2026
game has a market but no model row; a 1912 game has neither; a completed 2025 game has
both plus a result. Rendering "no data" once for the whole page would be wrong in every one
of those cases, so each section states its own absence and the page around it keeps working
— the same rule the Team page proves with tabs.

The model section is where the honesty rules land. `training_week_floor` is a COLUMN, not a
constant in this file: the floor is the model's property and it travels with the data, so
the copy cannot drift from what the model actually did.
"""
import html

import pandas as pd
import streamlit as st

from lib import (attribution, chips, filters, fmt, identity, params, shell,
                 states, table)
from lib.query import query
from lib.table import Col

COLUMNS = """
    game_id, season, season_type, week, start_date_et, venue_display, attendance,
    home_team_id, away_team_id,
    is_completed, is_conference_game, is_neutral_site,
    home_team, home_abbreviation, home_conference, home_logo_url, home_color_on_light,
    home_color_on_dark, home_points, home_wins, home_losses,
    away_team, away_abbreviation, away_conference, away_logo_url, away_color_on_light,
    away_color_on_dark, away_points, away_wins, away_losses,
    spread, spread_open, over_under, over_under_open, home_moneyline, away_moneyline,
    provider_key, line_snapshot_ts, market_implied_home_win_probability,
    market_implied_away_win_probability, overround, devig_method,
    model_name, model_family, predicted_margin, predicted_margin_home_perspective,
    predicted_total_points, predicted_home_points, predicted_away_points,
    home_win_probability, confidence_bucket, home_cover_edge, home_win_probability_edge,
    is_out_of_sample_week, training_week_floor,
    actual_margin, actual_margin_home_perspective,
    series_games, series_home_team_wins, series_away_team_wins, series_ties,
    series_first_season, series_last_season,
    model_version_key, attribution, as_of_ts,
    line_movement_provider_key, line_snapshot_count, line_movement_spans_snapshot_gap,
    line_spread_move_from_open, line_spread_largest_excursion,
    line_total_move_from_open, line_total_largest_excursion,
    line_market_implied_win_probability_move_from_open,
    line_market_implied_win_probability_largest_excursion,
    home_rank, away_rank, home_team_record_display, away_team_record_display,
    is_indoors, spread_favorite_side,
    home_q1, home_q2, home_q3, home_q4, home_overtime_points, home_periods,
    away_q1, away_q2, away_q3, away_q4, away_overtime_points, away_periods
"""


# --- R-501: the split, before the game and after it ----------------------------------------

# ⚠️ THE SPLIT IS STATE, NOT SUBJECT, AND THAT IS MARC'S RULING RATHER THAN A PREFERENCE.
#
# 2026-09-08, on the framework question: "There are two main different looks, what the matchup
# looks prior to the game, then post-game Scoreboard, Box Score, Team Stats etc. That's the
# major split." The same ruling killed R-444's SUBJECT-based grouping — game / market /
# context / sequence — and every cut offered alongside it. So there are two tabs named for
# WHEN, and there is no third tab for a subject.
#
# WHY IT EXISTS AT ALL: B074 measured eight panels, all eight populated on 52 of 52 FBS
# games. "The page has stopped being scannable, and the reason is that it succeeded."
#
# ⚠️ ANCHORS, NOT `st.tabs`, AND THE PATTERN IS SCORES' RATHER THAN A SECOND ONE (R-283).
# scores.py:181-224 solved this after Marc reported it: "Clicking a sort while on Against The
# Line or Box Score resets the user to the Game Results tab." `st.tabs` keeps its selection
# client-side and never touches the URL, so every link rebuilt the page at the default tab.
# `tab` is already a registered parameter (lib/params.py) and `params.link_here` preserves
# every known one, so a deep link into this page keeps its tab for free.
#
# ⚠️ AND ANCHORS ARE LAZY, WHICH MATTERS MORE HERE THAN ON SCORES. `st.tabs` renders every
# tab eagerly and only switches display, so wrapping these sections in it would multiply a
# cost the page already pays. Only the selected tab's panels are called below. Measured
# against live serving: five queries per render before this, two for a completed game after.
#
# ⚠️ THE PANELS ARE NAMED, NOT REFERENCED. Holding the function objects in this tuple would
# bind them at import, and then a test could not prove that the INACTIVE tab's panels were
# never called — monkeypatching `matchup._drives` would leave the bound original in the
# tuple and the lazy guarantee would be untestable. It is resolved at call time instead, so
# the assertion in test_matchup_tabs is real.
#
# (slug, label, panel names). THE SLUG IS WHAT GOES IN THE URL.
BEFORE, AFTER = "before", "after"
TABS = (
    # ⚠️ `_series` LEADS, AND `_weather` IS NOT HERE ANY MORE. R-520: head to head is a blurb
    # "close to the top" rather than a section, so it renders first. R-527: the weather folded
    # into the game header, which is why the page's query count did not move — the forecast is
    # still fetched once, by _conditions, and only before kickoff.
    (BEFORE, "Before the game",
     ("_series", "_market", "_line_movement", "_model", "_yardage", "_travel")),
    # ⚠️ ONE PANEL TODAY, AND THAT IS EXPECTED RATHER THAN UNBALANCED. The box score, the
    # advanced block and the player leaders are B076 — specified in
    # claude_work/cfdb_matchup_postgame_spec.md §1, all three on relations that already
    # exist. Nothing is stubbed here: a stub of an unbuilt thing is a promise the page
    # cannot keep, and it makes the next round impossible to measure.
    (AFTER, "After the game", ("_post_game", "_leaders", "_drives")),
)

# Which argument each panel takes. Named here rather than adapting the panels, because
# changing three signatures so a lookup table can be uniform would rewrite three test files
# to serve a data structure.
_GAME_ID_PANELS = {"_travel", "_drives", "_post_game", "_leaders"}


def _available_tabs(played: bool) -> tuple:
    """⚠️ AN UNPLAYED GAME HAS NO AFTER TAB AT ALL — NOT AN EMPTY ONE.

    The post-game spec's own line and it is right: "Empty is a state with a reason; an absent
    tab for an unplayed game is simply correct." An Empty state answers "why is there nothing
    here"; for a game that kicks off on Saturday the honest answer is not a state at all, it
    is that the question does not apply yet.

    A game that HAS been played always keeps the tab, even where cfdb holds nothing for it —
    drives are collected from 2024 onward, so a 1999 game shows the tab with one Empty block
    inside it. That is the opposite case and Empty is exactly right for it: the question
    applies, and the answer is that we do not hold it.
    """
    return TABS if played else TABS[:1]


def _active_tab(row) -> tuple:
    """The tab the URL asks for, or the one this game's STATE should open on.

    ⚠️ THE FALLBACK IS THE WHOLE OF "TWO DIFFERENT LOOKS". scores.py falls back to TABS[0]
    unconditionally; here a completed game opens on the after tab and a scheduled one on the
    before tab. Without that line this is one look with a tab bar on it, which is what
    test_a_completed_game_opens_on_the_after_tab was broken on purpose to prove.

    Two ways the URL can ask for something that does not apply, and neither raises:

      1. `?tab=after` on a game that has not been played — a real link someone sends on a
         Friday and opens on a Sunday, and a hand-edited URL besides.
      2. An unknown slug. scores.py already treats a hand-edited `?tab=` as noise rather than
         a request (AC-G.11).

    Both fall back to the tab this game's state would have opened on.
    """
    played = bool(row.get("is_completed"))
    available = _available_tabs(played)
    wanted = params.get("tab")
    for entry in available:
        if entry[0] == wanted:
            return entry
    # TABS[1] is the after tab, and `available` guarantees it is only reachable when played.
    return available[-1] if played else available[0]


def _tab_bar(active: str, played: bool) -> None:
    """R-283. THE TAB LIVES IN THE URL, WHICH IS WHY THESE ARE ANCHORS.

    ⚠️ NO BAR WHERE THERE IS NOTHING TO CHOOSE. A scheduled game has one tab, and a tab bar
    offering a single destination is a control that does nothing — the defect the rule
    immediately above this bar's CSS in lib/theme.py was written against. The scheduled game
    therefore reads exactly as it did before this round, minus the panel that could not have
    applied to it.
    """
    tabs = _available_tabs(played)
    if len(tabs) < 2:
        return
    links = []
    for slug, label, _panels in tabs:
        css = "cfdb-tab" + (" cfdb-tab-on" if slug == active else "")
        links.append(f"<a class='{css}' href='{params.link_here(tab=slug)}' "
                     f"target='_self'>{label}</a>")
    st.markdown(f"<div class='cfdb-tabbar'>{''.join(links)}</div>", unsafe_allow_html=True)


def _run_tab(entry, row, game_id) -> None:
    """Call this tab's panels, and ONLY this tab's panels.

    Resolved out of the module by name at call time — see the note on TABS. Each panel keeps
    the signature it already had; the set below says which of the two it is rather than every
    panel being rewritten to match its neighbours.
    """
    for name in entry[2]:
        panel = globals()[name]
        panel(game_id if name in _GAME_ID_PANELS else row)


def body(page) -> None:
    with states.section("srv_game"):
        game_id = params.get("game_id")
        if game_id is None:
            _picker()
            return

        df = query(f"""
            select {COLUMNS}
            from srv_game
            where game_id = :game_id
            limit 1
        """, {"game_id": game_id})

        if df.empty:
            # A game_id that resolves to nothing is the user asking for something that does
            # not exist — Empty with the bad value named, never a blank page (AC-G.11).
            states.empty("This game would be here.",
                         f"No game with id {game_id} is in the schedule.")
            _picker()
            return

        row = df.iloc[0]
        params.set_params(game_id=game_id, season=int(row["season"]))
        _game_header(row)
        table.as_of_caption(df)

        # R-501. Which of the two looks this game gets, and the panels that belong to it.
        # Every panel below still states its own absence and still runs inside its own
        # states.section, so the split changed WHEN a block is asked for and nothing about
        # how it fails.
        active = _active_tab(row)
        _tab_bar(active[0], bool(row.get("is_completed")))
        _run_tab(active, row, game_id)


def _picker() -> None:
    """No game_id. A REAL PICKER, not an arbitrary list.

    Arriving here cold used to show the most recent 300 games sorted by date with no way to
    narrow them — an unfiltered list, which is not a decision surface but a broken index.
    That only became visible because nothing on the site linked to this page, so the nav
    entry was the sole route in; with the deep links working it is the exception rather
    than the way in.

    Keeping the nav slot and giving it a job: the same filter bar every other page uses,
    grouped by day, searchable by team. AC-10.1 as amended.
    """
    scope = filters.game_scope()
    table.dataset_caption("Matchup", "srv_game")
    st.markdown("Pick a game to see the full matchup — market, model, and the series "
                "history. Every game row elsewhere on the site links straight here.")
    search = st.text_input("Find a team", placeholder="Type a team name…")

    games = query("""
        select game_id, season, week, start_date_et, game_date,
               home_team, away_team, home_conference, away_conference,
               home_points, away_points, is_completed, venue_display
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and (:conference is null or home_conference = :conference
               or away_conference = :conference)
        order by start_date_et, game_id
        limit 400
    """, {"season": scope.season, "season_type": scope.season_type,
          "week": scope.week, "conference": scope.conference})

    if search and not games.empty:
        mask = (games["home_team"].str.contains(search, case=False, na=False)
                | games["away_team"].str.contains(search, case=False, na=False))
        games = games[mask]

    states.render_or_state(
        games, "srv_game",
        "Games would be listed here.",
        f"No game matches “{search}”." if search else
        f"No games recorded for {scope.describe()}.",
        renderer=lambda d: _picker_table(d, scope),
        fix_label="Clear filters" if (scope.week or scope.conference) else None,
        fix=filters.clear)


def _picker_table(df, scope) -> None:
    """Grouped by day, like every other game list on the site."""
    for day, rows in df.groupby(df["game_date"], sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{fmt.day(pd.Timestamp(day))}</div>",
                    unsafe_allow_html=True)
        table.render(rows, [
            Col("start_date_et", "Kickoff", "time"),
            Col("away_team", "Away"),
            Col("away_points", "", "num", dp=0),
            Col("home_team", "Home"),
            Col("home_points", "", "num", dp=0),
            Col("venue_display", "Venue"),
        ], caption="",
            link_builder=lambda r: scope.link("matchup", game_id=r["game_id"]))


# --- R-518: the game header, nine columns --------------------------------------------------

# ⚠️ THE COLUMN ORDER IS MARC'S AND IT IS SYMMETRICAL ABOUT THE DETAILS COLUMN:
#
#   away logo | away team | away score | away glyph | DETAILS | home glyph | home score |
#   home team | home logo
#
# The two team columns face INWARD — away is right-aligned, home is left-aligned — so the
# names meet the scores in the middle rather than drifting to the page edges. That is what
# makes the row read as one matchup instead of two stacks.
_HEADER_WEIGHTS = (1.0, 3.6, 1.3, 0.45, 4.6, 0.45, 1.3, 3.6, 1.0)

# 🚨 NEITHER COLUMN EXISTS ON srv_game TODAY — measured against information_schema, not read
# off the model file. R-577 is session A's round to carry both across. They are named here,
# once, so the header renders them the day they land and omits them cleanly until then:
# `row.get()` on an absent column returns None and every use below is guarded.
#
# ⚠️ IF A SHIPS DIFFERENT NAMES, THESE TWO DICTS ARE THE ONLY LINES THAT CHANGE. Nothing
# else in the header refers to a mascot or a split record by name.
#
# ⚠️ AND THE PAGE MUST NOT JOIN TO FETCH THE MASCOT (§4.2, R-551). The mascot lives on
# srv_teams_index; a join added here would be a model change wearing a page change, and it
# would cost a second query on a page whose query count is a measured value.
_MASCOT_COLUMN = {"away": "away_mascot", "home": "home_mascot"}
_SPLIT_RECORD_COLUMN = {"away": "away_team_away_record_display",
                        "home": "home_team_home_record_display"}


def _rank_badge(rank) -> str:
    """A poll rank, or nothing. 291 of 3,831 games in 2025 have one on either side."""
    if rank is None or pd.isna(rank):
        return ""
    return (f"<span style='opacity:.6;font-size:.8rem;font-weight:600'>"
            f"#{int(rank)}</span> ")


def _team_cell(row, side: str, align: str) -> str:
    """Rank · team + mascot · record, split record — facing the middle of the header."""
    team = html.escape(str(row.get(f"{side}_team") or "?"))
    mascot = row.get(_MASCOT_COLUMN[side])
    if mascot is not None and pd.notna(mascot) and str(mascot).strip():
        team += f" <span style='opacity:.7'>{html.escape(str(mascot))}</span>"

    # ⚠️ THE OVERALL RECORD IS THE ONE LEADING INTO THIS GAME, NOT AFTER IT.
    # srv_game carries both — `*_record_display` and `*_record_after_display` — and on a
    # completed game they differ by exactly this result. The preview's whole discipline is
    # point-in-time (spec §5.3), so the header uses the leading-in reading on both tabs
    # rather than switching convention halfway down the page.
    records = []
    overall = row.get(f"{side}_team_record_display")
    if overall is not None and pd.notna(overall) and str(overall).strip():
        records.append(html.escape(str(overall)))
    split = row.get(_SPLIT_RECORD_COLUMN[side])
    if split is not None and pd.notna(split) and str(split).strip():
        records.append(f"{html.escape(str(split))} {side}")

    second = (f"<div style='opacity:.65;font-size:.8rem'>{', '.join(records)}</div>"
              if records else "")
    return (f"<div style='text-align:{align};line-height:1.25'>"
            f"<div style='font-weight:600'>{_rank_badge(row.get(f'{side}_rank'))}{team}</div>"
            f"{second}</div>")


def _score_cell(points, played: bool) -> str:
    """A scheduled game shows NO score rather than 0.

    Two zeroes is a real result — a scoreless tie — and rendering an unplayed game the same
    way asserts something false.
    """
    if not played or points is None or pd.isna(points):
        return ""
    return (f"<div style='font-size:2rem;font-weight:600;text-align:center;"
            f"line-height:1.1'>{int(points)}</div>")


def _winner_glyph(row, side: str) -> str:
    """Points AT that side's score, and ONLY if that side won.

    ⚠️ ABSENT, NOT EMPTY, BEFORE KICKOFF. B075's rule for the after tab is the same rule
    here: a post-game element on a pre-game page does not render a placeholder. A tie draws
    nothing on either side, which is why this asks who won rather than who did not lose.
    """
    if not bool(row.get("is_completed")):
        return ""
    home, away = row.get("home_points"), row.get("away_points")
    if home is None or away is None or pd.isna(home) or pd.isna(away):
        return ""
    won = (side == "home" and home > away) or (side == "away" and away > home)
    if not won:
        return ""
    # The glyph sits BETWEEN the two scores, so it points outward towards the score it
    # belongs to: the away score is to its left, the home score is to its right.
    arrow = "\u25c0" if side == "away" else "\u25b6"
    return (f"<div style='text-align:center;font-size:1.4rem;line-height:1.1;"
            f"opacity:.75'>{arrow}</div>")


def _conditions(row) -> str:
    """The weather, folded into the header as one line — or NOTHING at all (R-527).

    Marc: "Great data, but should be delivered in a tight/concise element in the game
    header." The standalone panel is gone from the preview body.

    🚨 IT COLLAPSES TO NOTHING RATHER THAN DRAWING AN EMPTY SLOT, and that is the point
    rather than a nicety. B075 measured that forecasts exist only about a week out — 253 of
    the 303 week-2 games, and ZERO for weeks 4 through 8 — so for most of a season this
    element has nothing to say, and a reserved slot would be dead space on every preview.

    ⚠️ `is_indoors` IS NOT "NO WEATHER", AND IT COSTS NO QUERY. A dome has a known answer —
    indoors — which is a different statement from "we have no forecast" (AC-G.11). It is a
    column on srv_game, already on the row the page fetched, so the roof is stated even when
    no forecast row exists at all.

    ⚠️ EVERY FIGURE HERE IS A FORECAST AND IT SAYS SO. The header draws this only before
    kickoff, so unlike the old panel there is no observation case to confuse it with — but
    the word stays, because a temperature with no tense reads as a measurement.

    ⚠️ int(), AND IT IS NOT DEFENSIVE TYPING. The value arrives as a numpy.int64 out of the
    DataFrame rather than as the int params.get() casts, and psycopg2 cannot adapt one:
    "can't adapt type 'numpy.int64'". That defect rendered the Error state on EVERY game and
    nothing in the suite could see it (B076).
    """
    indoors = bool(row.get("is_indoors")) if pd.notna(row.get("is_indoors")) else False
    parts = []
    df = query("""
        select game_id, temperature_f, wind_speed_mph, wind_direction_compass,
               weather_condition
        from srv_game_weather
        where game_id = :game_id
        limit 1
    """, {"game_id": int(row.get("game_id"))})
    if not df.empty:
        reading = df.iloc[0]
        if pd.notna(reading.get("temperature_f")):
            parts.append(f"{reading['temperature_f']:g}\u00b0F")
        if pd.notna(reading.get("wind_speed_mph")):
            wind = f"{reading['wind_speed_mph']:g} mph"
            if reading.get("wind_direction_compass"):
                wind += f" {html.escape(str(reading['wind_direction_compass']))}"
            parts.append(wind)
        if reading.get("weather_condition"):
            parts.append(html.escape(str(reading["weather_condition"])))

    if not parts and not indoors:
        return ""
    if indoors:
        # The roof first, then the outdoor readings labelled as such — CFBD reports the
        # weather at the venue's LOCATION, not inside it, so a domed game carries ordinary
        # outdoor numbers and printing them bare would state something false.
        return ("<div>Indoors"
                + (f" \u00b7 {' \u00b7 '.join(parts)} outside" if parts else "")
                + "</div>")
    return f"<div>Forecast \u00b7 {' \u00b7 '.join(parts)}</div>"


def _line_score(row) -> str:
    """The post-game scoreboard: quarters, overtime if there was any, and the final.

    3,805 of the 3,831 completed 2025 games carry a first quarter, so a completed game
    without one is rare rather than impossible and renders no table instead of a row of
    dashes.
    """
    quarters = ["q1", "q2", "q3", "q4"]
    if all(pd.isna(row.get(f"away_{q}")) for q in quarters):
        return ""
    headers = ["1", "2", "3", "4"]
    # OVERTIME IS A COLUMN THAT APPEARS, NOT ONE THAT IS ALWAYS THERE. 109 of 2025's
    # completed games went to overtime; the rest must not carry an empty OT column.
    overtime = any(pd.notna(row.get(f"{s}_overtime_points"))
                   and row.get(f"{s}_overtime_points") for s in ("away", "home"))
    if overtime:
        headers.append("OT")
    headers.append("T")

    def cells(side):
        values = [row.get(f"{side}_{q}") for q in quarters]
        if overtime:
            values.append(row.get(f"{side}_overtime_points"))
        values.append(row.get(f"{side}_points"))
        return "".join(
            f"<td style='padding:.05rem .3rem;text-align:right"
            f"{';font-weight:600' if i == len(values) - 1 else ''}'>"
            f"{'' if pd.isna(v) else int(v)}</td>"
            for i, v in enumerate(values))

    head = "".join(f"<th style='padding:.05rem .3rem;text-align:right;font-weight:500;"
                   f"opacity:.6'>{h}</th>" for h in headers)
    rows = ""
    for side in ("away", "home"):
        label = html.escape(str(row.get(f"{side}_abbreviation")
                                or row.get(f"{side}_team") or "?"))
        rows += (f"<tr><td style='padding:.05rem .4rem .05rem 0;opacity:.7'>{label}</td>"
                 f"{cells(side)}</tr>")
    return (f"<table style='margin:0 auto;border-collapse:collapse;font-size:.82rem'>"
            f"<tr><th></th>{head}</tr>{rows}</table>")


def _details_cell(row) -> str:
    """The centre column: the preview's facts before kickoff, the scoreboard after it."""
    played = bool(row.get("is_completed"))
    venue = html.escape(str(row.get("venue_display") or ""))
    if row.get("is_neutral_site"):
        venue += " \u00b7 neutral site" if venue else "neutral site"

    if played:
        return (f"<div style='text-align:center;font-size:.82rem;opacity:.85'>"
                f"<div style='font-weight:600;margin-bottom:.15rem'>Final</div>"
                f"{_line_score(row)}"
                f"<div style='opacity:.75;margin-top:.15rem'>{venue}</div></div>")

    lines = [f"<div style='font-weight:600'>{fmt.local_time(row.get('start_date_et'))}</div>"]
    # THE SPREAD IS THE HOME PERSPECTIVE AND THE HOME TEAM IS NAMED BESIDE IT. AC-1.4: a
    # home favorite is a NEGATIVE spread. Naming the side the number belongs to is exact and
    # needs no arithmetic; the favorite-perspective presentation Marc described belongs to
    # the market card (spec §3) and is B083's, not this header's.
    market = []
    if pd.notna(row.get("spread")):
        home_label = html.escape(str(row.get("home_abbreviation")
                                     or row.get("home_team") or "home"))
        market.append(f"{home_label} {fmt.signed(row.get('spread'), 'spread')}")
    if pd.notna(row.get("over_under")):
        market.append(f"O/U {fmt.number(row.get('over_under'), 'over_under')}")
    if market:
        lines.append(f"<div>{' \u00b7 '.join(market)}</div>")

    conditions = _conditions(row)
    if conditions:
        lines.append(conditions)
    if venue:
        lines.append(f"<div style='opacity:.75'>{venue}</div>")
    return ("<div style='text-align:center;font-size:.82rem;opacity:.9;line-height:1.45'>"
            + "".join(lines) + "</div>")


def _game_header(row) -> None:
    """R-518. One nine-column row, and the page's first formalised element.

    Marc: "We need to formalize the elements on the page, similar to how we did on
    Schedule/stacked." Spec §0's layout law — columns, not sections; away on the LEFT —
    starts here and governs everything placed below it.

    ⚠️ THE WEATHER QUERY MOVED INTO THIS FUNCTION RATHER THAN BEING ADDED TO THE PAGE. The
    standalone panel left the before tab in the same commit, so the page's query count is
    unchanged: the header asks for a forecast only before kickoff, which is the only tab
    state the removed panel ever ran in.
    """
    played = bool(row.get("is_completed"))
    columns = st.columns(_HEADER_WEIGHTS, vertical_alignment="center")
    cells = (
        identity.logo_or_monogram(row.get("away_logo_url"),
                                  str(row.get("away_team") or "?"), 44),
        _team_cell(row, "away", "right"),
        _score_cell(row.get("away_points"), played),
        _winner_glyph(row, "away"),
        _details_cell(row),
        _winner_glyph(row, "home"),
        _score_cell(row.get("home_points"), played),
        _team_cell(row, "home", "left"),
        identity.logo_or_monogram(row.get("home_logo_url"),
                                  str(row.get("home_team") or "?"), 44),
    )
    for column, markup in zip(columns, cells):
        with column:
            st.markdown(markup, unsafe_allow_html=True)


def _market(row) -> None:
    st.subheader("Market")
    if pd.isna(row.get("spread")) and pd.isna(row.get("over_under")):
        # Most of 110,634 games predate betting data entirely, which is an absence of
        # market rather than a failure to fetch one, so it renders Empty.
        states.empty("The betting market would be here.",
                     "No sportsbook line has been recorded for this game. "
                     "cfdb holds lines from 2013 onward, and only for games books priced.")
        return
    cols = st.columns(4)
    # AC-1.4 again: a home favorite is a NEGATIVE spread. Stated on the page, because this
    # is the number a reader is most likely to invert.
    cols[0].metric("Spread (home)", fmt.signed(row.get("spread"), "spread"),
                   help="Negative means the home team is favoured.")
    # R-009, third placement. Same sentence, one source.
    cols[1].metric("Total", fmt.number(row.get("over_under"), "over_under"))
    cols[2].metric("Home moneyline", fmt.signed(row.get("home_moneyline"), "", dp=0))
    cols[3].metric("Away moneyline", fmt.signed(row.get("away_moneyline"), "", dp=0))

    implied = row.get("market_implied_home_win_probability")
    if pd.notna(implied):
        st.caption(
            f"Implied home win probability {float(implied) * 100:.1f}% "
            f"(away {float(row.get('market_implied_away_win_probability')) * 100:.1f}%), "
            f"de-vigged by {row.get('devig_method')}; the book's overround was "
            f"{fmt.number(row.get('overround'), '', 4)}. Raw prices above are untouched.")
    chips.spread_sign_note()
    st.caption(f"Line from {row.get('provider_key') or 'an unnamed book'}, "
               f"snapshot {fmt.local_time(row.get('line_snapshot_ts'))}. "
               f"Opening spread {fmt.signed(row.get('spread_open'), 'spread_open')}, "
               f"opening total {fmt.number(row.get('over_under_open'), 'over_under_open')}.")


def _line_movement(row) -> None:
    """How far the line travelled between opening and now — the market's history, not its state.

    WHAT THE NET MOVE CANNOT SHOW, AND WHY THERE ARE TWO NUMBERS PER MARKET. A line that goes
    out three points and comes back reads as no move at all: 16 spreads and 6 probabilities in
    the built model are exactly that round trip. The excursion is the widest departure from the
    open, signed so it keeps the direction it departed in, and it is a DIFFERENT measurement
    from the net move — `assert_line_excursion_is_not_just_the_net_move` fails if the two ever
    collapse into one.

    ⚠️ READ `line_snapshot_count` BEFORE BELIEVING AN EXCURSION. 1,577 of 1,854 games carry a
    single snapshot, because 2024 and 2025 were backfilled one row per game, and on those the
    excursion equals the net move by construction rather than by measurement. The panel says so
    rather than drawing two numbers that look independent and are not.

    ⚠️ THE BOOK IS NAMED ON THE PANEL. Every measure is one book's, set by the
    `line_movement_provider` variable, because a move measured against another book's price is
    not a move. A market figure that does not say whose price it came from is the provenance
    defect the `market_implied_` prefix rule exists to prevent.

    NO THRESHOLD IS APPLIED. A059 measured the distributions and stopped there — Marc sets what
    counts as a big move — so nothing here is highlighted, coloured or ranked by a cutoff.
    """
    st.subheader("Line movement")
    # Its own section, like weather and drives: this reads columns the rest of the page does
    # not, so a movement failure degrades one block rather than blanking a Matchup that is
    # otherwise complete. No second query — the measures are already on the srv_game row the
    # page fetched, and re-asking for data in hand is a round trip the display-only contract
    # does not need.
    with states.section("srv_game"):
        snapshots = row.get("line_snapshot_count")
        if pd.isna(snapshots):
            # EMPTY, NOT DEGRADED. No snapshot history is the absence of a market to track,
            # not a fault in tracking it: the movement mart covers the seasons the snapshot
            # loader runs for, and a game outside them never had a line observed twice.
            states.empty(
                "How the line moved would be here.",
                "No line snapshots have been recorded for this game, so there is no opening "
                "price to measure a move against.")
            return

        cols = st.columns(3)
        # Spread and total in points, probability in PROBABILITY POINTS — moneylines are not
        # comparable as numbers (-110 to -130 and +200 to +180 are 4.1 and 2.4 points), so the
        # movement is expressed in the units the distribution was measured in.
        cols[0].metric(
            "Spread move",
            fmt.signed(row.get("line_spread_move_from_open"), "line_spread_move_from_open"),
            help="Current spread minus the opening spread. Negative means the home team is "
                 "favoured by more than it was.")
        cols[1].metric(
            "Total move",
            fmt.signed(row.get("line_total_move_from_open"), "line_total_move_from_open"))
        cols[2].metric(
            "Home win probability move",
            fmt.signed(row.get("line_market_implied_win_probability_move_from_open"), "", dp=2),
            help="De-vigged, in probability points.")

        wide = st.columns(3)
        wide[0].metric(
            "Widest spread excursion",
            fmt.signed(row.get("line_spread_largest_excursion"),
                       "line_spread_largest_excursion"),
            help="The furthest the spread ever got from its open, keeping the direction.")
        wide[1].metric(
            "Widest total excursion",
            fmt.signed(row.get("line_total_largest_excursion"),
                       "line_total_largest_excursion"))
        wide[2].metric(
            "Widest probability excursion",
            fmt.signed(row.get("line_market_implied_win_probability_largest_excursion"),
                       "", dp=2))

        observed = int(snapshots)
        book = row.get("line_movement_provider_key") or "an unnamed book"
        st.caption(
            f"Measured across {observed} snapshot{'' if observed == 1 else 's'} "
            f"from {book}. Every figure above is that one book's, because a move measured "
            f"against a different book's price is not a move.")

        if observed == 1:
            # DEGRADED, AND IT IS THE COMMON CASE. One observation cannot show a path, so the
            # excursion is the net move restated rather than a second fact. Said plainly
            # instead of drawing six numbers of which three are echoes.
            st.caption(
                "This game's line was observed once, so the widest excursion is the net move "
                "restated rather than a separate measurement.")

        if bool(row.get("line_movement_spans_snapshot_gap")):
            # THE OTHER DEGRADED STATE, and it travels on the row rather than in a footnote
            # somewhere: three days in 2026 hold no snapshots at all, and a window spanning
            # them was not observed throughout. The excursion is then a floor — the line may
            # have gone further while nobody was looking — and a floor presented as a
            # measurement is the defect the caveat exists to prevent.
            st.caption(
                "This game's line was being tracked across the three days that hold no "
                "snapshots, so the widest excursion above is a floor rather than a "
                "measurement — the line may have travelled further unobserved.")


def _model(row) -> None:
    st.subheader("Model")
    floor = row.get("training_week_floor")
    week = row.get("week")

    if pd.isna(row.get("predicted_margin")):
        # The two reasons a prediction is missing are completely different claims, and
        # collapsing them would be the site's worst kind of lie: "too early to say" versus
        # "we have nothing for this era".
        if pd.notna(floor) and pd.notna(week) and int(week) < int(floor):
            states.empty(
                "The model's forecast would be here.",
                chips.week_floor_note(
                    floor, row.get("season"),
                    clause=f", and this game is in Week {int(week)}"))
        else:
            states.empty(
                "The model's forecast would be here.",
                "No model has scored this game. Predictions cover 2025 from Week "
                f"{int(floor) if pd.notna(floor) else 5} onward.")
        return

    cols = st.columns(4)
    cols[0].metric("Predicted margin (home)",
                   fmt.signed(row.get("predicted_margin_home_perspective"),
                              "predicted_margin_home_perspective"),
                   help="Positive means the model has the home team winning by that many.")
    cols[1].metric("Predicted total",
                   fmt.number(row.get("predicted_total_points"), "predicted_total_points"))
    cols[2].metric("Home win probability",
                   fmt.number(row.get("home_win_probability"), "home_win_probability"))
    cols[3].metric("Cover edge",
                   fmt.signed(row.get("home_cover_edge"), "home_cover_edge"))

    if row.get("is_out_of_sample_week"):
        st.markdown(chips.out_of_sample_chip_html(True), unsafe_allow_html=True)

    st.caption(
        f"Model {row.get('model_name')} ({row.get('model_family')}), version "
        f"{row.get('model_version_key')}. Predicted score "
        f"{fmt.number(row.get('predicted_away_points'), '', 1)} – "
        f"{fmt.number(row.get('predicted_home_points'), '', 1)} (away – home).")

    actual = row.get("actual_margin_home_perspective")
    if pd.notna(actual):
        # Both readings come from the view. The app does not flip the sign: a sign
        # convention is a definition, and definitions live in dbt (G-3).
        st.caption(
            f"Actual margin "
            f"{fmt.signed(actual, 'actual_margin_home_perspective')} from the home "
            f"perspective ({fmt.signed(row.get('actual_margin'), 'actual_margin')} as "
            f"cfdb stores it, away minus home). Same result, read from the two ends.")
    attribution.model_attribution(pd.DataFrame([row]))


def _series(row) -> None:
    """R-520. Head to head as a BLURB, not a section.

    Marc: "Probably doesn't merit a full section, but I do like the content. Probably should
    just be a text blurb close to the top." So it renders first in the preview and costs one
    line — no subheader, no card, no Empty state.

    ⚠️ A SERIES OF NO GAMES IS NOT 0-0. Two teams who have never met and two teams who have
    split evenly are different statements, and the first is a sentence rather than a score.

    ⚠️ THE AWAY SIDE IS READ, NEVER DERIVED. srv_game.sql's own comment warns that taking it
    as `series_games - series_home_team_wins` is "only correct in a sport" without ties: the
    subtraction credits every draw to the away team. The model carries
    `series_away_team_wins` and this reads it.

    ⚠️ AWAY FIRST, matching the header above it and spec §0's layout law. The two names and
    the two numbers move together or the sentence inverts — which is the R-544 class, and it
    is asserted positionally rather than by counting names.
    """
    games = row.get("series_games")
    away, home = row.get("away_team") or "?", row.get("home_team") or "?"
    if pd.isna(games) or int(games) == 0:
        st.caption(f"{away} and {home} have never met.")
        return
    away_wins, home_wins = row.get("series_away_team_wins"), row.get("series_home_team_wins")
    ties = row.get("series_ties")
    tie_text = ""
    if pd.notna(ties) and int(ties):
        tie_text = f", with {int(ties)} tie{'s' if int(ties) != 1 else ''}"
    span = ""
    if pd.notna(row.get("series_first_season")) and pd.notna(row.get("series_last_season")):
        span = (f", {int(row.get('series_first_season'))} to "
                f"{int(row.get('series_last_season'))}")
    st.caption(
        f"**Head to head** \u2014 {away} {int(away_wins)}, {home} {int(home_wins)} across "
        f"{int(games)} meeting{'s' if int(games) != 1 else ''}{tie_text}{span}.")


# --- R-463: offence against defence -------------------------------------------------------

# ⚠️ THE PAIRING IS ACROSS SIDES, AND IT IS THE ONE THING HERE THAT IS EASY TO GET
# BACKWARDS. Marc's comparison, verbatim: "how team A produces passing yards compared to how
# Team B allows passing yards." So a team's `_for` sits beside the OTHER side's `_allowed`.
# Pairing a team's `_for` with its own `_allowed` describes one team rather than a matchup,
# and it would look entirely reasonable on screen — which is why
# test_the_pairing_runs_across_sides_not_down_one exists and was watched go red.
_YARDAGE_DIMENSIONS = (
    ("Rushing", "rushing_yards_for_per_game", "rushing_yards_allowed_per_game"),
    ("Passing", "passing_yards_for_per_game", "passing_yards_allowed_per_game"),
    # TOTAL EARNS ITS ROW ON A MEASUREMENT, NOT ON SYMMETRY. It is rushing + passing in
    # 13,686 of the 13,728 rows that carry any form, and differs in 42 by up to 11 yards —
    # so it is the source's own total rather than our arithmetic, and adding the two above
    # in this file would be metric maths in the app. It renders last and subordinate,
    # because 99.7% of the time it is the sum of the two lines over it.
    ("Total", "total_yards_for_per_game", "total_yards_allowed_per_game"),
)

_YARDAGE_COLUMNS = """
    team_id, team_display, team_slug, logo_url, color_on_light, color_on_dark,
    conference, classification, is_fbs, games_counted,
    rushing_yards_for_per_game, passing_yards_for_per_game, total_yards_for_per_game,
    rushing_yards_allowed_per_game, passing_yards_allowed_per_game,
    total_yards_allowed_per_game, as_of_ts
"""


def _yardage_direction(offence, defence) -> str:
    """One direction of the comparison: this side's attack against that side's defence."""
    accent = identity.text_on(offence)
    logo = identity.logo_or_monogram(
        offence.get("logo_url"), str(offence.get("team_display") or "?"), 20)
    lines = []
    # R-516. THE SECOND ARGUMENT IS THE COLUMN-NAME SLOT AND IT USED TO HOLD THE BARE WORD
    # 'yards', so `fmt.precision_for` had never once seen a column from this panel. A085
    # flipped that fallback to 0 and had to key ('yards', 1) in `fmt.PRECISION` purely to
    # hold this file harmless — 154.4 would otherwise have rendered 154 here.
    #
    # `dp=1` states the panel's precision where the decision is made, the way _ADVANCED_ROWS
    # already does. A PER-GAME AVERAGE IS NOT A COUNT: 154.4 and 154.0 are different seasons,
    # and putting two sides beside each other is the whole job of this panel. If that is ever
    # overturned, the reversal is DELETING `dp=1` — the column name is already correct, so
    # `fmt` decides from then on.
    for label, for_column, allowed_column in _YARDAGE_DIMENSIONS:
        subdued = " opacity:.75;font-size:.9rem;" if label == "Total" else ""
        lines.append(
            f"<div style='display:flex;align-items:baseline;gap:.5rem;{subdued}"
            f"padding:.15rem 0'>"
            f"<span style='min-width:4.5rem;opacity:.6;font-size:.8rem'>{label}</span>"
            f"<span style='min-width:5rem;font-weight:600;text-align:right'>"
            f"{fmt.number(offence.get(for_column), for_column, dp=1)}</span>"
            f"<span style='opacity:.45;font-size:.8rem'>gained</span>"
            f"<span style='opacity:.35;margin:0 .2rem'>vs</span>"
            f"<span style='min-width:5rem;font-weight:600;text-align:right'>"
            f"{fmt.number(defence.get(allowed_column), allowed_column, dp=1)}</span>"
            f"<span style='opacity:.45;font-size:.8rem'>allowed</span></div>")
    return (
        f"<div style='border-left:4px solid {accent};padding:.4rem .7rem;"
        f"margin-bottom:.5rem'>"
        f"<div style='display:flex;align-items:center;gap:.45rem;margin-bottom:.2rem'>"
        f"{logo}<span style='font-weight:600'>{offence.get('team_display') or '?'}</span>"
        f"<span style='opacity:.6;font-size:.85rem'>offence against "
        f"{defence.get('team_display') or '?'}'s defence</span></div>"
        + "".join(lines) + "</div>")


def _yardage(row) -> None:
    """Offence against defence, per game, LEADING INTO this game's own week (R-463).

    ⚠️ THE POINT-IN-TIME PROPERTY IS THE VIEW'S, NOT THIS PANEL'S. Marc, 2026-09-09: "Can't
    find ourselves at Week 10 and looking back to the matchups for a team in Week 2 and have
    their data for Week 2 showing like they've played through Week 10." srv_team_week is
    built at (season, season_type, week) grain over completed games in weeks strictly
    BEFORE the row's own week, so reading the row for THIS game's week is already the
    answer. Nothing here computes, adjusts or re-derives it, and nothing reads a
    season-grain view to approximate it.

    ⚠️ THE `_per_game` COLUMNS ARE RENDERED, NEVER THE SUMS. The sums ship so something can
    re-aggregate; a division in this file would be metric maths in the app, which is the rule
    the serving layer exists to keep. There is no `group by` and no `sum(` in the query
    below and there must never be one — the grain returns exactly one row per side.

    ⚠️ `games_counted` TRAVELS WITH THE NUMBERS FOR BOTH SIDES (AC-G.33), because the two
    can differ — 401752754 is 7 against 8 — and it is NOT "games played": it counts
    completed games both sides of whose box score cfdb holds. A reader comparing 154.4 to
    84.5 without knowing one is over seven games and the other over eight is being misled by
    two true numbers.

    NOTHING IS RANKED, COLOURED BY ADVANTAGE OR CALLED AN EDGE. Marc sets the line, not the
    page — the same rule _line_movement carries a test for.
    """
    st.subheader("Offence against defence")
    # Its own section and its own view: this is the only block on the page that reads
    # srv_team_week, so a failure here degrades one panel rather than blanking a Matchup
    # that is otherwise complete.
    with states.section("srv_team_week", degraded_if_missing="srv_team_week",
                        explanation="Week-grain team form has not been built yet."):
        home_id, away_id = row.get("home_team_id"), row.get("away_team_id")
        if pd.isna(home_id) or pd.isna(away_id):
            states.empty(
                "Each side's yardage against the other's defence would be here.",
                "This game's schedule row does not identify both teams, so there is "
                "nothing to look the two sides up by.")
            return

        # ONE QUERY, TWO ROWS. The grain returns exactly one row per (season, season_type,
        # week, team), which is the whole reason srv_team_week exists in this shape, so the
        # limit is the grain restated rather than a guess at a ceiling (AC-G.39).
        df = query(f"""
            select {_YARDAGE_COLUMNS}
            from srv_team_week
            where season = :season
              and season_type = :season_type
              and week = :week
              and team_id in (:home_team_id, :away_team_id)
            limit 2
        """, {"season": int(row["season"]), "season_type": row["season_type"],
              "week": int(row["week"]),
              "home_team_id": int(home_id), "away_team_id": int(away_id)})

        by_team = {int(r["team_id"]): r for _, r in df.iterrows()}
        home, away = by_team.get(int(home_id)), by_team.get(int(away_id))

        if home is None and away is None:
            # EMPTY. Neither side is carried at week grain, which is an absence of data
            # about this fixture rather than a fault in a side of it.
            states.empty(
                "Each side's yardage against the other's defence would be here.",
                f"Neither {row.get('home_team')} nor {row.get('away_team')} is carried in "
                f"the week-by-week team record for this season.")
            return

        if home is None or away is None:
            # ⚠️ DEGRADED, AND THE WHOLE PANEL — NOT HALF OF IT. Both directions of Marc's
            # comparison need both rows: with one side absent, the only thing left to draw
            # is one team's own for-and-allowed, which is a description of that team wearing
            # the layout of a matchup. That is the precise confusion 1c warns about, so the
            # panel says it cannot rather than rendering half a comparison as a whole one.
            #
            # It is Degraded rather than Empty because it is ours: srv_team_week inner joins
            # dim_team, and dim_team does not list every opponent an FBS side schedules.
            missing = row.get("home_team") if home is None else row.get("away_team")
            states.degraded(
                # ⚠️ R-500, and this is the case B074 REPORTED rather than fixed. srv_team_week
                # is built and published — it is this team's ROW that is absent — so the old
                # hardcoded "Not built yet" contradicted the sentence directly beneath it.
                # A081 added the `title` parameter to site/lib/states.py (session A's file)
                # and this is the one-argument change that consumes it.
                title="No data for this team",
                missing_object="srv_team_week",
                explanation=(
                    f"cfdb holds no week-by-week record for {missing} this season, and "
                    f"both directions of this comparison need both sides — so showing the "
                    f"other team's own figures here would read as a matchup while "
                    f"describing one team."))
            return

        counted = [int(side["games_counted"] or 0) for side in (home, away)]
        if not all(counted):
            # EMPTY, AND THE TWO REASONS ARE DIFFERENT CLAIMS. The per-game columns are NULL
            # BY DESIGN where nothing has been counted — srv_team_week's own comment: "0.0
            # yards per game is a measurement it did not make" — so a zero must never be
            # drawn here. But "nobody has played yet" and "cfdb holds no box scores for
            # these sides" are opposite statements, and collapsing them is the same lie
            # _model refuses to tell about a missing forecast. Measured: at the opening week
            # of a regular season, games_counted is 0 for every team in all 157 seasons; a
            # zero at any later week means the box scores were never held.
            opening = str(row.get("season_type")) == "regular" and int(row["week"]) == 1
            why = ("Neither side has played a counted game yet, so there is no per-game "
                   "figure to show — a zero here would be a measurement cfdb did not make."
                   if opening else
                   "cfdb holds no box scores for " + (
                       f"{row.get('home_team')} or {row.get('away_team')}" if not any(counted)
                       else f"{row.get('home_team') if not counted[0] else row.get('away_team')}")
                   + " in the weeks before this game, so there is no per-game figure to "
                     "show — a zero here would be a measurement cfdb did not make.")
            states.empty(
                "Each side's yardage against the other's defence would be here.", why)
            return

        st.markdown(_yardage_direction(away, home), unsafe_allow_html=True)
        st.markdown(_yardage_direction(home, away), unsafe_allow_html=True)

        # AC-G.33. The denominator is not decoration and it is named for each side
        # separately, because a bye or a missing box score makes the two differ.
        st.caption(
            f"Yards per game leading into week {int(row['week'])}, over "
            f"{counted[0]} completed game{'' if counted[0] == 1 else 's'} for "
            f"{home.get('team_display')} and {counted[1]} for {away.get('team_display')}. "
            f"games_counted is not games played — it counts the completed games both "
            f"sides of whose box score cfdb holds.")
        table.as_of_caption(df)


# --- R-505: what happened in the game ------------------------------------------------------

# ⚠️ ONE READ, TWO RENDERINGS — WHICH IS WHY THIS IS ONE PANEL AND NOT TWO.
#
# srv_game_team carries the plain box score AND the whole advanced block on the same relation
# (223 columns, measured). Two TABS entries would be two queries against one relation, which
# G-2's one-relation-one-pass rule exists to prevent — and it is also what stops the two
# sections disagreeing about a game they both describe. So the tab holds one panel name and
# the panel draws two headed sections from one frame.
#
# The grain is game × team, so a matchup is exactly two rows and the comparison layout is
# free: one column per side, one row per statistic.
_POSTGAME_COLUMNS = """
    game_id, team_id, team_display, team_logo_url, is_home,
    has_box_score, has_box_advanced, has_team_advanced, has_havoc,
    first_downs, total_yards, rushing_yards, passing_yards, rushing_attempts,
    turnovers, interceptions, fumbles_lost,
    third_down_conversions, third_down_attempts,
    fourth_down_conversions, fourth_down_attempts,
    penalties, penalty_yards,
    offense_plays, offense_drives, offense_ppa, offense_success_rate,
    offense_explosiveness, offense_standard_downs_success_rate,
    offense_passing_downs_success_rate, offense_rushing_plays_ppa,
    offense_passing_plays_ppa, offense_power_success, offense_stuff_rate,
    offense_line_yards, defense_havoc_rate,
    possession_display,
    offense_success_rate_display, offense_standard_downs_success_rate_display,
    offense_passing_downs_success_rate_display, offense_power_success_display,
    offense_stuff_rate_display, defense_havoc_rate_display,
    as_of_ts
"""

# ⚠️ THE SERVING LAYER SHIPS THE PERCENTAGE, BECAUSE THE APP CANNOT MULTIPLY (A080, R-509).
# B076 rendered these six as 0.375 and said so: turning a share into 37.5% is arithmetic, and
# lib/fmt.py's own docstring is "Formatting only — never arithmetic". A080 published the
# display string beside each share, which is the same answer srv_drive gave for durations.
#
# ⚠️ IT IS A MAP AND NOT A FOURTH TUPLE ELEMENT, AND THAT IS THE POINT OF THE SHAPE.
# `_GLOSSARY_FIELDS` derives from `_ADVANCED_ROWS`, and dim_field_metadata documents
# `offense_success_rate` — NOT `offense_success_rate_display`. Swapping the field name inside
# the rows would make the dictionary lookup ask for a column it has never heard of and turn
# six of the twelve tooltips into "(undefined)". Keeping the metric name in the row and the
# display column beside it means the page renders one and looks up the other, which is also
# what serving actually holds: X and X_display are two columns of one fact.
#
# ⚠️ FIVE ROWS ARE DELIBERATELY ABSENT AND IT WAS MEASURED, NOT ASSUMED. PPA per play, PPA
# rushing, PPA passing, explosiveness and line yards keep their decimals: offense_ppa runs
# NEGATIVE (−0.644) and offense_explosiveness reaches 2.737, and a share can do neither.
_DISPLAY_COLUMN = {
    "offense_success_rate": "offense_success_rate_display",
    "offense_standard_downs_success_rate": "offense_standard_downs_success_rate_display",
    "offense_passing_downs_success_rate": "offense_passing_downs_success_rate_display",
    "offense_power_success": "offense_power_success_display",
    "offense_stuff_rate": "offense_stuff_rate_display",
    "defense_havoc_rate": "defense_havoc_rate_display",
}


def _figure(side, field, dp) -> str:
    """The serving-shipped display string where there is one, the number otherwise."""
    display = _DISPLAY_COLUMN.get(field)
    if display:
        value = side.get(display)
        if value is not None and not (isinstance(value, float) and pd.isna(value)):
            return str(value)
    return fmt.number(side.get(field), dp=dp)


# (label, field, decimal places). The plain half — common knowledge, and the rows a reader
# already expects to find. Two of them are drawn from more than one field and carry their own
# renderer instead, below.
_BOX_SCORE_ROWS = (
    ("First downs", "first_downs", 0),
    ("Total yards", "total_yards", 0),
    ("Rushing yards", "rushing_yards", 0),
    ("Passing yards", "passing_yards", 0),
    ("Rushing attempts", "rushing_attempts", 0),
    ("Penalty yards", "penalty_yards", 0),
)

# ⚠️ THE DOZEN, AND THE CUT IS EDITORIAL RATHER THAN TECHNICAL.
#
# srv_game_team has 223 columns. Rendering them is not a page, it is a data dictionary with a
# scoreline on top — so a number earns its row by changing what a reader thinks about the game
# they just watched, and everything else stays in the Excel export and the dictionary, which
# is what those are for.
#
# ⚠️ THESE ARE THE `offense_*` FAMILY AND THAT WAS DECIDED ON COVERAGE, NOT TASTE. Serving
# carries two advanced families behind two different flags, and they are not equally present:
#
#     has_team_advanced   3,471 games   ← the offense_* / defense_* family, THIS ONE
#     has_box_advanced    1,849 games   ← ppa_overall_total, success_rate_overall_total, …
#     has_box_score       3,543 games
#
# The narrower family would blank this section on 48% of the games that HAVE a box score while
# an equivalent populated column sat beside it. Every field below is present on 6,942 of 6,942
# rows where has_team_advanced is true — measured, not assumed.
#
# ⚠️ AND THE DEFENSIVE MIRROR IS NOT A SECOND FACT. defense_ppa for one side equals
# offense_ppa for the other, to the last decimal — verified on 401752754. Rendering both per
# side would draw the same numbers twice; the defensive reading is the other column, read
# across. The one exception is havoc, which is why defense_havoc_rate appears and
# offense_havoc_rate does not: offense_havoc_rate is havoc SUFFERED by that offence, not
# generated by it, and labelling it as a defensive figure would be exactly wrong.
_ADVANCED_ROWS = (
    ("Predicted points added / play", "offense_ppa", 3),
    ("Success rate", "offense_success_rate", 3),
    ("Explosiveness", "offense_explosiveness", 3),
    ("Success rate, standard downs", "offense_standard_downs_success_rate", 3),
    ("Success rate, passing downs", "offense_passing_downs_success_rate", 3),
    ("PPA, rushing plays", "offense_rushing_plays_ppa", 3),
    ("PPA, passing plays", "offense_passing_plays_ppa", 3),
    ("Power success", "offense_power_success", 3),
    ("Stuff rate", "offense_stuff_rate", 3),
    ("Line yards", "offense_line_yards", 2),
    ("Havoc rate forced by this defence", "defense_havoc_rate", 3),
    # ⚠️ AC-G.33. The denominator, and it is not decoration: every rate above is over these
    # plays, and the two sides do not run the same number of them.
    ("Offensive plays", "offense_plays", 0),
)

_GLOSSARY_FIELDS = tuple(field for _label, field, _dp in _ADVANCED_ROWS)


def _postgame_glossary() -> dict:
    """What each advanced metric means, FROM THE DICTIONARY RATHER THAN FROM THIS FILE.

    ⚠️ PPA, havoc, explosiveness and stuff rate are not common knowledge, and a number a
    reader cannot interpret is worse than no number — it reads as padding. The definitions
    live in srv_data_dictionary (3,675 rows, and all twelve fields below are `authored`), so
    the page shows the same words the Excel export ships. Prose written here is prose that
    drifts from the dictionary.

    One query for all twelve, not one per metric, and `query` caches on the parameter set —
    so this is one read per TTL window across every game anyone opens, not one per render.
    """
    rows = query("""
        select column_name, column_description, is_documented
        from srv_data_dictionary
        where table_name = 'srv_game_team'
          and column_name = any(:fields)
        limit 60
    """, {"fields": list(_GLOSSARY_FIELDS)})
    return {r["column_name"]: r["column_description"]
            for _, r in rows.iterrows()
            if r.get("is_documented") and r.get("column_description")}


def _fraction(row, made_field, of_field) -> str:
    """`6/13`, not a percentage — the app does not divide (G-3)."""
    made, attempted = row.get(made_field), row.get(of_field)
    if pd.isna(made) or pd.isna(attempted):
        return fmt.EM_DASH
    return f"{int(made)}/{int(attempted)}"


def _turnovers(row) -> str:
    total = row.get("turnovers")
    if pd.isna(total):
        return fmt.EM_DASH
    ints, fumbles = row.get("interceptions"), row.get("fumbles_lost")
    parts = []
    if pd.notna(ints):
        parts.append(f"{int(ints)} INT")
    if pd.notna(fumbles):
        parts.append(f"{int(fumbles)} FUM")
    return f"{int(total)}" + (f" ({' · '.join(parts)})" if parts else "")


def _comparison(away, home, rows, glossary=None) -> str:
    """One row per statistic, one column per side. Away left, home right — the same
    convention the scoreline uses and the reason that layout reads as a matchup."""
    lines = []
    for label, field, dp in rows:
        hint = (glossary or {}).get(field)
        # ⚠️ A METRIC WITH NO DEFINITION DOES NOT RENDER AS A BARE NUMBER. It is named as
        # undefined instead, which is a finding a reader can act on rather than padding.
        # <span title=…>, NOT <abbr>: schedule.py has been shipping title attributes on
        # spans since R-085 and they survive Streamlit's sanitiser, which is the only
        # evidence available without a browser. The quotes are double and the text is
        # escaped, because a dictionary description containing an apostrophe would close a
        # single-quoted attribute and spill markup onto the page.
        marked = (f"<span title=\"{html.escape(str(hint), quote=True)}\" "
                  f"style='border-bottom:1px dotted currentColor;cursor:help'>"
                  f"{label}</span>" if hint else
                  f"{label}<span style='opacity:.5' title='Not yet defined in the data "
                  f"dictionary'> (undefined)</span>" if glossary is not None else label)
        lines.append(
            f"<div style='display:flex;align-items:baseline;gap:.5rem;padding:.15rem 0'>"
            f"<span style='min-width:5.5rem;font-weight:600;text-align:right'>"
            f"{_figure(away, field, dp)}</span>"
            f"<span style='flex:1;text-align:center;opacity:.65;font-size:.85rem'>"
            f"{marked}</span>"
            f"<span style='min-width:5.5rem;font-weight:600'>"
            f"{_figure(home, field, dp)}</span></div>")
    return "".join(lines)


def _custom_row(away, home, label, renderer) -> str:
    return (f"<div style='display:flex;align-items:baseline;gap:.5rem;padding:.15rem 0'>"
            f"<span style='min-width:5.5rem;font-weight:600;text-align:right'>"
            f"{renderer(away)}</span>"
            f"<span style='flex:1;text-align:center;opacity:.65;font-size:.85rem'>{label}</span>"
            f"<span style='min-width:5.5rem;font-weight:600'>{renderer(home)}</span></div>")


def _side_heading(away, home) -> str:
    parts = []
    for side, align in ((away, "flex-start"), (home, "flex-end")):
        logo = identity.logo_or_monogram(
            side.get("team_logo_url"), str(side.get("team_display") or "?"), 22)
        parts.append(f"<div style='flex:1;display:flex;align-items:center;gap:.4rem;"
                     f"justify-content:{align}'>{logo}"
                     f"<span style='font-weight:600'>{side.get('team_display') or '?'}</span>"
                     f"</div>")
    return ("<div style='display:flex;align-items:center;margin-bottom:.3rem'>"
            + parts[0] + parts[1] + "</div>")


def _post_game(game_id) -> None:
    """The box score and the advanced block — what happened, once it has happened (R-505).

    ⚠️ THE EMPTINESS TEST IS ON THE VALUES, NOT ON THE FRAME, AND THIS IS THE WHOLE TRAP.
    srv_game_team holds a row for every game back to 1869 and every box-score column is NULL
    in all 202,728 of the pre-2024 ones. So `if df.empty` is FALSE for a 1999 game and the
    obvious version of this panel renders a two-column table of em dashes for 101,354 games —
    exactly what AC-G.6 forbids: "a page must not show 0, an em dash or an empty table where
    the honest answer is 'nothing matched'." The view ships the guard itself: has_box_score,
    has_box_advanced, has_team_advanced and has_havoc are False on every one of those rows.

    ⚠️ AND THE FLAGS ARE INDEPENDENT, so this is not one guard but three. Measured on games
    from 2024 onward: 3,543 have a box score, 3,471 of those have the advanced block and 2,428
    have havoc. A game can therefore have a complete box score and no advanced figures at all,
    which is a Degraded state for that section rather than a reason to hide the panel.
    """
    st.subheader("Box score")
    with states.section("srv_game_team"):
        # ONE READ. Two rows, because the grain is game × team — the limit is the grain
        # restated rather than a guess at a ceiling (AC-G.39).
        df = query(f"""
            select {_POSTGAME_COLUMNS}
            from srv_game_team
            where game_id = :game_id
            limit 2
        """, {"game_id": game_id})

        played = [r for _, r in df.iterrows() if bool(r.get("has_box_score"))]
        if len(played) < 2:
            # EMPTY, ON THE VALUES. Box scores are held from 2024 onward, so a game before
            # that has two rows of nulls rather than no rows, and the honest answer is that
            # we do not hold it rather than a grid of dashes.
            states.empty(
                "The box score would be here.",
                "cfdb holds box scores from 2024 onward, and this game's is not among them.")
            return

        away = next((r for r in played if not bool(r.get("is_home"))), played[0])
        home = next((r for r in played if bool(r.get("is_home"))), played[-1])

        st.markdown(
            _side_heading(away, home)
            + _comparison(away, home, _BOX_SCORE_ROWS)
            + _custom_row(away, home, "Third down",
                          lambda r: _fraction(r, "third_down_conversions",
                                              "third_down_attempts"))
            + _custom_row(away, home, "Fourth down",
                          lambda r: _fraction(r, "fourth_down_conversions",
                                              "fourth_down_attempts"))
            + _custom_row(away, home, "Penalties",
                          lambda r: fmt.number(r.get("penalties"), dp=0))
            + _custom_row(away, home, "Turnovers", _turnovers),
            unsafe_allow_html=True)

        # ⚠️ POSSESSION, WHICH B076 REPORTED AS A SERVING GAP RATHER THAN WORKING AROUND.
        # It carried possession_seconds and nothing else, and 1,906 is not a figure to put in
        # front of a reader; dividing it into 31:46 is arithmetic in the page. A080 published
        # possession_display, the same answer srv_drive gave for durations, so the row exists
        # now and nothing here computes it. Sanity check on 401752665: 29:38 + 30:22 = 60:00.
        st.markdown(
            _custom_row(away, home, "Possession",
                        lambda r: r.get("possession_display") or fmt.EM_DASH),
            unsafe_allow_html=True)

        st.subheader("Advanced")
        # ⚠️ A SEPARATE FLAG, SO A SEPARATE STATE. 72 of the 3,543 games that have a box score
        # do not have this block, and a section that silently vanished would be
        # indistinguishable from one that had never been written.
        advanced = [r for r in played if bool(r.get("has_team_advanced"))]
        if len(advanced) < 2:
            states.empty(
                "The advanced figures would be here.",
                "This game has a box score but no advanced breakdown — the two are collected "
                "separately and one can arrive without the other.")
            table.as_of_caption(df)
            return

        glossary = _postgame_glossary()
        rows = [r for r in _ADVANCED_ROWS
                if r[1] != "defense_havoc_rate" or all(bool(s.get("has_havoc"))
                                                       for s in advanced)]
        st.markdown(
            _side_heading(away, home) + _comparison(away, home, rows, glossary),
            unsafe_allow_html=True)

        missing = [label for label, field, _dp in rows if field not in glossary]
        if missing:
            # A metric the dictionary does not define is named rather than quietly rendered.
            st.caption("Not yet defined in the data dictionary: " + ", ".join(missing) + ".")
        else:
            st.caption(
                "Hover a metric for its definition. Every rate is over that side's own "
                "offensive plays, which are counted on the last row — the two sides do not "
                "run the same number. Definitions come from the data dictionary the Excel "
                "export ships, so the page and the workbook cannot disagree.")
        table.as_of_caption(df)


# --- R-511: who led ---------------------------------------------------------------------

# ⚠️ THE CUT, AND IT WAS MEASURED BEFORE IT WAS CHOSEN. There are 50 category/type pairs per
# game. Coverage and field size are not remotely uniform, measured across 3,542 games:
#
#     category/type      games   avg field   field of one   tied
#     receiving/YDS      100.0%      7.2          0.1%       1.6%   ← the deepest competition
#     rushing/YDS        100.0%      5.6          0.0%       1.3%
#     passing/YDS        100.0%      1.6      ⚠️ 51.2%       0.1%   ← half are a field of ONE
#     defensive/TOT       58.1%     21.4          0.1%    ⚠️ 20.2%   ← the biggest field, and
#                                                                     a fifth end in a tie
#     kicking/*           99.7%      1.1      ⚠️ 91.3%
#     punting/*           99.8%      1.1      ⚠️ 88.8%
#
# ⚠️ KICKING AND PUNTING ARE EXCLUDED ON THAT EVIDENCE, not on taste: at a field of one in
# nine games out of ten, "the kicking leader" is a sentence about a competition that did not
# happen almost every time it is printed.
#
# TOUCHDOWN ROWS ARE EXCLUDED TOO, and for the opposite reason — rushing/TD ties 47.3% of the
# time and receiving/TD 53.3%, because most games have several players with exactly one. A row
# that is a tie more often than not is noise wearing a leaderboard.
#
# ⚠️ DIRECTION IS DECLARED PER ROW AND ALL FOUR ARE `highest_*`. Both ends ship because the
# warehouse does not know which way a stat reads and the page must not decide with arithmetic.
# For yards and tackles, more is the achievement. NOTHING here maps to `lowest_*`: "the player
# who threw the fewest interceptions" is not a leader, it is a sentence nobody wants, so
# passing/INT is omitted rather than inverted or relabelled.
#
# (label, stat_category, stat_type)
_LEADER_ROWS = (
    ("Passing yards", "passing", "YDS"),
    ("Rushing yards", "rushing", "YDS"),
    ("Receiving yards", "receiving", "YDS"),
    ("Tackles", "defensive", "TOT"),
)

_LEADER_KEYS = tuple(f"{category}/{stat}" for _label, category, stat in _LEADER_ROWS)


def _leader_note(row) -> str:
    """⚠️ THE HONESTY THIS PANEL EXISTS TO KEEP. What the number is actually a leader OF.

    `rank_population` is how many players the ranking ran over, and on `passing/YDS` it is
    **1 in 51.2% of team-games** — one team, one passer. "Ty Simpson led Alabama in passing"
    is true and is a claim about a competition that did not happen, and it is on the very
    first game anyone opens (401752665). A panel that prints "led" without reading this
    overclaims more often than not on the row a reader looks at first.

    `highest_tied_players > 1` is the other half of the same problem: 20.2% of `defensive/TOT`
    rows end in a tie, and a name printed alone where three players tied is a different false
    claim. A080 breaks ties with min() so the same name returns on every load — ⚠️ **stable is
    not the same as sole**, and the count is what says which.
    """
    field = row.get("rank_population")
    tied = row.get("highest_tied_players")
    if pd.isna(field) or int(field) <= 1:
        return "only player recorded"
    if pd.notna(tied) and int(tied) > 1:
        return f"tied, {int(tied)} of {int(field)}"
    return f"best of {int(field)}"


def _leader_name(row) -> str:
    """The player's name, linked to their page — or plain text where it cannot be (R-515).

    ⚠️ FOLLOWS team.py's ROSTER LINK RATHER THAN COINING A SECOND ONE. That call site is
    `params.link("players", q=full_name, player=slug, season=season)`, and all three arguments
    are load-bearing: the Players page refuses a search term under two characters, `player`
    picks this athlete out of the matches, and the page is season-scoped. Verified end to end
    against serving — q="Ty Simpson" matches, slug `ty-simpson-4685522` selects, and
    srv_player_stats returns 15 rows across 3 categories for it.

    ⚠️ A NULL SLUG RENDERS PLAIN TEXT, NOT A LINK TO NOWHERE — srv_game.sql's own rule.
    Measured before deciding which of its two cases this is: `highest_player_slug` is null or
    blank on **0 of 296,629 rows**, so the branch is unreachable against today's data. It is
    written anyway because it costs one condition, and because the alternative — discovering
    the object changed by shipping an anchor with an empty destination — is the failure the
    rule exists to name.

    ⚠️ ESCAPED, AND THAT IS NOT DEFENSIVE TYPING: 6,124 leader names carry an apostrophe
    (A'Amear Walton), which would close a single-quoted attribute and spill markup onto the
    page. Double quotes plus html.escape, the same pair B076's tooltips use.
    """
    name = str(row.get("highest_player_name") or "?")
    slug = row.get("highest_player_slug")
    if not slug or (isinstance(slug, float) and pd.isna(slug)) or not str(slug).strip():
        return html.escape(name)
    href = params.link("players", q=name, player=str(slug).strip(),
                       season=row.get("season"))
    return (f"<a href=\"{html.escape(href, quote=True)}\" target=\"_self\" "
            f"style='color:inherit'>{html.escape(name)}</a>")


def _leader_cell(row) -> str:
    """One side's leader for one row: who, how much, and out of what."""
    if row is None:
        return f"<span style='opacity:.45'>{fmt.EM_DASH}</span>"
    value = row.get("highest_stat_value")
    # highest_stat_raw carries the fraction-shaped stats — C/ATT, FG, XP — where there is no
    # numeric value at all (21,183 rows). None of the four rows above is one of those,
    # measured, but the fallback costs a line and means a later addition cannot render blank.
    figure = (fmt.number(value, dp=0) if pd.notna(value)
              else (row.get("highest_stat_raw") or fmt.EM_DASH))
    # ⚠️ NO NESTED ANCHOR. Col's comment records that a row link and a cell link cannot both
    # apply — but these rows are plain divs with no row-level href, so the name is the only
    # anchor here and there is nothing to lose a fight with. Checked before writing it.
    return (f"<div style='font-weight:600'>{_leader_name(row)}</div>"
            f"<div><span style='font-weight:600'>{figure}</span>"
            f"<span style='opacity:.55;font-size:.8rem'> · {_leader_note(row)}</span></div>")


def _leaders(game_id) -> None:
    """Who led each side, read rather than computed (R-511).

    ⚠️ THE RANKING IS NOT DONE HERE AND COULD NOT BE. B076 ended with this item blocked:
    nothing in serving ranked players within a game — `srv_player_stats` ranks at SEASON grain
    and carries no game_id, `srv_player_game_log` carries no rank — so "who led" was a window
    function, which CLAUDE.md puts upstream. A080 built `srv_game_team_leader` at
    (game_id, team_id, stat_category, stat_type), one row per QUESTION ASKED rather than per
    player, with both ends already resolved. This panel reads it with a WHERE and nothing else:
    no `order by`, no `rank(`, no `over (`, no `group by`.

    ⚠️ AND THE CADENCE IS NOT THE BOX SCORE'S, WHICH IS WHY IT CARRIES ITS OWN STAMP. The
    source is `/games/players` in the IMMUTABLE_WK bucket, so this object rebuilds Thursday and
    Sunday rather than two-hourly — deliberately, because a two-hourly rebuild would write
    byte-identical rows, which is the false freshness A078 and A079 spent two rounds removing.
    On a Saturday night the box score above will have moved and this will not. One page-level
    stamp over three blocks with three cadences would be the composition failure AC-G.33 is
    about, so this block says its own.
    """
    st.subheader("Game leaders")
    with states.section("srv_game_team_leader"):
        # ONE QUERY FOR BOTH TEAMS AND ALL FOUR ROWS. srv_game_team_leader is a different
        # relation to the box score's, so this is a second read on the tab and that is correct
        # rather than a G-2 violation — G-2 is one relation per query, not one query per tab.
        # The composite key is filtered in SQL so no cross product of category and type can
        # come back; eight rows is the ceiling and the grain restated (AC-G.39).
        df = query("""
            select season, team_id, team, home_away, stat_category, stat_type,
                   highest_player_name, highest_player_slug, highest_player_id,
                   highest_stat_value, highest_stat_raw, highest_tied_players,
                   rank_population, as_of_ts
            from srv_game_team_leader
            where game_id = :game_id
              and stat_category || '/' || stat_type = any(:keys)
            limit 8
        """, {"game_id": game_id, "keys": list(_LEADER_KEYS)})

        usable = [r for _, r in df.iterrows() if r.get("highest_player_name")]
        if not usable:
            # ⚠️ EMPTY, AND THE FRAME IS GENUINELY EMPTY HERE — WHICH IS THE OPPOSITE OF THE
            # BOX SCORE ABOVE IT. srv_game_team holds an all-NULL row for every game back to
            # 1869, so its emptiness test has to be on the values (AC-G.6, R-509). This object
            # covers 2024-2026 only and returns NO ROWS for anything earlier, so both tests
            # agree here — the value test is still what is written, because a row arriving
            # with no leader on it is the failure the frame check would miss.
            states.empty(
                "Who led each side would be here.",
                "Player-level box scores are collected from 2024 onward, and this game's are "
                "not among them.")
            return

        by_side = {}
        for row in usable:
            by_side[(str(row.get("home_away")), f"{row['stat_category']}/{row['stat_type']}")] \
                = row

        lines = []
        for label, category, stat in _LEADER_ROWS:
            key = f"{category}/{stat}"
            away, home = by_side.get(("away", key)), by_side.get(("home", key))
            if away is None and home is None:
                # ⚠️ PER-ROW ABSENCE IS REAL AND IT IS NOT AN EDGE CASE. defensive/TOT covers
                # 58.1% of games, so tackles are missing on two games in five while the other
                # three rows are present. The row is dropped rather than drawn with two
                # dashes, which would read as "nobody made a tackle".
                continue
            lines.append(
                f"<div style='display:flex;align-items:flex-start;gap:.5rem;"
                f"padding:.3rem 0;border-top:1px solid rgba(128,128,128,.18)'>"
                f"<div style='flex:1;text-align:right'>{_leader_cell(away)}</div>"
                f"<div style='min-width:8rem;text-align:center;opacity:.65;"
                f"font-size:.85rem;padding-top:.15rem'>{label}</div>"
                f"<div style='flex:1'>{_leader_cell(home)}</div></div>")

        away_side = next((r for r in usable if str(r.get("home_away")) == "away"), None)
        home_side = next((r for r in usable if str(r.get("home_away")) == "home"), None)
        heading = _leader_heading(away_side, home_side)
        st.markdown(heading + "".join(lines), unsafe_allow_html=True)

        st.caption(
            "\"best of 8\" is the field the ranking ran over. **\"only player recorded\" means "
            "nobody else on that side registered the stat**, so the figure is a total rather "
            "than a competition won — half of all passing rows are one team, one passer. "
            "\"tied\" means the value is shared and the name shown is one of several.")
        st.caption(
            "Player box scores refresh Thursday and Sunday, so on a game night this block can "
            "sit behind the box score above it.")
        table.as_of_caption(df)


def _leader_heading(away, home) -> str:
    """Team names over their own columns, away left — the scoreline's convention."""
    def name(side):
        return "?" if side is None else (side.get("team") or "?")
    return (f"<div style='display:flex;align-items:center;margin-bottom:.2rem'>"
            f"<div style='flex:1;text-align:right;font-weight:600'>{name(away)}</div>"
            f"<div style='min-width:8rem'></div>"
            f"<div style='flex:1;font-weight:600'>{name(home)}</div></div>")


def _travel(game_id) -> None:
    """How far each side came and how long they had to rest.

    TWO MEASURES WITH DIFFERENT COVERAGE, shown separately rather than blended. Rest comes
    from the schedule and exists for every game that is not a season opener; travel needs
    coordinates for both venues, so it is 2024 onward and about 79% even there. A null
    distance renders as an em dash, never as zero — zero means they played at home.
    """
    st.subheader("Travel and rest")
    with states.section("srv_game_travel"):
        df = query("""
            select team, opponent, is_home, is_neutral_site, game_venue, travel_km,
                   elevation_change_m, rest_days, rest_bucket, previous_game_date, as_of_ts
            from srv_game_travel
            where game_id = :game_id
            order by is_home desc
            limit 2
        """, {"game_id": game_id})
        if df.empty:
            states.empty("How far each side travelled would be here.",
                         "No travel or rest figures for this game.")
            return

        for _, r in df.iterrows():
            side = "Home" if r.get("is_home") else "Away"
            if r.get("is_neutral_site"):
                side = "Neutral site"
            st.markdown(f"**{r.get('team')}** · {side}")
            cols = st.columns(3)
            km = r.get("travel_km")
            cols[0].metric(
                "Travel",
                # Zero is a real answer here and reads as one; null is not.
                "—" if km is None or pd.isna(km)
                else ("Home venue" if float(km) < 1 else f"{float(km):,.0f} km"))
            rest = r.get("rest_days")
            cols[1].metric(
                "Rest",
                "—" if rest is None or pd.isna(rest) else f"{int(rest)} days",
                help=str(r.get("rest_bucket") or ""))
            change = r.get("elevation_change_m")
            cols[2].metric(
                "Elevation change",
                # Signed on purpose: arriving 1,500 m higher and 1,500 m lower are
                # different experiences and a magnitude would erase which happened.
                "—" if change is None or pd.isna(change) else f"{float(change):+,.0f} m")
        table.as_of_caption(df)


# The colour ladder's sourced rungs, mirrored from lib.identity so the caption below says
# "fell back" only when it actually did. `primary`/`alternate` are the team's own; `adjusted`
# and `fallback` are cfdb's, and only those two are debt worth naming.
_SOURCED_COLOR_RUNGS = ("primary", "alternate")


def _drive_colors(df) -> dict:
    """Each band's own colour, recovered from the OTHER band's `opponent_color_*`.

    ⚠️ srv_drive HAS NO `offense_color_*` COLUMNS. Verified against information_schema on the
    serving instance, not read off the model: the identity pair is asymmetric — `offense_*`
    carries team_id, slug, display, mascot and logo_url, and the three contrast colours exist
    on `opponent_*` alone.

    It is still recoverable from ONE game's rows without a join, because possession
    alternates: the home team is the opponent on every away-band drive, and vice versa. So a
    band's colour is read off the complementary band. That is a lookup within the single
    result set this panel already fetched, not a join and not a metric.

    It is also a workaround, and the honest fix is upstream — `offense_color_on_light` /
    `_on_dark` / `_source` on srv_drive, mirroring what opponent_* already has. That is a
    data-layer change and gets its own round; recorded in the B066 report rather than
    smuggled in here.
    """
    colors = {}
    for band in ("home", "away"):
        other = df[df["band"] == ("away" if band == "home" else "home")]
        if other.empty:
            continue
        row = other.iloc[0]
        colors[band] = {"color_on_light": row.get("opponent_color_on_light"),
                        "color_on_dark": row.get("opponent_color_on_dark"),
                        "color_source": row.get("opponent_color_source")}
    return colors


def _drive_bar(row) -> str:
    """The drive drawn on the field, 0 = the offense's own goal line, 100 = the opponent's.

    ⚠️ `start_yards_from_own_goal` and `end_yards_from_own_goal` are the ONLY coordinates both
    bands can share. `yardline` is absolute in the HOME team's frame, so a bar keyed off it
    mirrors the away band and reads as a rendering fault — it disagrees with the
    offense-relative frame on roughly half of all drives.

    ⚠️ AND THE BAR IS NOT `yards` LONG. yards is what the offense gained; the end coordinate
    is where a RETURN finished, and the two disagree on 15% of drives (34% of touchdowns). The
    bar is drawn from the coordinates because the bar is a position, not a gain.

    An off-field end coordinate suppresses the bar and keeps the row: 0.15% of drives carry a
    broken end coordinate, and a missing possession is a worse lie than a bar that admits it
    does not know where it ended.
    """
    start, end = row.get("start_yards_from_own_goal"), row.get("end_yards_from_own_goal")
    if not row.get("is_end_on_field") or pd.isna(start) or pd.isna(end):
        return ("<div style='opacity:.5;font-size:.75rem' "
                "title='CFBD's end coordinate for this drive falls off the field'>"
                "position unavailable</div>")
    lo, hi = sorted((float(start), float(end)))
    backwards = float(end) < float(start)
    fill = "#b45309" if backwards else "#334155"
    return (
        "<div style='position:relative;height:8px;background:rgba(128,128,128,.18);"
        "border-radius:4px' title='own "
        f"{start:g} to {end:g}{' — lost yards' if backwards else ''}'>"
        f"<div style='position:absolute;left:{lo}%;width:{max(hi - lo, 0.8)}%;"
        f"height:8px;background:{fill};border-radius:4px'></div></div>")


def _drives(game_id) -> None:
    """The alternating possession sequence — how the game actually went.

    THE SINGLE MOST LEGIBLE "how did this game go" ARTEFACT (matchup post-game spec §1.4),
    and it was the blocker there: stg_drive had landed and nothing read it. fct_drive and
    srv_drive now exist and are published, so this is the thing that reads them.

    ⚠️ SCORING IS READ FROM `scoring_side`, NEVER FROM THE RESULT TEXT. A `TD` suffix on a
    turnover or a kick means the DEFENCE scored — 908 drives across ten drive_result values,
    measured. Keying an offensive-touchdown mark off the substring "TD" puts every one of
    them on the wrong side of the game.
    """
    st.subheader("Drives")
    with states.section("srv_drive"):
        # Single table, single WHERE, always by game_id — srv_drive is 81,433 rows and the
        # rule that governs srv_matchup governs this.
        #
        # THE LIMIT IS THE CONTRACT, NOT DECORATION. lib.query rejects an unbounded select
        # outright (AC-G.39) and rejected this one while it was being written: "an unbounded
        # select is a defect even where today's filter happens to make it small". 200 is far
        # above the measured ceiling — the longest game in 81,433 rows carries 38 drives,
        # p99.9 is 37, the mean 23.5 — so it bounds the blast radius without ever truncating
        # a real game.
        df = query("""
            select drive_number, band, band_order, is_home_offense,
                   offense_team_display, offense_logo_url,
                   opponent_team_display,
                   opponent_color_on_light, opponent_color_on_dark, opponent_color_source,
                   drive_result, drive_result_category, scoring_side, is_scoring_drive,
                   plays, yards, elapsed_display,
                   start_yards_from_own_goal, end_yards_from_own_goal,
                   is_end_on_field, is_negative_drive,
                   end_offense_score, end_defense_score,
                   as_of_ts
            from srv_drive
            where game_id = :game_id
            order by drive_number
            limit 200
        """, {"game_id": game_id})

        if df.empty:
            # EMPTY, NOT DEGRADED. Drives are collected from 2024 onward, so a 2023 game has
            # none and never will — that is the scope of the data, not a fault in it.
            states.empty(
                "The drive-by-drive sequence would be here.",
                "Drives are collected from 2024 onward, and a game that has not kicked off "
                "yet has none.")
            return

        colors = _drive_colors(df)

        # DEGRADED IS A SEPARATE STATE FROM EMPTY, and this is the one that produces it: the
        # drives are all here, but a side's colour is cfdb's rather than the team's, so the
        # band reads in a neutral grey. Said once, above the sequence, rather than on every row.
        fell_back = sorted({
            str(row.get("opponent_team_display"))
            for _, row in df.iterrows()
            if row.get("opponent_color_source")
            and row["opponent_color_source"] not in _SOURCED_COLOR_RUNGS})
        if fell_back:
            st.caption(
                "Colour for " + ", ".join(fell_back) + " is cfdb's rather than the team's, "
                "so that side is banded in a neutral tone. Every drive below is present.")

        scored = int(df["is_scoring_drive"].fillna(False).astype(bool).sum())
        st.caption(f"{len(df)} drives · {scored} scoring")

        for _, row in df.iterrows():
            # identity.text_on defaults to the on-LIGHT variant, which is what team.py
            # does and the only precedent in the app — there is no theme detection here.
            # Both contrast-safe variants are selected above so the helper chooses, and
            # a missing colour falls to its neutral rather than to anything computed.
            accent = identity.text_on(colors.get(row.get("band")))
            logo = identity.logo_or_monogram(
                row.get("offense_logo_url"), row.get("offense_team_display") or "?", 18)
            # The score AFTER the drive, from the offense's own perspective, so a scoring
            # drive shows what it made the scoreboard say.
            side = row.get("scoring_side")
            mark = ("<span style='font-weight:600'>▲ offence</span>" if side == "offense"
                    else "<span style='font-weight:600'>▼ defence</span>" if side == "defense"
                    else "")
            yards = row.get("yards")
            yards_text = "—" if pd.isna(yards) else f"{int(yards):+d} yd"
            body_row = (
                f"<div style='border-left:4px solid {accent};padding:.35rem .6rem;"
                f"margin-bottom:.25rem;"
                f"background:{'rgba(120,160,120,.13)' if row.get('is_scoring_drive') else 'transparent'}'>"
                f"<div style='display:flex;align-items:center;gap:.5rem;flex-wrap:wrap'>"
                f"<span style='opacity:.55;font-size:.75rem;min-width:1.6rem'>"
                f"{'' if pd.isna(row.get('drive_number')) else int(row['drive_number'])}</span>"
                f"{logo}<span style='font-weight:600'>{row.get('offense_team_display') or '?'}</span>"
                f"<span style='opacity:.85'>{row.get('drive_result') or '—'}</span>{mark}"
                f"<span style='opacity:.6;font-size:.8rem;margin-left:auto'>"
                f"{'' if pd.isna(row.get('plays')) else int(row['plays'])} plays · {yards_text}"
                f" · {row.get('elapsed_display') or '—'}</span></div>"
                f"<div style='margin-top:.25rem'>{_drive_bar(row)}</div></div>")
            st.markdown(body_row, unsafe_allow_html=True)

        table.as_of_caption(df)


def render() -> None:
    shell.render_page("matchup", body)
