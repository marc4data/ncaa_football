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
import re
from collections import namedtuple

import altair as alt
import pandas as pd
import streamlit as st

from lib import (attribution, chips, distribution, filters, fmt, identity, params,
                 shell, states, table)
from lib.datasets import DATASETS
from lib.query import query
from lib.table import Col

# ⚠️ R-591. FOUR OF THE NAMES BELOW ARE A092's, AND THE HEADER COULD RENDER THEM FOR TWO
# ROUNDS WITHOUT SHOWING ONE.
#
# B082 wrote `_MASCOT_COLUMN` and `_SPLIT_RECORD_COLUMN` against columns that did not exist,
# guessing the names A's round would use. A092 shipped all four with exactly those names —
# the handshake held across three rounds with no conversation, because the expectation was
# written as a test rather than as a comment.
#
# 🚨 AND THE FEATURE WAS STILL INVISIBLE, because the SELECT did not ask for them. That is
# R-623's class and this is its second instance: B083 found the first when the market card
# read `favorite_definitions_disagree`, never selected, leaving the disagreement caption dead
# on all 70 games it exists for. Neither was visible to a test, because a hand-built fixture
# supplies every key and is therefore MORE COMPLETE than the query — and
# `ci/check_page_queries.py` cannot see the class at all, since it executes the page's SQL
# and a column the SQL never asks for is not in it to be executed.
# ⚠️ R-645: `spread_move_from_open` and `total_move_from_open` ARE HERE ON PURPOSE. They are
# the move that belongs to the `spread` and `over_under` on the same row — the unprefixed
# family, the one the Excel export has always read — so the card reconciles and the two
# surfaces answer with the same number. The `line_` family below is the excursion's, which is
# one book's snapshot series and names its own book in the caption.
#
# 🚨 AND THE EXPLANATION LIVES OUT HERE RATHER THAN INSIDE THE STRING. A102 put it inside as
# an SQL `--` comment first, and `test_every_column_the_card_reads_is_actually_SELECTED`
# went red: that guard does `COLUMNS.replace("\n", " ").split(",")`, so a comment
# glues itself to the next column name and the column reads as unselected. These were the
# first `--` comments this block had ever carried, so the limitation had never been hit.
# ci/check_page_reads.py parses properly and saw the column fine; the panel-scoped guard is
# the one to keep SQL comments out of.
# ⚠️ NO SQL COMMENT BELONGS INSIDE THIS STRING, AND THAT IS A CI CONSTRAINT RATHER THAN TASTE.
# `ci/check_page_queries.py:122` substitutes this block with `" ".join(value.split())` — it
# FLATTENS the list to one line — so a `--` comment loses the newline that ends it and swallows
# every column after it. B091 put two lines of explanation in here and CI reported
# "matchup.py: syntax error at end of input".
#
# 🚨 IT IS B088's DEFECT FROM THE OTHER SIDE. That round taught B's guard to strip comments
# before parsing this list; the CI checker still cannot, and `ci/` is session A's. Reported
# rather than worked around — and A102 made exactly this move when its comment broke B's guard.
#
# R-605: market_implied_home_points / _away_points were built by fct_market_probability and
# never shown until the board's fourth column, which is why they were absent from this SELECT.
COLUMNS = """
    game_id, season, season_type, week, start_date, venue_display, attendance,
    home_team_id, away_team_id,
    is_completed, is_conference_game, is_neutral_site,
    home_team, home_abbreviation, home_conference, home_logo_url, home_color_on_light,
    home_color_on_dark, home_points, home_wins, home_losses,
    away_team, away_abbreviation, away_conference, away_logo_url, away_color_on_light,
    away_color_on_dark, away_points, away_wins, away_losses,
    spread, spread_open, over_under, over_under_open, home_moneyline, away_moneyline,
    spread_move_from_open, total_move_from_open,
    provider_key, line_snapshot_ts, market_implied_home_win_probability,
    market_implied_away_win_probability, overround, devig_method,
    market_implied_home_points, market_implied_away_points,
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
    home_mascot, away_mascot,
    home_team_home_record_display, away_team_away_record_display,
    is_indoors, spread_favorite_side, moneyline_favorite_side,
    favorite_definitions_disagree,
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
    # ⚠️ `_market` AND `_line_movement` ARE ONE PANEL NOW (R-519). Marc: "Taking up WAY too
    # much space. Develop a card that we can drop in somewhere to cover both."
    (BEFORE, "Before the game",
     ("_series", "_market_and_model", "_yardage", "_travel")),
    # ⚠️ ONE PANEL TODAY, AND THAT IS EXPECTED RATHER THAN UNBALANCED. The box score, the
    # advanced block and the player leaders are B076 — specified in
    # claude_work/cfdb_matchup_postgame_spec.md §1, all three on relations that already
    # exist. Nothing is stubbed here: a stub of an unbuilt thing is a promise the page
    # cannot keep, and it makes the next round impossible to measure.
    (AFTER, "After the game", ("_post_game", "_drives")),
)

# Which argument each panel takes. Named here rather than adapting the panels, because
# changing three signatures so a lookup table can be uniform would rewrite three test files
# to serve a data structure.
_GAME_ID_PANELS = {"_travel", "_drives", "_post_game"}

# ⚠️ AND WHICH ALSO NEED THE SEASON (R-730). Both state an absence whose REASON depends on it
# — before 2024 the data was never collected, from 2024 on it lands after the game — and
# NEITHER the game_id NOR the returned frame can tell those apart: `_drives` gets a genuinely
# empty frame, and `_post_game`'s columns carry no season. The season is on the row `_run_tab`
# already holds, so this needs no query and no new column. `_travel` has one absence and needs
# no season.
#
# ⚠️ `_leaders` WAS THE THIRD ENTRY HERE AND WENT WITH THE SECTION (R-839, B110). Its absence
# note is not lost — the reason it needed the season is the same reason `_post_game` does, and
# that panel now carries the whole After tab's player story.
_SEASON_PANELS = {"_post_game", "_drives"}


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
        if name in _SEASON_PANELS:
            # ⚠️ `int()`, AND B076 IS WHY IT IS NOT DECORATION. A value taken off a DataFrame
            # row arrives as numpy.int64 rather than the int `params.get()` casts. It reaches
            # no driver here, but the cast is the habit that round paid for.
            panel(game_id, int(row["season"]))
        elif name in _GAME_ID_PANELS:
            panel(game_id)
        else:
            panel(row)


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
        # Directly under the header and the full width of it, as Marc asked. It draws only
        # when the book priced a probability, which is 67 of 1,609 upcoming games.
        _win_probability_bar(row)
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
        select game_id, season, week, start_date, game_date,
               home_team, away_team, home_conference, away_conference,
               home_points, away_points, is_completed, venue_display
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and (:conference is null or home_conference = :conference
               or away_conference = :conference)
        order by start_date, game_id
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
            Col("start_date", "Kickoff", "time"),
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


# R-595. CFBD'S OWN VOCABULARY, ENUMERATED FROM THE DATA RATHER THAN GUESSED — all 17 values
# that appear in srv_game_weather, measured 2026-09-11. Cloudy 2,488 · Clear 2,252 · Fair 1,081
# · Light Rain 167 · Rain Shower 155 · Rain 136 · Fog 102 · Overcast 97 · Heavy Rain 89 · Heavy
# Rain Shower 50 · Thunderstorm 10 · Snowfall 9 · Light Snowfall 9 · Heavy Snowfall 2 · Sleet 1
# · Heavy Sleet 1 · Heavy Sleet Shower 1, plus 458 nulls.
#
# 🚨 AN UNMAPPED CONDITION FALLS BACK TO THE WORD, NEVER TO A NEAR-ENOUGH ICON. A wrong icon is
# a confident false statement about the weather at a game, which is the class this project
# keeps removing; the word is merely less pretty. CFBD can add a value tomorrow and this map
# will not know — so it must degrade to text rather than to the closest guess.
_CONDITION_ICON = {
    "clear": "\u2600\ufe0f", "fair": "\U0001f324\ufe0f",
    "cloudy": "\u2601\ufe0f", "overcast": "\u2601\ufe0f",
    "fog": "\U0001f32b\ufe0f",
    "light rain": "\U0001f326\ufe0f", "rain shower": "\U0001f326\ufe0f",
    "rain": "\U0001f327\ufe0f", "heavy rain": "\U0001f327\ufe0f",
    "heavy rain shower": "\U0001f327\ufe0f",
    "thunderstorm": "\u26c8\ufe0f",
    "snowfall": "\U0001f328\ufe0f", "light snowfall": "\U0001f328\ufe0f",
    "heavy snowfall": "\u2744\ufe0f",
    "sleet": "\U0001f328\ufe0f", "heavy sleet": "\U0001f328\ufe0f",
    "heavy sleet shower": "\U0001f328\ufe0f",
}

# ⚠️ MARC'S THRESHOLD, DECLARED RATHER THAN INLINED — R-524's shape. "Only show wind_mph field
# value if >10". Measured: 1,873 of 7,108 readings clear it, so the line stays quiet on about
# three quarters of games, which is the point of having a threshold at all.
_WIND_FLOOR_MPH = 10

# 🚨 R-604. WIND BLOWING SIDEWAYS, AND THE GLYPH IS A CORRECTNESS POINT RATHER THAN A TASTE ONE.
#
# This was U+1F4A8 DASH SYMBOL (💨), which several platforms draw as a curled gust. Marc, from
# the Midwest: "the wind glyph should just be wind blowing sideways. The tornado glyph means
# something different to Midwest folks." ⚠️ A weather line that reads as a TORNADO WARNING on a
# football preview is a confident false statement, which is the class this project keeps
# removing — the same reason an unmapped condition falls back to the word rather than to a
# nearly-right icon.
#
# U+1F32C WIND FACE (🌬️) is the Unicode character whose name and depiction are both literally
# wind blowing sideways, and it is in no weather-warning vocabulary.
_WIND_ICON = "\U0001f32c️"


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
        condition = reading.get("weather_condition")
        if condition:
            icon = _CONDITION_ICON.get(str(condition).strip().lower())
            word = html.escape(str(condition))
            parts.append(f"{icon} {word}" if icon else word)
        # ⚠️ WIND ONLY ABOVE MARC'S FLOOR. A 4 mph reading is not weather anyone is planning
        # around, and printing it on every game is the noise he asked to remove.
        speed = reading.get("wind_speed_mph")
        if pd.notna(speed) and float(speed) > _WIND_FLOOR_MPH:
            # ⚠️ R-604: NO BRACKETS, NO DECIMAL. Marc: "Don't put brackets around the wind.
            # Don't include decimal point for wind." The brackets set the wind apart from the
            # temperature and condition beside it for no reason, and a tenth of a mile per
            # hour is precision nobody plans around — 10.9 and 11 are the same afternoon.
            #
            # ⚠️ R-604's LAST QUARTER. "Do include Direction if it's >10 mph" — the same floor,
            # because a direction is only worth reading when there is wind to have one. The
            # column was said twice to be blocked on a model round and never was:
            # `wind_direction_compass` is on `srv_game_weather`, 7,358 of 7,358 rows carry it,
            # and this query has selected it since B085.
            direction = reading.get("wind_direction_compass")
            heading = f" {html.escape(str(direction))}" if direction else ""
            parts.append(f"{float(speed):.0f} mph{heading} {_WIND_ICON}")

    if not parts and not indoors:
        return ""
    if indoors:
        # The roof first, then the outdoor readings labelled as such — CFBD reports the
        # weather at the venue's LOCATION, not inside it, so a domed game carries ordinary
        # outdoor numbers and printing them bare would state something false.
        return ("<div>Indoors"
                + (f" \u00b7 {' \u00b7 '.join(parts)} outside" if parts else "")
                + "</div>")
    # ⚠️ THE WORD "FORECAST" IS GONE AT MARC'S REQUEST, AND THE TENSE STILL HOLDS: this line
    # is drawn ONLY before kickoff — a completed game's details column is the scoreboard — so
    # there is no observation case for a reader to confuse it with. B082 added the word when
    # the element was new; the surrounding structure now carries the same meaning.
    return f"<div>{' \u00b7 '.join(parts)}</div>"


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


def _details_cell(row, conditions: str = "") -> str:
    """The centre column: the preview's facts before kickoff, the scoreboard after it.

    ⚠️ `conditions` ARRIVES ALREADY FETCHED, inside its own states.section in `_game_header`,
    so that a weather failure degrades one line rather than the page. This never queries.
    """
    played = bool(row.get("is_completed"))
    venue = html.escape(str(row.get("venue_display") or ""))
    if row.get("is_neutral_site"):
        venue += " \u00b7 neutral site" if venue else "neutral site"

    if played:
        return (f"<div style='text-align:center;font-size:.82rem;opacity:.85'>"
                f"<div style='font-weight:600;margin-bottom:.15rem'>Final</div>"
                f"{_line_score(row)}"
                f"<div style='opacity:.75;margin-top:.15rem'>{venue}</div></div>")

    lines = [f"<div style='font-weight:600'>{fmt.local_time(row.get('start_date'))}</div>"]
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

    # ⚠️ R-595: STADIUM ABOVE THE WEATHER, Marc's order. The venue is a fact about the game and
    # the weather is a fact about the day; he reads them in that order.
    if venue:
        lines.append(f"<div style='opacity:.75'>{venue}</div>")
    if conditions:
        lines.append(conditions)
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
    # 🚨 ITS OWN SECTION, AND B082 SHIPPED WITHOUT ONE. When the weather panel was standalone
    # it carried `states.section("srv_game_weather")`, so a weather failure degraded one
    # block. Folding it into the header left the query bare inside body()'s
    # `states.section("srv_game")` — which means a missing or broken srv_game_weather would
    # have rendered the Error state for the WHOLE PAGE, naming srv_game: a confident and
    # wrong diagnosis of a different view's problem. Restored here — if the fetch fails the
    # section says so above the header and the header still draws, without conditions.
    #
    # ⚠️ NO `dataset=`. The header reads TWO datasets — srv_game and srv_game_weather — and
    # captioning it with one would be R-574's defect (a caption that disagrees with what the
    # block actually reads) in a new place. Reported rather than papered over.
    conditions = ""
    if not played:
        with states.section("srv_game_weather"):
            conditions = _conditions(row)
    columns = st.columns(_HEADER_WEIGHTS, vertical_alignment="center")
    cells = (
        identity.logo_or_monogram(row.get("away_logo_url"),
                                  str(row.get("away_team") or "?"), 44),
        _team_cell(row, "away", "right"),
        _score_cell(row.get("away_points"), played),
        _winner_glyph(row, "away"),
        _details_cell(row, conditions),
        _winner_glyph(row, "home"),
        _score_cell(row.get("home_points"), played),
        _team_cell(row, "home", "left"),
        identity.logo_or_monogram(row.get("home_logo_url"),
                                  str(row.get("home_team") or "?"), 44),
    )
    for column, markup in zip(columns, cells):
        with column:
            st.markdown(markup, unsafe_allow_html=True)


# --- R-526: what the market gives each side ------------------------------------------------

# ⚠️ MARC ASKED FOR THE AWAY SEGMENT IN WHITE AND WHITE FAILS IN LIGHT THEME — a white bar on
# a near-white page is an invisible segment, and R-547 was exactly that class: a hardcoded
# colour answering the operating system rather than the app. This is theme.py's own
# vocabulary, so the neutral side tracks the reader's theme in both directions.
_NEUTRAL_FILL = "color-mix(in srgb, CanvasText 26%, Canvas)"


def _win_probability_bar(row) -> None:
    """R-526. One stacked bar, away on the left, home on the right.

    🚨 IT IS THE MARKET'S NUMBER AND THE LABEL SAYS SO. §4.3: `market_implied_` names the
    PROVENANCE, and it is a licence boundary wearing a naming convention. A bar labelled
    "Win probability" reads as cfdb's own model — it is not, and cfdb's own
    `home_win_probability` is NULL in all 111,049 rows (R-572), which is why the model panel
    stops drawing it in this same round. The two must never be mistaken for one number moving.

    ⚠️ IT COLLAPSES TO NOTHING WHEN THE BOOK PRICED NO PROBABILITY, and that is the common
    case rather than the edge one: measured on the only state this bar renders in — UPCOMING
    games — it is 67 of 1,609. The weather element one block up had to learn the same lesson.

    ⚠️ THE PROBABILITIES ARE READ, NEVER COMPUTED. Marc sketched "the favorite's implied
    probability, and 1 − p for the underdog", which assigns the whole vig to one side; the
    built columns normalise both (multiplicative de-vig, `devig_method` stored beside them).
    Doing either sum in this file would be metric maths in the app (G-3) as well as wrong.

    ⚠️ NO TEXT SITS ON EITHER FILL. A team colour cannot be trusted to contrast with text —
    that is what `identity.text_on` exists for — so the labels sit BELOW the bar and the
    segments carry colour alone. `_drive_bar` on this same page already fills with a team
    colour and puts nothing on it; this follows that rather than inventing a second rule.
    """
    home_p = row.get("market_implied_home_win_probability")
    away_p = row.get("market_implied_away_win_probability")
    if pd.isna(home_p) or pd.isna(away_p):
        return
    home_pct, away_pct = float(home_p) * 100, float(away_p) * 100

    away_label = html.escape(str(row.get("away_abbreviation")
                                 or row.get("away_team") or "Away"))
    home_label = html.escape(str(row.get("home_abbreviation")
                                 or row.get("home_team") or "Home"))
    home_fill = identity.text_on(row_for_side(row, "home"))

    st.markdown(
        f"<div style='margin:.15rem 0 .1rem'>"
        f"<div style='display:flex;height:10px;border-radius:5px;overflow:hidden'>"
        f"<div style='width:{away_pct:.4f}%;background:{_NEUTRAL_FILL}'></div>"
        f"<div style='width:{home_pct:.4f}%;background:{home_fill}'></div></div>"
        f"<div style='display:flex;justify-content:space-between;font-size:.78rem;"
        f"opacity:.8;margin-top:.15rem'>"
        f"<span>{away_label} {away_pct:.1f}%</span>"
        f"<span>{home_label} {home_pct:.1f}%</span></div>"
        f"<div style='text-align:center;font-size:.72rem;opacity:.55;margin-top:.05rem'>"
        f"Market-implied win probability, de-vigged from the moneylines \u2014 the book's "
        f"number, not cfdb's model</div></div>",
        unsafe_allow_html=True)


def row_for_side(row, side: str):
    """The colour pair `identity.text_on` expects, for one side of a game row.

    srv_game carries `home_color_on_light` / `away_color_on_dark` and friends; text_on wants
    a mapping with `color_on_light` / `color_on_dark`. This renames rather than computing —
    there is no contrast maths here, and a missing colour falls back inside text_on.
    """
    return {"color_on_light": row.get(f"{side}_color_on_light"),
            "color_on_dark": row.get(f"{side}_color_on_dark")}


# --- R-519: the market and its movement, in one card ---------------------------------------

# ⚠️ ▲/▼ WITH AN UNSIGNED MAGNITUDE, AND THE CHOICE IS NOT COSMETIC.
#
# Marc asked for "a small up/down arrow beside each, with the amount it moved". The Schedule
# card deliberately went the other way — `schedule.py:167`, MOVE_GLYPH = "Δ", with the reason
# stated: "Δ rather than ▷: the direction is already carried by the sign, and a directional
# glyph beside a negative number is two cues that can disagree."
#
# That objection is real and this project has the scar: R-544 was a sign convention rendering
# backwards on every graded game. So the arrow ships as Marc asked, and the objection is
# ANSWERED rather than overruled — the magnitude beside it is UNSIGNED, so there is exactly
# one direction cue on the page and nothing for it to disagree with.
#
# ⚠️ THE SIGN CONVENTION IS THE COLUMN'S, NOT OURS. `line_spread_move_from_open` is current
# minus opening, so ▲ means the number went UP: for a spread that is the home team being
# favored by LESS than it was. The card says so in words rather than assuming it reads.
MOVE_UP, MOVE_DOWN = "\u25b2", "\u25bc"


def _move_chip(value, column: str) -> str:
    """One movement: a direction glyph and an unsigned amount, or nothing at all.

    Returns "" for a null so the caller can omit the chip rather than draw a dash — a line
    that never moved and a line with no opening price on record are different statements, and
    only the second one is an absence.
    """
    if value is None or pd.isna(value):
        return ""
    if float(value) == 0:
        return "<span style='opacity:.5'>unmoved</span>"
    glyph = MOVE_UP if float(value) > 0 else MOVE_DOWN
    # abs() moves the direction into the glyph. It is a presentation transform on one column,
    # not a metric: nothing is summed, divided or compared (G-3).
    return (f"<span style='opacity:.7'>{glyph} "
            f"{fmt.number(abs(float(value)), column)}</span>")


def _favorite(row):
    """WHICH SIDE THE SPREAD MAKES THE FAVORITE — read, never derived.

    🚨 THERE ARE TWO DEFINITIONS AND THE WAREHOUSE KNOWS THEY DISAGREE. `spread_favorite_side`
    and `moneyline_favorite_side` answer the same question of different markets, and
    `favorite_definitions_disagree` flags the games where they differ — 70 rows, and 28 of
    them in 2025 alone. Deriving a favorite from the sign of `spread` in this file would
    silently pick a side of a question the model has already recorded as open.

    ⚠️ NULL IS THE COMMON CASE, NOT THE EDGE ONE: 2,234 of 2025's 3,831 games carry no
    favorite side at all, because most were never priced.
    """
    side = row.get("spread_favorite_side")
    if side not in ("home", "away"):
        return None, None
    label = row.get(f"{side}_abbreviation") or row.get(f"{side}_team") or side
    return side, str(label)


# R-597. THE THREE BOOKS CFBD ACTUALLY NAMES, measured: bovada 1,881 games · espn_bet 1,382 ·
# draftkings 147 on srv_game, and the same three on srv_line_movement with their display names.
#
# ⚠️ NO PROVIDER URL EXISTS ANYWHERE IN THE WAREHOUSE, so this map is the page's own and Marc
# asked for the link explicitly. It stays in this file until a SECOND page wants it — A091's
# labels earned `site/lib/` because Today and Matchup needed them at the same moment, and one
# page does not earn a shared module.
#
# 🚨 AN UNMAPPED PROVIDER RENDERS ITS NAME, NOT A DEAD LINK. A link that 404s is worse than
# plain text, and CFBD can add a book tomorrow.
_PROVIDER_SITE = {
    "bovada": ("Bovada", "https://www.bovada.lv"),
    "espn_bet": ("ESPN Bet", "https://espnbet.com"),
    "draftkings": ("DraftKings", "https://sportsbook.draftkings.com"),
}

# R-597. Marc: "a little question mark icon (like in the Rest label in the Travel and Rest
# section)… next to Market/Spread/Over/Under", with the prose moved off the card.
#
# ⚠️ THE REST LABEL'S ICON IS `st.metric(help=...)` AND THIS CARD CANNOT USE IT. A metric is a
# tile, and tiles are what Marc asked to remove from this card in the same review — "shrink
# horizontal footprint so that it can share the row with another element". So the icon is a
# `title=` span, which is the same affordance at a fraction of the height. Recorded because it
# is a deliberate deviation from the precedent he named, not an oversight.
#
# 🚨 R-607 DECIDED WHAT BELONGS HERE, AND THE TEST IS GENERIC VERSUS THIS GAME. Marc: "It should
# be generic info about what the metrics mean, not specific info about the lines for the Matchup.
# That will gain back a lot of vertical real estate b/c I think there is way too much text about
# Market."
#
# ⚠️ SO THE RULE IS A PROPERTY OF THE SENTENCE, NOT OF ITS LENGTH. A sentence that would read
# identically on every game in the database is generic and belongs in a hover; a sentence that
# names THIS row's overround, THIS row's disagreeing books or THIS row's unusable price is a
# statement of fact about the game on screen and STAYS ON THE CARD. Deleting one of those would
# be a regression wearing the costume of a tidy-up — B083's disagreement caption exists because
# the spread and the moneyline name different sides on 70 games, and A094 found a game priced
# −100000/−100000 rendering as a confident 50.0%.
_HELP = {
    "Market": "Every figure on this card is one book's price. A move measured against a "
              "different book's price is not a move.",
    # R-607: the card no longer CALLS `chips.spread_sign_note`, it consumes the same constant
    # in a hover instead — see `_spread_help`. Composed rather than copied, because R-009's
    # whole point is one sentence in one place and retyping it here would have recreated the
    # drift it exists to prevent.
    "Spread": None,
    "Over/Under": "The total points the book expects both teams to score combined.",
    # R-605. The board's fourth column is DERIVED, and the hover is where that is said once.
    "Implied points": "What the book's total and spread imply each team scores. cfdb derives "
                      "this from the two of them — it is not a price any book quoted, and no "
                      "book took a bet on it.",
    # R-607: what a de-vig IS. What THIS game's overround WAS stays on the card beside it.
    "Win probability": "A book's prices carry its margin, so the two sides imply more than "
                       "100% between them. De-vigging removes that margin proportionally to "
                       "recover what the price says about the game. The overround is how much "
                       "margin there was — 1.0000 would be a book taking none. These are the "
                       "book's numbers, not cfdb's model.",
}


def _spread_help() -> str:
    """The spread's hover: the SHARED sign note, plus what the arrow beside it means.

    🚨 COMPOSED FROM `chips.SPREAD_SIGN_NOTE`, NEVER RETYPED. R-009 put that sentence in one
    place because the same sign appears on Schedule, Scores and Matchup and three copies are
    three chances to drift. R-607 moved Matchup's rendering of it from a caption into this
    hover — which changes WHERE it is shown, and must not change the fact that there is one
    of it.

    ⚠️ THE `**` COMES OUT because a `title=` attribute is plain text, not markdown, and would
    otherwise show the asterisks. `schedule.py` does the same thing for the same reason when
    it puts the note inside an HTML block.
    """
    note = re.sub(r"\*\*(.+?)\*\*", r"\1", chips.SPREAD_SIGN_NOTE)
    return (f"Points given by the favorite. {note} The arrow is how far the number has "
            f"traveled since it opened, and the amount beside it carries no sign because the "
            f"arrow already has the direction.")


def _help_icon(key: str) -> str:
    """The question mark, with its prose in the browser's own tooltip."""
    text = html.escape(_HELP[key] or _spread_help(), quote=True)
    return (f"<span title='{text}' style='cursor:help;opacity:.45;font-size:.7rem;"
            f"vertical-align:super'>?</span>")


