"""Today — Looking Back. The weekly recap.

Front of house only. No pipeline, dbt, freshness or DQ content appears here (AC-1.7) — that
is System Overview's job, back of house.

WHAT THIS PAGE STOPPED BEING (R-428). It used to render an srv_game slate table, which
duplicated Schedule and answered a question Schedule answers better. The slate is not lost:
the link below routes to it. Today is now a recap of a COMPLETED week, and Looking Forward —
the week preview — is a later round and says so rather than showing an empty frame.

EVERY PANEL READS ONE SERVING VIEW AND DOES NO ARITHMETIC. The recap lists rank on columns
that already exist (`spread_favorite_side`, `moneyline_favorite_side`, `actual_margin`,
`favorite_covered`); the leaderboards order by a stored `stat_value`. Deriving a favorite or
a cover in Streamlit would be metric maths in the app, which is the rule those columns exist
to keep.
"""
import math

import altair as alt
import pandas as pd
import streamlit as st

from lib import filters, fmt, params, shell, states, tab, table
from lib.datasets import DATASETS
from lib.query import query
from lib.table import Col

# Model-derived framing is withheld before the week named here, which is
# `prediction_training_week_floor`. The
# recap is market-only until then and says which, rather than showing an empty model column.
MODEL_WEEK_FLOOR = 5

# A user radio rather than a constant, so the page never pulls a whole leaderboard table.
DEPTHS = (10, 25, 50)

POLLS = ("AP Top 25", "Coaches Poll")


# 🚨 WHAT "MOST EXCITING" ORDERS BY — R-709. ONE PLACE, NAMED, SO IT IS ONE LINE TO CHANGE.
#
# Marc, 2026-09-13, having looked at the old ordering: "Excitement index isn't going to cover it.
# OSU and Texas games are in the 6 range even. Need to factor in lead changes in the 4th qtr and
# swings in win probability."
#
# ⚠️ AND THE OLD ORDERING WAS NOT BAD AT THE TOP — IT WAS BAD IN THE TAIL, which is a different
# defect from the one the complaint sounds like. Measured on the 86 week-2 games that carry win
# probability, against the seven games Marc named as the acceptance test:
#
#     ordering                                          his 7 in top-10   worst rank
#     excitement_index desc            (what shipped)         4              31
#     lead_changes_fourth_quarter, then mean distance         4              21   <- this
#     mean distance late, then lead changes                   4              24
#     fourth-quarter WP range, then lead changes               3              21
#
# So every candidate puts four of his seven in the top ten and the choice is decided by the TAIL.
# Excitement buried Oklahoma @ Michigan at 31 of 86; this ordering has it 3rd. A117 measured the
# same game going from 17th to joint 1st on fourth-quarter lead changes alone.
#
# ✅ TWO COLUMNS WITH AN EXPLICIT TIE-BREAK, and the tie-break does real work rather than being
# decoration: fourth-quarter lead changes is a small integer (0 to 6 across the whole week), so
# ties are the common case and without a second key the order inside a tie is planner accident.
# `mean_distance_from_even_fourth_quarter_onward` breaks them by how close the game stayed, late —
# lower is closer.
#
# 🚨 NOT A COMPOSITE INDEX. A114, A115 and A117 all refused to build one and so does this: no
# weights, no scaling, no arithmetic. Two published columns and a documented precedence. The
# weighting is Marc's call and he has not made it — he will answer faster looking at this list
# than at another table.
#
# ⚠️ `nulls last` ON BOTH, because a game whose win-probability feed never reached the fourth
# quarter must not sort as if it were a dull one. Three games of 1,898 are in that state (A117).
# 🚨 A140, cfdb-main-R-916 — MIGRATE. THE SAME TWO KEYS, POINTED AT THE CORRECTED COLUMN.
#
# `lead_changes_fourth_quarter` counts win-probability crossings in the order the FEED lists the
# plays, and `stg_game_win_probability.play_number` is not chronological: 795 consecutive pairs
# step backwards on the clock across 336 of 1,898 games. `..._by_clock` counts the same crossings
# in the order the plays happened.
#
# ⚠️ THE WEIGHTING IS UNCHANGED AND IS NOT MINE TO CHANGE. Same two keys, same directions, same
# tie-break, same `nulls last`. Pointing an ordering at a corrected column is not a weighting
# change; adding or removing a key would be.
#
# 📊 AND THE TABLE ABOVE STILL HOLDS, which is worth stating rather than leaving to be assumed:
# **2026 week 2's top ten is IDENTICAL under both columns — same ten games, same order.** Across
# all 35 season-weeks the correction moves 2 games into the top ten and 2 out, in 2 weeks, and
# reorders 14 rows within it, in 3 weeks. Marc's Texas–Ohio State game does not move at all.
MOST_EXCITING_ORDER = ("lead_changes_fourth_quarter_by_clock desc nulls last, "
                       "mean_distance_from_even_fourth_quarter_onward asc nulls last, "
                       "game_id")


# --- data -----------------------------------------------------------------------------

# ⚠️ R-583. `DATASETS` MOVED TO `lib/datasets.py` AND IS IMPORTED, NOT DEFINED HERE.
#
# It was declared in this file by A089 and Matchup needs the same labels. Two tables naming
# the same views — `srv_game` and `srv_team_week` are read by both pages — would disagree, and
# preventing exactly that disagreement is what A089's design was for. The labels, the keys and
# the wording are unchanged by the lift; the module's own header carries the reasoning.

# (slug, label, panel names). THE SLUG IS WHAT GOES IN THE URL.
#
# ⚠️ ANCHORS, NOT `st.tabs`, AND R-283 IS WHY. Marc: "Clicking a sort while on Against The
# Line or Box Score resets the user to the Game Results tab." st.tabs keeps its selection
# client-side and never touches the URL, so every sort link rebuilds the page at the default
# tab. scores.py solved this first and B075 reused it for Matchup; this is the third page on
# the same pattern.
#
# ⚠️ AND ANCHORS ARE LAZY, WHICH ON THIS PAGE IS THE POINT RATHER THAN A SIDE EFFECT. Only
# the active tab's panels are called, so a reader who came to look forward does not pay for
# five backward panels' queries.
#
# Panels are NAMED rather than referenced so the laziness is testable: body() resolves each
# name out of the module at call time, and test_today_tabs.py asserts every name resolves to
# the real function rather than to a recorder.
TABS = (
    ("back", "Looking Back", ("_recap", "_movers", "_profile", "_leaderboards", "_bump")),
    ("forward", "Looking Forward", ("_looking_forward",)),
)


def _active_tab() -> tuple:
    """The tab the URL asks for, or the first. An unknown slug falls back rather than
    raising — a hand-edited `?tab=` is noise, not a request (AC-G.11)."""
    wanted = params.get("tab")
    for entry in TABS:
        if entry[0] == wanted:
            return entry
    return TABS[0]


def _tab_bar(active: str) -> None:
    """The same anchor bar scores.py and matchup.py draw, for the same reason (R-283).

    `params.link_here` preserves every known parameter, `tab` among them, so the week and
    conference filters survive a tab change and a sort link keeps the tab.
    """
    links = []
    for slug, label, _panels in TABS:
        css = "cfdb-tab" + (" cfdb-tab-on" if slug == active else "")
        links.append(f"<a class='{css}' href='{params.link_here(tab=slug)}' "
                     f"target='_self'>{label}</a>")
    st.markdown(f"<div class='cfdb-tabbar'>{''.join(links)}</div>",
                unsafe_allow_html=True)


def _completed_games(scope) -> pd.DataFrame:
    """Every completed game in scope. Feeds Most Exciting and all three recap lists.

    ⚠️ NO `--` COMMENTS INSIDE THE STRING. ci/check_page_queries.py and this page's own
    query test both flatten the SQL to a single line before running it, which turns a line
    comment into one that swallows every column after it — "syntax error at end of input",
    on a query that reads fine in the file. Notes about the select list go here.

    R-544. `actual_margin_home_perspective` is selected so the page can read the home side's
    own margin instead of negating the away one. See _favorite_margin for what that cost.

    R-545. `attribution` HAS BEEN ON srv_game ALL ALONG and this query did not ask for it, so
    attribution.model_attribution() took its "column missing from this view — this is a
    defect (AC-G.41)" branch and printed that sentence on the landing page. Every other view
    that calls that function selects the column; Today was the only one that did not. The
    message was right about itself and wrong about the view.

    🚨 A140, cfdb-main-R-916 — MIGRATE. THE FIVE `lag()`-DERIVED COLUMNS ARE READ FROM THEIR
    `..._by_clock` TWINS AND ALIASED BACK TO THEIR OLD NAMES.

    The feed's `play_number` is not chronological — 795 consecutive pairs step backwards on the
    clock across 336 of 1,898 games — so every column built from `lag()` over it counts crossings
    and swings that did not happen. Memphis at Georgia State publishes 25 lead changes; the game
    had 11.

    ⚠️ ALIASED RATHER THAN RENAMED THROUGHOUT, DELIBERATELY. The page's vocabulary is "lead
    changes", not "lead changes by clock": every `Col`, every filter and every caption downstream
    keeps working and keeps meaning what it says. **The alias is the migration; the five lines
    above are the only place a reader has to look to see which column is which.** When A141
    CONTRACTS the old ones the alias is what disappears.

    🚨 A139, cfdb-main-R-934. `home_abbreviation` IS SELECTED SO THE CURVE'S FINAL VALUE CAN NAME
    ITS SIDE. The bare percentage sat beside the AWAY team's name — the scoreboard puts away on
    the top line (R-522) — and told a reader the opposite of the truth while every label was
    correct. Null on 0 of the 1,895 games that can enter this panel, measured in serving.

    🚨 A138. `win_probability_curve_reaches_final_score` IS SELECTED BECAUSE THE CHART CANNOT
    BE HONEST WITHOUT IT. 99 of 1,898 curves stop before their game does (A136), and A138
    measured what a reader actually meets: 38 of 337 top-ten rows across 35 season-weeks, in 22
    of those weeks, two of them at #1. Without the flag the panel draws a line ending at 0.1%
    for a side that won 44-15 and nothing distinguishes it from a real collapse. ❌ SELECTING IT
    IS NOT RANKING ON IT — `MOST_EXCITING_ORDER` is untouched.

    ⚠️ R-558. `attribution` IS STILL SELECTED THOUGH body() NO LONGER CALLS
    model_attribution() — that is deliberate, not a leftover. See the note at the end of
    body(): attribution attaches to rendered model output, this page renders none yet, and
    keeping the column fetched makes restoring the call a one-line change on the day it does.
    """
    return query(f"""
        select game_id, season, week, season_type, game_date,
               home_team_display, away_team_display, home_team_slug, away_team_slug,
               home_abbreviation,
               home_logo_url, away_logo_url, home_conference, away_conference,
               home_points, away_points, actual_margin,
               actual_margin_home_perspective, excitement_index,
               spread_at_close, spread_current, spread_open, spread_move_from_open,
               favorite_covered, spread_favorite_side, moneyline_favorite_side,
               favorite_definitions_disagree,
               market_implied_home_win_probability, market_implied_away_win_probability,
               lead_changes_by_clock as lead_changes,
               largest_single_play_swing_by_clock as largest_single_play_swing,
               home_win_probability_range,
               lead_changes_fourth_quarter_by_clock as lead_changes_fourth_quarter,
               largest_single_play_swing_fourth_quarter_by_clock
                   as largest_single_play_swing_fourth_quarter,
               home_win_probability_range_fourth_quarter,
               lead_changes_overtime_by_clock as lead_changes_overtime,
               plays_with_win_probability_fourth_quarter,
               mean_distance_from_even_fourth_quarter_onward,
               win_probability_curve_reaches_final_score,
               home_q1, home_q2, home_q3, home_q4, home_overtime_points, home_periods,
               away_q1, away_q2, away_q3, away_q4, away_overtime_points, away_periods,
               attribution, as_of_ts
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and is_completed
          and (:division = 'all' or is_fbs_game)
          and (:conf is null or home_conference = :conf or away_conference = :conf)
        order by {MOST_EXCITING_ORDER}
        limit 400
    """, {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
          "conf": scope.conference, "division": scope.division})


