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

import pandas as pd
import streamlit as st

from lib import (attribution, chips, distribution, filters, fmt, glyphs, identity, params,
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
    game_id, season, season_type, week, start_date, game_date, venue_display, attendance,
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
    """Matchup's rendering of `glyphs.winner` — the WRAPPER is all that is left here.

    🚨 cfdb-wta-R-951. THE MARK MOVED TO `site/lib/glyphs.py` AND THIS DID NOT, WHICH IS THE
    WHOLE SHAPE OF THE MOVE. Marc asked for *"the same Matchup and outcome glyphs as on the
    Schedule page"* on Today, and *the same* means the same PRODUCER — but **the markup below is
    not about who won.** It is a block-level, centred, 1.4rem div, which is the geometry of the
    gap between two scores on this page's scoreboard and is meaningless in Today's Commentary
    cell. **A shared producer that hard-coded it would be forked the first time a second page
    needed a different footprint.**

    ⚠️ AND THE RULE TRAVELLED WITH THE MARK RATHER THAN STAYING HERE: `glyphs.winner` returns
    `None` before kickoff, on a tie, and for the side that did not win — **absent, not empty** —
    and says in its own docstring that a caller who does not know that will render a hole for a
    game nobody has played. `glyphs.render(None)` is the empty string, so forwarding `None` is
    already correct; this function keeps its own `if not mark` because the div must not be
    emitted either.
    """
    mark = glyphs.winner(row, side)
    if mark is None:
        return ""
    return (f"<div style='text-align:center;font-size:1.4rem;line-height:1.1;"
            f"opacity:.75'>{mark.glyph}</div>")


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
    # 🚨 cfdb-wta-R-900. MARC'S v14 ORDER IS TOTAL FIRST, AND THIS TUPLE IS THE ONLY PLACE IT IS
    # WRITTEN: *"The Offense vs Defense section should be a single table, organized in Rows:
    # Total, Rushing, Passing."* ⚠️ **It was Rushing · Passing · Total and the comment below said
    # why** — Total *"renders last and subordinate, because 99.7% of the time it is the sum of
    # the two lines over it"*. That reasoning is still TRUE and is no longer the instruction;
    # Marc has put the summary line first, which is a reading order, not a claim about the
    # arithmetic. ✅ The measurement it rests on is kept because it is still the reason Total is
    # not computed here.
    #
    # ⚠️ AND THE ORDER IS LOAD-BEARING TWICE: the sections render in this order AND
    # `_LEADER_PANELS` maps each label to the card panel beside it, so *"Total has QB Cards"* is
    # this tuple's first row meeting `"Total": "total"` — the panel the post-game tab calls
    # **Quarterback**. **Nothing had to be built for that half of the instruction; it had to be
    # checked, and it was.**
    #
    # TOTAL EARNS ITS ROW ON A MEASUREMENT, NOT ON SYMMETRY. It is rushing + passing in
    # 13,686 of the 13,728 rows that carry any form, and differs in 42 by up to 11 yards —
    # so it is the source's own total rather than our arithmetic, and adding the two below
    # in this file would be metric maths in the app.
    ("Total", "total_yards_for_per_game", "total_yards_allowed_per_game",
     "total_yards_for_minus_opponent_allowed_per_game", "total_matchup_outlook"),
    ("Rushing", "rushing_yards_for_per_game", "rushing_yards_allowed_per_game",
     "rushing_yards_for_minus_opponent_allowed_per_game", "rushing_matchup_outlook"),
    ("Passing", "passing_yards_for_per_game", "passing_yards_allowed_per_game",
     "passing_yards_for_minus_opponent_allowed_per_game", "passing_matchup_outlook"),
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
    # 🚨 cfdb-main-R-1070, AND THE DOCSTRING ABOVE ARGUES FOR A NUMBER RATHER THAN FOR A DECIMAL
    # — which is why this is a format change and not a rewrite. `+0` is still a number and still
    # not an em dash, so AC-G.32 and the `+0` reasoning both survive intact.
    #
    # ⚠️ **`-0` IS NOW REACHABLE AND IT IS HONEST RATHER THAN A DEFECT.** A delta of −0.4 yards
    # per game rounds to `-0`, which says *fractionally behind* — the sign is the fact and the
    # magnitude genuinely is under half a yard. 📊 Measured on live serving: it occurs on
    # **14 of 8,892 published sides (0.16%)**, against 15 that round to `+0`.
    # **The alternative — keeping a decimal for one of the three numbers Marc named in the
    # legend — is the thing he asked against.**
    return f"{float(value):+,.0f}"


def _yardage_side_heading(offense, defense, season=None) -> str:
    """Whose half this is: the team, and whose defense its figures are measured against.

    🚨 THIS IS WHAT SURVIVED R-756. The three metric rows under it are gone; without this line a
    reader cannot tell the two halves apart except by reading the logos inside a 180px chart.

    ## cfdb-wta-R-1071 — THE NAME IS A LINK, AND THE DESTINATION IS A DECISION

    > **MARC, v18:** *"Team Name is hyperlink to Teams page filtered to the Team"*

    🚨 **THERE ARE TWO PAGES AND ONLY ONE OF THEM CAN BE REACHED BY URL.** Read rather than
    assumed:

        teams.py    "Teams — page 7. The index: find a team, see its shape, click through."
                    a LIST. Its team filter is `st.text_input("Search teams")` — WIDGET STATE,
                    not a query parameter. **There is no `/teams?team=…` to link to.**
        team.py     "Team page — page 8. One team, tabs, everything cfdb knows this season."
                    takes `?team=<slug>&season=<n>`, which is what `table.team_link` builds.

    ✅ **SO THE LINK GOES TO `/team`, AND IT IS THE DESTINATION HIS SENTENCE DESCRIBES EVEN
    THOUGH IT IS NOT THE PAGE HE NAMED** — *Teams filtered to one team* and *the Team page* show
    the same thing, and only the second exists. ⚠️ **The literal reading would need a query
    parameter on `teams.py`, which is session A's file (§3 rule 3.1) — reported, not reached
    for.** If Marc meant the index with a row highlighted, that is a different round.

    ✅ **AND IT REUSES `table.team_link`, THE ONE BUILDER** — `today.py` and `scores.py` already
    do (§4.3: a second builder for one destination is the drift). ⚠️ **The SEASON is passed in
    rather than read off the row**: `_YARDAGE_COLUMNS` selects `team_slug` and NOT `season`, so
    `team_link`'s default `season_field` would find nothing and send a reader to the CURRENT
    season from a 2024 game. The game's own row has it; this takes it as an argument.

    ⚠️ **NESTED ANCHORS — CHECKED, NOT ASSUMED.** `today.py:_team_identity` records the rule
    (*"a table whose team name is a link passes NO `link_builder`"*), and it does not apply here:
    this string is written by `head_left.markdown(...)` straight into a Streamlit column, with no
    outer anchor anywhere above it. **Verified in Chromium, not by reading** — see the round's
    render.

    ⚠️ **`.cfdb-team` CARRIES `margin-left:.4rem` FOR THE TABLE CELLS IT WAS WRITTEN FOR**, and
    this row already spaces itself with `gap:.45rem`. The inline override is that one difference
    and nothing else; the colour and the hover underline stay the stylesheet's.
    """
    accent = identity.text_on(offense)
    logo = identity.logo_or_monogram(
        offense.get("logo_url"), str(offense.get("team_display") or "?"), 20)
    name = offense.get("team_display") or "?"
    # ⚠️ A DICT RATHER THAN THE SERIES, BECAUSE THE SEASON IS NOT ON THE SERIES. `team_link`
    # reads its two fields with `.get`, so this is the row it needs rather than a second builder.
    # ✅ AND IT RETURNS `None` FOR A MISSING SLUG — *"a link to nowhere is worse than a cell that
    # was never clickable"* — so the unlinked heading is the fallback, not a broken href.
    href = table.team_link("team_slug")({"team_slug": offense.get("team_slug"),
                                         "season": season})
    # 🚨 `flex:none` IS NOT TIDYING — WITHOUT IT A LONG NAME OVERPRINTS THE SENTENCE BESIDE IT,
    # AND ONLY THE RASTER SAW IT. `.cfdb-teamlink` carries `display:flex; min-width:0` (theme.py,
    # written for the table cells it was built for), so as a flex ITEM in this row the anchor can
    # shrink BELOW its own text — which then spills out of it and draws straight over
    # *"offense against …'s defense"*. **The plain `<span>` this replaced could not shrink**
    # (`min-width:auto`), so the row simply overflowed and R-755's `overflow:hidden` clipped it
    # at the block edge, which is the designed behaviour.
    # 📊 **AND MY OWN MEASUREMENT SAID IT WAS FINE**: the anchor's right edge stayed inside the
    # heading box — because the anchor had shrunk. That is B108's lesson exactly (*a width
    # reading reports the SLOT rather than the GLYPHS*) and §2.4's: the command answered a
    # different question from the one asked. **The 412px two-long-names render is what found it.**
    label = f"<span class='cfdb-team' style='font-weight:600;margin-left:0'>{name}</span>"
    style = "flex:none"
    if href:
        label = (f"<a class='cfdb-teamlink' href='{href}' target='_self' "
                 f"style='{style}'>{label}</a>")
    # ⚠️ `overflow:hidden` STAYS — R-755. One line of two team names is narrower than the rows
    # that used to sit under it, but a long pair still exceeds a 412px half, and the failure mode
    # without this is drawing over the column beside it rather than clipping inside this one.
    return (
        f"<div style='border-left:4px solid {accent};padding:.4rem .7rem;"
        f"margin-bottom:.5rem;overflow:hidden'>"
        f"<div style='display:flex;align-items:center;gap:.45rem;white-space:nowrap'>"
        f"{logo}{label}"
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
# 🚨 cfdb-wta-R-900. `whisker_low` AND `whisker_high` JOINED THIS LIST AND THE PANEL DID NOT
# WORK WITHOUT THEM — which is worth stating, because the failure is SILENT.
#
# `distribution.box()` frames on the whisker pair and reads it through
# `distribution._whisker_pair`, which looks the two keys up IN THE ROW. A row that carries
# neither returns `(None, None)`, and `box()` then returns its em-dash placeholder span rather
# than raising. ⚠️ **So every chart in this panel would have drawn a single `–` and every
# assertion of the form "the chart element is present" would have passed** — R-852's class, and
# the reason this round staged a break on it rather than trusting the render to look wrong.
#
# 🚨 cfdb-wta-R-964 / B119. THE RELATION MOVED AND THE COLUMN LIST MOVED WITH IT.
#
# ❌ `axis_min` / `axis_max` / `axis_step` ARE GONE, AND SO IS THE SENTENCE THAT KEPT THEM. It
# read *"`_week_frame_captions` still reports the week's own span from them"* — **and
# `_week_frame_captions` has not existed in this file for several rounds.** A comment naming a
# dead function is the next reader's false lead, which is the class B117 gave a test. The axis
# columns were the HISTOGRAM frame that `thumbnail` and `panel` need; a box plot is percentiles
# and whiskers, this panel draws only `box()`, and the new relation does not publish them.
#
# ❌ `teams_in_week`, `min_games_counted` AND `max_games_counted` GO TOO — they are properties of
# a population of TEAM SEASON-AVERAGES, and this is a population of GAMES. `weeks_counted`
# replaces them and answers the question that now matters: how many weeks of games are in it.
#
# 🚨 cfdb-wta-R-968. `min_value`, `max_value` AND `outlier_count` JOINED THIS LIST IN B118, AND
# THE FAILURE THEY CLOSE IS THE SILENT ONE THIS BLOCK ALREADY WARNS ABOUT ONE PARAGRAPH UP.
#
# A142 taught `distribution.describe()` to report the tail — *"2 beyond the whiskers (128.0 to
# 856.0)"* — and taught `box(outliers=True)` to draw it. **Both read the row, and this page
# selects its columns BY NAME**, so until they were named here the chart's own tooltip could not
# say how far the week reached. ⚠️ A row missing them degrades rather than raising (A142 pinned
# that property), which is exactly why nobody would have noticed.
#
# 📊 AND THE TAIL IS NOT RARE, WHICH IS WHAT MAKES IT WORTH THE THREE COLUMNS. Measured on live
# published serving this round: **207 of 282 rows on this relation — 73.4% — carry at least one
# outlier**, and the page showed none of it. 2026 regular week 3 `total_yards_for_per_game`:
# whiskers 204.0–620.5, `max_value` **702.5**, one team beyond. A reader could not tell that
# week from one with nothing unusual in it.
#
# ❌ `outliers=True` IS **NOT** PASSED AT THIS CALL SITE AND THAT IS A MEASURED REFUSAL RATHER
# THAN AN OVERSIGHT — see `_metric_chart` for the number that decided it. The COUNT is free; the
# RINGS cost frame width, and that is a look decision Marc has not been shown yet.
_DISTRIBUTION_COLUMNS = """
    season, season_type, week, metric, n, weeks_counted, mean, stddev,
    p25, p50, p75, whisker_low, whisker_high,
    min_value, max_value, outlier_count, as_of_ts
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
# centre a single 762 cannot drag.
#
# ✅ THE LAST SENTENCE USED TO READ *"the same reasoning is why the site's existing distribution
# work draws a box-and-whisker rather than error bars"* — AND v14 MAKES THIS PANEL THAT WORK.
# The argument is unchanged and it now governs the chart directly: `box()` draws p25/p50/p75 and
# the published whiskers, and reads `stddev` no more than this panel ever did.
# ⚠️ `_BAND_LOW` / `_BAND_MID` / `_BAND_HIGH` WERE HERE AND WENT WITH THE SCATTER. They named the
# percentile COLUMNS for a band this file drew itself; `box()` reads the row, so the page no
# longer names them. **Deleted rather than left as three unused strings — a constant nothing
# reads is the next reader's false lead.**

# A thin sample is a property of the week and the page says so rather than letting a reader
# assume season form. Two games or fewer is where "per game" and "that game" are the same
# number or nearly so.
_THIN_SAMPLE = 2


def _week_distribution(row):
    """The week's shared frame: every team-game played BEFORE this week, one row per metric.

    🚨 THE RELATION CHANGED IN B119 AND THE REASON IS THE CIRCLES (cfdb-wta-R-964).

    This panel read `srv_team_week_metric_distribution` — a distribution of TEAM SEASON-AVERAGES,
    one value per team. Marc asked for *"an unfilled circle mark indicating the measure for each
    game the team played"*, and **a single game is not a member of that population.**

    📊 B118 MEASURED WHAT DRAWING THEM THERE WOULD HAVE COST, on the same 668 real team-games:
    **15.42% of them fall beyond a whisker of the averages box against 0.30% of the game-grain
    one — a fifty-one-fold overstatement.** Averaging shrinks variance, so the averages box's
    middle half is 42.0% narrower and every circle reads as more extreme than it was. A reader
    would have been told one afternoon in seven was extraordinary when the truth is one in 333.

    ⚠️ AND THE OBVIOUS FIX WAS NOT AVAILABLE UNTIL A143. `srv_game_team_metric_distribution` is
    the right GRAIN and the wrong WEEK: its week-W row is week W's OWN games, so B118 measured
    **zero rows for all 2,921 unplayed 2026 games** and stopped rather than guess. A143 built
    this view — every team-game in weeks strictly BEFORE this one — which is the same
    point-in-time rule `srv_team_week` already applied at the other grain (R-463).

    ✅ SO ALL THREE THINGS ON THE SCALE ARE NOW ONE POPULATION: the box is every prior team-game,
    the circles are this team's prior games, and the value marker is their mean.

    🚨 KEYED ON (season, season_type, week), NOT ON `week` ALONE. A092's own crude check
    returned 12 rows for `week = 1` and every one was POSTSEASON — bowl games, eleven or
    twelve played, a real distribution. Keying on the week number alone would draw bowl
    numbers on a September page and look entirely plausible doing it.

    ⚠️ AC-G.39, AND THE LIMIT ROSE FROM 6 TO 18 BECAUSE THE GRAIN DID. The old relation published
    six metrics — a `_for` and an `_allowed` for each of three. This one publishes the eighteen
    box-score and advanced measures A125 built, of which this panel reads three. **The limit is
    the grain restated, not a guess**, and it is a literal because `ci/check_page_queries.py`
    interpolates these strings to execute them.
    """
    df = query(f"""
        select {_DISTRIBUTION_COLUMNS}
        from srv_game_team_metric_distribution_through_prior_week
        where season = :season
          and season_type = :season_type
          and week = :week
        limit 18
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
# 🚨 R-722's THREE VERDICTS MOVED TO `site/lib/glyphs.py` — cfdb-wta-R-951.
#
# Marc's rule, the `favorable` spelling that CI enforces, the shape-before-colour argument and the
# unclassified hollow square all live there now, **once**, because Today draws the same three marks
# and *"the same"* means the same producer. ❌ **Do not restate any of it here**: a second copy of a
# rule is a copy that drifts, which is the defect this move exists to prevent.
#
# ⚠️ WHAT STAYS ON THIS PAGE IS THE PRESENTATION — the `.8rem` in `_outlook_glyph` below, which is
# the size of Matchup's own legend block and is not a fact about the matchup.


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


def _yardage_row(offense, defense, week_rows, dimension, deltas=None,
                 leaders=None, usage=None, games=None, opponent_games=None) -> None:
    """ONE metric for ONE side: the box-and-whisker pair, with that side's cards BESIDE it.

    🚨 cfdb-wta-R-900 TURNED `_yardage_column` INSIDE OUT, AND THE REASON IS THE SPANNING
    HEADER. Marc: *"Total, Rushing, and Passing should each have a single header row that spans
    the whole page."* The old shape was **two Streamlit columns, each looping the three
    metrics** — so a metric's heading could only ever be emitted INSIDE one half, which is
    exactly the limitation the previous round wrote down and declined to fix: *"a header
    spanning BOTH halves is his later option and is deliberately not built, because the two
    halves are separate Streamlit columns."*
    ✅ **So the loop moved OUT and the columns moved IN** — `_yardage` now loops the metrics at
    the top level, emits one `_section_heading` across the page, and opens a fresh `st.columns`
    pair underneath it. **This is B112's shape on the other tab, reused rather than reinvented.**

    ⚠️ THE MIRROR SURVIVES INTACT (R-731): cards on the OUTSIDE, charts together in the middle.
    `order` is still in left-to-right order and still zipped against `st.columns`, so emission
    order and visual position remain the same fact and the positional tests still mean what
    they say.
    """
    label, for_column, allowed_column, delta_column, outlook_column = dimension
    order = ("chart", "cards") if _is_home_side(deltas) else ("cards", "chart")
    widths = [_SLOT_WIDTHS[slot] for slot in order]
    # ✅ cfdb-wta-R-901 / R-855. ONE PRODUCER, CALLED TWICE HERE — the series rule beside each
    # box and the card borders beside it are the SAME string, so a reader cannot be shown two
    # different colours for one team on one row.
    accent, opponent_accent = _accent(offense), _accent(defense)
    # ⚠️ TWO CALENDARS, ONE READ. `_game_calendar` already fetches BOTH teams — its `where` is
    # `team_id in (:away_team_id, :home_team_id)` — and returns them keyed by `team_id`, so the
    # opponent's rows were fetched all along and simply were not passed down. **No new query and
    # no new column** (cfdb-wta-R-986); this is plumbing, not a read.
    chart = _gained_allowed(offense, defense, for_column, allowed_column, week_rows, label,
                            _delta_for(deltas, outlook_column),
                            _delta_for(deltas, delta_column),
                            accent=accent, opponent_accent=opponent_accent,
                            games=games, game_column=_GAME_YARDS[label],
                            opponent_games=opponent_games,
                            game_allowed_column=_GAME_YARDS_ALLOWED[label])
    panel_key = (int(offense["team_id"]), _LEADER_PANELS[label])
    cards = _leader_block((leaders or {}).get(panel_key, []),
                          (usage or {}).get(panel_key), accent=accent)
    for slot, column in zip(order, st.columns(widths)):
        column.markdown(chart if slot == "chart" else cards, unsafe_allow_html=True)


def _metrics_without_a_week(week_rows) -> list:
    """Which of the six series this week holds no distribution for.

    🚨 THIS IS WHAT SURVIVED THE CHART CHANGE, AND ONE OF THE TWO OLD ABSENCES IS GONE FOR GOOD.
    The scatter could not plot a point outside `axis_min`/`axis_max`, so `_off_the_frame_*`
    existed to name the metrics it dropped and print their figures. ✅ **`box()` frames on the
    whiskers WIDENED BY THE VALUE** — its own comment: *"a figure outside the whiskers is drawn
    where it is rather than clamped to the edge"* — **so the new chart cannot exclude a team,
    and the absence it explained can no longer occur.**

    ⚠️ THE OTHER ABSENCE IS REAL AND STAYS: a week with no distribution row for a metric.
    `box(None, …)` returns a titled em dash, which holds the row's height (R-141) and says
    nothing a sighted reader can read — so the page says it here, in words, naming WHICH
    metrics (AC-G.11).
    """
    # 🚨 B119: KEYED ON THE GAME METRIC, AND THERE IS ONE LOOKUP WHERE THERE WERE TWO.
    # `week_rows` is now `srv_game_team_metric_distribution_through_prior_week`, whose metric
    # vocabulary is `total_yards` rather than `total_yards_for_per_game` — and gained and allowed
    # read the SAME row (see `_week_union`). **Left keyed on the old pair this would have looked
    # up two names the relation does not publish, found `None` for both, and reported all three
    # metrics missing on every week** — a caption naming a real absence that is not there.
    return [label for label, _f, _a, _d, _o in _YARDAGE_DIMENSIONS
            if week_rows.get(_GAME_YARDS[label]) is None]


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

# 🚨 R-899. THE SECTION's PER-GAME COLUMN, WHICH IS NOT THE PER-GAME-AVERAGE ONE.
#
# ⚠️ THE TWO VOCABULARIES DIFFER BY A SUFFIX AND THAT IS THE TRAP A128, A132 AND B110 EACH PAID
# FOR. `total_yards_for_per_game` is the team's AVERAGE on `srv_team_week`, which is what the box
# row draws; `total_yards` is ONE GAME's figure on `srv_game_team`, which is what the strip
# draws. **Deriving one from the other with a string replace would work until a column is renamed
# and then fail silently**, so the mapping is written out.
_GAME_YARDS = {"Total": "total_yards", "Rushing": "rushing_yards", "Passing": "passing_yards"}

# 🚨 WRITTEN OUT FOR THE REASON THE PARAGRAPH ABOVE GIVES, AND THE TEMPTATION HERE IS STRONGER.
# `total_yards` -> `total_yards_allowed` is a suffix away, and `f"{_GAME_YARDS[label]}_allowed"`
# would work today and **fail silently the day a column is renamed** — the same argument that
# stopped `_GAME_YARDS` being derived from `_YARDAGE_DIMENSIONS`. Three lines is the whole cost.
_GAME_YARDS_ALLOWED = {"Total": "total_yards_allowed",
                       "Rushing": "rushing_yards_allowed",
                       "Passing": "passing_yards_allowed"}

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
        # is the same choice `_card_half` makes for a missing third rusher.
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


def _leader_card(row, usage=None, accent: str = None) -> str:
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
            f"opacity:{_CARD_KPI_LABEL_OPACITY};white-space:nowrap'>"
            f"{html.escape(str(label))}</div>"
            f"<div style='font-size:.92rem;font-weight:600'>{shown}</div></div>")
    # 🚨 R-886. THE BORDER IS THE TEAM'S COLOUR — Marc, v11: *"Player Card borders should be
    # color of team."* ✅ `_accent` is B111's ONE producer of the composed `light-dark(...)`
    # string and the table header's underline already uses it (R-855); this is the same call,
    # not a second one. ⚠️ A side with no sourced colour yields `identity.FALLBACK` and the
    # border still draws — **1.01% of the games this panel renders (37 of 3,674), not the
    # 10.89% all-games figure** (R-876).
    #
    # ⚠️ AND IT IS LOUDER THAN THE 22%-ALPHA GREY IT REPLACES. That is a look decision and it is
    # Marc's; it is rendered as asked rather than quietly toned down. **Position still carries
    # the away/home distinction (AC-G.22) — the colour is the second signal, and the greyscale
    # render is in the report to prove the columns are still tellable apart without it.**
    # ⚠️ `data-cfdb='leader-card'` IS AN INTERFACE AND THE BORDER IS NOT. The tests anchored on
    # the literal grey border string until R-886 put the TEAM COLOUR there, at which point every
    # card-finding helper silently matched nothing — `_row_markup`'s own comment already says it:
    # *"The attribute exists to be anchored on; a style string is not an interface."*
    return (f"<div data-cfdb='leader-card' "
            f"style='border:1px solid {accent or 'rgba(128,128,128,.22)'};"
            f"border-radius:6px;"
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


def _leader_block(rows, usage=None, accent: str = None) -> str:
    """The three names under one chart — or an honest absence.

    ⚠️ `accent` IS cfdb-wta-R-901 AND IT IS A PASS-THROUGH, NOT A NEW PRODUCER. `_leader_card`
    has taken the parameter since R-886 and applies it to the border; this block simply never
    handed it one, so the BEFORE-THE-GAME cards drew the neutral grey while the POST-GAME cards
    drew the team colour. **One producer, `_accent`, two call sites — the state R-855 asks for.**

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
    return "".join(_leader_card(r, usage, accent=accent) for r in rows)


# --- cfdb-wta-R-900 / R-898: the Gained vs Allowed chart is a BOX-AND-WHISKER ----------------

# 🚨 MARC, v14: *"Let's modify the Gained vs Allowed chart. Instead make it a horizontal box
# whisker. Two rows/sections of data on the chart. Gained on top, Allowed on Bottom, label each
# series accordingly with team name and gained or allowed, as appropriate. Add a line for the
# average for the team at this point. Color and label the Metric value."*
#
# ✅ THE RENDERER IS A125's `distribution.box` AND NOTHING HERE DRAWS AN SVG. That module's
# opening argument is *"two renderers drift, and the day they disagree the reader cannot tell
# which is lying"*, and a second box plot written in this file is exactly that. This function
# composes TWO of its rows and owns the labels, the legend and the layout — which is the
# division of labour §3 rule 3.1 sets for a shared module and its call sites.
#
# ⚠️ *"a line for the average for the team at this point"* IS THE `value` MARKER, NOT A SECOND
# RULE. Before kickoff the team has no game figure, so its `*_per_game` through the prior week
# IS the number Marc is asking to see against the week's spread — and `box(value=…,
# value_color=…, value_label=…)` is a call A131 already ships for it. **A second line drawn
# from `mean` would put the LEAGUE average beside a series whose median is already on the
# chart, and the median is the better centre here for the reason the percentile note
# above `_THIN_SAMPLE` gives.**
# 📊 240, AND IT IS MEASURED IN THE BROWSER RATHER THAN DERIVED — R-750's LESSON, PAID AGAIN.
# The first draft wrote 296 from an arithmetic estimate of the slot, and the live render at
# 1300px with the sidebar open measured the chart slot at **246px**. `box()` emits
# `max-width:100%`, so the SVG did not overflow — **it SCALED**, to 246, quietly taking its 9px
# labels down with it to about 7.5.
#
# 🚨 AND THE DOM WAS SILENT: `width='296'` was on the element, every label was present, and the
# only instrument that could see it was `getBoundingClientRect()` on the live page. ⚠️ This is
# B108's class — *a `scrollWidth` reports the slot rather than the glyphs* — and R-859's: the
# attribute answers *what was declared*, which is a different question from *what was drawn*.
#
# ✅ 240 FITS THE 246px SLOT AT ITS DECLARED SIZE, so nothing scales and the labels stay 9px.
# ⚠️ It follows `_SLOT_WIDTHS` rather than the viewport: cards take 1.0 and the chart 1.6 of each
# half, and the card measured 150px beside a 246px chart — 1:1.64, which is the ratio doing
# exactly what it says. **A wider viewport gives the slot more room and leaves slack at the
# outer edge; it does not make this number wrong**, which is the property the fixed 180px square
# had before it and the reason R-609 keeps `use_container_width` off.
# ⚠️ MOVED. cfdb-wta-R-899 gave the box and the strip a shared gutter, so this
# ⚠️ MOVED. cfdb-wta-R-899 gave the box and the strip a shared gutter and this constant was
# declared beside it; B119 removed the strip and the gutter with it, so `_BOX_ROW_WIDTH` is
# declared beside the circles that now share its axis.

# ✅ THE TWO ROWS SHARE ONE X-AXIS — cfdb-wta-R-927, CLOSED. A139 shipped the parameter this
# needed and B116 flipped it; the argument is kept because it is the reason, not the status.
#
# 📊 WHAT IT WAS. `box()` frames on the row's own whisker pair widened by its value markers, so
# two independent calls gave two independent scales. Measured on live serving, 2026 regular
# week 15: on `total` the gained row spanned **204.0–620.5 (416.5 yards)** and the allowed row
# **142.5–508.5 (366.0)** across the same pixels — **a 13.8% scale difference, and the layout
# invited the reader to compare them by eye.** Nothing on the screen admitted to it.
#
# ✅ WHAT IT IS NOW. Both calls are handed `frame=` the WEEK's union of the two whisker pairs, and
# A139's parameter only ever WIDENS — `frame_lo = min(frame_lo, given_lo)` — so `lo`/`hi` still
# draw each row's own serifs and label each row's own boundaries. **The scale is shared; the
# numbers under it stay each row's own.** A shared axis that relabelled the whiskers with the
# union's numbers would tell a reader this team's week ran from 142.5 when it ran from 204.0,
# which is the dishonest version and is one line away.
#
# 📊 THE COST, MEASURED ACROSS ALL THIRTEEN 2026 REGULAR WEEKS rather than the one week the
# prompt tabled — the narrower row simply ends early:
#
#     pair       gained span   allowed span   (as a share of the union)
#     passing      100.0%         86.9%
#     rushing       91.2%         71.9%
#     total         88.1%         77.4%
#
# 🚨 AND THE RESIDUAL, WHICH IS REAL AND IS NOT ZERO. `box()` widens by its OWN value AFTER the
# frame is applied, so a team whose per-game figure falls outside the week union re-widens THAT
# row and the two stop matching exactly. **Measured: 60 of 3,786 team-weeks on the gained side
# and 60 on the allowed side — 2.85% of sides have one.**
#
# ✅ SETTLED IN B117 (cfdb-wta-R-927's residual): **KEEP R-590. THE RESIDUAL STAYS.** B116 left
# the trade open and Cowork closed it, and the reason is recorded HERE — beside the measurement —
# so the next round does not reopen it from first principles.
#
# **Cowork's reason, kept because it is the argument and not the verdict:** cross-matchup
# comparability is the stronger property, because it is what lets a reader carry an impression
# from one page to the next. **A frame that widens for whichever two teams happen to be on screen
# makes two matchups in the same week silently incomparable — the same defect as two box rows on
# two axes, one level up.** ⚠️ **2.85% of rows extending past a shared boundary, each drawn with a
# caret and its full number printed, is a cost a reader can SEE and reason about. An incomparable
# axis is not.**
#
# ⚠️ THE ALTERNATIVE, NAMED SO IT IS NOT REDISCOVERED: passing `union ∪ both values` would make
# the two rows agree in 100% of cases and would cost exactly the property above. **It is one line
# and it is not taken.** ✅ Either way the flip is a strict improvement: exact on 97.15% of sides,
# and closer on the rest than the 13.8% it replaces.
_BOX_SHARED_AXIS = True


def _week_union(week_rows, *columns):
    """The union of the named week rows' whisker pairs — the WEEK's, never the screen's.

    🚨 R-590 IS THE WHOLE CONSTRAINT: *"the axis is a property of the week, not of the two teams
    on screen … deriving the limits from the two teams present would look identical on any single
    game and be wrong across the week."* **This reads only distribution rows**, so two matchups
    in one week are handed the same frame and stay comparable.

    🚨 B119 NOW CALLS IT WITH **ONE** COLUMN, AND THAT IS A CHANGE OF FACT RATHER THAN A
    SHORTCUT — THE OLD DOCSTRING FORBADE EXACTLY THIS AND ITS REASON NO LONGER HOLDS.

    It read: *"a union of one row is that row's own frame wearing a shared name — the chart would
    look shared and not be."* ✅ **True while gained and allowed were two DIFFERENT rows**
    (`total_yards_for_per_game` against `total_yards_allowed_per_game`), which is what
    cfdb-wta-R-927 was about: B114 measured them 13.8% apart on `total`.

    ✅ **AT GAME GRAIN THEY ARE THE SAME ROW, AND THAT IS MARC'S OWN POINT ARRIVING ON THE PAGE:**
    *"If Oregon gained 497 yards last week. the opponent would have Allowed 497 and the match for
    setting the min/max and quartiles would lead to the same results."* A142 proved the bijection
    — the pool is mirror-closed, so the multiset of allowed values IS the multiset of gained
    values — and B118 confirmed it on three live weeks (2026 wk1 both 276.00/367.50/470.50; wk2
    both 283.25/357.50/459.75; 2025 wk7 both 305.75/375.00/448.00).

    ⚠️ **SO ONE ROW IS NOT HALF THE UNION — IT IS THE WHOLE OF IT**, and the frame it returns is
    genuinely the week's. The variadic signature is kept because the property it guards is
    unchanged and a future caller may again have two.

    ⚠️ IT RETURNS `None` WHEN A NAMED ROW IS ABSENT, which is the week this view cannot hold —
    week 1, where there is nothing before. `box(frame=None)` is then each row's own whiskers,
    which is the honest thing for a week we do not hold.
    """
    spans = []
    for column in columns:
        row = week_rows.get(column)
        if row is None:
            return None
        lo, hi = row.get("whisker_low"), row.get("whisker_high")
        if lo is None or hi is None or pd.isna(lo) or pd.isna(hi):
            return None
        spans.append((float(lo), float(hi)))
    return min(lo for lo, _hi in spans), max(hi for _lo, hi in spans)


# 🚨 cfdb-main-R-1028. THE PAGE'S TICK MODE, IN ONE PLACE, AND THE ONE PLACE IS THE POINT.
#
# **Marc, v17:** *"the boundaries of the chart should extend to the MIN and MAX"*, with those two
# labelled and the whisker ends not. A150 shipped that as `ticks=TICK_EXTREMES`.
#
# 🚨 AND IT IS A CONSTANT RATHER THAN A LITERAL AT EACH CALL SITE BECAUSE **`TICK_EXTREMES`
# SILENTLY CHANGES THE SCALE**, not just the labels: `box()` widens `frame_lo`/`frame_hi` to
# `min_value`/`max_value` when it is set (its own `wants_extremes`). **Three things in this file
# must therefore agree about it** — the two call sites, and `_box_frame`, which predicts the frame
# for the circle overlay. ⚠️ **A literal at each of the three is three chances to move two.**
_BOX_TICKS = distribution.TICK_EXTREMES

# 🚨 cfdb-main-R-974, OPEN SIX ROUNDS, AND MARC'S OWN LOOK AT THE SHIPPED v17 IS WHAT CLOSED IT.
#
# **Marc, 2026-09-16, on the live Oregon at Oklahoma State panel:** *"Looks like we just have
# box-whisker IQRs and do not have the min and the max as the true boundaries for that graph."*
#
# 🚨 IT WAS ALREADY CORRECT AND HE WAS STILL RIGHT, WHICH IS THE WHOLE ARGUMENT FOR THIS MARK.
# 📊 On his panel's **Total** row — 2026 wk2, measured on live serving — `whisker_low` = 67.0 =
# `min_value` and `whisker_high` = 762.0 = `max_value`, `outlier_count` **0**. The fences are
# −126.5 and 862.8, so the extremes sit inside them and the whiskers legitimately reach the
# chart's ends. **Nothing was wrong and nothing was visible.**
#
# ⚠️ AND WHEN THE EXTREMES *DO* LIE BEYOND THE FENCES, THE SPAN BETWEEN THE WHISKER END AND THE
# CHART'S BOUNDARY IS EMPTY — A150 and B126 both left it so. **A reader cannot tell *the whiskers
# reach the extremes* from *the chart continues past them to something unmarked*.** §4.3's family:
# the picture carries a distinction it does not draw. ✅ **The ring is that distinction, drawn.**
#
# 📊 AND IT IS NOT A RARE CASE — MEASURED, BECAUSE B118 REFUSED THIS MARK AND THE REFUSAL DESERVED
# CHECKING: a ring lands on **89.5% of the 846 rows the 240px chart draws** and **61.3% of the 648
# the metric cells draw.** ⚠️ Marc's Total row is in the quiet minority; **`rushing_yards` on that
# same panel carries `max_value` 569.0 against a whisker end of 365.0 and gets one.**
#
# 🚨 B118's MEASURED OBJECTION IS DEAD TWICE OVER. It cost **209 printed labels (6.3%)** — but
# those were the WHISKER-END labels Marc has since asked not to see (cfdb-main-R-1020), and the
# wider frame the rings need is the frame v17 already uses. 📊 **Confirmed rather than argued:
# across all 1,494 rows at both widths, the SVG with rings is BYTE-IDENTICAL to the one without
# once the ring groups and the aria narration are removed. The box does not compress; the rings
# add a mark and take nothing.**
_BOX_OUTLIERS = True

# 🚨 cfdb-main-R-1070 / cfdb-wta-R-1071. MARC'S v18, AND THE CLAUSE IS THE REQUIREMENT:
#
# > **MARC, v18:** *"MIN/MAX should extend full height of the plot (to the exten of the Box).
# > Plot MIN/MAX below (underneath in the Z) so that if IQR and MIN/MAX are equal, should be
# > able to discern both on the chart."*
#
# 📊 **AND IT IS THE COMMON CASE ON THE CHARTS HE LOOKS AT, NOT AN EDGE.** A154 measured the
# coincidence at **10.5% of 846 rows** — but 846 is every row of
# `srv_game_team_metric_distribution_through_prior_week`, **18 metrics × 47 weeks**, and the
# 240px chart draws **three** of those metrics. On the 141 rows it actually draws:
#
#     at least one end coincides   130 of 141   92.2%
#     both ends coincide             6 of 141    4.3%
#
# **On nine rows in ten of Marc's own yardage charts the whisker serif lands on the extreme**,
# which is exactly the picture he could not read (cfdb-main-R-1065). A154's number is not wrong;
# it answers *how often across the relation* and this answers *how often on this chart* (§2.4).
_BOX_EXTREME_LINES = True

# 🚨 THE VALUE LABEL LEAVES THE AXIS ROW — Marc, v18: *"Move the label for the box-whisker line
# for displyaing for the team to be either a) above the box, or below but inside the chart area
# (so that it doesn't compete for real estate with the the min, p25, p75, max axis labels and we
# get axis labels for MIN, p25, p75, MAX on all the box-whisker charts.)"*
#
# ⚠️ **IT CHANGES THE SVG's HEIGHT, AND THAT IS WHY IT IS A CONSTANT RATHER THAN A LITERAL.**
# `box()` adds a `top_band` and wraps its body in `translate(0, top_band)` once this is set, so
# **`_circle_column` — which matches `box()`'s box EXACTLY so the overlay needs no offset — has
# to follow it.** Three things in this file must agree about it: the two call sites and the
# overlay. A literal at each is three chances to move two, which is `_BOX_TICKS`' own reason.
_BOX_VALUE_OWN_ROW = True

# 🚨 THE PAGE'S OWN `wants_extremes`, AND IT EXISTS BECAUSE B126 WATCHED THE LAST ONE GO STALE.
#
# `box()` widens its frame to the published extremes when ANY of four arguments asks
# (`outliers`, `frame_extremes`, `ticks == TICK_EXTREMES`, and now `extreme_lines`). `_box_frame`
# copies that frame for the circle overlay, and B126's finding was that **a copy of a function's
# INPUTS is only safe while the input list is CLOSED** — A150 added a fourth way to ask and
# nothing failed. ⚠️ A154 has now added a FIFTH.
#
# ✅ So the page states the question once, over its own flags, instead of naming one of them.
# Today all three are True and the answer is unchanged; the point is that it stays right on the
# day one of them goes back to False.
_BOX_WANTS_EXTREMES = (_BOX_OUTLIERS or _BOX_EXTREME_LINES
                       or _BOX_TICKS == distribution.TICK_EXTREMES)


def _box_frame(row, value):
    """The span `box()` will frame this row on: its whiskers, widened by the value marker — and,
    under `_BOX_TICKS`, by the published extremes.

    🚨 THE OLD DOCSTRING WAS WRONG THREE WAYS AND THE THIRD ONE COST THIS ROUND ITS PART 0.
    It read: *"IT IS A READ, NOT A CALCULATION, AND IT EXISTS FOR THE REPORT RATHER THAN FOR THE
    PAGE. Nothing in the rendered panel calls it — `_week_frame_captions` does … A copy of
    `box()`'s framing RULE would drift; this is a copy of its INPUTS, which cannot."*

    ❌ *"Nothing in the rendered panel calls it"* — **B122 wired it in.** `_gained_allowed` calls
    it twice, and the frame it returns is the axis every circle is placed on.

    ❌ *"`_week_frame_captions` does"* — **that function has not existed for several rounds**, and
    this file already says so a thousand lines further up.

    🚨 *"A copy of its INPUTS … cannot [drift]"* — **A150 GAVE `box()` A NEW INPUT.** A copy of a
    function's inputs is only safe while the input list is CLOSED. Nothing was holding it closed,
    and nothing failed.

    📊 **MEASURED BEFORE THE FIX, ON EVERY REAL DISTRIBUTION ROW IN SERVING (141 of them):** the
    two frames differ on **135**, and on a 240px row a circle moves a **median of 13.0px and up to
    77.9px — 32% of the chart's width.** 61.5% of sampled placements drift 10px or more. ⚠️ **And
    the clamp in `_circle_column` would have pinned the widest to the edge, which looks
    deliberate.**

    ✅ **SO THE COPY STAYS — the module exposes no way to ASK what frame it used — BUT IT IS
    SINGLE-SOURCED TO `_BOX_WANTS_EXTREMES` AND PROBED AT THE PAGE'S OWN CONFIGURATION.** See
    `test_the_CIRCLES_and_the_BOX_agree_about_WHERE_A_VALUE_GOES`, which now renders a real
    `box()` with the page's ticks rather than with the module's default — **that guard existed
    through A150 and was blind for exactly this reason.**

    🚨 **B128: A154 ADDED THE FIFTH WAY TO ASK (`extreme_lines`) AND THIS DOCSTRING'S OWN LESSON
    CAME DUE AGAIN.** B126 wrote *"a copy of a function's INPUTS is only safe while the input
    list is CLOSED"* and then keyed the guard on ONE input. ✅ **The condition is now the page's
    own disjunction over its own flags (`_BOX_WANTS_EXTREMES`), so adding a sixth way costs one
    line in one place** — and the honest answer to *what would keep this honest next time* is
    that it cannot be kept honest from here at all: **only `distribution` can say what frame it
    used, and until it does this is a mirror that has to be re-checked every time A moves.**
    """
    if row is None:
        return None
    lo, hi = row.get("whisker_low"), row.get("whisker_high")
    if lo is None or hi is None or pd.isna(lo) or pd.isna(hi):
        return None
    lo, hi = float(lo), float(hi)
    if value is not None and not pd.isna(value):
        lo, hi = min(lo, float(value)), max(hi, float(value))
    # 🚨 THE HALF A150 ADDED. `box()` does this unconditionally once `wants_extremes` is true, so
    # a frame computed here without it is an axis the box is not drawn on.
    # ⚠️ GUARDED ON `_BOX_WANTS_EXTREMES` RATHER THAN ON ONE FLAG. B126 keyed it on `_BOX_TICKS`
    # alone, which was right that day and would have gone silently wrong the moment the page kept
    # `extreme_lines` and dropped the labels — the same shape as the drift B126 itself found.
    if _BOX_WANTS_EXTREMES:
        for name, pick in (("min_value", min), ("max_value", max)):
            edge = row.get(name)
            if edge is not None and not pd.isna(edge):
                if pick is min:
                    lo = min(lo, float(edge))
                else:
                    hi = max(hi, float(edge))
    return lo, hi


# 🚨 THE GLYPH IS THE OUTLOOK'S SHAPE, AND SHAPE COMES FIRST (AC-G.22). R-722's classification
# survives the chart change: the scatter carried it on its single point, and a box-and-whisker
# has no single point, so it moves into the legend block beside the subtraction it describes.
# ⚠️ FILLED AND HOLLOW ARE THE THIRD SIGNAL, which is what `_OUTLOOK_UNKNOWN` needs — it is not
# a fourth verdict and must not read as one, so it is a hollow SQUARE: neither of Marc's two
# shapes, and legible in greyscale without the colour.
def _outlook_glyph(outlook) -> str:
    """R-722's verdict as one character plus its colour, at THIS page's size.

    ⚠️ `.8rem` IS THE ONLY THING THIS FUNCTION STILL DECIDES, and it is the size of the legend
    block it sits in rather than anything about the verdict. `glyphs.outlook` owns the shape, the
    colour and the meaning; `glyphs.render` composes the span. **Today will call the same two and
    pass its own size.**
    """
    return glyphs.render(glyphs.outlook(outlook), size="font-size:.8rem")


def _legend_line(side, caption: str, column) -> str:
    """One line of the top-right block: logo, the word, the figure.

    🚨 AC-G.11 AT LOGO SIZE, AND IT IS B100's RULE CARRIED OVER: a missing logo falls back to
    the TEAM'S NAME, never to a hole.

    ⚠️ AND `identity.logo_or_monogram` IS NOT THAT FALLBACK, WHICH THIS ROUND FOUND BY READING IT
    RATHER THAN BY ASSUMING. Leaving the Vega spec looked like it turned B100's hand-rolled text
    substitute back into the app's own helper — **and the helper returns
    `<span class='cfdb-monogram-empty' … style='width:14px;height:14px'></span>` for a null
    logo.** That is correct for AC-G.28, which is about the FOOTPRINT not moving, and it draws
    **nothing a reader can see**. On a card the name is already beside it; in this block the
    logo is the only thing naming the side, so an empty box makes `Gained 154.4` anonymous.
    ✅ **So the branch stays, and it is B100's: no logo, the name in its place.** R-855's lesson
    pointed the other way for once — the existing path was right for its own call sites and
    wrong for this one, and only reading it said so.
    """
    name = str(side.get("team_display") or "?")
    logo_url = side.get("logo_url")
    missing = (logo_url is None or (isinstance(logo_url, float) and pd.isna(logo_url))
               or not str(logo_url).strip())
    logo = (f"<span style='opacity:.75'>{html.escape(name[:10])}</span>" if missing
            else identity.logo_or_monogram(logo_url, name, 14))
    return (f"<div style='display:flex;align-items:center;gap:.3rem;"
            f"justify-content:flex-end;white-space:nowrap'>"
            f"{logo}<span style='opacity:.8'>{html.escape(caption)}</span>"
            f"<span style='font-weight:600;min-width:3.2rem;text-align:right'>"
            # 🚨 cfdb-main-R-1070. **THE COLUMN WAS ALREADY BEING PASSED AND THEN OVERRIDDEN.**
            # Marc, v18: *"Don't use decimal points when displaying Yards. That includes …
            # legend Gained/Allowed/Delta"*. `fmt.precision_for` answers 0 for every column this
            # line receives; the `dp=1` was the only thing holding `154.4` on screen.
            f"{fmt.number(side.get(column), column)}</span></div>")


def _matchup_legend(team, opponent, for_column, allowed_column, delta, outlook) -> str:
    """Marc's *"Keep the current legend on the graph on top right"* — the worked subtraction.

    🚨 THE PROMPT CALLED THIS *"the green/red/yellow one"* AND THERE HAS NEVER BEEN A LEGEND ON
    THIS CHART. `matchup.py` contains the word nowhere, and `_scatter` — the Altair scatter B114
    replaced with this chart — said why in its own comment: the outlook's shape and colour were
    *"SET ON THE MARK RATHER THAN ENCODED FROM THE DATA, because this chart plots exactly one
    point — an encoding would add a scale and a legend to say what a single mark already is."*
    ⚠️ **What sat in the top right was `_annotation_layers`, also removed by B114: Marc's own
    v02.2 request for *"a line below the Opponent metric (like a math problem)"*.** That is the
    thing he is asking to keep, and this function is where it is kept.
    #
    ✅ AND LEAVING THE VEGA SPEC FIXES A FRAGILITY R-803 HAD TO WORK AROUND. In there the rule
    under the subtraction could not be a `mark_rule` — one positioned entirely in screen values
    inside a layered chart serialises correctly and DRAWS NOTHING — so it was a one-pixel
    `mark_rect` with a comment begging the next reader not to simplify it. **In HTML it is a
    `border-top` and the class of defect is gone**, which is the second thing this change buys
    beyond the shape Marc asked for.
    """
    return (
        f"<div data-cfdb='matchup-legend' style='float:right;text-align:right;"
        f"font-size:.72rem;line-height:1.35;margin:0 0 .15rem .6rem'>"
        f"{_legend_line(team, 'Gained', for_column)}"
        f"{_legend_line(opponent, 'Allowed', allowed_column)}"
        f"<div style='border-top:1px solid currentColor;opacity:.75;margin:.1rem 0'></div>"
        f"<div style='display:flex;align-items:center;gap:.3rem;justify-content:flex-end'>"
        f"{_outlook_glyph(outlook)}"
        f"<span style='font-weight:700'>{_signed_delta(delta)}</span></div></div>")


def _box_row(row, side, caption: str, column, accent: str, frame=None, overlay: str = "") -> str:
    """One series: its label, then `box()`'s SVG.

    ⚠️ THE LABEL IS DRAWN HERE BECAUSE `box()`'s OWN `label` IS NOT DRAWN AT ALL — it goes into
    the `aria-label` and nowhere else, which is correct for a module that does not know what
    layout it is in. Marc asked for *"team name and gained or allowed"*, so both are in it.
    ⚠️ AND THE ACCENT IS A LEFT RULE ON THE LABEL, NOT A COLOURED WORD (AC-G.25): the team
    colour is *"only allowed to appear as a rule"*, and the label still reads in greyscale
    because the WORD says which series it is.
    """
    # 🚨 `side is None`, NEVER `side or {}` — R-610, AND THIS ROUND WALKED INTO IT. The sides
    # arrive as pandas Series and `Series.__bool__` RAISES, so `(side or {}).get(...)` is a
    # ValueError inside `states.section`, which catches it and draws an Error card. B091 shipped
    # exactly this expression one panel along; `test_matchup_yardage.py` records it in the
    # fixture's own comment; **the first draft of this function did it again anyway, and the
    # harness's `assert_no_error_card` is what said so.** A comment recording a trap does not
    # prevent the trap (R-768).
    value = None if side is None else side.get(column)
    name = "?" if side is None else str(side.get("team_display") or "?")
    # ⚠️ THE LABEL IS THE FORMATTED FIGURE, NOT `box()`'s DEFAULT. `fmt.number` is given the
    # COLUMN, so a yardage renders the way every other yardage on this page does; `box()`'s own
    # fallback knows only a decimal count. **`None` means "let the module label it", which is
    # what an absent figure must get — there is nothing to format.**
    # ✅ `frame=` IS A139's PARAMETER AND IT ONLY WIDENS. Both series on a metric are handed the
    # SAME week union, so they are drawn on one scale — and each row keeps its own whisker serifs
    # and its own boundary labels, because `lo`/`hi` draw and `frame_lo`/`frame_hi` scale.
    # ✅ `height=_BOX_BAND` IS A145's PARAMETER AND THIS IS THE CALL SITE IT WAS BUILT FOR.
    # Marc: *"The box-whisker will have to be taller to accommodate the circles."* A145 proved
    # `height=None` renders today's bytes exactly and that **Matchup is the only consumer of
    # `box()`**, so the whole blast radius of passing it is this page.
    # 🚨 cfdb-main-R-1020. MARC TOOK THE PRINTED NUMBERS OFF: *"Don't think we have real estate
    # to print the numbers.  Draw the whiskers but don't add tick marks/labels for the values."*
    #
    # ✅ `ticks` GATES ONLY THE `place(...)` CALLS IN `distribution.box` — the box edges, the bold
    # median and the whisker serifs draw regardless — so this is *draw the whiskers, drop the
    # numbers* exactly, with no geometry hanging off it. **Read at `e001a17` rather than taken
    # from the prompt** (§2.2.1c), because B124 proved a three-round-old claim about a column
    # false by opening the file.
    #
    # ⚠️ THE VALUE LABEL STAYS AND THAT IS MARC'S OWN SPLIT: the ticks are the percentile and
    # boundary numbers, **the marker is the team's own figure and is the one they came for**.
    # `box()` places the marker's label BEFORE the `ticks` gate, so the two are independent.
    # 🚨 cfdb-main-R-1070, MARC'S v18, AND THE `dp=1` BELOW WAS THE ONE THAT MATTERED MOST.
    #
    # > **MARC, v18:** *"Don't use decimal points when displaying Yards. That includes
    # > Box/Whisker marks, axis labels, legend Gained/Allowed/Delta, Player Cards. Exception is
    # > YDS/CARRY (#.#)"*
    #
    # ⚠️ **THE LINE ALREADY PASSED THE COLUMN AND THEN OVERRODE IT WITH A LITERAL.**
    # `fmt.number(value, column, dp=1)` — the column name is right there and `dp=1` outranks it,
    # so the team's own figure, the number a reader came for, printed `413.5` while every other
    # yardage on this page printed `413`. **Dropping the override is the whole change**; the rule
    # itself is `fmt.precision_for`'s and has been since R-555 (§4.2.1 — one place, not two).
    #
    # ✅ `metric=column` ASKS THE SAME TABLE FOR THE AXIS LABELS. 📊 Measured on the 141 rows this
    # call site draws: all four axis labels survived on **42 (29.8%)** and now survive on
    # **141 (100%)** — and the DECIMAL alone does it, before the label move is counted.
    # ⚠️ A154's 70.8% baseline is the 846-row relation, 15 of whose metrics this chart never
    # draws; both numbers are right about different populations (§2.4).
    chart = distribution.box(
        row, value=value, width=_BOX_ROW_WIDTH, label=caption, value_color=accent,
        frame=frame, height=_BOX_BAND, ticks=_BOX_TICKS, outliers=_BOX_OUTLIERS,
        metric=column, extreme_lines=_BOX_EXTREME_LINES,
        value_labels_own_row=_BOX_VALUE_OWN_ROW,
        value_label=(None if value is None or pd.isna(value)
                     else fmt.number(value, column)))
    return (
        f"<div data-cfdb='box-series' data-series='{caption.lower()}' "
        f"style='margin:.1rem 0 .45rem'>"
        # ⚠️ THE INDENT WENT WITH THE GUTTER (B119). This read
        # a 40px left margin so the SVG lined up with the strip's plot, which sat
        # right of a 40px opponent column. **The circles carry no per-row label, so there is no
        # column to clear and the chart starts at the block's own left edge** — see
        # `_BOX_ROW_WIDTH`, which took the 40px back.
        f"<div style='font-size:.7rem;opacity:.75;border-left:3px solid {accent};"
        f"padding-left:.35rem;margin-bottom:.1rem;white-space:nowrap;overflow:hidden;"
        f"text-overflow:ellipsis'>"
        f"{html.escape(name)} "
        f"<span style='font-weight:600'>{html.escape(caption)}</span></div>"
        # 🚨 THE RELATIVE WRAPPER IS THE WHOLE OVERLAY MECHANISM, AND IT IS ONE LINE. The chart's
        # SVG and the circles' SVG are the same width and the same height and both sit at this
        # box's origin, so **they share one coordinate system and nothing computes an offset.**
        # ⚠️ An offset would be a second copy of `box()`'s internal layout, which is exactly the
        # coupling `_AXIS_PAD` declares once and guards with a test rather than spreading.
        # ⚠️ THE WRAPPER IS WIDTH-BOUNDED so the absolute child cannot escape it; `box()` emits
        # `max-width:100%` and the overlay matches, so both scale together if the slot narrows.
        #
        # 🚨 AND IT IS AN `inline-block` SPAN RATHER THAN A `div`, WHICH THE BROWSER TAUGHT ME.
        # The first draft used a block `div`, and `getBoundingClientRect()` measured the GAINED
        # row's overlay **40.3px above its own chart** while the Allowed row was exact.
        # ⚠️ **`_matchup_legend` is `float:right`.** A block wrapper's LINE BOXES flow around that
        # float, so the chart — an inline `span` from `box()` — was pushed down by the legend's
        # height, while the absolutely-positioned overlay ignored the float and stayed at the
        # wrapper's top. **Two elements that must share a coordinate system, in two different
        # ones.**
        # ✅ An `inline-block` participates in the line flow exactly as `box()`'s own span did, so
        # the float interaction is unchanged — and it is a positioned ancestor, so the overlay
        # measures from the chart rather than from a box the float moved.
        # 🚨 NO TEST COULD HAVE SEEN THIS. The markup was identical for both rows and every
        # assertion about structure passed; only `getBoundingClientRect()` on a real page could
        # tell the two apart. **B119 changed its code for a render, B120 for a measurement, and
        # this is the third.**
        f"<span style='position:relative;display:inline-block;"
        f"width:{_BOX_ROW_WIDTH}px;max-width:100%'>"
        f"{chart}{overlay}</span></div>")


# 🚨 R-899. THE CALENDAR, ONE READ FOR BOTH SIDES AND ALL THREE METRICS.
#
# ⚠️ IT IS THE SECOND QUERY THIS PANEL MAKES AGAINST `srv_game_team` AND THAT IS THE GRAIN
# TALKING, NOT A DUPLICATE. `_game_team_rows` reads ONE GAME's two rows for the deltas; this
# reads TWO TEAMS' whole regular seasons. Different `where`, different row count, same relation —
# G-2 is one relation per query, which both satisfy. `lib.query.query` is `@st.cache_data`
# wrapped, so neither pays for the other.
#
# ⚠️ AND IT CARRIES ALL SIX PER-GAME COLUMNS RATHER THAN ONE, because the three sections draw
# three different strips off the same rows. Six columns in one read beats three reads.
#
# 🚨 cfdb-wta-R-994. `opponent_classification` IS THE SEVENTH AND IT IS WHAT MARC'S FILL RULE
# READS: *"Can circles be team color filled with 90% black border (for FBS opponents). Non-FBS
# opponenets should not be filled."* It is the classification of **that game's own opponent**,
# already on the row the circle is drawn from — so the rule is a column this query selects and
# **not a join, a second read or a lookup in the page** (G-2).
#
# ⚠️ IT DID NOT EXIST IN SERVING UNTIL A146 AND B121 STOPPED A ROUND ON IT (cfdb-main-R-1007):
# `srv_game_team.sql:153` MENTIONS the name in a comment and line 156 consumes it inside
# `is_fbs_game`, and live serving answered `UndefinedColumn`. **Checked against
# `information_schema` this round before anything was keyed on it**, which is the rule that
# mention cost.
_CALENDAR_COLUMNS = """
    team_id, week, game_date, is_home, opponent_abbreviation,
    opponent_team_display, opponent_rank, opponent_classification,
    record_before_display,
    points_for, points_against,
    total_yards, rushing_yards, passing_yards,
    total_yards_allowed, rushing_yards_allowed, passing_yards_allowed,
    game_figures_state
"""


def _game_calendar(season: int, season_type: str, team_ids: tuple, before) -> dict:
    """Both teams' regular-season calendars BEFORE this game, kickoff ASCENDING, keyed by team_id.

    🚨 `before` IS A LEAKAGE BOUND AND IT IS THE WHOLE OF cfdb-wta-R-1000. Marc found it on the
    live site: *"this is the Today / Before the Game. It shouldn't present data that transpired
    during the game. This should be data from prior to the game, so there should only be 1 circle
    in this Week 2 matchup."*

    ❌ **THIS QUERY HAD NO TIME BOUND OF ANY KIND.** It fetched a team's whole season and the page
    drew a circle for every row carrying a figure — **including the game being previewed, and
    every game after it.** A week-2 preview drew two circles; a week-1 matchup in a finished
    season drew the entire twelve-game season, none of which had happened yet.

    🚨 **AND THE IRONY IS WORTH KEEPING: THE BOX WAS ALWAYS HONEST AND THE MARKS ON IT WERE NOT.**
    A143 built `srv_game_team_metric_distribution_through_prior_week` to be strictly-before-week,
    argued the rule at length and shipped a dbt test asserting the boundary. **Half the panel
    obeyed R-463 and half did not, on the same axis, in the same picture** — through B119, B120 and
    B122, because the filter read *games with figures* and nobody asked **figures as of when.**


    ✅ **`game_date <` IS THE BOUND, AND THE THREE CANDIDATES WERE MEASURED RATHER THAN RANKED.**

    | | |
    |---|---|
    | ❌ `week < :week` | **wrong at a real edge, and a big one.** 📊 2026 regular **week 1 has NINE
      distinct kickoff dates** and week 2 has three — so a Saturday preview would drop a team's own
      Thursday game, which it genuinely played |
    | ❌ a KICKOFF timestamp | **`srv_game_team` does not publish one.** It carries `game_date`
      (a `date`) and nothing else temporal; `start_date` lives on `srv_game`. §2.5 again — the
      column the obvious fix wants is not there |
    | ✅ `game_date < :before` | **date against date, one filter, no cast.** A team cannot play
      twice in a day, so *earlier date* and *earlier kickoff* are the same set |

    ⚠️ **AND THE PROMPT SAID TO PREFER A KICKOFF BOUND BECAUSE A WEEK BOUND IS WRONG. IT IS RIGHT
    ABOUT THE WEEK AND THE KICKOFF IS NOT AVAILABLE** — but the date bound is equivalent to it in
    every case but one, measured: **120 team-games of 225,350 (0.053%) share a date with another
    game of the same team, and exactly ONE pair since 2024.** Those lose an earlier same-day game.
    ✅ **A `start_date` on `srv_game_team` would close it exactly; it is A's file and it is not
    worth a round on its own** — reported rather than worked around.

    ⚠️ **AND IT IS A FILTER, NOT A COMPUTATION (§4.2.1).** A `WHERE` on a published date creates no
    quantity, has no second consumer and cannot disagree with an export. **The comparison is
    date-to-date on two columns the warehouse already publishes** — which is also why the game
    row's own `game_date` had to join `COLUMNS`: deriving it from `start_date` in the page would be
    a timezone conversion, and the two genuinely differ (game 401856670 is `game_date`
    **2026-09-12** against `start_date` **2026-09-13 02:15Z**).

    🚨 THE ORDER FLIPPED IN B119 AND IT IS MARC'S INSTRUCTION, NOT A TIDY-UP. v14 asked for the
    strip *"order by kick-off date, desc"*; v15 asks for the circles *"Order them top down (asc)
    based on kick-off date"* — **the opposite, and stated explicitly.** ✅ The order is still
    decided HERE, once, so nothing downstream forms a second opinion (R-768: a page that re-sorts
    a frame it was given ends up asserting that pandas sorts).

    🚨 AC-G.39, AND THE BOUND WAS WRONG UNTIL B120 — TWICE IN A ROW, THE SAME WAY.

    B115 wrote *"max 13"* from 2026 alone and it travelled through two prompts. B119 corrected it
    to *"15 — two teams in 2025 and one in 2024"* and concluded *"two teams cannot exceed 30
    rows"*. ⚠️ **B119's query was `order by season desc limit 12`, so it only ever looked at the
    four most recent seasons.** R-859's class, committed while fixing an instance of it: the
    command answered *the longest calendar in recent seasons*, which is a different question from
    *the longest calendar*.

    📊 MEASURED ACROSS EVERY SEASON `srv_game_team` HOLDS — the page can reach all of them, since
    `srv_game` spans **1869 to 2026**:

        longest regular-season calendar   22 games  (team 80, 1894 — the only season above 20)
        arithmetic ceiling for two teams  44 rows   > the old limit of 40
        worst REAL pair in any matchup    33 rows   (1894 game 1491: 11 + 22)
        matchups that exceed 40 today     0

    ✅ **SO NOTHING IS TRUNCATED ON THE LIVE SITE AND THE OLD LIMIT WAS NEVER BREACHED — but it
    was justified by a false sentence, and the ceiling the GRAIN permits is 44.** AC-G.39 asks the
    bound to be the grain restated rather than a guess, so it is **60**: above the ceiling with
    room, and small enough to still be a bound.

    🚨 AND THE ASCENDING ORDER CHANGES WHICH END A TRUNCATION WOULD COST. The old comment said a
    descending order *"would truncate the OLDEST games, which is the end a descending order makes
    least harmful"*. **Ascending truncates the NEWEST**, which is the harmful end — so the bound
    is no longer merely comfortable, it is load-bearing. 30 against 40 is the margin, and the
    circles are sized for 15 for the same reason.
    """
    df = query(f"""
        select {_CALENDAR_COLUMNS}
        from srv_game_team
        where season = :season
          and season_type = :season_type
          and team_id in (:away_team_id, :home_team_id)
          and game_date < :before
        order by game_date asc
        limit 60
    """, {"season": season, "season_type": season_type,
          "away_team_id": int(team_ids[0]), "home_team_id": int(team_ids[1]),
          "before": before})
    return {team: rows for team, rows in df.groupby("team_id", sort=False)}


# --- cfdb-wta-R-964: the ordered jitter, one circle per game --------------------------------

# 🚨 MARC, v15, VERBATIM: *"Instead of printing a full calendar below, Within the Box-Whisker
# chart, allow enough vertical space to place an unfilled circle mark indicating the measure for
# each game the team played. Order them top down (asc) based on kick-off date. The rows can be
# tight to the point the circle marks overlap vertically by 50%. The calendar is almost acting
# like an ordered jitter. Get it right for the primary team first (gained), then we'll do the
# same for the opponent (allowed)"*
#
# ✅ THIS REPLACES B115's CALENDAR STRIP AND HE SAID WHY: *"The listing of the games/calendar
# isn't working how I expected, but it is demonstrating the challenge with fitting all those data
# points in the vertical space."* ⚠️ **The strip was not wasted — four of its measured lessons are
# load-bearing here** (cfdb-wta-R-941, R-955, R-956, and the caret rule), and they are cited at
# the lines that depend on them rather than summarised.
#
# 🚨 WHAT DOES **NOT** CARRY: THE RESERVED ROW. The strip printed a row for every scheduled game
# so the shape of the season was visible before it was played, with `no box score` and `not yet`
# as named absences. **These are circles for games the team HAS PLAYED** — *"for each game the
# team played"* — so an unplayed game contributes no mark and there is no absence to name.
# **A branch for a state that cannot arise is decoration (R-762), so there is no branch.**

# 🚨 THE GUTTER IS GONE AND `_BOX_ROW_WIDTH` GETS ITS 40px BACK.
#
# B115 cut the box from 240 to 206 to buy a 40px column for the strip's opponent abbreviation,
# and indented the box by the same amount so the two lined up. **The circles carry no per-row
# label — the opponent, the record and the score live in the hover (Part 2) — so the column that
# cost the chart a sixth of its width has nothing to put in it.**
#
# ⚠️ 240 IS B114's MEASURED CEILING, NOT AN INVENTED ONE: the live render at 1300px with the
# sidebar open measured the chart slot at **246px**, and `box()` emits `max-width:100%`, so a
# wider SVG does not overflow — **it SCALES, quietly taking its 9px labels down with it.** 240
# fits at its declared size; 246 is the wall. **Re-verified in the browser this round rather than
# carried (R-805).**
_BOX_ROW_WIDTH = 240

# 🚨 `_AXIS_PAD` IS `box()`'s PRIVATE `pad` AND COPYING IT IS THE THING B114 REFUSED TO DO.
#
# ⚠️ RENAMED FROM `_STRIP_PAD` / `_strip_x` IN B119, AND THE RENAME IS THE POINT RATHER THAN
# TIDYING. The calendar strip is gone; a constant named after a deleted element is the next
# reader's false lead — the class B115 was caught by with four dead `_scatter` pointers and the
# class B117 gave a test. **What it names is the AXIS `box()` draws on, which is what it always
# actually was.**
#
# B114's own words, declining to align two box rows by width-and-offset: *"it needs `box()`'s
# internal `pad`, which is a local variable. Coupling this file to another module's private
# constant is worse than the parameter it is avoiding."* ⚠️ **That judgement stands for that
# problem and cannot be applied to this one**: there is no way to put a NEW element on an
# existing chart's axis without knowing that chart's geometry, and the alternative is a column of
# circles that does not line up with the distribution it is drawn against.
#
# ✅ SO THE COUPLING IS DECLARED AND THEN MADE LOUD. `test_the_CIRCLES_and_the_BOX_agree_about_
# WHERE_A_VALUE_GOES` renders a real `box()` and reads back the x it drew its median at, then
# asserts this module's own mapping puts the same number in the same place. **The day
# `site/lib/distribution.py` changes its padding, that test fails and names why** — which is what
# a silent copy of a constant can never do. ⚠️ **It survived the strip deliberately: it is the
# instrument that lets the circles be trusted to sit where they claim.**
_AXIS_PAD = 10


def _axis_x(value, frame, width):
    """Where `value` sits on the box row's axis — the SAME mapping `box()` uses.

    ⚠️ A COORDINATE TRANSFORM, NOT METRIC ARITHMETIC (§4.2.1), and the same note `_box_scale`
    carries in `site/lib/distribution.py`: this produces a pixel offset inside one <svg>, which
    nobody can cite, export or sort on. The quantities it maps — the whiskers, the frame, the
    game's own yardage — all arrive published.
    """
    lo, hi = frame
    span = (hi - lo) or 1.0
    return _AXIS_PAD + (float(value) - lo) / span * (width - 2 * _AXIS_PAD)


# 🚨 SIZED FOR FIFTEEN, AND THE THIRTEEN IT REPLACES IS WHY THE RULE EXISTS (cfdb-wta-R-976).
#
# B115 measured *"1 to 13 games"* on **2026** serving and wrote 13. That figure travelled through
# two prompts unchecked. 📊 **Measured across every season in serving this round: the longest
# regular-season calendar is FIFTEEN — two teams in 2025 and one in 2024, both selectable on the
# site today.** A column sized to 13 overflows by two circles on a season a reader can open now.
#
# 🚨 AND THE PITCH IS MEASURED RATHER THAN SET TO MARC'S CEILING. He granted *"tight to the point
# the circle marks overlap vertically by 50%"* — **a ceiling he will tolerate, not a target.**
# At d=7 a 50% overlap is a pitch of 3.5px and fifteen games in 56px; at a pitch of 8 they do not
# overlap at all and fifteen take **119px**.
#
# 📊 THE BUDGET THAT DECIDES IT, measured in the browser this round at 1300px: the three-card
# block beside the chart is **325px**, and the chart column at a pitch of 8 totals legend + two
# box rows + 119 ≈ **283px**. ✅ **The circles fit without overlapping at all, so none of Marc's
# allowance is spent** — the tightest layout he authorised is not the one the page needs, and
# spending it would cost legibility for nothing.
#
# ⚠️ FIXED PITCH, VARYING TOTAL HEIGHT — B115's argument, and it survives the chart change
# because it was never about the strip. A height fixed at 119px and divided by the game count
# would give a 13-game team 9.2px where its 15-game neighbour gets 8, **and two columns on one
# screen would stop being comparable — the same defect as two box rows on two axes.** A fixed
# pitch makes the column's LENGTH an honest reading of how long the season is.
_CIRCLE_D = 7
_CIRCLE_PITCH = 8
_CIRCLE_MAX_GAMES = 15

# 🚨 cfdb-wta-R-993 / v16. THE BAND THE CIRCLES ARE OVERLAID ON — A145's `box(height=)`.
#
# **Marc:** *"The circles need to be overlayed on top of the Box-Whisker with same x and y-axis.
# The box-whisker will have to be taller to accommodate the circles that will cover full regular
# season schedule (even with 50% overlap)."*
#
# 📐 THE ARITHMETIC HE AUTHORISED. At `_CIRCLE_D` = 7 a 50% vertical overlap is a pitch of 3.5, so
# the centres of *n* circles span `(n-1) × 3.5` and the column needs `7 + (n-1) × 3.5`:
#
#     15 games (the longest MODERN regular season)   7 + 14 × 3.5 =  56px
#     22 games (the longest in serving — 1894)       7 + 21 × 3.5 =  80.5px
#
# 📊 **56 IS THE NUMBER, AND THE BLOCK IS WHY.** B120 measured the whole two-box metric block at
# **218.3px against a 354.5px three-card block** beside it, and a taller box multiplies by two per
# block. Measured in the browser this round at 1300px: the overlay REMOVES the two separate circle
# columns from the flow and adds `2 × (band − 26)`, which lands the block at **250.5px at band 56**
# and **298.5px at band 80** — both inside 354.5, and 56 is the one Marc's own sentence names.
#
# 🚨 AND IT IS A CEILING RATHER THAN A FIXED PITCH, WHICH IS THE CLAMP BELOW. B120 measured the
# longest regular-season calendar in serving at **22 games (team 80, 1894)**, not 15. At band 56 a
# 22-game column would need a pitch of 2.33 and **overflow the band at 3.5** — circles clipped by
# the viewBox, silently. `_circle_pitch` compresses instead, so nothing is ever clipped and the
# compression engages on exactly one season in the whole archive.
_BOX_BAND = 56
_CIRCLE_PITCH_MAX = 3.5


def _circle_pitch(n: int, band: int = None) -> float:
    """The vertical gap between successive circles — Marc's ceiling, compressed only if it must be.

    🚨 A CEILING, NOT A FIXED PITCH, AND cfdb-wta-R-976 IS WHY. Marc authorised *"tight to the
    point the circle marks overlap vertically by 50%"*, which at `_CIRCLE_D` = 7 is a pitch of
    3.5. **B120 then measured that the longest regular-season calendar in serving is 22 games
    (team 80, 1894), not the 15 two earlier rounds had assumed** — and 22 circles at 3.5 need
    80.5px of an band that is 56.

    ⚠️ **THE ALTERNATIVE IS SILENT CLIPPING.** An SVG does not complain when a mark falls outside
    its viewBox; the last games of the season would simply not be there, and every test asserting
    *"one circle per played game"* reads the markup rather than the viewport, so all of them would
    still pass. **That is the failure mode this function exists to make impossible.**

    ✅ SO THE PITCH IS `min(ceiling, what fits)` — the ceiling for every modern season, and a
    compression that engages on exactly one season in the archive. ⚠️ **It is stated rather than
    hidden: at 22 games the overlap is 67% rather than 50%, which is past what Marc authorised,
    and the honest reading is that his sentence was written about a modern schedule.**
    """
    band = _BOX_BAND if band is None else band
    if n <= 1:
        return _CIRCLE_PITCH_MAX
    # The centres span `band - _CIRCLE_D`, so the whole circle stays inside the band.
    return min(_CIRCLE_PITCH_MAX, (band - _CIRCLE_D) / (n - 1))


# 🚨 cfdb-wta-R-994. MARC'S FILL RULE, v16, VERBATIM:
#
# *"Can circles be team color filled with 90% black border (for FBS opponents). Non-FBS
# opponenets should not be filled."*
#
# ⚠️ THE FILL IS THE ENCODING AND THE TEAM COLOUR IS DECORATION ON TOP OF IT, WHICH IS THE RIGHT
# WAY ROUND AND WORTH SAYING BECAUSE THE NEXT READER WILL BE TEMPTED TO KEY SOMETHING ON THE HUE.
# B121's render carries a greyscale column and **filled versus unfilled separates cleanly with
# the colour removed** (AC-G.22). 10.89% of games have a side with no sourced colour at all
# (B109), so a rule carried by the hue would be unreadable on one game in ten.
_FBS = "fbs"

# 🚨 *"90% BLACK"* IS A CONTRAST INSTRUCTION, NOT A HEX LITERAL, AND B121 RENDERED WHY —
# `claude_work/renders/B121_fill_and_border_options.png`, three options x light, dark and
# greyscale. A literal `rgba(0,0,0,.9)` ring around a team-filled circle on the dark page's
# `#0e1117` **is in the DOM and not on the screen**: the circle reads as a plain dot.
#
# ✅ SO IT USES THE MECHANISM `_accent` ALREADY HAS RATHER THAN A SECOND ONE (§4.3). `light-dark()`
# follows the `color-scheme` Streamlit sets — not `prefers-color-scheme`, which answers the
# OPERATING SYSTEM and hands a reader on a dark Mac running the app in Light the wrong palette
# (R-547, R-552). B109 measured the cost of getting this wrong on the other element: **18.6% of
# teams publish `#000000`** as their on-light colour and it rendered invisible on a dark page.
# ⚠️ THE DARK VARIANT IS 85% WHITE RATHER THAN PURE WHITE so the ring carries the same visual
# weight as an unfilled circle's stroke, which is drawn at `opacity:.85` below.
_CIRCLE_FILL_BORDER = "light-dark(rgba(0,0,0,.9), rgba(255,255,255,.85))"

# ⚠️ THE DIVISION IN WORDS, FOR THE HOVER ONLY. Measured on live published serving this round:
# `opponent_classification` takes **six states** across `srv_game_team` — `fbs` (149,528 rows),
# `fcs` (34,017), `iii` (12,674), `ii` (12,150), `ii/iii` (4,330) and **NULL (12,651)**.
# 🚨 B121 MEASURED FIVE VALUES ON `classification` AND THE OPPONENT COLUMN'S DOMAIN IS NOT THE
# SAME SET — `ii/iii` is in it. **A `.get` with a fallback rather than a lookup that raises**, so
# a seventh value someday degrades to its own raw name instead of an Error card over the panel.
_DIVISIONS = {"fbs": "FBS", "fcs": "FCS", "ii": "Division II", "iii": "Division III",
              "ii/iii": "Division II/III"}


def _circle_paint(game, accent: str) -> tuple:
    """`(fill, stroke)` for one game's circle, from **that game's own opponent**.

    🚨 THE CLASSIFICATION IS THE ROW'S, AND THAT IS WHAT MAKES THE ALLOWED COLUMN CORRECT FOR
    FREE. B120's allowed circles are **the opposing team's** games, so on that column the
    opponent is the other team's opponent — *not* the team this panel is about. A rule written in
    page code as *"is the opponent an FBS team"* would read the panel's own opponent and be wrong
    on every allowed circle; `opponent_classification` sits on the calendar row the circle is
    already drawn from, so there is nothing to get right twice.

    🚨 NULL IS A THIRD STATE AND IT DRAWS UNFILLED — DELIBERATELY, AND THIS IS THE DECISION.
    A fill ASSERTS *this opponent was an FBS team*, and a null cannot support that assertion, so
    the fill requires positive evidence and absence falls to the unfilled side.

    📊 MEASURED BEFORE THE RULE WAS WRITTEN (§2.5), on live published serving:

    - **coverage is 99.496% on the population that draws circles** — 7,311 of 7,348 played
      team-games carry a classification. The 37 that do not are **every one of them an FCS team
      playing an unaffiliated or NAIA school** (Virginia Lynchburg, Kentucky Christian, Ave
      Maria), and they are reachable here: **19 team-seasons** hold such a game AND an FBS
      opponent, so an FBS-vs-that-team Matchup draws the null on its allowed column.
    - ⚠️ **AND ONE OF THOSE 16 OPPONENT NAMES HAS CARRIED `fbs` IN SOME ERA — "Cumberland (TN)",
      the 1916 Georgia Tech fixture.** That is a name collision across a century, and it is
      precisely why nothing here infers a division from a NAME. Only the row's own column.

    ⚠️ SO THE PICTURE SAYS *not FBS* AND THE HOVER SAYS *which* (AC-G.11). An unfilled circle
    conflates *we know the opponent was FCS* with *we do not know what the opponent was*, which
    are different facts — see `_circle_title`, where the division is named for exactly the
    circles the fill cannot distinguish.

    ⚠️ THE FILL COLOUR IS THE ACCENT THE COLUMN WAS ALREADY HANDED, never a colour fetched here.
    `_gained_allowed` passes `opponent_accent` for the allowed column for the same reason the
    stroke does — R-855, one producer, called twice.
    """
    classification = game.get("opponent_classification")
    if classification is None or pd.isna(classification):
        return "none", accent
    if str(classification).strip().lower() == _FBS:
        return accent, _CIRCLE_FILL_BORDER
    return "none", accent


def _circle_title(game, column) -> str:
    """Marc's hover: *"the Week #, Opponenet Rank, Name, Record, Final Score"*.

    🚨 ZERO JOINS, AND THE B118 PROMPT SAID FOUR. `srv_game_team` — the relation the calendar
    already reads — publishes every one of these, so this is `_CALENDAR_COLUMNS` carrying five
    more names rather than a query this page is not allowed to write (G-2).

    🚨 §2.5, AND IT IS THE RULE THAT PAID HERE: A COLUMN THAT EXISTS IS NOT A COLUMN THAT HAS
    DATA. Measured on the 668 played 2026 team-games — week, opponent, record and both scores at
    **100.0%**, and **`opponent_rank` at 7.6%, 51 of 668.**

    ✅ AND THE 7.6% IS A FACT RATHER THAN A GAP, WHICH IS THE HALF WORTH CHECKING. Per week the
    view carries **25 distinct ranked teams** — a Top 25 — so a null `opponent_rank` means the
    opponent was **unranked**, not that cfdb failed to hold a ranking. **AC-G.11: the tooltip says
    so in a word, and never draws an em dash for it.** An em dash here would report a data gap
    that does not exist, on nine tooltips in ten.

    ⚠️ THE RECORD IS `record_before_display`, WHICH IS THE RECORD GOING INTO THAT GAME. The
    alternative — the record after it — would put a team's final record beside its week-1 circle
    and read as though it were true that afternoon. R-463's property, at row grain.
    """
    week = game.get("week")
    rank = game.get("opponent_rank")
    ranked = not (rank is None or pd.isna(rank))
    name = str(game.get("opponent_team_display") or game.get("opponent_abbreviation") or "?")
    home = game.get("is_home")
    where = "" if home is None or pd.isna(home) else ("vs " if bool(home) else "at ")
    record = game.get("record_before_display")
    scored, allowed = game.get("points_for"), game.get("points_against")
    bits = [f"Week {int(week)}" if week is not None and not pd.isna(week) else "Week ?"]
    bits.append(f"{'No. ' + str(int(rank)) + ' ' if ranked else 'unranked '}{where}{name}".strip())
    # 🚨 cfdb-wta-R-994 / AC-G.11 — THE HOVER SAYS *WHICH* NON-FBS, BECAUSE THE FILL CANNOT.
    #
    # Marc's rule is binary and the picture is therefore binary: filled means FBS, unfilled means
    # everything else. ⚠️ **"Everything else" is five states, and one of them is a NULL** — *we
    # know the opponent was FCS* and *we do not know what the opponent was* are different facts,
    # and an unfilled circle states the first while sometimes meaning the second.
    #
    # ✅ SO IT IS NAMED ON EXACTLY THE CIRCLES THE FILL LEAVES AMBIGUOUS, AND NOT ON THE OTHERS.
    # An FBS opponent gets no phrase: the fill already says so and the section caption says what
    # the fill means, so a sixth line on every tooltip would spend Marc's five-item hover spec
    # (*"the Week #, Opponenet Rank, Name, Record, Final Score"*) restating what is on the screen.
    division = game.get("opponent_classification")
    if division is None or pd.isna(division):
        bits.append("opponent's division not recorded")
    elif str(division).strip().lower() != _FBS:
        key = str(division).strip().lower()
        bits.append(f"{_DIVISIONS.get(key, key.upper())} opponent")
    if record is not None and not pd.isna(record):
        bits.append(f"{record} going in")
    if not (scored is None or pd.isna(scored) or allowed is None or pd.isna(allowed)):
        # ⚠️ THE VERB IS DECIDED BY THE TWO NUMBERS AND NEVER BY A STORED FLAG, because this row
        # is the TEAM's side of the game and `points_for` is already that team's.
        verdict = "W" if float(scored) > float(allowed) else (
            "L" if float(scored) < float(allowed) else "T")
        bits.append(f"{verdict} {int(scored)}-{int(allowed)}")
    value = game.get(column)
    if not (value is None or pd.isna(value)):
        bits.append(f"{fmt.number(value, column, dp=0)} yards")
    # 🚨 cfdb-main-R-1046. ONE STATEMENT PER LINE, LIKE THE CHART'S OWN TOOLTIP UNDER IT.
    #
    # A150 broke `describe()` onto separate lines; this joined with `" · "`, so **two tooltips on
    # one picture broke differently** and a reader hovering a circle and then the chart behind it
    # saw two conventions. §4.3's drift, at the smallest possible scale.
    #
    # 🚨 AND THE CHARACTER IS NOT THE ONE A150 USED, WHICH IS THE WHOLE OF THIS FIX. `describe()`
    # lands in a `title='…'` ATTRIBUTE, so A150's `_attr` emits the numeric reference `&#10;` —
    # a raw newline in an attribute survives a browser but not necessarily a sanitiser.
    # **This string is emitted as an SVG `<title>` ELEMENT, through `html.escape`**, and there
    # the two swap places:
    #
    #     html.escape("a\nb")      -> 'a\nb'          ✅ the newline passes through and breaks
    #     html.escape("a&#10;b")   -> 'a&amp;#10;b'   ❌ the reader sees the literal text &#10;
    #
    # ⚠️ **Measured in Python and then confirmed in Chromium with `el.textContent`**, because the
    # question is what the TOOLTIP shows, not what the markup says (A150's own method).
    return "\n".join(bits)


def _shifted(body: str, top_band: int) -> str:
    """`box()`'s own translate, applied to the overlay so the two stay in one coordinate space.

    ⚠️ **THIS IS A COPY OF `box()`'s WRAPPER AND THE COPY IS THE POINT, NOT AN OVERSIGHT.** The
    overlay is a SIBLING `<svg>` at the same origin; there is no way to ask the module where it
    put its body, so the only alternative to mirroring the transform is arithmetic on every
    circle's `y` — which is the same copy spread over a loop instead of stated once.
    ✅ Emitted only when there IS a band, so a page that turns `_BOX_VALUE_OWN_ROW` off renders
    the pre-B128 bytes exactly.
    """
    return f"<g transform='translate(0,{top_band})'>{body}</g>" if top_band else body


def _circle_column(games, column, frame, accent, width, band: int = None) -> str:
    """Marc's ordered jitter: one circle per played game, earliest at the top, **drawn INSIDE
    the box-and-whisker's own band** (v16, cfdb-wta-R-993) and **filled when that game's opponent
    was an FBS team** (v16, cfdb-wta-R-994 — see `_circle_paint`).

    🚨 IT IS AN OVERLAY NOW, AND THAT CHANGES WHAT SAYS WHOSE GAMES THESE ARE. B119 and B120 spent
    two rounds making the column HUG its own row — 1.2px above against 15.2px below, a 12.7 : 1
    ratio — because **position was the only signal**. ✅ **Overlaid, the box says it**: the circles
    are inside the row's own chart, which is a stronger statement than proximity and one a reader
    cannot misread. ⚠️ `test_A_CIRCLE_COLUMN_HUGS_THE_ROW_IT_BELONGS_TO` asserted the old property
    and is retired with its reason recorded — see its replacement,
    `test_THE_CIRCLES_ARE_DRAWN_INSIDE_THEIR_OWN_ROWS_CHART`.

    ⚠️ THE SVG MATCHES `box()`'s OWN BOX EXACTLY — same width, same total height, same top-band
    translate — and is positioned at the same origin, so **the two share one coordinate system
    and no offset arithmetic is needed.** `_box_row` supplies the `position:relative` wrapper.
    🚨 **B128: `box()`'s total height stopped being `band + 15`.** `value_labels_own_row` adds a
    `top_band` above the plot, so the match is now `top_band + band + 15` with the marks under
    the same translate — see `_shifted`, and `_BOX_VALUE_OWN_ROW`, which both ends read.

    🚨 THE ORDER IS THE QUERY's AND IS NOT RE-SORTED HERE. `_game_calendar` asks for
    `order by game_date asc`, so re-sorting in the page would be a second opinion about the same
    fact — and R-768's class is a test that sorts its own frame and then asserts pandas sorts.

    🚨 THE FRAME IS HANDED IN, NEVER RECOMPUTED (cfdb-wta-R-941). It is the frame the GAINED box
    row above is drawn on, so the circles and the distribution share one scale. ⚠️ **A column that
    computed its own would look identical today and silently stop agreeing the moment anything
    upstream moved** — which is precisely what B116 needed and the reason this is a parameter.

    🚨 A FIXED WIDTH, NEVER `flex:1` (cfdb-wta-R-955), AND THE 1700px RENDER IS THE ONLY THING
    THAT EVER SAW WHY. B115's first strip let its plot stretch to fill the row: at 1300px the slot
    is 246px so it lined up perfectly, and **at 1700px the slot is 369px, the plot took 329 and
    `box()`'s SVG stayed at its declared width** — every mark in the wrong place, with a green
    suite and a pixel-exact 1300px raster. **`box()` ships a FIXED width, so anything that means
    to share its axis must be fixed too.** This is an `<svg>` with a declared width for that
    reason.

    🚨 *"UNFILLED"* WAS MARC's WORD IN v15 AND IT IS NO LONGER TRUE OF EVERY CIRCLE — v16 asks
    for a team-colour fill on FBS opponents, so the two rules meet here. **B119's reason for
    `fill='none'` survives for the unfilled half and is worth keeping written down:** two circles
    at the same yardage still read as two marks rather than one darker blob, which is the whole
    point of a jitter. ⚠️ **The overlap cost is therefore paid on the FILLED circles only**, and
    B121 measured it at this pitch a round before the column to key it on existed.
    """
    # 🚨 `games is None` IS THE SAME ABSENCE AS "NO ROWS WITH FIGURES", AND BEFORE cfdb-wta-R-1000
    # IT WAS A DIFFERENT CODE PATH THAT DREW NOTHING AT ALL.
    #
    # `_game_calendar` groups by `team_id`, so a team with NO rows is simply missing from the dict
    # and `calendars.get(id)` is `None`. ⚠️ **That was unreachable while the query was unbounded —
    # every team had a season.** With the bound, a team whose first game IS this one returns zero
    # rows, and `_gained_allowed`'s old `games is not None` guard skipped the overlay silently:
    # **no circles and no sentence**, which is the absence-with-no-name AC-G.11 exists to stop.
    # ✅ Found by a test written for the reworded sentence, which could not reach it.
    played = [] if games is None else [
        game for _i, game in games.iterrows()
        if not (game.get(column) is None or pd.isna(game.get(column)))]
    if not played:
        # 🚨 AC-G.11, AND cfdb-wta-R-1000 MADE THIS THE MOST-READ SENTENCE ON THE PANEL IN WEEK 1.
        #
        # It used to be a rare state; with the leakage bound applied **every season-opening
        # matchup hits it, on both sides, for all six charts.** So the words were re-read as a
        # week-1 reader would read them and they were wrong twice over:
        #
        # ❌ *"No games played yet"* — the team may have played plenty; what it has not played is
        #   a game BEFORE THIS ONE. The old wording is a claim about the season, and after the
        #   bound it is a claim this branch cannot support.
        # ❌ *"nothing to plot against the spread"* — 🚨 **`Spread` appears FIVE times on this same
        #   page meaning the BETTING LINE** (`Spread/Over/Under`, the market card). On a yardage
        #   chart that is a genuine ambiguity, and it was sitting in the one sentence a week-1
        #   reader sees six times.
        #
        # ✅ The replacement names the absence (*no games before this one*), names what is missing
        # (*game marks*), and says it is temporary (*yet*) — without borrowing a word the page
        # already uses for something else.
        return ("<div data-cfdb='game-circles' data-games='0' "
                "style='font-size:.58rem;opacity:.45;padding:.2rem 0'>"
                "No games before this one, so there are no game marks on this chart yet."
                "</div>")
    lo, hi = frame
    band = _BOX_BAND if band is None else band
    # 🚨 THE SVG IS THE SAME BOX AS `box()`'s, WHICH IS WHAT MAKES THE OVERLAY EXACT. `box()`
    # returns `height + 15` — the band plus its label strip — so matching that and sitting at the
    # same origin puts both drawings in one coordinate space. **Any other height would need an
    # offset, and an offset is a second copy of `box()`'s internal layout** (the coupling
    # `_AXIS_PAD` already declares once and guards with a test).
    # 🚨 B128, AND THIS IS THE LINE THAT WOULD HAVE BROKEN SILENTLY. `box()`'s total height is
    # `top_band + height + 15`, and `top_band` is ZERO only while nothing has asked for a label
    # row above the plot. **`value_labels_own_row=True` asks**, so from this round the chart is
    # 15px taller AND its whole body is wrapped in `translate(0, top_band)`.
    #
    # ⚠️ **AN OVERLAY THAT DID NOT FOLLOW WOULD BE SHORT BY 15px AND HIGH BY 15px** — every
    # circle floating above its own box, on a chart that still looked composed. That is the
    # defect this panel has already paid for twice (B119's float, B122's band), and it is why
    # `_BOX_VALUE_OWN_ROW` is a shared constant rather than a literal at the call site.
    top_band = distribution.LABEL_BAND if _BOX_VALUE_OWN_ROW else 0
    height = top_band + band + 15
    pitch = _circle_pitch(len(played), band)
    # ⚠️ CENTRED ON THE BAND'S MIDLINE, WHICH IS WHERE `box()` DRAWS ITS WHISKER RULE (`mid =
    # height / 2`). A top-anchored column would hang the season off the top of the box and leave
    # the rule bare underneath; centring puts the games either side of the line they are measured
    # against. **Chosen from the raster, not from the arithmetic** — see the round's report.
    # ✅ AND THE PITCH IS STILL FIXED WITHIN A SEASON LENGTH, so B115's property survives: two
    # teams with the same number of games get the same spacing, and the column's EXTENT is an
    # honest reading of how long the season is.
    span = pitch * (len(played) - 1)
    top = band / 2.0 - span / 2.0
    marks = []
    for index, game in enumerate(played):
        value = float(game.get(column))
        inside = lo <= value <= hi
        x = _axis_x(min(max(value, lo), hi), frame, width)
        y = top + index * pitch
        title = html.escape(_circle_title(game, column))
        # 🚨 A VALUE BEYOND THE SHARED FRAME IS PINNED AND SAYS SO — B115's rule, and the one
        # place this element cannot follow `box()`. `box()` widens its frame around an
        # out-of-range value; a mark that shares an axis CANNOT, because widening is exactly what
        # would take it off the axis it is here to share. ✅ **The NUMBER is never wrong — it is
        # printed in full beside the pinned circle — only the POSITION is bounded, and the caret
        # is what says so.** An unmarked pin would read as "at the extreme" when the truth is
        # "beyond it", which is the overclaim `box()`'s own comment warns about.
        extra = ""
        if not inside:
            caret = "◂" if value < lo else "▸"
            anchor = "start" if value < lo else "end"
            at = x + 6 if value < lo else x - 6
            extra = (
                f"<text x='{x + (-6 if value < lo else 6):.1f}' y='{y + 2:.1f}' "
                f"text-anchor='middle' font-size='6' fill='currentColor' "
                f"opacity='.8'>{caret}</text>"
                f"<text x='{at:.1f}' y='{y + 2.5:.1f}' text-anchor='{anchor}' font-size='7' "
                f"fill='currentColor' opacity='.75'>{fmt.number(value, column, dp=0)}</text>")
        # 🚨 cfdb-wta-R-994. THE FILL IS PER CIRCLE, FROM THAT GAME'S OWN OPPONENT — see
        # `_circle_paint`, which carries the rule, the null decision and the measurement.
        # ⚠️ B119's `fill='none'` WAS DELIBERATE AND ITS REASON SURVIVES FOR THE UNFILLED HALF:
        # *"two circles at the same yardage still read as two marks rather than one darker
        # blob"*. **Marc's rule overrides it for FBS opponents and only for them**, so the
        # overlap cost is paid on the filled circles alone — which B121 measured at this pitch
        # before the column existed.
        fill, stroke = _circle_paint(game, accent)
        marks.append(
            f"<g data-cfdb='game-circle' data-week='{html.escape(str(game.get('week')))}'>"
            f"<title>{title}</title>"
            f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{_CIRCLE_D / 2:.1f}' fill='{fill}' "
            f"stroke='{stroke}' stroke-width='1.2' opacity='.85'></circle>{extra}</g>")
    # ⚠️ AC-G.11 — THE SVG NARRATES ITSELF, because a screen reader gets only this string and a
    # column of circles is otherwise silent. It says how many and over what, which is the fact.
    reading = (f"{len(played)} game{'' if len(played) == 1 else 's'} played, each drawn at its "
               f"own figure on the same scale as the distribution above")
    # 🚨 `pointer-events:none` IS THE TOOLTIP DECISION AND IT IS THE WHOLE OF cfdb-wta-R-993.
    #
    # B119 closed this by geometry: *"the circles are a sibling of the chart, not a child… nesting
    # is impossible, so suppression is impossible."* ⚠️ **Overlaying removes that impossibility** —
    # an element drawn on top of the chart takes the pointer, and the tooltip it would suppress is
    # `box()`'s own `title='{describe(row)}'`, **the one that has named the week's tail since
    # B118** and the only place a reader can read n, the quartiles and the outlier count.
    #
    # ✅ **THE CHART'S TOOLTIP WINS, BECAUSE IT IS THE ONE A READER CANNOT GET ANY OTHER WAY.**
    # The circle's own facts — week, opponent, record, score — are all on the page or one click
    # away on the Schedule; the distribution's are not written anywhere else.
    # ⚠️ **AND THE ALTERNATIVE FAILS A TEST THE PROMPT SET: *"a hover that works everywhere except
    # on the marks is not the same as one that works."* With fifteen circles over a 240px chart
    # the marks cover a real share of it, so keeping the per-circle tooltip would punch holes in
    # the chart's own.
    # 🚨 THE `<title>` ELEMENTS STAY IN THE MARKUP DELIBERATELY. They are not dead weight: a
    # screen reader reads them, and `pointer-events:none` suppresses only the POINTER. **So the
    # per-game facts are still there for anyone not using a mouse** — which is the half of AC-G.11
    # that a purely visual decision would have thrown away.
    return (f"<div data-cfdb='game-circles' data-games='{len(played)}' "
            f"style='position:absolute;top:0;left:0;pointer-events:none'>"
            f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}' "
            f"role='img' aria-label='{html.escape(reading)}' "
            f"style='display:block;max-width:100%'>{_shifted(''.join(marks), top_band)}"
            f"</svg></div>")


def _gained_allowed(team, opponent, for_column, allowed_column, week_rows,
                    label: str, outlook=None, delta=None,
                    accent: str = None, opponent_accent: str = None,
                    games=None, game_column: str = None,
                    opponent_games=None, game_allowed_column: str = None) -> str:
    """Marc's v14 chart: the team's GAINED on top, the opponent's ALLOWED below, and the legend.

    🚨 TWO SERIES OVER TWO DIFFERENT DISTRIBUTIONS, WHICH IS WHY IT IS TWO CALLS AND NOT
    `box()`'s TWO-SIDED MODE. Two-sided draws two VALUES on ONE distribution — v10's *"data
    points for both teams"* on a single measure — and this is the other shape: one value each on
    two league-wide spreads, `*_for_per_game` and `*_allowed_per_game`. **Reaching for
    `value_below` here would draw the opponent's allowed figure against the GAINED spread, which
    is a real number in the wrong place.**

    ⚠️ AND THE PAIRING IS THE PANEL'S, NOT A CHOICE MADE HERE: this team's offence against THAT
    team's defence — which is what the `_scatter` B114 replaced plotted, and what
    `_yardage_side_heading` still announces.

    🚨 AN ABSENT WEEK ROW IS `box()`'s OWN PLACEHOLDER AND THAT IS DELIBERATE. It returns a
    titled em dash rather than nothing, so the row keeps its height and the two series stay
    aligned — R-141's rule, and the alternative is the top series sliding down onto the bottom
    one's label whenever one of the six metrics is missing for the week.

    🚨 R-899's STRIP TAKES THE **GAINED** ROW's FRAME, AND WHICH ONE IT TAKES IS A REAL CHOICE.
    This half of the panel is *"<Team> offense against <Opponent>'s defense"*, and the strip
    carries that team's own per-game yardage — so it belongs to the Gained series and is drawn on
    Gained's axis.

    ✅ **AND SINCE B116 THAT IS THE SAME AXIS THE ALLOWED ROW IS ON.** cfdb-wta-R-927 was the
    same problem one element up — the two box rows framed on their own whiskers, 13.8% apart on
    `total` — and A139's `frame=` closed it. **All three elements on a metric now share one
    scale**, so a position means the same yardage in the gained row, the allowed row and the
    calendar beneath them.

    ⚠️ **THE STRIP DID NOT MOVE FOR FREE, WHICH B115 PREDICTED IT WOULD.** It reads `_box_frame`
    — the gained row's whiskers widened by its value — and that is **not** what `box()` scales on
    once a union is handed in. The frame is widened by the union here before the strip sees it;
    without that line the strip would have stayed on the pre-flip axis while the chart above it
    moved, which is the identical disagreement in a new place.

    ⚠️ AND THE FRAME IS `_box_frame`, WHICH IS THE SAME INPUTS `box()` USES — the week's whisker
    pair widened by the team's own value — rather than a second computation off the same row.
    """
    # ✅ ONE UNION PER METRIC, COMPUTED ONCE AND GIVEN TO EVERYTHING ON THE SCALE.
    # 🚨 B119. ONE ROW FEEDS BOTH SERIES, AND `_week_union`'s DOCSTRING CARRIES THE ARGUMENT.
    # At game grain the gained distribution IS the allowed distribution (A142's bijection), so
    # the shared axis is no longer assembled from two rows — it is the one row's own whiskers.
    week_row = week_rows.get(game_column)
    union = _week_union(week_rows, game_column) if _BOX_SHARED_AXIS else None
    # 🚨 THE STRIP'S FRAME IS THE GAINED ROW'S **EFFECTIVE** FRAME, NOT ITS WHISKERS.
    # B115 wrote *"a strip reading the shared frame moves with it for free"* — that is true only
    # if the strip reads what `box()` will ACTUALLY scale on, which is the row's own span widened
    # by its value AND by the union. ⚠️ Reading `_box_frame` alone would have left the strip on
    # the pre-flip axis while the box above it moved, which is the same disagreement one row up.
    frame = _box_frame(week_row, team.get(for_column))
    if frame is not None and union is not None:
        frame = (min(frame[0], union[0]), max(frame[1], union[1]))
    # 🚨 BOTH SIDES NOW — MARC ASKED FOR THE SECOND HALF: *"Get it right for the primary team
    # first (gained), then we'll do the same for the opponent (allowed)"*.
    #
    # ⚠️ EACH COLUMN IS DRAWN ON **ITS OWN ROW'S** EFFECTIVE FRAME, NOT ON ONE SHARED FRAME, AND
    # THAT IS cfdb-wta-R-941 RATHER THAN A REFINEMENT. The prompt said *"the frame — the same
    # one"*, and the DISTRIBUTION row is indeed the same one. **The FRAME is not.** `box()` frames
    # on the row's whiskers widened by ITS OWN value marker, and the two rows carry different
    # markers — this team's gained average against the opponent's allowed average. When either
    # falls outside the week's union, that row alone re-widens, and a circle column handed the
    # other row's frame would sit on an axis its box is not drawn on.
    # 📊 MEASURED THIS ROUND ON LIVE PUBLISHED SERVING, AND THE NUMBER IS SMALL ENOUGH TO BE
    # WORTH STATING PRECISELY: the two effective frames differ on **147 of 24,759 sides —
    # 0.594%** across 2025 and 2026 regular, all three metrics. On 2026 `total_yards` they differ
    # on **none of 3,786**, because the game-grain whiskers (57–762) are far wider than the range
    # of team season-averages that sit on them.
    #
    # ⚠️ SO THE PROMPT'S *"the frame — the same one"* IS RIGHT 99.4% OF THE TIME AND WRONG 147
    # TIMES, AND THOSE 147 ARE EXACTLY THE ROWS A READER WOULD BE MISLED ON. Handing both columns
    # one frame would cost nothing on almost every page and put a mark in the wrong place on the
    # pages where a team's average is extreme — which is the same residual B117 weighed and kept
    # when it settled cfdb-wta-R-927, and the same argument: a cost a reader can see beats one
    # they cannot.
    #
    # ✅ THE PAIRING IS THE PANEL'S OWN: this half is *"<Team> offense against <Opponent>'s
    # defense"*, so the GAINED circles are this team's per-game yardage and the ALLOWED circles
    # are **the opponent's per-game yardage allowed** — the same rows the opponent's own Gained
    # column would use on the other side of the page, read through a different column.
    allowed_frame = _box_frame(week_row, opponent.get(allowed_column))
    if allowed_frame is not None and union is not None:
        allowed_frame = (min(allowed_frame[0], union[0]), max(allowed_frame[1], union[1]))
    # ⚠️ THE GUARD IS ON THE FRAME ALONE NOW. `games` being `None` is a state the element knows
    # how to draw — it is the season opener, and it says so — whereas a missing FRAME means there
    # is no axis to draw anything on, which is the week's own absence and is named in the caption.
    circles = ""
    if frame is not None:
        circles = _circle_column(games, game_column, frame, accent, _BOX_ROW_WIDTH)
    allowed_circles = ""
    if allowed_frame is not None:
        allowed_circles = _circle_column(opponent_games, game_allowed_column, allowed_frame,
                                         opponent_accent, _BOX_ROW_WIDTH)
    return (
        f"<div data-cfdb='gained-allowed' data-metric='{html.escape(label.lower())}'>"
        f"{_matchup_legend(team, opponent, for_column, allowed_column, delta, outlook)}"
        # 🚨 THE CIRCLES SIT DIRECTLY UNDER THE ROW THEY BELONG TO, AND THAT IS AC-G.22 RATHER
        # THAN A LAYOUT PREFERENCE. B115's strip sat below BOTH rows and leaned on the accent
        # colour to say whose games it drew — **shape and position first, colour second**, and
        # colour alone cannot carry it: `_accent` is the team's own hue, 10.89% of games have a
        # side with no sourced colour at all (B109), and the fallback is the same string for
        # both sides. **Position is unambiguous and survives greyscale.**
        # ✅ AND IT IS THE SHAPE THE ALLOWED HALF WILL NEED: gained box, gained circles, allowed
        # box, allowed circles. The alternative — both boxes, then both columns of circles —
        # separates every mark from the distribution it is drawn against.
        # 🚨 v16: EACH COLUMN IS NOW OVERLAID ON ITS OWN ROW'S CHART rather than emitted beneath
        # it. Marc: *"The circles need to be overlayed on top of the Box-Whisker with same x and
        # y-axis."* ✅ **The association that B119 and B120 spent two rounds encoding in PROXIMITY
        # is now structural** — a circle is inside its row's chart — which is why B120's hug test
        # is retired rather than re-tuned.
        f"{_box_row(week_row, team, 'Gained', for_column, accent, union, circles)}"
        f"{_box_row(week_row, opponent, 'Allowed', allowed_column, opponent_accent, union, allowed_circles)}"
        f"<div style='clear:both'></div></div>")


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
        # R-899. Both calendars, one read, six strips.
        # 🚨 cfdb-wta-R-1000. THE BOUND IS THIS GAME'S OWN DATE, AND IT REACHES BOTH COLUMNS.
        # `_game_calendar` fetches BOTH teams in one read, so a single `game_date < :before`
        # bounds the Gained circles and the Allowed ones together — **a bound applied to one side
        # only would be right about half the time and look right all of it.**
        calendars = _game_calendar(int(row["season"]), row["season_type"],
                                   (int(away_id), int(home_id)), row["game_date"])

        # ⚠️ R-522 / spec §0: AWAY ON THE LEFT, HOME ON THE RIGHT. Marc made it a page law
        # rather than this panel's choice — "Data about Away team will be on the left. Same
        # information for the Home team will be on the right" — and the game header already
        # obeys it. The two blocks used to be stacked, away above home, which said the same
        # thing in a different shape on the same page.
        # 🚨 THE SIDE HEADINGS ARE EMITTED ONCE, ABOVE THE SECTIONS, AND THAT IS FORCED BY THE
        # SPANNING HEADER. They used to be the first thing inside each column, which was right
        # while each column owned the whole run of metrics; with the metric loop outside, a
        # per-column heading would repeat three times down the page.
        head_left, head_right = st.columns(2)
        # ⚠️ THE SEASON IS THE GAME'S, NOT TODAY'S (cfdb-wta-R-1071). `_YARDAGE_COLUMNS` has no
        # `season`, and a team link without one lands on the current season from a 2024 page.
        head_left.markdown(_yardage_side_heading(away, home, row.get("season")),
                           unsafe_allow_html=True)
        head_right.markdown(_yardage_side_heading(home, away, row.get("season")),
                            unsafe_allow_html=True)

        # 🚨 cfdb-wta-R-900. ONE TABLE, THREE SECTIONS, EACH HEADER SPANNING THE PAGE — Marc,
        # v14. The heading is emitted OUTSIDE the `st.columns` pair beneath it, and that is the
        # whole mechanism: a markdown block at the top level is the full content width, and the
        # two halves open under it. **B112 solved *"cover the entire row"* this way on the
        # post-game tab and this is the same call, not a second implementation.**
        for dimension in _YARDAGE_DIMENSIONS:
            st.markdown(_section_heading(dimension[0]), unsafe_allow_html=True)
            left, right = st.columns(2)
            with left:
                _yardage_row(away, home, distribution, dimension,
                             deltas.get(int(away_id)), leaders, usage,
                             games=calendars.get(int(away_id)),
                             opponent_games=calendars.get(int(home_id)))
            with right:
                _yardage_row(home, away, distribution, dimension,
                             deltas.get(int(home_id)), leaders, usage,
                             games=calendars.get(int(home_id)),
                             opponent_games=calendars.get(int(away_id)))

        # ⚠️ AN ABSENCE THAT SAYS WHICH ABSENCE IT IS (AC-G.11), AND THERE IS NOW ONE RATHER
        # THAN TWO. See `_metrics_without_a_week`: the off-the-frame case the scatter had cannot
        # happen to a box plot, so the caption that named it has gone with the defect. This is
        # the one that survives — the week itself holds no spread for that metric — and it still
        # prints the two figures, because the row otherwise draws an em dash and says nothing.
        missing_week = _metrics_without_a_week(distribution)
        if missing_week:
            st.caption("  ·  ".join(
                # ⚠️ THE SAME TWO FIGURES THE LEGEND PRINTS, SO THEY FOLLOW THE SAME RULE
                # (cfdb-main-R-1070). A caption that said `154.4` beside a legend saying `154`
                # would be two spellings of one measurement on one panel.
                f"{label} {fmt.number(away.get(for_column), for_column)} gained vs "
                f"{fmt.number(home.get(allowed_column), allowed_column)} allowed"
                for label, for_column, allowed_column, _d, _o in _YARDAGE_DIMENSIONS
                if label in missing_week)
                + " — not drawn against the week, because this week has no distribution "
                  "to draw them against.")

        # AC-G.33. The denominator is not decoration and it is named for each side
        # separately, because a bye or a missing box score makes the two differ.
        st.caption(
            f"Yards per game leading into week {int(row['week'])}, over "
            f"{counted[0]} completed game{'' if counted[0] == 1 else 's'} for "
            f"{home.get('team_display')} and {counted[1]} for {away.get('team_display')}. "
            f"games_counted is not games played — it counts the completed games both "
            f"sides of whose box score cfdb holds.")

        if distribution:
            # 🚨 B119. THE DENOMINATOR IS TEAM-GAMES NOW, NOT TEAMS, AND THE SENTENCE HAD TO
            # MOVE WITH THE RELATION. `teams_in_week` and `min_games_counted` describe a
            # population of team season-averages and are not published by
            # `srv_game_team_metric_distribution_through_prior_week`. **Left as they were, this
            # caption would have raised a KeyError inside `states.section` and drawn an Error
            # card over a working panel** — B091's exact failure, one panel along.
            entry = next(iter(distribution.values()))
            observations = int(entry["n"])
            weeks = int(entry["weeks_counted"])
            # 🚨 R-608: A THIN LINE AND A THICK LINE ARE ONLY SELF-DESCRIBING IF SOMETHING SAYS
            # SO. The weights carry which percentile each edge is, and a reader cannot deduce
            # that from the picture — so the sentence that explains the box explains its sides
            # too, in the one place that already had to exist.
            # 🚨 REWRITTEN FOR THE BOX PLOT, AND THE OLD TEXT IS EXACTLY THE DEFECT B113 SPENT
            # A ROUND ON. It said *"the shaded box is the middle half … the dashed lines are the
            # medians … the box's thin sides are the 25th percentile and its thick sides the
            # 75th"* — a true and careful description of the SCATTER's band, its two dashed
            # median rules and its weighted edges, **none of which exist on a box-and-whisker.**
            # A caption that survives the chart it describes is a justification that stays in
            # the file after it stops being true, one layer out from the code.
            # ⚠️ AMERICAN SPELLING, AND IT IS ENFORCED RATHER THAN PREFERRED. The first draft
            # of this caption read "labelled" and "coloured";
            # `test_no_user_facing_string_uses_british_spelling` failed the build, which is the
            # same guard A119 hit on `favourable` and the reason that literal is what it is.
            # 🚨 THE LAST SENTENCE IS THE ONE THAT MOVED, AND IT HAD TO MOVE WITH THE FLAG.
            # It read *"The two rows are framed on their OWN spreads rather than on a shared one,
            # so read each against its own boundary labels rather than comparing the two by
            # eye"* — **true for exactly as long as `_BOX_SHARED_AXIS` was False, and false the
            # instant it flipped.** ⚠️ The flag, this sentence and the strip are three things that
            # move together, and the paired tests exist so no future round can move one alone.
            # 🚨 AND THE CAPTION SAYS WHAT THE CIRCLES ARE, BECAUSE NOTHING ELSE ON THE PAGE
            # CAN. Marc asked for the marks; a reader meeting a column of rings needs to be told
            # they are single games and that the colored rule is their average — **two different
            # kinds of quantity on one axis, which is legitimate and is exactly the thing that
            # must be said rather than left to be inferred.**
            # 🚨 cfdb-wta-R-994. THIS SENTENCE IS WHERE THE FILL IS EXPLAINED, AND THE CHOICE
            # WAS BETWEEN HERE AND THE HOVER.
            #
            # ⚠️ **A HOVER CANNOT INTRODUCE AN ENCODING, ONLY CONFIRM ONE.** A reader hovers a
            # mark because they already wonder what it is; the reader this has to reach is the
            # one who sees two kinds of circle and does not know a question is available. So the
            # ENCODING is stated here, in the one sentence that already had to explain what a
            # circle is, and the hover names the per-circle detail the picture cannot carry.
            # ✅ AND IT COSTS NO NEW FURNITURE: the alternative was a legend, which would put a
            # key beside all six charts to define one binary — and `_matchup_legend`'s own
            # comment already argues against exactly that shape.
            #
            # 🚨 *"EACH OPEN CIRCLE BELOW IT"* WAS FALSE ON BOTH COUNTS AND THIS ROUND FIXES BOTH.
            # **"Below it"** described B120's layout, where the column sat under the chart;
            # **B122 overlaid the circles INSIDE the band** and left this sentence behind. **"Open"**
            # stops being true here for every FBS opponent. ⚠️ This is the defect the comment
            # forty lines up already names — *"a caption that survives the chart it describes"* —
            # found in the same caption one round later, which is why it is worth saying twice.
            # 🚨 cfdb-main-R-1017 — THE PANEL NOW NAMES THE BOX'S WINDOW. A148 measured the
            # boundary in anger and wrote the reasoning into the MODEL; **the reader meets the
            # PANEL**, and §4.3 is the same rule here as anywhere: the thing carries its window
            # or the caption does. Three facts a reader cannot deduce from the picture — the
            # weeks are those BEFORE this game's own, the population is GAMES rather than team
            # averages, and it is CUMULATIVE rather than last week alone.
            # ⚠️ A148's one honest exception is deliberately NOT here: two previews a season
            # (the Celebration Bowl) count a same-day game that kicks off later, worth ~1.7px.
            # That is a footnote in the model, not a thing a reader needs.
            #
            # 🚨 AND *"BOTH LABELED"* WENT FALSE IN THIS SAME ROUND — cfdb-wta-R-1024 AGAIN, ONE
            # ROUND AFTER IT WAS NAMED. Marc removed the tick and boundary labels
            # (cfdb-main-R-1020), so a caption promising the whiskers are "both labeled" was
            # describing a chart that no longer exists — **found only by re-reading the whole
            # sentence rather than the clause this round came to edit.** That is now the standing
            # instruction for this caption, and the guard list below holds all three phrases.
            #
            # 🚨 B128 — FOURTH PHRASE, AND THIS ONE WAS THE SENTENCE MARC HIMSELF DISAGREED WITH.
            # It read *"the chart itself RUNS PAST THEM to the lowest and highest single game"*.
            # 📊 **On 130 of the 141 rows this chart draws (92.2%) a whisker end IS an extreme,
            # so the chart runs past nothing** — and the caption told the reader otherwise. That
            # is exactly what he reported at v17: *"Looks like we just have box-whisker IQRs and
            # do not have the min and the max as the true boundaries."* **The picture was right
            # and the words promised a gap that is usually not there.**
            # ✅ The replacement names the MARK rather than a gap — a lighter full-height line at
            # each extreme, which is drawn whether or not a whisker reaches it — and then says
            # what the coincident case LOOKS like, because that is the case nine readers in ten
            # are looking at. **Marc's v18 sentence is the acceptance and it is now also the
            # caption: *"if IQR and MIN/MAX are equal, should be able to discern both."***
            frame = (f"Each series is drawn against all {observations:,} team-games played in "
                     f"the {weeks} week{'' if weeks == 1 else 's'} before this game's own — "
                     f"every game those weeks held, counted cumulatively rather than week by "
                     f"week, and not the teams' averages. The box is the middle half, the bold "
                     f"line inside it the median, and the whiskers run to the low and high "
                     f"boundaries. A lighter full-height line stands at the lowest and at the "
                     f"highest single game anywhere in that population, each labeled below — "
                     f"where a whisker reaches that far the two stand together, with the "
                     f"whisker's short serif drawn over the line, and where it does not, a ring "
                     f"marks the game beyond it. The colored mark is "
                     f"that team's average per game, and each circle drawn on it is one game "
                     f"the team played, earliest at the top — filled when that game's "
                     f"opponent was an FBS team, open when it was not. ✅ Both rows are drawn "
                     f"against the same spread, so the two sets of circles can be compared "
                     f"directly: the same position means the same yardage whether it was gained "
                     f"or allowed.")
            if weeks <= _THIN_SAMPLE:
                # 🚨 A092 MEASURED THIS AND SAID TO SAY IT, AND B119 MOVED WHAT "THIN" MEANS.
                # It used to read the least-played TEAM's game count, because the population was
                # team averages and a one-game team's "per game" was that game. **The population
                # is now games, so a game is never an average of anything** — what is thin is the
                # SEASON behind it, and that is `weeks_counted`.
                frame += (f" ⚠️ Early in the season this is thin: it rests on "
                          f"{weeks} week{'' if weeks == 1 else 's'} of results, so the spread "
                          f"will move a good deal as more games are played.")
            st.caption(frame)
        else:
            # ABSENT, NOT AN EMPTY FRAME. AC-G.11 and B075's rule: say WHICH absence it is.
            #
            # 🚨 B119 SPLIT THIS IN TWO, AND BOTH HALVES OF THE OLD SENTENCE HAD GONE FALSE.
            #
            # It read *"No week-wide distribution has been BUILT for this week, so the charts that
            # put these two sides against the rest of the FBS are not drawn."*
            #
            # ❌ *"has been built"* NAMES THE WRONG ABSENCE FOR WEEK 1. This view is every
            # team-game played in weeks strictly BEFORE this one, so **week 1 has no row and can
            # never have one — there is nothing before it.** That is not a pipeline that has not
            # run; it is the first week of the season, and telling a reader the warehouse is
            # missing something is telling them something false about the world.
            # ❌ *"the rest of the FBS"* IS THE WRONG POPULATION SINCE A142. The pool is now every
            # team-game in a game involving an FBS side, which **admits the non-FBS opponent's
            # side too** — 80 non-FBS teams entered the 2026 pool for 85 team-games. That change
            # is what makes gained and allowed match, and the caption must not still claim a pool
            # the model deliberately stopped using.
            opening = str(row.get("season_type")) == "regular" and int(row["week"]) == 1
            st.caption(
                "This is the season's opening week, so there are no earlier games to draw a "
                "spread from yet — the charts that place these two sides against the rest of "
                "the season start next week."
                if opening else
                "No spread has been built for the weeks before this one, so the charts that "
                "place these two sides against every other team-game are not drawn.")
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

# ⚠️ THE READER'S NAME FOR A COLUMN, BUILT FROM THE ROW TUPLES RATHER THAN RETYPED — so a
# measure named in a caption is named the way the row above it is (cfdb-main-R-1091). A second
# spelling of eighteen labels is a second thing to keep in step.
_ROW_LABELS = {field: label for label, field, _dp in _BOX_SCORE_ROWS + _ADVANCED_ROWS}


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
    # 🚨 R-885. `1 (1/0)` RATHER THAN `1 (1 INT · 0 FUM)` — Marc, v11, and the unit moved to the
    # LABEL, which is where a unit belongs when every row in the column shares it. The measure
    # is `Turnovers (INT/FUM)`; the value is the split.
    #
    # 📊 AND IT IS THE WHOLE POINT OF THE CHANGE RATHER THAN A TIDY-UP. This one string governed
    # `_TABLE_VALUE_WIDTH` for the entire panel — measured at **116px in a 116px cell**, 2.5x the
    # next widest value (`47.1%`, 45px) — which is why B111's chart shipped at 110px, 45% under
    # B108's 200px floor. **Marc went at the constraint rather than the symptom.**
    #
    # ⚠️ THE ORDER IS INT THEN FUM AND THE LABEL SAYS SO. A bare `1 (1/0)` with no key is two
    # numbers a reader must guess at; `Turnovers (INT/FUM)` overhead makes the pair readable
    # once for the whole column instead of on every row.
    ints, fumbles = row.get("interceptions"), row.get("fumbles_lost")
    if pd.isna(ints) and pd.isna(fumbles):
        return f"{int(total)}"
    # ⚠️ A MISSING HALF IS AN EM DASH, NOT A ZERO (AC-G.32). `0/1` and `—/1` are different
    # claims: one says no interceptions, the other says we do not hold the split.
    part = "/".join(str(int(v)) if pd.notna(v) else fmt.EM_DASH for v in (ints, fumbles))
    return f"{int(total)} ({part})"


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
# ⚠️ SUPERSEDED BY R-885's BUDGET BELOW, AND KEPT AS THE REASON RATHER THAN AS A NUMBER: the
# value column is no longer sized against the turnovers string, because that string is now
# `1 (1/0)`. The measurement above is why it HAD to be 116 and why it no longer does.

# 🚨 R-864. THE LABEL COLUMN CAME DOWN 12.0 → 8.5rem TO PAY FOR THE CHART COLUMN, AND IT IS THE
# ONLY COLUMN ON THIS ROW WITH REAL SLACK. Measured in the browser at 1300px, sidebar open:
#
#     table Streamlit column   502px      the row used 440 of it — 62px spare
#     label 192 · value 116 · value 116   + three 8px gaps
#     widest measure name      188px      `Havoc rate forced by this defense`, 4px under its box
#     widest value             110px      `1 (0 INT · 1 FUM)`, 6px under its box
#     card name column          86px      tightest names need 87 — the cards have NO slack
#
# ⚠️ SO THE 62px OF SPARE WAS THE WHOLE BUDGET, AND A USEFUL CHART NEEDS 200 (B108's floor,
# confirmed by A131's own sweep). **The cards cannot pay** — their name column is already at its
# measured limit. The label can, because it is the one cell whose full text survives being
# clipped: `_comparison` already wraps every defined measure in `<span title="...">`, so the
# name is on hover and the dotted underline says so.
#
# ⚠️ AND THE COST TURNED OUT TO BE SMALLER THAN THIS COMMENT FIRST CLAIMED — MEASURED IN THE
# BROWSER, NOT REASONED. `_TABLE_LABEL_CELL` carries `overflow:hidden;text-overflow:ellipsis`
# but **no `white-space:nowrap`**, so a long name WRAPS to a second line instead of truncating.
# At 136px the widest name measures 133px and **0 of 23 labels clip**. The two-line names sit
# inside the 56px the chart already imposes, so nothing grows. **The ellipsis this column was
# sized against never fires.**
#
# 🚨 AND IT IS STILL NOT ENOUGH AT 1300px. ⚠️ **CORRECTED IN R-893: this paragraph said 110px
# and 45% under the floor, and named "the 200px alternative" — all three were B111's numbers and
# B112 moved every one of them.** The row budget is 510px now (the gutter halved), so
# 136 + 116 + 116 + 24 leaves **118px, 41% under the floor**, and the alternative this file
# actually carries is **230px** at `_TABLE_CELLS_EQUAL = False`. **That is Marc's trade, not
# this round's to settle.** At 1700px the same row leaves 244px unused and the question does
# not arise.
#
# 🚨 CORRECTED AGAIN, IN B117 (cfdb-wta-R-961): THIS SENTENCE ATTACHED 230px TO `True`, WHICH IS
# THE OPPOSITE OF WHAT THE CODE DOES. `True` makes the three value cells take a third of the
# budget each, leaving the chart the NARROW 118px; `False` gives the value cells their content
# width and the chart the wider 230px. ⚠️ **The paragraph already carried one correction notice
# and shipped an inverted claim anyway**, and the stray space inside the old
# `` `_TABLE_CELLS_EQUAL = True ` `` is the fingerprint of the edit that did it.
# ✅ **So it now has a test.** `test_the_COMMENTS_ABOUT_THE_CHART_WIDTH_AGREE_WITH_THE_CODE`
# recomputes both widths from the literals and checks every pixel figure this file pairs with a
# flag value. **Comments have no test — that is the class, four instances this week — and this is
# one that cheaply can.**
_TABLE_LABEL_WIDTH = 8.5       # rem — 136px; the longest Advanced names WRAP, they do not clip
_TABLE_GAP = 0.5               # rem, between the four columns

_REM = 16

# 🚨 R-885. THE THREE CELLS, AND WHICH ARITHMETIC GOVERNS THEM IS ONE CONSTANT.
#
# **Marc, v11: *"Measure Cells and graph cells should be equal horizontal widths."*** ✅ Built,
# and the report puts the cost in front of him rather than just obeying — because the two
# readings of the same sentence are 122px apart on the one number this panel has been fighting
# over for four rounds.
#
# 📊 MEASURED AT 1300px WITH THE SIDEBAR OPEN, after v11's halved gutter gives the table 510px:
#
#     row = label 136 + three cells + three 8px gaps (24)   ->  486px for the three cells
#
#     EQUAL     three cells of 162px            -> the chart is 162px
#     CONTENT   values at what they now need    -> the chart is what is left
#
# ⚠️ AND `CONTENT` ONLY BECAME POSSIBLE THIS ROUND. The value column was 116px because
# `1 (1 INT · 0 FUM)` needed 116; at `1 (1/0)` the widest value in either section is far
# narrower, so the room the turnovers row was holding is released to the chart. **That is the
# whole causal chain Marc described, and it checks out.**
#
# 🚨 THE FLOOR IS THE REASON IT MATTERS: B108 measured the minimum useful plot width at 200px
# and A131's sweep agrees. B111 shipped 110px and said so. **One of these two options clears
# that floor for the first time and the other does not.**
# 🚨 SHIPPED `True` — MARC'S LITERAL WORDS — AND THE ARITHMETIC IS IN THE REPORT RATHER THAN
# THE DECISION BEING TAKEN HERE. Measured at 1300px, both rendered:
#
#     True   label 136 | value 116 | value 116 | chart 118     the three cells are equal
#     False  label 136 | value  60 | value  60 | chart 230     the values are at their content
#
# ⚠️ AND THE TWO HALVES OF HIS OWN SENTENCE PULL APART, WHICH IS WHY BOTH ARE BUILT. He wrote
# *"That will allow the Box Score to **reduce width of the measure value cells**. Measure Cells
# and graph cells should be **equal** horizontal widths."* **At `True` the value cells do not
# reduce at all** — they stay 116px around a 46px number, because equal-thirds of the same
# budget is what 116 already was. The reduction he gave as the REASON for changing the
# turnovers string only happens at `False`.
#
# 📊 AND THE FLOOR IS WHAT IT COSTS: B108 measured the minimum useful plot width at 200px and
# A131's sweep agrees. **`True` is 118px — 41% under it, and barely better than B111's 110px.
# `False` is 230px, over it for the first time since the chart existed.**
_TABLE_CELLS_EQUAL = True     # True = Marc's literal reading; False = values at their content

# 📊 THE ROW BUDGET, MEASURED RATHER THAN ASSUMED. At 1300px with the sidebar open the content
# area runs 380 → 1220 = 840px. v11 makes it two Streamlit columns instead of three and halves
# the gutter (Part 3), so: 840 − 8 (gutter) − 322 (the card region, two 153px columns and their
# own 16px gap) = **510px for the table**.
#
# ⚠️ IT IS A DECLARED CONSTANT BECAUSE THE CHART'S WIDTH MUST BE A REAL NUMBER OF PIXELS.
# `box()` emits `max-width:100%`, so a chart handed a width its cell cannot honour is SCALED
# rather than clipped — B108's 432px viewBox squeezed into 216px rendered its `18` four pixels
# tall, correct in the DOM and unreadable on the screen. **The row is built to fit the budget;
# the budget is not inferred from the row.**
_TABLE_ROW_BUDGET = 510        # px — the table column at 1300px, sidebar open, after Part 3

_TABLE_CELL_BUDGET = (_TABLE_ROW_BUDGET - int(_TABLE_LABEL_WIDTH * _REM)
                      - 3 * int(_TABLE_GAP * _REM))

# 📊 WHAT THE VALUES ACTUALLY NEED AT `1 (1/0)`, measured in the browser at 1.05rem:
#     `1 (1/0)`  48px   ·  `47.1%`  45px  ·  `-0.075`  45px  ·  `762`  30px
# **60px carries the widest with 12px to spare** — and it is the first time since v08 that the
# value column has been sized by a METRIC rather than by one composite string.
_TABLE_VALUE_CONTENT_PX = 60   # px — the widest value at `1 (1/0)` is 48, plus margin

# 🚨 R-895. THE THIRD OPTION, AND IT ONLY MAKES SENSE BESIDE `_TABLE_CELLS_EQUAL = False`.
#
# 📊 **AND THE CAVEAT IN THE ASK IS ANSWERABLE FROM THE CODE RATHER THAN THE BROWSER: the header
# cell does NOT set the value column's width.** `_TABLE_VALUE_CELL` carries
# `width:{_TABLE_VALUE_WIDTH}rem`, a declared constant derived from the row budget — so the cell
# cannot shrink or grow from its contents, and **removing the text buys no width at all.** What
# it buys is the absence of a TRUNCATION.
#
# ⚠️ WHICH IS THE WHOLE POINT, BECAUSE v11 MOVED THE IDENTITY. The card region's header now
# carries the FULL team name — `North Alabama`, `Arkansas` — one column to the right and on the
# same line. So at `False` the abbreviation is not lost, it is **duplicated badly**: a clipped
# `U…` beside an intact `North Alabama`. **Dropping the text leaves the logo, the team-coloured
# rule under it, and the full name one column over.**
#
# ❌ NOT PICKED HERE. Three options, three renders, one constant each.
_TABLE_HEADER_SHOWS_NAME = True
_TABLE_VALUE_PX = ((_TABLE_CELL_BUDGET // 3) if _TABLE_CELLS_EQUAL
                   else _TABLE_VALUE_CONTENT_PX)
_TABLE_CHART_WIDTH = _TABLE_CELL_BUDGET - 2 * _TABLE_VALUE_PX
_TABLE_VALUE_WIDTH = _TABLE_VALUE_PX / _REM    # rem, for the cell CSS


# 🚨 MARC, v10: *"Make the font of the value a little bigger."* ⚠️ NAMED AGAINST ITS NEIGHBOURS
# RATHER THAN PICKED: the measure name is `.85rem` and the column header is `.92rem`, and a
# value larger than its own header inverts the hierarchy. **1.05rem sits above both and is the
# largest step that does not.** The turnovers row is the one to watch and the report measures
# it — `1 (0 INT · 1 FUM)` had 6px of margin at the old size.
_TABLE_VALUE_FONT = 1.05       # rem — against .85 (measure name) and .92 (column header)

# ⚠️ THE MEASURE NAME IS LEFT-ALIGNED AND FIXED-WIDTH, not `flex:1`. A flexing name column is
# what pushed the two figures apart in the centred layout (R-807); here it would let the value
# columns drift right as the table column grows, so the two sections would stop lining up at
# exactly the viewport widths where there is room to notice.
_TABLE_LABEL_CELL = (f"width:{_TABLE_LABEL_WIDTH}rem;flex:none;opacity:.75;font-size:.85rem;"
                     f"overflow:hidden;text-overflow:ellipsis")
_TABLE_VALUE_CELL = (f"width:{_TABLE_VALUE_WIDTH}rem;flex:none;font-weight:600;"
                     f"font-size:{_TABLE_VALUE_FONT}rem;"
                     f"text-align:right;overflow:hidden;text-overflow:ellipsis;"
                     f"white-space:nowrap")
# 🚨 `overflow:hidden` ON THE ROW — R-755, and this panel has paid for it twice. A Streamlit
# column does not clip its children, so a row wider than its share draws OVER the column beside
# it rather than compressing. The table is hard left now and the card columns are to its right,
# so what it would overrun is the AWAY CARDS.
_TABLE_ROW = "display:block;max-width:100%;box-sizing:border-box;padding:.15rem 0;overflow:hidden"
# 🚨 `center`, NOT `baseline`, SINCE R-864 — AND THE RASTER IS THE ONLY THING THAT SAID SO.
# Baseline is the right answer for a row of three text cells and the wrong one the moment a
# 56px picture joins them: an SVG's baseline is its bottom edge, so the chart hung above its own
# figures and read as belonging to the row above. **Every cell was present, every width was
# exact, and the DOM said nothing.** Measured after the change: the chart's centre and the
# figures' centre agree to 0px, against 15px apart with `align-self:center` alone and further
# still with baseline.
_TABLE_ROW_INNER = f"display:flex;align-items:center;gap:{_TABLE_GAP}rem"


# 🚨 R-864. THE CHART'S OWN COLUMN — Marc, v10: *"make a single box-whisker chart, create a new
# column for it to the right of the home metric value."*
#
# ⚠️ IT IS A FIXED PIXEL WIDTH AND IT HAS TO BE, WHICH IS WHY IT COULD NOT SIMPLY BE `flex:1`.
# `box()` emits `<svg viewBox='0 0 W H' width='W' style='max-width:100%'>`, so an SVG handed a
# width its cell cannot honour is SCALED DOWN rather than clipped — and B108 paid for exactly
# that: a 432px viewBox squeezed into 216px rendered its `18` at 4px tall. **The DOM was
# correct and the text was unreadable.** A flexible cell would reintroduce it at every viewport
# the arithmetic did not happen to match, so the width is declared and the row is built to fit.
#
# 📊 WHAT IT IS AND WHAT IT IS NOT. ⚠️ **CORRECTED IN R-893 — it read "110px … 45% under it",
# which was true of B111 and stopped being true the moment B112 halved the gutter.** The width
# is **118px at 1300px** against B108's 200px floor and A131's sweep, which puts 200px at the
# point where the below band stops dropping to three labels: **41% under it.** See
# `_TABLE_CELLS_EQUAL` for the alternative that clears the floor and what it costs, and
# `_TABLE_LABEL_WIDTH` for where the room came from and why the cards could not give any.

# ⚠️ R-854 IS DISSOLVED RATHER THAN ARGUED. The old band was 116px because it sat UNDER a 116px
# value column governed by `1 (1 INT · 0 FUM)` — a composite string that cannot be plotted at
# all. Its own column is governed by nothing but the chart, so the constraint is gone; what
# replaces it is the room the cards need, which is a different and smaller number.
# 🚨 THE CHART IS CENTRED ON ITS ROW, AND THE RASTER IS WHAT FOUND IT — but the fix is on
# `_TABLE_ROW_INNER`, not here.
#
# ⚠️ **CORRECTED IN R-875. THIS COMMENT SAID `align-self:center` AND CLAIMED `_TABLE_ROW_INNER`
# ALIGNS THE ROW ON THE TEXT BASELINE. Both halves were wrong**, and the comment 25 lines above
# `_TABLE_ROW_INNER` says so correctly: **it has been `align-items:center` since B111.** Worse,
# `align-self:center` on this cell alone is the technique B111 MEASURED AT 15px AND REJECTED —
# the chart centred and the text stayed at the top of the row. **So a reader who found this
# comment first was handed the rejected fix as the shipped one.**
#
# ✅ THE HISTORY WORTH KEEPING: baseline alignment is right for three cells of text and wrong
# for a 56px picture, because an SVG's baseline is its bottom edge — so the chart hung ABOVE its
# own row and read as belonging to the row above. **Every cell was present, the widths were
# exact and the DOM said nothing.** Centring the ROW put the two centres 0px apart. It was the
# third time on this panel that a picture caught what the markup could not (B103's invisible
# `mark_rule`, B108's 2:1 squash, that).
_TABLE_CHART_CELL = (f"width:{_TABLE_CHART_WIDTH}px;flex:none;min-width:0;"
                     f"display:flex;align-items:center")


def _accent(pair) -> str:
    """ONE team colour, as the finished CSS string — and it is written HERE and nowhere else.

    🚨 R-855, AND THIS ROUND IS THE THIRD TO TOUCH IT. `_table_header` built this expression
    inline; B111 needs the identical string for the chart marker. **Two copies that agree today
    are two copies that drift**, and the header underline and the marker naming the same team in
    different colours is precisely the kind of quiet disagreement this file has paid for.

    ⚠️ `identity.text_on(pair)` ALONE IS NOT THE ANSWER, AND B109 MEASURED WHY. It defaults to
    the ON-LIGHT variant, which rendered `rgb(0,0,0)` against a `rgb(14,17,23)` page — invisible
    — for the **18.6% of teams that publish `#000000` there**. `light-dark()` follows the
    `color-scheme` property Streamlit sets, where `prefers-color-scheme` answers the OPERATING
    SYSTEM and hands a reader on a dark Mac with the app in Light the wrong palette (R-547,
    R-552). **Nothing here computes a colour; both variants come straight from `identity`.**

    ⚠️ A SIDE WITH NO SOURCED COLOUR GETS `identity.FALLBACK` from `text_on` — neutral grey, in
    both modes. **10.89% of games have one** (B109), and the marker must still draw: position is
    the encoding and colour is decoration on top (AC-G.22).
    """
    return (f"light-dark({identity.text_on(pair)}, "
            f"{identity.text_on(pair, dark_theme=True)})")


# ✅ R-885. THE SECOND SECTION'S NAME — Marc, v11. He typed *"Advances"*; the section is
# **Advanced Team Stats**, and it is a constant because the string is keyed in three places:
# the heading, the table header row, and the glossary caption beneath. A rename that moves the
# visible word and leaves the others is a rename that half happened.
_ADVANCED_SECTION = "Advanced Team Stats"

# 🚨 R-885. THE BOLD RULE THAT DEFINES EACH SECTION — Marc, v11: *"should have a bold
# underline to help define the section."*
#
# ⚠️ IT IS A SECOND, HEAVIER RULE AND NOT THE ONE ALREADY THERE. `_table_header` draws a 1px
# rule at 25% under the LOGO ROW, which separates the header from the figures; this one belongs
# to the section's NAME and separates one section from the other. **Two rules doing two jobs**,
# which is why this is 2px and the other stays 1px — same weight twice would read as the same
# boundary drawn twice.
#
# 🚨 cfdb-wta-R-995. IT MOVED FROM `border-bottom` TO `border-top` IN B121, AND v11's WORD
# *"underline"* IS NOW WRONG ABOUT THE CODE — WHICH IS WORTH SAYING RATHER THAN LEAVING.
#
# **Marc, v16:** *"Header rows (Total, Rushing, Passing. Can you move the dark separator line to
# be above the row title instead of below. Replace the lower line with one that is much lighter,
# the same weight as horizontal line in the box-whisker plots."*
#
# ⚠️ **HE IS CHANGING HIS OWN v11 AND v14 INSTRUCTIONS, NOT CONTRADICTING THE CODE.** B112 built
# the spanning header for v14's *"a bold line underneath it"*, and that sentence is why this was
# a `border-bottom` for nine rounds. **The 2px is unchanged and its job is unchanged — it still
# marks where one section ends and the next begins. It now does that ABOVE the name**, which is
# where a separator between two sections actually belongs: below the name it sat between the
# title and the rows the title introduces.
#
# ✅ AND THE LOWER RULE IS A DIFFERENT THING NOW. It no longer separates sections — it closes the
# heading off from the rows beneath, so it takes the weight of the chart's own furniture:
# `distribution.py:774` draws the whisker rule at **`stroke-width='1' opacity='.55'`**, and this
# is that line in CSS.
_SECTION_RULE = "border-top:2px solid currentColor"

# ⚠️ A SEPARATE `<div>` RATHER THAN A `border-bottom` ON THE HEADING, AND THAT IS THIS FILE'S OWN
# PRECEDENT RATHER THAN A NEW MECHANISM (§4.3). `opacity` on the heading would fade the TITLE
# with the rule; `_matchup_legend` and `_yardage_side_heading` both already draw a faded rule as
# a standalone div — `border-top:1px solid currentColor;opacity:.75` and `…:.25` — so this is the
# third instance of a pattern, not a first of a new one.
# ⚠️ `color-mix(in srgb, currentColor 55%, transparent)` would also work and `site/lib/theme.py`
# already uses `color-mix`. **The standalone div is preferred because it is THIS file's habit and
# because it matches `opacity='.55'` exactly**, which is what Marc asked to match.
_SECTION_UNDERRULE = "border-top:1px solid currentColor;opacity:.55"


def _section_heading(title: str) -> str:
    """One section's name inside the table, with the bold rule under it (R-885).

    🚨 IT IS MARKUP RATHER THAN `st.subheader`, AND THAT IS THE WHOLE POINT. Two subheaders
    meant two Streamlit blocks with two `st.columns` splits between them, and the seam between
    those blocks IS the whitespace Marc asked to remove. **Inside the table's own markdown
    there is no seam to remove** — the sections are two headings in one continuous run of rows.

    ⚠️ AND IT KEEPS THE HEADING INSIDE THE TABLE COLUMN, so it cannot span the card region the
    way `st.subheader` did. A section name stretching over the player cards was always wrong;
    it only looked right while the cards were cut to the same sections.
    """
    # ⚠️ THE PADDING MOVED WITH THE RULE AND WAS RE-TUNED BY LOOKING, NOT BY SWAPPING THE
    # PROPERTY. `padding-bottom:.25rem` held the title off a rule BELOW it; with the 2px above,
    # the space that matters is between that rule and the title, so it is `padding-top`. ⚠️ The
    # top MARGIN also drops from 1.1rem to .9rem: the rule now sits at the very top of the block,
    # so the old margin plus a visible rule read as a larger gap than v14's did.
    return (f"<div style='font-size:1.15rem;font-weight:700;margin:.9rem 0 0;"
            f"padding-top:.35rem;{_SECTION_RULE}'>{html.escape(title)}</div>"
            f"<div style='{_SECTION_UNDERRULE};margin:.25rem 0 .45rem'></div>")


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
    # 🚨 R-885. THE NAME MOVED OUT OF THIS CELL AND THE CELL STAYED. `_section_heading` now
    # carries the section's name with Marc's bold rule under it, so printing it here as well
    # drew **"Box score" twice, one line apart** — which the raster showed and no assertion
    # could: both elements were correct, present, and exactly what their own tests asked for.
    # ⚠️ THE EMPTY CELL IS NOT DEAD SPACE: it is the label column's width, and removing it
    # would slide both logos left out of register with every figure beneath them.
    cells = [f"<span style='{_TABLE_LABEL_CELL}'></span>"]
    for side, key in ((away, "away"), (home, "home")):
        logo = identity.logo_or_monogram(
            side.get("team_logo_url"), str(side.get("team_display") or "?"), 20)
        pair, abbr = (colors or {}).get(key) or (None, "")
        accent = _accent(pair)
        # 🚨 R-856. THE ABBREVIATION, FALLING BACK TO THE FULL NAME. `North Alabama` did not
        # fit this cell and drew `North Ala…`; `UNA` fits with room to spare, and the LOGO
        # beside it is doing the identifying work that a clipped word was failing at. The
        # monogram still comes off the full name — a two-letter fallback built from `UNA`
        # would be a worse answer than one built from `North Alabama`.
        name = (abbr or str(side.get("team_display") or "?")
                if _TABLE_HEADER_SHOWS_NAME else "")
        cells.append(
            f"<span style='{_TABLE_VALUE_CELL};font-weight:700;display:flex;"
            f"align-items:center;justify-content:flex-end;gap:.3rem;"
            f"border-bottom:3px solid {accent};padding-bottom:.15rem'>{logo}"
            f"<span style='overflow:hidden;text-overflow:ellipsis'>"
            f"{html.escape(name)}</span></span>")
    # ⚠️ THE FOURTH CELL IS EMPTY AND IS STILL EMITTED. The header row is a row like any other,
    # and a header one cell short of the rows beneath it stops being a header — its two logos
    # would sit over the wrong columns the moment the chart column exists (R-864).
    cells.append(f"<span style='{_TABLE_CHART_CELL}'></span>")
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
    min_value, whisker_low, p25, p50, p75, whisker_high, max_value,
    outlier_count
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


# 🚨 cfdb-wta-R-1159. WHAT THE CHARTS ARE DRAWN OVER, WHICH THIS PANEL HAS NEVER SAID.
#
# ⚠️ **AC-G.33 IS ALREADY SATISFIED FOR THE FIGURES AND NOT FOR THE CHARTS, IN THE SAME
# CAPTION.** The Advanced caption ends *"Every rate is over that side's own offensive plays,
# which are counted on the last row"* — the rate's denominator, named. **The CHART beside it has
# a completely different denominator — `n` team-games in the week — and nothing on the panel
# names it.** AC-G.33's own words: *a hit rate without an `n` is a defect, not a style choice.*
#
# 📊 **AND THE WEEKS WHERE IT MATTERS ARE MEASURED, NOT IMAGINED.** Across all 648 published
# rows at this call site:
#
#     n >= 100      486 rows    27 weeks
#     n 51-100       90 rows     5 weeks
#     n 11-25        36 rows     2 weeks   <- 2024 wk15, 2025 wk15 (n=18)
#     n <= 2         36 rows     2 weeks   <- 2024 wk16, 2025 wk16 (n=2)
#
# 🚨 **36 CHARTS — 5.6% — DRAW A BOX, A MEDIAN, TWO WHISKERS, TWO EXTREME LINES AND A RING OVER
# TWO OBSERVATIONS.** Their quartiles are interpolations between two numbers. **That is the
# picture claiming a shape it cannot support**, and it is a strictly worse version of the
# zero-width box B130 went looking for and did not find.
#
# ✅ **THE 240px PANEL ALREADY DOES THIS AND ITS WORDING IS THE PRECEDENT (§4.3 — not a new
# pattern, the same one):** *"Yards per game leading into week N, over X completed games"*, plus
# `_THIN_SAMPLE`'s *"Early in the season this is thin…"*. This is that sentence for the other
# call site, which is the one that actually gets thin samples — the cumulative window never
# does (846 of 846 rows at n > 100).
#
# ⚠️ **`n` IS PER METRIC AND IS NOT UNIFORM WITHIN A WEEK — 29 of 36 weeks yes, 7 no** (it is
# coverage: `n < team_games_in_week` on 40 of 648 rows). **So the caption states the RANGE it
# actually saw rather than one number**, and each chart's own exact `n` stays where
# `distribution.describe()` already puts it, in that chart's hover.
_THIN_DISTRIBUTION = 10


def _distribution_note(spread) -> str:
    """One sentence naming what the eighteen charts are drawn over, and saying when it is thin.

    ⚠️ **READ FROM THE ROWS THE PANEL ALREADY HOLDS**, so this costs no query — `spread` is
    `_metric_distribution`'s dict and every row carries its own `n`.

    🚨 **AND IT RETURNS `""` RATHER THAN A SENTENCE WHEN THERE ARE NO CHARTS**, because a
    caption describing charts that were not drawn is the R-875 class this page keeps finding.
    """
    counted = {metric: int(row["n"]) for metric, row in spread.items()
               if row.get("n") is not None and not pd.isna(row.get("n"))}
    if not counted:
        return ""
    counts = sorted(counted.values())
    low, high = counts[0], counts[-1]
    over = (f"{low:,} team-games" if low == high
            else f"{low:,} to {high:,} team-games, depending on the measure")
    note = (f"The charts draw each measure against every team-game played in this game's own "
            f"week — {over}, with each chart's own count in its hover.")
    # 🚨 AC-G.11 / AC-G.33. THE THIN CASE IS NAMED SPECIFICALLY RATHER THAN LEFT TO THE READER
    # TO NOTICE. A box-and-whisker over two observations has quartiles that are interpolations
    # between two numbers, and the picture says nothing about that on its own.
    if low > _THIN_DISTRIBUTION:
        return note
    # ── cfdb-main-R-1091: THE CLAUSE HAS TO SAY WHAT IT IS DESCRIBING ────────────────────
    #
    # 🚨 B130 TOOK `low` FROM THE SAME SORTED LIST TWICE AND USED IT FOR TWO DIFFERENT JOBS.
    # The *over* clause states the RANGE — correctly, *"196 to 200 team-games, depending on the
    # measure"* — and the *thin* clause then stated **`low` alone**, as though it described the
    # panel. **In a week where one measure's coverage drops and the rest do not, that sentence
    # would read *"with only 8 team-games, the box and the whiskers are drawn between a handful
    # of numbers"* beside seventeen charts drawn over 172** — a false statement about the panel,
    # made by a sentence written to stop a false impression.
    #
    # ✅ **UNREACHABLE TODAY, BY THE DATA RATHER THAN BY THE CODE, WHICH IS WHY IT NEEDED A TEST
    # AND NOT JUST A FIX.** B130's buckets are exhaustive over all 648 rows — 486 at n >= 100,
    # 90 at 51–100, 36 at 11–25, 36 at <= 2 — and **nothing sits between 3 and 10**, so every
    # week is currently all-thin or all-fat and the straddle cannot occur. ⚠️ **It becomes
    # reachable the first time one endpoint's coverage slips**, and nothing about the data
    # guarantees it will not.
    #
    # ✅ **NAMING THE MEASURES BEATS SUPPRESSING THE CLAUSE, AND THE REASON IS AC-G.11 ITSELF.**
    # The alternative the prompt offered — fire only when `high <= _THIN_DISTRIBUTION` — is
    # honest about the panel and **silent about the one chart a reader would over-trust**. An
    # absence must say WHICH absence it is; a caveat must say which charts it is about.
    thin = sorted((metric for metric, n in counted.items() if n <= _THIN_DISTRIBUTION),
                  key=lambda metric: (counted[metric], metric))
    if len(thin) == len(counted):
        # THE WHOLE PANEL IS THIN — B130's wording, unchanged, because it is true here and
        # naming eighteen measures would be a list where a sentence does.
        return note + (f" ⚠️ This week is too thin for that shape to mean much: with "
                       f"only {low:,} team-game{'' if low == 1 else 's'}, the box and the "
                       f"whiskers are drawn between a handful of numbers rather than across a "
                       f"population.")
    # ⚠️ THE LABEL A READER SEES, NOT THE COLUMN NAME. `_ROW_LABELS` is built from the same two
    # tuples the table's rows come from, so a measure cannot be named here under a spelling that
    # appears nowhere on the panel.
    named = ", ".join(f"{_ROW_LABELS.get(metric, metric)} ({counted[metric]:,})"
                      for metric in thin)
    return note + (f" ⚠️ {'One measure rests' if len(thin) == 1 else 'Some measures rest'}"
                   f" on too few for that shape to mean much: {named}. The rest are drawn over "
                   f"the full week.")


def _metric_chart(row, away_value, home_value, dp, accents, metric: str = "") -> str:
    """ONE chart for the measure, carrying BOTH teams — Marc, v10, and it replaces two.

    ❌ `site/lib/distribution.py` IS SESSION A's AND IS NOT EDITED HERE (§3 rule 3.1). A131
    shipped the two-sided parameters; this is the call site they were built for.

    🚨 AWAY IS THE ABOVE VALUE AND HOME IS THE BELOW VALUE, and that pairing is the whole
    assertion this function makes. Marc: *"Would be ideal to label Away above the line, Home
    below, if possible."* ⚠️ **`accents` arrives as an ORDERED PAIR, not a dict**, for the same
    reason `_metric_cell` takes away and home positionally: B082 and B083 both proved a presence
    assertion cannot see a left/right swap, and A131 proved the sharper version one round ago —
    its colour break left every orientation test GREEN and its side break left the colour test
    GREEN. **They are two independent mistakes and they need two independent tests.**

    🚨 `value_below` IS PASSED ON EVERY ROW, INCLUDING WHEN IT IS `None`, AND THAT IS LOAD-
    BEARING RATHER THAN TIDY. `box()` selects two-sided mode on the ARGUMENT BEING PRESENT, not
    on its value: `two_sided = show_value and value_below is not _UNSET`. Omit it for a side
    that has no figure and away silently stops being *the upper half* and becomes *the only
    value*, drawn as a centre marker — **a mark that reads as belonging to neither team, on a
    panel whose entire job is comparing two.** The absence is then narrated by the `aria-label`
    as *"one value — the other side has none"* (AC-G.11), which is the honest sentence.

    ⚠️ THE COLOUR ARRIVES COMPOSED. `box()` takes the finished `light-dark(...)` string and
    resolves nothing; `_accent` is its one producer, shared with the header underline so the two
    cannot disagree (R-855). A `None` pair still yields a string — `identity.FALLBACK` — because
    **10.89% of games have a side with no sourced colour** and the marker must still draw.

    ⚠️ THE WHISKERS DRAW `whisker_low`/`whisker_high`, NOT `min_value`/`max_value`, AND BOTH ARE
    PUBLISHED. The fences are drawn because the extremes compress the box to nothing: on 2026
    week 1 rushing yards the box is 35% of the whisker span and 22% of the min-max span, and the
    outliers are counted separately in `outlier_count` precisely so the box stays readable.

    🚨 cfdb-wta-R-968. `outliers=True` IS NOT PASSED HERE, AND THE PARAGRAPH ABOVE TURNED OUT TO
    BE THE MEASUREMENT THAT DECIDES IT RATHER THAN A WORRY ABOUT ONE.

    A142 shipped `box(outliers=True)`, which draws each extreme as an open ring and **widens the
    frame to take it in** — deliberately, because *"an outlier pinned to the boundary reads as
    'at the extreme' when the truth is 'beyond it'"*. ✅ The widening is the honest half. ❌ What
    it costs at THIS chart's width is not.

    📊 MEASURED ON ALL 648 PUBLISHED ROWS: 397 (61.3%) would widen, and on those the drawn
    whisker span keeps a median 80.9% of its width — **and a worst case of 23.4%.** The
    compression lands almost entirely on the ADVANCED measures, which is this panel:

        offense_passing_plays_ppa   77.5% median   worst 23.4%  (2024 wk14: whisker 0.98, max 5.87)
        offense_explosiveness       82.3%
        offense_rushing_plays_ppa   82.8%
        total_yards / passing_yards / first_downs    100.0% — the box-score half barely moves

    🚨 `_TABLE_CHART_WIDTH` IS 118px TODAY, so 23.4% of it is a box about **twenty-seven pixels
    wide** carrying two value markers and their labels.

    ⚠️ AND THE WIDTH IS THE SYMPTOM RATHER THAN THE INSTRUMENT. B108's lesson is that the DOM
    says nothing about illegibility — every element present, correct, and unreadable — so this
    was counted instead of eyeballed. `box()` DROPS a label that would collide (its own rule 2:
    *"a shifted label points at the wrong place on the axis"*), which turns squashing into a
    countable loss:

    📊 RENDERED AT 118px ACROSS ALL 648 PUBLISHED ROWS, rings off against rings on:
        3,301 labels drawn -> 3,092. **209 printed numbers lost (6.3%),
        and 161 of 648 charts (24.8%) lose at least one.**
        The eight worst metrics are ALL Advanced — passing_plays_ppa 38, rushing_plays_ppa 36,
        stuff_rate 20 — and **no Box Score measure appears among them.**

    ✅ SO THE COST IS NOT UNIFORM AND A FUTURE ROUND HAS A REAL THIRD OPTION: `outliers` is a
    per-CALL argument, so the Box Score half could draw rings while the Advanced half does not.
    **That is a look decision with a measured price on both sides, which is exactly the shape
    R-895 says goes to Marc rather than being taken in passing** — see
    `claude_work/renders/B118_outlier_rings_at_real_width.png`.

    ✅ SO THE COUNT SHIPS AND THE RINGS DO NOT. `outlier_count` is now selected, so `describe()`
    tells every reader *how many* lie beyond the whiskers and how far the week reached, in the
    tooltip that already exists on all eighteen charts — the whole of Marc's *"add the data
    points to also show the IQR whiskers"* that costs no geometry. ⚠️ **Drawing them is a look
    decision and it is Marc's** (R-895's pattern): B118 renders the two options rather than
    picking one.
    """
    if row is None:
        return ""
    away_accent, home_accent = accents
    # 🚨 cfdb-main-R-1020, THE SECOND CALL SITE — the same instruction, and Marc scoped it to
    # both when asked.
    #
    # ⚠️ `value_label=None` DOES NOT SUPPRESS A LABEL HERE, WHICH IS WORTH WRITING DOWN BECAUSE
    # IT READS AS THOUGH IT DOES. `box()` falls back to `fmt.number(value, dp=dp)` when the
    # override is `None`, so **both sides' own figures are printed and both survive this change**
    # — away above the axis, home below it. What `TICK_NONE` removes here is the boundary pair.
    # 🚨 cfdb-main-R-1070, AND THE PROMPT ASKED ME TO SAY WHICH OF TWO THINGS THE `dp` WAS.
    # **IT IS A THIRD.** It is not `fmt.precision_for` and it is not a careless literal: it is
    # `dp_band`, chosen PER SECTION and measured — 0 for Box Score because all six are integer
    # counts, 2 for Advanced because R-829 found that one decimal COLLAPSES the quartiles on
    # eleven 0–1 rates.
    #
    # ✅ **SO `dp=None` MEANS *ASK THE COLUMN* AND THE BOX SCORE HALF NOW DOES.** 📊 Verified
    # rather than assumed: `fmt.precision_for` returns 0 for all six of `_BOX_SCORE_ROWS`, so
    # that section's bytes do not move and the literal it used to carry is gone (§4.2.1 — the
    # decimal rule in one place).
    #
    # 🚨 **THE ADVANCED HALF KEEPS ITS 2 AND THAT IS A REFUSAL WITH A NUMBER BEHIND IT.**
    # 📊 Measured on all 648 published rows, counting rows where two of the four axis labels
    # print the SAME string — a box labelled as if it spanned nothing:
    #
    #     metric                                dp_band=2   precision_for
    #     offense_stuff_rate                      1/36          7/36   (rate -> 1)
    #     defense_havoc_rate                      1/36          5/36   (rate -> 1)
    #     offense_success_rate                    0/36          3/36   (rate -> 1)
    #     offense_standard_downs_success_rate     0/36          3/36   (rate -> 1)
    #     offense_passing_downs_success_rate      0/36          2/36   (rate -> 1)
    #
    # **Marc's v18 sentence is about YARDS.** Pointing this half at `precision_for` would trade a
    # measured decision for one he did not ask for — so `metric=` is passed and `dp` still wins,
    # which is `box()`'s own documented precedence.
    #
    # 🚨 **cfdb-wta-R-1153 / cfdb-main-R-1085 — B129: THE BAND THAT ARRIVES HERE IS NOW A ROW's
    # PRECISION CAPPED BY ITS SECTION's, NOT THE SECTION's FLAT NUMBER.** The reasoning, the four
    # candidates and the three measurements are at the ONE place that computes it, in
    # `_comparison`; this function takes the answer and does not re-derive it. ⚠️ **What changed
    # for this call site: `Offensive plays` stopped drawing `40.00` and the rates did not move.**
    #
    # 🚨 **AND B128's OWN 31.2% WAS WRONG — MINE, AND IN THE EXACT CLASS B128 CAUGHT IN A154.**
    # It probed `dp=2` on ALL EIGHTEEN metrics, **including the six Box Score counts the page
    # never draws at 2** — on which it scores **5.6% against the page's real 99.5%**. 📊 The
    # page's true baseline was **62.5%**, and B129's rule takes it to **68.1%**. *A guard probing
    # a configuration the page does not use is blind to the page*, one round after writing it
    # down (cfdb-wta-R-1156).
    band = {} if dp is None else {"dp": dp}
    return distribution.box(
        row, width=_TABLE_CHART_WIDTH, ticks=_BOX_TICKS, outliers=_BOX_OUTLIERS,
        metric=metric, extreme_lines=_BOX_EXTREME_LINES,
        value_labels_own_row=_BOX_VALUE_OWN_ROW,
        value=away_value, value_color=away_accent, value_label=None,
        value_below=home_value, value_below_color=home_accent, **band)


def _accent_pair(colors) -> tuple:
    """The two teams' finished colour strings, AWAY FIRST — one ordered pair, never a dict.

    🚨 A DICT WOULD LET A SWAP PASS A PRESENCE TEST. The pair is unpacked positionally at every
    call site, so away's colour cannot reach home's marker without the unpacking changing too —
    which is the same reason `_metric_cell` takes its two figures positionally (R-522, B082,
    B083). ⚠️ A side with no entry still yields a string: `_accent(None)` is `identity.FALLBACK`
    in both themes, and 10.89% of games need it.
    """
    lookup = colors or {}
    return tuple(_accent((lookup.get(side) or (None, ""))[0]) for side in ("away", "home"))


def _comparison(away, home, rows, glossary=None, spread=None,
                value_width=None, dp_band=None, colors=None) -> str:
    """One row per statistic, one column per side. Away left, home right — the same
    convention the scoreline uses and the reason that layout reads as a matchup."""
    accents = _accent_pair(colors)
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
            # ⚠️ `dp_band=None` MEANS *ASK THE COLUMN*, WHICH IS A REPURPOSING RATHER THAN A
            # NEW STATE: it used to fall back to the row tuple's own `dp`, and neither call
            # site has ever passed `None`, so that branch was dead. **The row's `dp` still
            # formats the two printed figures** through `_figure` — only the CHART defers.
            #
            # ── cfdb-wta-R-1153: THE BAND IS A CEILING, NOT A FLOOR ──────────────────────
            #
            # 🚨 THE DEFECT B128 FOUND AND CORRECTLY LEFT ALONE: `Offensive plays` printed its
            # figure as `61` and its chart's axis as **`40.00 · 92.00 · 59.50`**. A COUNT AT TWO
            # DECIMALS, LIVE — because `dp_band` is chosen per SECTION and the Advanced section
            # holds eleven 0–1 rates and one integer count. **A per-section number cannot be
            # right for both.**
            #
            # ✅ AND IT IS RIGHT FOR BOTH THE MOMENT IT STOPS BEING A FIXED WIDTH AND BECOMES A
            # LIMIT. The row already declares what the measure has — it is the same `dp`
            # `_figure` prints with. The section declares what a 118px cell can carry. **The
            # chart takes the LESSER, so it never claims more precision than the figure beside
            # it and never spends more than the cell affords.**
            #
            #     offense_plays    row 0, ceiling 2  ->  0   ✅ the defect, closed
            #     the rates        row 3, ceiling 2  ->  2   ✅ exactly R-829's choice, unmoved
            #     line_yards       row 2, ceiling 2  ->  2   ✅ unchanged
            #     Box Score        no ceiling        ->  the column, as B128 shipped it
            #
            # 📊 MEASURED ON ALL 648 PUBLISHED ROWS AT THIS CALL SITE'S OWN CONFIGURATION,
            # against the three numbers the round was set — and against `dp_band=2`'s baseline
            # rather than against zero:
            #
            #     candidate                       counts w/    rate rows w/ two    four labels
            #                                  decimal axis    identical labels      at 118px
            #     today (per-section band)            1            28 / 396           62.5%
            #     per-ROW band                        0            27 / 396           44.0%  ❌
            #     max(precision_for, band)            1            28 / 396           56.8%  ❌
            #     re-key fmt.precision_for            0         🚨 50 / 396           75.2%
            #  ✅ min(row, band) — THIS ONE            0            28 / 396           68.1%
            #
            # ⚠️ **THE OTHER THREE EACH FAIL A NUMBER.** A per-ROW band gives the rates their
            # tuple's 3 decimals and costs 18 points of survival; `max` does not fix the count at
            # all; re-keying `fmt` buys the most survival and **doubles the rows where two of the
            # four axis labels print the same string** — a box labelled as if it spanned nothing,
            # which is the defect R-829 measured and is worse than a missing label. ✅ This one
            # is the only candidate that improves all three at once, and it costs the rates
            # NOTHING: 28 is today's 28.
            #
            # ⚠️ AND `min` IS WHY THE FIGURE AND THE CHART CANNOT DISAGREE AGAIN — see
            # `test_a_ROWS_FIGURE_AND_ITS_AXIS_COME_FROM_ONE_DECISION`. It is a property of the
            # arithmetic rather than a coincidence of two tables agreeing (§4.2.1).
            chart=_metric_chart((spread or {}).get(field),
                                away.get(field), home.get(field),
                                None if dp_band is None else min(dp, dp_band),
                                accents, metric=field)))
    return "".join(lines)


def _metric_cell(away_value: str, label: str, home_value: str, chart: str = "") -> str:
    """One measure, as a table row: NAME, the two figures, then the CHART (R-847, R-864).

    ⚠️ AWAY BEFORE HOME, AND IT IS ONE ORDERED PAIR RATHER THAN TWO ARGUMENTS USED TWICE — the
    away-over-home law this site follows everywhere (R-522). B082 and B083 both proved a
    presence assertion cannot see a left/right swap, so the test asserts the ORDER.

    🚨 THE CHART IS A FOURTH CELL ON THE SAME FLEX ROW, NOT A SECOND ROW UNDERNEATH. Marc, v10:
    *"create a new column for it to the right of the home metric value."* The band that used to
    sit below the figures is gone with `_metric_band`; a row is now one line.

    ⚠️ THE CHART CELL IS ALWAYS EMITTED, EVEN EMPTY — R-141's law, which this file already
    follows in `thumbnail`: *an element that appears only when populated shifts everything
    beside it.* The five composite rows draw nothing inside it and still reserve it, so the
    figures do not jump left on those rows.

    ⚠️ EVERYTHING STAYS INSIDE THE ROW, so it inherits `overflow:hidden` and cannot draw over
    the card columns sitting to the table's right — R-755, which this panel has paid for twice.
    """
    return (f"<div data-cfdb='metric-cell' style='{_TABLE_ROW}'>"
            f"<div style='{_TABLE_ROW_INNER}'>"
            f"<span style='{_TABLE_LABEL_CELL}'>{label}</span>"
            f"<span style='{_TABLE_VALUE_CELL}'>{away_value}</span>"
            f"<span style='{_TABLE_VALUE_CELL}'>{home_value}</span>"
            f"<span style='{_TABLE_CHART_CELL}'>{chart}</span></div></div>")


def _custom_row(away, home, label, renderer) -> str:
    """A measure the view publishes no distribution for — a fraction, a composite, a clock.

    🚨 NO CHART, AND THAT IS AC-G.11 RATHER THAN AN OVERSIGHT. `box()`'s own placeholder says
    *"cfdb holds no distribution for this week yet"*, which is TRUE of a measure that could have
    one and FALSE of these five: third down is `6/14`, turnovers is `1 (1 INT · 0 FUM)` and
    possession is `30:51`. **They are not scalars, so there is nothing to take a percentile of —
    ever — and a placeholder promising one later would be the wrong absence.**

    ✅ THE COLUMN IS STILL RESERVED, THOUGH, AND THAT IS R-141's LAW: *an element that appears
    only when populated shifts everything beside it.* `_metric_cell` emits the chart cell on
    every row and this one leaves it empty, so the two figures sit in the same place on a
    turnovers row as on a yards row. **Reserved and blank is not the same as absent, and only
    one of the two keeps the table a table.**
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
# 🚨 R-886. ONE ORDERED LIST, NOT TWO SECTIONS — AND THE DICT IS WHAT MARC'S v11 DISSOLVED.
#
# **Marc: *"For the Player Cards. Continuous, top-down, Quarterbacks (2), Rushing (3),
# Receiving (3), Defense (3), Punter (1), Placekicker (1) … The Player cards should flow top to
# bottom, with no vertical association to the Box/Advanced."***
#
# ⚠️ THE SPLIT BY SECTION EXISTED ONLY TO KEEP THE CARDS IN REGISTER WITH THE TABLE BESIDE THEM.
# The cards were drawn TWICE — once beside Box score, once beside Advanced — which is why
# `_CARD_GROUPS` was keyed by section and why Receiving was in one and Defense in the other.
# **v11 says the vertical breaks are independent, so the cards are drawn ONCE and every group
# appears exactly once.** The keying by section had no other job.
#
# ✅ AND THIS IS THE MACHINERY B113 NEEDS: Punter and Placekicker are **two more tuples in this
# list and nothing else**. The renderer loops it, the reserved-slot rule reads `_RESERVED_GROUPS`,
# and the position header spans both columns for whatever is in it. ❌ **They are NOT added here
# — the serving relation publishes neither panel yet; A134 is measuring whether it can.**
_CARD_GROUPS = (
    ("Quarterback", "total", 2),
    ("Rushing", "rushing", 3),
    ("Receiving", "passing", 3),
    ("Defense", "defensive", 3),
    # ✅ R-887. THE TWO MARC ASKED FOR IN v11, AT THE END, IN HIS ORDER RATHER THAN ALPHABETICAL:
    # *"Quarterbacks (2), Rushing (3), Receiving (3), Defense (3), Punter (1), Placekicker (1)."*
    #
    # 📊 THE GATE WAS QUERIED BEFORE THESE WERE ADDED, not after (R-887): serving carries
    # **punting 8,016 rows over 7,156 team-games** and **kicking 7,816 over 7,149**. A134's
    # publish had shipped by the time this round ran; a group pointed at an empty panel would
    # draw a row of empty boxes, which is the hole AC-G.11 forbids.
    #
    # ⚠️ AND THE DEPTH LITERAL IS `1` BECAUSE MARC SAID SO, NOT BECAUSE THE DATA GUARANTEES IT.
    # Measured on serving: **810 punting team-games (11.3%) and 629 kicking (8.8%) carry more
    # than one man** — maximum **3** for punting and **4** for kicking. `rank()` with a tie
    # yields `1,2,3,3`, and all four rows pass `leader_rank <= 3`. **The slice takes rank 1; the
    # renderer must not assume the relation hands it only one row, and a fixture returning four
    # proves it does not.**
    ("Punter", "punting", 1),
    ("Placekicker", "kicking", 1),
)

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
# 🚨 R-886. TWO SLOTS: THE TABLE, THEN THE CARD REGION. The weights are the old three
# re-expressed — the cards were 1.0 + 1.0 with a gutter between them, and that whole assembly
# is now one slot that splits itself, so 3.14 : 2.0 keeps the same proportions.
_POST_GAME_LAYOUT = (("table", 3.14), ("cards", 2.0))
_POST_GAME_SPLIT = tuple(width for _slot, width in _POST_GAME_LAYOUT)

# 📊 HALF OF THE 16px MEASURED BEFORE THE CHANGE (Part 3). An int, because Streamlit 1.63's
# `gap` accepts one — the named sizes jump 8 → 16 and neither `xsmall` nor `xxsmall` is
# guaranteed to be 8 across versions, so the number is stated rather than named.
_POST_GAME_GUTTER = 8


def _post_game_columns():
    """The TWO columns, keyed by slot — the table, then the whole card region (R-886).

    🚨 IT WAS THREE AND IS NOW TWO, AND THAT IS v11's STRUCTURAL CHANGE RATHER THAN A TIDY-UP.
    The away and home cards were two Streamlit slots, which is why a position header could not
    *"cover the entire row of player cards"* — Streamlit has no way to place one element across
    two of its columns. **The card region is one slot now and splits itself**, so the header
    spans, and the two halves stay in register without depending on Streamlit at all.

    📊 THE GUTTER IS HALVED — Marc, v11: *"Cut the whitespace in half."* **Measured at 1300px
    before the change: 16px.** `st.columns` takes `gap` as an int in Streamlit 1.63, so this is
    an argument rather than CSS — which is what the round was told to establish rather than
    assume. `gap=8` is exactly half, and the report carries the after-measurement.
    """
    return dict(zip((slot for slot, _w in _POST_GAME_LAYOUT),
                    st.columns(_POST_GAME_SPLIT, gap=_POST_GAME_GUTTER)))


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
    return (f"<div data-cfdb='reserved-card' "
            f"style='border:1px dashed rgba(128,128,128,.28);border-radius:6px;"
            f"padding:.28rem .45rem;margin-bottom:.3rem;box-sizing:border-box;"
            f"height:{height:g}rem;display:flex;align-items:center'>"
            f"<span style='font-size:.72rem;opacity:.5;line-height:1.25'>{what}</span></div>")


# 🚨 R-886. THE BOLD UNDERLINE — Marc, v11: *"the Position … should cover the entire row of
# player cards and have a bold underline breaking the vertical space."* Two pixels against the
# table header's one, so the two rules read as different weights rather than as the same rule
# drawn twice, and in the same neutral grey the card border uses so nothing here invents a
# colour (the team colour is the CARD's edge, not the heading's).
_CARD_RULE = "border-bottom:2px solid rgba(128,128,128,.45)"

# 📊 MARC: *"The metric names are too light, gain 50% darker."* They were `opacity:.5`. **.75 is
# the reading that makes them 50% less transparent**, and the alternative reading — 50% of the
# remaining gap to opaque, which is also .75 — agrees. Both renders are in the report.
_CARD_KPI_LABEL_OPACITY = .75

# The gap between the away and home card halves, inside the card region's own flex.
_CARD_COLUMN_GAP = 0.6


# 🚨 R-889. THE VERTICAL DIVIDER — Marc, v11: *"give a vertical line divider (25% gray)."*
#
# 🚨 IT IS DRAWN ON THE COLUMN, NOT INSIDE A ROW, AND THAT IS R-755. `_TABLE_ROW` carries
# `overflow:hidden` because a Streamlit column does not clip its children — a rule drawn inside
# a table row would be clipped by it, and one drawn inside the card region would end where the
# cards end. **This panel has paid for that twice.**
#
# ✅ AND IT SPANS THE TALLER SIDE FOR FREE, WHICH IS THE THING THE PROMPT ASKED TO BE SOLVED.
# Streamlit's columns are flex children, and flex's default `align-items: stretch` makes every
# child the height of the tallest. **A border on the column is therefore the full height of the
# row**, whichever half is taller — and with the two halves no longer in register (v11), which
# one that is now varies by game. A rule sized to the table would end mid-card; one sized to
# the cards would overrun the table. **Neither is sized; the browser is.**
#
# ⚠️ `:has()` SCOPES IT TO THIS COLUMN ONLY. The marker is emitted inside the card region, so
# the selector cannot reach any other `st.columns` on the page — and this page has several.
#
# ⚠️ 25% GREY IN BOTH THEMES, NOT `#404040`. `rgba(128,128,128,.25)` is neutral against either
# ground and is the same family as the card's own `rgba(128,128,128,.22)`, which is the
# precedent this file already set.
_CARD_DIVIDER_CSS = (
    "<div data-cfdb='cards-rule'></div>"
    "<style>[data-testid=\"stColumn\"]:has([data-cfdb=\"cards-rule\"])"
    "{border-left:1px solid rgba(128,128,128,.25);padding-left:.55rem}</style>")


def _card_position_header(title: str) -> str:
    """One position heading, SPANNING BOTH card columns, with a bold rule under it (R-886).

    🚨 THIS IS WHY THE CARDS STOPPED BEING TWO `st.columns` SLOTS. A header that *"covers the
    entire row of player cards"* cannot be drawn inside either column — it has to span them —
    and Streamlit gives no way to place one element across two of its columns. **So the whole
    card region is now ONE markdown block with its own two-column flex inside it**, which is
    also what lets the away and home halves stay in register without depending on Streamlit.
    """
    return (f"<div style='font-size:.7rem;font-weight:700;letter-spacing:.06em;"
            f"text-transform:uppercase;opacity:.8;margin:.85rem 0 .35rem;"
            f"padding-bottom:.2rem;{_CARD_RULE}'>{html.escape(title)}</div>")


def _card_team_header(away, home, accents) -> str:
    """Team logo and name over each side's cards — Marc, v11: *"an overall header"*.

    ⚠️ `identity.logo_or_monogram` IS THE ONE PRODUCER AND `_table_header` ALREADY USES IT — a
    team with no logo gets a monogram at the identical footprint (AC-G.28), so the two halves
    cannot fall out of register because one side has no crest.
    """
    cells = []
    for side, accent in zip((away, home), accents):
        logo = identity.logo_or_monogram(
            side.get("team_logo_url"), str(side.get("team_display") or "?"), 22)
        cells.append(
            f"<div style='flex:1;min-width:0;display:flex;align-items:center;gap:.35rem;"
            f"padding-bottom:.25rem;border-bottom:3px solid {accent}'>{logo}"
            f"<span style='font-weight:700;font-size:.9rem;overflow:hidden;"
            f"text-overflow:ellipsis;white-space:nowrap'>"
            f"{html.escape(str(side.get('team_display') or '?'))}</span></div>")
    return (f"<div style='display:flex;gap:{_CARD_COLUMN_GAP}rem;margin-bottom:.2rem'>"
            + "".join(cells) + "</div>")


def _post_game_cards(leaders, away, home, colors) -> str:
    """ONE continuous, top-to-bottom card region — away left, home right (R-886).

    🚨 DRAWN ONCE, NOT ONCE PER SECTION, AND THAT IS v11's STRUCTURAL CHANGE. The cards used to
    be rendered beside Box score and again beside Advanced, which is what kept them in vertical
    register with the table and what forced `_CARD_GROUPS` to be keyed by section. **Marc:
    *"the vertical breaks are independent"*.** So the region is one block, every group appears
    exactly once, and the table beside it is free to be whatever height it is.

    ⚠️ R-849's RESERVED QUARTERBACK SLOT SURVIVES, AND DELETING IT WOULD HAVE BEEN THE WRONG
    READING OF v11. It was built for TWO alignments and Marc dissolved only one of them:

      · cards ↔ the table beside them — **dissolved**, explicitly
      · AWAY cards ↔ HOME cards — **still wanted**, and now load-bearing in a new way: a
        position header SPANS both halves, so an unmatched card does not merely misalign the
        rows below, it puts them under the wrong heading.

    📊 Measured: **3,990 of 6,736 team-games (59.2%) have exactly one quarterback, and 1,812 of
    3,520 games (51.5%) have the two sides carrying different counts.**
    """
    accents = _accent_pair(colors)
    blocks = [_CARD_DIVIDER_CSS, _card_team_header(away, home, accents)]

    # 🚨 A SIDE WE HOLD NOTHING FOR STILL SAYS SO, AND THE RESERVED SLOT MUST NOT SWALLOW IT.
    # R-849 reserves the second quarterback so the two halves stay in register — but a side
    # with NO leaders in any group is not a side missing one player, it is a side we hold
    # nothing for. **Reserving two blank quarterbacks there answers a different question from
    # the one the reader is asking** (AC-G.11). ⚠️ SAID ONCE, UNDER THE TEAM HEADER, rather than
    # once per group: four copies of the same sentence down one column is the hole restated.
    held = {which: any((leaders or {}).get((int(side["team_id"]), panel))
                       for _t, panel, _w in _CARD_GROUPS)
            for which, side in zip(("away", "home"), (away, home))}
    if not all(held.values()):
        notices = "".join(
            f"<div data-cfdb='card-half' data-side='{which}' style='flex:1;min-width:0'>"
            + ("" if held[which] else
               "<div style='font-size:.72rem;opacity:.45;padding:.3rem 0'>"
               "No player leaders held for this side.</div>")
            + "</div>"
            for which in ("away", "home"))
        blocks.append(f"<div style='display:flex;gap:{_CARD_COLUMN_GAP}rem;"
                      f"align-items:flex-start'>{notices}</div>")

    for title, panel, wanted in _CARD_GROUPS:
        halves = []
        drawn_any = False
        for which, side, accent in zip(("away", "home"), (away, home), accents):
            team_id = int(side["team_id"])
            rows = (leaders or {}).get((team_id, panel), [])[:wanted]
            drawn_any = drawn_any or bool(rows)
            # ⚠️ A SIDE WE HOLD NOTHING FOR DRAWS NO RESERVED SLOTS EITHER — its sentence is
            # above, and a reserved quarterback under it would contradict it.
            halves.append(_card_half(rows, wanted, title, accent, which)
                          if held[which] else
                          f"<div data-cfdb='card-half' data-side='{which}' "
                          f"style='flex:1;min-width:0'></div>")
        # ⚠️ A GROUP NEITHER SIDE HAS IS DROPPED WITH ITS HEADER — a heading over two empty
        # halves is a promise of players nobody recorded, which is the wrong absence (AC-G.11).
        # The QUARTERBACK group is the exception and reserves instead; that is `_RESERVED_GROUPS`.
        if not drawn_any and title not in _RESERVED_GROUPS:
            continue
        blocks.append(_card_position_header(title))
        blocks.append(f"<div style='display:flex;gap:{_CARD_COLUMN_GAP}rem;"
                      f"align-items:flex-start'>" + "".join(halves) + "</div>")
    return "".join(blocks)


def _card_half(rows, wanted: int, title: str, accent: str, side: str) -> str:
    """One side's cards for one group, in its own half of the region.

    ⚠️ TWO ABSENCES, AND THEY ARE DIFFERENT SENTENCES (AC-G.11): a side missing its SECOND
    quarterback reserves the slot and names it; a side with none at all gets one block spanning
    the group, because naming a *first* quarterback that never existed invents the slot it is
    apologising for (R-856).
    """
    # 🚨 R-887. AN ENTIRELY EMPTY HALF UNDER A DRAWN HEADER IS THE HOLE AC-G.11 FORBIDS, AND
    # v11's SPANNING HEADER IS WHAT CREATED IT. A group is skipped only when NEITHER side has
    # rows; when ONE side has a punter and the other does not, the header draws across both and
    # the empty half was **blank — no card, no text, nothing a reader could tell from missing
    # data.** Measured before it was fixed: `leader-cards=0 reserved=0 text=''`.
    #
    # 📊 IT IS NOT AN EDGE CASE AT THE NEW DEPTH. **153 of 7,309 sides (2.1%) have no punting
    # row at all**, and at depth 1 "short" and "empty" are the same thing — which is why
    # Rushing and Receiving never needed this and Punter does.
    #
    # ⚠️ AND IT IS A RULE RATHER THAN A LIST, so the next group added cannot forget it. It is
    # deliberately NOT `_RESERVED_GROUPS`: that reserves a FIXED-HEIGHT slot to keep the two
    # columns' card counts in register (R-849), which is a different job from naming an absence.
    # **A sentence, not a held slot** — nothing below it needs the register, because these are
    # the last two groups. ⚠️ AND `_RESERVED_GROUPS` IS EXCLUDED EXPLICITLY: a side with no
    # quarterback gets R-856's block spanning both slots, which already names the absence and
    # holds the height. Letting this branch take that case replaced an 84px block with one line
    # and put every group below it out of register — caught by
    # `test_a_side_with_NO_QUARTERBACK_gets_ONE_block_and_NOT_a_FIRST_and_a_SECOND`.
    if not rows and title not in _RESERVED_GROUPS:
        return (f"<div data-cfdb='card-half' data-side='{side}' "
                f"style='flex:1;min-width:0'>"
                f"<div style='font-size:.7rem;opacity:.45;padding:.3rem 0'>"
                f"No {title.lower()} recorded.</div></div>")
    drawn = "".join(_leader_card(r, accent=accent) for r in rows)
    if title in _RESERVED_GROUPS and len(rows) < wanted:
        if rows:
            drawn += "".join(
                _reserved_card(f"No {_ORDINALS[index]} {title.lower()} recorded")
                for index in range(len(rows), wanted))
        else:
            drawn += _reserved_card(
                f"No {title.lower()} recorded for this side.", slots=wanted)
    # ⚠️ `data-side` IS AN INTERFACE. Away and home are two `flex:1` children of the same row,
    # and telling them apart by position in a regex over nested divs is the kind of helper that
    # answers wrongly (R-758). The attribute says which is which.
    return (f"<div data-cfdb='card-half' data-side='{side}' "
            f"style='flex:1;min-width:0'>{drawn}</div>")


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
    # 🚨 R-885. THE `st.subheader` IS GONE AND THE SECTION NAMES LIVE IN THE TABLE. Marc, v11:
    # *"one big continuous table … There should not be a block of whitespace that splits
    # Box/Advanced."* Two subheaders around two `st.columns` splits IS that whitespace — the
    # seam between Streamlit blocks — so removing it means having one block, and the names move
    # inside it where `_section_heading` gives each one Marc's bold rule.
    #
    # ⚠️ THE DATASET CAPTION STAYS WITH `states.section` AND THAT IS THE CHOICE THE ROUND MADE.
    # It names the RELATION the whole panel reads (`srv_game_team`), not a section of the table
    # — both sections come from that one read — so it belongs to the panel and renders once,
    # above the split. **Putting it under one of the two headings would have implied the other
    # section came from somewhere else.**
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
        # 🚨 R-885/R-886. ONE TABLE, BUILT AS ONE STRING, WRITTEN ONCE.
        #
        # **Marc, v11: *"Box Score and Advanced should be one big continuous table … There
        # should not be a block of whitespace that splits Box/Advanced."*** The two sections
        # used to be two `st.subheader` calls around two separate `st.columns` splits, and the
        # whitespace he is describing is the seam between those two Streamlit blocks — not a
        # margin this file sets. **Removing it means there is only one block.**
        parts = [
            _section_heading("Box score"),
            _table_header(away, home, "Box score", colors),
            # 🚨 ZERO DECIMALS FOR BOX SCORE, AND IT IS THE PANEL'S OWN NATURE RATHER THAN A
            # PREFERENCE: all six measures are integer counts — first downs, yards, attempts.
            # At `box()`'s old default of 1 every label read `22.0`, `5.0`, `38.0`, which is
            # precision the measure does not have.
            # ✅ B128: `dp_band=None` is *ask the column*, and `fmt.precision_for` answers 0
            # for all six — the same number this line used to state as a literal, now sourced
            # from the one table that owns the rule (Marc's v18, R-555).
            _comparison(away, home, _BOX_SCORE_ROWS, spread=spread, dp_band=None,
                        colors=colors),
            _custom_row(away, home, "Third down",
                        lambda r: _fraction(r, "third_down_conversions",
                                            "third_down_attempts")),
            _custom_row(away, home, "Fourth down",
                        lambda r: _fraction(r, "fourth_down_conversions",
                                            "fourth_down_attempts")),
            _custom_row(away, home, "Penalties",
                        lambda r: fmt.number(r.get("penalties"), dp=0)),
            _custom_row(away, home, "Turnovers (INT/FUM)", _turnovers),
            # ⚠️ POSSESSION, WHICH B076 REPORTED AS A SERVING GAP RATHER THAN WORKING AROUND.
            # It carried possession_seconds and nothing else, and 1,906 is not a figure to put
            # in front of a reader; dividing it into 31:46 is arithmetic in the page. A080
            # published possession_display, so the row exists and nothing here computes it.
            _custom_row(away, home, "Possession",
                        lambda r: r.get("possession_display") or fmt.EM_DASH),
        ]

        # ⚠️ A SEPARATE FLAG, SO A SEPARATE STATE. 72 of the 3,543 games that have a box score
        # do not have this block, and a section that silently vanished would be
        # indistinguishable from one that had never been written. **What changed in v11 is that
        # its absence no longer ends the panel** — the table is one continuous run, so Box
        # score stays drawn and only the second section reports itself missing.
        advanced = [r for r in played if bool(r.get("has_team_advanced"))]
        glossary, rows = None, []
        if len(advanced) >= 2:
            glossary = _postgame_glossary()
            rows = [r for r in _ADVANCED_ROWS
                    if r[1] != "defense_havoc_rate" or all(bool(s.get("has_havoc"))
                                                           for s in advanced)]
            parts += [
                # ✅ R-885. `Advanced Team Stats`, Marc's v11 name. His *"Advances"* is a typo.
                _section_heading(_ADVANCED_SECTION),
                _table_header(away, home, _ADVANCED_SECTION, colors),
                # ⚠️ ELEVEN OF THESE TWELVE ARE RATES BETWEEN 0 AND 1. At `box()`'s default of
                # 1 the quartiles COLLAPSE — a real week-1 passing-downs row goes p25 0.240 →
                # `0.2` and p75 0.433 → `0.4`, so a box spanning a fifth of the scale is
                # labelled as if it spanned two tenths. `dp=2` (R-829).
                # 🚨 **AND *ELEVEN OF TWELVE* IS THE WHOLE OF cfdb-wta-R-1153: THE TWELFTH IS
                # `Offensive plays`, AN INTEGER COUNT**, which this number drew as `40.00` for as
                # long as the band was flat. **It is a CEILING now** — `_comparison` takes the
                # lesser of it and the row's own precision — so the eleven keep their 2 and the
                # one that never wanted it prints integers.
                _comparison(away, home, rows, glossary, spread=spread, dp_band=2,
                            colors=colors),
            ]

        # 🚨 THE SPLIT HAPPENS ONCE, AFTER BOTH SECTIONS ARE BUILT. Two splits are what put the
        # cards in vertical register with each section, which is exactly what v11 dissolves.
        slots = _post_game_columns()
        slots["table"].markdown("".join(parts), unsafe_allow_html=True)
        # ⚠️ INSIDE THE TABLE COLUMN AND BEFORE THE `advanced < 2` RETURN BELOW, because the
        # Box score section draws charts too and that early exit would skip the sentence that
        # describes them (cfdb-wta-R-1159).
        note = _distribution_note(spread)
        if note:
            with slots["table"]:
                st.caption(note)
        # ⚠️ THE CARD REGION IS ONE BLOCK AND IS DRAWN ONCE — every group appears exactly once,
        # top to bottom, with no vertical association to the table beside it.
        slots["cards"].markdown(
            _post_game_cards(leaders, away, home, colors), unsafe_allow_html=True)

        if len(advanced) < 2:
            # ⚠️ INSIDE THE TABLE COLUMN, NOT FULL WIDTH — the absence belongs to the table's
            # second section, and a full-width empty state would read as the whole panel's.
            with slots["table"]:
                states.empty(
                    "The advanced figures would be here.",
                    "This game has a box score but no advanced breakdown — the two are "
                    "collected separately and one can arrive without the other.")
            table.as_of_caption(df)
            return

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