def _provider_link(row, key_column: str = "provider_key") -> str:
    """The book, as a link where we know one — NOT suppressed into the hover.

    Marc: "Should include (don't suppress to the question mark hover) the Provider for the
    line we are using. Present as the name of Provider as a hyperlink to their site."

    🚨 R-645: WHICH KEY IS THE CALLER'S TO SAY, AND IT USED TO GUESS. This preferred
    `line_movement_provider_key` whatever the number beside it came from, so the market card
    named DraftKings while displaying Bovada's price. The two keys differ on 1,739 of the
    1,886 games that carry both — 92% — so the guess was wrong far more often than it was
    right. The default is the family the card displays; the excursion caption passes its own.
    """
    key = row.get(key_column) or row.get("provider_key")
    if not key:
        return "an unnamed book"
    name, url = _PROVIDER_SITE.get(str(key), (None, None))
    if not name:
        # Unknown book: its key is still a fact, and a name we do not have is not a link.
        return html.escape(str(key))
    return (f"<a href='{url}' target='_blank' rel='noopener noreferrer'>"
            f"{html.escape(name)}</a>")


# ⚠️ EACH HEADER KEEPS B090's `?`, AND THE SECOND ELEMENT IS WHICH HOVER IT OPENS. R-607 put
# the generic prose behind these icons; a board that dropped them would delete that work while
# looking tidier, so the column names carry them rather than the old row labels.
_BOARD_COLUMNS = (
    ("Point Spread", "Spread"),
    ("Moneyline", "Win probability"),
    ("Total", "Over/Under"),
    ("Implied points", "Implied points"),
)


def _chip(main: str, under: str = "") -> str:
    """One bordered cell. The big number, and the small one beneath it.

    🚨 THE SMALL SLOT IS WHERE A BOOK PRINTS THE PRICE, AND WE DO NOT HAVE ONE. The reference
    board shows `-110` beside every spread and total; `stg_lines` parses no spread price and
    no total price, so there is nothing to render there and inventing one would be a fabricated
    market number on a betting page. ✅ Marc solved it without saying so — he asked for the
    spread "with Delta Change, smaller", so the MOVE goes where the vig goes.
    """
    below = (f"<div style='font-size:.7rem;opacity:.6;margin-top:.1rem'>{under}</div>"
             if under else "")
    return (f"<div style='border:1px solid var(--cfdb-border, rgba(128,128,128,.28));"
            f"border-radius:5px;padding:.3rem .45rem;text-align:center;min-width:4.6rem'>"
            f"<div style='font-weight:600;font-size:.95rem'>{main}</div>{below}</div>")


def _board_row(row, side: str, spread_final, is_favorite: bool) -> str:
    """One team's line across the four columns."""
    name = (row.get(f"{side}_abbreviation") or row.get(f"{side}_team") or side)

    # POINT SPREAD — per side, from the column. The favorite carries the negative number and
    # the underdog carries the mirror, which is what `spread_final` already is on each row.
    # ⚠️ NOT DERIVED FROM THE SIGN OF `spread`: B083 established there are two definitions of
    # "favorite" and the warehouse records when they disagree.
    spread_cell = _chip(
        fmt.signed(spread_final, "spread") if pd.notna(spread_final) else "—",
        _move_chip(row.get("spread_move_from_open"), "spread_move_from_open"))

    # MONEYLINE — the price, with this side's implied win probability beneath it.
    price = row.get(f"{side}_moneyline")
    implied = row.get(f"market_implied_{side}_win_probability")
    # ⚠️ RED ON THE FAVORITE IS DECORATION, NOT THE SIGNAL (AC-G.22). The sign already says
    # which side is favored, so a reader in greyscale loses nothing.
    tint = " color:var(--cfdb-negative, #b3261e)" if is_favorite else ""
    money_cell = _chip(
        f"<span style='{tint}'>{fmt.signed(price, '', dp=0)}</span>"
        if pd.notna(price) else "—",
        f"{float(implied) * 100:.1f}%" if pd.notna(implied) else "")

    # TOTAL — 🚨 SPLIT ACROSS THE TWO ROWS, NOT REPEATED. `O 43.5` on the away row and
    # `U 43.5` on the home row, which is what the reference board does and what makes the two
    # rows a board rather than two copies of one number.
    total = row.get("over_under")
    total_cell = _chip(
        f"{'O' if side == 'away' else 'U'} {fmt.number(total, 'over_under')}"
        if pd.notna(total) else "—",
        _move_chip(row.get("total_move_from_open"), "total_move_from_open"))

    # IMPLIED POINTS — 🚨 ONE NUMBER, NEVER AN O/U PAIR. The reference's Team Total is a priced
    # market with an over and an under; cfdb's is DERIVED from the total and the spread. Drawing
    # it as two chips would dress a derivation as a quoted market (§4.3, the R-571 class), so it
    # is one chip and the column is labelled "Implied points".
    points = row.get(f"market_implied_{side}_points")
    points_cell = _chip(fmt.number(points, "", dp=1) if pd.notna(points) else "—")

    return (f"<div style='display:grid;grid-template-columns:6.5rem repeat(4, 1fr);"
            f"gap:.35rem;align-items:center;padding:.2rem 0'>"
            f"<div style='font-weight:600;font-size:.9rem'>{html.escape(str(name))}</div>"
            f"{spread_cell}{money_cell}{total_cell}{points_cell}</div>")


def _board(row) -> str:
    """R-605. Marc's board: two rows, AWAY over HOME, four columns, every cell a chip.

    ⚠️ THE REFERENCE IS A SPORTSBOOK SCREENSHOT AND THREE OF ITS COLUMNS ARE NOT OURS —
    the `-110` prices, Team Total as a bettable O/U pair, and the rotation numbers. Each is
    handled where it arises rather than designed around; see `_chip` and `_board_row`.

    ⚠️ `23.5`, NOT `23½`. The reference writes fractions and cfdb writes decimals everywhere
    else; that is a site-wide convention and Marc has not asked to change it.

    ⚠️ NO KICKOFF TIME. It sits in the reference's header strip and the game header above
    already renders it.
    """
    teams = _game_team_rows(int(row["game_id"]))
    side_of = {}
    for side in ("away", "home"):
        team_id = row.get(f"{side}_team_id")
        side_of[side] = teams.get(int(team_id)) if pd.notna(team_id) else None

    favorite_side = row.get("spread_favorite_side")
    header = ("<div style='display:grid;grid-template-columns:6.5rem repeat(4, 1fr);"
              "gap:.35rem;padding-bottom:.2rem;font-size:.7rem;opacity:.55'>"
              "<div></div>"
              + "".join(f"<div style='text-align:center'>{label}"
                        f"{_help_icon(key)}</div>"
                        for label, key in _BOARD_COLUMNS)
              + "</div>")

    body_rows = "".join(
        _board_row(row, side,
                   None if side_of[side] is None else side_of[side].get("spread_final"),
                   favorite_side == side)
        for side in ("away", "home"))

    return (f"<div style='border:1px solid var(--cfdb-border, rgba(128,128,128,.3));"
            f"border-radius:6px;padding:.55rem .7rem;margin:.2rem 0'>"
            f"{header}{body_rows}{_card_footer(row)}</div>")


def _card_footer(row) -> str:
    """R-606. Whose prices these are and when they were gathered, as the card's own footer.

    Marc: "Footer underneath the card should indicate Provider and when the last metric
    snapshot was gathered." ✅ A102 already made the card name its book; this turns a caption
    into furniture, which is the direction that buys the vertical space R-607 is about.

    ⚠️ AC-G.35 — THE *AS OF* IS A COLUMN, NEVER `now()`. `line_snapshot_ts` is when the book's
    price was observed, and it travels with the price rather than with the render.

    🚨 AND IT IS THE CARD'S OWN BOOK, WHICH IS NOT OBVIOUS FROM THE COLUMN NAME. `srv_game`
    exposes ONE timestamp under TWO names — `l.snapshot_ts as line_snapshot_ts, l.snapshot_ts`
    — and both come from `latest_line`, the same CTE as `provider_key`. Verified rather than
    assumed: the two columns are identical in all 112,675 rows, so despite the `line_` prefix
    this is the displayed price's own snapshot and not the movement series'. ⚠️ That mattered
    because `line_movement_provider_key` names a DIFFERENT book on 1,739 of 1,920 games, and
    pairing this stamp with the card's book would have been R-645 all over again if the prefix
    had meant what it looks like.
    """
    book = _provider_link(row)
    stamp = row.get("line_snapshot_ts")
    when = (f" · snapshot {html.escape(fmt.local_time(stamp))}"
            if pd.notna(stamp) else "")
    # ⚠️ THE COUNT RIDES ALONG BECAUSE IT IS A FACT ABOUT THIS ROW AND IT HAD NOWHERE ELSE TO
    # GO. The caption this footer replaces carried it, and `_excursions` is SILENT when there
    # is no history at all — so dropping it would have quietly deleted "we have one look at
    # this line", which is the difference between a line that has not moved and a line nobody
    # watched. It costs no extra height here.
    snapshots = row.get("line_snapshot_count")
    seen = ""
    if pd.notna(snapshots):
        observed = int(snapshots)
        seen = f" · {observed} snapshot{'' if observed == 1 else 's'}"
    else:
        seen = " · no snapshot history"
    return (f"<div style='border-top:1px solid var(--cfdb-rule, rgba(128,128,128,.25));"
            f"margin-top:.35rem;padding-top:.3rem;font-size:.75rem;opacity:.6'>"
            f"Line from {book}{when}{seen}</div>")


def _market_and_model(row) -> None:
    """R-596. The market card and the model, sharing one row.

    Marc: the card was "taking up way too much real estate… shrink horizontal footprint so
    that it can share the row with another element", and "Model — move to the right of Market,
    so they share the same row."

    ⚠️ THIS IS A LAYOUT CHANGE, NOT A REBUILD. The card shipped one round ago and was right for
    a full-width slot; `cfdb_card_vocabulary.md` still governs its parts. Both panels keep
    their own `states.section`, so one failing still degrades one half rather than the row.
    """
    left, right = st.columns(2)
    with left:
        _market_card(row)
    with right:
        _model(row)


def _market_card(row) -> None:
    """R-519. One card for the market and how it moved.

    Marc: "Taking up WAY too much space. Develop a card that we can drop in somewhere to
    cover both." This replaces `_market` and `_line_movement`, which between them drew ten
    st.metric tiles and five captions.

    ⚠️ IT FOLLOWS THE SCHEDULE CARD'S LINE BLOCK RATHER THAN INVENTING A SECOND GRAMMAR:
    label, line, movement — one row per market, the two moneylines on their own row, and the
    provenance last. `cfdb_card_vocabulary.md` names those parts and this uses the names.

    NO SECOND QUERY. Every column is already on the srv_game row the page fetched.
    """
    st.markdown(f"### Market {_help_icon('Market')}", unsafe_allow_html=True)
    # One section for the whole card, as `_line_movement` had: these are columns the rest of
    # the page does not read, so a failure here degrades the card rather than blanking a
    # Matchup that is otherwise complete.
    with states.section("srv_game", dataset=DATASETS["srv_game"]):
        has_line = pd.notna(row.get("spread")) or pd.notna(row.get("over_under"))
        has_money = pd.notna(row.get("home_moneyline")) or pd.notna(row.get("away_moneyline"))
        if not has_line and not has_money:
            # Most of 110,634 games predate betting data entirely, which is an absence of
            # market rather than a failure to fetch one.
            states.empty("The betting market would be here.",
                         "No sportsbook line has been recorded for this game. "
                         "cfdb holds lines from 2013 onward, and only for games books priced.")
            return

        rows = []
        side, favorite = _favorite(row)
        if pd.notna(row.get("spread")):
            if favorite:
                # THE SPREAD IS SHOWN FROM THE FAVORITE'S SIDE, which is how Marc reads it and
                # how a book prints it. The magnitude is the same number either way; only the
                # name in front of it changes, and it comes from the column rather than from
                # the sign.
                line = f"{favorite} {fmt.number(-abs(float(row['spread'])), 'spread')}"
            else:
                # No favorite side recorded, so the number is stated as the column defines it
                # — from the home perspective — and labelled that way rather than guessed.
                home = row.get("home_abbreviation") or row.get("home_team") or "home"
                line = f"{html.escape(str(home))} {fmt.signed(row.get('spread'), 'spread')}"
            # 🚨 R-645: THE MOVE COMES FROM THE SAME ROW AS THE PRICE ABOVE IT.
            #
            # This chip used to read `line_spread_move_from_open` while the number beside it
            # came from `spread` — two different books, in one row, and the row did not even
            # add up: Marc's 401856679 showed Bovada's 5 next to DraftKings' 7.0, when
            # 5 − (−1.5) is 6.5. Excel read the unprefixed column and showed 6.5, so the two
            # surfaces disagreed about a fact on a betting page.
            #
            # ⚠️ AND THE CAPTION BELOW ALREADY STATED THE RULE THIS BROKE: "a move measured
            # against a different book's price is not a move."
            #
            # Measured 2026-09-11: the two families disagree on 1,107 of the 1,332 games that
            # carry both — 83% — and name a different book on 1,739 of 1,886 — 92%. The
            # unprefixed family wins because it is what `spread` and `over_under` above
            # already are, so the row reconciles; because the Excel export already reads it
            # and already labels it `Book`; and because it covers 330 games the `line_`
            # family does not, which would otherwise lose their chip entirely.
            rows.append(("Spread", line,
                         _move_chip(row.get("spread_move_from_open"),
                                    "spread_move_from_open")))
        if pd.notna(row.get("over_under")):
            rows.append(("Over/Under", fmt.number(row.get("over_under"), "over_under"),
                         _move_chip(row.get("total_move_from_open"),
                                    "total_move_from_open")))

        st.markdown(_board(row), unsafe_allow_html=True)

        if bool(row.get("favorite_definitions_disagree")):
            # 🚨 70 GAMES, AND THE CARD SAYS SO RATHER THAN PICKING ONE. The spread and the
            # moneyline can name different favorites — a near-pick'em priced slightly
            # differently in the two markets — and the model records the disagreement instead
            # of resolving it. Presenting one silently would be the page deciding something
            # the warehouse deliberately left open.
            other = row.get("moneyline_favorite_side")
            other_label = (row.get(f"{other}_abbreviation") or row.get(f"{other}_team")
                           if other in ("home", "away") else None)
            st.caption(
                f"The spread makes {favorite or 'one side'} the favorite and the moneyline "
                f"makes {html.escape(str(other_label)) if other_label else 'the other'} the "
                f"favorite. cfdb records the disagreement rather than resolving it.")

        # 🚨 R-607: `chips.spread_sign_note()` USED TO RENDER HERE AND ITS TEXT IS NOW IN THE
        # SPREAD `?`. It is true of every spread ever printed, which is the definition of
        # generic, and it sat under a card that already carried a question mark for exactly
        # that sentence.
        #
        # ⚠️ THE SHARED COMPONENT IS UNTOUCHED. `lib/chips.py` is session A's (§3 rule 3) and
        # Schedule and Scores still call it; what changed is this call site, which is mine.
        _market_provenance(row)
        _excursions(row)


def _market_provenance(row) -> None:
    """Whose prices these are, and the de-vig if the book priced a probability.

    Every figure on the card is ONE book's by construction. A price with no book attached is
    the provenance defect the `market_implied_` prefix rule exists to prevent, and it renders
    perfectly while being wrong.
    """
    implied = row.get("market_implied_home_win_probability")
    if pd.notna(implied):
        # 🚨 R-607: THE NUMBERS, NOT THE LECTURE. What a de-vig IS moved into the
        # "Win probability" help; what THIS row's overround WAS is a fact about this game and
        # cannot go into generic copy without ceasing to be true of it.
        st.caption(
            f"Implied home win probability {float(implied) * 100:.1f}% "
            f"(away {float(row.get('market_implied_away_win_probability')) * 100:.1f}%) "
            f"{_help_icon('Win probability')} · overround "
            f"{fmt.number(row.get('overround'), '', 4)}, de-vigged by "
            f"{row.get('devig_method')}.", unsafe_allow_html=True)


def _excursions(row) -> None:
    """R-519 §1.3. The widest excursions, as ONE line under the card.

    ⚠️ MARC DID NOT ASK FOR THESE AND DID NOT DROP THEM EITHER, so they keep their content and
    lose their three metric tiles. Cowork's call, and the height they now cost is one caption.

    ⚠️ B074'S CAVEAT DECIDES WHETHER THE LINE RENDERS AT ALL. On a single-snapshot game the
    furthest the line got and its net move are THE SAME NUMBER by construction — 1,577 of
    1,854 rows carry one snapshot — so presenting them as two measurements would be inventing
    a second fact. On those games the line is not drawn; the caption says why instead.
    """
    snapshots = row.get("line_snapshot_count")
    if pd.isna(snapshots):
        return
    if int(snapshots) == 1:
        st.caption("This game's line was observed once, so its widest excursion is the net "
                   "move restated rather than a separate measurement.")
        return
    parts = []
    for label, column in (("spread", "line_spread_largest_excursion"),
                          ("total", "line_total_largest_excursion")):
        if pd.notna(row.get(column)):
            parts.append(f"{label} {fmt.signed(row.get(column), column)}")
    probability = row.get("line_market_implied_win_probability_largest_excursion")
    if pd.notna(probability):
        parts.append(f"win probability {fmt.signed(probability, '', dp=2)} points")
    if not parts:
        return
    floor_note = ""
    if bool(row.get("line_movement_spans_snapshot_gap")):
        # The line was tracked across the three days in 2026 that hold no snapshots, so the
        # excursion is a FLOOR — it may have travelled further unobserved — and a floor
        # presented as a measurement is the defect this caveat exists to prevent.
        floor_note = (" These are floors rather than measurements: this game's line was "
                      "tracked across the three days that hold no snapshots.")
    # 🚨 R-645: THIS BLOCK IS THE OTHER BOOK'S, AND IT NOW SAYS SO.
    #
    # The excursion set is deliberately one book's snapshot series — srv_game.sql prefixes it
    # `line_` for exactly that reason, because pairing an excursion with a different book's
    # price "would be partly the spread between books rather than anything the market did".
    # ⚠️ THAT ARGUMENT IS SOUND AND IT IS WHY THIS STAYS ON THE `line_` FAMILY. What was
    # missing is that the card above now reads the unprefixed family, and the two name a
    # DIFFERENT BOOK on 1,739 of the 1,886 games that carry both — 92%. A panel that quietly
    # switches books between one caption and the next is the defect this round removes, so
    # the book is named here whenever it is not the one the card already named.
    movement_book = row.get("line_movement_provider_key")
    card_book = row.get("provider_key")
    whose = ""
    if movement_book and movement_book != card_book:
        whose = (f" Measured on {_provider_link(row, 'line_movement_provider_key')}, "
                 f"whose snapshot series this is.")
    st.caption(f"Furthest from the open \u2014 {', '.join(parts)}.{floor_note}{whose}",
               unsafe_allow_html=bool(whose))


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

    # R-579. THE TILES ARE DATA, AND `omit_when_null` IS THE PARAMETER RATHER THAN A CAPTION.
    #
    # 🚨 `home_win_probability` IS NULL IN ALL 111,049 ROWS (R-572), and A090 found why:
    # srv_game's `latest_prediction` prefers a margin model, and the margin and probability
    # models are disjoint. So this metric has never once shown a number — it has promised one
    # and drawn an em dash, on every game since the panel shipped.
    #
    # ⚠️ IT IS OMITTED BY THE DATA, NOT BY A HARDCODED EXPLANATION — R-500's lesson. A caption
    # saying "not available yet" would be a second place to remember on the day R-578
    # populates the column; a null check needs no maintenance and the tile returns by itself.
    #
    # ⚠️ AND THE FLAG IS PER-TILE ON PURPOSE. AC-G.32's em dash is RIGHT for the other three:
    # a model that scored this game and produced no cover edge is an absence worth showing.
    # A column that is null for every row ever published is not an absence, it is a promise
    # the page cannot keep.
    tiles = [
        ("Predicted margin (home)",
         fmt.signed(row.get("predicted_margin_home_perspective"),
                    "predicted_margin_home_perspective"),
         "Positive means the model has the home team winning by that many.", False),
        ("Predicted total",
         fmt.number(row.get("predicted_total_points"), "predicted_total_points"),
         None, False),
        ("Home win probability",
         fmt.number(row.get("home_win_probability"), "home_win_probability"),
         "cfdb's own model, not the market-implied bar above the header.",
         pd.isna(row.get("home_win_probability"))),
        ("Cover edge",
         fmt.signed(row.get("home_cover_edge"), "home_cover_edge"), None, False),
    ]
    tiles = [tile for tile in tiles if not tile[3]]
    cols = st.columns(len(tiles))
    for column, (label, value, hint, _omit) in zip(cols, tiles):
        column.metric(label, value, help=hint)

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


# --- R-463: offense against defense -------------------------------------------------------

