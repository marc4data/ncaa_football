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

from lib import (filters, fmt, glyphs, identity, params, shell, states, tab, table,
                 theme, winprob)
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
# 🚨 A153. THE FIRST KEY IS THE SCOREBOARD'S OWN LEAD CHANGES — §3.3's MIGRATE, and Marc chose it
# with A152's numbers in front of him: *"Show actual scoreboard lead changes instead."*
#
# 📊 HE CHOSE IT KNOWING THE TIEBREAK WOULD DO MOST OF THE SORTING. In the fourth quarter the
# scoreboard measure tops out at 3 this season and most of the top ten tie at 2, so
# `mean_distance_from_even_fourth_quarter_onward` decides the order between them. ✅ That is what a
# tiebreak is FOR — *changed hands twice, then stayed within a score* is a good definition of
# exciting — and it is a deliberate trade rather than a property nobody noticed.
#
# ⚠️ THE TIEBREAK IS UNCHANGED AND SO IS THE POPULATION. 📊 Measured before the switch: the old key
# and the new one are NULL on the same 3 games of 1,898 and disagree on none, so the panel shows
# the same games in a different order rather than a different set.
MOST_EXCITING_ORDER = ("scoreboard_lead_changes_fourth_quarter desc nulls last, "
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


# ── A153, §3.3's MIGRATE: WHAT `_completed_games` SELECTS AND WHO STILL READS IT ─────────────
#
# 🚨 A COMMENT INSIDE THE SQL STRING BREAKS `ci/check_page_queries.py`, WHICH IS WHY THIS IS HERE.
# That checker executes every page query against CI's serving layer and normalises it with
# `" ".join(raw.split())` (`check_page_queries.py:120`) — collapsing the statement onto ONE line,
# where a `--` comment swallows everything after it. The symptom is
# `today.py: syntax error at end of input`, and the SQL is perfectly valid in every other context.
# **Python comments above the query, never SQL comments inside it.**
#
# ✅ The panel now RANKS, FILTERS and DISPLAYS on `scoreboard_lead_changes*` — Marc's call.
#
# ✅ AND THE FIVE `*_by_clock` ALIASES ARE GONE AS OF A156 (cfdb-main-R-1103). A153 found them
# unread, A155 contracted the feed-ordered columns they replaced, and this round removed the
# selects themselves — five columns fetched on every load of this page and read by nothing.
#
# 🚨 THE COUNT WAS REDONE RATHER THAN INHERITED, AND A155's OWN R-1104 IS WHY: that round's
# consumer search used `grep -v "_by_clock"` on `grep -rn` output, which filters on the PATH, so
# it hid the one file NAMED for the term. **Redone here with no `-v` at all** — exact names, a
# trailing boundary, and the LINES read rather than counted. Every surviving mention is prose, a
# test fixture key, or a guard's own list; nothing reads the values.
#
# ⚠️ THE COLUMNS THEMSELVES STAY PUBLISHED. This is a page query, not a serving contract: the
# `*_by_clock` measures are real and `srv_game` still carries them. Nothing in `dbt/` moves, and
# §2.3 row counts are not owed for removing a SELECT item.
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

    🚨 A144. SIX COLUMNS ARRIVED FOR THE SHARED TEAM-IDENTITY CELL, AND TWO OF THEM ARE THE
    ANSWER TO A QUESTION THAT LOOKED LIKE A TRAP.

    Marc, on four separate sections: *"Include Rank Team Name and record."*

    📊 `home_rank` / `away_rank` — NULL MEANS UNRANKED, WHICH IS A PUBLISHED FACT RATHER THAN A
    GAP (AC-G.11). Measured on 2026 regular: the values run 1..25 and stop there, because it is a
    Top 25; 5.3% of PLAYED games carry a home rank. B118 established exactly this for the twin
    `opponent_rank` on `srv_game_team` and measured 7.6%; the same query here returns 7.63%.
    **So the cell says "unranked", never an em dash** — `table.team_cell` already draws no badge
    at all, which is AC-1.5 and is the older, better answer.

    🚨 THE RECORD PAIR, AND THE SOURCE COLUMN'S NAME IS MISLEADING RATHER THAN THE COLUMN.
    `srv_game.sql` reads `rw_home.current_record as home_team_record_display`, and "current"
    invites exactly one conclusion. **It is wrong.** Seventeen lines above it that file says, in
    capitals, *"R-084. THE RECORD AS IT STOOD GOING INTO THIS GAME'S WEEK"*, and
    `fct_team_record_week` builds it over `rows between unbounded preceding and 1 preceding`.
    📊 MEASURED RATHER THAN REASONED: across 2026 regular, **all 453 week-1 games carry `0-0` —
    one distinct value.** A current-as-of-now record could not do that after two weeks of play.

    ✅ SO BOTH HALVES OF R-140's PAIR ARE SELECTED and `table.record_span` chooses between them:
    a completed game shows the record it PRODUCED, a scheduled one the record it carried IN.
    Looking Back is all completed games, so in practice this panel always shows the after-record
    — but the rule is the shared one rather than a local shortcut, which is what stops the two
    pages drifting.

    ⚠️ `is_completed` IS SELECTED THOUGH THE `where` ALREADY FILTERS ON IT. `glyphs.winner` and
    `table.record_span` both READ it off the row, and a column a page filters on is not a column
    a page has. It was not in this select list before A144.

    🚨 A147. THREE COLUMNS FOR THE RESULT STRIP, CHECKED AGAINST THE DATABASE RATHER THAN AGAINST
    SCHEDULE'S QUERY (§2.2.1c.2).

    `upset_level`, `winner_covered_close` and `over_met` are what `glyphs.result_strip` reads.
    ⚠️ **THE PROMPT SAID SCHEDULE READS `srv_schedule`, THAT LOOKING BACK READS A DIFFERENT
    RELATION, AND THAT THE SECOND MIGHT NOT CARRY THEM.** 📊 **THERE IS NO `srv_schedule`.**
    `schedule.py:202` reads `from srv_game` — **the same relation this query reads** — so they are
    the same columns, and all four the strip needs are on it.

    ✅ THE CHECK WAS STILL WORTH RUNNING: it turned *"these may be different"* into *"they are the
    same object"*, which is a stronger statement than either guess.

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
               home_rank, away_rank,
               home_team_record_display, away_team_record_display,
               home_team_record_after_display, away_team_record_after_display,
               is_completed,
               upset_level, winner_covered_close, over_met,
               home_points, away_points, actual_margin,
               actual_margin_home_perspective, excitement_index,
               spread_at_close, spread_current, spread_open, spread_move_from_open,
               favorite_covered, spread_favorite_side, moneyline_favorite_side,
               favorite_definitions_disagree,
               market_implied_home_win_probability, market_implied_away_win_probability,
               home_win_probability_range,
               home_win_probability_range_fourth_quarter,
               scoreboard_lead_changes,
               scoreboard_lead_changes_fourth_quarter,
               scoreboard_lead_changes_overtime,
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
    """The team yardage board. A144 MOVED IT FROM `srv_team_game_log` TO `srv_game_team`.

    > **MARC**, on the leaderboards: *"Include Team Logo, Rank, Record."*

    🚨 A RELATION SWITCH RATHER THAN A JOIN, AND THE SETTLED DECISION IS WHY. `srv_team_game_log`
    carries `team_slug`, `team_display` and `logo_source_url` — and **no rank and no record**.
    Both facts exist one relation over, at the SAME game x team grain, on `srv_game_team`:
    `team_rank` and `record_before_display`. Enriching one frame from another is a JOIN, and
    *"Streamlit is display-only: single-table SELECT + WHERE. No joins"* forbids it. Reading the
    view that already holds every column is the same data in one pass (G-2).

    📊 EVERY COLUMN THIS BOARD NEEDS WAS CHECKED AGAINST `information_schema` BEFORE THE SWITCH,
    not against the model file: `team_display`, `team_slug`, `team_logo_url`, `team_rank`,
    `record_before_display`, `opponent`, `total_yards`, `rushing_yards`, `passing_yards`,
    `classification`, `conference`, `is_completed` — all present.

    ⚠️ `record_before_display` IS THE ONLY RECORD THIS VIEW PUBLISHES, and its own comment says
    why the name is the guard: *"on a game x team row a bare [record] is ambiguous"*. So this
    board shows the record going INTO the game, where Looking Back's game-grain panels show the
    record the game produced (R-140). **Two relations, two available facts, and the cell says
    which through `record_span`'s `title` rather than leaving a reader to assume.**
    """
    return query("""
        select team_display, team_slug, team_logo_url, team_rank, record_before_display,
               conference, opponent, week, is_completed,
               total_yards, rushing_yards, passing_yards, points_for, result, as_of_ts
        from srv_game_team
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

    🚨 ONE SELECT LIST FEEDS ALL THREE BOARDS, which is why A149's eight new columns are one
    change rather than three. A146 published them on this view (`63b05dd`) and nothing read them
    for three rounds.

    ⚠️ CHECKED AGAINST `information_schema` ON LIVE PUBLISHED SERVING BEFORE THEY WERE DRAWN, not
    against A146's model file — §2.2.1c.2, which B121 learned by getting
    `UndefinedColumn: column "opponent_classification" does not exist` back from a column a model
    file appeared to publish. All eight are present; `srv_player_game_log` publishes 33.

    🚨 §2.5's SECOND QUESTION — *how many rows carry it* — ONCE HAD A LOUD ANSWER HERE, AND
    A166 RE-ASKED IT AND FOUND THE ANSWER HAD MOVED (cfdb-main-R-1306).

    ⚠️ **THIS PARAGRAPH USED TO READ `2026 … 40.9% 🚨` AND `dim_athlete holds 138 teams for 2026,
    every one of them FBS`, STATED AS CURRENT FACT.** Both were true when A149 measured them and
    neither is true now:

        measured by A149          2026   40.9% carry a jersey · 138 teams in dim_athlete
        measured by A166 (live)   2026   92.9% carry a jersey · 306 teams, 31,070 athletes

    📊 **THE CAUSE IS THAT THE ROSTER WAS REFETCHED ON 2026-09-16** — `raw.raw_roster` holds four
    payloads totalling 7.5MB, last fetched that day, against the single pre-season pull of
    2026-08-15 that A149 found. **The FBS-only gap closed itself.**

    ✅ **AND ON THE POPULATION THAT ACTUALLY REACHES A CARD IT IS BETTER STILL**: of the ninety
    players in the nine top-10 columns the cards draw, jersey, position and class year are
    present on **90 of 90**, and a team logo on 89. At depth 25 it is 98.2%; at 50, 96.9%.

    ⚠️ **THE ABSENCE HANDLING STAYS EXACTLY AS IT WAS.** `_player_identity` still names the one
    absence worth naming and omits the rest — the measurement changes what is TYPICAL, not what
    is POSSIBLE, and a view with no classification column can still serve a player whose team has
    no roster row. **A number in a docstring is a claim with a date on it; this one is A166's.**
    """
    return query("""
        select player_name, player_slug, team, conference, opponent, week,
               stat_category, stat_type, stat_value, as_of_ts,
               jersey, position, class_year_display,
               team_slug, team_display, team_logo_url, team_rank, record_before_display
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
    # ⚠️ A165 SELECTS THE CONTRAST-SAFE PAIR, NOT `color_primary`. R-855's lesson, measured:
    # nearly a fifth of teams publish #000000 as their on-light value, so the raw brand colour
    # can be invisible against the page it is drawn on. The ladder already answers "what is safe
    # against THIS background" and is what the drives panel reads.
    #
    # 🚨 **THIS NOTE IS A PYTHON COMMENT AND NOT A SQL ONE, AND THAT COST TWO CI RUNS.**
    # `ci/check_page_queries.py` normalises a query to a single line before executing it, so
    # every `--` comment swallows the rest of the statement — `syntax error at end of input`.
    # An earlier draft also carried a literal per-cent, which the driver reads as a parameter
    # marker — `dict is not a sequence`. **Two different failures from prose inside a query
    # string, neither visible locally because the unit tests stub `query` (R-538's class).**
    # ✅ Nothing goes between the triple quotes but SQL.
    return query("""
        select season, week, poll_name, rank, team_display, team_slug,
               first_place_votes, points, as_of_ts,
               color_on_light, color_on_dark
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


# 🚨 A167 (cfdb-main-R-1310). THE SCOREBOARD COLUMN IS SIZED TO THE SCOREBOARD, NOT TO A
# PERCENTAGE — and A165's 40% is the whitespace Marc is pointing at.
#
# > **MARC, Today v06:** *"Scoreboard - unneccessary white space to the right of the scoreboard."*
#
# ⚠️ **A165 WIDENED THIS COLUMN 26% -> 40% TO FIX A TRUNCATION THAT WAS NEVER IN IT**, and its
# own measurement said so at the time: *"+54% width, ellipsised count UNCHANGED at eleven"*. The
# clip was `.cfdb-sb-team`'s fixed width inside the nested table, which the same round fixed
# separately at 13rem (cfdb-main-R-1301). **The percentage bought nothing and the whitespace is
# what is left of it.**
#
# 📊 MEASURED IN CHROMIUM by rendering `_scoreboard` at 4, 5, 6, 9 and 13 periods:
#
#     4 periods (regulation)   425.6px   5 thead cells
#     5 periods (overtime)     463.2px   6 thead cells
#     6, 9, 13 periods         463.2px   ← IDENTICAL. It does not keep growing.
#
# 🚨 **AND THAT CAP IS THE DATA'S SHAPE, NOT A COINCIDENCE**: `_quarter_cells` draws ONE overtime
# column because `{side}_overtime_points` is a single total with no per-overtime breakdown
# published. Real games reach **13 periods** (Illinois at Penn State, 2021, nine overtimes) and
# the scoreboard is the same width for all of them. **So the natural width has exactly TWO
# values and the column can be derived rather than guessed.**
#
# ✅ THIS IS `layout[1]`'s OWN PATTERN, APPLIED TO THE COLUMN BESIDE IT: derived from the frame,
# because a constant *"would be wrong the first week nothing goes to overtime"* — and equally
# wrong the first week something does.
_SCOREBOARD_REGULATION_PX = 426
_SCOREBOARD_OVERTIME_PX = 464
_SCOREBOARD_GUTTER_PX = 12


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


# ── THE TWO CELLS FOUR SECTIONS SHARE ───────────────────────────────────────────────────────
#
# 🚨 MARC ASKED FOR THE SAME TWO THINGS UNDER FOUR HEADINGS — Most Exciting, Biggest Upsets,
# Biggest Underdog Covers and Leaderboards — and Cowork's reading of the spec is the rule this
# section exists to obey: **"Building them four times is four chances to diverge."**
#
# ✅ AND THE TEAM HALF WAS ALREADY BUILT. `table.team_cell` has drawn logo + rank badge + name
# since Schedule, and `rankings.py`, `stats.py`, `standings.py` and `teams.py` all call it. A144
# added NOTHING to it: what was missing was the RECORD, and R-129 says the record cannot live
# inside it — *"the record leaves the anchor entirely rather than being styled to look
# non-clickable"*. So the record moved to `table.record_span` beside it, out of `schedule.py`,
# and these two functions are the composition rather than a third producer.

def _team_identity(row, side: str, slug_field=None, display_field=None,
                   logo_field=None, rank_field=None,
                   record_field=None, record_after_field=None) -> str:
    """Rank + logo + hyperlinked name + record, for one side of a row.

    🚨 THE NAME IS THE LINK AND THE ROW IS NOT ONE, WHICH IS A CONSTRAINT AND NOT A STYLE.
    `table.render` wraps a cell's content in the ROW's anchor when the table has a `link_builder`,
    and nested anchors are invalid HTML with the OUTER one winning — so a reader would click the
    team name and land on the game. **Every table using this cell therefore passes no
    `link_builder`**, which `_espn_link`'s own comment already established for Most Exciting and
    `test_no_table_with_a_linked_team_name_also_links_its_rows` now asserts for all four.

    ⚠️ THE RECORD SITS OUTSIDE THE ANCHOR — R-129, and Schedule reaches the same layout the same
    way. Inside it, the record would be dead text under a pointer cursor.

    🚨 A164: THE TWO ARE WRAPPED IN `.cfdb-identity` SO THEY SHARE A LINE — Marc asked three
    times in Today v04 (*"Records should be inline with the Team Name, not line below it"*,
    twice, and *"Team - Ranks inline with team name, not below"*). **One cell, seven tables, one
    fix.**

    📊 THE CAUSE WAS MEASURED AND IT IS NOT THE ONE IT LOOKS LIKE. `.cfdb-teamlink` is
    `display:flex`, which is a BLOCK-LEVEL box, so the record sibling could never share its line
    at any width. The suspected culprit — `.cfdb-table .cfdb-team`'s `max-width:100%` — was
    tested in Chromium and exonerated: neutralising it left the record wrapped on 4 of 4 rows,
    as did deleting that rule's whole ellipsis cluster, while inline-flex alone fixed 3 of 4.
    ⚠️ **THE WRAPPER ADDS A LEVEL RATHER THAN EDITING EITHER RULE**, because `.cfdb-teamlink`,
    `.cfdb-team` and `.cfdb-team-record` are all read outside this function — `schedule.py`
    composes the record differently, and the game cards and the legend read the name. The
    geometry belongs to the cell that has the problem.

    ⚠️ THE COLUMN NAMES ARE ARGUMENTS BECAUSE THE RELATIONS GENUINELY DISAGREE, and that is worth
    one parameter rather than one copy: `srv_game` spells a side `home_team_slug` / `home_rank`,
    `srv_game_team` spells the same facts `team_slug` / `team_rank` / `record_before_display`.
    The defaults are `srv_game`'s, because three of the four call sites read that view.
    """
    prefix = f"{side}_" if side else ""
    slug_field = slug_field or f"{prefix}team_slug"
    display_field = display_field or f"{prefix}team_display"
    logo_field = logo_field or f"{prefix}logo_url"
    rank_field = rank_field or f"{prefix}rank"
    record_field = record_field or f"{prefix}team_record_display"
    if record_after_field is None and not side:
        record_after_field = None
    elif record_after_field is None:
        record_after_field = f"{prefix}team_record_after_display"

    cell = table.team_cell(row, slug_field, display_field, logo_field, rank_field)
    href = table.team_link(slug_field)(row)
    if href:
        cell = f"<a class='cfdb-teamlink' href='{href}' target='_self'>{cell}</a>"
    record = table.record_span(row, record_field, record_after_field)
    return f"<span class='cfdb-identity'>{cell}{record}</span>"


# ── A166: THE PLAYER CARD, AND WHY IT IS A FOURTH SHAPE RATHER THAN A COPY ────────────────
#
# > **MARC, Today v04:** *"Swtich to player cards. 3 columns for Yardage (QB, Receiving,
# > Rushing). Include top 10 for each category. The player card needs to indicate the Team
# > logo/name"* — and, in v05, *"Player Cards haven't made it in yet."* **He asked twice.**
#
# 📊 R-855 — READ THE EXISTING PATHS, THEN TEST THEM FOR THE CASE AT HAND. There were three
# player renderings here and this takes something from each without copying any:
#
#     today.py `_player_identity`   ✅ TAKEN WHOLE. Jersey/name/year/position with every part
#                                     optional and none substituted (R-084), the `#7.0` float
#                                     guard, and the one absence worth naming. **Not
#                                     reimplemented — called.**
#     today.py `_team_identity`     ✅ TAKEN WHOLE, which is what carries `table.team_cell` ->
#                                     `identity.logo_or_monogram` (AC-G.28) and R-121's NaN
#                                     guard. **A card that built its own <img> would re-open a
#                                     bug that cost this site two teams in a screenshot.**
#     matchup.py's 150px card       ❌ READ AND NOT USED. It is a two-line PREVIEW card in
#                                     session B's file; importing from a view would couple two
#                                     pages, and editing it is not this round's to do.
#     team.py's `Col("jersey","#")` ❌ THE OPPOSITE TRADE — a whole column per fact. A board of
#                                     ninety cards cannot spend a column on two characters.
def _player_card(row, stat_label: str) -> str:
    """One player, as MATCHUP's card — plus the team line Today needs and Matchup does not.

    > **MARC, Today v06:** *"Prefer the player card from the Matchup, but want to add in the team
    > logo/name for this Today page b/c there's no context about what team they play for on the
    > Today page."*

    🚨 **A166 BUILT A DIFFERENT SHAPE ON INSTRUCTION AND HE PREFERS THIS ONE.** Its prompt said of
    Matchup's card *"Read it for its proportions; do not import from it and do not edit it"*, and
    the round obeyed and recorded it as READ AND NOT USED. **He has seen both.** ✅ The identity
    row is now `identity.player_row` — promoted to `lib/`, called by both pages, **not copied and
    not imported across views** (cfdb-main-R-1308).

    ⚠️ **THE TEAM LINE IS THE HALF HE SAYS IS MISSING AND IT IS THE REASON HE ASKED**, so it goes
    through `_team_identity` -> `table.team_cell` -> `identity.logo_or_monogram`. **A card that
    builds its own `<img>` re-opens R-121's NaN bug that cost this site two teams in a
    screenshot** — A166 established that and it has not changed.

    🚨 **THE BORDER STAYS NEUTRAL, AND THAT IS DECIDED BY DATA RATHER THAN TASTE
    (cfdb-main-R-1309).** Matchup's card borders in the team's colour through `_accent`, and the
    prompt's recommendation was to promote that too. 📊 **`srv_player_game_log` publishes NO
    colour column at all** — checked against `information_schema` on live published serving, not
    against a model file (§2.2.1c.2). The page reads one relation with a single-table SELECT and
    no join (§4.2.1), **so there is no colour here to draw with.** ✅ **`_accent` was therefore
    NOT promoted**: moving a function to `lib/` for a caller that cannot yet use it is
    speculative, and the real prerequisite is a model change. **Reported, not worked around.**
    """
    # The same formatter the tables use — `Col(kind="num")` calls exactly this, so a card and a
    # row can never disagree about how many decimal places a stat has.
    value = fmt.number(row.get("stat_value"), "stat_value")
    return (f"<div class='cfdb-card'>"
            f"{identity.player_row(row)}"
            # ⚠️ THE STAT READS SECOND, straight after the name: it is the reason the card is on
            # the board. The team line follows it — Marc asked for the team as CONTEXT, which is
            # a thing you check after you have read who and what.
            f"<div class='cfdb-card-stat'>"
            f"<span class='cfdb-card-value'>{value}</span>"
            f"<span class='cfdb-card-unit'>{fmt.text(stat_label)}</span></div>"
            f"<div class='cfdb-card-team'>{_team_identity(
                row, '', slug_field='team_slug', display_field='team_display',
                logo_field='team_logo_url', rank_field='team_rank',
                record_field='record_before_display')}</div>"
            f"</div>")


def _player_card_grid(columns, stat_label: str) -> None:
    """Three columns of cards, one per category. `columns` is [(heading, frame), ...].

    🚨 **THE TOP-N IS PER COLUMN, WHICH IS A DIFFERENT QUESTION FROM THE ONE THE TABLE ASKED.**
    `_player_board` was called ONCE per board with three categories and `limit {DEPTH}`, so its
    list was a BLENDED top-N — on the yardage board that is passing yards crowding out rushing,
    because a passer gains more yards than a runner. Marc asked for *"top 10 for each
    category"*, so each column runs its own query.

    ⚠️ **NINE CALLS WHERE THERE WERE THREE, AND THE SAME SINGLE-TABLE SELECT EVERY TIME** — no
    new SQL string, no join, and the display-only contract is untouched (§4.2.1). ✅ A window
    function would collapse it to three and was NOT reached for: `@st.cache_data` already wraps
    `query`, the nine differ only in two bind parameters, and adding a `row_number()` to dodge a
    cost nobody has measured is the optimisation this project keeps writing rules about.

    ⚠️ **EVERY PART IS OPTIONAL EXCEPT THE HEADING.** A column whose query returns nothing draws
    its heading and an honest line rather than vanishing, because a missing column in a
    three-column grid reads as a layout fault rather than as an absence (AC-G.11).
    """
    cells = []
    for heading, frame in columns:
        if frame is None or frame.empty:
            body = "<div class='cfdb-card-none'>Nothing in this category yet.</div>"
        else:
            body = "".join(_player_card(row, stat_label)
                           for _index, row in frame.iterrows())
        cells.append(f"<div class='cfdb-cardcol'>"
                     f"<div class='cfdb-cardcol-head'>{fmt.text(heading)}</div>{body}</div>")
    st.markdown(f"<div class='cfdb-cardboard'>{''.join(cells)}</div>",
                unsafe_allow_html=True)


def _commentary(row, scope, stacked: bool = False) -> str:
    """The game's marks and the ESPN link, in one cell. `stacked` puts the link on its own line.

    > **MARC, Today v01:** *"In the Commentary column, add the same Matchup and outcome glyphs as
    > on the Schedule page. Put them in the top row of the cell, the ESPN link below in the same
    > cell."*

    🚨 **THAT SECOND SENTENCE WAS NEVER IMPLEMENTED, AND THIS DOCSTRING QUOTED IT FOR FOUR ROUNDS
    AS THOUGH IT HAD BEEN (cfdb-main-R-1230).** `.cfdb-commentary` had NO CSS RULE of any kind, so
    the span was inline and the link fell below the marks only where the column happened to be too
    narrow to hold both. 📊 A164 measured it in Chromium on the real page: **Most Exciting put
    ESPN on its own line at a 1300px viewport and on the SAME line at 1600px** — the same markup,
    the layout flipping on viewport alone — while the two recap panels kept it inline at both.
    **A layout that is true by accident on one panel reads exactly like a layout that was chosen.**

    ✅ **NOW IT IS A DECISION.** `.cfdb-commentary` is an inline flex row with a declared gap;
    `stacked=True` adds `.cfdb-commentary-stacked` and makes it a column. ⚠️ **AND THE TWO ARE
    DELIBERATELY DIFFERENT, because Marc asked for two different things in Today v04** — a
    *"carriage return"* on Most Exciting, a *"Space"* on Upsets and Underdogs, whose measured gap
    was exactly 0px. Averaging them into one rule would have satisfied neither sentence.

    ⚠️ **THE WINNER TRIANGLE IS GONE — Marc, Today v04, in all three panels.** `glyphs.winner`
    keeps its other caller — `matchup.py`'s `_winner_glyph`, asserted rather than assumed — so
    nothing here orphans it. `glyphs.result_strip` STAYS: his *"diamond outcome glyph"* is the strip's, and he
    was positioning the link relative to it rather than asking for it to go.

    🚨 *"THE SAME … GLYPHS AS ON THE SCHEDULE PAGE"* MEANT SCHEDULE'S *Game* COLUMN CELL, AND MARC
    SETTLED IT WITH A PICTURE — a column headed **Game**, then a lined rectangle, a filled circle, a
    filled square and a hollow diamond. That is `schedule.py:512`'s `Col("game", "Game", …)`: the
    details glyph followed by the three result indicators.

    ⚠️ **A144 READ IT AS THE MATCHUP-OUTLOOK VERDICT AND FLAGGED THE AMBIGUITY AT THE TIME** —
    *"Marc's phrase 'as on the Schedule page' is the imprecise part of his sentence"*. **So this is
    a corrected reading of MARC, not a correction of A144**, and A144's measurement that Today
    needed none of Schedule's producers was right for the reading it had.

    ✅ **AND THE STRIP IS APT HERE IN A WAY THE OUTLOOK WOULD NOT HAVE BEEN.** *Upset · covered ·
    over* are facts about a FINISHED game, which is all this panel contains. The outlook is a
    PRE-GAME verdict — which is why choosing among its three variants needed a question put to Marc
    at all. **A cell saying "the favorite lost and the total went over" is doing the job the column
    is named for.**

    ── THE ORDER, AND WHY THE ANCHORS ARE SAFE ────────────────────────────────────────────────

    Details glyph, then the outcome arrow, then the strip: the affordance first, then who won, then
    what the market made of it — escalating specificity, left to right.

    🚨 **TWO ANCHORS IN THIS CELL AND NEITHER IS INSIDE THE OTHER.** The details glyph goes to the
    matchup; ESPN goes out. That is fine. What is not is either of them inside the ROW's anchor —
    `table.render` wraps a cell in it when the table has a `link_builder`, nested anchors are
    invalid HTML and the OUTER one wins, so a reader would click ESPN and stay on the site.
    **Every table drawing this cell passes no `link_builder`**, asserted for all four.

    ⚠️ **THE STRIP SITS OUTSIDE THE DETAILS ANCHOR, WHICH IS SCHEDULE'S OWN RULE CARRIED OVER**:
    *"NOT inside the anchor: it is three states of information, not a destination, and a pointer
    cursor over it would say otherwise."*

    ✅ `glyphs.winner` STILL RETURNS `None` FOR FOUR REASONS AND EXACTLY ONE OCCURS HERE — a tie.
    A144 established that; it is not re-opened.
    """
    href = scope.link("matchup", game_id=row.get("game_id"))
    details = (f"<a class='cfdb-cell-link-alt' href='{href}' target='_self' "
               f"title='Open the matchup'>"
               f"<span class='cfdb-details'>{table.DETAILS_GLYPH}</span></a>")
    stack = " cfdb-commentary-stacked" if stacked else ""
    return (f"<span class='cfdb-commentary{stack}'>"
            f"<span class='cfdb-commentary-marks'>{details}"
            f"<span class='cfdb-strip-gap'></span>{glyphs.result_strip(row)}</span>"
            f"{_espn_link(row)}</span>")


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
    answer; see `winprob.sparkline_svg`.

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
    # 🚨 A144. THE NAME CELL IS NOW THE SHARED TEAM-IDENTITY CELL — Marc: *"Add Logo, Rank,
    # Record to Scoreboard section"* — and it is the SAME producer the three list panels call, so
    # the four cannot drift. The scoreboard's own law is untouched: away first, always.
    #
    # ⚠️ IT GOES IN THE `<th scope='row'>` IT ALREADY HAD, so the grid's first-row column widths
    # (see the header note below) are decided by the same cell that decided them before. A new
    # column would have taken the alignment out from under every scoreboard on the page.
    body = (side_row(_team_identity(row, "away"), row.get("away_points"), away_pairs,
                     "cfdb-sb-away")
            + side_row(_team_identity(row, "home"), row.get("home_points"), home_pairs,
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
    # ✅ A153. THE CAPTION SAYS "lead changes" AGAIN AND IT IS TRUE THIS TIME — the whole point of
    # the two-round sequence.
    #
    # 🚨 MARC MET THE ORIGINAL DEFECT AT THIS SENTENCE. It said *"Ranked by lead changes in the
    # fourth quarter"* while `MOST_EXCITING_ORDER` ranked on `lead_changes_fourth_quarter_by_clock`
    # — the MODEL'S WIN PROBABILITY crossing 0.5, per that column's own header. His report was
    # *"Lead changes in 4th quarter doesn't seem accurate… Math isn't mathin'."* **A true-sounding
    # label on a different number, which is §4.3's worst form.**
    #
    # ⚠️ A152 REWROTE IT TO DESCRIBE THE CROSSINGS HONESTLY, *because the ranking had not moved
    # yet* — a caption must describe what the panel does today, not what it is about to do.
    # ✅ **A153 moves the ranking, so the sentence moves back.** Neither round left it false.
    #
    # ⚠️ AND THE CHART SENTENCE IS RE-READ AGAIN RATHER THAN ASSUMED SETTLED (cfdb-wta-R-1024,
    # R-1043 — this class has bitten four rounds running). A152 changed *"above the line the home
    # side was ahead"* to *"the model gave the home side the better chance"* precisely to stop a
    # reader carrying "lead" across from the ranking sentence. 🚨 **That fix is MORE necessary now,
    # not less**: the ranking sentence says "lead changes" again, so "ahead" one clause later would
    # read as the scoreboard when the chart plots a probability. **It stays as A152 wrote it.**
    st.caption(
        "Ranked by **how many times the lead actually changed hands in the fourth "
        "quarter**, then by how close the game stayed after it — not by CFBD's excitement "
        "index, which ranked the week's best fourth quarter 31st of 86. A tie is not a lead, "
        "so a game that drew level and went ahead again changed hands once. Each scoreboard "
        "reads away over home, quarter by "
        "quarter, with overtime shown separately and the final at the right. The chart "
        "is the home side's win probability on every play against the game clock, "
        "unsmoothed and filled from even — above the line the model gave the home side the "
        "better chance, below it the away side. Quarter marks fall at the same place on every chart, so a "
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
    top = df[df["scoreboard_lead_changes_fourth_quarter"].notna()].head(10)

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
    # ⚠️ `iterrows`, NOT `itertuples`: `curve_label` reads columns with `.get` so a missing one
    # is an absence rather than an AttributeError, and a namedtuple has no `.get`.
    labels = {row["game_id"]: winprob.curve_label(row, by_game.get(row["game_id"]))
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

        The panel filters on `scoreboard_lead_changes_fourth_quarter` being non-null (A153; it
        was `lead_changes_fourth_quarter` and the two are NULL on the same 3 games of 1,898,
        measured — the ranking moved, the population did not), and that column and
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
        # 🚨 `curve_label` OWNS THE `is False` TRAP, AND A138's PANEL TEST CAUGHT IT ON ITS FIRST
        # RUN. A boolean arriving out of a pandas frame is `numpy.bool_(False)`, which is NOT the
        # Python `False` singleton, so `reaches is not False` was True for every row and the whole
        # truncation branch would have been dead code that reads as handled.
        text, is_cut = labels.get(row.game_id, ("", False))
        return winprob.sparkline_svg(points, label=text, is_cut=is_cut)

    # 🚨 THE CURVE COLUMN IS SIZED TO THE WIDEST CHART IN THIS FRAME, AND IT HAS TO BE.
    # `.cfdb-table` is `table-layout:fixed`, so without a colgroup every column takes an equal
    # share and a 254px overtime chart overflows a 137px cell. Reading B — shared SCALE, not
    # shared extent — means the charts differ in width by design, so the column is the widest of
    # them and the narrower ones simply do not fill it. Computed from the data rather than from a
    # constant, because a constant would be wrong the first week nothing goes to overtime.
    widest = max((winprob.chart_width(by_game[game_id])
                  for game_id in top["game_id"] if game_id in by_game),
                 default=winprob.chart_width(None))
    # 🚨 A165. THE SCOREBOARD TAKES 40% AND THE THREE LEAD COLUMNS ARE PINNED NARROW.
    # 📊 **THE WIDTH ALONE FIXES NOTHING AND THAT WAS MEASURED BEFORE IT WAS BUILT** — taking
    # the Scoreboard column from 288px to 443px left the ellipsised-name count at 11, because
    # the name is clipped by `.cfdb-sb-team`'s own fixed width inside the nested table. **That
    # rule is where the truncation fix actually is** (`theme.py`, cfdb-main-R-1301); this
    # layout is what gives the wider cell somewhere to sit.
    # ⚠️ 52px IS MARC'S NUMBER, NOT A ROUND ONE. He asked to *"Reduce by at least 50%"*, and
    # these columns measured 104.3px each at a 1300px viewport — so 52px is exactly that, and
    # 56px (a 46% cut) would have missed it. 📊 Swept against the header row, which is what
    # pins the floor: at 56, 52, 50 and 46px the header stays 44.4px and does NOT wrap, so the
    # binding constraint is the ask rather than the label. The freed 157px goes to the
    # scoreboard rather than being shared out.
    # 🚨 A167: THE SCOREBOARD COLUMN IS NOW DERIVED TOO — see `_SCOREBOARD_REGULATION_PX`.
    # ⚠️ `home_periods` RATHER THAN A LEAD-CHANGE COUNT: overtime lead changes can be 0 in a game
    # that went to overtime, so the column that decides the WIDTH must be the one that decides
    # whether an overtime CELL is drawn, which is what `_quarter_cells` reads.
    periods = pd.to_numeric(top.get("home_periods"), errors="coerce")
    scoreboard_px = (_SCOREBOARD_OVERTIME_PX if periods is not None and (periods > 4).any()
                     else _SCOREBOARD_REGULATION_PX)
    layout = [f"{scoreboard_px + _SCOREBOARD_GUTTER_PX}px", f"{widest + 12}px",
              "52px", "52px", "52px", "auto", "auto", "auto"]

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
            # 🚨 A153. THE PANEL SHOWS THE NUMBER IT RANKS ON, which is the whole of Marc's
            # sentence: *"Show actual scoreboard lead changes instead."* Ranking on the scoreboard
            # count while still DISPLAYING the win-probability crossings under a column headed
            # "lead changes" would have left the false label he reported exactly where it was, on
            # a panel ordered by a number he could not see.
            # 🚨 A165. THE LABELS CARRY THE NOUN ONCE, IN THE CAPTION, NOT THREE TIMES IN THE
            # HEADER ROW. Marc: *"The Lead Change columns need to use less horizontal space.
            # Reduce by at least 50% horizontally."*
            # 📊 THESE COLUMNS WERE WIDE BECAUSE OF THEIR HEADER TEXT, NOT THEIR NUMBERS — every
            # value is a single digit. `4TH-QTR LEAD CHANGES` wrapped to two lines, which made
            # the HEADER ROW 59.4px at a 1300px viewport against 44.4px at 1600px where it did
            # not wrap. ✅ Shortening the labels returns that 15px **and** lets the columns be
            # pinned narrow without the header growing back — which is the trap: a density win
            # in the body paid for by a taller header is not a win.
            Col("scoreboard_lead_changes_fourth_quarter", "4th qtr", kind="num"),
            Col("scoreboard_lead_changes_overtime", "OT", kind="num"),
            # ⚠️ A164. MARC MOVED A DISPLAYED COLUMN, NOT THE SORT — Today v04: *"Move Lead
            # Changes Game between OT Lead Changes and How Close Late."* `MOST_EXCITING_ORDER`
            # is untouched and the caption still describes the ordering, which is unchanged.
            # ✅ `layout` DOES NOT MOVE AND THAT IS ASSERTED, NOT ASSUMED: it pins only the first
            # two columns and the six that follow are all "auto", so two of them swapping is
            # invisible to it. `test_most_exciting_layout_pins_only_the_first_two_columns` holds
            # that property, because a `layout` silently out of step with the columns shows up
            # only on a wide viewport.
            Col("scoreboard_lead_changes", "Game", kind="num"),
            Col("mean_distance_from_even_fourth_quarter_onward", "How close, late", kind="num", dp=3),
            Col("excitement_index", "Excitement", kind="num", dp=1),
            # 🚨 A144. THE OUTCOME GLYPH JOINS THE LINK IN ONE CELL — Marc: *"Put them in the
            # top row of the cell, the ESPN link below in the same cell."* `_commentary` says
            # which of `glyphs.winner`'s four None-reasons can occur on a panel of completed
            # games, and why the Matchup half of his sentence is not here.
            # ⚠️ `stacked=True` IS MARC'S "carriage return", AND IT IS THE ONLY PANEL THAT GETS
            # IT. The two recap panels get the horizontal gap he asked for there instead —
            # see `_commentary`, which measured all three before choosing.
            Col("espn", "Commentary", render=lambda r: _commentary(r, scope, stacked=True)),
        ], layout=layout, anchor="most-exciting",
            # ⚠️ PLAIN TEXT, NOT MARKDOWN. `table.render` puts this straight into an HTML
            # `<caption>` element — it is not `st.caption` — so `**bold**` renders as four
            # literal asterisks. Caught in the raster; every other `caption=` on this page is
            # plain prose for the same reason.
            caption="Lead changes: fourth quarter, overtime, whole game. Ordered by "
                    "fourth-quarter lead changes, then by mean distance from an even win "
                    "probability from the fourth quarter onward (lower is closer)."))


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


# 🚨 THE GROUPS THIS PAGE CAN ACTUALLY DRAW. R-178's law, and it cuts BOTH ways: *"the legend
# cannot draw a mark the row does not"* — and it must not omit one the row can.
#
# ⚠️ `glyphs.entries()` OFFERS TWO GROUPS AND TODAY DRAWS ONE. The Matchup verdict is not on
# `srv_game` at any grain this page reads (see `_commentary`), so listing it would explain a mark
# no row here can produce — which is the same defect as omitting one, pointed the other way.
# **The day a Matchup outlook reaches this panel, this tuple is the one line that changes.**
# 🚨 THE GROUPS THIS PAGE CAN ACTUALLY DRAW. R-178's law, and it cuts BOTH ways: *"the legend
# cannot draw a mark the row does not"* — and it must not omit one the row can.
#
# ⚠️ A147 ADDED A SECOND FAMILY AND THE MATCHUP VERDICT IS STILL NOT IN IT. `glyphs.entries()`
# offers *Matchup* and *Outcome*; this page draws **Outcome** and now the result strip's *Against
# the line*, and it still cannot draw the Matchup outlook — there is no outlook column on
# `srv_game` at any grain (A144 measured it). **Listing it would explain a mark no row here can
# produce**, which is the same defect as omitting one, pointed the other way.
# 🚨 A164 (cfdb-main-R-1143). THIS WENT FROM ("Outcome",) TO EMPTY, AND A TEST FORCED IT.
# Marc removed the winner triangle from the Commentary cell in Today v04 — so `glyphs.winner` is
# no longer called anywhere on this page, and "Outcome" became a group the legend explained and
# no row could draw. ✅ **R-178's law caught it in the same run**:
# `test_the_legend_lists_every_mark_today_can_draw_and_invents_none` builds its expectation by
# RENDERING the real cell rather than by reading this tuple, so deleting the arrows turned it red
# immediately. ⚠️ **A legend entry for a mark that is gone is not a harmless leftover: it tells a
# reader to look for something the page will never show.**
# **The day an outcome mark returns to this page, this tuple is the one line that changes.**
LEGEND_GROUPS_DRAWN = ()


def _legend() -> None:
    """The legend, as a popover button. A144, extended by A147.

    > **MARC:** *"Need the legend button to help with the icons"*

    ✅ **`st.popover` IS SCHEDULE'S OWN CHOICE AND IT IS ALREADY A BUTTON**, so the site has one
    legend affordance rather than two (§4.3). Schedule's own reasoning carries unchanged: *"a legend
    is consulted WHILE looking at the thing it explains, and a modal covers exactly what the reader
    is comparing against."*

    🚨 IT ENUMERATES FROM THE MODULE, NEVER FROM A PARALLEL LIST — and A147 added a second
    enumerator rather than merging the two. `glyphs.entries()` answers *what did we expect* and
    *who won*; `glyphs.strip_entries()` answers *what did the market make of it*. **A flat list
    would let this legend inherit Schedule's groups and Schedule's inherit the Matchup verdict**,
    and neither page can draw the other's.

    ⚠️ THE DETAILS GLYPH IS LISTED BY HAND AND THAT IS THE ONE ENTRY WITH NO ENUMERATOR BEHIND IT,
    because it has no producer to enumerate: it is `table.DETAILS_GLYPH`, a single constant, drawn
    by `_commentary` directly. **Said out loud rather than hidden, because every other entry on this
    legend is derived and this one is not.**
    """
    groups = [(title, [(glyphs.render(mark, size="font-size:.95rem"), mark.title)
                       for mark in marks])
              for title, marks in glyphs.entries() if title in LEGEND_GROUPS_DRAWN]
    groups.append(("Game", [
        (f"<span class='cfdb-details'>{table.DETAILS_GLYPH}</span>", "Open the matchup")]))
    groups += glyphs.strip_entries()
    with st.popover("Legend", use_container_width=False,
                    help="What every mark on this page means"):
        for title, rows in groups:
            st.markdown(
                f"<div class='cfdb-legend-side'>"
                f"<div class='cfdb-legend-title'>{title}</div>"
                + "".join(
                    f"<div class='cfdb-legend-row'>"
                    f"<span class='cfdb-legend-key'>{swatch}</span>"
                    f"<span>{label}</span></div>" for swatch, label in rows)
                + "</div>", unsafe_allow_html=True)


def _favorite_side(row) -> str:
    """Which side of the fixture the spread made favorite. `graded` guarantees it is one of two.

    ⚠️ THE RECAP LISTS CARRY `favorite` AND `opponent` AS DISPLAY-NAME STRINGS, which is enough to
    print a name and not enough to draw a team. Logo, rank, slug and record are all spelled
    `home_*` / `away_*` on the row, so the cell needs the SIDE rather than the label — and the
    side is already on the frame as `spread_favorite_side`, which is what `graded` filters on.
    """
    return "home" if row.get("spread_favorite_side") == "home" else "away"


def _favorite_cell(row) -> str:
    """The favorite, as the shared team-identity cell."""
    return _team_identity(row, _favorite_side(row))


def _underdog_cell(row) -> str:
    """The other side. Named for what it IS on both lists rather than for a column.

    ⚠️ ON THE UPSETS LIST THIS TEAM IS "Beaten by" AND ON THE COVERS LIST IT IS THE "Underdog" —
    the same side of the same fixture under two headings, which is exactly why one producer draws
    both and the heading is the caller's word.
    """
    return _team_identity(row, "away" if _favorite_side(row) == "home" else "home")


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
        # ⚠️ THE TWO TEAM COLUMNS ARE THE SHARED CELL, not the display-name strings `favorite`
        # and `opponent` this function derives. Those stay on the frame because the SORT still
        # keys on them — a rendered cell of HTML is not sortable, and `Col.field` is what
        # `apply_sort` reads (A141).
        [Col("favorite", "Lost", render=_favorite_cell),
         Col("opponent", "Beaten by", render=_underdog_cell),
         Col("spread", "Favored by", kind="num", dp=1),
         # MARC: *"Margin should be integer."* `fmt.precision_for` matches the substring
         # "margin" and returns 1, so this needed saying explicitly rather than by omission.
         Col("fav_margin", "Margin", kind="num", dp=0),
         # MARC: *"Market gave them should be ##.#%"* — `fmt.percent`, which A144 added because
         # the site had no percent shape and was about to get its second inline f-string.
         Col("fav_win_prob", "Market gave them",
             render=lambda r: fmt.percent(r.get("fav_win_prob"))),
         Col("espn", "Commentary", render=lambda r: _commentary(r, scope))],
        caption="Ranked by the loser's pregame market-implied win probability.",
        anchor="how-the-week-went-against-the-market")

    st.markdown("**Biggest underdog covers**")
    st.caption(
        "Underdogs the market priced too low, ranked by how far past the number they finished. "
        "These are graded against the spread rather than the result, so a team here may still "
        "have lost the game.")
    table.render(covers.assign(underdog=covers["opponent"], beat=covers["ats"].abs()),
                 [Col("underdog", "Underdog", render=_underdog_cell),
                  Col("favorite", "Favorite", render=_favorite_cell),
                  Col("spread", "Getting", kind="num", dp=1),
                  Col("beat", "Covered by", kind="num", dp=1),
                  Col("espn", "Commentary", render=lambda r: _commentary(r, scope))],
                 caption="Ranked by points beyond the closing spread.",
                 anchor="how-the-week-went-against-the-market")

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
                       f"\u201chas a gap\u201d is a floor, not a measurement.{caveat}",
                 anchor="the-weeks-movers"))


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

    # ⚠️ THE DECLARED VIEW FOLLOWED THE QUERY. `test_the_views_named_in_sections_are_exactly_the
    # _views_the_module_reads` caught this the moment `_team_yardage` changed relation — the
    # section still named `srv_team_game_log` while the module read `srv_game_team`, and a
    # degraded-state card would have named a view this panel no longer touches.
    with states.section("srv_game_team", dataset=DATASETS["srv_game_team"]):
        teams = _team_yardage(scope, depth)
        st.markdown("**Team yardage**")
        states.render_or_state(
            teams, "srv_game_team",
            "The team yardage board would be here.",
            f"No completed team box scores for {scope.describe()}. Box scores start in 2024.",
            renderer=lambda d: table.render(d, [
                # 🚨 THE SAME CELL THE THREE GAME-GRAIN PANELS DRAW, reading this relation's
                # spelling of the four facts. `srv_game_team` publishes no after-record, so the
                # last argument is omitted and `record_span` shows the before-record — see
                # `_team_yardage`.
                Col("team_display", "Team",
                    render=lambda r: _team_identity(
                        r, "", slug_field="team_slug", display_field="team_display",
                        logo_field="team_logo_url", rank_field="team_rank",
                        record_field="record_before_display")),
                Col("opponent", "Opponent"),
                Col("total_yards", "Total", kind="num"),
                Col("rushing_yards", "Rush", kind="num"),
                Col("passing_yards", "Pass", kind="num"),
            ], caption="Ranked by total offense, with each team's record going into the game.", anchor="leaderboards"),
        )

    # 🚨 A166: THREE CARD BOARDS, NINE COLUMNS, AND THE THIRD SPLITS ON A DIFFERENT AXIS.
    #
    # ⚠️ **THE DEFENSIVE BOARD IS NOT THE YARDAGE BOARD WITH A DIFFERENT ARGUMENT**, and copying
    # the call would have silently produced one column or three empty ones. Yardage and
    # touchdowns split on `stat_category` at a fixed `stat_type`; defence is ONE category
    # (`defensive`) split on THREE `stat_type`s.
    #
    # 📊 ENUMERATED FROM LIVE PUBLISHED SERVING RATHER THAN FROM THE CAPTION THAT CLAIMED IT
    # (§2.2.1c.2, and §2.5's second question — a value that exists is not a value that has rows).
    # 2026, `stat_category = 'defensive'`, every type present with its row count:
    #
    #     PD 15,372 · QB HUR 15,372 · SACKS 15,372 · SOLO 15,372 · TD 15,372 · TFL 15,372 ·
    #     TOT 15,372        (9,062 distinct players in each)
    #
    # ✅ So `TOT`/`TFL`/`SACKS` is the right trio and the old caption was right — **but it is
    # `SACKS`, not `SACK`**, which is the sort of thing a guess gets wrong and a query does not.
    # ⚠️ `SOLO`, `PD`, `QB HUR` and `TD` are equally populated and are NOT drawn: Marc named
    # tackles, TFL and sacks, and a fourth column nobody asked for is a decision, not a freebie.
    with states.section("srv_player_game_log", dataset=DATASETS["srv_player_game_log"]):
        st.markdown("**Player yardage**")
        st.caption("Top players by yards in each category, deepest first. "
                   "\"QB\" is the passing column — it is not filtered on position, and the "
                   "passing leader has been a quarterback in every week measured.")
        yardage = [(label, _player_board(scope, depth, (category,), "YDS"))
                   for label, category in (("QB", "passing"),
                                           ("Receiving", "receiving"),
                                           ("Rushing", "rushing"))]
        states.render_or_state(
            # ⚠️ THE CONCATENATION DECIDES THE STATE, THE THREE FRAMES DRAW THE GRID. The state
            # machinery asks one question — is there anything at all? — and three columns that
            # are each separately empty is the same answer as one empty board. The renderer
            # ignores the frame it is handed and reads the columns it closed over, which is why
            # a column that IS empty still draws its heading.
            pd.concat([frame for _label, frame in yardage]) if yardage else pd.DataFrame(),
            "srv_player_game_log",
            "The player yardage board would be here.",
            f"No player box scores for {scope.describe()}. Box scores start in 2024.",
            renderer=lambda _d: _player_card_grid(yardage, "yards"),
        )

        st.markdown("**Touchdowns**")
        st.caption("A different board from yardage, and mostly different names on it.")
        touchdowns = [(label, _player_board(scope, depth, (category,), "TD"))
                      for label, category in (("QB", "passing"),
                                              ("Receiving", "receiving"),
                                              ("Rushing", "rushing"))]
        states.render_or_state(
            pd.concat([frame for _label, frame in touchdowns]) if touchdowns else pd.DataFrame(),
            "srv_player_game_log",
            "The touchdown board would be here.",
            f"No player box scores for {scope.describe()}.",
            renderer=lambda _d: _player_card_grid(touchdowns, "touchdowns"),
        )

        st.markdown("**Defensive leaders**")
        st.caption("Tackles, tackles for loss and sacks — three stat types on one category, "
                   "which is a different split from the two boards above.")
        defence = [(label, _player_board(scope, depth, ("defensive",), stat_type))
                   for label, stat_type in (("Tackles", "TOT"),
                                            ("Tackles for loss", "TFL"),
                                            ("Sacks", "SACKS"))]
        states.render_or_state(
            pd.concat([frame for _label, frame in defence]) if defence else pd.DataFrame(),
            "srv_player_game_log",
            "The defensive board would be here.",
            f"No defensive box scores for {scope.describe()}.",
            renderer=lambda _d: _player_card_grid(defence, ""),
        )


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
# ⚠️ THE PICTURE TAKES AN EXPLICIT WIDTH UNDER CONCAT. `use_container_width` sizes the
# OUTER spec, and a concat divides that between its halves — so leaving the left half
# to infer its width makes the split depend on how wide the table's text happens to
# render, which is R-603's collapse wearing a different hat.
_BUMP_CHART_WIDTH = 820