def _team_yardage(scope, depth: int) -> pd.DataFrame:
    return query("""
        select team_display, team_slug, conference, opponent, week,
               total_yards, rushing_yards, passing_yards, points_for, result, as_of_ts
        from srv_team_game_log
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and is_completed
          and (:division = 'all' or classification = 'fbs')
          and (:conf is null or conference = :conf)
          and total_yards is not null
        order by total_yards desc, team_display
        limit {DEPTH}
    """.replace("{DEPTH}", str(int(depth))),
        {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
         "conf": scope.conference, "division": scope.division})


def _player_board(scope, depth: int, categories, stat_type: str) -> pd.DataFrame:
    """One leaderboard over srv_player_game_log.

    ⚠️ NO CLASSIFICATION COLUMN ON THIS VIEW, so `division` cannot be applied here the way it
    is on the team board — see the report. Conference still filters.
    """
    return query("""
        select player_name, player_slug, team, conference, opponent, week,
               stat_category, stat_type, stat_value, as_of_ts
        from srv_player_game_log
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and stat_type = :stat_type
          and stat_category = any(:cats)
          and (:conf is null or conference = :conf)
          and stat_value is not null
        order by stat_value desc, player_name
        limit {DEPTH}
    """.replace("{DEPTH}", str(int(depth))),
        {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
         "conf": scope.conference, "cats": list(categories), "stat_type": stat_type})


def _line_movement(scope) -> pd.DataFrame:
    """Every completed game in scope with its line-movement columns, ranked in the panel.

    ⚠️ NOT FILTERED TO GAMES THAT MOVED. The panel needs the games with NO snapshots in order
    to say how many it is not showing — a list that silently shortens is the fallback-at-100%
    defect, and the count is only knowable here. So this reads the scope and the panel does
    the ranking and the arithmetic of what it dropped.

    ⚠️ THERE ARE TEN `line_*` COLUMNS, NOT ELEVEN. A074's prompt and INDEX.md both say
    eleven; counted from published serving's information_schema on 2026-09-09 it is ten, and
    `line_snapshot_ts` is the tenth (not read here). The likely source of the miscount is that
    `srv_game` ALSO carries older unprefixed `spread_move_from_open` and `total_move_from_open`
    from before B070 — different columns with confusable names. The nine selected below are
    read as published; nothing here derives a movement figure.
    """
    return query("""
        select game_id, home_team_display, away_team_display,
               line_spread_largest_excursion, line_spread_move_from_open,
               line_total_largest_excursion, line_total_move_from_open,
               line_market_implied_win_probability_largest_excursion,
               line_market_implied_win_probability_move_from_open,
               line_snapshot_count, line_movement_spans_snapshot_gap,
               line_movement_provider_key, as_of_ts
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and is_completed
          and (:division = 'all' or is_fbs_game)
          and (:conf is null or home_conference = :conf or away_conference = :conf)
        order by game_id
        limit 400
    """, {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
          "conf": scope.conference, "division": scope.division})


def _yardage_profile(scope) -> pd.DataFrame:
    """One row per team, as the team stood ENTERING the week in scope. R-477.

    Reads srv_team_week, which is week grain — the whole reason R-476 exists. The season-grain
    srv_team_overview would answer the same question with a full season of yardage beside a
    September game, which is the defect Marc caught in the spec this round came from.

    The per-game columns are read AS PUBLISHED. Dividing here would be metric maths in the
    app; the view carries both the sums and the per-game figures for exactly that reason.
    """
    return query("""
        select team_id, team_display, team_slug, conference, week,
               games_counted,
               total_yards_for_per_game, total_yards_allowed_per_game,
               as_of_ts
        from srv_team_week
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and (:division = 'all' or is_fbs)
          and (:conf is null or conference = :conf)
        order by team_display
        limit 400
    """, {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
          "conf": scope.conference, "division": scope.division})


def _rankings(scope) -> pd.DataFrame:
    """Full season of AP and Coaches, for the bump chart and its companion table."""
    return query("""
        select season, week, poll_name, rank, team_display, team_slug,
               first_place_votes, points, as_of_ts
        from srv_rankings
        where season = :season and season_type = :season_type
          and poll_name = any(:polls)
        order by poll_name, week, rank
        limit 2000
    """, {"season": scope.season, "season_type": scope.season_type, "polls": list(POLLS)})


# --- panels ---------------------------------------------------------------------------

def _win_probability_curves(game_ids) -> pd.DataFrame:
    """Every plotted point for the games Most Exciting is showing, in ONE read.

    🚨 ONE QUERY, NOT TEN. Ten games times ~154 plays is about 1,540 rows — measured at 1,592
    for 2026 week 2 — which is one small read. A query per row would be ten round trips on a
    page that already runs several, and B099 established the shape for six cards' worth of
    dots: fetch the whole set keyed by id, then slice in the page.

    ⚠️ AC-G.39 — THE `limit` IS THE GRAIN RESTATED, NOT A GUESS. The grain is (game, play);
    ten games at the observed maximum of 255 plays is 2,550, so 4,000 is that bound with room
    for a longer game and is not a number chosen to look safe.

    🚨 IT USED TO ORDER BY `play_number` AND THIS DOCSTRING USED TO CALL THAT COLUMN THE
    POSITION AXIS — "monotonic, unique within a game, no restarts". **cfdb-main-R-916 measured
    that false.** Ordering each curve by `play_number`:

        consecutive regulation pairs stepping BACKWARDS on the clock      795
        games affected                                        336 of 1,898 (17.7%)
        worst single back-step                                    −3,567 seconds
        overtime games with overtime interleaved into regulation       10 of 70

    Game 401635615 carries fourth-quarter plays at `play_number` 0–3 and a first-quarter play
    at 4. Drawn on that axis its line crossed the whole width backwards, and every point on it
    was a real point.

    ✅ SO THE ORDER FOLLOWS THE COORDINATE THE CHART ACTUALLY DRAWS ON — A136's
    `elapsed_from_kickoff_seconds`, which is the clock.

    ⚠️ `nulls last` IS EXPLICIT RATHER THAN LOAD-BEARING, AND A140 CORRECTED THIS SENTENCE BY
    MEASURING IT. It used to say that without the clause "Postgres would sort overtime to the
    FRONT of the game"; a staged break removing it came back **GREEN**, because `ORDER BY x`
    ASCENDING already puts NULLs LAST in Postgres. It is DESC that puts them first — R-890's
    actual shape, and `MOST_EXCITING_ORDER` above is where that matters. ✅ The clause stays
    because it says out loud that the NULLs are overtime and belong at the end, so a round that
    later flips this to DESC has to edit it rather than overlook a comment.

    ⚠️ AND INSIDE AN OVERTIME PERIOD `play_number` IS THE ONLY ORDER A PLAY HAS —
    `stg_play`'s period-5-and-above rows take six distinct clock values in total — so it stays
    as the tie-break, which is exactly where it is still correct.

    ❌ NOT `play_id`: it is TEXT in this feed and not fixed width (A121 measured 5 to 18
    characters), so ordering on it is a lexical sort that scrambles play order while every row
    stays real.
    """
    if not len(game_ids):
        return pd.DataFrame()
    return query("""
        select game_id, play_number, period, is_overtime,
               elapsed_from_kickoff_seconds, overtime_period, overtime_axis_offset_periods,
               home_win_probability, home_score, away_score, play_text
        from srv_game_win_probability_play
        where game_id = any(:game_ids)
        order by game_id, elapsed_from_kickoff_seconds nulls last, play_number
        limit 4000
    """, {"game_ids": [int(g) for g in game_ids]})


# ── HOW DARK THE AXIS MARKS ARE, IN ONE PLACE (A138) ──────────────────────────────────────
#
# 🚨 MARC: "The axis marks need to be darker on the win probability chart." A122's precedent is
# exactly this class and it is the reason these are named rather than inlined: a band shaded at
# .07 was invisible, shipped looking finished, and .18 was chosen BY RASTERISING IT AT 4x AND
# LOOKING. A138 did the same and the before/after is in its report.
#
#     tick   .18 -> .32    quarter boundaries. The complaint.
#     major  (new) .55     halftime and the fourth quarter — Marc's own "(darker)"
#     zero   .35 -> .50    the even line, which is now the fill's baseline and carries more
#     fill   (new) .20     the area. Read at the same weight as the overtime band on purpose:
#                          neither may drown a tick, and the two are often adjacent.
_CURVE_TICK_OPACITY = .32
_CURVE_MAJOR_OPACITY = .55
_CURVE_ZERO_OPACITY = .50
_CURVE_FILL_OPACITY = .20
_CURVE_OT_SHADE_OPACITY = .18
_CURVE_OT_RULE_OPACITY = .8


# ── THE WIN-PROBABILITY CHART'S COORDINATE SYSTEM (A138, cfdb-main-R-905) ──────────────────
#
# 🚨 SHARED SCALE, NOT SHARED EXTENT, AND MARC'S TWO SENTENCES BOTH SURVIVE IT.
# "Y axis should be consistent across all rows" and "Games with overtime will be longer"
# cannot both hold if every chart is the same width — one of them has to give. They both hold
# if what is shared is the PIXELS PER SECOND: a quarter boundary lands at the same offset on
# every row, and an overtime game's chart is physically wider because it contains more game.
#
# 📊 A136 MEASURED THE ALTERNATIVE AND IT IS EXPENSIVE. Sizing every chart to the week's
# longest game spends 15.8-42.9% of a regulation chart's width on emptiness; in 2026 week 2 —
# the only week of 33 that reaches three overtimes — that is 84 charts paying for two.
_CURVE_REGULATION_UNITS = 3600          # seconds of regulation, and the axis unit itself
_CURVE_PX_PER_UNIT = 176.0 / 3600.0     # the SHARED SCALE. 176px of regulation, as before.
# ⚠️ ONE OVERTIME PERIOD IS DRAWN A QUARTER WIDE, AND THE NUMBER IS ARGUED RATHER THAN PICKED.
# A122's complaint was density: on the `play_number` axis Wake Forest at Purdue's 24 overtime
# plays occupied 20px of 180, about 0.8px a play against regulation's 1.0. A quarter's width is
# 44px, so those same 24 plays get 1.8px each — denser than regulation rather than sparser,
# which is the right way round for the part of the game that decided it.
_CURVE_OT_BAND_UNITS = 900
# ── ROOM AT THE RIGHT FOR THE FINAL LABEL, MEASURED RATHER THAN GUESSED (A139) ────────────
#
# 🚨 THE LABEL IS MONOSPACE ON PURPOSE, AND THAT IS WHAT MAKES ITS WIDTH A MEASUREMENT RATHER
# THAN A TABLE. A133 needed a per-character advance table for `distribution.py` because that
# text is proportional and `1` is not `8`. Setting this one in the same monospace stack every
# numeric column on the page already uses makes EVERY character the same width, so the whole
# question collapses to one number.
#
# 📊 MEASURED IN THE BROWSER at `font-size:9` in `ui-monospace,SFMono-Regular,Menlo,monospace`,
# via `getComputedTextLength()`: `M`, `i` and `%` all return **5.422px**, and `MICH 100%`
# returns 48.781 for nine characters — 5.4201 each. That uniformity IS the property being
# relied on, so it is recorded rather than assumed.
_CURVE_LABEL_CHAR_PX = 5.4219
# The gap between the last point and the first glyph, and a little air after the last one.
_CURVE_LABEL_OFFSET = 4.0
_CURVE_LABEL_TRAIL = 2.0
_CURVE_LABEL_FONT = "ui-monospace,SFMono-Regular,Menlo,monospace"


def _curve_axis_units(points: pd.DataFrame) -> pd.Series:
    """Where each play sits on the chart's x axis, in axis units.

    🚨 TWO PUBLISHED COORDINATES, NEVER ADDED AND NEVER COALESCED — A136 built them that way
    and asserted it in dbt:

        regulation   `elapsed_from_kickoff_seconds`, 0…3600. NULL for every overtime play.
        overtime     `overtime_axis_offset_periods`, in OVERTIME PERIODS. NULL in regulation.

    They are never both populated on one row (0 of 291,548) and they are in different units,
    so the overtime one is scaled onto this axis by ONE page constant — §4.2.1's permitted
    shape, the same one `sx`/`sy` have always been. Combining two published columns would not
    be.

    ⚠️ A PLAY WITH NO PERIOD HAS NO POSITION ON A CLOCK AXIS, and gets NaN here rather than a
    guess. Exactly one play of 291,548 is in that state — the one with no `stg_play` match —
    and it is dropped from the line rather than placed somewhere it was not. AC-G.32: an
    unknown is not a zero and is not the end of the game.
    """
    elapsed = pd.to_numeric(points["elapsed_from_kickoff_seconds"], errors="coerce")
    offset = pd.to_numeric(points["overtime_axis_offset_periods"], errors="coerce")
    return elapsed.where(
        elapsed.notna(),
        _CURVE_REGULATION_UNITS + offset * _CURVE_OT_BAND_UNITS)