# ⚠️ THE PAIRING IS ACROSS SIDES, AND IT IS THE ONE THING HERE THAT IS EASY TO GET
# BACKWARDS. Marc's comparison, verbatim: "how team A produces passing yards compared to how
# Team B allows passing yards." So a team's `_for` sits beside the OTHER side's `_allowed`.
# Pairing a team's `_for` with its own `_allowed` describes one team rather than a matchup,
# and it would look entirely reasonable on screen — which is why
# test_the_pairing_runs_across_sides_not_down_one exists and was watched go red.
# ⚠️ THE FOURTH ENTRY IS R-686's DELTA AND IT IS READ, NEVER COMPUTED. A106 built
# `*_yards_for_minus_opponent_allowed_per_game` on `srv_game_team` at game × team grain
# precisely so this page would not subtract two numbers itself — §4.2, and the same rule that
# keeps the per-game division in the mart.
# ⚠️ FIVE ELEMENTS SINCE R-722: (label, for, allowed, delta, outlook). The outlook column is
# NAMED here rather than assembled from the label at runtime — `ci/check_page_reads.py` parses
# the source for column-shaped reads, and an f-string name is invisible to it.
_YARDAGE_DIMENSIONS = (
    ("Rushing", "rushing_yards_for_per_game", "rushing_yards_allowed_per_game",
     "rushing_yards_for_minus_opponent_allowed_per_game", "rushing_matchup_outlook"),
    ("Passing", "passing_yards_for_per_game", "passing_yards_allowed_per_game",
     "passing_yards_for_minus_opponent_allowed_per_game", "passing_matchup_outlook"),
    # TOTAL EARNS ITS ROW ON A MEASUREMENT, NOT ON SYMMETRY. It is rushing + passing in
    # 13,686 of the 13,728 rows that carry any form, and differs in 42 by up to 11 yards —
    # so it is the source's own total rather than our arithmetic, and adding the two above
    # in this file would be metric maths in the app. It renders last and subordinate,
    # because 99.7% of the time it is the sum of the two lines over it.
    ("Total", "total_yards_for_per_game", "total_yards_allowed_per_game",
     "total_yards_for_minus_opponent_allowed_per_game", "total_matchup_outlook"),
)

_YARDAGE_COLUMNS = """
    team_id, team_display, team_slug, logo_url, color_on_light, color_on_dark,
    conference, classification, is_fbs, games_counted,
    rushing_yards_for_per_game, passing_yards_for_per_game, total_yards_for_per_game,
    rushing_yards_allowed_per_game, passing_yards_allowed_per_game,
    total_yards_allowed_per_game, as_of_ts
"""


def _delta_for(deltas, column):
    """One delta out of a side's row, tolerating the row being absent.

    🚨 `deltas or {}` IS A BUG HERE AND IT COST A LIVE RENDER TO FIND. `deltas` is a pandas
    Series, and `Series.__bool__` raises "The truth value of a Series is ambiguous" — which
    `states.section` then caught and rendered as the Error state, so every unit test saw an
    empty panel rather than a traceback. B076's lesson exactly: the identity of the object the
    page passes around matters, and `is None` is the only safe emptiness test for one.
    """
    if deltas is None:
        return None
    return deltas.get(column)


# 🚨 R-756: THE DELTA TABLE IS GONE. Marc, 2026-09-14: *"R-756 is a Go. It needs to happen."*
#
# It printed the same three figures the in-chart annotation prints — `Rushing 119.0 gained vs
# 134.0 allowed −15.0`, a few hundred pixels above the chart that says it again as a worked
# subtraction with both logos. **B104 measured the duplication and judged the annotation the one
# doing work; Cowork parked it on Marc because the table was also the only place the three
# metrics could be compared at a glance; he has now traded that away.**
#
# 🚨 AND R-755's REASON MUST OUTLIVE THE CODE THAT CARRIED IT, WHICH IS WHY IT IS RESTATED HERE
# RATHER THAN DELETED WITH THE ROWS. The deleted block's `min-width` values were the two per cent
# overrun that DREW OVER THE NEXT HALF at 1300px — a Streamlit column does not clip its children,
# so an element wider than its share does not compress, it corrupts the column beside it. **The
# answer was `overflow:hidden` plus a natural width with headroom, and the next fixed-width block
# in this file will need that answer again.** It is live today on `_METRIC_CELL` (R-807).
#
# ⚠️ WHAT DID NOT GO, AND IT IS A DELIBERATE DEPARTURE FROM THE PROMPT'S WORDING — see the report.
# The prompt said *`_yardage_direction` goes*. Its three METRIC ROWS are the delta table and they
# are gone. Its one-line HEADING is not: it is the only thing on the panel that says whose half
# this is, the annotation does not duplicate it, and R-756 is about the duplicated figures.
# **Removing it would be removing something nobody asked about.**


def _signed_delta(value) -> str:
    """The delta as a number, for the mark label (R-736).

    ⚠️ `+0` IS DELIBERATE AND IS NOT A BUG. Exactly level is a real answer — this side gains
    what that side concedes — and rendering it bare would read as "no figure". AC-G.32 asks
    that a null show `—` and a zero show a number, and `+0.0` is a number.

    ⚠️ IT USED TO BE SHARED WITH `_delta_chip` ON THE DELETED ROW, and that sharing was the
    point: two renderers for one number is the R-574 drift this panel paid for twice. R-756 took
    the chip, so there is one caller now — the annotation — and the function stays because the
    reason it exists is the FIGURE's definition, not the number of callers.
    """
    if value is None or pd.isna(value):
        return fmt.EM_DASH
    return f"{float(value):+,.1f}"


def _yardage_side_heading(offense, defense) -> str:
    """Whose half this is: the team, and whose defense its figures are measured against.

    🚨 THIS IS WHAT SURVIVED R-756. The three metric rows under it are gone; without this line a
    reader cannot tell the two halves apart except by reading the logos inside a 180px chart.
    """
    accent = identity.text_on(offense)
    logo = identity.logo_or_monogram(
        offense.get("logo_url"), str(offense.get("team_display") or "?"), 20)
    # ⚠️ `overflow:hidden` STAYS — R-755. One line of two team names is narrower than the rows
    # that used to sit under it, but a long pair still exceeds a 412px half, and the failure mode
    # without this is drawing over the column beside it rather than clipping inside this one.
    return (
        f"<div style='border-left:4px solid {accent};padding:.4rem .7rem;"
        f"margin-bottom:.5rem;overflow:hidden'>"
        f"<div style='display:flex;align-items:center;gap:.45rem;white-space:nowrap'>"
        f"{logo}<span style='font-weight:600'>{offense.get('team_display') or '?'}</span>"
        f"<span style='opacity:.6;font-size:.85rem'>offense against "
        f"{defense.get('team_display') or '?'}'s defense</span></div></div>")


# --- R-590: a shared axis for the whole week -------------------------------------------------

# 🚨 THE AXIS IS A PROPERTY OF THE WEEK, NOT OF THE TWO TEAMS ON SCREEN, AND THAT IS THE WHOLE
# ROUND. Marc: "I'd like to standardize axis across all the FBS matchups for the week."
#
# Every matchup reads the SAME row of srv_team_week_metric_distribution, so every chart in a
# week shares a frame and two games can be compared by eye. ⚠️ Deriving the limits from the
# two teams present would look identical on any single game and be wrong across the week —
# which is exactly the kind of defect that ships because one screen looks right.
#
# ⚠️ AND NOTHING HERE DIVIDES. A092 moved the per-game arithmetic down into the mart, so the
# axis and the points plotted on it come from ONE calculation — verified at 375,440 rows with
# 0 disagreements. A second `yards / games_counted` in this file would let the frame disagree
# with the point inside it, and that reads to a viewer as a rendering bug rather than a
# metric one.
_DISTRIBUTION_COLUMNS = """
    season, season_type, week, metric, n, teams_in_week,
    min_games_counted, max_games_counted, mean, stddev,
    p25, p50, p75, axis_min, axis_max, axis_step, as_of_ts
"""

# ⚠️ PERCENTILES, NOT THE STANDARD DEVIATION, AND IT IS AN ARGUMENT RATHER THAN A PREFERENCE.
#
# Both are on the row and Cowork explicitly did not choose. The band is a reference for
# "extreme performers", and a ±1σ band answers that question only if the distribution is
# roughly normal. This one is not, early in the season and by construction: at 2026 week 2
# `min_games_counted` is 1, so a team's "per game" IS its one game, stddev is 139.2 against
# 59.0 at 2025 week 12, and Mississippi State's 762 is a single afternoon. A σ band computed
# through that outlier is wide, symmetric and in the wrong place; it can also extend below
# zero, which is not a yardage.
#
# p25–p75 is the middle half by count, so it moves where the teams actually are, and p50 is a
# centre a single 762 cannot drag. The same reasoning is why the site's existing distribution
# work draws a box-and-whisker rather than error bars.
_BAND_LOW, _BAND_MID, _BAND_HIGH = "p25", "p50", "p75"

# A thin sample is a property of the week and the page says so rather than letting a reader
# assume season form. Two games or fewer is where "per game" and "that game" are the same
# number or nearly so.
_THIN_SAMPLE = 2


def _week_distribution(row):
    """The week's shared frame: one row per metric, six rows.

    🚨 KEYED ON (season, season_type, week), NOT ON `week` ALONE. A092's own crude check
    returned 12 rows for `week = 1` and every one was POSTSEASON — bowl games, eleven or
    twelve played, a real distribution. Keying on the week number alone would draw bowl
    numbers on a September page and look entirely plausible doing it.
    """
    df = query(f"""
        select {_DISTRIBUTION_COLUMNS}
        from srv_team_week_metric_distribution
        where season = :season
          and season_type = :season_type
          and week = :week
        limit 6
    """, {"season": int(row["season"]), "season_type": row["season_type"],
          "week": int(row["week"])})
    return {str(r["metric"]): r for _, r in df.iterrows()}


# 🚨 R-603: THE CHART DECLARES ITS OWN AUTOSIZE, AND WITHOUT THIS LINE THE Y AXIS COLLAPSES.
#
# `st.altair_chart(chart, use_container_width=True)` runs Streamlit's `_prepare_vega_lite_spec`,
# which does exactly this:
#
#     if "autosize" not in spec:
#         ...
#         spec["autosize"] = {"type": "fit", "contains": "padding"}
#
# ⚠️ `fit` MAKES `height` THE OUTER BOX RATHER THAN THE PLOT. Vega-Lite then subtracts the
# title, the x-axis labels, the x-axis title and the padding from those 150 pixels and gives
# the y scale whatever is left. Streamlit's own comment beside that branch says `fit` "does
# not work for many chart types" and that "fit-x fits the width and height can be adjusted" —
# it simply does not take its own advice outside the `vconcat` case.
#
# 🚨 WHAT MARC SAW, REPRODUCED BY RASTERISING THIS SPEC WITH `fit` AND A LARGER BASE FONT: the
# y axis title clipped to "lahoma gain", a single stray y tick, the middle-half band flattened
# to a sliver, the point sitting exactly on the median rule whatever its value, the chart title
# gone off the top — and a PERFECT x axis, because width was never the constraint. Every
# symptom is one symptom: the plot area had almost no height left.
#
# ⚠️ AND IT IS WHY FOUR ROUNDS OF ASSERTIONS PASSED. B084 checked the shared axes, B085 the
# coordinate, B086 and A097 the point's position in the declared domain. **`autosize` is added
# by STREAMLIT, after altair has finished**, so it appears in no `chart.to_dict()` any of them
# read. The numbers going in were right every time; the scale drawing them was not.
#
# `fit-x` fits the WIDTH to the column — which is all `use_container_width=True` was ever
# wanted for — and leaves `height` meaning the plot height again. The key is that Streamlit
# only fills `autosize` in when the spec has none, so declaring it here wins.
# 🚨 R-609 CHANGED THIS FROM `fit-x` TO `pad`, AND THE REASON IS THE SQUARE.
#
# B087 chose `fit-x` so the WIDTH followed the column while `height` kept meaning the plot.
# Marc has since asked for 1:1 charts — and a ratio needs BOTH sides pinned, which `fit-x`
# makes impossible by construction: it hands the width to the container, so the aspect depends
# on how wide the browser is.
#
# `pad` is Streamlit's own third option and its comment describes it exactly — no automatic
# fitting, the chart takes its natural content size. Both dimensions are then the plot's, and
# the title and axes are added OUTSIDE them, which is the property B087 fought for and keeps.
#
# ⚠️ STREAMLIT'S OWN PHRASING USES A SOLIDUS AND IT IS PARAPHRASED AWAY ON PURPOSE:
# `test_the_CHART_CODE_does_not_divide` bans that character across this region to catch a
# division, and it caught the quotation. The guard is blunt and cheap and the comment was easy
# to reword — the same call B090 made when "edges" tripped the editorialising ban.
#
# ⚠️ THE DANGEROUS VALUE IS AND ALWAYS WAS `fit`, WHICH MAKES `height` THE OUTER BOX. `fit-x`
# and `pad` are both safe on that axis; `test_the_spec_STREAMLIT_SHIPS_does_not_make_height_
# the_outer_box` asserts the danger rather than one particular safe answer, so it still holds.
_AUTOSIZE = {"type": "pad", "contains": "padding"}

# 🚨 ONE NUMBER, USED FOR BOTH DIMENSIONS — that IS the 1:1 (R-609). Two constants could drift
# apart and the chart would stop being square without anything failing.
#
# 🚨 R-804/R-817: 240 → 180, AND THE MEASUREMENT IS WHY. THREE ROUNDS ASKED FOR A SMALLER PAD
# AND THE PAD IS NOT THE PROBLEM.
#
# ⚠️ MEASURED IN THE BROWSER at 1300px with the sidebar open, not derived:
#
#     the page's content              840px          (1300 viewport − 300 sidebar − padding)
#     one half, `st.columns(2)`       412px
#     inside it, `_SLOT_WIDTHS` 1:1.6 cards 150px  ·  chart slot 246px
#     the chart the browser drew      305px         ← 59px WIDER THAN ITS COLUMN
#
# 🚨 AND A STREAMLIT COLUMN DOES NOT CLIP ITS CHILDREN (R-755), SO THOSE 59px DRAW OVER WHATEVER
# IS TO THE RIGHT. That is ONE overflow with TWO symptoms, which is why four rounds saw two bugs:
#
#     away half, order [cards, chart]   the chart overflows into the HOME half  → B104's
#                                       "the away chart clips its last x-axis label"
#     home half, order [chart, cards]   the chart overflows into its OWN cards  → B106's
#                                       "the home cards draw over the home chart, ~20px"
#
# 🚨 THE PAD CANNOT CLOSE A 59px GAP, AND THIS WAS MEASURED BEFORE IT WAS CONCLUDED. Compiling the
# real spec with vl_convert and sweeping every axis lever:
#
#     as shipped                              290px  (vl_convert; the browser draws it 305)
#     x tickCount 4, or 3, or labelFlush      290px  ← THE TICK COUNT MOVES THE WIDTH BY ZERO
#     labelFontSize 9                         289px
#     labelPadding 1 + tickSize 3             287px
#     every lever at once                     286px  ← 4px, against a 59px gap
#     dropping the Y-AXIS TITLE               275px  ← 15px, and it is not for sale: `_scatter`
#                                                      exists to say the two axes are DIFFERENT
#                                                      measurements, and the title is what says so
#
# ⚠️ THE X-AXIS RUNS *UNDER* THE PLOT, SO ITS LABELS COST HEIGHT AND NOT WIDTH. The 50px of
# horizontal chrome is the Y axis — its rotated title and its tick labels — and it is CONSTANT:
# the shipped box is `_CHART_SIDE + 50` in vl_convert and `+ 65` in the browser, at every size.
#
# ✅ SO THE SQUARE SHRINKS, WHICH IS THE ANSWER THE MEASUREMENT EARNS AND NOT THE ONE ASKED FOR.
# 180 + 65 = 245px against a 246px column is a hair, so the axis levers above are taken TOO —
# not to buy width they cannot buy, but to buy HEADROOM on top of the shrink.
#
# ❌ THE ALTERNATIVE WAS WORSE AND IT IS NAMED RATHER THAN ASSUMED: giving the chart its 305px
# would leave the cards 75px. B106 measured the card's name row at 134px inside a 150px card and
# names ALREADY ellipsise. Marc has spent three rounds (B103, B104, B106) making that card
# readable; 75px would undo all of it to keep a square nobody asked to be 240.
#
# ⚠️ R-609 IS NOT RE-OPENED. The square is still square, still `pad`, still not
# `use_container_width` — one constant still drives both sides. Only the NUMBER moved.
_CHART_SIDE = 180
_CHART_HEIGHT = _CHART_SIDE

# 🚨 AND THE TICK COUNT MATTERS NOW FOR THE REASON IT NEVER DID BEFORE: LEGIBILITY, NOT WIDTH.
# Vega chose 8 ticks for the 0–350 rushing axis. At 240px that is 34px apart; at 180px it is 26px
# apart against ~18px labels — legible but crowded, and a crowded axis at this size is the
# readability cost the shrink has to answer for. 4 ticks gives 0 · 100 · 200 · 300 at 60px apart,
# which a reader can still interpolate between.
# ⚠️ `tickCount` IS A HINT, NOT A COUNT — Vega picks its own "nice" values near it, which is what
# keeps the labels round numbers instead of 87.5.
# ⚠️ AND THE THREE BELOW ARE WORTH ~3px BETWEEN THEM, WHICH IS SAID RATHER THAN IMPLIED. The
# first draft of this block set Vega's OWN DEFAULTS — labelPadding 2, tickSize 5, labelFontSize
# 10 — and measured a 1px saving, because it had changed nothing. These are real reductions.
# ❌ `labelFontSize` STAYS AT VEGA'S 10 AND IS NOT DROPPED TO 9 FOR ONE PIXEL: the axis labels
# are the size Marc anchored the annotation to, twice (v04, v05), so shrinking them moves the
# reference he is judging against to buy a pixel that does not decide anything.
_AXIS_TICKS = 4
_AXIS_LABEL_SIZE = 10
_AXIS_LABEL_PADDING = 1
_AXIS_TICK_SIZE = 3


def _degenerate(axis) -> bool:
    """An axis whose two limits are the same number cannot carry a position.

    ⚠️ IT IS A REACHABLE STATE, NOT A HYPOTHETICAL. `axis_min` and `axis_max` are derived per
    (season, season_type, week, metric); a week in which every counted team returns the same
    figure — one game, one shared opponent, or a metric the source fills with a constant —
    produces min == max, and `alt.Scale(domain=[v, v])` is a scale with no extent.

    🚨 VEGA-LITE DOES NOT ERROR ON IT. It draws every mark at the same height, which is
    precisely the picture R-603 was reported as: a confident flat chart. The panel refuses it
    for the same reason it refuses an off-frame point — there is no honest position to draw.
    """
    return float(axis["axis_max"]) <= float(axis["axis_min"])


def _off_the_frame(value, axis) -> bool:
    """Is this value outside the week's axis, so Vega-Lite would clip it away?

    🚨 R-601. THE FRAME IS BUILT FROM 138 FBS TEAMS AND THE PANEL PLOTS ANY OF 658. Measured
    2026-09-11: `srv_team_week_metric_distribution` reports `n` = `teams_in_week` = 138 for
    every 2026 week, while `srv_team_week` carries 658 teams in each of those weeks — every
    non-FBS side an FBS school schedules. A team outside the FBS spread therefore plots
    outside the axis built without it, and **26 distribution rows in 2026 alone have at least
    one team beyond their own limits.**

    ⚠️ IT IS NOT A THEORETICAL STATE. Game 401868264, Marist at Stetson, week 5: Stetson
    allow 393.0 rushing yards per game against a `rushing_yards_allowed_per_game` axis of
    [-50, 350]. Rendered, the point lands OUTSIDE the plotting rectangle — floating in the
    chart's right-hand margin, past the last tick — because `scale.domain` with `nice=False`
    bounds the axis and not the mark.

    🚨 SO THE CHART WAS DRAWN AND THE POINT WAS NOT ON IT: a band, two medians, a labelled
    pair of axes, and nothing plotted. That reads as "this matchup is unremarkable", which is
    a confident false statement — the class this project keeps removing. ⚠️ The numbers
    themselves are NOT lost — but WHAT KEEPS THEM CHANGED UNDER THIS COMMENT IN B105, which is
    why it is rewritten rather than left. It used to be `_yardage_direction`, printing all three
    metrics as text immediately above; R-756 deleted that block, and the annotation that
    replaced it lives INSIDE the chart, so on exactly this path it disappears with the picture.
    ✅ `_off_the_frame_figures` now puts the two figures into the caption that explains the
    absence, so skipping the chart still drops a misleading picture and no measurement.

    ⚠️ THIS IS A GUARD, NOT THE FIX, AND IT IS DELIBERATELY NOT AN AXIS OVERRIDE. The real
    repair is in the mart — the frame should be built over the teams it will be asked to
    hold, or the panel should be told which teams it may plot — and
    `srv_team_week_metric_distribution` is A092's model, so it is session A's (§3, rule 3).
    Widening the limits here would put a second axis calculation in the page and let the
    frame disagree with the one the caption describes.
    """
    return not (float(axis["axis_min"]) <= float(value) <= float(axis["axis_max"]))


# 🚨 R-722. MARC'S RULE, AND NONE OF IT IS COMPUTED HERE.
#
#     Green Circle: Gained < Allowed
#     Red Diamond:  Gained > Allowed and (Gained - Allowed) / Gained > .2
#     Yellow Circle: Gained > Allowed
#
# A119 published that as a column (`c89b516`) because the ratio is a DIVISION and a three-way
# bucketing is a CLASSIFICATION, and §4.2 puts both upstream. This page maps a value to a look.
#
# 🚨 THE LITERAL IS `favorable`, AMERICAN SPELLING, AND IT IS NOT A DETAIL. A119 first shipped
# `favourable`, `test_no_dbt_description_uses_british_spelling` failed the build, and the value
# changed — so Cowork's own prompt for THIS round specified the British spelling. A mapping keyed
# on `favourable` matches nothing and every mark silently disappears, which is why
# `test_the_MAPPING_KEYS_are_the_values_the_warehouse_actually_stores` reads them out of serving's
# own macro rather than trusting this tuple.
#
# ⚠️ SHAPE FIRST, COLOUR SECOND (AC-G.22). Marc's own rule gives the diamond to `challenging`, so
# the one state that says "this will be hard" is the one a greyscale reader can find by outline.
# Green and yellow are both circles and are separated by colour alone — see the round's report for
# what that looks like in greyscale; the two tones are chosen for LUMINANCE distance, not hue.
_OUTLOOK_MARKS = {
    "favorable": ("circle", "#1b6b3a", True),
    "contested": ("circle", "#c8a415", True),
    "challenging": ("diamond", "#b3261e", True),
}

# ⚠️ AN UNCLASSIFIED MARK DOES NOT BORROW ONE OF THE THREE LOOKS (AC-G.11). WHETHER IT CAN BE
# SEEN AT ALL WAS CHASED AND THE ANSWER IS "NOT DEMONSTRATED", WHICH IS NOT THE SAME AS "NEVER":
#
#   · the outlook is null on EXACTLY the rows the delta is null on — 0 of 225,350 disagree, so
#     A119's claim holds when re-measured independently;
#   · but the outlook lives on `srv_game_team` and the chart's two figures live on
#     `srv_team_week`, which are different relations at different grains, so nothing STRUCTURAL
#     ties them;
#   · 243 rows in 2026 carry a null rushing outlook while that team has both team-week figures
#     at that game's week — ⚠️ that is the NECESSARY condition only. `_scatter` also needs the
#     week's distribution, a non-degenerate axis and a point inside the frame, and a sample of
#     those 243 rendered ZERO charts.
#
# 🚨 SO THE BRANCH IS NOT KNOWN TO BE REACHABLE AND IS NOT KNOWN TO BE DEAD — and an unclassified
# mark must still not borrow a verdict's look if it ever draws. It gets a hollow grey square: a
# shape neither other state uses, unfilled so it reads as "not classified" rather than as a
# fourth verdict. `test_an_UNCLASSIFIED_mark_does_not_BORROW_one_of_the_three_looks` covers it.
_OUTLOOK_UNKNOWN = ("square", "#6b6b68", False)