# ── A156: THE TABLE IS A CHART ELEMENT SO THAT THE AXIS CAN BE SHARED ───────────────────────
#
# > **MARC:** *"The chart and the Table need to share the same Y-axis. … consume that with the
# > table (which might be better of as a chart element that's printed in something that is
# > structured like a table)"*
#
# 🚨 TWO RENDERERS CANNOT SHARE A SCALE. The table was `table.render` — HTML, uniform row height
# — and the chart is Altair, so rank 7 on the picture and rank 7 in the table sat at unrelated y
# and no amount of CSS would have tied them together. **His parenthesis is the answer: inside
# Altair, an `hconcat` whose second half is text marks on the SAME `alt.Y`.** One renderer, one
# scale, and the alignment is a property of the encoding rather than of arithmetic anybody has
# to keep in step.
#
# ✅ THE PRIMITIVE WAS MEASURED BEFORE IT WAS BUILT ON, and the first measurement was WORTHLESS.
# A prototype pinned the same explicit `domain` on BOTH halves and compared rendered pixel y for
# five teams: they agreed. **Then the negative control — the identical spec with
# `y="independent"` — ALSO agreed**, because two independent scales over one domain at one
# height produce identical pixels. 🚨 The instrument could not fail: R-760's class, in the
# measuring rig rather than in a test.
#
# ✅ WHAT MAKES IT DISCRIMINATING IS ALSO WHAT MAKES IT CORRECT: **only the chart pins a domain,
# and the table inherits one through the shared resolve.** Under `independent` the table then
# scales its own narrower rank range across the full height and the halves disagree by ~100px;
# under `shared` they cannot disagree at all. ⚠️ AND IT IS THE §4.2.1 QUESTION IN A CHART SPEC:
# a domain literal repeated on both halves is one number with two homes, and the two homes drift.
#
#     measured, vega-lite 6.4.3, ranks 1-3 present in both halves:
#         shared        60.5/60.5   144.5/144.5   228.5/228.5     agree
#         independent   60.5/158.5  144.5/298.5   228.5/438.5     disagree
#
# ⚠️ WHAT IS LOST, SAID PLAINLY RATHER THAN DISCOVERED LATER: `table.render` applied the sort it
# drew (A141) and a chart element cannot. **At a shared rank axis the row order IS rank**, so the
# Rank, Team and delta sort links were already saying what the axis says — but **sorting by
# POINTS is genuinely gone**, and that is the one a reader might have used.
# 🚨 A164 (cfdb-main-R-1144). THE RIGHT-ANGLE LOOK MARC ASKED FOR, AND WHY THIS ONE OF THREE.
# > *"Can we switch to a bump chart look where the changes to the lines are right angles instead
# > of diagonal lines."*
#
# Vega-Lite offers three, and they put the vertical in three different places:
#
#     step         the vertical falls at the MIDPOINT between two weeks — on no tick at all
#     step-before  the vertical falls at the EARLIER week, so the new rank is drawn a week EARLY
#     step-after   the line HOLDS the rank across its own week and turns at the NEXT week's tick
#
# ✅ **`step-after` IS THE ONLY ONE THAT MATCHES WHAT A POLL IS.** A rank is announced FOR a week
# and held through it, so the horizontal segment belongs over the week that rank was held and the
# turn belongs on the tick where the new rank was published. ⚠️ **The other two draw a team at a
# rank it did not hold** — `step-before` for a whole week, `step` for half of one — which is the
# same class of quiet untruth the null grid below exists to prevent.
_BUMP_INTERPOLATE = "step-after"
_BUMP_TABLE_WIDTH = 250
_BUMP_ROW_FONT = 11