_CURVE_PAD = 2


def _curve_final_value(points: pd.DataFrame):
    """The home win probability at the LAST PLOTTED play, or None.

    ⚠️ "Last plotted" rather than "last row": a play with no period has no position on a clock
    axis and is dropped from the line, so the label has to read the same filtered frame the
    curve does or it would name a point that is not on the chart.
    """
    if points is None or points.empty:
        return None
    plotted = points[_curve_axis_units(points).notna()]
    if plotted.empty:
        return None
    value = plotted["home_win_probability"].iloc[-1]
    return None if pd.isna(value) else float(value)


def _curve_label(row, points) -> tuple:
    """`(text, is_cut)` for the mark at the end of the curve. ONE definition, two consumers.

    🚨 cfdb-main-R-934. THE LABEL USED TO BE A BARE PERCENTAGE AND IT SAT BESIDE THE WRONG TEAM'S
    NAME. Row 1 of 2026 week 2 read `IOWA STATE … / IOWA …` with `94%` against it — and the 94%
    is IOWA's, the HOME side, while the scoreboard deliberately puts the AWAY team on the top
    line (R-522). Every label was correct and the panel still told a reader the opposite of the
    truth. ⚠️ The `aria-label` already said *"Home win probability"*, so a screen-reader user was
    told which side it was and a sighted reader was not — an inversion of the usual failure.

    ✅ THE FIX IS THE HOME SIDE'S ABBREVIATION IN FRONT OF THE NUMBER, and the other two
    candidates were rejected for reasons rather than taste:

        label the WINNER          ❌ DISQUALIFIED BY THE GEOMETRY. The curve is home-perspective
                                  and the label sits at the last point's own height, so when the
                                  away side won the number would read 96% while sitting at the
                                  BOTTOM of the chart, where the home curve ended at 4%. A label
                                  that contradicts its own position is worse than a bare one.
        anchor it to the home row ❌ Moves the label away from the point it labels, and vertical
                                  alignment is not something a reader decodes as "this is the
                                  home team's number" while scanning ten rows.
        the abbreviation          ✅ Same glyph run as the number, so it survives greyscale and
                                  thumbnailing; agrees with the geometry (above the even line is
                                  home); and agrees with the `aria-label`, which now names the
                                  team rather than the role.

    📊 COVERAGE MEASURED IN PUBLISHED SERVING RATHER THAN ASSUMED: `home_abbreviation` is null on
    **0 of the 1,895 games that can enter this panel**, longest **4 characters**, mean 3.3. It is
    null on 4.9% of `srv_game` as a whole and reaches 9 characters on 22 rows there, none of
    which can be ranked here. ⚠️ A130's chain ends in "drop the suffix rather than print `None`";
    the same applies — with no abbreviation the label falls back to the bare percentage, and the
    `aria-label` still names the side.

    ⚠️ THE CUT CASE KEEPS ITS OWN SHAPE. There is no value to attribute to anybody, so it stays
    the single word and does not grow a team name in front of it.
    """
    reaches = row.get("win_probability_curve_reaches_final_score")
    if not (bool(reaches) if pd.notna(reaches) else True):
        return ("cut", True)
    final = _curve_final_value(points)
    if final is None:
        return ("", False)
    side = row.get("home_abbreviation")
    side = None if side is None or pd.isna(side) else str(side).strip()
    percent = f"{final * 100:.0f}%"
    return ((f"{side} {percent}" if side else percent), False)


def _curve_bands(points: pd.DataFrame) -> int:
    """How many overtime periods this game's curve spans. 0 for a regulation game."""
    if points is None or points.empty or "overtime_period" not in points:
        return 0
    periods = pd.to_numeric(points["overtime_period"], errors="coerce")
    return int(periods.max()) if periods.notna().any() else 0


def _curve_width(points: pd.DataFrame, label: str = "") -> int:
    """This game's chart width in pixels, at the shared scale, including room for its label.

    🚨 THE PANEL NEEDS THIS BEFORE IT RENDERS ANY ROW, which is why it is its own function.
    `.cfdb-table` is `table-layout:fixed`: with no colgroup every column takes an equal share,
    and a chart that is wider than its share overflows the cell rather than shrinking. Reading B
    makes the charts differ in width on purpose, so the column has to be the widest of them —
    and that is a fact about the FRAME, not about any one row.

    ⚠️ A139 MADE THE GUTTER DEPEND ON THE LABEL RATHER THAN ON A CONSTANT, because naming the
    home side made the label variable. A fixed gutter would have had to be sized for the longest
    label the data can produce — 9 characters plus " 100%" is 76px — and would have spent that on
    every chart on the page forever. Sized per row it costs what it costs: `MICH 100%` is 55px
    against the old constant's 30, and a `cut` row is 23 and gets NARROWER.
    """
    span = _CURVE_REGULATION_UNITS + _curve_bands(points) * _CURVE_OT_BAND_UNITS
    gutter = (_CURVE_LABEL_OFFSET + len(label) * _CURVE_LABEL_CHAR_PX + _CURVE_LABEL_TRAIL
              if label else _CURVE_LABEL_TRAIL)
    return int(round(_CURVE_PAD * 2 + span * _CURVE_PX_PER_UNIT + gutter))