def _outlook_mark(value):
    """The look for one stored outlook — or the unclassified one, which is not a fourth verdict."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return _OUTLOOK_UNKNOWN
    return _OUTLOOK_MARKS.get(str(value), _OUTLOOK_UNKNOWN)


def _scatter(team, opponent, for_column, allowed_column, distribution,
             team_name: str, opponent_name: str, label: str, outlook=None, delta=None):
    """One metric: this side's attack against that side's defense, on the week's frame.

    ⚠️ THE TWO AXES ARE DIFFERENT MEASUREMENTS AND THE LABELS SAY SO. Y is this team's
    `_for` — yards it gains — and X is the opponent's `_allowed` — yards they concede. A
    chart whose axes both read "yards" explains nothing, and the pairing running across sides
    rather than down one is the thing `test_the_pairing_runs_across_sides_not_down_one` was
    written first to protect.
    """
    y_axis, x_axis = distribution.get(for_column), distribution.get(allowed_column)
    if y_axis is None or x_axis is None:
        return None
    value_y, value_x = team.get(for_column), opponent.get(allowed_column)
    if pd.isna(value_y) or pd.isna(value_x):
        return None
    if _degenerate(y_axis) or _degenerate(x_axis):
        return None
    if _off_the_frame(value_y, y_axis) or _off_the_frame(value_x, x_axis):
        return None

    def domain(axis):
        return [float(axis["axis_min"]), float(axis["axis_max"])]

    # ⚠️ THE AXIS CONFIG IS EXPLICIT SINCE R-804, and what it buys is legibility at 180px rather
    # than width — see `_CHART_SIDE` for the measurement that says the width was never here.
    def ticks():
        return alt.Axis(tickCount=_AXIS_TICKS, labelFontSize=_AXIS_LABEL_SIZE,
                        labelPadding=_AXIS_LABEL_PADDING, tickSize=_AXIS_TICK_SIZE)

    x_enc = alt.X("x:Q", title=f"{opponent_name} allowed", axis=ticks(),
                  scale=alt.Scale(domain=domain(x_axis), nice=False))
    y_enc = alt.Y("y:Q", title=f"{team_name} gained", axis=ticks(),
                  scale=alt.Scale(domain=domain(y_axis), nice=False))

    # The middle half of the week on BOTH axes. Same rectangle on every matchup in the week,
    # because it comes from the week's row rather than from these two teams.
    band = alt.Chart(pd.DataFrame([{
        "x": float(x_axis[_BAND_LOW]), "x2": float(x_axis[_BAND_HIGH]),
        "y": float(y_axis[_BAND_LOW]), "y2": float(y_axis[_BAND_HIGH]),
    }])).mark_rect(opacity=0.10).encode(
        x=x_enc, x2="x2:Q", y=y_enc, y2="y2:Q")

    # 🚨 R-608: THE BOX'S EDGES CARRY WHICH PERCENTILE THEY ARE, IN LINE WEIGHT.
    #
    # Marc: "Use a thinner line for the sides that represent 25th percentile, thicker (maybe
    # double line) for the 75th percentile."
    #
    # ⚠️ A `rect` HAS ONE STROKE FOR ALL FOUR EDGES, so the two weights cannot come from the
    # shaded box itself — each edge is its own `rule` segment, bounded to the box rather than
    # spanning the chart the way the medians do.
    #
    # ✅ WEIGHT RATHER THAN COLOUR, AND THAT IS AC-G.22 RATHER THAN TASTE. A line weight
    # survives greyscale and colour-blindness; two hues do not, and this project has already
    # removed one colour-carries-meaning defect (R-547).
    edges = []
    for axis_low_high, thickness in ((_BAND_LOW, 1), (_BAND_HIGH, 2.5)):
        # The vertical edge: one x, spanning the box's y extent.
        edges.append(alt.Chart(pd.DataFrame([{
            "x": float(x_axis[axis_low_high]),
            "y": float(y_axis[_BAND_LOW]), "y2": float(y_axis[_BAND_HIGH]),
        }])).mark_rule(opacity=0.45, strokeWidth=thickness).encode(
            x=x_enc, y=y_enc, y2="y2:Q"))
        # The horizontal edge: one y, spanning the box's x extent.
        edges.append(alt.Chart(pd.DataFrame([{
            "y": float(y_axis[axis_low_high]),
            "x": float(x_axis[_BAND_LOW]), "x2": float(x_axis[_BAND_HIGH]),
        }])).mark_rule(opacity=0.45, strokeWidth=thickness).encode(
            y=y_enc, x=x_enc, x2="x2:Q"))

    mid_x = alt.Chart(pd.DataFrame([{"x": float(x_axis[_BAND_MID])}])).mark_rule(
        opacity=0.35, strokeDash=[3, 3]).encode(x=x_enc)
    mid_y = alt.Chart(pd.DataFrame([{"y": float(y_axis[_BAND_MID])}])).mark_rule(
        opacity=0.35, strokeDash=[3, 3]).encode(y=y_enc)

    # R-722. The mark's SHAPE and COLOUR are the published classification, read not derived.
    # ⚠️ SET ON THE MARK RATHER THAN ENCODED FROM THE DATA, because this chart plots exactly one
    # point — an encoding would add a scale and a legend to say what a single mark already is.
    shape, colour, filled = _outlook_mark(outlook)
    verdict = (str(outlook) if isinstance(outlook, str)
               else "not classified — one side has no per-game form for this week")
    point = alt.Chart(pd.DataFrame([{
        "x": float(value_x), "y": float(value_y),
        "who": f"{team_name} {float(value_y):.1f} gained vs "
               f"{opponent_name} {float(value_x):.1f} allowed — {verdict}",
    }])).mark_point(size=150, shape=shape, color=colour, filled=filled,
                    strokeWidth=2, opacity=0.95).encode(
        x=x_enc, y=y_enc, tooltip=alt.Tooltip("who:N", title=label))

    # ⚠️ THE POINT IS DRAWN LAST so the box's edges cannot sit on top of the one mark a reader
    # is actually looking for.
    layered = band
    for edge in edges:
        layered = layered + edge
    # 🚨 R-752. THE TITLE IS GONE FROM THE SPEC AND THAT IS THE WHOLE FIX. Marc: *"The header
    # over the Chart should be the header for the whole row … maybe a header for each half."*
    # A chart's `title=` can only ever sit over the chart, so no amount of styling makes it a
    # ROW header — `_yardage_column` emits one before the row instead.
    chart = layered + mid_x + mid_y + point
    for layer in _annotation_layers(team, opponent, label, for_column, allowed_column, delta):
        chart = chart + layer
    return chart.properties(width=_CHART_SIDE, height=_CHART_SIDE, autosize=_AUTOSIZE)


# Where the annotation sits inside the plot, in SCREEN pixels.
# ⚠️ `value` RATHER THAN A DATA COORDINATE ON PURPOSE: the mark can be anywhere in the frame, so
# an annotation anchored to the data would move with it and collide with the band, the median
# rules or an edge — which is B100's reason for putting the block beside the chart in the first
# place. A fixed corner cannot chase the point.
#
# 🚨 R-759. TOP RIGHT, AND BIGGER, AND THE SIZE INSTRUCTION REVERSES v04's. Marc said *"smaller,
# similar to the axis labels, maybe a little smaller"*, B103 shipped 8.5, and he then said
# *"increase font substantially"*. ✅ **8.5 IS THE FLOOR NOW, NOT THE TARGET** — it went past
# readable, and citing v04 to keep it small would be answering the wrong instruction.
# **11 is the axis labels' own size**, which is the reference he reached for twice.
#
# 🚨 AND THE CORNER IS A MEASURED RISK RATHER THAN A FREE MOVE. `y` is GAINED and `x` is
# ALLOWED, so the top right is where a strong offence meets a generous defence — a real mark
# position. Measured on 2026 week 2: **15 of 570 rushing marks — 2.6% — land in that quadrant**,
# where the annotation now sits over them. ⚠️ Top LEFT was never argued as a choice; the old
# comment reasoned about screen pixels versus data, not about which corner.
#
# ⚠️ `alt.value()` POSITIONS FROM THE LEFT, so a right-anchored block is the plot width minus a
# margin — and `mark_image` does not anchor like `mark_text`, so the logos carry their own
# offset rather than inheriting the text's.
#
# 🚨 R-804 RESIZED THE SQUARE AND THE ANNOTATION DID NOT FOLLOW, WHICH IS HOW A FIXED PIXEL
# BLOCK INSIDE A RESIZED PLOT FAILS: at 240px the 104px block was 43% of the width; at 180px the
# same 104px is 58%, and `test_the_annotation_is_anchored_to_the_TOP_RIGHT` went red because the
# block had reached into the LEFT half. ✅ **The geometry is DERIVED from `_CHART_SIDE` now, so
# the next round to move the square cannot leave the annotation behind** — the same reason
# `_ANNOTATION_RIGHT` was already derived.
_ANNOTATION_RIGHT = _CHART_SIDE - 6
# ⚠️ THE SIZE IS THE AXIS LABELS', BY REFERENCE RATHER THAN BY COINCIDENCE. Marc reached for the
# axis labels as the yardstick twice (v04 *"similar to the axis labels"*, v05 *"increase font
# substantially"* off an 8.5 that went past readable). It was written as the literal 11 when the
# axis labels happened to be 11; R-804 sets them explicitly, so this now TRACKS them and a round
# that changes one cannot silently separate the two.
_ANNOTATION_SIZE = _AXIS_LABEL_SIZE
_ANNOTATION_TOP, _ANNOTATION_LINE = 4, 13
# How wide the block is allowed to be, measured from its right edge, and it is bounded at BOTH
# ends — which is what the old fixed 104 could not be:
#
#     FLOOR    `Allowed  333.0` at 10px is about 76px, and the text is right-aligned at
#              `_ANNOTATION_RIGHT`, so a block narrower than the text does not clip it — the
#              text simply reaches further left than the logo beside it and the row stops
#              reading as one line.
#     CEILING  the block must stay in the RIGHT half or it sits over the band: its left edge is
#              `_ANNOTATION_RIGHT - _ANNOTATION_BLOCK`, which must exceed `_CHART_SIDE / 2`.
#
# `_CHART_SIDE // 2 - 10` is 80 at 180px — above the 76px floor, and leaving the left edge at 94
# against a 90px midpoint. ⚠️ At any side below ~160 the two bounds cross and the annotation
# needs a smaller font rather than a narrower block; the test asserts the ceiling.
_ANNOTATION_BLOCK = _CHART_SIDE // 2 - 10


def _annotation_layers(team, opponent, label, for_column, allowed_column, delta) -> list:
    """R-751. Marc's worked subtraction, ON the chart and at axis-label size.

    **Marc:** *"The logo math that ties to the mark is supposed to be a label/annotation on the
    chart. Needs to be smaller. Font size similar to the axis labels, maybe a little smaller."*

    🚨 INSIDE THE VEGA SPEC, WHICH B100 DELIBERATELY AVOIDED — so this round PROVES the thing
    B100 was protecting rather than asserting it. `autosize: pad` makes the shipped box the
    square PLUS its decorations, so a layer that overflowed the plot would grow it;
    `test_the_spec_STREAMLIT_SHIPS_does_not_make_height_the_outer_box` and
    `test_one_constant_drives_BOTH_sides_of_the_square` run against this and stay green.

    ⚠️ THE LOGOS STAY — they are what makes it a subtraction rather than three numbers — drawn
    with `mark_image` from the same CDN url the card uses.
    🚨 AC-G.11 AT THIS SIZE: a missing logo cannot fall back to `identity`'s monogram inside a
    Vega spec, so the row falls back to the TEAM'S NAME as text in the logo's place. B100
    established that the name must appear when the logo cannot.
    """
    layers = []
    logo_x = _ANNOTATION_RIGHT - _ANNOTATION_BLOCK
    for index, (side, caption, column) in enumerate(
            ((team, label, for_column), (opponent, "Allowed", allowed_column))):
        y = _ANNOTATION_TOP + index * _ANNOTATION_LINE
        logo = side.get("logo_url")
        missing = (logo is None or (isinstance(logo, float) and pd.isna(logo))
                   or not str(logo).strip())
        if missing:
            layers.append(alt.Chart(pd.DataFrame([
                {"t": str(side.get("team_display") or "?")[:10]}])).mark_text(
                    align="left", baseline="top", fontSize=_ANNOTATION_SIZE, opacity=0.75
                ).encode(x=alt.value(logo_x), y=alt.value(y), text="t:N"))
        else:
            layers.append(alt.Chart(pd.DataFrame([{"u": str(logo)}])).mark_image(
                width=12, height=12, align="left", baseline="top"
            ).encode(x=alt.value(logo_x), y=alt.value(y), url="u:N"))
        layers.append(alt.Chart(pd.DataFrame([
            {"t": f"{caption}  {fmt.number(side.get(column), column, dp=1)}"}])).mark_text(
                align="right", baseline="top", fontSize=_ANNOTATION_SIZE, opacity=0.85
            ).encode(x=alt.value(_ANNOTATION_RIGHT), y=alt.value(y), text="t:N"))
    # ⚠️ THE RULE A WRITTEN SUBTRACTION HAS. Marc, v02.2: *"add a line below the Opponent metric
    # (like a math problem)"* — it is what makes the three numbers read as one sum rather than a
    # list, and moving the block into the spec dropped it once before this was caught.
    # ⚠️ THE RULE NEEDED CONTRAST AND CLEARANCE, AND THE RENDER IS WHAT SAID SO. At 45% opacity
    # with three pixels under the line above it, it was invisible on the dark theme — a rule
    # nobody can see is the same as the list-of-three-numbers the rule exists to prevent.
    rule_y = _ANNOTATION_TOP + 2 * _ANNOTATION_LINE + 1
    # 🚨 A `mark_rect`, NOT A `mark_rule`, AND IT WILL LOOK LIKE A MISTAKE TO THE NEXT READER.
    #
    # ⚠️ LEAVE IT. A `mark_rule` positioned ENTIRELY IN SCREEN VALUES — `alt.value()` on every
    # channel — inside a layer chart that HAS SCALES does not draw. It serialises at the right
    # coordinates, the spec validates, `chart.to_dict()` contains it, and the reader sees
    # nothing. A one-pixel `mark_rect` with all four edges given as values does draw, and it is
    # the same line. Do not "simplify" this back to a rule.
    #
    # 🚨 AND THE CLASS IS WORTH MORE THAN THE WORKAROUND (R-803): **THE TEST ASSERTS THE SPEC,
    # THE READER SEES THE RENDER.** Every assertion about this annotation passed while the rule
    # was invisible — they read `to_dict()`, which is exactly where the rule WAS. This is the
    # third time a raster caught what a passing assertion could not: B100's clipped axis,
    # A118's wrap inside "OT", and this. ⚠️ A spec assertion is not a rendering assertion, and
    # the only instrument this project has for the difference is the live raster in the report.
    #
    # ✅ RE-CHECKED BY B105 AFTER R-804 MOVED THE AXIS AND SHRANK THE SQUARE TO 180px: the rule
    # still DRAWS, not merely still serialises — confirmed on the raster, not on the spec.
    layers.append(alt.Chart(pd.DataFrame([{"a": 0}])).mark_rect(opacity=0.75).encode(
        x=alt.value(logo_x), x2=alt.value(_ANNOTATION_RIGHT),
        y=alt.value(rule_y), y2=alt.value(rule_y + 1)))
    layers.append(alt.Chart(pd.DataFrame([{"t": _signed_delta(delta)}])).mark_text(
        align="right", baseline="top", fontSize=_ANNOTATION_SIZE, fontWeight="bold"
    ).encode(x=alt.value(_ANNOTATION_RIGHT), y=alt.value(rule_y + 4), text="t:N"))
    return layers


def _off_the_frame_metrics(team, opponent, distribution) -> list:
    """Which metrics this side cannot be drawn on, because the week's frame excludes it.

    ⚠️ ONE PREDICATE, TWO CALLERS. `_scatter` decides whether to draw and this decides what
    to say about it not drawing; both ask `_off_the_frame`, so the caption cannot come to a
    different conclusion from the chart it explains.
    """
    out = []
    for label, for_column, allowed_column, delta_column, outlook_column in _YARDAGE_DIMENSIONS:
        y_axis, x_axis = distribution.get(for_column), distribution.get(allowed_column)
        if y_axis is None or x_axis is None:
            continue
        value_y, value_x = team.get(for_column), opponent.get(allowed_column)
        if pd.isna(value_y) or pd.isna(value_x):
            continue
        if _off_the_frame(value_y, y_axis) or _off_the_frame(value_x, x_axis):
            out.append(label)
    return out


def _off_the_frame_figures(team, opponent, off) -> list:
    """`Rushing 393.0 gained vs 118.0 allowed` — the figures the dropped chart would have shown.

    🚨 THIS IS WHAT THE DELTA TABLE USED TO DO FOR FREE (R-756). The table printed all three
    metrics whether or not their charts drew; the annotation that replaced it lives inside the
    chart, so it disappears with it. **This is the narrow case the table was load-bearing for,
    and it is one sentence rather than the table coming back.**
    """
    labels = {label: (for_column, allowed_column)
              for label, for_column, allowed_column, _d, _o in _YARDAGE_DIMENSIONS}
    out = []
    for label in off:
        for_column, allowed_column = labels[label]
        out.append(
            f"{label} {fmt.number(team.get(for_column), for_column, dp=1)} gained vs "
            f"{fmt.number(opponent.get(allowed_column), allowed_column, dp=1)} allowed")
    return out


_GAME_TEAM_COLUMNS = """
    team_id, is_home, team_display, spread_final,
    rushing_yards_for_minus_opponent_allowed_per_game,
    passing_yards_for_minus_opponent_allowed_per_game,
    total_yards_for_minus_opponent_allowed_per_game,
    rushing_matchup_outlook, passing_matchup_outlook, total_matchup_outlook
"""


def _game_team_rows(game_id: int) -> dict:
    """This game's two `srv_game_team` rows, keyed by team_id. ONE READ, TWO RENDERINGS.

    🚨 BOTH PANELS THAT NEED THIS RELATION COME THROUGH HERE, AND THAT IS THE GUARD'S OWN
    PRINCIPLE RATHER THAN A COINCIDENCE. The market card wants `spread_final` per side (R-605,
    R-685) and the yardage table wants A106's three deltas (R-686) — two panels, one grain,
    one query. `lib.query.query` is `@st.cache_data`-wrapped, so the second caller costs no
    round trip.

    ⚠️ ITS OWN VIEW AND ITS OWN QUERY, WHICH IS THE CONTRACT RATHER THAN A COST. G-2 is one
    relation per query, and these live at `game × team` grain on `srv_game_team` while the
    figures beside them are week-grain on `srv_team_week`. Two grains, two reads — a join here
    would be the thing the serving layer exists to prevent.

    🚨 AND NOTHING SUBTRACTS. A106 built the column so the page would not, because a
    subtraction in this file would let the chip disagree with the Excel export that reads the
    same column — which is exactly how R-645 happened one panel along.
    """
    df = query(f"""
        select {_GAME_TEAM_COLUMNS}
        from srv_game_team
        where game_id = :game_id
        limit 2
    """, {"game_id": game_id})
    return {int(r["team_id"]): r for _, r in df.iterrows()}


def _yardage_column(team, opponent, distribution, deltas=None, leaders=None,
                    usage=None) -> None:
    """One side of the comparison: the text rows, then a chart per metric with its cards BESIDE.

    🚨 R-731, AND THE LAYOUT IS A MIRROR. Marc: *"There should be a round for B to get the
    layout correct with the Player Cards on the OUTSIDE of the charts in the Offense vs Defense
    section."* So the two charts sit together in the middle of the page and the cards are
    pushed to the outer edges:

        away (left column)     cards | chart
        home (right column)    chart | cards

    ⚠️ WHICH MEANS THIS FUNCTION HAS TO KNOW WHICH SIDE IT IS, and it is called twice with the
    same signature. It reads `is_home` off the `srv_game_team` row it is ALREADY handed — see
    `_is_home_side` for what was measured and what the alternatives were.

    🚨 ONE LIST DECIDES BOTH THE ORDER AND THE COLUMN, which is the whole reason the test can
    be trusted. `order` is in left-to-right order and `st.columns` returns left-to-right, so
    zipping them makes the emission order and the visual position the SAME FACT. Reversing the
    list moves the card block and its emission together; there is no way to change one and
    leave the other, and therefore no way for a passing test to describe a layout that is not
    on the screen.

    ⚠️ THE WIDTHS COME OFF THE SAME LIST, WHICH IS WHY AN ASYMMETRIC RATIO IS SAFE HERE. The
    first version split the side 50/50 and the LIVE RENDER showed the away charts clipped on
    their right edge — the axis read "300 :" where the home side read "300 350". `autosize:
    pad` makes the spec's outer box the plot PLUS its axis labels, so 240px of square needs
    more than 240px of column. Weighting the chart slot fixes it, and because the weights are
    read out of `order` rather than written as a second tuple, a ratio cannot end up applied
    the wrong way round while the positional assertions still pass.
    """
    st.markdown(_yardage_side_heading(team, opponent), unsafe_allow_html=True)
    team_name = str(team.get("team_display") or "?")
    opponent_name = str(opponent.get("team_display") or "?")
    order = ("chart", "cards") if _is_home_side(deltas) else ("cards", "chart")
    widths = [_SLOT_WIDTHS[slot] for slot in order]
    # 🚨 R-756's SECOND HOLE, AND IT IS THE ONE NOBODY PREDICTED. The prompt's premise was *the
    # three figures survive in the annotation* — TRUE ONLY WHERE THE CHART SURVIVES. The
    # annotation lives INSIDE the Vega spec, so on every row that draws no chart the figures the
    # deleted table used to print now have nowhere to be. ⚠️ Not a rare path: A092 measured that
    # NO week-wide distribution exists at week 1 of a regular season, so the whole panel is in
    # this state at the start of every year.
    drawn = set()
    for index, (label, for_column, allowed_column, delta_column,
                outlook_column) in enumerate(_YARDAGE_DIMENSIONS):
        # 🚨 R-752. THE HEADER IS THE ROW'S, NOT THE CHART'S. It used to be the Altair spec's
        # own `title=`, which can only ever sit over the chart — Marc asked for a header for the
        # row, and *"maybe a header for each half (start with each half)"*. ✅ ONE PER HALF PER
        # METRIC, emitted before the row; a header spanning BOTH halves is his later option and
        # is deliberately not built, because the two halves are separate Streamlit columns.
        #
        # ⚠️ AND A SMALL RULE BETWEEN THE BLOCKS, NOT BEFORE THE FIRST. Marc: *"a small line or
        # element to break the space between Rushing, Passing, and Total."* A hairline at low
        # opacity — the three blocks are one panel, so this separates them without sectioning
        # them.
        st.markdown(
            ("<div style='border-top:1px solid currentColor;opacity:.12;"
             "margin:.9rem 0 0'></div>" if index else "")
            + f"<div style='font-weight:600;font-size:.95rem;margin:.45rem 0 .1rem'>"
              f"{html.escape(label)}</div>",
            unsafe_allow_html=True)
        chart = _scatter(team, opponent, for_column, allowed_column, distribution,
                         team_name, opponent_name, label,
                         _delta_for(deltas, outlook_column),
                         _delta_for(deltas, delta_column))
        if chart is not None:
            drawn.add(label)
        # R-687. The names go OUTSIDE the chart; R-731 puts them BESIDE it rather than below.
        panel_key = (int(team["team_id"]), _LEADER_PANELS[label])
        cards = _leader_block((leaders or {}).get(panel_key, []),
                              (usage or {}).get(panel_key))
        for slot, column in zip(order, st.columns(widths)):
            if slot == "chart":
                if chart is not None:
                    # ⚠️ NOT use_container_width: a square the container can stretch is
                    # not a square. R-609, and a narrower column does not change that.
                    column.altair_chart(chart, use_container_width=False)
                # ⚠️ R-751 MOVED THIS ONTO THE CHART. The block that used to sit under it is
                # `_annotation_layers` now, inside the spec — see `_scatter`.
            else:
                column.markdown(cards, unsafe_allow_html=True)
    # ⚠️ AN ABSENCE THAT SAYS WHICH ABSENCE IT IS (AC-G.11). A chart silently missing from a
    # row of three reads as "we hold nothing"; these two hold a figure that is off the scale
    # the rest of the week is drawn on, and the figures are printed in full just above.
    # 🚨 R-756 BROKE THIS SENTENCE AND THE ROUND THAT REMOVED THE TABLE HAD TO MEND IT.
    # It used to end *"The numbers are above"* — and "above" WAS the delta table. With the table
    # gone the only place those three figures survive is the annotation INSIDE the chart, so on
    # exactly the rows where the chart is DROPPED they now survive nowhere. **A caption that
    # points at figures that no longer exist is the R-571 class, and AC-G.11 asks an absence to
    # say WHICH absence it is — so the caption carries the numbers itself.**
    # ✅ Not a new layout: the sentence already named the metrics, and naming their values is
    # what makes it true again.
    off = _off_the_frame_metrics(team, opponent, distribution)
    if off:
        st.caption(
            f"{'  ·  '.join(_off_the_frame_figures(team, opponent, off))} not plotted — one of "
            f"each pair falls outside the range this week's chart is drawn on, so there is no "
            f"honest place to put the point.")
    # ⚠️ AND WHICH ABSENCE IT IS, SEPARATELY (AC-G.11). `off` is the metric we CAN explain — the
    # point leaves a frame we hold. This is the rest: no distribution built for the week, or an
    # axis that cannot carry a position. The page holds the two figures either way and says them.
    # ❌ NOT one merged sentence: "outside the week's range" and "there is no week's range" are
    # different facts, and B075's rule is that an absence names itself.
    unplotted = [label for label, *_rest in _YARDAGE_DIMENSIONS
                 if label not in drawn and label not in off]
    figures = _off_the_frame_figures(team, opponent, unplotted)
    if figures:
        st.caption(f"{'  ·  '.join(figures)} — not drawn against the week, because this week "
                   f"has no distribution to draw them against.")


# ⚠️ THE LEADER BLOCK LIVES BELOW `_yardage_column` ON PURPOSE.
# `test_the_CHART_CODE_does_not_divide` reads the source between `_week_distribution`
# and `_yardage_column` and bans a solidus there to catch a division. These functions are
# markup — every closing HTML tag carries one — so putting them inside that window would
# have meant widening a guard to fit code it was never about. Moving the code was free.
_LEADER_COLUMNS = """
    team_id, panel, leader_metric, leader_rank, tied_players, qualified_players,
    player_id, player_name, player_slug, jersey, position, class_year_display,
    stat_1_label, stat_1_value, stat_1_value_secondary, stat_1_format,
    stat_2_label, stat_2_value, stat_2_value_secondary, stat_2_format,
    stat_3_label, stat_3_value, stat_3_value_secondary, stat_3_format