def _bump_table_chart(current: pd.DataFrame) -> alt.Chart:
    """The table, drawn as text marks that INHERIT the chart's y scale.

    🚨 IT DECLARES NO SCALE AND NO DOMAIN, AND THAT IS THE WHOLE DESIGN. `resolve_scale(y=...)`
    is what ties the halves together, and a domain repeated here would be a second copy of the
    chart's own `worst` — the §4.2.1 question in a chart spec, and the exact drift this panel
    exists to remove. **It would also make the round's own verification worthless**: two halves
    pinned to one domain land on identical pixels whether the scale is shared or not, which is
    how the first version of that measurement passed its own negative control.

    ⚠️ `axis=None` IS NOT COSMETIC EITHER. Without it the table half draws its OWN rank axis, and
    the first render did: 25 rank numbers plus 6 axis ticks at 1/5/10/15/20/25, each tick sitting
    at the identical y as the rank it duplicates. **Measured as six "row collisions" that were
    not rows at all** — the picture said the table was too tight when it was drawing a second
    axis on top of itself.

    ⚠️ AND THE COLUMNS ARE PLACED AT PIXEL x THROUGH `alt.value`, which bypasses the x scale
    entirely — the table half has no x quantity, only four gutters. The header row sits at a
    NEGATIVE pixel y for the same reason: it is chrome, not a rank.
    """
    y = alt.Y("rank:Q", axis=None)
    columns = (
        (34, "right", "Rank", alt.Text("rank:Q", format="d")),
        (46, "left", "Team", alt.Text("team_display:N")),
        (186, "right", "Points", alt.Text("points:Q", format=",d")),
        (196, "left", "vs prev", alt.Text("delta:N")),
    )
    layers = []
    for x_px, align, heading, text in columns:
        layers.append(alt.Chart(current).mark_text(
            align=align, fontSize=_BUMP_ROW_FONT, baseline="middle").encode(
                x=alt.value(x_px), y=y, text=text))
        layers.append(alt.Chart(current.head(1)).mark_text(
            align=align, fontSize=_BUMP_ROW_FONT, fontWeight="bold", baseline="bottom",
            opacity=0.75).encode(x=alt.value(x_px), y=alt.value(-6),
                                 text=alt.value(heading)))
    return alt.layer(*layers).properties(width=_BUMP_TABLE_WIDTH, height=_BUMP_HEIGHT)