def _sparkline_svg(points: pd.DataFrame, label: str = "", is_cut: bool = False,
                   height: int = 44) -> str:
    """One game's win-probability curve, as inline SVG sized for a table cell.

    🚨 A CHART CANNOT LIVE INSIDE `table.render`, WHICH IS WHY THIS IS SVG AND NOT ALTAIR.
    `table.render` emits HTML and `st.altair_chart` is a Streamlit call; a cell cannot contain
    one. ⚠️ A138 RE-ASKED THIS RATHER THAN INHERITING IT, because the scoreboard change could
    have moved the container — and the answer is unchanged, because the container did not move.
    The scoreboard became one CELL of the same table, not a replacement for it, so the ten
    games still sit side by side in one grid and a sparkline is still the only mark that keeps
    that. ⚠️ `_scatter_svg` in this same file is the precedent: hand-drawn inline SVG in
    `currentColor`.

    🚨 THE X AXIS IS THE ELAPSED CLOCK, AND IT USED TO BE `play_number`. The docstring this
    replaces said `play_number` was "monotonic, unique within a game, no restarts" — and
    cfdb-main-R-916 measured that false: **795 consecutive pairs step BACKWARDS on the clock,
    across 336 of 1,898 games (17.7%)**, worst single back-step −3,567 seconds. Game 401635615
    has fourth-quarter plays at `play_number` 0–3 and a first-quarter play at 4, so its line
    crossed the whole width backwards with every point real. A comment asserting a property the
    warehouse does not have is worse than no comment, because the next reader trusts it.

    ⚠️ ORDER FOLLOWS THE COORDINATE, NOT `play_number` — see `_win_probability_curves`. Inside
    an overtime period `play_number` is the only order a play has, and there it is still used.

    🚨 THE COORDINATE MAPPING BELOW IS ARITHMETIC IN A PAGE FILE, AND IT IS NOT R-611's CLASS.
    §4.2.1's test is HOW MANY CONSUMERS A NUMBER CAN HAVE: `sx`/`sy` turn an axis position and
    a probability into pixel offsets inside this one <svg>, and a pixel offset is not a quantity
    anybody can cite, export, sort on or disagree with. ✅ THE SAME GOES FOR THE SIGNED AXIS.
    Marc asked for −1…1; the published column is 0…1 and the transform is `2p − 1`. That is a
    COORDINATE, not a fact about football — nobody can export "the home side was at +0.42" —
    so it lives here beside `sx`/`sy` rather than in dbt.

    📊 AND THE SIGNED AXIS CHANGES NO PIXEL, WHICH IS WORTH SAYING PLAINLY RATHER THAN LETTING
    A READER ASSUME OTHERWISE: `sy` already mapped an ABSOLUTE 0…1 onto the full height, so the
    y axis was ALREADY consistent across rows and 2p−1 onto −1…1 is the identical mapping. What
    actually changes is that the mid line is now ZERO and the curve is FILLED FROM IT — which is
    the point. Fill from zero makes the SIGN the picture, and above-or-below-zero is POSITION,
    so it survives greyscale (AC-G.22). The fill is decoration on a signal that already works
    without it — A131's argument for the two-sided box, one panel over.

    ⚠️ `sy` FLIPS AND MUST KEEP FLIPPING — SVG y grows downward and a home side at 1.0 belongs
    at the top. `_scatter_svg` in this same file deliberately does not flip and says why; the
    two sit in one file, so each states which it is.

    ❌ NO SMOOTHING, NO INTERPOLATION, NO ROLLING AVERAGE — every published point is plotted.
    The spikes ARE the drama and this panel exists to show them; a smoothed win-probability
    curve is a different claim about the game, and an AREA chart of a smoothed curve is the same
    different claim with more ink on it.
    """
    if points is None or points.empty:
        return fmt.EM_DASH

    pad = _CURVE_PAD
    units = _curve_axis_units(points)
    plotted = points.assign(_x_units=units)
    plotted = plotted[plotted["_x_units"].notna()]
    if plotted.empty:
        return fmt.EM_DASH

    # THE WIDTH IS THE GAME'S OWN LENGTH AT THE SHARED SCALE. A regulation game ends at 3600
    # units; each overtime period adds a band. Nothing is padded out to match another row.
    bands = _curve_bands(plotted)
    span_units = _CURVE_REGULATION_UNITS + bands * _CURVE_OT_BAND_UNITS
    width = _curve_width(plotted, label)
    ph = height - 2 * pad

    def sx(axis_units) -> float:
        return pad + float(axis_units) * _CURVE_PX_PER_UNIT

    def sy(probability) -> float:
        # −1…1 with zero in the middle, which is arithmetically the same mapping 0…1 had.
        return pad + (1.0 - float(probability)) * ph

    right = sx(span_units)
    zero = sy(0.5)
    parts = []

    # ── REFERENCE LINES ───────────────────────────────────────────────────────────────────
    #
    # 🚨 MARC NAMED FIVE REGULATION MARKS AND THE CLOCK HAS FOUR BOUNDARIES. "Start, 2nd, half,
    # 3rd, 4th" is what a broadcast shows, where halftime is an INTERVAL and the third quarter
    # begins after it. On an elapsed-clock axis "half" and "3rd" ARE THE SAME INSTANT — 1800
    # seconds — so five names map to four distinct quarter starts:
    #
    #     Start          0      kickoff
    #     2nd          900      the second quarter begins
    #     half / 3rd  1800      halftime AND the third quarter, one line carrying both names
    #     4th         2700      the quarter this panel's whole ordering is about
    #     (end)       3600      regulation ends; where overtime begins if there is any
    #
    # ✅ SO FIVE MARKS ARE DRAWN, NOT FOUR, and the fifth is the end of regulation rather than
    # an invented boundary. Marc's "Final" is the labelled end of the curve, below.
    #
    # ⚠️ AND THE EMPHASIS IS MARC'S OWN — "half (darker)", "4th (full, darker)". 1800 carries
    # two of his names and 2700 opens the quarter this panel ranks on, so those two are the
    # heavy ones.
    for at_units, weight, opacity in ((0, .5, _CURVE_TICK_OPACITY),
                                      (900, .5, _CURVE_TICK_OPACITY),
                                      (1800, .9, _CURVE_MAJOR_OPACITY),
                                      (2700, 1.1, _CURVE_MAJOR_OPACITY),
                                      (3600, .5, _CURVE_TICK_OPACITY)):
        if at_units > span_units:
            continue
        x = sx(at_units)
        parts.append(f"<line x1='{x:.1f}' y1='{pad}' x2='{x:.1f}' y2='{height - pad}' "
                     f"stroke='currentColor' stroke-width='{weight}' "
                     f"opacity='{opacity}'></line>")

    # ── OVERTIME: A SHADED BAND AND A HEAVY DIVIDER PER PERIOD ────────────────────────────
    #
    # ⚠️ SHADED FIRST, SO IT SITS UNDER THE LINE. A118 measured Jacksonville State at Ohio: TWO
    # fourth-quarter lead changes and ELEVEN in overtime. On an unmarked curve that reads as one
    # very long fourth quarter — the drama attributed to the wrong part of the game, with every
    # point still real.
    #
    # 🚨 THE DIVIDER IS PER PERIOD NOW, NOT ONE AT THE START OF OVERTIME. Each overtime period
    # has its own band and its own boundary, because each resets the clock and alternates
    # possession. A136 proved the arithmetic that makes this land exactly: the reference line
    # for overtime k falls on offset k − 1, so it sits exactly on the band edge.
    if bands:
        ot_start = sx(_CURVE_REGULATION_UNITS)
        parts.append(f"<rect x='{ot_start:.1f}' y='{pad}' "
                     f"width='{right - ot_start:.1f}' height='{ph}' "
                     f"fill='currentColor' opacity='{_CURVE_OT_SHADE_OPACITY}'></rect>")
        for band in range(bands):
            x = sx(_CURVE_REGULATION_UNITS + band * _CURVE_OT_BAND_UNITS)
            # ⚠️ DELIBERATELY HEAVIER THAN A QUARTER TICK. Overtime is a different KIND of
            # boundary from a quarter change and must not read as one more tick.
            parts.append(f"<line x1='{x:.1f}' y1='{pad}' x2='{x:.1f}' y2='{height - pad}' "
                         f"stroke='currentColor' stroke-width='1.4' "
                         f"opacity='{_CURVE_OT_RULE_OPACITY}'></line>")

    # ── ZERO. The only reference point on the whole picture, and now the fill's baseline. ──
    parts.append(f"<line x1='{pad}' y1='{zero:.1f}' x2='{right:.1f}' y2='{zero:.1f}' "
                 f"stroke='currentColor' stroke-width='.6' "
                 f"opacity='{_CURVE_ZERO_OPACITY}' stroke-dasharray='2 2'></line>")

    # ── THE CURVE ─────────────────────────────────────────────────────────────────────────
    #
    # 🚨 STILL BROKEN AT EVERY OVERTIME BOUNDARY, AND A138 RE-DECIDED IT RATHER THAN INHERITING
    # IT. The original reason was density — `play_number` compressed overtime into a 20px sliver
    # and a wash was not legible — and the new coordinate removes that reason: overtime now
    # starts exactly where regulation ends and gets a quarter's width. ✅ THE OTHER REASON
    # STANDS ON ITS OWN AND IS WHY THE BREAK SURVIVES: overtime IS discontinuous football. The
    # clock resets, possession alternates, and the curve genuinely does not continue from the
    # fourth quarter's last play. A filled area that ran straight through would draw one
    # continuous game where there were two.
    #
    # ⚠️ AND NO POINT MOVES TO ACHIEVE IT. A stroke weight is a rendering property; a coordinate
    # is a claim about when something happened.
    #
    # ⚠️ `is True` RATHER THAN TRUTHINESS. A null `is_overtime` is UNKNOWN: read as regulation it
    # would draw a break that did not happen, read as overtime it would suppress the real one.
    # Compared this way it does neither — it never triggers a transition. AC-G.32.
    # ONE PASS, carrying the previous play's band — not a lookup per point. The first draft
    # re-filtered the frame for every play, which is the O(n^2) shape A097 and A120 both paid for.
    segments, current, previous_band = [], [], None
    for axis_units, probability, in_overtime, ot_period in zip(
            plotted["_x_units"], plotted["home_win_probability"],
            plotted["is_overtime"], plotted.get("overtime_period", plotted["_x_units"] * 0)):
        now_overtime = in_overtime is True or in_overtime == 1
        band = int(ot_period) if (now_overtime and pd.notna(ot_period)) else 0
        if band != previous_band and previous_band is not None and current:
            segments.append(current)
            current = []
        current.append((sx(axis_units), sy(probability)))
        previous_band = band
    segments.append(current)

    for index, coords in enumerate(segments):
        if len(coords) < 2:
            continue
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        # THE AREA, FILLED FROM ZERO. One closed path down to the baseline at each end: the
        # lobes above and below fill on their own sides, so the sign is the shape.
        area = (f"M{coords[0][0]:.1f},{zero:.1f} "
                + " ".join(f"L{x:.1f},{y:.1f}" for x, y in coords)
                + f" L{coords[-1][0]:.1f},{zero:.1f} Z")
        parts.append(f"<path d='{area}' fill='currentColor' "
                     f"opacity='{_CURVE_FILL_OPACITY}' stroke='none'></path>")
        is_overtime_segment = index > 0
        parts.append(
            f"<polyline points='{line}' fill='none' stroke='currentColor' "
            f"stroke-width='{1.8 if is_overtime_segment else 1.1}' "
            f"opacity='{1.0 if is_overtime_segment else 0.85}'></polyline>")

    # ── THE FINAL VALUE, AND THE ONE ABSENCE THAT MATTERS (AC-G.11) ───────────────────────
    #
    # 🚨 99 OF 1,898 CURVES NEVER REACH THEIR OWN GAME'S FINAL SCORE — CFBD's feed truncates,
    # and `srv_game.win_probability_curve_reaches_final_score` says which. A136 measured the
    # consequence and A138 measured how often a reader would actually meet it: **38 of 337
    # top-ten rows across 35 season-weeks, in 22 of those weeks, including two #1 rows.** This
    # is not a defensive branch; it is one row in nine.
    #
    # ❌ SO A TRUNCATED CURVE IS NOT LABELLED WITH A FINAL VALUE, because the number is not one.
    # Coastal Carolina at UTSA ends at 0.1% for a side that won 44-15; printing "0%" beside it
    # would be a confident wrong number a reader cannot tell from a real collapse.
    # ✅ IT IS STILL DRAWN — the first four fifths of the curve are real and dropping them would
    # lose more than it protects — and the end of the line is cut with a dashed rule and the word
    # so the absence says WHICH absence it is.
    last_x, last_y = segments[-1][-1] if segments and segments[-1] else (right, zero)
    # ⚠️ CLAMPED INTO THE BOX. A game that ends at 100% puts its last point on the top edge, and
    # a baseline placed 3px below it still hangs the glyphs above the viewBox — where they are
    # clipped by the cell, not by the SVG, so it looks like a rendering bug. Found by rasterising.
    label_y = min(max(last_y + 3.0, pad + 7.0), height - pad - 1.0)
    if is_cut:
        parts.append(f"<line x1='{last_x:.1f}' y1='{pad}' x2='{last_x:.1f}' "
                     f"y2='{height - pad}' stroke='currentColor' stroke-width='1' "
                     f"opacity='.5' stroke-dasharray='1 2'></line>")
        described = ("Win probability by play, home side; the feed stops before the end of the "
                     "game, so there is no final value")
    else:
        described = (f"Win probability by play, home side, ending at {label}" if label
                     else "Win probability by play, home side")
    if label:
        # 🚨 MONOSPACE, AND IT IS NOT A STYLE CHOICE — see `_CURVE_LABEL_CHAR_PX`. Every glyph
        # is 5.4219px wide at this size, which is what lets `_curve_width` size the gutter
        # exactly rather than from an advance table. It also matches `.cfdb-num`, so the label
        # reads as one more figure on a page of figures.
        parts.append(f"<text x='{last_x + _CURVE_LABEL_OFFSET:.1f}' y='{label_y:.1f}' "
                     f"font-size='9' font-family='{_CURVE_LABEL_FONT}' "
                     f"fill='currentColor' opacity='.75'>{label}</text>")

    return (f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}' "
            f"role='img' aria-label='{described}' "
            f"style='display:block'>{''.join(parts)}</svg>")


def _quarter_cells(row, side: str):
    """One team's score by quarter, as (column label, value) pairs — or None if unknown.

    🚨 AC-G.32 IS THE WHOLE JOB HERE, AND THE THREE CASES LOOK IDENTICAL IF YOU ARE NOT CAREFUL:

        a quarter that was PLAYED and scoreless     0
        a quarter that was NEVER PLAYED             ABSENT — no pair is emitted for it at all
        a quarter whose score we do not HAVE        an em dash in that position

    A line reading `7 0 3 0` says the team was shut out in two quarters. A line reading
    `7 0 3` says the game had three quarters. Printing four values with zeroes for the missing
    ones would invent two shut-out quarters; printing a BLANK for both "never played" and
    "we do not know" collapses two different facts into one.

    ⚠️ `home_periods` / `away_periods` IS WHAT TELLS THEM APART, and it is the reason this
    function takes a side rather than assuming four. A game with 4 periods has no fifth column;
    a game with 5 or more has overtime, with a real number in it.

    🚨 AND OVERTIME IS LABELLED, NEVER FOLDED INTO THE FOURTH QUARTER — A117's lesson applied to
    the display. Jacksonville State @ Ohio had TWO fourth-quarter lead changes and ELEVEN in
    overtime. A scoreboard that added the overtime points onto Q4 would tell the reader the
    drama happened in a quarter where it did not, and every number on the line would still be a
    real number.

    ⚠️ ONE OVERTIME COLUMN, NOT ONE PER PERIOD, AND THAT IS THE DATA'S SHAPE RATHER THAN A
    CHOICE: `{side}_overtime_points` is a single total. A game in the panel reaches as many as
    twelve periods — eight overtimes — and there is no per-overtime breakdown published to draw.

    📊 A138 SPLIT THIS OUT OF `_quarter_line`, WHICH IS NOW RETIRED. That function joined these
    same values into one string with ` &middot; ` separators and had exactly one caller — the two
    by-quarter columns the scoreboard absorbed. It is deleted rather than left unused: a page
    helper nothing calls is a helper the next reader has to prove is dead.

    ⚠️ AND THE DEFECT IT CARRIED A FIX FOR CANNOT RECUR IN A GRID, WHICH IS WHY DELETING IT IS
    SAFE. Its first version joined with `&nbsp;&middot;&nbsp;`, making a five-period line ONE
    unbreakable run: it did not fit the column, and a browser with nowhere legal to break broke
    mid-word instead — Wake Forest at Purdue rendered as `7 · 10 · 3 · 3 · O` / `T 15`, the wrap
    landing inside the word "OT". ✅ In the scoreboard every value is its own `<td>`, so there is
    no run to break and the fix is structural rather than typographic.
    """
    periods = row.get(f"{side}_periods")
    if periods is None or pd.isna(periods):
        return None
    periods = int(periods)

    pairs = []
    for quarter in range(1, min(periods, 4) + 1):
        value = row.get(f"{side}_q{quarter}")
        pairs.append((str(quarter),
                      fmt.EM_DASH if value is None or pd.isna(value) else f"{int(value)}"))

    if periods >= 5:
        overtime = row.get(f"{side}_overtime_points")
        pairs.append(("OT", fmt.EM_DASH if overtime is None or pd.isna(overtime)
                      else f"{int(overtime)}"))
    return pairs