"""

# 🚨 PASSING SHOWS RECEIVERS, AND THAT IS MARC'S PAIRING CARRIED AS DATA. The view's
# `leader_metric` already says which stat each panel ranks, so this page does not choose — it
# reads. ⚠️ Do not "correct" passing to passers: he asked for the receivers a passing game
# produced, which is a different and deliberate question.
_LEADER_PANELS = {"Rushing": "rushing", "Passing": "passing", "Total": "total"}

# ⚠️ `_ORDINAL` WAS HERE AND R-753 REMOVED IT WITH THE RANK BADGE. Marc: *"Don't include the
# rank."* The cards are drawn in rank order so the ORDER carries it; nothing carries a TIE any
# more, which the round reported rather than inventing a place for.


def _split_name(value) -> tuple:
    """A player's name as (first line, bold line). 🚨 AN ASSUMPTION, NOT A FORMAT.

    `player_name` is ONE STRING; the view does not carry the parts. **First token as the first
    name and the remainder as the last** is the rule, and it renders *Emmett Mosley V* and
    *Ray Davis Jr.* the way a reader expects — the remainder keeps the suffix with the surname
    rather than stranding it on its own line.

    ⚠️ A SINGLE-TOKEN NAME HAS NO FIRST LINE AND RENDERS AS THE BOLD LINE ALONE. An empty first
    line would still occupy its line-height and shift that one card's header down relative to
    the others — a hole reserved for something that does not exist (AC-G.11), and the same
    mistake as an em dash for an absent measure.
    """
    parts = str(value or "?").split()
    if len(parts) < 2:
        return "", (parts[0] if parts else "?")
    return parts[0], " ".join(parts[1:])


# 🚨 R-735. MARC: "Reduce Player Card width by 50%. The Player Card and Yard scatterplot
# should share the horizontal space at 1:4." ⚠️ THOSE ARE ONE INSTRUCTION AND THE RATIO
# GOVERNS: at the previous 1:1.2 the card was 45% of the pair and at 1:4 it is 20%, which is
# the "50%" reduction he asked for.
#
# ⚠️ THE FAILURE MODE HAS CHANGED SIDES AND ONLY A RENDER SEES IT. B098 measured that a 50/50
# split CLIPPED THE AWAY AXIS — it read "300 :" where home read "300 350" — because
# `autosize: pad` (R-609) ships the 240px square PLUS its labels. 1:4 gives the chart MORE
# room, so that cannot recur; the CARD is now the side with 20% and the side that can clip.
#
# ⚠️ Read out of `order` rather than written as a second mirrored tuple — see `_yardage_column`,
# which is why this is one literal rather than a layout round.
# 🚨 R-750. THE THIRD SLOT IS SLACK, AND COWORK MEASURED WHY THE RATIO ALONE CANNOT FIX IT.
# Marc: *"Too much white space between the left side and right side."*
#
#     outer split   `left, right = st.columns(2)` — each half is 50% of the page
#     the chart     `_CHART_SIDE = 240`, `use_container_width=False`
#
# 🚨 A PROPORTIONAL COLUMN CANNOT SIZE A FIXED-WIDTH ELEMENT. At ~1300px each half is ~640px
# and the chart slot took 4/5 of it — ~512px — to draw something ~300px wide. **The ~210px of
# dead space is INSIDE the chart slot**, on the side away from the cards, which is both gaps in
# his screenshot: between the away chart and the home block, and between the home chart and its
# own cards. ⚠️ **1:3 buys the card ~32px and removes ~32px of gap; it is the answer to the CARD
# being narrow and NOT to the white space. Two problems, named as one.**
#
# ✅ So a third slot absorbs the remainder at the OUTER edge of each half, pulling both halves'
# content toward the centre. ⚠️ IT IS STILL PROPORTIONAL AND THEREFORE BRITTLE ACROSS VIEWPORT
# WIDTHS — the page cannot read a column's pixel width — which is why this round renders at two
# of them rather than tuning against one. ❌ R-609 is NOT re-opened: the square stays 240px and
# `use_container_width` stays False.
_SLOT_WIDTHS = {"cards": 1.0, "chart": 1.6}

# R-731. The card is built for three KPI slots. ⚠️ THE SENTENCE THAT USED TO SIT HERE SENT A
# FUTURE ROUND TO `_CARD_KPIS`, WHICH B099 DELETED — the labels are read off the row now, and
# the block below says why. A comment naming a thing that no longer exists is the same class of
# stale instruction as the mirrors in `docs/` (§4.4).
_CARD_KPI_SLOTS = 3

# 🚨 R-806. THE NAME IS NOT AT THE JERSEY'S SIZE, AND THE MEASUREMENT IS WHY.
# Marc asked for *"Font same as Jersey number"*. ⚠️ MEASURED IN THE BROWSER, ON THE LIVE PAGE,
# at 1300px with the sidebar open — not derived, because the derivation was wrong first: the
# preview card is **150px** and the name row inside it **134px**, where an estimate off the
# half-width had said 168px.
#
#     size     px per char   chars that fit 134px   of 4 real 2026 names, clipped
#     1.5rem      11.0              12.2                  4 of 4  ← the jersey's, as asked
#     1.25rem      9.24             14.5                  3 of 4  ← shipped
#     1.1rem       8.29             16.2                  3 of 4
#     1.0rem       7.88             17.0                  1 of 4  (the 28-char outlier only)
#
#     names as `Last, First`:  median 14 · p90 17 · max 28 ("Abdul-Rahim Gladding, Na'eem")
#
# 🚨 SO THE JERSEY'S SIZE DOES NOT FIT THE MEDIAN NAME, LET ALONE THE LONG ONES.
#
# 🚨 R-835. MARC DID NOT PICK ONE OF THOSE FOUR SIZES — HE CHANGED THE SHAPE, AND THAT REMOVES
# THE CONSTRAINT INSTEAD OF TRADING AGAINST IT. 2026-09-14, verbatim: *"Font of the jersey
# number and last name are too big. First name should be above the last name in a small font.
# Jersey # Font can be bigger than Last Name b/c it has the vertical space of First Name <br>
# Last Name."*
#
# ⚠️ SO B106's *the name gets its own full-width row* IS REVERTED, AND NOTHING WAS BROKEN. It
# was the right call for the premise it had — `Last, First` on ONE line, where the longest
# string is the WHOLE name — and Marc removed that premise by putting the name back on two
# lines. **`Robinson, Steven` is 16 characters; `Robinson` is 8.** Splitting the name roughly
# halves the longest string the column has to hold, which is why this shape fits where four
# sizes of the other one did not.
#
#     ┌───────────────────────────────┐
#     │  #14    Steven      JR        │   first name — small, not bold
#     │         Robinson    RB        │   last name  — bold
#     └───────────────────────────────┘
#        jersey  name        year/pos
#
# ⚠️ THE ORDERING IS A RULE, NOT A PREFERENCE, AND IT IS ASSERTED: **jersey > last > first.**
# It is Marc's own reason the jersey may be the largest — it spans the two-line block, so it
# has height the name lines do not.
# ⚠️ AND BOTH CAME DOWN, because he said *too big* about the jersey's 1.5 AND the name's 1.25.
#
# 🚨 THE SET IS MEASURED, NOT OFFERED. Three complete sets were rendered from this very function
# at the card's real 150px and the truncations COUNTED — `claude_work/renders/
# B107_card_header_sets.png`, and the numbers are the reason this one shipped:
#
#     set                                     name lines truncated, of 10
#     A   jersey 1.25 · last 1.0  · first .75          2   (Singleton, Sanders II)
#     B   jersey 1.4  · last 1.05 · first .78          3
#     C   jersey 1.15 · last .92  · first .7           0   ← shipped
#
# ⚠️ `.92` IS NEAR THE CEILING RATHER THAN A ROUND NUMBER, AND THAT IS DELIBERATE: `Sanders II`
# is the longest surname the game holds at 10 characters and needs 70.8px of a 72px column at
# this size. At `.95` it truncates again. **The constant is the measurement.**
#
# 🚨 THE BAR THIS HAD TO BEAT: 7 of 18 rendered names truncated at B106's one-line `Last, First`.
_CARD_JERSEY_SIZE = 1.15
_CARD_LAST_SIZE = 0.92
_CARD_FIRST_SIZE = 0.7

# 🚨 R-848. *"'#' font needs to be a little bigger"*, AND IT IS ONE OF TWO LITERALS — SAY WHICH.
# The `#` is a RATIO of the jersey (R-806, `em` not `rem`, so it follows whatever the jersey is).
# **The RATIO moved, .5 → .62; the jersey did NOT.**
#
# ⚠️ AND THAT IS THE WHOLE REASON: B107 measured `_CARD_LAST_SIZE = .92` as a CEILING —
# `Sanders II` needs 70.8px of a 72px name column and truncates at `.95`. Growing the JERSEY
# widens its column and takes those pixels straight out of the name, which would put
# truncations back on a panel that measured 0 of 32. **Growing the ratio costs the name nothing:
# the `#` is 5px of a 26px jersey block and the block is `min-width`-bounded either way.**
_CARD_HASH_RATIO = 0.62


def _card_text(value) -> str:
    """A card field as text, with NULL meaning ABSENT rather than the string `nan`.

    🚨 `str(value or "")` DOES NOT DO THIS AND THAT IS THE WHOLE REASON THIS EXISTS: NaN is
    truthy, so the `or` never fires and the page prints `nan`. `pd.isna` is the only test that
    answers for None, NaN and NaT alike.
    """
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip()


# 🚨 R-733. THE LABELS ARE DATA NOW, AND B098 SAID WHY IT HAD TO CHANGE. That round shipped
# `_CARD_KPIS` — a static tuple of (label, column) — which was the right shape for ONE measure
# whose name the view did not carry. A116 then shipped three per row, and their names vary by
# panel:
#
#     passing   Receptions · Yards · TD
#     rushing   Carries · Yards · Yds/Carry
#     total     Comp-Att · Yards · TD
#
# ⚠️ A STATIC TUPLE BESIDE PER-ROW LABELS IS THE R-574 DRIFT A116 CHOSE THE VIEW TO AVOID, and
# the trio is explicitly still moving. So the tuple is gone and the label is read.
#
# ⚠️ `yards_through_prior_week` LEFT THE SELECT LIST WITH IT. It was that tuple's only reader and
# `stat_2_value` is the same number; a column selected for a reader that no longer exists is
# the drift this note is about, one layer down.

# The renderings the view names, parsed from its own source by the test rather than trusted
# here — see `test_the_page_knows_every_FORMAT_the_view_can_emit`.
_KPI_INTEGER = "integer"
_KPI_DECIMAL_1 = "decimal_1"
_KPI_PAIR = "pair"


def _kpi_value(value, secondary, format_name: str):
    """One KPI's number, rendered the way the VIEW says — or `None` if it does not say.

    ⚠️ `pair` COMPOSES `51-75` FROM TWO COLUMNS AND THAT IS FORMATTING, NOT ARITHMETIC (§4.2).
    A116 shipped two numbers rather than a finished string precisely so the page does the
    display and the warehouse does the measuring; joining them with a hyphen creates no new
    quantity, which is the line `players.py:202` crossed and R-611 spent two rounds removing.

    🚨 AN UNKNOWN FORMAT DRAWS NOTHING RATHER THAN SOMETHING PLAUSIBLE. A fourth rendering
    arriving from a later A round is a LAYOUT decision, and guessing at it — printing the raw
    float, or falling back to `integer` — would put a number on the card that nobody designed
    and that a reader cannot tell from a designed one.
    ⚠️ Drawing nothing is the safe half; the LOUD half is a test that reads the model's own
    source for its format literals, so a fourth one fails in CI on the commit that adds it
    rather than going quiet on the page.
    """
    if format_name == _KPI_INTEGER:
        return fmt.number(value, "", dp=0)
    if format_name == _KPI_DECIMAL_1:
        return fmt.number(value, "", dp=1)
    if format_name == _KPI_PAIR:
        return f"{fmt.number(value, '', dp=0)}-{fmt.number(secondary, '', dp=0)}"
    return None


def _is_home_side(deltas) -> bool:
    """Which side of the mirror this column is — READ, not passed (R-731).

    ✅ `is_home` IS ALREADY IN THE FRAME THIS PANEL HOLDS. `_GAME_TEAM_COLUMNS` selects it and
    `_yardage` hands each column its own `srv_game_team` row, so this costs no query and no new
    column. Measured against live serving: 225,350 rows, `is_home` set on every one, exactly
    two rows per game and exactly one of them home.

    ⚠️ THE TWO SOURCES THE PROMPT NAMED WERE MEASURED FIRST AND NEITHER IS USABLE HERE:

        srv_team_week                              has NEITHER is_home nor home_away — and it
                                                   should not: a team is not home or away in
                                                   a WEEK, only in a game
        srv_game_team_leader_through_prior_week     HAS home_away, but `_LEADER_COLUMNS` does
                                                   not select it, so reading it would mean
                                                   adding a column to a query to learn
                                                   something another frame already carries

    ⚠️ AND AN ABSENT ROW FALLS BACK TO THE AWAY ORDER RATHER THAN GUESSING. A game with no
    `srv_game_team` row draws no delta chips either, so it is already a degraded render; the
    mirror is then unmirrored, which is visible, rather than silently reversed on one side.
    """
    if deltas is None:
        return False
    value = deltas.get("is_home")
    if value is None or (not isinstance(value, bool) and pd.isna(value)):
        return False
    return bool(value)


def _game_leaders(game_id: int) -> dict:
    """Who leads each side through the PRIOR week, keyed by (team_id, panel).

    🚨 THE LONG NAME IS THE POINT. `srv_game_team_leader` answers a different question — who
    led IN this game, from its own box score — and on a preview that box score does not exist
    yet. A102 spent a round on two near-identically-named COLUMNS that disagreed on 83% of
    games; these are two VIEWS answering two windows, and the only thing standing between them
    is a test.
    """
    df = query(f"""
        select {_LEADER_COLUMNS}
        from srv_game_team_leader_through_prior_week
        where game_id = :game_id
        limit 60
    """, {"game_id": game_id})
    out = {}
    for _, r in df.iterrows():
        out.setdefault((int(r["team_id"]), str(r["panel"])), []).append(r)
    # ⚠️ ORDERED BY THE RANK THE VIEW ALREADY CARRIES, AND THE LIVE RENDER IS WHAT CAUGHT THIS.
    # Oklahoma's receivers came back 2nd, 1st, 3rd — the query has no `order by` and a
    # DataFrame preserves whatever order the driver returned. Sorting on `leader_rank` is
    # presenting the column's own answer, not deriving one: A106 computed the rank upstream
    # precisely so the page would not, and putting a row in rank order is not ranking it.
    for rows in out.values():
        rows.sort(key=lambda r: int(r["leader_rank"]))
    return out


# ⚠️ NAMED FIELDS RATHER THAN A DICT, AND `ci/check_page_reads.py` IS THE REASON. That guard
# reads `something.get("name")` as a COLUMN read and asks which query selects it; `timeline` is
# a key this page builds, not a column, so the dict form made a real guard report a false
# positive. The guard has a `PROVIDED_BY_THE_PAGE` escape hatch and using it would have meant
# editing session A's file to describe session B's data structure — so the structure changed
# instead. It reads better too: the shape is now stated once, here.
_Usage = namedtuple("_Usage", "timeline players")

_USAGE_COLUMNS = """
    team_id, panel, player_id, usage_game_id,
    usage_season_type_ordinal, usage_week,
    usage_total, usage_total_max_in_window, usage_games_in_window,
    usage_share_of_max