def _bump_chart(frame: pd.DataFrame, poll: str, current: pd.DataFrame) -> None:
    """A bump chart: rank 1 at the top, one line per team, gaps where a team was unranked.

    `current` is the latest week, drawn beside it as a table on the SAME y scale.
    """
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
    # ⚠️ THE SCALE AND THE AXIS ARE BOUND ONCE AND REUSED, NOT READ BACK OFF `y`. A164 built the
    # left-label chart with `scale=y.scale` and the whole spec failed to serialise — those
    # attributes are Altair PROPERTY SETTERS, not the values — and the panel would have rendered
    # a handled error card, green in every test, because no test builds this chart.
    y_scale = alt.Scale(reverse=True, domain=[0.5, worst + 0.5], nice=False)
    y_axis = alt.Axis(values=[v for v in (1, 5, 10, 15, 20, 25) if v <= worst], tickMinStep=1)
    y = alt.Y("rank:Q", title="Rank", scale=y_scale, axis=y_axis)

    # ── TEAM COLOUR ON THE LINES (A165, cfdb-main-R-1304) ───────────────────────────────
    #
    # > **MARC, Today v05:** *"Team colors will help."*
    #
    # 🚨 THE COMMENT THAT USED TO SIT HERE SAID BRAND COLOURS WERE *"not available here:
    # srv_rankings carries team_slug and no colour"*. **That was false against the model.**
    # `srv_rankings.sql` has selected `color_on_light` and `color_on_dark` for some time, and
    # A164 confirmed all three colour columns in live published serving via
    # `information_schema`; only `_rankings`'s own SELECT omitted them. ⚠️ **A design decision
    # defended by a measurement that had expired** — the third such comment found in three
    # rounds (R-1230, R-1237, this).
    #
    # ✅ **THE REST OF THE OLD NOTE WAS RIGHT AND IS KEPT, BECAUSE IT NAMES THE RISK THIS TAKES
    # ON:** *"a categorical palette runs out well before 25 and starts recycling, so two teams
    # get the same colour and the reader has no way to know which."* **Team colours can
    # reproduce exactly that failure**, so it was measured before it was shipped rather than
    # assumed to be an improvement.
    #
    # 📊 THE 2026 AP FIELD, 26 ranked teams, distinct colours out of 26:
    #
    #     on light   23/26   three pairs share a colour
    #     on dark    20/26   🚨 SEVEN COLLAPSE ONTO #ffffff — Alabama, Houston, Indiana,
    #                        Oklahoma, Penn State, Texas A&M, Utah
    #
    # ⚠️ **THE DARK COLLAPSE IS REAL AND IS THE LADDER'S, NOT THIS PANEL'S** (B136 measured 44
    # teams onto #ffffff across the whole league, cfdb-wta-R-1259). ✅ **IT STILL SHIPS, AND THE
    # REASON IS THE BASELINE RATHER THAN THE IDEAL: today ALL TWENTY-FIVE lines are one colour.**
    # Nineteen become distinguishable and seven stay exactly as distinguishable as they are now
    # — there is no reader who can tell two lines apart today and cannot after this.
    #
    # ✅ **HOVER EMPHASIS AND BOTH ENDPOINT LABELS STAY**, because they are what still separates
    # those seven, and the labels are what the caption's own case rests on.
    dark = theme.viewer_is_dark()
    swatch = "color_on_dark" if dark else "color_on_light"
    # ⚠️ THE FALLBACK IS THE OLD BEHAVIOUR. A team with no published colour keeps the neutral
    # this panel drew for everyone until now, rather than becoming invisible or a guess.
    #
    # 🚨 `pd.notna`, NOT `or`, AND A TEST FOUND THAT THE HARD WAY. A missing colour arrives out
    # of a DataFrame as `NaN`, **and `float('nan')` is TRUTHY in Python** — so `palette[t] or
    # neutral` passed the NaN straight through and a literal `NaN` reached the Vega spec, where
    # it is not a colour and not an error either. The fixture's one colourless team is what
    # caught it; a fixture where every team has a swatch could not have (R-744).
    neutral = "#fafafa" if dark else "#31333f"
    palette = (frame.dropna(subset=["team_display"])
                    .drop_duplicates("team_display")
                    .set_index("team_display")[swatch])

    def _swatch(team):
        value = palette.get(team)
        return str(value) if pd.notna(value) and str(value).strip() else neutral
    domain = [t for t in teams if t in palette.index]
    scheme = alt.Scale(domain=domain, range=[_swatch(t) for t in domain])
    colour = alt.Color("team_display:N", scale=scheme, legend=None)
    base = alt.Chart(data).encode(x=x, y=y, detail="team_display:N")
    # ⚠️ `invalid` IS SET EXPLICITLY AND MUST STAY THAT WAY. Vega-Lite's default for path
    # marks changed in 5.14 — before it, an invalid value was FILTERED, which joins the two
    # points either side and draws exactly the straight line across a team's unranked weeks
    # that the null grid above exists to prevent. v6.4.1 defaults to breaking paths, so this
    # is currently redundant; it is written down because the whole correctness of the gap
    # rests on it and a silent default is not something to rest it on.
    lines = base.mark_line(interpolate=_BUMP_INTERPOLATE, clip=True,
                           invalid="break-paths-filter-domains").encode(
        color=colour,
        strokeWidth=alt.condition(hover, alt.value(3.0), alt.value(1.25)),
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.55)))
    points = base.mark_circle(clip=True).encode(
        color=colour,
        size=alt.condition(hover, alt.value(70), alt.value(22)),
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.65)),
        tooltip=[alt.Tooltip("team_display:N", title="Team"),
                 alt.Tooltip("week:O", title="Week"),
                 alt.Tooltip("rank:Q", title="Rank", format="d")])
    labels = alt.Chart(last).mark_text(align="left", dx=8, fontSize=11).encode(
        x=x, y=y, text="team_display:N",
        opacity=alt.condition(hover, alt.value(1.0), alt.value(0.75)))
    # 🚨 A164. THE LEFT LABEL IS ADDED AND THE RIGHT ONE STAYS — Marc asked to *"Label the left
    # of the line with the school name"*, which is an ADDITION and not a move. ⚠️ The caption
    # tells a reader that *"a team on the picture with no row beside it was ranked earlier in
    # the season and is not ranked now"* — those are precisely the teams the right-hand table
    # does NOT name, so dropping the right label would make the caption's own case unreadable.
    first = (data.dropna(subset=["rank"]).sort_values("week")
                 .groupby("team_display", as_index=False).first())
    # 🚨 A TIE PUTS TWO LABELS AT THE SAME HEIGHT, AND ONLY THE RASTER SHOWED IT
    # (cfdb-main-R-1145). 2026 AP week 1 has two teams at rank 14, so `BYU` and `USC` were drawn
    # at an identical y — measured 0.0px apart — and overstruck into an unreadable smear.
    #
    # ⚠️ **THE DENSITY FEAR WAS THE WRONG WORRY, WHICH IS WHY IT HAD TO BE RENDERED.** 25 teams
    # over a 420px band is a 16.8px pitch against an 11px font; 24 of the 25 labels sit clear.
    # **The only collision in the frame came from a TIE, and no amount of width fixes that.**
    #
    # ❌ **NUDGING THE TIED LABELS APART WAS TRIED AND MEASURED AND IT DOES NOT WORK.** Spreading
    # them ∓0.45 of a rank separated BYU from USC and put BYU 9.2px from *Alabama* one rank up —
    # the collision moved rather than cleared, because a 16.8px pitch against ~13px of text
    # leaves under 4px of slack and there is simply nowhere to put a second label.
    #
    # ✅ **SO TIED TEAMS SHARE ONE LABEL, WHICH IS ALSO THE TRUER STATEMENT.** They hold the same
    # rank that week; one mark naming both says exactly that, and it is legible. ⚠️ It is a
    # STRING JOIN of two published values, not a computed quantity — §4.2.1's own example of
    # rendering — and it changes no line and no point, which still sit on the real rank.
    first = (first.groupby(["week", "rank"], as_index=False)
                  .agg(team_display=("team_display", " · ".join)))
    start_labels = alt.Chart(first).mark_text(align="right", dx=-8, fontSize=11).encode(
        x=x, y=y, text="team_display:N", opacity=alt.value(0.75))

    # ── THE CONCAT, AND THE THREE THINGS IT CHANGES ────────────────────────────────────
    #
    # ⚠️ `configure_view` MOVES TO THE TOP LEVEL. A `configure_*` on a sub-chart of a concat is
    # invalid Vega-Lite and Altair raises on it; the setting is global by nature anyway.
    #
    # ⚠️ AND THE RIGHT PADDING GOES WITH IT. It existed so the endpoint labels beside each line
    # were not clipped; under a concat the table half is what sits to the right of them, so the
    # allowance belongs to the LEFT half's own width rather than to the whole spec.
    picture = alt.layer(lines, points, labels, start_labels).add_params(hover).properties(
        width=_BUMP_CHART_WIDTH, height=_BUMP_HEIGHT)
    chart = alt.hconcat(
        picture, _bump_table_chart(current), spacing=18,
    ).resolve_scale(y="shared").configure_view(stroke=None)
    # ── A156: R-659's SQUEEZE DOES NOT APPLY TO A CONCAT, AND THE OPPOSITE IS TRUE ──────
    #
    # ⚠️ R-659 MEASURED THIS PANEL AS A SINGLE VIEW and its table is kept below as history,
    # because the numbers were real and they describe a chart this no longer is. **Re-measured
    # under the concat, in Chromium, reproducing BOTH of Streamlit's steps from its source
    # rather than from memory** — `_prepare_vega_lite_spec` imposing autosize, and the frontend
    # setting `spec.width` to the container:
    #
    #     container   600   700   900   1100   1300   1600
    #     svg drawn   1173 at every one of them        plot group h = 420.0, exactly as asked
    #
    # 🚨 AND VEGA-LITE SAYS WHY, IN ITS OWN CONSOLE: `WARN Autosize "fit" only works for single
    # views and layered views.` An `hconcat` is neither, so the `fit` Streamlit imposes is
    # IGNORED — which is why the plot keeps the full 420 instead of losing ~35px to it, and why
    # `use_container_width=True` is now INERT here. **The panel is a fixed 1173px.**
    #
    # ✅ THAT IS THE SAFE DIRECTION AND IT IS WORTH SAYING WHICH RISK IT RETIRES: R-603's
    # collapse is a chart SHRINKING to nothing inside a box it does not control. This cannot
    # shrink at all. What it can do is leave whitespace on a very wide viewport, or overflow a
    # narrow one — a layout cost, not a legibility one, and visible rather than silent.
    #
    # ⚠️ THE HISTORIC SINGLE-VIEW MEASUREMENT (A100), KEPT SO NOBODY RE-DERIVES IT:
    #
    #     axis font    10px   13px   16px   20px   24px   28px
    #     plot drawn     388    381    375    366    355    345
    st.altair_chart(chart, use_container_width=True)
    st.caption(
        f"{poll}, full season. **Rank 1 is at the top.** Every ranked team is drawn; a line "
        "stops where a team left the poll and restarts where it returned, so a gap is a "
        "week unranked rather than a rank held. Hover a line to follow one team. "
        f"**The table beside it is week {int(frame['week'].max())} and shares the chart's rank "
        "axis**, so a team's row sits at the same height as its line — a team on the picture "
        "with no row beside it was ranked earlier in the season and is not ranked now.")


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
        # 🚨 THE TABLE IS DRAWN INSIDE THE CHART NOW (A156), so it is passed in rather than
        # rendered after. `sort_values` stays and is not decoration: text marks are emitted in
        # data order, and a stable order is what makes a staged break legible.
        _bump_chart(one, poll, current.sort_values("rank"))


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

    # 🚨 A166: `index=1` -> `index=0`, WHICH IS TEN. Both of Marc's sentences point here and
    # they were pulling against each other at 25.
    #
    # > **Today v04:** *"Include top 10 for each category."*
    # > **Today v05:** *"We need things more dense vertically."*
    #
    # 📊 MEASURED AT 1300px, the three player boards, before and after the switch to cards:
    #
    #     three 25-row tables (what shipped)      3,266px
    #     cards at depth 10  — his sentence       2,286px   ✅ 30% SHORTER than the tables
    #     cards at depth 25  — the old default    5,642px   🚨 73% TALLER
    #     cards at depth 50                      11,236px
    #
    # ⚠️ **A CARD IS LESS DENSE THAN A ROW AND THE GRID IS WHAT PAYS FOR IT** — three columns
    # means thirty cards are ten tall. At ten the redesign is a density WIN; at twenty-five it
    # is a 73% regression against the thing he asked for one round earlier.
    #
    # ⚠️ **THIS ALSO MOVES THE TEAM YARDAGE BOARD TO TEN**, because it is one control for all
    # four boards. That is a visible change he did not ask for in those words, and it is called
    # out in the report rather than buried — **the radio is on the page and one click restores
    # 25**, which is why this is a default rather than a constant.
    depth = st.radio("Leaderboard depth", DEPTHS, index=0, horizontal=True,
                     key="today_depth", help="How many rows each leaderboard shows.")

    _tab_bar(slug)
    # 🚨 A144. THE LEGEND BUTTON SITS UNDER THE TAB BAR, ABOVE THE PANELS THAT USE THE MARKS —
    # Marc: *"Need the legend button to help with the icons"*. `st.popover` is Schedule's own
    # control for the same job, so the site has one legend affordance rather than two (§4.3).
    #
    # ⚠️ IT IS DRAWN FOR EVERY TAB THOUGH ONLY SOME PANELS CARRY MARKS, and that is the cheaper
    # of two wrongs: a legend that appears and disappears as a reader moves between tabs reads as
    # a rendering fault, and `LEGEND_GROUPS_DRAWN` already guarantees it never explains a mark
    # this page cannot produce.
    _legend()
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