def _scoreboard(row) -> str:
    """One game as a scoreboard: away over home, quarter by quarter, final at the right.

    > **MARC:** *"Can you present each row like a scoreboard, Away over Home, each quarter, then
    > final score, followed by the chart. Sorting moves the games, not the rows within the
    > game."*

    🚨 THE SECOND SENTENCE IS A GRAIN STATEMENT, NOT A PREFERENCE, AND IT IS WHY THIS IS ONE
    CELL RATHER THAN TWO ROWS OF THE OUTER TABLE. The sort key is the GAME. Away-over-home is
    fixed INSIDE it and never participates in a sort — and building it as a nested table makes
    that structurally impossible rather than merely intended: `table.render` sorts the outer
    frame, and there is no column on it whose ordering can reach inside a cell. R-522's
    away-over-home law, which B082 and B083 both proved a presence assertion cannot see.

    ✅ AND IT IS WHY THE CHART IS STILL SVG. The scoreboard became one CELL of the same table,
    not a replacement for it, so ten games still sit side by side in one grid and the constraint
    that forced inline SVG is unchanged. A138 re-asked that question rather than inheriting the
    answer; see `_sparkline_svg`.

    📊 ONE HEADER ROW SERVES BOTH SIDES, AND THAT IS MEASURED RATHER THAN ASSUMED: `home_periods`
    and `away_periods` differ on **0 of 109,739 completed games**. Where they somehow did, each
    side emits its own cells and the shorter one is simply shorter — which is `_quarter_cells`'s
    "never played" state reading correctly rather than a ragged table reading wrongly.

    ⚠️ THE TEAM NAMES LIVE HERE NOW. This cell absorbs what were four columns — the matchup, the
    final score, and the two by-quarter lines — so nothing was dropped to make room for it.
    """
    away_pairs = _quarter_cells(row, "away")
    home_pairs = _quarter_cells(row, "home")
    labels = [label for label, _ in (away_pairs or home_pairs or [])]

    def side_row(name, points, pairs, css):
        """One line of the scoreboard, with AC-G.32's three states as three different cells.

        ⚠️ THE GRID HAS TO CARRY THE SAME THREE STATES THE STRING DID, and a blank cell is only
        ONE of them:

            `0`        played and scoreless
            blank      that side has no such period — the column exists because the OTHER side
                       reports it. Never observed: `home_periods` and `away_periods` differ on
                       0 of 109,739 completed games, so this is the unreachable branch
            em dash    we do not have the number. `pairs is None` means no period count at all,
                       so the WHOLE line is em dashes rather than blanks — blanking it would say
                       the game had no quarters
        """
        cells = [f"<th scope='row' class='cfdb-sb-team'>{name}</th>"]
        for index in range(len(labels)):
            if pairs is None:
                value = fmt.EM_DASH
            elif index < len(pairs):
                value = pairs[index][1]
            else:
                value = ""
            cells.append(f"<td>{value}</td>")
        final = fmt.EM_DASH if points is None or pd.isna(points) else f"{int(points)}"
        cells.append(f"<td class='cfdb-sb-final'>{final}</td>")
        return f"<tr class='{css}'>{''.join(cells)}</tr>"

    # ⚠️ THE HEADER'S FIRST CELL CARRIES THE TEAM CLASS THOUGH IT HOLDS NOTHING. Under
    # `table-layout:fixed` the browser takes every column's width from the FIRST row, so an
    # unclassed corner cell leaves the name column to be guessed and the grid stops lining up
    # down the page — which is the defect the fixed layout is there to fix.
    head = ("<tr><td class='cfdb-sb-team'></td>"
            + "".join(f"<th scope='col'>{label}</th>" for label in labels)
            + "<th scope='col' class='cfdb-sb-final'>F</th></tr>")
    # AWAY FIRST, ALWAYS. The order of these two lines is the law, not a default.
    body = (side_row(row.get("away_team_display"), row.get("away_points"), away_pairs,
                     "cfdb-sb-away")
            + side_row(row.get("home_team_display"), row.get("home_points"), home_pairs,
                       "cfdb-sb-home"))
    return (f"<table class='cfdb-scoreboard'><thead>{head}</thead>"
            f"<tbody>{body}</tbody></table>")


def _espn_link(row) -> str:
    """A link out to ESPN's commentary for this game.

    ✅ THE KEY WAS VERIFIED BY HAND BEFORE THIS SHIPPED, ON THREE GAMES, AND IT IS WORTH
    SAYING WHY THREE. CFBD's `game_id` being ESPN's event id is widely believed and had never
    been established here. A wrong id does not fail — it serves a DIFFERENT GAME, which on a
    page Marc is making presentable is worse than no link at all. One match could be
    coincidence; three of three with the scores agreeing is not.

        401856679  ->  Oklahoma Sooners 10 at Michigan Wolverines 17      (ours: 10 at 17)
        401856682  ->  Ohio State Buckeyes 23 at Texas Longhorns 24       (ours: 23 at 24)
        401866418  ->  Jacksonville State Gamecocks 27 at Ohio Bobcats 29 (ours: 27 at 29)

    Teams, home/away sides AND final scores matched on all three, and all three gamecast URLs
    returned HTTP 200.

    ⚠️ EXTERNAL, AND IT HAS TO READ AS EXTERNAL. `target="_blank"` plus the arrow, because a
    reader who clicks this is leaving the site and should know before they click.
    `rel="noopener noreferrer"` because a new tab opened from our page would otherwise get a
    handle back to it.

    ⚠️ AND THIS COLUMN CANNOT COEXIST WITH A ROW LINK ON THIS TABLE. `table.render` wraps a
    cell's content in the row's anchor when there is one, and nested anchors are invalid HTML
    with the outer one winning — the reader would click "ESPN" and stay on the site. That is
    the same trap `Col.link`'s own comment names. This table deliberately passes no
    `link_builder`.
    """
    game_id = row.get("game_id")
    if game_id is None or pd.isna(game_id):
        return fmt.EM_DASH
    return (f"<a href='https://www.espn.com/college-football/game/_/gameId/{int(game_id)}' "
            "target='_blank' rel='noopener noreferrer'>ESPN &nearr;</a>")


def _most_exciting(df: pd.DataFrame, scope) -> None:
    st.subheader("Most exciting")
    st.caption(
        "Ranked by **lead changes in the fourth quarter**, then by how close the game stayed "
        "after it — not by CFBD's excitement index, which ranked the week's best "
        "fourth quarter 31st of 86. Each scoreboard reads away over home, quarter by "
        "quarter, with overtime shown separately and the final at the right. The chart "
        "is the home side's win probability on every play against the game clock, "
        "unsmoothed and filled from even — above the line the home side was ahead, below "
        "it the away side was. Quarter marks fall at the same place on every chart, so a "
        "game that went to overtime is simply longer. A cut line at the end means CFBD's "
        "feed stopped before the game did, so there is no final value to show. "
        "Source: [CollegeFootballData.com](https://collegefootballdata.com); commentary links "
        "go to ESPN.")
    # ⚠️ THE ROWS ARRIVE IN ORDER. `_completed_games` orders by MOST_EXCITING_ORDER, so the
    # page does not sort and does not compute — §4.2. Changing what "most exciting" means is
    # one edit to that constant and nothing here moves.
    #
    # ⚠️ FILTERED ON THE COLUMN IT RANKS ON, not on excitement_index. A game whose
    # win-probability feed never reached the fourth quarter cannot be placed in this ordering
    # at all, and showing it at the bottom would say it was dull rather than unmeasured.
    top = df[df["lead_changes_fourth_quarter"].notna()].head(10)

    # ONE READ for every curve on the panel, then sliced per row. See _win_probability_curves.
    #
    # ⚠️ ITS OWN `states.section`, AND NOT ONLY TO SATISFY THE GUARD THAT NAMES EVERY VIEW A
    # MODULE READS. The curve is a SECOND view behind this panel, and it is the supplementary
    # one: if `srv_game_win_probability_play` has not been published, the ranking, the quarter
    # scoreboard and the ESPN links are all still correct and worth showing. Degrading the
    # column rather than the panel is R-748's rule — assert upstream, degrade downstream —
    # applied to a page rather than to a chart helper.
    #
    # `curves` is bound BEFORE the block because `section` swallows the exception and the code
    # below still runs; an unbound name there would turn a handled degradation into a crash.
    curves = pd.DataFrame()
    with states.section("srv_game_win_probability_play",
                        degraded_if_missing="Win probability by play has not been published yet.",
                        dataset=DATASETS["srv_game_win_probability_play"]):
        if not top.empty:
            curves = _win_probability_curves(top["game_id"])
    by_game = dict(tuple(curves.groupby("game_id"))) if not curves.empty else {}

    # ⚠️ THE LABEL IS BUILT ONCE PER ROW AND USED TWICE — by the width below and by the chart.
    # Two call sites deriving the same string is how the column ends up sized for a label the
    # chart does not draw, and the symptom would be a clipped percentage rather than an error.
    # ⚠️ `iterrows`, NOT `itertuples`: `_curve_label` reads columns with `.get` so a missing one
    # is an absence rather than an AttributeError, and a namedtuple has no `.get`.
    labels = {row["game_id"]: _curve_label(row, by_game.get(row["game_id"]))
              for _index, row in top.iterrows()} if not top.empty else {}

    def curve_cell(row) -> str:
        """One row's sparkline.

        🚨 THIS PANEL CANNOT SHOW A GAME WITHOUT A CURVE, AND THAT IS MEASURED RATHER THAN
        ASSUMED. The first version of this function carried two AC-G.11 absence branches —
        "before 2024" for the play-by-play scope and "not yet" for a game the feed has not
        reached. Asked R-760's question — WHAT WOULD HAVE TO BE WRONG FOR THIS TO FIRE? — the
        answer was NOTHING THE PAGE CAN PRODUCE:

            games with a fourth-quarter lead-change count but no curve rows      0
            games that can enter this panel at all                           1,895, 2024-2026

        The panel filters on `lead_changes_fourth_quarter` being non-null, and that column and
        the curve are built from the SAME staging model — so a game that can be ranked here
        always has a curve, and a pre-2024 game can never be ranked here at all. Two carefully
        worded sentences for states that cannot occur are decoration, and decoration in an
        absence branch is worse than none: it reads as a handled case and is never exercised.

        ⚠️ THE EM DASH STAYS as a defensive fallback, unreachable today. Should the panel's
        filter ever change to admit an unranked game — which is the edit that would make the
        absence real — this returns an honest blank rather than raising, and AC-G.11's
        "which absence is it" question gets asked again, properly, by that round.
        """
        points = by_game.get(row.game_id)
        if points is None or points.empty:
            return fmt.EM_DASH
        # 🚨 `_curve_label` OWNS THE `is False` TRAP, AND A138's PANEL TEST CAUGHT IT ON ITS FIRST
        # RUN. A boolean arriving out of a pandas frame is `numpy.bool_(False)`, which is NOT the
        # Python `False` singleton, so `reaches is not False` was True for every row and the whole
        # truncation branch would have been dead code that reads as handled.
        text, is_cut = labels.get(row.game_id, ("", False))
        return _sparkline_svg(points, label=text, is_cut=is_cut)

    # 🚨 THE CURVE COLUMN IS SIZED TO THE WIDEST CHART IN THIS FRAME, AND IT HAS TO BE.
    # `.cfdb-table` is `table-layout:fixed`, so without a colgroup every column takes an equal
    # share and a 254px overtime chart overflows a 137px cell. Reading B — shared SCALE, not
    # shared extent — means the charts differ in width by design, so the column is the widest of
    # them and the narrower ones simply do not fill it. Computed from the data rather than from a
    # constant, because a constant would be wrong the first week nothing goes to overtime.
    widest = max(
        (_curve_width(by_game[game_id], labels.get(game_id, ("", False))[0])
         for game_id in top["game_id"] if game_id in by_game),
        default=_curve_width(None))
    layout = ["26%", f"{widest + 12}px"] + ["auto"] * 6

    states.render_or_state(
        top, "srv_game",
        "The week's most exciting games would be here.",
        f"No completed games with fourth-quarter win probability for {scope.describe()}.",
        renderer=lambda d: table.render(d, [
            # 🚨 ONE SCOREBOARD CELL, ABSORBING FOUR COLUMNS — the matchup, the final score and
            # the two by-quarter lines. Marc: "present each row like a scoreboard, Away over
            # Home, each quarter, then final score, followed by the chart." Nothing was dropped
            # to make room: what were eleven columns are eight, and the four that went are all
            # inside this one.
            Col("scoreboard", "Scoreboard", render=_scoreboard),
            # ⚠️ THE CURVE SITS BESIDE THE SCORE, not at the end of the row. It is the picture of
            # what the ordering claims, so it belongs where a reader looking at the outcome
            # already is — and Marc asked for it in exactly that place.
            Col("curve", "Win probability", render=curve_cell),
            Col("lead_changes_fourth_quarter", "4th-qtr lead changes", kind="num"),
            Col("lead_changes_overtime", "OT lead changes", kind="num"),
            Col("mean_distance_from_even_fourth_quarter_onward", "How close, late", kind="num", dp=3),
            Col("lead_changes", "Lead changes, game", kind="num"),
            Col("excitement_index", "Excitement", kind="num", dp=1),
            Col("espn", "Commentary", render=_espn_link),
        ], layout=layout,
            caption="Ordered by fourth-quarter lead changes, then by mean distance from an "
                    "even win probability from the fourth quarter onward (lower is closer)."))


def _favorite_margin(row):
    """The favorite's own point margin, read from the column carried for that side.

    ⚠️ R-544. THE TWO BRANCHES USED TO BE EACH OTHER'S, AND IT INVERTED THE SIGN ON EVERY
    GRADED GAME — three panels, not one. `actual_margin` is AWAY MINUS HOME
    (srv_game.sql:312, "away minus home, per the convention"), so it is NOT the home side's
    margin and must not be handed to the home branch. `actual_margin_home_perspective`
    (srv_game.sql:623) is the home number and already exists beside it.

    Marc found it on the landing page: Virginia Tech, favored by 54.5 at home, won 73-3.
    `actual_margin` = 3 - 73 = -70, so the page reported -70 - 54.5 = -124.5 "points missed"
    for a team that beat the number by 15.5.

    ⚠️ VERIFIED AGAINST THE VIEW'S OWN VERDICT, not against reasoning: recomputing
    `favorite_covered` from this expression agrees on 171 of 171 graded 2026 games. The old
    expression agreed on 64.
    """
    return (row.actual_margin_home_perspective if row.spread_favorite_side == "home"
            else row.actual_margin)