"""


def _game_usage(game_id: int) -> dict:
    """Marc's game dots, read as ONE frame for the whole panel (R-694).

    **Marc, 2026-09-12:** *"a small block of circles that run horizontal under the player. One
    circle for each game the team played and fill it if the player played the game, or to the
    proportion of the game the player played."*

    ⚠️ ONE QUERY FOR SIX CARDS' WORTH OF DOTS, not one per card. `_yardage` already reads four
    relations; a per-card read would be eighteen on a busy game.

    🚨 THE ORDER IS (season_type_ordinal, week) AND NEVER week ALONE. Postseason weeks restart
    at 1, so a bowl game sorts into October on the second key by itself. Sorted HERE rather than
    in SQL for the reason B091 gave about `leader_rank`: putting rows in the order a column
    already states is presenting that column's answer, not deriving one — and it is testable
    without a database, which an `order by` is not.

    ⚠️ THE TIMELINE IS THE TEAM's, THE FILLS ARE THE PLAYER's. Marc asked for one circle per
    game the TEAM played, so the timeline is the union of the games any of that side's leaders
    appear in; a player missing from one of them gets an empty circle rather than a shorter row.
    """
    df = query(f"""
        select {_USAGE_COLUMNS}
        from srv_game_team_leader_usage
        where game_id = :game_id
        limit 900
    """, {"game_id": game_id})
    rows = [r for _, r in df.iterrows()]
    rows.sort(key=lambda r: (int(r["usage_season_type_ordinal"]), int(r["usage_week"]),
                             int(r["usage_game_id"])))
    out = {}
    for r in rows:
        entry = out.setdefault((int(r["team_id"]), str(r["panel"])), _Usage([], {}))
        earlier = int(r["usage_game_id"])
        if earlier not in entry.timeline:
            entry.timeline.append(earlier)
        entry.players.setdefault(str(r["player_id"]), {})[earlier] = r
    return out


_DOT = 9


def _usage_dots(entry, player_id) -> str:
    """One circle per game the team played, filled to this player's share of his own maximum.

    🚨 THE FILL IS RELATIVE TO THE PLAYER'S OWN MAXIMUM, AND THE REASON IS MEASURED. Usage is
    strongly positional — medians QB 0.551, RB 0.134, WR 0.058, TE 0.041 — so a circle filled
    against a flat 0–1 scale leaves every receiver about 6% full. ⚠️ That is visually empty, and
    INDISTINGUISHABLE FROM "did not play", which is the one thing these circles exist to show.
    A107 proved it on Sedrick Alexander: 0.229 absolute is a nearly-empty circle and 93%
    against his own maximum.

    ✅ THE DENOMINATOR IS READ, NOT DERIVED. `usage_total_max_in_window` is a published column
    precisely so the page never takes a maximum over rows — that window function is the thing
    CLAUDE.md puts upstream, and computing it here would be the defect this design prevents.
    Scaling one published number by another published one to size a shape is rendering.

    ⚠️ AC-G.22 — THE FILL IS A SHAPE, NOT A COLOUR. Every circle uses one ink; only the filled
    HEIGHT carries the meaning, so the row reads identically in greyscale and to a colour-blind
    reader. B091's delta chips made the sign carry it and the colour only agree; this carries it
    in geometry and uses no second colour at all.
    """
    timeline = entry.timeline
    played = entry.players.get(str(player_id)) or {}
    dots = []
    for earlier in timeline:
        row = played.get(earlier)
        if row is None:
            # ⚠️ THE FIRST OF THE TWO ABSENCES: the team played, this player has no row for it.
            dots.append(
                f"<span title='Did not appear' style='width:{_DOT}px;height:{_DOT}px;"
                f"border-radius:50%;border:1px solid currentColor;opacity:.35;"
                f"display:inline-block'></span>")
            continue
        # 🚨 R-740 / §4.2.1. THE SHARE IS READ, NOT DIVIDED. A120 published
        # `usage_share_of_max` precisely so this page stops computing `usage_total /
        # usage_total_max_in_window` — the test is how many consumers the number can have, not
        # whether the result is a pixel. `usage_total` stays because the HOVER quotes the
        # absolute share, which is a different number from the scaled one.
        scaled = row.get("usage_share_of_max")
        share = row.get("usage_total")
        window = int(row.get("usage_games_in_window") or 0)
        # 🚨 R-740's SECOND HALF: THE RAISE IS GONE, AND COWORK ASKED FOR IT AND WAS WRONG.
        #
        # B102 made a null share raise, on the reasoning that the branch was provably dead and
        # a lie is worse than a loud failure. ⚠️ **BUT `_usage_dots` IS CALLED FROM
        # `_leader_card` INSIDE `_yardage_column`** — so ONE bad row would take down three
        # charts and nine cards for every viewer, on a game day, with no alert. The blast
        # radius was never one dot.
        #
        # ✅ ASSERT UPSTREAM, DEGRADE DOWNSTREAM. A121 shipped
        # `assert_leader_usage_carries_a_drawable_denominator`, so the BUILD fails on a row the
        # page cannot draw — that is the loud half, and it is upstream where it belongs. B099
        # reasoned exactly this way about an unknown KPI format eight hundred lines above, and
        # this is the shape the page should have had all along.
        #
        # ⚠️ AC-G.32: "NOTHING" IS NOT AN EMPTY CIRCLE. An empty circle at full border opacity
        # is what `did not appear` draws, and a null share means the opposite — he played and
        # we cannot scale it. So the dot is omitted entirely and the row is one shorter, which
        # is the same choice `_post_game_card_column` makes for a missing third rusher.
        if scaled is None or pd.isna(scaled):
            continue
        # ⚠️ THE CLAMP STAYS. It guards what a CSS gradient can accept rather than the metric —
        # a published ratio outside 0–1 would paint outside the circle instead of announcing
        # itself.
        fill = max(0.0, min(1.0, float(scaled)))
        # ⚠️ THE SECOND ABSENCE IS A CAVEAT RATHER THAN A GAP, AND THE HOVER CARRIES IT. With one
        # observation the maximum IS that game, so the circle is full by construction and means
        # "we have seen him once" rather than "fully involved" — B085's single-snapshot shape.
        note = (" · only 1 game observed, so this is his own maximum by construction"
                if window == 1 else f" · {window} games observed")
        dots.append(
            f"<span title='{float(share):.1%} of the team{note}' "
            f"style='width:{_DOT}px;height:{_DOT}px;border-radius:50%;"
            f"border:1px solid currentColor;display:inline-block;"
            f"background:linear-gradient(to top, currentColor {fill:.0%}, "
            f"transparent {fill:.0%})'></span>")
    return (f"<div style='display:flex;gap:3px;align-items:center;margin-top:.3rem;"
            f"flex-wrap:wrap'>{''.join(dots)}</div>")


def _card_tie(row) -> str:
    """The marker that says this player's place is SHARED — R-856's half of the tie problem.

    🚨 IT PUTS BACK WHAT R-753 TOOK, WITHOUT PUTTING BACK THE THING MARC REMOVED. His words
    were *"Don't include the rank"*, and this file recorded the cost in `_leader_card` at the
    time: *"`_ORDINAL` AND THE `T-1st` TIE MARKER WENT WITH IT… nothing now carries a TIE. Two
    players sharing second place render as second and third. Reported rather than solved in
    passing."* **So this deliberately does NOT read `T-1st`.** The cards are drawn in rank
    order and the order is what carries the place; what was missing is the statement that a
    place is not sole, and that is all this says.

    📊 IT IS NOT DEFENCE-ONLY, AND MAKING IT SO WOULD HAVE READ AS A DEFENSIVE ANNOTATION
    RATHER THAN AS A TIE. Measured on `srv_game_team_leader_in_this_game`, share of rows with
    `tied_players > 1`: passing rank 3 **9.8%**, rushing rank 3 **7.7%**, defensive rank 3
    **11.9%**, `total` **0.1%**. Every panel ties; the defence ties most. `tied_players` was
    already in `_POST_GAME_LEADER_COLUMNS` and read by nothing, which is how the gap survived.

    🚨 COWORK'S TIE FIGURES FOR THIS ROUND CAME OFF THE WRONG RELATION, AND IT IS THE EXACT
    TRAP ITS OWN PART 0 WARNED ABOUT. The prompt gave *"at rank 1, 20.3% of team-games are
    tied"*. **20.3% is `srv_game_team_leader` — 888 of 4,375 `defensive/TOT` rows — which is
    the relation this round DELETED, not the one the cards read.** Measured on the cards'
    relation, ties run **2.1% / 3.3% / 5.7%** of the 4,368 defensive team-games at ranks 1/2/3.
    ✅ The two figures Cowork took from the right relation were exact: **1,017 rows carry
    `tied_players > 1`**, and **5.9% of defensive team-games return more than three rows**.

    ⚠️ AND IT MUST NOT CHANGE THE CARD'S HEIGHT, WHICH IS WHY IT IS INLINE IN THE POSITION LINE
    RATHER THAN A LINE OF ITS OWN. `_RESERVED_CARD_HEIGHT` is pinned to a real card's 84px, and
    B109 measured what a 33px register error does to two columns side by side. A marker on its
    own row would grow ONLY the tied cards, so two cards in the same column would differ —
    worse than the misalignment R-849 exists to remove. At `.6rem` inside a line whose
    `line-height` is set by `.78rem` text, the inline span cannot raise the line box.
    """
    tied = row.get("tied_players")
    if tied is None or pd.isna(tied) or int(tied) <= 1:
        return ""
    return (f"<span style='font-size:.6rem;font-weight:400;opacity:.55;"
            f"white-space:nowrap'> tied {int(tied)}</span>")


def _leader_card(row, usage=None) -> str:
    """One player: name, jersey, position, class, and his yards so far.

    ⚠️ AC-G.32 ON THE JERSEY. 0 of 8,447 non-FBS leader rows carry one, because the roster
    load covers 138 of 305 teams (R-693) — so a missing jersey is an ABSENCE we can explain,
    not a zero and not a blank that reads as one. It renders as an em dash in the same slot,
    which keeps the cards aligned and says "we do not hold this" rather than "#0".
    """
    jersey = row.get("jersey")
    # 🚨 R-806. THE `#` GLYPH AT HALF THE DIGITS' SIZE. Marc: *"Reduce font of the # in Jersey #
    # to .5 of current value."* — the `#` alone, not the number, so `em` rather than `rem`: it
    # halves whatever the jersey is set to and cannot drift if that constant moves.
    # ⚠️ AC-G.32: NO JERSEY STILL RENDERS `—`, and it carries NO `#` — a hash with nothing after
    # it reads as a broken number rather than as an absence. B104 judged the doubled em dash an
    # absence rather than a defect; at this size it is the same em dash without the hash.
    number = (f"<span style='font-size:{_CARD_HASH_RATIO}em;opacity:.65'>#</span>{int(jersey)}"
              if pd.notna(jersey) else "—")
    first, last = _split_name(row.get("player_name"))
    # 🚨 R-753. THREE COLUMNS, AND THE RANK IS GONE. Marc: *"Don't include the rank. The header
    # row should have 3 columns: 1 - Jersey number · 2 - Present player name on 2 lines. First
    # name on top, not bold and small. Bold last name. · 3 - Position on top, year on bottom."*
    #
    # ⚠️ `_ORDINAL` AND THE `T-1st` TIE MARKER WENT WITH IT, AND SOMETHING WAS LOST. The cards
    # are drawn in rank order, so the ORDER still carries the rank — but nothing now carries a
    # TIE. Two players sharing second place render as second and third. **Reported rather than
    # solved in passing: inventing a new place for it is a look decision.**
    # 🚨 R-800. THE JERSEY IS 2x AND FILLS BOTH ROWS THE NAME BLOCK MAKES. Marc, v05: *"Make the
    # Jersey Number 2x in size. Fill the 2 rows First/Last creates."* So it is one glyph
    # spanning the header's full height rather than a small label on the first line.
    # ⚠️ AC-G.32 GETS LOUDER HERE: no jersey renders `—` at the same 2x size, which is a big em
    # dash. The round rendered it and reports whether it reads as an absence or as a defect.
    #
    # 🚨 R-801. COLUMN 3 IS COLUMN 2's MIRROR: year on top in the small faded line, POSITION in
    # the last name's treatment below it. Marc: *"Flip Position and Year, then apply last name
    # formatting to Position."* — the same SIZE AND WEIGHT as the surname, not `font-weight`
    # bolted onto a faded line, which is what makes the header read as a grid rather than as
    # three unrelated stacks.
    # 🚨 R-835. THE NAME IS TWO LINES AGAIN AND SHARES THE ROW — see `_CARD_JERSEY_SIZE` for
    # Marc's words and for why splitting the name is what makes it fit.
    small = "font-size:.66rem;opacity:.6;line-height:1.1"
    strong = "font-weight:700;font-size:.78rem;line-height:1.15"
    # 🚨 `nan` WAS REACHING THE PAGE, AND `or ""` IS EXACTLY WHY. A null arrives out of the
    # frame as `float('nan')`, and **NaN IS TRUTHY IN PYTHON** — so `row.get(…) or ""` returns
    # the NaN rather than the fallback and `str()` renders the three characters `nan`. B106's
    # own live render of Arkansas vs North Alabama is where this was seen; it is not new, and
    # it is not rare: 13,431 of 75,283 preview leader rows (17.8%) and 3,734 of 53,873
    # post-game rows (6.9%) carry no position and no class year.
    # ⚠️ AC-G.32, AND THE TWO SLOTS TAKE DIFFERENT ANSWERS ON PURPOSE. The position is a VALUE
    # and an absent value is an em dash — the same statement the jersey already makes one line
    # above. The year is the small faded line and it is the surname block's mirror (R-801), so
    # an absent year is an absent LINE, not a dash: B103 settled that a missing first name
    # renders the bold line alone rather than an empty row that shifts the card's height.
    year = _card_text(row.get("class_year_display"))
    position = _card_text(row.get("position"))
    tie = _card_tie(row)
    # ⚠️ `min-width:0` ON EVERY FLEX CHILD THAT CAN OVERFLOW, and it is what makes the ellipsis
    # work at all: without it a flex child refuses to shrink below its content and the name
    # pushes the year/position column off the card instead of truncating — the R-745 class,
    # five rounds old now.
    # ⚠️ THE JERSEY'S `min-width` CAME DOWN WITH ITS FONT, AND THE SECOND CUT WAS MEASURED.
    # 2.4rem was set for a 1.5rem jersey. At 1.25rem `#14` draws ~26px, so 2.4rem (38px) was
    # reserving 12px the NAME column needed — and the name column is the one that runs out.
    # 1.7rem (27px) still clears the widest real jersey, `#99` at ~26px, with a pixel to spare.
    # 🚨 MEASURED, NOT PICKED: at 2.0rem the name column was 68px and `Singleton` needed 74.
    clip = "min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
    name_block = (
        f"<div style='flex:1;{clip}'>"
        # 🚨 THE FIRST NAME IS OMITTED, NOT BLANKED, WHEN THERE IS NONE — B103's ruling, and it
        # survives the reshape unchanged. An empty first line would still take its line-height
        # and drop that one card's surname below its neighbours': a hole reserved for something
        # that does not exist (AC-G.11).
        + (f"<div style='font-size:{_CARD_FIRST_SIZE}rem;opacity:.6;line-height:1.15;{clip}'>"
           f"{html.escape(first)}</div>" if first else "")
        + f"<div style='font-weight:700;font-size:{_CARD_LAST_SIZE}rem;line-height:1.15;"
          f"{clip}'>{html.escape(last)}</div></div>")
    top = [
        # 🚨 `align-items:center` IS MARC'S OWN ARGUMENT MADE MECHANICAL: the jersey spans the
        # two-line block, so it is centred against BOTH lines rather than sitting on the first.
        # That vertical room is his stated reason it may be the largest of the three.
        f"<div style='min-width:1.7rem;font-weight:700;font-size:{_CARD_JERSEY_SIZE}rem;"
        f"line-height:1;display:flex;align-items:center'>{number}</div>",
        name_block,
        "<div style='text-align:right;min-width:0'>"
        + (f"<div style='{small}'>{html.escape(year)}</div>" if year else "")
        + f"<div style='{strong};white-space:nowrap'>"
          f"{html.escape(position) if position else fmt.EM_DASH}{tie}</div></div>",
    ]
    # 🚨 ONLY THE SLOTS THAT EXIST ARE DRAWN, AND AN EM DASH WOULD BE THE WRONG ABSENCE.
    # AC-G.32 puts a dash where a VALUE is missing; a slot with no label is a MEASURE that does
    # not exist, which is a different statement (AC-G.11). B098 argued this when two of three
    # were empty; it still holds for a slot the view leaves unnamed.
    cells = []
    for slot in range(1, _CARD_KPI_SLOTS + 1):
        label = row.get(f"stat_{slot}_label")
        if label is None or (not isinstance(label, str) and pd.isna(label)) or not str(label):
            continue
        shown = _kpi_value(row.get(f"stat_{slot}_value"),
                           row.get(f"stat_{slot}_value_secondary"),
                           str(row.get(f"stat_{slot}_format") or ""))
        if shown is None:
            continue
        cells.append(
            f"<div><div style='font-size:.6rem;letter-spacing:.03em;text-transform:uppercase;"
            f"opacity:.5;white-space:nowrap'>{html.escape(str(label))}</div>"
            f"<div style='font-size:.92rem;font-weight:600'>{shown}</div></div>")
    return (f"<div style='border:1px solid rgba(128,128,128,.22);border-radius:6px;"
            f"padding:.28rem .45rem;margin-bottom:.3rem'>"
            f"<div style='display:flex;align-items:stretch;gap:.4rem'>"
            f"{''.join(top)}</div>"
            f"<div style='display:grid;grid-template-columns:repeat({_CARD_KPI_SLOTS},1fr);"
            f"gap:.3rem;margin-top:.25rem;text-align:center'>{''.join(cells)}</div>"
            f"{_card_dots(row, usage)}</div>")


def _card_dots(row, usage) -> str:
    """The dots under one player — or the absence, and they are DIFFERENT absences (AC-G.11).

    🚨 NO USAGE ROWS AT ALL IS NOT "PLAYED NO GAMES", AND THE DATA PROVES IT. On 401856679 Ben
    McCreary is Oklahoma's SECOND-ranked rusher through the prior week — he has yards, so he
    played — and `srv_game_team_leader_usage` holds not one row for him. Drawing his team's
    games as a row of empty circles would say he appeared in none of them, which is false.
    ⚠️ So a player we hold nothing for gets a sentence, and a player we hold SOMETHING for gets
    the full timeline with empty circles where he is missing.

    ⚠️ 2026 COVERAGE IS STILL PARTIAL — A113 measured 12,955 rows over 1,162 games and A115
    found every per-game endpoint under-fetching the newest week (R-718). So this absence is
    common right now rather than exotic, which is exactly why it gets its own words.
    """
    if usage is None or not usage.timeline:
        return ""
    if not (usage.players.get(str(row.get("player_id"))) or {}):
        return ("<div style='font-size:.62rem;opacity:.45;margin-top:.3rem'>"
                "No game-by-game usage held for this player.</div>")
    return _usage_dots(usage, row.get("player_id"))


def _leader_block(rows, usage=None) -> str:
    """The three names under one chart — or an honest absence.

    ⚠️ FOUR STATES A106 MEASURED, AND EACH IS A DIFFERENT SENTENCE:
      · ZERO rows — a week-1 game, where nobody has yards through week zero. Not a failure.
      · FEWER THAN THREE — common early; Michigan's `total` panel is ONE name on 401856679
        and that is correct, because one quarterback has thrown.
      · A TIE — ranks are shared, so three-way-for-third returns MORE than three rows.
        🚨 NOT TRUNCATED: dropping the second of two tied players would invent a winner.
      · NO JERSEY — handled in `_leader_card`.
    """
    if not rows:
        return ("<div style='font-size:.75rem;opacity:.5;padding:.15rem 0'>"
                "No yards recorded before this week.</div>")
    return "".join(_leader_card(r, usage) for r in rows)


def _yardage(row) -> None:
    """Offense against defense, per game, LEADING INTO this game's own week (R-463).

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
    st.subheader("Offense vs Defense")
    # Its own section and its own view: this is the only block on the page that reads
    # srv_team_week, so a failure here degrades one panel rather than blanking a Matchup
    # that is otherwise complete.
    with states.section("srv_team_week", dataset=DATASETS["srv_team_week"],
                        degraded_if_missing="srv_team_week",
                        explanation="Week-grain team form has not been built yet."):
        home_id, away_id = row.get("home_team_id"), row.get("away_team_id")
        if pd.isna(home_id) or pd.isna(away_id):
            states.empty(
                "Each side's yardage against the other's defense would be here.",
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
                "Each side's yardage against the other's defense would be here.",
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
                "Each side's yardage against the other's defense would be here.", why)
            return

        # R-590. The week's shared frame, fetched once for both columns and all six charts.
        distribution = _week_distribution(row)
        # R-686. The three deltas, at this game's own grain. ONE query, both sides.
        deltas = _game_team_rows(int(row["game_id"]))
        # R-687. One read, both sides, all three panels.
        leaders = _game_leaders(int(row["game_id"]))
        # R-694. Marc's game dots, and the same rule: ONE read for six cards' worth.
        usage = _game_usage(int(row["game_id"]))

        # ⚠️ R-522 / spec §0: AWAY ON THE LEFT, HOME ON THE RIGHT. Marc made it a page law
        # rather than this panel's choice — "Data about Away team will be on the left. Same
        # information for the Home team will be on the right" — and the game header already
        # obeys it. The two blocks used to be stacked, away above home, which said the same
        # thing in a different shape on the same page.
        left, right = st.columns(2)
        with left:
            _yardage_column(away, home, distribution,
                            deltas.get(int(away_id)), leaders, usage)
        with right:
            _yardage_column(home, away, distribution,
                            deltas.get(int(home_id)), leaders, usage)

        # AC-G.33. The denominator is not decoration and it is named for each side
        # separately, because a bye or a missing box score makes the two differ.
        st.caption(
            f"Yards per game leading into week {int(row['week'])}, over "
            f"{counted[0]} completed game{'' if counted[0] == 1 else 's'} for "
            f"{home.get('team_display')} and {counted[1]} for {away.get('team_display')}. "
            f"games_counted is not games played — it counts the completed games both "
            f"sides of whose box score cfdb holds.")

        if distribution:
            sample = min(int(entry["min_games_counted"]) for entry in distribution.values()
                         if pd.notna(entry["min_games_counted"]))
            teams = int(next(iter(distribution.values()))["teams_in_week"])
            # 🚨 R-608: A THIN LINE AND A THICK LINE ARE ONLY SELF-DESCRIBING IF SOMETHING SAYS
            # SO. The weights carry which percentile each edge is, and a reader cannot deduce
            # that from the picture — so the sentence that explains the box explains its sides
            # too, in the one place that already had to exist.
            frame = (f"Both columns share one frame: the shaded box is the middle half of all "
                     f"{teams} FBS teams this week and the dashed lines are the medians, so "
                     f"every matchup in the week is drawn on the same axes. The box's thin "
                     f"sides are the 25th percentile and its thick sides the 75th.")
            if sample <= _THIN_SAMPLE:
                # 🚨 A092 MEASURED THIS AND SAID TO SAY IT. At 2026 week 2 the thinnest team
                # has played ONE game, so its "per game" IS that game — the same figure the
                # yardage board shows for a single result. Presenting that as season form is
                # the overclaim B077 removed from the leaders panel by deleting the word
                # "led", one panel along.
                frame += (f" ⚠️ Early in the season this is thin: the least-played team in "
                          f"the week has {sample} counted game"
                          f"{'' if sample == 1 else 's'}, so a per-game figure is close to a "
                          f"single afternoon rather than a settled average.")
            st.caption(frame)
        else:
            # ABSENT, NOT AN EMPTY FRAME. AC-G.11 and B075's rule: say WHICH absence it is.
            st.caption(
                "No week-wide distribution has been built for this week, so the charts that "
                "put these two sides against the rest of the FBS are not drawn.")
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
    season, season_type, week,
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
# offense_havoc_rate does not: offense_havoc_rate is havoc SUFFERED by that offense, not
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
    ("Havoc rate forced by this defense", "defense_havoc_rate", 3),
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


# --- R-847: the measure name goes LEFT, and the table goes hard left ----------------------
#
# **Marc, v08: *"move the measure name to the left, then 2 columns for the metric values. One
# big table, with a header row for Box Score / Logo Away / Logo Home"*.**
#
# 🚨 THIS REPLACES THE CENTRED CELL. IT DOES NOT EXTEND IT. `_METRIC_CELL_WIDTH`, the centring
# `margin:0 auto`, the per-panel value slots R-810 sized and `_METRIC_BOX_WIDTH` are all GONE —
# a round that left them beside this would put two layout systems in one panel, which is the
# drift this file has paid for five times. ✅ **Not wasted work and not a criticism of Marc: he
# is converging by eye and this is what that looks like.**
#
# ⚠️ WHAT SURVIVES FROM R-807, BECAUSE IT WAS NEVER ABOUT CENTRING: **both values stay
# RIGHT-ALIGNED.** A column of figures that lines up on its first digit rather than its units is
# unreadable, and that is true wherever the column sits.
#
# ⚠️ AND ONE WIDTH FOR BOTH SECTIONS, NOT R-810's TWO. R-810 sized Box Score and Advanced
# separately because a CENTRED cell could differ per panel without the centre moving. Marc has
# now asked for *one big table*, so the two sections' columns must line up with each other down
# the page — and that means the widest value in EITHER section governs BOTH.
#
# 📊 MEASURED IN THE BROWSER, by the text box rather than the slot:
#
#     `1 (1 INT · 0 FUM)`   110px   ← the widest anywhere, and it is Box Score's TURNOVERS row
#     `47.1%`                43px   ← the widest in Advanced
#     `Havoc rate forced by this defense`  188px at .85rem  ← the widest measure name
#
# 🚨 ONE ROW GOVERNS THE VALUE COLUMN AND IT IS NOT A METRIC ROW — turnovers is 2.5x the next
# widest value on the page. Reshaping it is a look decision and Marc's; this round measured it.
_TABLE_VALUE_WIDTH = 7.25      # rem — 116px against a measured 110px worst case
_TABLE_LABEL_WIDTH = 12.0      # rem — the longest measure name, verbatim
_TABLE_GAP = 0.5               # rem, between the three columns

# ⚠️ THE MEASURE NAME IS LEFT-ALIGNED AND FIXED-WIDTH, not `flex:1`. A flexing name column is
# what pushed the two figures apart in the centred layout (R-807); here it would let the value
# columns drift right as the table column grows, so the two sections would stop lining up at
# exactly the viewport widths where there is room to notice.
_TABLE_LABEL_CELL = (f"width:{_TABLE_LABEL_WIDTH}rem;flex:none;opacity:.75;font-size:.85rem;"
                     f"overflow:hidden;text-overflow:ellipsis")
_TABLE_VALUE_CELL = (f"width:{_TABLE_VALUE_WIDTH}rem;flex:none;font-weight:600;"
                     f"text-align:right;overflow:hidden;text-overflow:ellipsis;"
                     f"white-space:nowrap")
# 🚨 `overflow:hidden` ON THE ROW — R-755, and this panel has paid for it twice. A Streamlit
# column does not clip its children, so a row wider than its share draws OVER the column beside
# it rather than compressing. The table is hard left now and the card columns are to its right,
# so what it would overrun is the AWAY CARDS.
_TABLE_ROW = "display:block;max-width:100%;box-sizing:border-box;padding:.15rem 0;overflow:hidden"
_TABLE_ROW_INNER = f"display:flex;align-items:baseline;gap:{_TABLE_GAP}rem"


def _table_band_width() -> float:
    """ONE band's width — it sits under its own value column, so it IS the value column.

    ⚠️ AND IT IS SMALLER THAN EITHER NUMBER B108 SHIPPED. That round sized the bands against a
    CENTRED cell whose halves were 216px (Box Score) and 148px (Advanced); v08's value columns
    are 116px, so the band loses room in both sections. **The report carries the measurement
    against the 200px floor rather than burying it — it is a consequence of the shape Marc
    asked for, not a choice this round made.**
    """
    return _TABLE_VALUE_WIDTH * _REM