def _recap_lists(df: pd.DataFrame, scope) -> None:
    st.subheader("How the week went against the market")
    if scope.week is not None and scope.week < MODEL_WEEK_FLOOR:
        st.caption(
            f"Market-only edition. Model-derived framing is withheld before week "
            f"{MODEL_WEEK_FLOOR} because the season has not trained enough games to say "
            f"anything honest; both lists are the closing market and the result.")

    graded = df[df["spread_favorite_side"].notna() & df["actual_margin"].notna()].copy()
    if graded.empty:
        states.empty("The recap lists would be here.",
                     f"No graded games with a closing line for {scope.describe()}.")
        return

    # ⚠️ THIS COMMENT USED TO CLAIM "carried not derived … all this does is order rows and
    # pick a side's label to show", AND THAT WAS NOT TRUE (R-544). `ats` on the next line is
    # metric arithmetic — margin minus the number — computed here, in a page, which is the
    # rule the serving layer exists to keep. The claim is worth recording because it is
    # plausibly WHY the inverted sign survived: a reader checking this block was told there
    # was no derivation in it to check.
    #
    # What IS carried: `favorite_covered`, `actual_margin`, `actual_margin_home_perspective`,
    # and the two market-implied probabilities. What is derived here: `favorite`/`opponent`
    # (labels), `spread` (an abs), and `ats`.
    #
    # ⚠️ `ats` CANNOT SIMPLY BE CARRIED, AND THE REASON IS GRAIN. srv_game_team already has
    # `ats_margin_final` (srv_game_team.sql:78) with `covered_final` beside it — but that is
    # game×TEAM grain and these three panels are game grain, one row per fixture showing the
    # favorite's side. Reading it here would mean a second query at a different grain and a
    # filter to the favorite's row. That may well be the right shape; it is a serving/query
    # change rather than a sign fix, so it is logged (R-551) rather than done in a round
    # whose job was to stop the page publishing false numbers.
    graded["favorite"] = graded.apply(
        lambda r: r.home_team_display if r.spread_favorite_side == "home"
        else r.away_team_display, axis=1)
    graded["opponent"] = graded.apply(
        lambda r: r.away_team_display if r.spread_favorite_side == "home"
        else r.home_team_display, axis=1)
    graded["fav_margin"] = graded.apply(_favorite_margin, axis=1)
    graded["spread"] = graded["spread_at_close"].fillna(graded["spread_current"]).abs()
    graded["ats"] = graded["fav_margin"] - graded["spread"]
    graded["fav_win_prob"] = graded.apply(
        lambda r: r.market_implied_home_win_probability if r.spread_favorite_side == "home"
        else r.market_implied_away_win_probability, axis=1)

    # 🚨 TWO LISTS, NOT THREE — AND THE UPSETS LEAD. R-711, and Marc's words were
    # "Underperformers - should be biggest upsets."
    #
    # ⚠️ THE THING HE ASKED FOR WAS ALREADY ON THE PAGE, SECOND, UNDER A METHOD DESCRIPTION.
    # `lost` — favorites that lost outright, ranked by how likely the market thought they were to
    # win — IS "biggest upsets" by the best definition this warehouse can express. It was headed
    # "Underperformers — by how likely the market thought they were to win", which is a method
    # standing in for a title, and it sat below a list headed "Underperformers". He read the
    # first heading and asked for what was underneath it.
    #
    # 🚨 AND THE OTHER TWO LISTS WERE THE SAME ROWS. Not overlapping — IDENTICAL, by
    # construction. The two expressions were character-for-character the same:
    #
    #     missed = graded[graded["ats"] < 0].sort_values("ats").head(10)
    #     covers = graded[graded["ats"] < 0].sort_values("ats").head(10)
    #
    # so the section spent two of its three lists on one set of games, framed twice, and buried
    # the third. The old caption argued for keeping both — "the reader's question differs: who
    # disappointed, and who was undervalued" — and that argument was written when the upset list
    # was NOT the headline. Once "biggest upsets" leads, "who disappointed" is the same question
    # again, asked twice.
    #
    # ✅ THE UNDERDOG FRAMING SURVIVES, AND THAT IS A DECISION WITH A REASON: a section about
    # upsets should name the team that did the unlikely thing, not the one that failed to.
    # ⚠️ Nothing is deleted but a PRESENTATION — `ats` keeps a reader in the surviving list.
    upsets = graded[graded["fav_margin"] < 0].sort_values(
        "fav_win_prob", ascending=False, na_position="last").head(10)
    covers = graded[graded["ats"] < 0].sort_values("ats").head(10)

    st.markdown("**Biggest upsets**")
    st.caption(
        "Favorites that lost outright, ranked by how likely the market thought the loser was "
        "to win \u2014 not by the size of the spread, and not by the final margin. A short "
        "favorite losing a coin-flip is not an upset; a heavy one losing is.")
    table.render(
        upsets,
        [Col("favorite", "Lost"), Col("opponent", "Beaten by"),
         Col("spread", "Favored by", kind="num", dp=1),
         Col("fav_margin", "Margin", kind="num"),
         Col("fav_win_prob", "Market gave them", kind="num", dp=3)],
        caption="Ranked by the loser's pregame market-implied win probability.")

    st.markdown("**Biggest underdog covers**")
    st.caption(
        "Underdogs the market priced too low, ranked by how far past the number they finished. "
        "These are graded against the spread rather than the result, so a team here may still "
        "have lost the game.")
    table.render(covers.assign(underdog=covers["opponent"], beat=covers["ats"].abs()),
                 [Col("underdog", "Underdog"), Col("favorite", "Favorite"),
                  Col("spread", "Getting", kind="num", dp=1),
                  Col("beat", "Covered by", kind="num", dp=1)],
                 caption="Ranked by points beyond the closing spread.")

    disagree = int(graded["favorite_definitions_disagree"].fillna(False).sum())
    if disagree:
        st.caption(
            f"\u26a0\ufe0f In {disagree} of these games the spread and the moneyline named "
            "different favorites. The upsets list uses the moneyline, because that is what an "
            "implied win probability comes from; the covers list uses the spread.")


def _movers(scope, depth: int) -> None:
    """R-475. The week's games ranked by how far the line travelled.

    ⚠️ RANKED BY LARGEST EXCURSION, NOT BY NET MOVE, and that is the whole point of the
    panel. A059 measured that excursion exceeds net move at every decile and that roughly a
    third of games END WHERE THEY STARTED having moved in between — so a ranking on net move
    hides precisely the games worth looking at. Both numbers are shown; only the excursion
    orders the list.

    ⚠️ NO THRESHOLD, NO COLOUR SCALE, NO "BIG MOVER" BADGE. A059 measured the distributions
    and deliberately stopped there: Marc sets the line, not the page. This shows the ranked
    list and the numbers.

    ⚠️ THE EXCURSION IS SIGNED, so the ranking is on its MAGNITUDE while the displayed value
    keeps its direction — a 6-point move toward the home side and one toward the away side
    are equally far travelled and belong equally high on the list.

    ⚠️ THE WIN-PROBABILITY COLUMNS ARE ALREADY IN PROBABILITY POINTS. Measured on published
    serving 2026 wk1: `market_implied_home_win_probability` runs 0.068…0.98 while
    `line_market_implied_win_probability_largest_excursion` runs -13.4…+10.6. They do NOT
    share a scale. Multiplying this one by 100 — the obvious thing to do to a column whose
    name says "probability" — renders 1,338 points and looks merely large rather than wrong.
    """
    st.subheader("The week's movers")

    with states.section("srv_game", dataset=DATASETS["srv_game"]):
        games = _line_movement(scope)
        if games.empty:
            states.empty(
                "The week's line movement would be here.",
                f"No completed games for {scope.describe()}.")
            return

        moved = games[games["line_spread_largest_excursion"].notna()]
        # THE THREE POPULATIONS, kept apart because they are different facts. A game with one
        # snapshot is not a game with no snapshots: the first was priced and never re-priced,
        # the second was never seen. Collapsing them into "no data" would overstate the hole.
        no_snapshots = int((games["line_snapshot_count"].fillna(0) == 0).sum())
        too_few = len(games) - len(moved) - no_snapshots

        # THE BOOK, READ FROM THE DATA RATHER THAN NAMED IN A LITERAL. These figures are
        # DraftKings-only by construction, and a movement number without its source is the
        # provenance defect the `market_implied_` prefix rule exists to prevent. Reading it
        # from the column means the caption cannot drift from what was actually priced.
        books = sorted({str(b) for b in moved["line_movement_provider_key"].dropna().unique()})
        book = ", ".join(books) if books else "an unnamed book"

        dropped = []
        if no_snapshots:
            dropped.append(f"{no_snapshots} had no line snapshots")
        if too_few:
            dropped.append(f"{too_few} had too few to measure a move")
        tail = f" Of {len(games)} completed games, {' and '.join(dropped)}." if dropped else ""

        st.caption(
            f"Ranked by the largest distance the spread traveled at any point, not by where "
            f"it finished — about a third of games end where they opened having moved in "
            f"between. Prices from {book}.{tail}")

        # mergesort because it is STABLE: games tied on excursion — and ties are common,
        # since spreads move in half and whole points — keep the query's game_id order
        # instead of reshuffling between renders of the same week.
        by_distance = moved["line_spread_largest_excursion"].abs()
        order = by_distance.sort_values(ascending=False, kind="mergesort").index
        ranked = moved.reindex(order).head(depth)

        # ⚠️ ON A SINGLE-SNAPSHOT GAME THE EXCURSION EQUALS THE NET MOVE BY CONSTRUCTION.
        # 2024 and 2025 were backfilled one row per game, so for those rows the two numbers
        # this panel shows side by side are the same measurement twice — and the caption's
        # "furthest it travelled, not where it finished" is not true of them. matchup.py's
        # own panel says this for one game; a ranked list needs to say it too, or the reader
        # ranks a week of 2025 believing they are looking at round trips that were never
        # observed. Said only when such a row is actually on screen.
        single = int((ranked["line_snapshot_count"].fillna(0) <= 1).sum())
        caveat = (f" {single} of these were priced once, so their furthest and net figures "
                  f"are the same number by construction rather than by measurement."
                  if single else "")

        states.render_or_state(
            ranked,
            "srv_game",
            "The week's line movement would be here.",
            f"No games with enough line snapshots to measure a move for {scope.describe()}.",
            renderer=lambda d: table.render(d, [
                Col("matchup", "Game",
                    render=lambda r: f"{r.away_team_display} at {r.home_team_display}"),
                Col("line_spread_largest_excursion", "Spread — furthest", kind="signed", dp=1),
                Col("line_spread_move_from_open", "Spread — net", kind="signed", dp=1),
                Col("line_total_largest_excursion", "Total — furthest", kind="signed", dp=1),
                Col("line_market_implied_win_probability_largest_excursion",
                    "Win prob — furthest (pp)", kind="signed", dp=1),
                # dp=0 BECAUSE THE FRAME FLOATS IT. line_snapshot_count is a bigint in
                # serving, but games with no snapshots put NaN in the column and pandas
                # widens the whole thing to float64 — so the default rendered "94.0" against
                # real data and "94" against any fixture without a null in it. Measured on
                # published serving, not reasoned about.
                Col("line_snapshot_count", "Snapshots", kind="num", dp=0),
                # ⚠️ PER ROW, NOT A FOOTNOTE. A window that spans a snapshot gap makes THAT
                # game's excursion a FLOOR rather than a measurement — the line may have gone
                # further while nobody was looking. 98 of 171 priced games in 2026 wk1 span
                # one, so a footnote would be describing the majority of the list.
                Col("line_movement_spans_snapshot_gap", "Window",
                    # ⚠️ NO APOSTROPHE IN THE TITLE, AND DOUBLE QUOTES AROUND IT. The first
                    # version wrote title='This game\'s prices…', whose apostrophe CLOSED the
                    # attribute mid-sentence and spilled the rest into the tag as stray
                    # attributes. It looked correct in the source and was only visible in
                    # rendered output against real rows.
                    render=lambda r: (
                        '<span title="Prices for this game have a gap in them, so the '
                        'distance shown is a floor: the line may have traveled further '
                        'while it was unobserved.">has a gap</span>'
                        if r.get("line_movement_spans_snapshot_gap") else "complete")),
            ], caption=f"Spread and total in points; win probability in de-vigged "
                       f"probability points. Prices from {book}. A row marked "
                       f"\u201chas a gap\u201d is a floor, not a measurement.{caveat}"))


def _scatter_svg(rows, x_dom, y_dom, x_step=50, y_step=50, width=560, height=380) -> str:
    """The scatter itself. Inline SVG in currentColor, following lib/distribution.py's
    precedent — one series, one hue, no legend, hairline axes (the chart standard's §7).

    ⚠️ THE DEFENSE AXIS RUNS THE OTHER WAY, AND THAT IS THE WHOLE DESIGN DECISION.
    Low yards allowed is GOOD. Plotted the obvious way — value increasing upward, as a reader
    trained on cartesian axes expects — the best defenses land at the bottom and the chart
    reads backwards to anyone scanning for "up and right is good", which is how everyone scans
    a scatter before reading a word of it.
    So yards allowed increases DOWNWARD: the strongest defenses are at the TOP, the strongest
    offenses at the RIGHT, and the top-right corner is unambiguously the good one. In SVG this
    needs no flip — y already grows downward — which is precisely why it is easy to ship the
    wrong orientation without noticing you chose one.

    An axis label alone would not carry this, so the direction is stated three ways: arrows on
    both axis titles, the words "better" on each, and a corner marker. No colour scale, no
    threshold line, no quadrant shading — none of those judgements has been made.
    """
    pad_l, pad_r, pad_t, pad_b = 56, 18, 20, 46
    pw, ph = width - pad_l - pad_r, height - pad_t - pad_b
    x0, x1 = x_dom
    y0, y1 = y_dom

    def sx(v):
        return pad_l + (float(v) - x0) / (x1 - x0) * pw

    def sy(v):
        # NOT flipped: small "allowed" -> small y -> top of the plot. See the docstring.
        return pad_t + (float(v) - y0) / (y1 - y0) * ph

    def esc(t):
        return (str(t).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    parts = []
    # ⚠️ TICKS ARE WALKED BY THE STEP, NOT SLICED INTO A FIXED COUNT. The first version drew
    # five evenly-spaced ticks across the domain, which puts them on 75s when the domain is
    # 250-550 — the bounds were round and everything between them was not. The chart standard
    # §0.2 wants the bounds to BE ticks so every render lands on the same round numbers and
    # two charts are comparable at a glance; that only holds if the whole ladder is round.

    def ladder(lo, hi, step):
        n, out = 0, []
        while lo + n * step <= hi + 1e-9:
            out.append(lo + n * step)
            n += 1
        return out

    for v in ladder(x0, x1, x_step):
        gx = sx(v)
        parts.append(f"<line class='cfdb-sc-grid' x1='{gx:.1f}' y1='{pad_t}' "
                     f"x2='{gx:.1f}' y2='{pad_t + ph}'/>")
        parts.append(f"<text class='cfdb-sc-tick' x='{gx:.1f}' y='{pad_t + ph + 14}' "
                     f"text-anchor='middle'>{v:.0f}</text>")
    for v in ladder(y0, y1, y_step):
        gy = sy(v)
        parts.append(f"<line class='cfdb-sc-grid' x1='{pad_l}' y1='{gy:.1f}' "
                     f"x2='{pad_l + pw}' y2='{gy:.1f}'/>")
        parts.append(f"<text class='cfdb-sc-tick' x='{pad_l - 8}' y='{gy + 3:.1f}' "
                     f"text-anchor='end'>{v:.0f}</text>")

    for r in rows:
        cx, cy = sx(r["x"]), sy(r["y"])
        parts.append(
            f"<circle class='cfdb-sc-pt' cx='{cx:.1f}' cy='{cy:.1f}' r='3.5'>"
            f"<title>{esc(r['team'])} — {r['x']:.1f} gained, {r['y']:.1f} allowed "
            f"per game over {int(r['games'])} game(s)</title></circle>")

    # The good corner, named. A reader scans the shape first, so this is a mark and not prose.
    parts.append(f"<text class='cfdb-sc-corner' x='{pad_l + pw - 2}' y='{pad_t + 12}' "
                 f"text-anchor='end'>better \u2197</text>")
    parts.append(f"<text class='cfdb-sc-axis' x='{pad_l + pw / 2:.0f}' y='{height - 8}' "
                 f"text-anchor='middle'>Yards gained per game \u2192 better</text>")
    parts.append(f"<text class='cfdb-sc-axis' transform='rotate(-90 12 {pad_t + ph / 2:.0f})' "
                 f"x='12' y='{pad_t + ph / 2:.0f}' text-anchor='middle'>"
                 f"\u2191 better \u2014 fewer yards allowed per game</text>")

    return (f"<div class='cfdb-scatter'><svg viewBox='0 0 {width} {height}' "
            f"role='img' aria-label='Yards gained per game against yards allowed per game; "
            f"stronger teams sit toward the top right'>{''.join(parts)}</svg></div>")


def _profile(scope, depth: int) -> None:
    """R-477. Offense against defense, per game, as the teams stood ENTERING the week in
    scope.

    ⚠️ THE COPY SAYS "the week in scope" OR "the selected week", never the present-tense
    phrasing. Looking Back is week-selectable, so present-tense wording names whichever week
    the READER is on rather than the current one.
    test_the_week_floor_is_named_not_hardcoded_in_copy exists for exactly this and caught the
    first draft of this panel. ⚠️ It greps the SOURCE, so it cannot tell page copy from a
    comment discussing page copy — which is why this note describes the banned phrasing
    instead of quoting it. Weakening the test to allow the quote would be the wrong trade.
    """
    st.subheader("Offense and defense, per game")

    with states.section("srv_team_week", dataset=DATASETS["srv_team_week"]):
        # ⚠️ A SCATTER NEEDS ONE POINT PER TEAM, WHICH NEEDS ONE WEEK. The week filter offers
        # "All", and under it srv_team_week returns every week for every team — sixteen points
        # per team, not one. Aggregating them down here would be the app deriving a figure,
        # which is the rule this whole layer exists to keep, so the honest answer is to ask
        # for a week rather than to quietly draw the wrong chart.
        if scope.week is None:
            states.empty(
                "The offense-and-defense chart would be here.",
                "This chart shows each team as it stood entering ONE week, so it needs a "
                "week rather than the whole season. Pick a week above.")
            return

        teams = _yardage_profile(scope)
        if teams.empty:
            states.empty(
                "The offense-and-defense chart would be here.",
                f"No teams in scope for {scope.describe()}.")
            return

        table.as_of_caption(teams)
        playable = teams[(teams["games_counted"].fillna(0) > 0)
                         & teams["total_yards_for_per_game"].notna()
                         & teams["total_yards_allowed_per_game"].notna()]
        dropped = len(teams) - len(playable)

        # ⚠️ WEEK 1 IS EVERY TEAM. Nothing has been played before it, so no team has a point
        # and the honest render is an Empty state rather than an empty pair of axes — an empty
        # chart says "we drew this and there was nothing", which reads as a fault.
        if playable.empty:
            states.empty(
                "The offense-and-defense chart would be here.",
                f"No team has played a completed game before {scope.describe()}, so there is "
                f"nothing to plot yet. Week 1 is always empty here — the figures are what a "
                f"team carries INTO the week.")
            return

        xs = playable["total_yards_for_per_game"].astype(float)
        ys = playable["total_yards_allowed_per_game"].astype(float)

        # Domain rounded OUT to a whole tick, per the chart standard §0.2, so the bounds ARE
        # ticks and every render of this chart lands on the same round numbers.
        def domain(series, step=50):
            lo = math.floor(series.min() / step) * step
            hi = math.ceil(series.max() / step) * step
            return (lo, hi if hi > lo else lo + step), step

        rows = [{"team": t, "x": x, "y": y, "games": g}
                for t, x, y, g in zip(playable["team_display"], xs, ys,
                                      playable["games_counted"])]

        x_dom, x_step = domain(xs)
        y_dom, y_step = domain(ys)
        st.markdown(_scatter_svg(rows, x_dom, y_dom, x_step, y_step),
                    unsafe_allow_html=True)

        # ⚠️ SAY WHAT WAS DROPPED AND WHY. A silently shorter chart is the same defect as a
        # silently shorter list — the reader cannot tell 130 teams from 130 of 136.
        note = (f"{len(playable)} teams. Each point is one team as it stood ENTERING "
                f"{scope.describe()} — every figure is over completed games in earlier weeks, "
                f"never the selected week's own game. Up and to the right is stronger on "
                f"both sides: "
                f"the vertical axis runs downward so fewer yards allowed is higher.")
        if dropped:
            note += (f" {dropped} teams are not plotted because they had no completed game "
                     f"before the selected week.")
        st.caption(note)


def _leaderboards(scope, depth: int) -> None:
    st.subheader("Leaderboards")

    with states.section("srv_team_game_log", dataset=DATASETS["srv_team_game_log"]):
        teams = _team_yardage(scope, depth)
        st.markdown("**Team yardage**")
        states.render_or_state(
            teams, "srv_team_game_log",
            "The team yardage board would be here.",
            f"No completed team box scores for {scope.describe()}. Box scores start in 2024.",
            renderer=lambda d: table.render(d, [
                Col("team_display", "Team"), Col("opponent", "Opponent"),
                Col("total_yards", "Total", kind="num"),
                Col("rushing_yards", "Rush", kind="num"),
                Col("passing_yards", "Pass", kind="num"),
            ], caption="Ranked by total offense."))

    with states.section("srv_player_game_log", dataset=DATASETS["srv_player_game_log"]):
        yards = _player_board(scope, depth, ("passing", "rushing", "receiving"), "YDS")
        st.markdown("**Player yardage**")
        states.render_or_state(
            yards, "srv_player_game_log",
            "The player yardage board would be here.",
            f"No player box scores for {scope.describe()}. Box scores start in 2024.",
            renderer=lambda d: table.render(d, [
                Col("player_name", "Player"), Col("team", "Team"),
                Col("stat_category", "Category"),
                Col("stat_value", "Yards", kind="num"),
            ], caption="Passing, rushing and receiving yards in one board."))

        tds = _player_board(scope, depth, ("passing", "rushing", "receiving"), "TD")
        st.markdown("**Touchdowns**")
        st.caption("A different board from yardage, and mostly different names on it.")
        states.render_or_state(
            tds, "srv_player_game_log",
            "The touchdown board would be here.",
            f"No player box scores for {scope.describe()}.",
            renderer=lambda d: table.render(d, [
                Col("player_name", "Player"), Col("team", "Team"),
                Col("stat_category", "Category"),
                Col("stat_value", "TD", kind="num"),
            ], caption="Passing, rushing and receiving touchdowns."))

        st.markdown("**Defensive leaders**")
        defense = _player_board(scope, depth, ("defensive",), "TOT")
        states.render_or_state(
            defense, "srv_player_game_log",
            "The defensive board would be here.",
            f"No defensive box scores for {scope.describe()}.",
            renderer=lambda d: table.render(d, [
                Col("player_name", "Player"), Col("team", "Team"),
                Col("opponent", "Opponent"),
                Col("stat_value", "Tackles", kind="num"),
            ], caption="Total tackles. TFL and sacks are separate stat types on the same view."))


# ⚠️ R-562. THE ONLY ALTAIR IN THE SITE, AND IT IS NOT A NEW DEPENDENCY.
# `altair` is a HARD REQUIREMENT of streamlit — `pip show streamlit` lists it first — so it is
# already in the image and importing it adds no package. It is declared in
# site/requirements.txt anyway, because a direct import deserves a direct declaration: relying
# on a transitive pin means the day streamlit drops altair this page raises on import, and
# that file's own header says the failure mode for a missing site dependency is silent.
#
# WHY NOT st.line_chart. It cannot do the one thing a bump chart requires. Measured on the
# pinned streamlit 1.61.1: the call accepts only
# `data, x, y, x_label, y_label, color, width, height, use_container_width` — no scale, no
# domain, no reverse — and the Vega-Lite it generates encodes y as
# `{"type": "quantitative", "scale": {}}`. An empty scale on a quantitative axis ascends
# upward, so RANK 1 PLOTTED AT THE BOTTOM. The caption that used to sit under it said "Rank 1
# at the top of the axis is inverted by convention", which was false in both halves: the axis
# was not inverted and nothing in that call could invert it.
#
# WHY NOT HAND-DRAWN SVG, which this file has a precedent for in _scatter_svg. The only hard
# requirement here is an inverted ordinal axis, and `alt.Scale(reverse=True)` is that in three
# words. `st.line_chart`'s own docstring calls itself "syntax-sugar around st.altair_chart",
# so this removes the sugar rather than adding a layer.
_BUMP_HEIGHT = 420


def _bump_chart(frame: pd.DataFrame, poll: str) -> None:
    """A bump chart: rank 1 at the top, one line per team, gaps where a team was unranked."""
    weeks = sorted(int(w) for w in frame["week"].unique())
    teams = list(frame["team_display"].unique())

    # ⚠️ THE FULL TEAM x WEEK GRID, AND IT IS LOAD-BEARING RATHER THAN TIDINESS.
    # A team that drops out of the poll and returns has NO ROW for the weeks between, and a
    # line mark joins whatever consecutive points it is given — so on the raw frame Altair
    # would draw a straight segment across the gap, saying the team held a rank it did not
    # hold. Reindexing onto every (team, week) pair puts an explicit null in the gap, and a
    # line mark breaks at a null. This is the chart honouring the same rule the table beneath
    # it already honours: `_delta` refuses to render a missing previous rank as "no change",
    # and the picture must not contradict it.
    grid = pd.MultiIndex.from_product([teams, weeks],
                                      names=["team_display", "week"]).to_frame(index=False)
    data = grid.merge(frame[["team_display", "week", "rank"]],
                      on=["team_display", "week"], how="left")
    data["week"] = data["week"].astype(int)

    worst = int(frame["rank"].max())
    # Endpoint labels sit to the right of each team's last week, so the plotting area stops
    # short of the full width rather than the labels being clipped.
    last = (data.dropna(subset=["rank"]).sort_values("week")
                .groupby("team_display", as_index=False).last())

    hover = alt.selection_point(fields=["team_display"], on="pointerover",
                                nearest=False, empty=True, clear="pointerout")

    x = alt.X("week:O", title="Week", axis=alt.Axis(labelAngle=0))
    # 🚨 reverse=True IS THE WHOLE POINT OF THIS PANEL. Rank 1 at the TOP.
    y = alt.Y("rank:Q", title="Rank",
              scale=alt.Scale(reverse=True, domain=[0.5, worst + 0.5], nice=False),
              axis=alt.Axis(values=[v for v in (1, 5, 10, 15, 20, 25) if v <= worst],
                            tickMinStep=1))

    # ONE NEUTRAL COLOUR RATHER THAN TWENTY-FIVE, AND THIS IS A DELIBERATE CHOICE.
    # A categorical palette runs out well before 25 and starts recycling, so two teams get the
    # same colour and the reader has no way to know which. `currentColor` follows the theme,
    # the hovered team is what gets emphasis, and the endpoint labels are what identify a
    # line. Team BRAND colours would be the real answer and they are not available here:
    # srv_rankings carries team_slug and no colour, and adding a join in the page is a model
    # change wearing a page change. Logged, not built.
    base = alt.Chart(data).encode(x=x, y=y, detail="team_display:N")
    # ⚠️ `invalid` IS SET EXPLICITLY AND MUST STAY THAT WAY. Vega-Lite's default for path
    # marks changed in 5.14 — before it, an invalid value was FILTERED, which joins the two
    # points either side and draws exactly the straight line across a team's unranked weeks
    # that the null grid above exists to prevent. v6.4.1 defaults to breaking paths, so this
    # is currently redundant; it is written down because the whole correctness of the gap
    # rests on it and a silent default is not something to rest it on.
    lines = base.mark_line(interpolate="monotone", clip=True,
                           invalid="break-paths-filter-domains").encode(
        strokeWidth=alt.condition(hover, alt.value(3.0), alt.value(1.25)),
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.35)))
    points = base.mark_circle(clip=True).encode(
        size=alt.condition(hover, alt.value(70), alt.value(22)),
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.45)),
        tooltip=[alt.Tooltip("team_display:N", title="Team"),
                 alt.Tooltip("week:O", title="Week"),
                 alt.Tooltip("rank:Q", title="Rank", format="d")])
    labels = alt.Chart(last).mark_text(align="left", dx=8, fontSize=11).encode(
        x=x, y=y, text="team_display:N",
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.75)))

    chart = (lines + points + labels).add_params(hover).properties(
        height=_BUMP_HEIGHT, padding={"right": 96}).configure_view(stroke=None)
    # ⚠️ R-659: THIS CHART IS SQUEEZED BY STREAMLIT'S AUTOSIZE AND DELIBERATELY NOT "FIXED".
    #
    # `_prepare_vega_lite_spec` imposes `autosize: fit` on any spec that declares none, which
    # makes `height` the OUTER BOX rather than the plot — the defect that collapsed Matchup's
    # 150px charts (R-603). Measured in a real browser (A100), plot height drawn against the
    # 420 asked for, as the axis font grows:
    #
    #     axis font    10px   13px   16px   20px   24px   28px
    #     plot drawn     388    381    375    366    355    345
    #
    # 🚨 IT LOSES A NEAR-CONSTANT ~35px, NOT A PROPORTION, because its axis labels are short
    # and horizontal — so it degrades gracefully and cannot reach a collapse at any font a
    # reader will set. `performance.py`'s calibration curve loses ~6.5px PER pixel of font and
    # was fixed for exactly that reason; this one would need a 100px axis font to break.
    #
    # ⚠️ THE DELIVERABLE HERE IS THE MEASUREMENT, NOT A NEW CHART. If this is ever given a
    # smaller height, or labels that rotate, re-measure before trusting it.
    st.altair_chart(chart, use_container_width=True)
    st.caption(
        f"{poll}, full season. **Rank 1 is at the top.** Every ranked team is drawn; a line "
        "stops where a team left the poll and restarts where it returned, so a gap is a "
        "week unranked rather than a rank held. Hover a line to follow one team.")