_REM = 16
_TABLE_BAND_WIDTH = int(_table_band_width())


def _table_header(away, home, title: str, colors=None) -> str:
    """Marc's *"header row for Box Score / Logo Away / Logo Home"*, with a rule beneath it.

    ⚠️ THE TEAM COLOUR IS A RULE AND NOTHING ELSE — `identity.accent_style`'s own docstring
    calls that *"the only place a team colour is allowed to appear (AC-G.25)"*, and B102
    measured why: a raw hex behind text is 1.8 luma from its neighbour in dark mode. **A border
    needs no contrast maths, so there is none in this file.**

    🚨 AND `light-dark()` RATHER THAN THE ON-LIGHT VARIANT ALONE, BECAUSE THE RASTER CAUGHT THE
    ALTERNATIVE FAILING. The app's precedent is `identity.text_on(row)`, which defaults to the
    ON-LIGHT colour — `_drives` says so in its own comment, *"which is what team.py does and the
    only precedent in the app"*. **Rendered in dark mode, North Alabama's accent came out
    `rgb(0,0,0)` against a `rgb(14,17,23)` page: invisible.** Not a corner case — **6,338 of
    34,061 team rows (18.6%) publish `#000000` as their on-light colour, and every one of them
    has an on-dark variant.**

    ✅ `light-dark()` IS THE TOOL THIS CODEBASE ALREADY USES FOR EXACTLY THIS, and theme.py says
    why in full: it follows the `color-scheme` property Streamlit sets, where
    `prefers-color-scheme` answers the OPERATING SYSTEM and gets a reader on a dark Mac with the
    app in Light the wrong palette (R-547, R-552). **Both variants come straight from
    `identity.text_on`; nothing here computes a colour.**

    ⚠️ A TEAM WITH NO SOURCED COLOUR DRAWS `identity.FALLBACK` — neutral grey, same footprint,
    in both modes. Measured: 10.89% of games have a side with no colour published.
    """
    cells = [f"<span style='{_TABLE_LABEL_CELL};font-weight:700;opacity:.9;"
             f"font-size:.92rem'>{html.escape(title)}</span>"]
    for side, key in ((away, "away"), (home, "home")):
        logo = identity.logo_or_monogram(
            side.get("team_logo_url"), str(side.get("team_display") or "?"), 20)
        pair, abbr = (colors or {}).get(key) or (None, "")
        accent = (f"light-dark({identity.text_on(pair)}, "
                  f"{identity.text_on(pair, dark_theme=True)})")
        # 🚨 R-856. THE ABBREVIATION, FALLING BACK TO THE FULL NAME. `North Alabama` did not
        # fit this cell and drew `North Ala…`; `UNA` fits with room to spare, and the LOGO
        # beside it is doing the identifying work that a clipped word was failing at. The
        # monogram still comes off the full name — a two-letter fallback built from `UNA`
        # would be a worse answer than one built from `North Alabama`.
        name = abbr or str(side.get("team_display") or "?")
        cells.append(
            f"<span style='{_TABLE_VALUE_CELL};font-weight:700;display:flex;"
            f"align-items:center;justify-content:flex-end;gap:.3rem;"
            f"border-bottom:3px solid {accent};padding-bottom:.15rem'>{logo}"
            f"<span style='overflow:hidden;text-overflow:ellipsis'>"
            f"{html.escape(name)}</span></span>")
    return (f"<div style='{_TABLE_ROW}'><div style='{_TABLE_ROW_INNER}'>"
            + "".join(cells) + "</div></div>"
            # Marc: *"a horizontal line between the header row and the metrics row"*.
            + "<div style='border-top:1px solid currentColor;opacity:.25;"
              "margin:.15rem 0 .35rem'></div>")


# 🚨 R-808. THE DISTRIBUTION THE BANDS ARE DRAWN AGAINST — Marc, v07: *"use it to show the
# spread/dispersion of each metric in the Box Score and Advanced… where the data point lands
# shown with a bright vertical bar, labeled."*
#
# ⚠️ `srv_game_team_metric_distribution`, AND THE GRAIN IS THE WHOLE CHOICE. It is every FBS
# TEAM-GAME in that week, so the band answers *where did this team's afternoon sit among every
# other team's afternoon* — which is the question a box score invites. The two siblings answer
# different ones: `srv_week_metric_distribution` is game-grain (both teams summed) and
# `srv_team_week_metric_distribution` is a team's cumulative season form, which is what the
# Offense-vs-Defense charts already use.
#
# ⚠️ AND IT PUBLISHES EXACTLY THE EIGHTEEN MEASURES THE TWO PANELS RENDER — 6 in Box Score and
# 12 in Advanced — which is not a coincidence: A125 built it for this call site.
_DISTRIBUTION_ROW_COLUMNS = """
    metric, n, team_games_in_week,
    min_value, whisker_low, p25, p50, p75, whisker_high, max_value
"""


def _metric_distribution(season, season_type, week) -> dict:
    """Every measure's spread for this week, keyed by metric. ONE read for eighteen bands.

    🚨 ONE READ, NOT ONE PER MEASURE. Eighteen queries for one panel would be eighteen round
    trips per page load, and `query` caches on the parameter set — so this is one read per TTL
    window across every game in the week, not one per render.

    ⚠️ AC-G.39, AND THE LIMIT IS THE GRAIN RESTATED RATHER THAN A GUESS AT A CEILING: one row
    per metric per week, and serving publishes eighteen. ⚠️ IT IS A LITERAL RATHER THAN A NAMED
    CONSTANT because `ci/check_page_queries.py` interpolates these strings to execute them and
    cannot resolve a placeholder it has not been taught — every other query in this file states
    its limit the same way.
    """
    if season is None or week is None:
        return {}
    df = query(f"""
        select {_DISTRIBUTION_ROW_COLUMNS}
        from srv_game_team_metric_distribution
        where season = :season and season_type = :season_type and week = :week
        limit 24
    """, {"season": int(season), "season_type": str(season_type or "regular"),
          "week": int(week)})
    return {str(r["metric"]): r for _, r in df.iterrows()}


def _metric_band(row, away_value, home_value, width, dp) -> str:
    """The spread for one measure, under its two figures — A125's `box()`, at this cell's width.

    ❌ `site/lib/distribution.py` IS SESSION A's AND IS NOT EDITED HERE (§3 rule 3.1). This is
    the call site A125 shipped the parameters for.

    🚨 TWO BANDS, ONE PER SIDE, AND THAT IS THE POINT RATHER THAN A DUPLICATION. The measure's
    spread is the same for both teams; what differs is WHERE EACH TEAM'S OWN FIGURE FALLS in it,
    which is the only thing Marc asked the bright bar to show. One shared band could carry only
    one of the two marks, and the panel exists to compare two sides.

    ⚠️ ONE BAND PER VALUE COLUMN SINCE R-847 — it sits directly under its own figure, so its
    width IS the value column's. The centred cell it used to split in half is gone.

    ⚠️ THE WHISKERS DRAW `whisker_low`/`whisker_high`, NOT `min_value`/`max_value`, AND BOTH ARE
    PUBLISHED. v07 said *"measure the min/max"* and v06 said *"label upper/lower boundaries"* —
    they are different columns and they are different numbers. **The fences are drawn, because
    the extremes compress the box to nothing: on 2026 week 1 rushing yards the box is 35% of the
    whisker span and 22% of the min-max span, and the outliers are counted separately in
    `outlier_count` precisely so the box stays readable.** `box()` reads the fences and is A's;
    this call site could not choose otherwise without editing it.
    """
    if row is None:
        return ""
    # ⚠️ THE LABEL COLUMN IS SPANNED BY AN EMPTY SPACER so each band starts exactly under its own
    # figure. Without it the two bands would begin at the row's left edge and sit under the
    # measure NAME, pointing at the wrong column.
    return (f"<div style='{_TABLE_ROW_INNER};margin-top:.05rem'>"
            f"<span style='{_TABLE_LABEL_CELL}'></span>"
            + "".join(
                f"<span style='width:{_TABLE_VALUE_WIDTH}rem;flex:none;min-width:0'>"
                f"{distribution.box(row, value=v, width=int(width), dp=dp)}</span>"
                for v in (away_value, home_value))
            + "</div>")


def _comparison(away, home, rows, glossary=None, spread=None,
                value_width=None, dp_band=None) -> str:
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
        # ⚠️ THE RAW COLUMN FEEDS THE BAND, NOT `_figure`'s STRING. `_figure` returns serving's
        # display string where there is one — `47.1%` for six of the Advanced rates — and the
        # distribution is published in the metric's own unit. A band drawn from the display
        # string would be drawing from text.
        lines.append(_metric_cell(
            _figure(away, field, dp), marked, _figure(home, field, dp),
            band=_metric_band((spread or {}).get(field), away.get(field), home.get(field),
                              _TABLE_BAND_WIDTH,
                              dp if dp_band is None else dp_band)))
    return "".join(lines)


def _metric_cell(away_value: str, label: str, home_value: str, band: str = "") -> str:
    """One measure, as a table row: NAME LEFT, then the two figures (R-847).

    ⚠️ AWAY BEFORE HOME, AND IT IS ONE ORDERED PAIR RATHER THAN TWO ARGUMENTS USED TWICE — the
    away-over-home law this site follows everywhere (R-522). B082 and B083 both proved a
    presence assertion cannot see a left/right swap, so the test asserts the ORDER.

    ⚠️ THE BAND GOES INSIDE THE ROW, so it inherits `overflow:hidden` and cannot draw over the
    card columns now sitting to the table's right — R-755, which this panel has paid for twice.
    """
    row = (f"<div style='{_TABLE_ROW_INNER}'>"
           f"<span style='{_TABLE_LABEL_CELL}'>{label}</span>"
           f"<span style='{_TABLE_VALUE_CELL}'>{away_value}</span>"
           f"<span style='{_TABLE_VALUE_CELL}'>{home_value}</span></div>")
    return f"<div data-cfdb='metric-cell' style='{_TABLE_ROW}'>{row}{band}</div>"


def _custom_row(away, home, label, renderer) -> str:
    """A measure the view publishes no distribution for — a fraction, a composite, a clock.

    🚨 NO BAND, AND THAT IS AC-G.11 RATHER THAN AN OVERSIGHT. `box()`'s own placeholder says
    *"cfdb holds no distribution for this week yet"*, which is TRUE of a measure that could have
    one and FALSE of these five: third down is `6/14`, turnovers is `1 (1 INT · 0 FUM)` and
    possession is `30:51`. **They are not scalars, so there is nothing to take a percentile of —
    ever — and a placeholder promising one later would be the wrong absence.**
    """
    return _metric_cell(renderer(away), label, renderer(home))


# The first season any of the three after-tab subjects exists at all. Drives, box scores and
# player box scores all start here: claude_code/CLAUDE.md puts play-by-play scope at "2024,
# 2025, 2026 only", and srv_game_team carries an all-NULL box-score row for every game before
# it. One constant because one change of scope moves all three.
_COLLECTED_FROM = 2024


def _absence_note(season, not_yet: str, out_of_scope: str) -> str:
    """WHICH absence this is (AC-G.11), and until R-730 the page could not tell.

    🚨 THE SENTENCE ON THE DRIVES PANEL WAS FLATLY FALSE AND A112 RENDERED IT. Michigan vs
    Oklahoma, `is_completed = True`, kicked off at 9:00 AM and read six hours later:

        "Drives are collected from 2024 onward, and a game that has not kicked off yet
         has none."

    ⚠️ The game had kicked off, and finished. The other two sections said something TRUE for
    the wrong REASON — "we hold this from 2024 onward, and this game's is not among it"
    invites SCOPE as the explanation when for a 2026 game the reason is LATENCY.

    ⚠️ AND THE WINDOW IS THE POINT. It opens when the game ends and closes when the next
    collection lands, which is exactly when a reader opens the page to see what happened.

    **Two states reach here, not three.** `_available_tabs` gives an unplayed game no after
    tab at all, so every caller of this is already past `is_completed` — see its docstring,
    which argues that an absent tab beats an empty one. The "not kicked off yet" case the old
    copy described is unreachable from these three panels by construction.

    ⚠️ SAY WHEN, NOT WHICH JOB (AC-G.7). "Collected after the game finishes" tells a reader to
    come back; naming the run that has not happened names an internal they cannot act on.
    """
    if season is not None and int(season) < _COLLECTED_FROM:
        return out_of_scope
    return not_yet


# 🚨 R-738. THE POST-GAME CARDS READ A DIFFERENT VIEW FROM THE PREVIEW'S, AND THE TWO NAMES
# DIFFER BY A SUFFIX. `..._through_prior_week` is what a player brought INTO the game;
# `..._in_this_game` is what he did IN it. ⚠️ A102 spent a whole round on a pair this similar,
# so these constants and their reader are deliberately separate from `_LEADER_COLUMNS` and
# `_game_leaders` — one function must never be able to read both.
_POST_GAME_LEADER_COLUMNS = """
    team_id, panel, leader_rank, tied_players, qualified_players,
    player_id, player_name, player_slug, jersey, position, class_year_display,
    stat_1_label, stat_1_value, stat_1_value_secondary, stat_1_format,
    stat_2_label, stat_2_value, stat_2_value_secondary, stat_2_format,
    stat_3_label, stat_3_value, stat_3_value_secondary, stat_3_format
"""

# Marc, v03: *"Include QA, Top 3 Rusher"*. ⚠️ `QA` READ AS `QB` — his v02 pairing was
# "Total → top 3 QBs", and the `total` panel ranks quarterback total yards.
#
# 🚨 ONE QB AND THREE RUSHERS, AND A120 MEASURED WHY IT IS NOT THREE OF EACH: of 6,736 `total`
# groups, **6,300 — 93.5% — have fewer than three leaders**, and 3,990 have exactly one. A team
# plays one quarterback. Marc's own wording already says so: QB singular, three rushers.
#
# 🚨 R-809. THE RECEIVERS JOIN THEM, AND THIS IS A SCOPE EXPANSION RATHER THAN A DEFECT FIX.
# Marc, 2026-09-14: *"I don't see any WR in the player cards, but I see the RB's in Box Score AND
# Advanced. We need full coverage."*
#
# ⚠️ THERE WERE NO RECEIVERS BECAUSE NOTHING ASKED FOR ANY. His v03 said *"Include QA, Top 3
# Rusher"* and that is exactly what shipped — the `passing` panel was never in this tuple.
# **Nothing was broken; the ask grew.** Saying so matters: a round that reports this as a bug
# reports a fix for something that was working to its specification.
#
# ⚠️ AND `passing` IS THE RECEIVERS, NOT THE PASSERS — A116 and B099 both settled that, and the
# quarterback is already here under `total`. Correcting "passing" to "passers" would draw the
# same man twice and still leave Marc without a WR.
#
# ✅ ORDERED THE WAY A READER READS A GAME: the quarterback, then who ran it, then who caught it.
# ✅ AND THE DATA IS THE BEST-COVERED OF THE THREE — A120 measured the passing panel at 7,341
# groups with only 50 (0.7%) holding fewer than three players, against rushing's 6.6%.
#
# 🚨 THE DEPTH CAME DOWN 3 → 2, AND IT IS THE DIAL COWORK NAMED RATHER THAN ONE THIS ROUND
# INVENTED: *"if seven cards run taller than the panel they flank, TRIM THE DEPTH — 3 → 2 per
# discipline — RATHER THAN DROP A DISCIPLINE. Coverage is what he asked for; depth is the
# adjustable dial."* ⚠️ THE CONDITION FIRED, MEASURED on Sam Houston at Troy at 1300px:
#
#     depth              cards   card column   Box score   Advanced    overrun
#     3 per discipline     7        515px         353px       384px    +162 / +131
#     2 per discipline     5        426px         353px       384px     +73 /  +42   ← shipped
#
# 🚨 AND IT COLLIDES WITH A LITERAL OF MARC'S OWN, WHICH IS FLAGGED RATHER THAN RESOLVED HERE:
# v03 says *"Include QA, Top 3 Rusher"* — **three** is his number for the rushers. The RECEIVERS
# have no stated depth, so `("passing", 2)` contradicts nothing; `("rushing", 2)` contradicts
# him. ⚠️ **It is one literal to put back, and B107's report puts the trade in front of him with
# these numbers rather than deciding it in a comment.**
# 🚨 R-848. GROUPED, WITH A HEADER OVER EACH GROUP, AND THE DEPTH IS MARC'S OWN v08 NUMBER.
# *"grouped with a header above each section: Quarterback (2, if 2 QBS played…), Rushing (3),
# Receiving (3, in the Advanced section)"*
#
# ⚠️ THIS REOPENS A DECISION HE MADE AN HOUR EARLIER — R-840, *keep 2 and 2 as shipped*, with
# the height trade in front of him. **v08 supersedes it on his word; it is not new work being
# smuggled in.**
#
# 🚨 AND RECEIVING-IN-ADVANCED-ONLY IS THE SPLIT COWORK EXPLICITLY REJECTED IN B107's PROMPT —
# *"nothing in the data makes that division mean anything"*. ✅ **Marc overruled it and his
# reason beats the objection: Cowork argued about MEANING, he is arguing about FIT.** Eight
# cards beside one panel is a different shape from five beside each of two.
#
# ⚠️ HOW *"Receiving (3, in the Advanced section)"* IS READ, AND IT IS ONE LINE TO CHANGE:
# **the quarterbacks and rushers stay in BOTH sections, and receiving is ADDED in Advanced.**
# The parenthetical places receiving; it does not say the others move. So Box Score draws five
# and Advanced draws eight, which is the "EIGHT per side" the round was briefed on.
# 🚨 R-839's PAGE HALF. THE DEFENCE JOINS BOX SCORE, AND IT IS THE ONLY DEFENSIVE FIGURE LEFT
# ON THE PAGE. The `st.subheader("Game leaders")` section went in the same round (B110), and its
# own comment had already measured what that section alone carried: `defensive/TOT` was one of
# two rows *"NOWHERE ELSE"*. **Deleting it without this tuple line would have taken the last
# tackle off the Matchup page.** The two changes are one change and must not be separated.
#
# ✅ A128 BUILT THE PANEL TO DROP STRAIGHT IN, AND IT DOES — VERIFIED RATHER THAN ASSUMED:
# Solo-Ast · Tackles · TFL, with `stat_1_format` = `pair`, which is the format `Comp-Att`
# already uses. **No new page branch, and `game_yards` is read NOWHERE in this file** — the
# cards read the generic `stat_N_*` slots, so the 19.9% of defensive rows with a null
# `game_yards` cannot draw a hole here. Checked before building, not after.
#
# ⚠️ BOX RATHER THAN ADVANCED, ON BALANCE: box goes 5 → 8 and advanced stays 8. The
# meaning argument — tackles are counting stats, Box Score is the counting panel — is the
# weaker of the two, because Marc split receiving by FIT rather than by meaning (R-848).
_CARD_GROUPS = {
    "box": (("Quarterback", "total", 2), ("Rushing", "rushing", 3),
            ("Defense", "defensive", 3)),
    "advanced": (("Quarterback", "total", 2), ("Rushing", "rushing", 3),
                 ("Receiving", "passing", 3)),
}

# 🚨 R-849. THE GROUPS A MISSING PLAYER IS RESERVED IN, AND IT IS SCOPED RATHER THAN GENERAL.
#
# **Marc: *"Quarterback (2, if 2 QBS played. If only 1 QB played reserve space for the second on
# with a blank, so home/away cards are aligned)"*.**
#
# 🚨 THIS REVERSES AC-G.11, B103's RULING AND B107's OWN `test_a_SHORT_ROW_is_drawn_SHORT_and_
# reserves_no_hole` — AND HE IS NOT BEING INCONSISTENT. **R-847 changed what the right answer
# is.** While the cards FLANKED the table, a short away column had nothing to line up against.
# **Side by side, an unmatched slot puts every row below it out of register between the teams.**
#
# ✅ AND IT KEEPS BOTH RULES, BECAUSE A RESERVED SLOT IS NOT A HOLE IF IT SAYS IT IS RESERVED.
# An empty card reading *no second quarterback* is a statement; an empty box with nothing in it
# is the hole AC-G.11 forbids. **Drawn, never left as a gap.**
#
# 📊 AND IT EARNS ITS KEEP — MEASURED BEFORE IT WAS BUILT (§2.5):
#     3,990 of 6,736 team-games — 59.2% — have exactly ONE quarterback in the `total` panel
#     🚨 1,812 of 3,520 games — 51.5% — have the two sides carrying DIFFERENT counts
# **So more than half of all games are the case this exists for.**
#
# ⚠️ QUARTERBACK ONLY. Rushing is short 6.4% of the time and receiving 0.7%, and those groups
# sit BELOW the quarterbacks — a short rushing group misaligns nothing under it in the other
# column, because receiving is the last group in the only section that has it. **A reserved slot
# there would be a hole bought for no alignment.**
_RESERVED_GROUPS = ("Quarterback",)

# 🚨 THE RESERVED CARD IS A REAL CARD'S HEIGHT, AND THE FIRST VERSION WAS NOT — WHICH MADE THE
# WHOLE FEATURE USELESS. A `min-height:3.2rem` slot measured 51px against a real card's 84px, so
# reserving kept the two columns' card COUNTS in step and left their group headers **33px out of
# register** — the exact misalignment R-849 exists to remove, moved down a level. **Only the
# raster showed it: every card was present and the count was right.**
#
# 📊 84px MEASURED IN THE BROWSER at 1300px with the sidebar open, and it is uniform — a card's
# height is its jersey block plus its KPI row, and neither varies with the name (nowrap, and
# ellipsised since R-745). `box-sizing:border-box` so the border and padding sit INSIDE it.
_RESERVED_CARD_HEIGHT = 5.25   # rem = 84px

# 🚨 R-847. TABLE HARD LEFT, THEN AWAY CARDS, THEN HOME CARDS. Marc, v08: *"Move the Box Score
# and Advanced tables all the way to the left. Move the Away Player Cards to be next (left) of
# the Home Player cards."*
#
# ⚠️ AWAY BEFORE HOME SURVIVES (R-522, spec §0). What ENDS is the MIRROR — `order` used to be
# reversed per side so the cards flanked the table, and B105 measured that as the reason one
# overflow landed on a different neighbour on each side. **Both card columns are on the same
# side now, so there is no mirror left to get the wrong way round.**
#
# 📊 THE RATIO IS THE OLD ONE RE-EXPRESSED, NOT A NEW GUESS. B108 measured the three columns at
# 1300px with the sidebar open: **table 493px, cards 157px each.** The same three widths in the
# new order are 3.14 : 1 : 1, so the table keeps the width it had and the cards keep theirs —
# **only their positions move, which is exactly what Marc asked for.**
#
# 🚨 ONE LIST DECIDES BOTH THE ORDER AND THE WIDTH, WHICH IS B098's PATTERN AND THE REASON A
# TEST CAN BE TRUSTED HERE. `st.columns` returns its columns LEFT TO RIGHT, so zipping them
# against this list makes the visual position and the width THE SAME FACT. **There is no way to
# move a block without moving its width, and therefore no way for a passing positional test to
# describe a layout that is not on the screen.**
_POST_GAME_LAYOUT = (("table", 3.14), ("away", 1.0), ("home", 1.0))
_POST_GAME_SPLIT = tuple(width for _slot, width in _POST_GAME_LAYOUT)