def _bump(scope, depth: int) -> None:
    st.subheader("Poll movement")
    with states.section("srv_rankings", dataset=DATASETS["srv_rankings"]):
        polls = _rankings(scope)
        if polls.empty:
            states.empty("The poll chart would be here.",
                         f"No AP or Coaches poll rows for {scope.describe()}.")
            return
        poll = st.radio("Poll", POLLS, horizontal=True, key="today_poll")
        one = polls[polls["poll_name"] == poll]
        if one.empty:
            states.empty("The poll chart would be here.", f"No {poll} rows for this season.")
            return

        _bump_chart(one, poll)

        latest_week = int(one["week"].max())
        current = one[one["week"] == latest_week].copy()
        previous = one[one["week"] == latest_week - 1][["team_display", "rank"]]
        previous = previous.rename(columns={"rank": "prev_rank"})
        current = current.merge(previous, on="team_display", how="left")

        # ⚠️ A team with no previous rank is NEW or RETURNING, never "no change". Rendering
        # that as 0 or blank is the defect this column exists to avoid.
        def _delta(row) -> str:
            if pd.isna(row.prev_rank):
                return "new" if latest_week == int(one["week"].min()) else "unranked last week"
            change = int(row.prev_rank) - int(row["rank"])
            return "—" if change == 0 else (f"▲ {change}" if change > 0 else f"▼ {abs(change)}")

        current["delta"] = current.apply(_delta, axis=1)
        table.render(current.sort_values("rank"), [
            Col("rank", "Rank", kind="num"),
            Col("team_display", "Team"),
            Col("points", "Points", kind="num"),
            Col("delta", "vs previous week"),
        ], caption=f"{poll}, week {latest_week}. Points are the poll total; first-place votes "
                   "are carried separately on the view.")


def _recap(scope, depth: int) -> None:
    """The week that happened: Most Exciting and the three market lists.

    Lifted out of body() by R-573 so it can be NAMED in TABS like every other panel. It was
    the one section written inline, which meant the tab split could not reference it and the
    assignment test could not see it.
    """
    with states.section("srv_game", dataset=DATASETS["srv_game"]):
        games = _completed_games(scope)
        table.as_of_caption(games)

        if games.empty:
            states.empty(
                "The weekly recap would be here.",
                f"No completed games for {scope.describe()}. "
                "Pick a week that has finished, or widen the conference filter.")
        else:
            _most_exciting(games, scope)
            _recap_lists(games, scope)


def _looking_forward(scope, depth: int) -> None:
    st.subheader("Looking forward")
    st.caption(
        "The week preview — matchups to watch, and what the market makes of them — is the "
        "next round of work on this page. It is not built yet, and an empty frame would "
        "imply it was.")
    st.markdown(f"For the full slate, see [Schedule]({scope.link('schedule')}).")


# --- page -----------------------------------------------------------------------------

def body(page) -> None:
    scope = filters.game_scope()

    # THE TAB SAYS WHICH WEEK YOU ARE LOOKING AT. `lib/tab.py`, and this is also the call
    # that EXERCISES its suffix parameter in production rather than only in a test — both
    # branches of it, because `scope.week` is None whenever the week filter reads "All" and
    # the suffix is then dropped instead of rendering `M4D · Today · Week None`.
    #
    # The later call wins: app.py has already set `M4D · Today` before this page ran.
    tab.set_title_for("today", suffix=f"Week {scope.week}" if scope.week else None)

    # ⚠️ R-574. THE PAGE-LEVEL `table.dataset_caption("Looking Back", "srv_game")` THAT USED
    # TO SIT HERE IS GONE, and it was wrong twice over: "Looking Back" is a TAB, not a
    # dataset, and `srv_game` is one of the FIVE views this page reads. Each section now
    # states its own, from its own states.section call.
    slug, _label, panels = _active_tab()

    depth = st.radio("Leaderboard depth", DEPTHS, index=1, horizontal=True,
                     key="today_depth", help="How many rows each leaderboard shows.")

    _tab_bar(slug)
    for name in panels:
        globals()[name](scope, depth)

    # 🚨 R-558. ATTRIBUTION ATTACHES TO RENDERED MODEL OUTPUT, AND THIS PAGE RENDERS NONE.
    #
    # ⚠️ WHOEVER ADDS A `predicted_*` COLUMN TO THIS PAGE ADDS THE CALL BACK WITH IT:
    #
    #     attribution.model_attribution(_completed_games(scope))
    #
    # `attribution` IS STILL SELECTED in _completed_games on purpose, so that is a one-line
    # change rather than two. §0.9's design is that a page cannot render the model's numbers
    # without having fetched the string saying whose model it is; keeping the column fetched
    # keeps that guarantee ready rather than making the next person rediscover it.
    #
    # This page is EXPECTED to gain model numbers — MODEL_WEEK_FLOOR and _recap_lists'
    # "model-derived framing is withheld before week N" both anticipate it.
    #
    # WHY IT CAME OUT (R-558, tracing back to R-545). A083 fixed a false claim here:
    # `attribution` had been on srv_game all along and this query was the only one not
    # asking for it, so model_attribution() took
    # its "column missing from this view — this is a defect (AC-G.41)" branch and printed
    # that on the landing page. Correct, and it left a true statement that was still noise —
    # on the current season the page said "attribution is null on every row", a warning about
    # the absence of provenance for predictions it never showed.
    #
    # ⚠️ TODAY DOES RENDER PROBABILITIES, AND THEY ARE NOT OURS. `market_implied_*` is the
    # BOOK's number and the prefix is itself the provenance (§4.3 — "a licence boundary
    # wearing a naming convention"). `largest_single_play_swing` and
    # `home_win_probability_range` are CFBD play-by-play derivatives and are selected but
    # never rendered. There is no `predicted_*` anywhere in this module.


def render() -> None:
    # R-479. `shell.page` DOES NOT EXIST — the module exports render_page(key, body), and the
    # other fourteen views all call it that way. This line raised AttributeError on every
    # open from A067 (c2f5b50, #143, 2026-09-08) until 2026-09-09, and Today is app.py's
    # DEFAULT page, so it was the first thing every visitor hit.
    #
    # Nothing in the repo could see it. test_site_foundation IMPORTS every view module, which
    # succeeds — the name is only resolved when render() is called. The site-image smoke test
    # builds st.Page objects and counts them without running one. A074's panel-exercise test
    # calls the panels directly and never goes through render(). Every check was one layer
    # away from the only line that mattered. That gap is R-480.
    shell.render_page("today", body)