def _post_game_columns():
    """The three columns, keyed by slot — table, away cards, home cards, left to right."""
    return dict(zip((slot for slot, _w in _POST_GAME_LAYOUT),
                    st.columns(_POST_GAME_SPLIT)))


def _post_game_flank(away_col, home_col, leaders, away, home, section: str) -> None:
    """Both sides' cards, side by side to the RIGHT of the table (R-847).

    🚨 AWAY THEN HOME, AND THE ORDER IS THE PAGE LAW (R-522) RATHER THAN A HABIT. It used to be
    a MIRROR — the cards flanked the table, so away sat left of it and home right of it — and
    B105 measured that mirror as the reason a 59px overflow landed on a different neighbour on
    each side. **Both columns are on the same side now, so the mirror is gone; the ordering
    survives it.** ⚠️ B082 and B083 both proved a presence assertion cannot see a left/right
    swap, so the test asserts the ORDER of the two blocks.
    """
    for column, side in ((away_col, away), (home_col, home)):
        column.markdown(
            _post_game_card_column(leaders, int(side["team_id"]), section),
            unsafe_allow_html=True)


def _post_game_identity(game_id: int) -> dict:
    """The two teams' colours AND abbreviations, for the table header (R-848, R-856).

    ⚠️ A SEPARATE READ BECAUSE `srv_game_team` HAS NO COLOUR COLUMN — measured, not assumed.
    `srv_game` publishes `away_color_on_light` / `home_color_on_dark` and friends, which is the
    pair `row_for_side` already renames for `identity.text_on`. **No new colour path, and no
    contrast maths anywhere in this file.**

    🚨 R-856. THE ABBREVIATION RIDES ON THE READ THAT WAS ALREADY HAPPENING. B109's new header
    truncated *North Alabama* to **North Ala…** — it counted 0 of 40 truncations in the CARD
    names and was right, but the table header is an element it had just built and did not
    count. **`srv_game.away_abbreviation` / `home_abbreviation` exist**, so this is two columns
    on an existing bounded `limit 1` rather than a second query, and G-2 is untouched.

    ✅ AND IT IS THIS FILE'S OWN ESTABLISHED PATTERN RATHER THAN A NEW ONE — CHECKED, NOT
    ASSUMED. `_GAME_COLUMNS` has selected both columns all along and **nine call sites already
    read them**, every one with the same fallback — the abbreviation, then the full team name.
    This header was the odd one out. ⚠️ R-855 says a precedent is
    evidence of what was done rather than of what is correct, so it was TESTED in the case it
    is used for here — rendered at 1300px and 1700px, `UNA` and `ARK`, neither truncated.

    📊 AND THE ANSWER IS THE SAME ONE A130 NEEDS, WHICH IS WHY IT IS WORTH STATING FLAT: the
    column EXISTS, so the browser tab and this header read the same object rather than
    inventing two page-level abbreviations. **A130 landed while this round was in flight and
    reached the same conclusion independently** — `site/lib/tab.py`'s `teams_suffix` reads
    `srv_game.{home,away}_abbreviation` with this file's fallback chain, and says so.

    ⚠️ Coverage is not total and the gap is ancient
    rather than current — across all 112,675 games, 12,018 away and 5,560 home are null; **on
    the 3,674 games that actually have a box score, 39 away and 2 home.** Max length is 9
    characters, so it cannot itself truncate. **A null falls back to the full name**, which is
    exactly the behaviour before this change, on ~1% of the games this header draws.
    """
    df = query("""
        select away_color_on_light, away_color_on_dark,
               home_color_on_light, home_color_on_dark,
               away_abbreviation, home_abbreviation
        from srv_game
        where game_id = :game_id
        limit 1
    """, {"game_id": game_id})
    if df.empty:
        return {}
    row = df.iloc[0]
    # ⚠️ A TUPLE RATHER THAN A DICT, AND `ci/check_page_reads.py` IS THE REASON — it scans
    # `row.get("name")` reads and asks which SELECT provides that column. A dict of the page's
    # own making reads identically to a serving row at the call site, so `entry.get("abbr")`
    # tripped it as a column no query selects. **The checker is right that the two are
    # indistinguishable; the fix is to stop them looking alike.** Unpacking says at the call
    # site that this is a page-built pair, not a row.
    return {side: (row_for_side(row, side),
                   _card_text(row.get(f"{side}_abbreviation")))
            for side in ("away", "home")}


def _post_game_leaders(game_id: int) -> dict:
    """Who led IN this game, keyed by (team_id, panel) — A120's `..._in_this_game` view.

    ⚠️ ONE READ FOR FOUR CARD COLUMNS. Both post-game panels are flanked by the same cast, so a
    read per panel would be two reads for one answer.

    The limit is the grain restated (AC-G.39): two teams x three panels x three ranks is
    eighteen, and ties can push a rank past one row.
    """
    df = query(f"""
        select {_POST_GAME_LEADER_COLUMNS}
        from srv_game_team_leader_in_this_game
        where game_id = :game_id
        limit 60
    """, {"game_id": game_id})
    out = {}
    for _, r in df.iterrows():
        out.setdefault((int(r["team_id"]), str(r["panel"])), []).append(r)
    # Rank order is the column's own answer, not a ranking done here — B091's point about
    # `leader_rank`, and the query carries no `order by`.
    for rows in out.values():
        rows.sort(key=lambda r: int(r["leader_rank"]))
    return out


def _reserved_card(what: str, slots: int = 1) -> str:
    """A slot held open for a player who does not exist, SAYING SO (R-849).

    🚨 THIS IS THE WHOLE DIFFERENCE BETWEEN A RESERVED SLOT AND A HOLE. AC-G.11 forbids an
    empty box that a reader cannot distinguish from missing data; it does not forbid a box that
    NAMES its own emptiness. The card keeps the row register between the two columns AND tells
    the reader why it is blank — the same border and the same footprint as a real card, so
    nothing shifts, and a sentence inside it so nothing is mysterious.

    🚨 R-856. `slots` LETS ONE BLOCK STAND IN FOR SEVERAL, AND IT EXISTS BECAUSE THE ORDINAL
    WAS LYING. A side with no quarterback at all drew *No first quarterback recorded* over *No
    second quarterback recorded*, and **a reader does not think of quarterbacks as numbered
    slots** — the ordinal is an artefact of the card grid, not a fact about the game, so the
    first of those reads as a rendering error. One block saying the thing that is true of the
    SIDE answers the question actually being asked.

    ⚠️ THE FOOTPRINT IS ARITHMETIC, NOT A GUESS, BECAUSE B109 PROVED THE COST OF GETTING IT
    WRONG. `n` stacked cards occupy `n` heights plus the `n-1` margins BETWEEN them (the last
    margin is outside the run either way), so a block replacing them is
    `n * _RESERVED_CARD_HEIGHT + (n - 1) * 0.3rem`. **Alignment survives to the pixel and the
    group headers below stay in register** — which is the whole reason R-849 exists.
    """
    height = slots * _RESERVED_CARD_HEIGHT + (slots - 1) * 0.3
    return (f"<div style='border:1px dashed rgba(128,128,128,.28);border-radius:6px;"
            f"padding:.28rem .45rem;margin-bottom:.3rem;box-sizing:border-box;"
            f"height:{height:g}rem;display:flex;align-items:center'>"
            f"<span style='font-size:.72rem;opacity:.5;line-height:1.25'>{what}</span></div>")


def _card_group_header(title: str) -> str:
    """The small heading over one group of cards — Marc's *"a header above each section"*."""
    return (f"<div style='font-size:.66rem;font-weight:700;letter-spacing:.05em;"
            f"text-transform:uppercase;opacity:.5;margin:.45rem 0 .2rem'>"
            f"{html.escape(title)}</div>")


def _post_game_card_column(leaders, team_id, section: str = "box") -> str:
    """One side's cards, GROUPED, with a header over each group (R-848).

    ⚠️ TWO ABSENCES, AND THEY ARE DIFFERENT SENTENCES (AC-G.11):

      · the QUARTERBACK group reserves its second slot and says so — R-849, because the two
        card columns now sit side by side and an unmatched slot pushes every row below it out
        of register. Measured: 51.5% of games have the sides carrying different QB counts.
      · RUSHING and RECEIVING are drawn SHORT, exactly as B107 shipped. They are the LAST
        groups in their column, so a short one misaligns nothing beneath it, and a reserved
        slot there would be a hole bought for no alignment at all.
    """
    # 🚨 A SIDE WE HOLD NOTHING FOR STILL SAYS SO, AND THE RESERVED SLOT MUST NOT SWALLOW THAT.
    # R-849 reserves the second quarterback so the two columns stay in register — but a side
    # with NO leaders in any group is not a side missing one player, it is a side we hold
    # nothing for. **Reserving two blank quarterbacks there would answer a different question
    # from the one the reader is asking**, and it is the exact AC-G.11 confusion the reserved
    # card exists to avoid. The sentence wins whenever every group is empty.
    if not any((leaders or {}).get((int(team_id), panel))
               for _title, panel, _wanted in _CARD_GROUPS[section]):
        return ("<div style='font-size:.72rem;opacity:.45;padding:.3rem 0'>"
                "No player leaders held for this side.</div>")
    blocks = []
    for title, panel, wanted in _CARD_GROUPS[section]:
        rows = (leaders or {}).get((int(team_id), panel), [])[:wanted]
        if not rows and title not in _RESERVED_GROUPS:
            continue
        # ⚠️ `usage=None` ON PURPOSE: R-694's dots count EARLIER games, which is a preview
        # question. `_card_dots` returns nothing for a card with no usage, so the post-game
        # card is the same card without them rather than a second implementation of one.
        drawn = "".join(_leader_card(r) for r in rows)
        if title in _RESERVED_GROUPS and len(rows) < wanted:
            # 🚨 R-856. TWO SENTENCES, AND WHICH ONE IS TRUE DEPENDS ON WHETHER ANY PLAYED.
            # A side with ONE quarterback is missing its second and the ordinal is a fact
            # about the pair. A side with NONE is not missing a second anything, and naming
            # a *first* quarterback that never existed invents the slot it is apologising for.
            #
            # 🚨 AND THE VERB IS `recorded` RATHER THAN `played`, WHICH IS A MEASUREMENT AND
            # NOT A PREFERENCE. *Played* asserts about the GAME; the box score's silence only
            # means nothing was WRITTEN DOWN. Measured on the cards' own relation: of the
            # **573** sides with no `total` row, **571 — 99.7% — have receivers in the same
            # game**, so the ball was thrown and caught and a quarterback was unmistakably on
            # the field. *No quarterback played* would be false on essentially every side this
            # sentence is drawn for. **The render game is one of them: North Alabama at
            # Arkansas, no quarterback row, three receivers.**
            if rows:
                drawn += "".join(
                    _reserved_card(f"No {_ORDINALS[index]} {title.lower()} recorded")
                    for index in range(len(rows), wanted))
            else:
                drawn += _reserved_card(
                    f"No {title.lower()} recorded for this side.", slots=wanted)
        blocks.append(_card_group_header(title) + drawn)
    return "".join(blocks)


# The word a reserved slot uses for the place it is holding. ⚠️ Only as deep as the deepest
# reserved group, so a list that runs out is a group that reserves more than it says it does.
_ORDINALS = ("first", "second", "third")


def _post_game(game_id, season) -> None:
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
    with states.section("srv_game_team", dataset=DATASETS["srv_game_team"]):
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
            #
            # ⚠️ AND WHICH ABSENCE IT IS DEPENDS ON THE SEASON, NOT ON THE FRAME. The
            # pre-2024 sentence is unchanged — it was already right for that case.
            states.empty(
                "The box score would be here.",
                _absence_note(
                    season,
                    not_yet="Box scores are collected after the game finishes, and this "
                            "game's has not arrived yet.",
                    out_of_scope="cfdb holds box scores from 2024 onward, and this game's "
                                 "is not among them."))
            return

        away = next((r for r in played if not bool(r.get("is_home"))), played[0])
        home = next((r for r in played if bool(r.get("is_home"))), played[-1])
        # R-738. ONE read, four card columns — both panels are flanked by the same cast.
        leaders = _post_game_leaders(game_id)

        # 🚨 R-808. ONE READ FOR EIGHTEEN BANDS, BEFORE EITHER PANEL DRAWS.
        # ⚠️ THE WEEK COMES OFF THE ROW THIS PANEL ALREADY HAS, which is why `_POSTGAME_COLUMNS`
        # gained `season`, `season_type` and `week` rather than this taking a second query: the
        # distribution is keyed by the week, and the game knows its own.
        spread = _metric_distribution(away.get("season"), away.get("season_type"),
                                      away.get("week"))
        # 🚨 R-847. THE COLOURS ARE READ HERE AND NOWHERE ELSE. `srv_game_team` carries NO
        # colour column — measured — so the header's accent comes from `srv_game`, whose
        # `away_color_on_light` / `home_color_on_dark` pairs are exactly the shape
        # `row_for_side` was already written for. ⚠️ ONE bounded read, cached by `query`.
        colors = _post_game_identity(game_id)
        slots = _post_game_columns()
        _post_game_flank(slots["away"], slots["home"], leaders, away, home, "box")
        slots["table"].markdown(
            _table_header(away, home, "Box score", colors)
            # 🚨 `dp=0` FOR BOX SCORE, AND IT IS THE PANEL'S OWN NATURE RATHER THAN A PREFERENCE:
            # all six measures are integer counts — first downs, yards, attempts. At `box()`'s
            # default of 1 every label reads `22.0`, `5.0`, `38.0`, which is precision the
            # measure does not have. Measured: `dp` changes no label COUNT at this width, so
            # this costs nothing — see `_metric_band` and R-829.
            + _comparison(away, home, _BOX_SCORE_ROWS, spread=spread, dp_band=0)
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
        slots["table"].markdown(
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
        # 🚨 R-848. THE CAST IS NO LONGER THE SAME IN BOTH SECTIONS. R-738 kept it identical so
        # a reader scrolling between the panels would not find it changed; Marc's v08 puts
        # RECEIVING in Advanced only, and his reason is FIT rather than meaning — eight cards
        # beside one panel is a different shape from five beside each of two.
        adv = _post_game_columns()
        _post_game_flank(adv["away"], adv["home"], leaders, away, home, "advanced")
        adv["table"].markdown(
            # 🚨 `dp=2` FOR ADVANCED (R-829). ⚠️ THE `_METRIC_VALUE_NARROW` THIS COMMENT USED
            # TO NAME IS GONE WITH THE CENTRED CELL — R-810 sized the two panels' value slots
            # separately because a centred cell could differ per panel without the centre
            # moving; v08's *one big table* needs the two sections' columns to line up with
            # each other, so one width serves both.
            # ⚠️ ELEVEN OF THESE TWELVE ARE RATES BETWEEN 0 AND 1. At `box()`'s default of 1 the
            # quartiles COLLAPSE — a real week-1 passing-downs row goes p25 0.240 → `0.2` and
            # p75 0.433 → `0.4`, so a box spanning a fifth of the scale is labelled as if it
            # spanned two tenths, and this team's 0.348 prints `0.3`, the same as the median it
            # is not.
            # ⚠️ AND THE COST OF THE ONE-SENTENCE RULE IS NAMED: `Offensive plays` is a count and
            # reads `71.00`. The alternative — each row's own `dp`, which this file already
            # carries for the VALUE — was not taken because six of these rates print a serving
            # display string (`47.1%`) whose `dp` has nothing to do with the share the
            # distribution is published in. **Per panel is a rule; per row would be a rule with
            # six exceptions.**
            _table_header(away, home, "Advanced", colors)
            + _comparison(away, home, rows, glossary, spread=spread, dp_band=2),
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
        # 🚨 R-839. THIS SENTENCE OUTLIVED THE SECTION IT WAS WRITTEN FOR, AND THE MEASUREMENT
        # IS WHY. B110 deleted `st.subheader("Game leaders")`, whose caption read *"Player box
        # scores refresh Thursday and Sunday, so on a game night this block can sit behind the
        # box score above it."* **The fact is still true of what is left on this tab and
        # nothing else here says it**, so it belongs to the TAB rather than to the section —
        # deleting it with its block would have lost it.
        #
        # 📊 MEASURED ON LIVE SERVING RATHER THAN REASONED FROM THE DAG, 2026-09-14:
        #     srv_game_team                      as_of  12:00 UTC today
        #     srv_game_team_leader_in_this_game  as_of  17:58 UTC YESTERDAY
        # **The cards are eighteen hours behind the table they sit beside, right now.** The
        # box score is on the two-hourly bucket and the player box scores are `IMMUTABLE_WK`,
        # Thursday and Sunday.
        #
        # ⚠️ AND THE STAMP BELOW IS THE BOX SCORE'S, NOT THE CARDS'. `as_of_caption(df)` reads
        # the `srv_game_team` frame, so it prints the newer of the two times for a panel that
        # contains both. That is a REPORTED finding rather than one fixed in passing (R-500):
        # a second timestamp is a look decision, and the deleted section used to carry the
        # honest one for free. **The sentence is what keeps the reader from being misled by it.**
        st.caption(
            "The player cards refresh Thursday and Sunday, so on a game night they can sit "
            "behind the box score beside them. **\"tied 2\" on a card means that figure is "
            "shared** — the players are level, not first and second.")
        table.as_of_caption(df)


def _travel(game_id) -> None:
    """How far each side came and how long they had to rest.

    TWO MEASURES WITH DIFFERENT COVERAGE, shown separately rather than blended. Rest comes
    from the schedule and exists for every game that is not a season opener; travel needs
    coordinates for BOTH the game venue and the team's home venue. A null distance renders as
    an em dash, never as zero — zero means they played at home.

    🚨 THE ABSENT CASE IS THE COMMON ONE AND THAT IS MEASURED, NOT ASSUMED (R-634). Of 3,180
    upcoming 2026 sides, 659 (20.7%) carry `travel_miles` and 482 (15.2%) carry
    `elevation_change_ft`. Per GAME it is starker: of 1,590 upcoming games, 287 (18.1%) have
    both sides' distance, 85 (5.3%) have one, and 1,218 (76.6%) have neither. ⚠️ So the empty
    state is furniture rather than an edge case — the same thing B083 established for the
    market card, where the absent favorite was 2,234 of 3,831.

    ⚠️ MILES AND FEET SINCE R-634. Marc, 2026-09-11: "all distance measurements in miles,
    elevation measurements in feet." The conversion is NOT done here — a multiplication in the
    page is metric maths and §4.2 puts it in dbt. A097 shipped `travel_miles`,
    `elevation_change_ft`, `game_elevation_ft` and `home_elevation_ft`, each rounded from the
    SAME unrounded measurement as its metric twin rather than converted from the rounded one,
    so the two cannot disagree. Verified against Arizona State → Wembley Stadium: 8,463.6 km =
    5,259.0 miles, and `elevation_change_ft` is -1,027 where converting the rounded -313.2 m
    would have given -1,028.

    ⚠️ ONLY THE TWO COLUMNS THIS PANEL RENDERS ARE SWAPPED. `game_elevation_*` and
    `home_elevation_*` are not read here and adding them would grow a panel Marc asked to
    shrink (R-600).
    """
    st.subheader("Travel and rest")
    with states.section("srv_game_travel", dataset=DATASETS["srv_game_travel"]):
        df = query("""
            select team, opponent, is_home, is_neutral_site, game_venue, travel_miles,
                   elevation_change_ft, rest_days, rest_bucket, previous_game_date, as_of_ts
            from srv_game_travel
            where game_id = :game_id
            order by is_home desc
            limit 2
        """, {"game_id": game_id})
        if df.empty:
            states.empty("How far each side traveled would be here.",
                         "No travel or rest figures for this game.")
            return

        for _, r in df.iterrows():
            # R-600. ONE LINE PER SIDE, NOT A HEADING AND THREE TILES. Marc: "Too big, not
            # that important." Six st.metric tiles and two headings became two lines; every
            # figure and every caveat survives, and the panel costs about a fifth of the
            # height it did.
            #
            # ⚠️ COMPRESSED, NOT DELETED — he said too big, not unwanted. And the conditional
            # highlight R-524 asks for still waits on a measured threshold: shrinking needed
            # no distribution, so it happened now; choosing what counts as "significant" by
            # taste is the thing R-524 exists to prevent.
            side = "Home" if r.get("is_home") else "Away"
            if r.get("is_neutral_site"):
                side = "Neutral site"
            miles = r.get("travel_miles")
            # ⚠️ AC-G.32. Zero is a real answer here and reads as one; null is not, and the
            # two must never render the same. A home side carries 0.0 — measured, not assumed:
            # 367 of the upcoming sides are a literal zero rather than a null. "home venue"
            # says what that zero MEANS, which is why it is preferred to "0.0 mi"; what
            # matters for the rule is that it is emphatically not the em dash.
            travel = ("—" if miles is None or pd.isna(miles)
                      else "home venue" if float(miles) < 1 else f"{float(miles):,.1f} mi")
            rest = r.get("rest_days")
            rest_text = "—" if rest is None or pd.isna(rest) else f"{int(rest)}d rest"
            bucket = str(r.get("rest_bucket") or "")
            if bucket:
                # The Rest label's hover survives the shrink — it is the one piece of prose
                # here that says what a number MEANS rather than repeating it.
                rest_text = (f"<span title='{html.escape(bucket, quote=True)}' "
                             f"style='cursor:help;border-bottom:1px dotted'>{rest_text}</span>")
            change = r.get("elevation_change_ft")
            # 🚨 SIGNED ON PURPOSE, AND THE SIGN IS THE FACT. Arriving 1,500 ft higher and
            # 1,500 ft lower are different experiences and a magnitude would erase which
            # happened — Arizona State drop 1,027 ft going to Wembley, a side going to Laramie
            # climbs. The leading + or − is what says which, so this must never be abs()ed.
            elevation = ("—" if change is None or pd.isna(change)
                         else f"{float(change):+,.0f} ft")
            st.markdown(
                f"<div style='padding:.1rem 0'><strong>{html.escape(str(r.get('team')))}"
                f"</strong> <span style='opacity:.6'>{side}</span> · {travel} · "
                f"{rest_text} · {elevation}</div>", unsafe_allow_html=True)
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


def _drives(game_id, season) -> None:
    """The alternating possession sequence — how the game actually went.

    THE SINGLE MOST LEGIBLE "how did this game go" ARTEFACT (matchup post-game spec §1.4),
    and it was the blocker there: stg_drive had landed and nothing read it. fct_drive and
    srv_drive now exist and are published, so this is the thing that reads them.

    ⚠️ SCORING IS READ FROM `scoring_side`, NEVER FROM THE RESULT TEXT. A `TD` suffix on a
    turnover or a kick means the DEFENSE scored — 908 drives across ten drive_result values,
    measured. Keying an offensive-touchdown mark off the substring "TD" puts every one of
    them on the wrong side of the game.
    """
    st.subheader("Drives")
    with states.section("srv_drive", dataset=DATASETS["srv_drive"]):
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
            #
            # 🚨 THE SECOND CLAUSE USED TO READ "and a game that has not kicked off yet has
            # none", WHICH IS FALSE HERE IN EVERY CASE: this panel is only reachable from the
            # after tab, which an unplayed game does not have. A112 rendered it on a game
            # that had finished six hours earlier.
            states.empty(
                "The drive-by-drive sequence would be here.",
                _absence_note(
                    season,
                    not_yet="Drives are collected after the game finishes, and this game's "
                            "have not arrived yet.",
                    out_of_scope="Drives are collected from 2024 onward, and this game's are "
                                 "not among them."))
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
                "Color for " + ", ".join(fell_back) + " is cfdb's rather than the team's, "
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
            mark = ("<span style='font-weight:600'>▲ offense</span>" if side == "offense"
                    else "<span style='font-weight:600'>▼ defense</span>" if side == "defense"
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
