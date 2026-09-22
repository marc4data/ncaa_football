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
import html
import math
import re
import statistics

import altair as alt
import pandas as pd
import streamlit as st

from lib import (filters, fmt, glyphs, identity, metrics, params, shell, states, tab,
                 table, theme, winprob)
from lib import schedule_table
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

    🚨 A171, cfdb-main-R-1602. THE FOUR COLOUR COLUMNS ARE SELECTED SO THE CURVE'S TWO LOBES CAN
    TAKE THEIR OWN TEAM'S COLOUR. Marc: *"shade the area with the color of team favored at that
    point"*, and asked to choose between the line, the fill and both, he picked the fill.
    `lib/winprob.py` holds no team colours and looks none up — §4.2.1, `identity` owns that — so
    the caller supplies them and `identity.accent_color` composes the `light-dark()` pair.
    📊 Null on 0 of the 1,898 games this panel can draw, in BOTH themes, measured in serving.

    ⚠️ AND THE NOTE LIVES HERE RATHER THAN IN THE QUERY BECAUSE OF THE PARAGRAPH BELOW, WHICH
    A171 WALKED STRAIGHT INTO. The first draft put this as a `--` comment inside the string and
    `test_no_user_facing_string_uses_british_spelling` caught it — but the spelling was the
    lesser half: `ci/check_page_queries.py` normalises a query to ONE LINE, so a `--` comment
    swallows every column after it. A165 paid for this exact mistake and wrote the warning that
    is four lines further down.

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
               home_color_on_light, home_color_on_dark,
               away_color_on_light, away_color_on_dark,
               upset_margin_big, upset_margin_blowout,
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
               opponent_team_slug, opponent_team_display, opponent_logo_url, opponent_rank,
               total_yards, rushing_yards, passing_yards, points_for, points_against,
               result, as_of_ts
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


def _player_board(scope, depth: int, categories, stat_types) -> pd.DataFrame:
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
    # 🚨 A175 (cfdb-main-R-1753). THREE METRICS MEANS A DIFFERENT QUERY, NOT A DIFFERENT CARD.
    #
    # > **MARC, v09:** *"I want 3 metrics per card."*
    #
    # `srv_player_game_log` is MELTED — one row per player × stat_type — so one card showing
    # three numbers needs three rows fetched and folded into one.
    #
    # 🚨 AND THE ORDER IS THE HARD PART. Ordering the fetch by `stat_value desc` across THREE
    # types sorts a passer's 400 YDS above everyone's 3 TD, so a `limit` would keep the yardage
    # rows and cut the touchdown rows **of the very players the board is about**. The window
    # below orders every row of a player by THAT PLAYER'S PRIMARY value, so a player's three
    # rows travel together and the limit cuts whole players rather than metrics.
    #
    # ⚠️ ONE RELATION, ONE QUERY, NO JOIN (G-2). The fold is a reshape of rows already fetched,
    # which is what `augment` does for the workbook — not arithmetic between two columns.
    # 🚨 A178 (cfdb-main-R-1855). `color_on_light` / `color_on_dark` ARE A177's, PUBLISHED
    # YESTERDAY, AND THIS IS THEIR FIRST CONSUMER. Marc asked for the team name in the team's
    # colour on this card in v10 — reversing his own v09 *"don't necessary need the color on
    # this page"* after looking at it. `cfdb-main-R-1309` refused it correctly for six rounds
    # because the column did not exist; it exists now at 0.30% null, and the page reads it
    # from the one relation it was already reading (no join, G-2).
    #
    # 🚨 AND THIS NOTE IS A PYTHON COMMENT RATHER THAN A SQL ONE, WHICH COST ONE CI-EQUIVALENT
    # RUN TO RELEARN. `ci/check_page_queries.py` normalises a query to a SINGLE LINE before
    # executing it, so a `--` comment swallows the rest of the statement — the first draft put
    # these six lines inside the triple quotes and the checker returned `dict is not a
    # sequence`. `_rankings` carries the identical warning fifteen hundred lines up: **nothing
    # goes between the triple quotes but SQL.**
    primary = stat_types[0]
    return query("""
        select player_name, player_slug, team, conference, opponent, week,
               stat_category, stat_type, stat_value, as_of_ts,
               jersey, position, class_year_display,
               team_slug, team_display, team_abbreviation, team_logo_url, team_rank,
               record_before_display, color_on_light, color_on_dark
        from srv_player_game_log
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and stat_type = any(:types)
          and stat_category = any(:cats)
          and (:conf is null or conference = :conf)
          and stat_value is not null
        order by max(case when stat_type = :primary then stat_value end)
                 over (partition by player_slug, team) desc nulls last,
                 player_name, stat_type
        limit {DEPTH}
    """.replace("{DEPTH}", str(int(depth) * len(stat_types) * 2)),
        {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
         "conf": scope.conference, "cats": list(categories),
         "types": list(stat_types), "primary": primary})


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
    # ── A190 (cfdb-main-R-1935): THE FOUR FACTS THE HOVER NAMES, NOW THAT THEY EXIST ──────
    #
    # > **MARC, v09 / v10 / v11 — he has asked three times:** *"The chart has to have hover
    # > capabilities. Think I've described what should be in the hover."*
    #
    # 🚨 A176 REFUSED THIS AND WAS RIGHT TO: its own comment in `_scatter_svg` records that
    # `srv_team_week` published **no rank, no record and no percentile at all**, and a join is
    # what G-2 forbids. ✅ **A177/A178 published them since**, so the refusal has expired
    # rather than been overruled.
    #
    # 📊 VERIFIED AGAINST `information_schema` ON LIVE PUBLISHED SERVING BEFORE THIS WAS
    # WRITTEN (§2.2.1c.2), and then for ROWS rather than columns (§2.5) — 2026 week 3, FBS:
    #
    #     138 teams   record_before_display 138   both percentiles 138   logo_url 138
    #                 percentile_population 138   ap_rank 25
    #
    # ⚠️ `ap_rank` AT 25 OF 138 IS THE CORRECT NUMBER, NOT A GAP — a poll ranks 25 teams. The
    # other 113 are the "unranked" branch, and `NaN` is truthy (A191), so every reader of it
    # tests with `pd.isna` rather than truthiness.
    return query("""
        select team_id, team_display, team_slug, conference, week,
               games_counted,
               total_yards_for_per_game, total_yards_allowed_per_game,
               total_yards_for_percentile, total_yards_allowed_percentile,
               percentile_population, ap_rank, record_before_display,
               color_on_light, color_on_dark, logo_url,
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


def _week_opponents(scope) -> pd.DataFrame:
    """Who each team plays in the scoped week — for the scatter hover's last line only.

    🚨 A190 (cfdb-main-R-1936). THE MARKS ARE FORM *ENTERING* THE WEEK, NOT A GAME, AND THAT
    IS WHY THE OPPONENT IS A SEPARATE READ RATHER THAN A COLUMN ON THE POINT.

    > **MARC, v10**, naming an opponent among the hover's contents.

    ⚠️ `_yardage_profile` answers *how did this team stand coming in*; the opponent answers
    *who are they playing*. They are different grains and different relations, so putting the
    opponent on the point would either need a join in the page (G-2) or make the profile row
    mean two things at once. **One more single-table SELECT is the cheaper honesty.**

    ⚠️ AND IT RETURNS EMPTY WHEN NO SINGLE WEEK IS IN SCOPE. The panel's week filter accepts
    "All", and under it `srv_team_week` returns every week for every team — there is no single
    week to name, so the hover simply omits the line rather than picking one arbitrarily.

    🚨 AC-G.39 — THE `limit` IS THE GRAIN RESTATED, AND THE FIRST ONE WAS A GUESS THAT CUT
    REAL ROWS. It was `400`, copied from the profile query beside it, which is ONE ROW PER
    TEAM. **This grain is one row per team-GAME, which is roughly double**: 2026 week 3 holds
    **622 rows**, so 400 silently dropped 222 of them and 41 of the 138 plotted teams lost
    their opponent line — Georgia, Ohio State, Clemson and Duke among them. ⚠️ **It looked
    exactly like a bye**, which is a state this hover legitimately has, so nothing about the
    page said it was wrong. It was found by counting: 97 lines against 138 marks.

    ✅ 1,000 is the grain's own ceiling — ~134 FBS plus ~120 non-FBS teams in a week, at most
    one row each per game, and a week has never exceeded 700.
    """
    if scope.week is None:
        return pd.DataFrame()
    return query("""
        select team_id, opponent_team_display, opponent_logo_url, opponent_rank,
               is_home
        from srv_game_team
        where season = :season and season_type = :season_type and week = :week
        limit 1000
    """, {"season": scope.season, "season_type": scope.season_type, "week": scope.week})


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
    # ── A190 (cfdb-main-R-1943): THE GAME THAT EXPLAINS THE MOVE ──────────────────────────
    #
    # > **MARC, v11:** *"bring in srv_game as a left join… a hover that shows a simple
    # > scoreboard look (away over home) with logo, name, record, and scores for the
    # > corresponding week."*
    #
    # ⚠️ THE JOIN IS IN dbt AND NOT HERE — §4.2.1, and it is the clearest case of it: a
    # page-side join is exactly what the display-only contract forbids. `srv_rankings` now
    # carries the explaining game already resolved into away and home, so this stays a
    # single-table SELECT and the page orders nothing.
    #
    # 📊 POLL WEEK N REFLECTS GAME WEEK N-1, established from the data rather than assumed —
    # see the model for the measurement and for the competing alignment that was tested and
    # refuted.
    return query("""
        select season, week, poll_name, rank, team_display, team_slug,
               first_place_votes, points, as_of_ts,
               color_on_light, color_on_dark,
               explained_by_game_week,
               game_away_display, game_away_record_after, game_away_points,
               game_home_display, game_home_record_after, game_home_points,
               game_result_for_team
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
# 🚨 A189 RE-MEASURED THESE AND BOTH WERE OVER-PROVISIONED — Marc: *"a lot of padding to the
# right of the scoreboard."*
#
# 📊 MEASURED IN CHROMIUM against the real week-3 render, per row, not per constant:
#
#     the nine REGULATION rows       427px content   (constant said 426)
#     the one OVERTIME row           458px content   (constant said 464)   <- Temple at Toledo
#     the column it was given        476px = 464 + 12 gutter
#
# ⚠️ SO THE CONSTANT WAS 6px TOO WIDE AND THE GUTTER ADDED 12 MORE: the widest row carried
# **18px** of slack and every regulation row carried **49px**. Correcting the constants returns
# 6px to every row and the gutter drops to 6, which is still a visible separation at 0.9rem.
#
# 🚨 AND THE ANSWER TO MARC'S QUESTION IS HERE RATHER THAN IN A COMMIT MESSAGE: **the most
# overtimes last week was ONE period**, in Temple at Toledo (48-49). One overtime game in the
# rendered ten widens this column by 31px for the other nine, because a column has one width.
# That is most of the padding he saw; the rest was these two numbers.
_SCOREBOARD_REGULATION_PX = 427
_SCOREBOARD_OVERTIME_PX = 458
_SCOREBOARD_GUTTER_PX = 6


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
def _fold_metrics(frame, stat_types, depth: int) -> pd.DataFrame:
    """Melted rows -> one row per player, with a column per statistic. A175.

    🚨 THE SAME RESHAPE THE WORKBOOK NEEDED IN THE SAME SPEC, AND THAT IS NOT A COINCIDENCE.
    > **MARC, v09:** *"I want 3 metrics per card"* — and, four lines later, *"Player Stats is a
    > melted dataset, too long for export. Pivot each Category, with Statistic as columns."*
    **One root cause — `stat_type` is a ROW — surfacing on a page and in a spreadsheet at once.**

    ⚠️ AND THEY ARE DELIBERATELY NOT ONE SHARED HELPER, which §4.3 asks to be reasoned rather
    than assumed. The workbook's pivot emits **two** columns per statistic (value AND rank),
    keys on `(player_name, team)` across a whole season, and runs inside `Sheet.augment` on a
    frame the writer owns. This one takes the **top `depth` players by the PRIMARY metric**
    from a week-scoped frame and keeps the identity columns the card reads. **A single helper
    would need a rank flag, a key list and a depth — and one caller would inherit the other's
    defaults the first time somebody edited it**, which is R-744's shape exactly. Two small
    reshapes, each legible where it is used, and this comment is the link between them.

    ⚠️ THE PRIMARY DECIDES THE ORDER. The board is already sorted by it in SQL, so taking the
    first `depth` rows of the primary's slice preserves the ranking the panel has always had.
    """
    if frame is None or frame.empty:
        return frame
    primary = stat_types[0]
    leaders = frame[frame["stat_type"] == primary].drop_duplicates(
        subset=["player_slug", "team"]).head(depth)
    if leaders.empty:
        return leaders
    out = leaders.copy()
    for stat in stat_types:
        rows = frame[frame["stat_type"] == stat].drop_duplicates(
            subset=["player_slug", "team"]).set_index(["player_slug", "team"])
        key = out.set_index(["player_slug", "team"]).index
        out[f"metric_{stat}"] = rows["stat_value"].reindex(key).values
    return out


def _player_card(row, stat_label: str, metric_types=(), rank=None) -> str:
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
    # 🚨 A175 (cfdb-main-R-1753). THREE METRICS WHERE THERE WAS ONE.
    # > **MARC, v09:** *"I want 3 metrics per card."*
    #
    # ⚠️ AN EMPTY `metric_types` KEEPS THE SINGLE-VALUE CARD, and the defensive board still
    # uses it deliberately: that board already splits on THREE stat_types, one per column, so
    # handing it a trio would print the same number three times in three columns.
    #
    # 🚨 AND THE PARAMETER IS `metric_types` BECAUSE `metrics` IS A MODULE THIS FILE IMPORTS.
    # A173 added `from lib import … metrics …` for the legend's upset bands. The first draft of
    # this function called the parameter `metrics`, and with no argument passed the name
    # resolved to the MODULE — which is always truthy, so **every card would have taken the
    # three-metric branch and iterated a module object.** `flake8` cannot see it: the name is
    # legitimately bound at module scope. **A shadowed import is an undefined name that passes
    # every lint.**
    if metric_types:
        cells = "".join(
            f"<div class='cfdb-card-metric'>"
            f"<span class='cfdb-card-value'>"
            f"{fmt.number(row.get(f'metric_{stat}'), 'stat_value')}</span>"
            f"<span class='cfdb-card-unit'>{fmt.text(stat)}</span></div>"
            for stat in metric_types)
        stat_block = f"<div class='cfdb-card-metrics'>{cells}</div>"
    else:
        # The same formatter the tables use — `Col(kind="num")` calls exactly this, so a card
        # and a row can never disagree about how many decimal places a stat has.
        value = fmt.number(row.get("stat_value"), "stat_value")
        stat_block = (f"<div class='cfdb-card-stat'>"
                      f"<span class='cfdb-card-value'>{value}</span>"
                      f"<span class='cfdb-card-unit'>{fmt.text(stat_label)}</span></div>")
    # ── A178 (cfdb-main-R-1855): THE TEAM NAME IN THE TEAM'S COLOUR ────────────────────────
    #
    # > **MARC, v10:** *"Color Team Name with Team Color while retaining the underlyine to
    # > indicate the hyperlink."*
    #
    # ✅ **v10 REVERSES v09's *"don't necessary need the color on this page"*, and that is the
    # loop working rather than a mistake** — the neutral card shipped, he looked at it, and he
    # asked for the colour. `cfdb-main-R-1309` refused it for six rounds because the column did
    # not exist; **A177 published it yesterday** and this is its first consumer.
    #
    # ⚠️ THE COLOUR IS SET ON A WRAPPER, NOT PASSED INTO THE SHARED CELL. `_team_identity` ->
    # `table.team_cell` serves Schedule, Scores and the Team page as well; giving it a colour
    # parameter would be a change to every caller for one caller's benefit. A CSS custom
    # property on the wrapper reaches the anchor inside it and reaches nothing else.
    #
    # ⚠️ AND THE UNDERLINE IS HIS OWN CONSTRAINT, which is a real one: colour alone is not an
    # affordance, and a coloured-but-unstyled name reads as emphasis rather than as a link.
    # The rule in `theme.py` sets both together so neither can be removed without the other.
    accent = identity.accent_color(row)
    # ── A191 (cfdb-main-R-2006): THE SHORT NAME UNDER THE LOGO, AND THE FULL ONE ON HOVER ──
    #
    # > **MARC, 2026-09-21:** *"team name under the logo, readable. If the full name can't fit
    # > at the card width, use the site's existing short/abbreviated team name and say which
    # > field."*
    #
    # 📊 IT CANNOT FIT, MEASURED RATHER THAN ASSUMED. In Chromium on this page at 2026 week 3
    # the team track is 57.6px and **15 of 40 names overflow it** (max 112.9px, "Mississippi
    # Valley State"), and the track beside it is already short of room at 1100px — 90.9px with
    # 56 of 150 player rows overflowing. ⚠️ **So widening this column pays for one truncation
    # with another**, which is the trade A165 named and A189 repeated.
    #
    # ✅ THE FIELD IS `team_abbreviation`, PUBLISHED BY A191 ON `srv_player_game_log` FROM
    # `dim_team.abbreviation` — the site's existing short name, the same one `srv_teams_index`,
    # `srv_team_overview` and `srv_standings` publish. See that model for why it is a column
    # rather than a page-side join (G-2).
    #
    # ⚠️ THE COLUMN IS ALL-OR-NOTHING ON PURPOSE. Showing the full name where it fits and an
    # acronym where it does not would make a column that reads as a data fault; one form for
    # every card reads as a choice. **The full name is not lost — it is the cell's `title`**,
    # so the one reader who needs it hovers.
    #
    # ⚠️ AND THE FALLBACK IS THE DISPLAY NAME, NOT A BLANK. `abbreviation` is null for some
    # teams (Chicago State, in 2026 week 3), and an empty cell beside a logo reads as a
    # missing team rather than a missing abbreviation (AC-G.11).
    short = fmt.text(row.get("team_abbreviation")) or None
    full = fmt.text(row.get("team_display"))
    team_block = (f"<div class='cfdb-card-team' style='--cfdb-card-accent:{accent}'"
                  f"{f' title="{html.escape(full)}"' if short and full else ''}>"
                  f"{_team_identity(
                      row, '',
                      slug_field='team_slug',
                      display_field='team_abbreviation' if short else 'team_display',
                      logo_field='team_logo_url', rank_field='team_rank')}</div>")

    # 🚨 A175 (cfdb-main-R-1756). THE REFLOW, AND IT IS IN TODAY'S WRAPPER BECAUSE MOVING THE
    # SHARED ROW WOULD MOVE MATCHUP.
    #
    # > **MARC, v09:** *"There is a lot of horizontal space in this layout, can we fit team info
    # > on an existing line? (maybe move Yr/Position to a column close to the name, then add a
    # > cell for Team Logo/Name/Record)"*
    #
    # ⚠️ HIS PARENTHESIS IS A SUGGESTION; THE SENTENCE BEFORE IT IS THE REQUIREMENT — use the
    # horizontal space. The player identity and the team now share ONE line instead of
    # occupying two, which is the space he is pointing at.
    #
    # 📊 MEASURED BEFORE CHOOSING WHERE TO PUT IT: `identity.player_row` is called by
    # `matchup.py:2374` AND `today.py` (cfdb-main-R-1308, promoted by A167 precisely so it is
    # not copied). **Reflowing INSIDE it would have moved Matchup's player cards too**, which
    # is a change to session B's page that A175 was not asked to make and could not verify.
    # ✅ So the flex row is HERE, wrapping the shared cell rather than altering it — Matchup's
    # card is byte-identical.
    # ── A178 (cfdb-main-R-1856): THE v10 REFLOW — ONE ROW, LEFT TO RIGHT ───────────────────
    #
    # > **MARC, v10:** *"make these different, move the team name and logo to the far left,
    # > Jersey #, Player Name, Class/Pos. … Move the metrics to the right side of the cards and
    # > have them more densely populated. … Add a column on the far left that indicates the
    # > overall rank of the player card."*
    #
    # rank · team · [jersey · name · year/position] · metrics —— and the middle bracket is
    # `identity.player_row` UNCHANGED, which already emits those three in that order.
    #
    # 🚨 `identity.player_row` IS SHARED WITH MATCHUP (`matchup.py:2374`, cfdb-main-R-1308), SO
    # THE REFLOW IS AGAIN IN TODAY'S WRAPPER AND NOT IN THE SHARED ROW — A175 made exactly this
    # call for exactly this reason, and the report proves Matchup's card byte-identical rather
    # than asserting it. **The order Marc asked for is the order that function already
    # produces**, so wrapping is not a workaround here; it is the whole change.
    #
    # ⚠️ THE RANK IS THE CARD'S POSITION IN ITS OWN COLUMN, and it is passed in rather than
    # computed here — `_player_card_grid` knows the ordering because it is the thing that
    # ordered them. Inventing a second ranking inside the card is how two numbers that should
    # agree stop agreeing.
    # 🚨 THE CELL IS ALWAYS EMITTED, EMPTY IF THERE IS NO RANK, AND A TEST CAUGHT WHY. The card
    # is a four-track CSS grid; a missing first child does not leave a hole, it shifts every
    # remaining cell one track to the LEFT — so a card drawn without a rank would put the team
    # where the rank belongs and the metrics where the player belongs, silently, on a page
    # whose whole point this round is that the columns line up.
    # 🚨 A189 (cfdb-main-R-1932). THE RANK IS NO LONGER IN THE CARD.
    #
    # > **MARC:** *"Could also save some horizontal real estate by not printing the rank in the
    # > player card. Instead, have a row header with the rank so it's only printed once per row
    # > instead printing in each card."*
    #
    # ⚠️ IT MOVED TO `_player_card_grid`, WHICH IS WHERE IT WAS ALWAYS COMPUTED — A178's comment
    # on that loop says the position in the frame IS the rank, and warns against recomputing it
    # inside the card. Lifting it to the row makes that structural rather than advisory: the
    # card can no longer print a rank because it is no longer given one.
    #
    # ⚠️ `rank` IS KEPT IN THE SIGNATURE AND IGNORED so Matchup's caller — which passes it —
    # does not have to change in the same round as a Today layout edit (§3 rule 3.1).
    # 🚨 A192 (cfdb-main-R-2012). CLASS AND POSITION LEAVE THE ROW AND BECOME THE CELL'S TITLE.
    #
    # 📊 THE ROW CANNOT AFFORD THEM AND THE LAST NAME IS WORTH MORE. Measured in Chromium at
    # 2026 week 3: the widest last name is "Chambers-Smith" at **109.2px**, and the class/
    # position block costs **17.8px plus a 6.4px gap**. At 1100px the whole card is 173.3px, so
    # those 24.2px are the difference between a readable surname and "Chambers-Sm…".
    #
    # ⚠️ NOT DELETED — MOVED. The pair is the cell's `title`, so it is one hover away, and
    # `_player_card_grid`'s heading already says which category the board is. **Marc's v11 ask
    # is that the card "presents well"**, and a card that cannot say who the player is fails
    # that in the one way that matters.
    #
    # ⚠️ AND IT IS TODAY'S DECISION ALONE. `identity.player_row` still EMITS the block —
    # Matchup draws it exactly as before — and Today hides it with a rule scoped under
    # `.cfdb-card`, a class `matchup.py` does not use anywhere. See `theme.py`.
    who_title = " \u00b7 ".join(part for part in (fmt.text(row.get("class_year_display")),
                                                  fmt.text(row.get("position"))) if part)
    return (f"<div class='cfdb-card'>"
            f"{team_block}"
            f"<div class='cfdb-card-who'"
            f"{f' title=\'{html.escape(who_title)}\'' if who_title else ''}>"
            f"{identity.player_row(row)}</div>"
            # ⚠️ THE METRICS ARE LAST IN THE MARKUP AND RIGHT-ALIGNED IN THE LAYOUT, which is
            # the same thing said twice on purpose: a reader scanning for the number finds it
            # at a fixed x, and a screen reader meets it after the player it belongs to.
            f"{stat_block}"
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
    # 🚨 A189 (cfdb-main-R-1932). THE BOARD IS ROWS NOW, NOT THREE INDEPENDENT STACKS.
    #
    # The rank is printed ONCE per row in a gutter to the left, instead of once per card —
    # three times the ink and three times the horizontal space for one number that is the same
    # in all three. ⚠️ **The rank still means position within its own column**, which is what
    # A178 established and what the queries order by; the gutter shows it once because all
    # three columns share the position, not because they share a ranking.
    #
    # ⚠️ COLUMNS CAN BE UNEQUAL — a category with fewer players leaves a hole in its column
    # rather than pulling the row below it up, which would put rank 4 beside rank 3.
    per_column, headings = [], []
    for heading, frame, metric_types in columns:
        headings.append(fmt.text(heading))
        if frame is None or frame.empty:
            per_column.append(None)
        else:
            per_column.append([
                _player_card(row, stat_label, metric_types)
                for _index, row in frame.iterrows()])

    depth = max((len(c) for c in per_column if c), default=0)
    head = ("<div class='cfdb-cardrow-rank cfdb-cardrow-head'></div>"
            + "".join(f"<div class='cfdb-cardcol-head'>{h}</div>" for h in headings))
    rows = []
    for position in range(depth):
        cells_in_row = []
        for cards in per_column:
            if cards is None:
                cells_in_row.append("<div class='cfdb-card-none'>"
                                    "Nothing in this category yet.</div>"
                                    if position == 0 else "<div></div>")
            else:
                cells_in_row.append(cards[position] if position < len(cards) else "<div></div>")
        rows.append(f"<div class='cfdb-cardrow-rank'>{position + 1}</div>"
                    + "".join(cells_in_row))
    st.markdown(f"<div class='cfdb-cardboard'>{head}{''.join(rows)}</div>",
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


def _row_colors(row) -> tuple:
    """`(home, away)` as finished CSS colour strings for one game row.

    🚨 A171 (cfdb-main-R-1602). THE ADAPTER EXISTS BECAUSE OF THE ITERATOR, not because of the
    colours. `table.render` hands a renderer an `itertuples` row, which is a namedtuple and has
    **no `.get`** — and `identity.accent_color` reads its row with `.get` so it can accept the
    wide game rows every other caller passes. One small mapping here is cheaper than teaching
    the shared function about two row shapes.

    ⚠️ AND IT IS NOT A SECOND THEME MECHANISM. Nothing here decides light or dark: the string
    it returns is `light-dark(...)`, resolved by the BROWSER, which is the whole reason this
    chart can do what the Vega-based drives panel could not (cfdb-main-R-1236).
    """
    fields = {key: getattr(row, key, None)
              for key in ("home_color_on_light", "home_color_on_dark",
                          "away_color_on_light", "away_color_on_dark")}
    return (identity.accent_color(fields, "home"), identity.accent_color(fields, "away"))


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
    # 🚨 A191 (cfdb-main-R-2003). ONE LINE, AND THE REST IS IN THE HEADERS.
    #
    # > **MARC, 2026-09-21:** *"cut it to one line on how the list is ranked. Any other
    # > explanation it carried goes into header tooltips or is dropped. Keep the source credit
    # > if the site's convention requires it, on the same line."*
    #
    # ⚠️ A189 REMOVED THE `caption=` BELOW THE TABLE AND LEFT THIS ONE, WHICH IS WHY IT STILL
    # READS AS A PARAGRAPH OF METHODOLOGY: the fourteen lines above this one said what the
    # ordering is, what a tie is, how the scoreboard reads, what the chart plots, what its
    # axis does in overtime and what a cut line means — six explanations of five columns, in
    # prose, above a table whose headers said nothing.
    #
    # ✅ EVERY SENTENCE IS ACCOUNTED FOR, NOT DELETED. The ranking sentence stays here because
    # it is the one thing that is about the LIST rather than about a column. The other five
    # moved onto the columns they describe as `title=` tooltips — see `Col("scoreboard", …)`,
    # `Col("curve", …)`, `Col("scoreboard_lead_changes_fourth_quarter", …)` and
    # `Col("espn", …)` below. **The excitement-index comparison is dropped**: it was a note
    # about why A153 changed the ordering, which is history the register holds and a reader
    # of the week's games does not need.
    #
    # ⚠️ AND THE SOURCE CREDIT GOES, BECAUSE THE SITE'S CONVENTION IS A FOOTER AND NOT A
    # CAPTION — `lib/attribution.CFBD_CREDIT`, rendered by `shell.page` on EVERY page (AC-G.43)
    # and asserted by `tests/test_footer.py`. This panel was the only one on the site carrying
    # a second copy, so removing it brings Most Exciting into line rather than out of it. The
    # ESPN half of that sentence was never attribution at all and is now the Commentary
    # tooltip.
    st.caption(
        "Ranked by **how many times the lead actually changed hands in the fourth "
        "quarter**, then by how close the game stayed after it.")
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
        # 🚨 A171. THE COLOURS ARE THE CALLER'S TO SUPPLY, which is why they are composed here
        # rather than inside the chart: `lib/winprob.py` holds no team colours and must not
        # reach for one (§4.2.1 — `identity` owns that). ⚠️ `row` here is an itertuples row,
        # so it has no `.get`; `_row_colors` adapts it.
        home_fill, away_fill = _row_colors(row)
        return winprob.sparkline_svg(points, label=text, is_cut=is_cut,
                                     home_color=home_fill, away_color=away_fill)

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
    # 🚨 A189 (cfdb-main-R-1928). THE LAST SIX ARE FIXED AND THE TABLE SCROLLS.
    #
    # > **MARC:** *"Can we do something where the last 6 columns get a fixed width and the table
    # > will have a horizontal scroll instead of forcing them to be super narrow, and then their
    # > headers take up a bunch of vertical space, making the table very wonky?"*
    #
    # 📊 THE HEADER TEXT IS THE BINDING CONSTRAINT ON ALL SIX, WHICH IS WHY `auto` WENT WRONG.
    # Measured at 1600px with the table's own font — header on one line vs the widest body cell:
    #
    #     4th qtr           58px header   8px cell
    #     OT                38px header   8px cell
    #     Game              57px header   8px cell
    #     How close, late  113px header  36px cell
    #     Excitement        88px header  20px cell
    #     Commentary        93px header  67px cell
    #
    # ⚠️ **EVERY CELL IS SMALLER THAN ITS OWN HEADER**, so `auto` sized them from the header and
    # then, at a narrow viewport, collapsed them below it: measured at 1100px the three `auto`
    # columns fell to 45px each and the header row grew 45px -> 60px. **That is the "wonky"** —
    # a density loss in the body paid for by a taller header, which is the trap A165 named.
    #
    # 🚨 A191 (cfdb-main-R-2007). THE SIX WIDTHS ABOVE WERE WRONG AND THE HEADERS WRAPPED
    # ANYWAY — the defect A189 reported fixed, under a test that certified it.
    #
    # 📊 A189 MEASURED WITH A CANVAS `measureText` ON `getComputedStyle(el).font`, AND THAT
    # SHORTHAND CARRIES NEITHER `text-transform` NOR `letter-spacing`. This header row has
    # both, so it measured `4th qtr` where the browser draws `4TH QTR`, tracked — and the
    # padding it then added was 16px against an actual 17.6px. Measured in Chromium against a
    # live render, as the whole `th` box including the sort glyph and both paddings:
    #
    #     4th qtr          shipped 74px    browser needs  82.9px   -> wrapped to 3 lines
    #     OT               shipped 54px    browser needs  44.1px      fitted
    #     Game             shipped 73px    browser needs  59.7px      fitted
    #     How close, late  shipped 129px   browser needs 145.0px   -> wrapped to 3 lines
    #     Excitement       shipped 104px   browser needs 106.2px      fitted (the table gave
    #                                                                 it 106.2 regardless)
    #     Commentary       shipped 109px   browser needs 109.5px      fitted
    #
    # ✅ THE NUMBERS NOW HAVE ONE HOME AND A WAY TO BE RE-PROVEN: `ci/measure_header_widths.py`
    # holds them and re-measures them in a real browser on demand, and
    # `test_the_last_six_columns_are_fixed_and_fit_their_own_headers` asserts these widths
    # against that module rather than against a second copy. Read that file for why a `Range`
    # over the live header cannot answer this question.
    #
    # ⚠️ +17px ACROSS THE SIX, AND IT COSTS NOTHING, which is the point of `scroll=True`:
    # Marc asked for a horizontal scroll precisely so these columns would stop being rationed.
    # `sticky=2` keeps Scoreboard and Win probability in place while the six move.
    layout = [f"{scoreboard_px + _SCOREBOARD_GUTTER_PX}px", f"{widest + 12}px",
              "85px", "47px", "62px", "147px", "109px", "112px"]

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
            # A191: the caption's scoreboard sentence, on the column it describes.
            Col("scoreboard", "Scoreboard", render=_scoreboard,
                title="Away over home, quarter by quarter, with overtime shown separately "
                      "and the final at the right"),
            # ⚠️ THE CURVE SITS BESIDE THE SCORE, not at the end of the row. It is the picture of
            # what the ordering claims, so it belongs where a reader looking at the outcome
            # already is — and Marc asked for it in exactly that place.
            # A191: the caption's three chart sentences, on the chart's own column.
            Col("curve", "Win probability", render=curve_cell,
                title="The home side's win probability on every play against the game clock, "
                      "unsmoothed and filled from even \u2014 above the line the model gave "
                      "the home side the better chance, below it the away side. Quarter marks "
                      "fall at the same place on every chart, so a game that went to overtime "
                      "is simply longer. A cut line at the end means CFBD's feed stopped "
                      "before the game did."),
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
            # ⚠️ A189: THE TOOLTIPS CARRY WHAT THE REMOVED CAPTION CARRIED. Without them
            # `4th qtr` / `OT` / `Game` are three bare nouns — the caption was the only thing
            # saying they count LEAD CHANGES.
            # A191: "A tie is not a lead" was in the caption and belongs here — it is the
            # rule this column counts by, and it is the only one of the three that needs it.
            Col("scoreboard_lead_changes_fourth_quarter", "4th qtr", kind="num",
                title="Lead changes in the fourth quarter. A tie is not a lead, so a game "
                      "that drew level and went ahead again changed hands once"),
            Col("scoreboard_lead_changes_overtime", "OT", kind="num",
                title="Lead changes in overtime"),
            # ⚠️ A164. MARC MOVED A DISPLAYED COLUMN, NOT THE SORT — Today v04: *"Move Lead
            # Changes Game between OT Lead Changes and How Close Late."* `MOST_EXCITING_ORDER`
            # is untouched and the caption still describes the ordering, which is unchanged.
            # ✅ `layout` DOES NOT MOVE AND THAT IS ASSERTED, NOT ASSUMED: it pins only the first
            # two columns and the six that follow are all "auto", so two of them swapping is
            # invisible to it. `test_most_exciting_layout_pins_only_the_first_two_columns` holds
            # that property, because a `layout` silently out of step with the columns shows up
            # only on a wide viewport.
            Col("scoreboard_lead_changes", "Game", kind="num",
                title="Lead changes in the whole game"),
            Col("mean_distance_from_even_fourth_quarter_onward", "How close, late", kind="num", dp=3),
            Col("excitement_index", "Excitement", kind="num", dp=1),
            # 🚨 A144. THE OUTCOME GLYPH JOINS THE LINK IN ONE CELL — Marc: *"Put them in the
            # top row of the cell, the ESPN link below in the same cell."* `_commentary` says
            # which of `glyphs.winner`'s four None-reasons can occur on a panel of completed
            # games, and why the Matchup half of his sentence is not here.
            # ⚠️ `stacked=True` IS MARC'S "carriage return", AND IT IS THE ONLY PANEL THAT GETS
            # IT. The two recap panels get the horizontal gap he asked for there instead —
            # see `_commentary`, which measured all three before choosing.
            # A191: "commentary links go to ESPN" was the tail of the caption's source line.
            Col("espn", "Commentary", render=lambda r: _commentary(r, scope, stacked=True),
                title="Outcome marks for the game; the link goes to ESPN"),
        ], layout=layout, anchor="most-exciting",
            # 🚨 A189 (cfdb-main-R-1927). THE `caption=` IS GONE — Marc: *"The paragraph about
            # methodology should be removed below the table showing the Most Exciting games."*
            #
            # ⚠️ WHAT IT SAID IS NOT LOST, IT MOVED: the three lead columns carry one-line
            # `title` tooltips naming what they count, and the ORDERING sentence was already
            # in the `st.caption` above this table — it was duplicated here, which is part of
            # why it read as a paragraph of methodology.
            #
            # 🚨 AND THE TABLE NOW SCROLLS RATHER THAN COMPRESSING. `sticky=2` pins Scoreboard
            # and Win probability, which are the two Marc said were "showing completely"; the
            # six fixed columns scroll past them. See `layout` above for the measurements.
            scroll=True, sticky=2))


def _upset_score(row) -> str:
    """The final, loser's score first — e.g. `24–31`. A189 (cfdb-main-R-1929).

    > **MARC:** *"Add the scores"* (Biggest upsets)

    🚨 READ, NOT RECOMPUTED. `home_points` and `away_points` are published on `srv_game` and are
    what every other panel on this page shows; deriving the pair from `actual_margin` and one
    side's score would be metric arithmetic in a page (§4.2.1) **and** a second source for a
    number the frame already carries — the drift R-544 cost this module once already, on this
    very frame, when `ats` was computed here and had its sign inverted on every graded game.

    🚨 A191 (cfdb-main-R-2002). THE LOSER COMES FROM THE RESULT, NOT FROM A FAVORITE
    DEFINITION — and A189 got that wrong in the one place it can be told apart.

    📊 MEASURED ON LIVE SERVING, 2026 WEEK 3: Wyoming at Central Michigan rendered `24–10`,
    winner first, while every other row read loser first. Wyoming (away) scored 10, Central
    Michigan (home) 24, and the row carries **`spread_favorite_side = away` against
    `moneyline_favorite_side = home`** — `favorite_definitions_disagree` is true. A189 read the
    moneyline side first, so it named the WINNER as the favorite and printed the pair in that
    order. The panel's own "Lost" label reads the SPREAD side, so one row said two things.

    ⚠️ "THE LOSER IS THE FAVORITE" WAS TRUE OF EVERY OTHER ROW, WHICH IS WHAT MADE IT SURVIVE.
    A definition that is right 85 times out of 86 reads as correct on any render anyone looks
    at. **`min`/`max` over the two published scores cannot disagree with the scoreboard**, and
    it needs neither favorite column — so the two definitions being in conflict stops being a
    thing this cell has an opinion about.

    ⚠️ THIS IS NOT METRIC ARITHMETIC (§4.2.1). Nothing is computed: both numbers are published
    and both are printed, and the only decision is which of the two goes first — an ordering,
    like the en dash beside it. An en dash, not a hyphen: it is a score pair, and the site uses
    `–` for that everywhere else.
    """
    home, away = row.get("home_points"), row.get("away_points")
    if home is None or away is None or pd.isna(home) or pd.isna(away):
        return ""
    home, away = int(home), int(away)
    return f"{min(home, away)}–{max(home, away)}"


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


# A173: Schedule's layout, declared rather than derived — the same reasoning as R-622's
# `LEGEND_SUBSECTION_COLUMNS`. ⚠️ NOT Schedule's INVENTORY: `Result` is absent because A164
# removed the winner arrows, and `Examples` is absent because Today draws no result strip.
LEGEND_COLUMN_WEIGHTS = [1, 2]
LEGEND_LEFT_GROUPS = ["Game"]
STRIP_GROUP = "Against the line"
LEGEND_SUBSECTION_COLUMNS = [
    ["Outcome", "Against the Spread"],
    ["Against Over/Under", "Misc"],
]


def _legend(df=None) -> None:
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

    # 🚨 A173 (cfdb-main-R-1703). THE BANDS ARE PASSED NOW, AND NOT PASSING THEM WAS THE WHOLE
    # OF THE INCONSISTENCY MARC NAMED.
    #
    # 📊 `strip_entries()` with no argument renders the LEVEL NAMES — "Upset", "upset by more
    # than a touchdown", "upset by more than two touchdowns". With bands it renders the
    # NUMBERS — "Upset by 7 or fewer", "Upset by 8–14", "Upset by 15+". Schedule passed its
    # frame and Today passed nothing, so **the same three marks carried different words on two
    # pages a reader moves between, and the vaguer page was the one he was looking at.**
    #
    # ⚠️ AND THE FRAME HAS TO CARRY THE COLUMNS OR THIS IS THEATRE. `metrics.from_frame`
    # degrades to `DEFAULTS` when they are absent — deliberately, *"because a page that raised
    # because one row was null would be trading a wrong label for a blank screen"* — so a
    # legend can show plausible numbers that were never read from anything.
    # 📊 A173 MEASURED IT: before this round **no query on the site selected either column**,
    # so SCHEDULE's numbers were the defaults too. They were right only because the shipped
    # defaults (7, 14) happen to equal the published values. `_completed_games` now selects
    # both, so Today's labels are read from the data (cfdb-main-R-1704).
    bands = metrics.upset_bands(*metrics.from_frame(df))
    band_labels = dict(zip(("upset", "big", "blowout"), bands))

    # Schedule's layout, copied: one popover at container width, an outer 1:2 split, and the
    # long group's four subsections across a nested pair. ⚠️ THE INVENTORY IS NOT COPIED —
    # Schedule's Game group lists five marks and its Result group two, and `NEUTRAL`, `DOME`
    # and `MOVE_GLYPH` appear in this file zero times. R-178 cuts both ways.
    # ⚠️ THE STRIP RENDERS FROM `strip_subsections`, NOT FROM `strip_entries`, and the first
    # draft appended BOTH — leaving a `groups += strip_entries(bands)` whose result nothing
    # drew. A staged break that removed its `bands` argument came back GREEN, which is how the
    # dead line was found: the rows a reader sees never came from it.
    subsections = dict(glyphs.strip_subsections(band_labels))
    by_title = dict(groups)

    def block(title, rows) -> str:
        return (f"<div class='cfdb-legend-side'>"
                f"<div class='cfdb-legend-title'>{title}</div>"
                + "".join(
                    f"<div class='cfdb-legend-row'>"
                    f"<span class='cfdb-legend-key'>{swatch}</span>"
                    f"<span>{label}</span></div>" for swatch, label in rows)
                + "</div>")

    def sub_block(heading) -> str:
        return (f"<div class='cfdb-legend-sub'>{heading}</div>"
                + "".join(
                    f"<div class='cfdb-legend-row'>"
                    f"<span class='cfdb-legend-key'>{swatch}</span>"
                    f"<span>{label}</span></div>"
                    for swatch, label in subsections[heading]))

    with st.popover("Legend", use_container_width=True,
                    help="What every mark on this page means"):
        left, right = st.columns(LEGEND_COLUMN_WEIGHTS)
        for title in LEGEND_LEFT_GROUPS:
            if title in by_title:
                left.markdown(block(title, by_title[title]), unsafe_allow_html=True)
        # The spanning title, emitted ONCE above the nested pair — Schedule's own reason:
        # `st.columns` has no colspan, so a heading inside one of them reads as a heading for
        # that column alone.
        right.markdown(f"<div class='cfdb-legend-side'>"
                       f"<div class='cfdb-legend-title'>{STRIP_GROUP}</div></div>",
                       unsafe_allow_html=True)
        for column, headings in zip(right.columns(len(LEGEND_SUBSECTION_COLUMNS)),
                                    LEGEND_SUBSECTION_COLUMNS):
            column.markdown(
                "<div class='cfdb-legend-side cfdb-legend-nested'>"
                + "".join(sub_block(heading) for heading in headings)
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
    # 🚨 `ats` IS GONE WITH THE LIST THAT READ IT — A189 (cfdb-main-R-1929).
    #
    # It was `fav_margin - spread`: **metric arithmetic in a page**, which is the line §4.2.1
    # draws, and R-544 records what it cost when the sign was inverted on every graded game.
    # The underdog covers list was its only consumer; removing that section without removing
    # this would have left a contract violation computed for nobody.
    #
    # ⚠️ IF IT IS EVER NEEDED AGAIN IT COMES FROM THE MODEL, NOT FROM HERE. `srv_game_team`
    # already publishes `ats_margin_final` with `covered_final` beside it, at game x TEAM
    # grain — the grain difference is why it was recomputed here rather than read, and that is
    # a model round, not a page one.
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
    # 🚨 A189: `covers` IS GONE — Marc: *"Biggest Underdog covers / Remove this section"*.
    # `ats` is still computed above and still used by `_movers`; nothing else fed this list.

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
         # A189: the final, loser first — Marc: *"Add the scores"*. Its own column rather than
         # folded into a team cell, so it reads as a score and stays where a reader expects.
         Col("score", "Score", render=_upset_score,
             # A191: the wording followed the fix. "The losing favorite" was the
             # definition `_upset_score` no longer uses — and on the one row where the
             # two favorite columns disagree it named the WINNER. See `_upset_score`.
             title="Final score, the losing side first"),
         # MARC: *"Market gave them should be ##.#%"* — `fmt.percent`, which A144 added because
         # the site had no percent shape and was about to get its second inline f-string.
         Col("fav_win_prob", "Market gave them",
             render=lambda r: fmt.percent(r.get("fav_win_prob"))),
         Col("espn", "Commentary", render=lambda r: _commentary(r, scope))],
        caption="Ranked by the loser's pregame market-implied win probability.",
        anchor="how-the-week-went-against-the-market")

    disagree = int(graded["favorite_definitions_disagree"].fillna(False).sum())
    if disagree:
        st.caption(
            f"\u26a0\ufe0f In {disagree} of these games the spread and the moneyline named "
            "different favorites. This list uses the moneyline, because that is what an "
            "implied win probability comes from.")


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


# 🚨 A190 (cfdb-main-R-1941). TEN, AND THE ANSWER TO MARC'S "10 OR 20" IS MEASURED.
#
# > **MARC, v11:** *"10 or 20"*.
#
# ⚠️ AN EARLIER DRAFT OF THIS COMMENT CITED 26.4px A ROW AND A 380px CHART, AND BOTH WERE
# WRONG. 380 is the SVG's **viewBox** height, not what it draws — the chart scales to its
# column, so it renders 673px at 1680 and 351px at 1100. The row figure was never measured at
# all. 📊 Measured in Chromium with the sidebar open, after the row became two lines:
#
#     row 44.8px · header 22.1 · footnote 24.8  ->  ten rows draw 502px
#
#     1680px   chart 673px   table 502px   fits, 171px to spare
#     1440px   chart 540px   table 502px   fits
#     1280px   chart 451px   table 502px   51px past the chart
#     1100px   chart 351px   table 502px   151px past the chart
#
# ✅ **TWENTY DOES NOT FIT AT ANY WIDTH TESTED** — 943px, against a 673px chart at the widest.
# So ten it is, and the report puts the numbers to Marc rather than deciding his range for
# him. ⚠️ Raising it is this one constant.
_DISTANCE_TOP_N = 10


def _distance_table(ranked, centre, population: int) -> str:
    """The companion table: how far the strongest teams sit from the median intersection.

    > **MARC, v11:** *"measures how far the top-right data points are from the intersection of
    > the 2 means or medians showing the dotted line… the longest hypotenuse."*

    ⚠️ THE RANK IS THE DISTANCE RANK AND THE HEADER SAYS SO. A column headed "#" beside team
    logos on a page that also draws AP polls would be read as the AP rank by anyone not told
    otherwise — and this panel's own hover shows the AP rank two inches away. **A true-looking
    label on a different number is §4.3's worst form**, and it is the defect A153 was called in
    to fix on Most Exciting.

    ⚠️ THE DISTANCE COLUMN IS DROPPED, NOT SHRUNK. Marc allowed it *"only if it fits"*; at 18%
    of the row a sixth numeric column pushes the team name to an ellipsis, and the name is the
    thing being ranked. **The number is in the header tooltip's explanation and on the row's
    own `title`, so it is one hover away rather than gone.**

    🚨 AND THE ROW IS TWO LINES, BECAUSE SIX COLUMNS DO NOT FIT ON ONE AT THE WIDTH HE ASKED
    FOR. 📊 Measured in Chromium at 1440 with the sidebar open, from clones in an off-screen
    nowrap box (A191/A192's method — never a box that is already clipped):

        rank 17.6 + logo 17.6 + name-and-record 130.7 + gained 32 + allowed 32 + gaps 16
          = 245.9px needed, against 168.4px available at 18% of the row

    **A first pass shipped one line and clipped 8 of 10 team names at 1440 and 10 of 10 at
    1100** — the exact defect A192 had just spent a round removing from the player cards.
    Marc's band is 15-20%; 25% would be needed for one line, so the row wraps instead: the
    name gets the full width on line one and the three small facts sit under it.

    ⚠️ AND BELOW ~1400px THE TABLE GOES UNDER THE CHART BY ITSELF. `.cfdb-far` carries a
    `min-width` equal to what line one needs, and Streamlit's column row is `flex-wrap:wrap`,
    so the column simply cannot shrink past it and drops to its own full-width line. **That is
    Marc's "the table stacks below the chart" case, handled by the container rather than by a
    breakpoint** — which matters because the board's width depends on the sidebar.
    """
    if not ranked:
        # AC-G.11: say WHICH absence. An empty quadrant is a real state — a conference filter
        # can leave nobody better than the median on both axes — and it is not a failure.
        return ("<div class='cfdb-far'><div class='cfdb-far-head'>Furthest from the "
                "median</div><div class='cfdb-far-none'>No team in this scope is better "
                "than the median on both axes.</div></div>")

    tip = ("Straight-line distance from the intersection of the two dotted median lines, "
           "in yards per game, for teams better than the median on BOTH axes. "
           "This is the distance rank, not the AP rank.")
    out = [f"<div class='cfdb-far'><div class='cfdb-far-head' title='{html.escape(tip)}'>"
           f"Furthest from the median</div>"]
    for position, (distance, row) in enumerate(ranked, start=1):
        logo = (f"<img class='cfdb-far-logo' src='{html.escape(str(row['logo_url']))}' alt=''/>"
                if row.get("logo_url") and not pd.isna(row["logo_url"]) else
                "<span class='cfdb-far-logo'></span>")
        record = ("" if not row.get("record_before_display") or pd.isna(row["record_before_display"])
                  else f"<span class='cfdb-far-rec'>{html.escape(str(row['record_before_display']))}</span>")
        row_tip = (f"{row['team']} — {distance:.1f} yards per game from the median "
                   f"intersection; {row['y']:.1f} gained, {row['x']:.1f} allowed")
        out.append(
            f"<div class='cfdb-far-row' title='{html.escape(row_tip)}'>"
            f"<span class='cfdb-far-rank'>{position}</span>{logo}"
            f"<span class='cfdb-far-team'>{html.escape(str(row['team']))}</span>"
            # ⚠️ COMPACT, BECAUSE THE WORDS WRAPPED. "2-0 · 702 gained · 203 allowed" drew
            # over two lines inside a 160px column, taking the row to 61.2px and the table
            # past the bottom of the chart. The footnote below already says which number is
            # which, so repeating it on all ten rows bought nothing and cost the layout.
            f"<span class='cfdb-far-meta'>{record}"
            f"<span class='cfdb-far-num'>{row['y']:.0f}</span>"
            f"<span class='cfdb-far-slash'>/</span>"
            f"<span class='cfdb-far-num'>{row['x']:.0f}</span></span></div>")
    if centre:
        out.append(f"<div class='cfdb-far-foot'>Gained / allowed per game. Median "
                   f"{centre[1]:.0f} / {centre[0]:.0f} over {population} teams shown.</div>")
    out.append("</div>")
    return "".join(out)


def _scatter_medians(rows):
    """`(mid_x, mid_y, n_x, n_y)` for the rendered frame, or None. A190 (cfdb-main-R-1939).

    🚨 ONE SOURCE, BECAUSE TWO THINGS NOW DEPEND ON THESE NUMBERS. The chart draws the dotted
    lines from them and the distance table measures from their intersection — and Marc's ask
    is explicitly about *"the intersection of the 2 means or medians showing the dotted
    line"*. **If the table computed its own, the two could disagree and the table would be
    measuring from a centre the reader cannot see.** That is R-645's class: one quantity, two
    computations, eventual drift.

    ⚠️ STILL NOT A SERVING METRIC, AND §4.2.1 IS STILL NOT ENGAGED. This is a statistic OF THE
    ROWS ON SCREEN — the panel is week-scoped and conference-filtered, so it moves with what
    is being looked at, exactly as `_spark_max` does (cfdb-main-R-1750). The test that decides
    the hard cases is *how many consumers can this number have*, and the answer is **this
    drawing and the table beside it, which are the same picture**.
    """
    values_x = [float(r["x"]) for r in rows if r.get("x") is not None]
    values_y = [float(r["y"]) for r in rows if r.get("y") is not None]
    if not values_x or not values_y:
        return None
    return (statistics.median(values_x), statistics.median(values_y),
            len(values_x), len(values_y))


def _distance_ranking(rows, limit: int = 10):
    """The top-right teams, ordered by distance from the median intersection.

    > **MARC, v11:** *"measures how far the top-right data points are from the intersection of
    > the 2 means or medians showing the dotted line… the longest hypotenuse."*

    🚨 THREE DECISIONS, EACH STATED BECAUSE EACH COULD REASONABLY HAVE GONE THE OTHER WAY:

    **The centre is the MEDIAN intersection**, not the mean, because the dotted lines he is
    pointing at are medians (`_scatter_medians`). Measuring from a centre the chart does not
    draw would make the table's "distance" unverifiable by eye.

    **Only the top-right quadrant qualifies** — better than the median on BOTH axes. On this
    chart that is more yards gained (`y > mid_y`) and FEWER yards allowed (`x < mid_x`),
    because the x axis runs right-to-left (A176). ⚠️ **Getting that inequality backwards would
    rank the worst teams while looking entirely plausible**, which is why it is asserted.

    **Distance is √(Δgained² + Δallowed²) in yards per game.** Both axes are already the same
    unit, so no scaling is needed and none is applied — a normalised distance would be a
    different, unstated statistic.

    ⚠️ FEWER THAN `limit` TEAMS IS NORMAL, NOT AN ERROR. A conference filter can leave a
    handful of teams, and a quadrant can hold two. The caller shows what there is and says how
    many (AC-G.11).
    """
    medians = _scatter_medians(rows)
    if not medians:
        return [], None
    mid_x, mid_y, _n_x, _n_y = medians
    corner = []
    for r in rows:
        x, y = r.get("x"), r.get("y")
        if x is None or y is None:
            continue
        if float(y) > mid_y and float(x) < mid_x:
            dx, dy = mid_x - float(x), float(y) - mid_y
            corner.append((math.hypot(dx, dy), r))
    corner.sort(key=lambda pair: pair[0], reverse=True)
    return corner[:limit], (mid_x, mid_y)


def _scatter_svg(rows, x_dom, y_dom, x_step=100, y_step=100, width=560, height=380) -> str:
    """The scatter itself. Inline SVG in currentColor, following lib/distribution.py's
    precedent — one series, one hue, no legend, hairline axes (the chart standard's §7).

    🚨 A176 (cfdb-main-R-1761). MARC TRANSPOSED IT, AND THE DIRECTION LOGIC MOVED WITH THE AXIS
    RATHER THAN BEING REWRITTEN.

    > **MARC, v09:** *"Switch Y and X axis, so that Y is Yards gained (top is better), and X is
    > yards allowed (right is smaller and better)."*

    ⚠️ BOTH AXES NOW RUN AGAINST THE NAIVE MAPPING, and that is the whole design decision.
    **Y is yards gained and MORE is better, so it must increase UPWARD** — which in SVG means
    inverting, because y grows downward. **X is yards allowed and FEWER is better, so it must
    decrease RIGHTWARD** — also an inversion. The pair is what keeps "up and to the right is
    stronger" true, which is how everyone scans a scatter before reading a word of it.

    ⚠️ THE CAPTIONS MOVED WITH THEM. A caption left on the old axis is `cfdb-main-R-1082`'s
    defect, and it cost a round.

    An axis label alone would not carry this, so the direction is stated three ways: arrows on
    both axis titles, the words "better" on each, and a corner marker. No colour scale, no
    threshold line, no quadrant shading — none of those judgements has been made.
    """
    pad_l, pad_r, pad_t, pad_b = 56, 18, 20, 46
    pw, ph = width - pad_l - pad_r, height - pad_t - pad_b
    x0, x1 = x_dom
    y0, y1 = y_dom

    def sx(v):
        # A176: X is yards ALLOWED and right is SMALLER, so x DECREASES rightward.
        return pad_l + (x1 - float(v)) / (x1 - x0) * pw

    def sy(v):
        # A176: Y is yards GAINED and top is MORE, so y INCREASES upward — an inversion,
        # because SVG's y grows downward. See the docstring: both axes now run against the
        # naive mapping, and that pair is what keeps "up and to the right is stronger" true.
        return pad_t + (y1 - float(v)) / (y1 - y0) * ph

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

    # ── A178 (cfdb-main-R-1853): THE MEDIAN LINES ──────────────────────────────────────────
    #
    # > MARC, v10: "Add bolder lines for the median values and label."
    #
    # ✅ §4.2.1 IS NOT ENGAGED, AND THE TEST IS THE ONE THAT DECIDES THE HARD CASES: "how many
    # consumers can this number have?" A median OF THE ROWS ON SCREEN has exactly one — this
    # drawing. It is a property of the rendered frame, like `_spark_max` (cfdb-main-R-1750),
    # not a published quantity a second panel could disagree with.
    #
    # 🚨 AND IT MOVES WITH THE FRAME, WHICH IS WHY THE LABEL CARRIES ITS POPULATION. The panel
    # is week-scoped and conference-filtered, so "median" is the median of whatever Marc is
    # looking at. A median line whose scope silently changed would be worse than no line —
    # AC-G.33 — so the count is in the label and the hover says what it counted.
    medians = _scatter_medians(rows)
    if medians:
        mid_x, mid_y, n_x, n_y = medians
        values_x, values_y = [0] * n_x, [0] * n_y
        gx, gy = sx(mid_x), sy(mid_y)
        parts.append(
            f"<line class='cfdb-sc-median' x1='{gx:.1f}' y1='{pad_t}' "
            f"x2='{gx:.1f}' y2='{pad_t + ph}'><title>Median yards allowed per game: "
            f"{mid_x:.1f}, over {len(values_x)} teams shown</title></line>")
        parts.append(
            f"<line class='cfdb-sc-median' x1='{pad_l}' y1='{gy:.1f}' "
            f"x2='{pad_l + pw}' y2='{gy:.1f}'><title>Median yards gained per game: "
            f"{mid_y:.1f}, over {len(values_y)} teams shown</title></line>")
        # The labels sit INSIDE the plot against their own line, because a label in the margin
        # would compete with the axis ticks that are already there.
        parts.append(
            f"<text class='cfdb-sc-median-label' x='{gx + 4:.1f}' y='{pad_t + 11}'>"
            f"median {mid_x:.0f}</text>")
        parts.append(
            f"<text class='cfdb-sc-median-label' x='{pad_l + pw - 4:.1f}' "
            f"y='{gy - 4:.1f}' text-anchor='end'>median {mid_y:.0f}</text>")

    # 🚨 A176. UNFILLED CIRCLES IN THE TEAM'S OWN COLOUR — Marc: *"Make these unfilled circles.
    # Color by Team color"*. The colour arrives COMPOSED from the caller as a `light-dark()`
    # string (`identity.accent_color`), so this function looks nothing up and the browser
    # resolves the theme (cfdb-main-R-1601).
    #
    # 📊 THE COLUMNS WERE CHECKED BEFORE THIS WAS BUILT: `srv_team_week` publishes
    # `color_on_light`, `color_on_dark` and `logo_url` at 0.00% null over the 1,932 team-weeks
    # this panel can draw — and publishes **no rank, no record and no percentile at all**.
    # Three of the six facts his hover names are not in the relation, and a join is what G-2
    # forbids. **Named as a gap in A176's report rather than worked around.**
    #
    # ⚠️ AND THE COLOURS COLLIDE: 138 teams resolve to 109 distinct light colours and 96 dark,
    # so roughly a fifth of marks share a hue with another. **Position is the encoding here and
    # colour is identification on top of it** — the same ruling A171 made for the win-
    # probability fill.
    # 🚨 A190 (cfdb-main-R-1937). THE MARKS, AND A RING ON THE ONES THE TABLE RANKS.
    #
    # > **MARC, v11:** the distance table should connect to the chart.
    #
    # The ring is drawn BEFORE the circle so the dot sits on top of it, and it is the team's
    # own colour at low opacity rather than a second hue — the panel already rules that
    # position is the encoding and colour is identification (A171/A176).
    hotspots = []
    for r in rows:
        cx, cy = sx(r["x"]), sy(r["y"])
        colour = r.get("accent") or "currentColor"
        if r.get("ranked_by_distance"):
            parts.append(
                f"<circle class='cfdb-sc-ring' cx='{cx:.1f}' cy='{cy:.1f}' r='8' "
                f"fill='none' stroke='{colour}' stroke-width='1.2'/>")
        parts.append(
            f"<circle class='cfdb-sc-pt' cx='{cx:.1f}' cy='{cy:.1f}' r='4' "
            f"fill='none' stroke='{colour}' stroke-width='1.4'>"
            # ⚠️ THE SVG `<title>` STAYS. It is what a screen reader announces and what a
            # browser with the stylesheet unloaded still shows; the HTML layer below is an
            # enhancement over it, not a replacement for it (AC-G.11's spirit — do not remove
            # the accessible answer to add a prettier one).
            f"<title>{esc(r['team'])} — {r['y']:.1f} gained, {r['x']:.1f} allowed "
            f"per game over {int(r['games'])} game(s)</title></circle>")
        hotspots.append(_scatter_hotspot(r, cx / width, cy / height, esc))

    # The good corner, named. A reader scans the shape first, so this is a mark and not prose.
    parts.append(f"<text class='cfdb-sc-corner' x='{pad_l + pw - 2}' y='{pad_t + 12}' "
                 f"text-anchor='end'>better \u2197</text>")
    # A176: the captions moved WITH their axes. X is now the defence and reads right-is-fewer;
    # Y is now the offence and reads up-is-more.
    parts.append(f"<text class='cfdb-sc-axis' x='{pad_l + pw / 2:.0f}' y='{height - 8}' "
                 f"text-anchor='middle'>"
                 f"fewer yards allowed per game \u2192 better</text>")
    parts.append(f"<text class='cfdb-sc-axis' transform='rotate(-90 12 {pad_t + ph / 2:.0f})' "
                 f"x='12' y='{pad_t + ph / 2:.0f}' text-anchor='middle'>"
                 f"\u2191 better \u2014 more yards gained per game</text>")

    # 🚨 A190 (cfdb-main-R-1938). AN HTML LAYER OVER THE SVG, BECAUSE AN SVG `<title>` IS
    # PLAIN TEXT AND MARC'S HOVER NAMES A LOGO.
    #
    # ⚠️ AND IT IS CSS-ONLY, WHICH IS A CONSTRAINT RATHER THAN A PREFERENCE. Streamlit's
    # `unsafe_allow_html` strips `<script>`, so there is no JS to position a tooltip with:
    # every hotspot carries its own tooltip as a child, shown by `:hover` and `:focus-within`.
    # **`:focus-within` with `tabindex` is what makes it work on a tap and on a keyboard** —
    # `:hover` alone is a mouse-only feature, and Marc's ask says hover, not mouse.
    #
    # ⚠️ THE PERCENTAGES MAP ONTO THE viewBox, WHICH IS WHY THE SVG MUST FILL ITS BOX. The
    # overlay is `inset:0` on a `position:relative` parent and each hotspot is placed at
    # `cx/width%` — correct only while the SVG is `width:100%;height:auto` with the viewBox's
    # own aspect ratio, so `theme.py` sets exactly that and a test asserts it.
    #
    # ⚠️ THE EDGE FLIP IS COMPUTED HERE, NOT IN CSS. A tooltip anchored left on a point in the
    # right-hand third is clipped by the chart's own box; `data-side` says which way to open,
    # from the point's own position, because CSS cannot ask where its element is.
    return (f"<div class='cfdb-scatter'><svg viewBox='0 0 {width} {height}' "
            f"role='img' aria-label='Yards gained per game against yards allowed per game; "
            f"stronger teams sit toward the top right'>{''.join(parts)}</svg>"
            f"<div class='cfdb-sc-layer'>{''.join(hotspots)}</div></div>")


def _scatter_hotspot(row, fx: float, fy: float, esc) -> str:
    """One focusable hotspot over a mark, carrying the hover Marc described.

    > **MARC, v09 + v10, combined:** logo, AP rank (or unranked), team, record, yards gained
    > per game with percentile, yards allowed per game with percentile — and an opponent.

    ⚠️ THE OPPONENT IS A LINE OF ITS OWN RATHER THAN PART OF THE TEAM'S, because the mark
    is the team's form ENTERING the week and not a game. Presenting the opponent as though the
    numbers described that matchup would be the R-1082 class — a label describing something
    other than what it sits on. **It is omitted entirely when no single week is in scope.**

    ⚠️ EVERY OPTIONAL FIELD IS TESTED WITH `pd.isna`, NOT FOR TRUTHINESS. `ap_rank` is null for
    113 of 138 teams and `NaN` is truthy (A191), so `if rank` would print "nan" as a rank on
    every unranked team — which is exactly the defect A191 spent a round removing from the
    Week average row.
    """
    side = "left" if fx > 0.58 else "right"
    vert = "up" if fy < 0.32 else "down"

    def px(value) -> str:
        """`p97` from a published percentile.

        🚨 A190 (cfdb-main-R-1942). THE COLUMN IS A FRACTION IN [0, 1], NOT A 0-100 FIGURE,
        AND THE FIRST DRAFT OF THIS SHIPPED `p1` FOR THE BEST OFFENCE IN THE COUNTRY.

        📊 CAUGHT IN THE RENDER, NOT IN THE CODE: the hover for Georgia — 576.5 yards gained
        per game, second most of 138 — read **`p1`**, and so did LSU's defence at 142.5
        allowed, the best in the country. Measured on live serving: Miami's 702.5 is
        `1.0000`, Washington State's 204.0 is `0.0000`. **`int(round(0.99))` is 1.**

        ⚠️ AND IT WOULD HAVE READ AS A PLAUSIBLE NUMBER. `p1` is a percentile, it is in range,
        and it appears next to a team that is genuinely at one extreme — nothing about it
        looks like a bug except that it is exactly backwards.

        ✅ THE DIRECTION WAS CHECKED SEPARATELY AND IS CORRECT: `_models.yml` records that
        `total_yards_allowed_percentile` **descends**, so higher is better on both axes — "a
        raw ascending percentile would put the worst defense in the country at p99". Verified
        against the rows: LSU (fewest allowed) 1.0000, UL Monroe (most) 0.0000.

        ⚠️ `x 100` IS RENDERING, NOT METRIC MATHS — §4.2.1 names this case exactly: "scaling
        ONE column by a CONSTANT WRITTEN IN THE CODE". The population sits on its own line
        below (AC-G.33), which is the site's own convention for a percentile.
        """
        if value is None or pd.isna(value):
            return ""
        return f"p{int(round(float(value) * 100))}"

    rank = row.get("rank")
    badge = ("" if rank is None or pd.isna(rank)
             else f"<span class='cfdb-sc-rank'>#{int(rank)}</span>")
    unranked = "" if badge else "<span class='cfdb-sc-unranked'>unranked</span>"
    logo = (f"<img class='cfdb-sc-logo' src='{esc(row['logo_url'])}' alt=''/>"
            if row.get("logo_url") and not pd.isna(row["logo_url"]) else "")
    record = ("" if not row.get("record_before_display") or pd.isna(row["record_before_display"])
              else f"<span class='cfdb-sc-record'>{esc(str(row['record_before_display']))}</span>")

    gained_pct, allowed_pct = px(row.get("total_yards_for_percentile")), px(row.get("total_yards_allowed_percentile"))
    pop = row.get("percentile_population")
    pop_note = ("" if pop is None or pd.isna(pop)
                else f"<div class='cfdb-sc-pop'>percentiles over {int(pop)} teams</div>")

    opponent = row.get("opponent")
    versus = ""
    if opponent:
        opp_logo = (f"<img class='cfdb-sc-logo' src='{esc(opponent['logo'])}' alt=''/>"
                    if opponent.get("logo") else "")
        opp_rank = (f"<span class='cfdb-sc-rank'>#{int(opponent['rank'])}</span>"
                    if opponent.get("rank") is not None else "")
        # ⚠️ THE WEEK IS NAMED BY NUMBER, NOT BY A DEICTIC. The panel's week is chosen by the
        # reader (R-428), so a phrase like the one R-428 forbids means whatever he last
        # clicked —
        # `test_the_week_floor_is_named_not_hardcoded_in_copy` refuses the phrase outright.
        # Printing the number is both allowed and more useful.
        versus = (f"<div class='cfdb-sc-vs'>{esc(opponent['label'])}: {esc(opponent['prep'])} "
                  f"{opp_logo}{opp_rank}{esc(opponent['name'])}</div>")

    return (
        f"<span class='cfdb-sc-hot' tabindex='0' "
        f"style='left:{fx * 100:.2f}%;top:{fy * 100:.2f}%'>"
        f"<span class='cfdb-sc-tip' data-side='{side}' data-vert='{vert}'>"
        f"<span class='cfdb-sc-head'>{logo}{badge}{unranked}"
        f"<span class='cfdb-sc-team'>{esc(row['team'])}</span>{record}</span>"
        f"<span class='cfdb-sc-stat'><b>{row['y']:.1f}</b> yards gained per game"
        f"{f' <i>{gained_pct}</i>' if gained_pct else ''}</span>"
        f"<span class='cfdb-sc-stat'><b>{row['x']:.1f}</b> yards allowed per game"
        f"{f' <i>{allowed_pct}</i>' if allowed_pct else ''}</span>"
        f"{pop_note}{versus}</span></span>")


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

        # 🚨 A176 (cfdb-main-R-1761). X AND Y SWAPPED AT THE SOURCE, not inside the drawing.
        # > **MARC, v09:** *"Switch Y and X axis, so that Y is Yards gained (top is better),
        # > and X is yards allowed (right is smaller and better)."*
        # The scale functions carry the DIRECTION; this carries which measure is which axis,
        # and keeping the two separate is what let the swap be a two-line change.
        xs = playable["total_yards_allowed_per_game"].astype(float)
        ys = playable["total_yards_for_per_game"].astype(float)

        # Domain rounded OUT to a whole tick, per the chart standard §0.2, so the bounds ARE
        # ticks and every render of this chart lands on the same round numbers.
        # A178: 100-yard increments (Marc, v10), so the DOMAIN rounds out to 100s too —
        # otherwise the bounds stop being ticks and the chart standard's §0.2 argument
        # ("every render lands on the same round numbers") quietly stops holding.
        def domain(series, step=100):
            lo = math.floor(series.min() / step) * step
            hi = math.ceil(series.max() / step) * step
            return (lo, hi if hi > lo else lo + step), step

        # 🚨 THE COLOUR IS COMPOSED HERE, NOT IN THE CHART (cfdb-main-R-1601). `_scatter_svg`
        # holds no team colours and looks none up; it receives a finished `light-dark(...)`
        # string the BROWSER resolves, so a mid-session theme flip is correct with no Python
        # in the loop. 📊 `color_on_light`/`color_on_dark` are 0.00% null on this population.
        # ── A190 (cfdb-main-R-1936): THE OPPONENT, LOOKED UP ONCE AND ATTACHED BY team_id ──
        # ⚠️ EMPTY WHEN NO SINGLE WEEK IS IN SCOPE — see `_week_opponents`. `.get` on a dict
        # built from an empty frame simply misses, so the hover omits the line with no branch.
        opponents = {}
        for _i, o in _week_opponents(scope).iterrows():
            name = o.get("opponent_team_display")
            if name is None or pd.isna(name):
                continue
            logo = o.get("opponent_logo_url")
            rank = o.get("opponent_rank")
            opponents[int(o["team_id"])] = {
                "name": str(name),
                # 🚨 `is_home` DECIDES THE PREPOSITION, and it is the team's own row: a home
                # team hosts ("vs"), an away team visits ("at"). Printing "vs" for both would
                # be wrong on half the rows and unnoticeable on any single hover.
                "prep": "vs" if bool(o.get("is_home")) else "at",
                "label": f"Week {int(scope.week)}",
                # ⚠️ `logo`, NOT `logo_url`. A blanket rename of the SCATTER ROW's keys to
                # their published column names swept this dict up too, and the reader still
                # asked for `logo` — so every opponent logo silently vanished while the line
                # itself kept rendering. 📊 Measured in the browser: 78 `.cfdb-sc-vs` lines,
                # **0 images inside them**. This dict is the hover's own vocabulary (the
                # receiver is in `check_page_reads.NOT_A_ROW` for exactly that reason), so
                # its keys are deliberately NOT column names.
                "logo": None if logo is None or pd.isna(logo) else str(logo),
                "rank": None if rank is None or pd.isna(rank) else int(rank),
            }

        rows = [{"team": t, "x": x, "y": y, "games": g,
                 "accent": identity.accent_color(
                     {"color_on_light": cl, "color_on_dark": cd}),
                 "rank": rk, "record_before_display": rec, "logo_url": lg,
                 "total_yards_for_percentile": gp, "total_yards_allowed_percentile": ap, "percentile_population": pp,
                 "team_id": int(tid), "opponent": opponents.get(int(tid))}
                for t, x, y, g, cl, cd, rk, rec, lg, gp, ap, pp, tid in zip(
                    playable["team_display"], xs, ys, playable["games_counted"],
                    playable["color_on_light"], playable["color_on_dark"],
                    playable["ap_rank"], playable["record_before_display"],
                    playable["logo_url"], playable["total_yards_for_percentile"],
                    playable["total_yards_allowed_percentile"],
                    playable["percentile_population"], playable["team_id"])]

        # ── A190 (cfdb-main-R-1940): THE DISTANCE RANKING, AND THE RING THAT CONNECTS IT ───
        # The ranking is computed BEFORE the chart is drawn so the top ten can be marked on
        # the marks themselves — the table and the chart are one picture or they are two
        # things the reader has to reconcile.
        ranked, centre = _distance_ranking(rows, limit=_DISTANCE_TOP_N)
        for _d, r in ranked:
            r["ranked_by_distance"] = True

        x_dom, x_step = domain(xs)
        y_dom, y_step = domain(ys)

        # 🚨 THE TABLE TAKES THE NARROW SIDE — Marc: *"Table on the right, 15-20% of the row
        # width; the chart takes the rest."* 82/18 sits inside that band.
        # ⚠️ Streamlit stacks columns itself below ~640px of container, so the "narrow
        # viewport" case Marc asked about needs no breakpoint of ours: the table falls under
        # the chart on its own.
        chart_col, table_col = st.columns([82, 18], gap="small")
        with chart_col:
            st.markdown(_scatter_svg(rows, x_dom, y_dom, x_step, y_step),
                        unsafe_allow_html=True)
        with table_col:
            st.markdown(_distance_table(ranked, centre, len(rows)),
                        unsafe_allow_html=True)

        # ⚠️ SAY WHAT WAS DROPPED AND WHY. A silently shorter chart is the same defect as a
        # silently shorter list — the reader cannot tell 130 teams from 130 of 136.
        # 🚨 A176. THIS PROSE DESCRIBED THE OLD ORIENTATION AND HAD TO MOVE WITH THE AXES.
        # It read *"the vertical axis runs downward so fewer yards allowed is higher"* — true of
        # the chart before the swap and false of the one below it. ⚠️ `cfdb-main-R-1082`'s defect
        # is a caption left on the axis it used to describe, and the SVG's own two captions are
        # not the only ones on this panel: **this `st.caption` is a third, and my first pass
        # tested the two inside the SVG and missed it.** A test now drives the real `_profile`
        # and reads this string (cfdb-main-R-1763).
        note = (f"{len(playable)} teams. Each point is one team as it stood ENTERING "
                f"{scope.describe()} — every figure is over completed games in earlier weeks, "
                f"never the selected week's own game. Up and to the right is stronger on both "
                f"sides: the vertical axis is yards GAINED, so higher is more, and the "
                f"horizontal axis runs right-to-left, so further right is FEWER yards "
                f"allowed.")
        if dropped:
            note += (f" {dropped} teams are not plotted because they had no completed game "
                     f"before the selected week.")
        st.caption(note)


# Marc's number, held as a number rather than folded into the expression: *"1.15 of the table
# MAX"*. See `_spark_max`, and `test_the_yardage_bars_leave_headroom_for_their_labels`.
_SPARK_HEADROOM = 1.15


def _week_average_row(scope) -> dict:
    """The week's average yardage over **every team in an FBS game**, not just the rows shown.

    🚨 A189 (cfdb-main-R-1931). > **MARC:** *"Can we add a row that is the average for the week
    (all teams involved in an FBS game, not just the ones we are showing)"*

    📊 HIS WORDS AND THE PAGE'S OWN FILTER ARE DIFFERENT POPULATIONS, AND THE DIFFERENCE IS
    MATERIAL — measured on live published serving, 2026 week 3:

        every team in an FBS game (his words)   150 team-games, 18 of them non-FBS   380 yards
        FBS-classified teams only (the filter)  132 team-games,  0 non-FBS           399 yards

    ⚠️ **HIS WORDS ARE APPLIED**: *"all teams involved"* includes the FCS side of an FBS game, and
    those eighteen teams pull the average down nineteen yards. The board above may be filtered to
    FBS by `scope`, so this row can describe a wider population than the rows it sits under —
    **which is exactly what he asked for**, and the caption says so rather than leaving a reader
    to assume the mean is of the visible rows.

    ⚠️ ONE QUERY, ONE RELATION, NO JOIN (G-2), AND THE MEAN IS COMPUTED IN SQL. A mean is a
    statistic of a stated population, not a rendering: computing it in the page would be the
    metric arithmetic §4.2.1 forbids, and it could not see the rows the page never fetched.
    """
    frame = query("""
        select count(*) as n,
               avg(total_yards) as total_yards,
               avg(rushing_yards) as rushing_yards,
               avg(passing_yards) as passing_yards
        from srv_game_team
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and is_completed and is_fbs_game
        limit 1
    """, {"season": scope.season, "season_type": scope.season_type, "week": scope.week})
    if frame is None or frame.empty or not int(frame.iloc[0]["n"] or 0):
        return {}
    row = frame.iloc[0]
    return {"n": int(row["n"]), "total_yards": row["total_yards"],
            "rushing_yards": row["rushing_yards"], "passing_yards": row["passing_yards"]}


def _team_score(row) -> str:
    """`W 38\u201317` / `L 17\u201338` — the result and the final, from published columns.

    A189. > **MARC:** *"Include the scores next to the teams"*

    ⚠️ `result` IS PUBLISHED AND IS NOT DERIVED HERE from comparing the two numbers: the view
    already decides what a win is, and a page re-deciding it is a second definition that can
    disagree (§4.2.1). The two points columns are read, not computed.
    """
    pf, pa, res = row.get("points_for"), row.get("points_against"), row.get("result")
    if pf is None or pa is None or pd.isna(pf) or pd.isna(pa):
        return ""
    mark = (str(res)[:1].upper() if res else "")
    return f"{mark} {int(pf)}\u2013{int(pa)}".strip()


def _spark_max(frame) -> float:
    """The ONE denominator every bar on the yardage board is drawn against.

    🚨 A175 (cfdb-main-R-1750). > **MARC:** *"proportionate and relative to the max of the Total
    column"* — so Total's max, for Total, Rush AND Pass alike.

    ⚠️ IT IS A PROPERTY OF THE RENDERED FRAME, NOT OF THE RELATION. The board is `depth`-limited
    and scope-filtered, so the denominator MOVES when Marc changes the depth radio or the week —
    which is correct: the bars compare the rows he is looking at, not the rows that exist.

    ⚠️ AND IT RETURNS 0 FOR AN EMPTY OR ALL-NULL FRAME, which `_spark_cell` reads as "draw no
    bar" rather than dividing by it. A single-row frame gives that row a full-width bar, which
    is honest — it is the max of what is shown.
    """
    if frame is None or getattr(frame, "empty", True) or "total_yards" not in frame.columns:
        return 0.0
    values = pd.to_numeric(frame["total_yards"], errors="coerce").dropna()
    top = float(values.max()) if len(values) else 0.0
    # 🚨 A189 (cfdb-main-R-1930). 1.15x THE TABLE MAX, NOT THE MAX ITSELF.
    #
    # > **MARC:** *"Can we change the fixed axis for the Total, Rush, Pass to be 1.15 of the
    # > table MAX? That will push the size of the bars down a little bit so the label isn't in
    # > the chart."*
    #
    # ⚠️ THE REASON IS THE LABEL, NOT THE BAR. `_spark_cell` right-aligns the number in the
    # CELL while the bar grows from the left, so the longest bar reached full cell width and
    # ran underneath its own value. Headroom keeps them apart without changing what a bar
    # MEANS — every bar still shares one denominator, which is the property A175 established.
    return top * _SPARK_HEADROOM if top > 0 else 0.0


def _spark_cell(row, field: str, frame) -> str:
    """One yardage cell: a bar from the left, the number right-aligned in the CELL.

    ⚠️ THE NUMBER IS NOT AT THE END OF THE BAR, and that is Marc's own last clause. A value
    riding the bar's end would encode the same quantity twice and line up with nothing.

    ⚠️ §4.2.1 IS NOT ENGAGED. A bar's width is a rendering proportion of one published number
    against another published number in the SAME FRAME — exactly what `distribution.thumbnail`
    already does — not a metric. **No percentage column is published for it.**
    """
    value = row.get(field)
    text = fmt.number(value, field, None)
    top = _spark_max(frame)
    if top <= 0 or value is None or (isinstance(value, float) and pd.isna(value)):
        return f"<span class='cfdb-spark'><span class='cfdb-spark-value'>{text}</span></span>"
    share = max(0.0, min(1.0, float(value) / top))
    return (f"<span class='cfdb-spark'>"
            f"<span class='cfdb-spark-bar' style='width:{share * 100:.1f}%'></span>"
            f"<span class='cfdb-spark-value'>{text}</span></span>")


def _leaderboards(scope, depth: int) -> None:
    st.subheader("Leaderboards")

    # ⚠️ THE DECLARED VIEW FOLLOWED THE QUERY. `test_the_views_named_in_sections_are_exactly_the
    # _views_the_module_reads` caught this the moment `_team_yardage` changed relation — the
    # section still named `srv_team_game_log` while the module read `srv_game_team`, and a
    # degraded-state card would have named a view this panel no longer touches.
    with states.section("srv_game_team", dataset=DATASETS["srv_game_team"]):
        teams = _team_yardage(scope, depth)
        # 🚨 A189 (cfdb-main-R-1931). THE WEEK AVERAGE IS APPENDED AS A ROW, PINNED LAST.
        #
        # ⚠️ PINNED RATHER THAN SORTED WITH THE REST, and it has to be: a mean is not a
        # competitor. Sorting would drop it into the middle of the ranking as though it were a
        # team, and on a sorted board it would land somewhere different every click.
        # **Last rather than first** because the board is a ranking — a reader coming to see
        # who led should meet the leader, and the benchmark reads naturally as the line the
        # board is measured against once the rows above it are read.
        #
        # ⚠️ `sortable="applied"` IS WHAT KEEPS IT THERE. `table.render` would otherwise sort
        # the frame including this row; "applied" means the caller has ordered it and render
        # draws the links without re-sorting. The panel arrives ordered by the SQL already.
        week_avg = _week_average_row(scope)
        if week_avg:
            teams = pd.concat([teams, pd.DataFrame([{
                "team_display": f"Week average \u00b7 {week_avg['n']} teams",
                "is_summary_row": True,
                "total_yards": week_avg["total_yards"],
                "rushing_yards": week_avg["rushing_yards"],
                "passing_yards": week_avg["passing_yards"],
            }])], ignore_index=True)
            # 🚨 A191 (cfdb-main-R-2010). `pd.concat` FILLS THE MISSING FLAG WITH `NaN`, AND
            # NaN IS TRUTHY — SO A189's `if r.get("is_summary_row")` FIRED ON EVERY ROW.
            #
            # 📊 MEASURED IN A REAL BROWSER AGAINST LIVE SERVING, 2026 week 3:
            # `.cfdb-summary-row` matched **11 elements, not 1** — the benchmark row and all
            # ten teams. Every team on the board was rendering as a plain italic label:
            # **no logo, no rank badge, no record, and no link to its team page.** It is live
            # in production at `a7c50bb` and the same count comes back from the A189 baseline
            # render, so this shipped with A189 rather than arriving here.
            #
            # ⚠️ IT DID NOT LOOK BROKEN, WHICH IS WHY IT SURVIVED A RENDER REVIEW. Ten italic
            # team names under a heading read as a deliberately plain table; the missing
            # affordances are only visible if you know the cell is supposed to carry them.
            # The `nan` in the Opponent column — the defect Cowork DID catch — was this same
            # NaN one column to the right, where it happened to print.
            #
            # ✅ NORMALISED ONCE, HERE, RATHER THAN GUARDED AT EACH READER. Two columns read
            # this flag and a third could; `fillna(False).astype(bool)` makes the column a
            # real boolean so `r.get(...)` means what every reader assumes it means.
            teams["is_summary_row"] = teams["is_summary_row"].fillna(False).astype(bool)
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
                # ⚠️ A189: THE SUMMARY ROW IS NOT A TEAM, so it does not get a team's cell —
                # no logo, no rank badge, no record, and no link to a team page that does not
                # exist. Styled as a label so it reads as the benchmark it is.
                Col("team_display", "Team",
                    render=lambda r: (
                        f"<span class='cfdb-summary-row'>{r.get('team_display')}</span>"
                        if r.get("is_summary_row") else
                        _team_identity(
                            r, "", slug_field="team_slug", display_field="team_display",
                            logo_field="team_logo_url", rank_field="team_rank",
                            record_field="record_before_display"))),
                # 🚨 A175 (cfdb-main-R-1751). THE OPPONENT IS THE SAME CELL AS THE TEAM NOW.
                # > **MARC, Today v04:** *"Opponent - should look the same as the Team column
                # > layout."* It was a bare string beside a Team column carrying a logo, a rank
                # badge and a record.
                #
                # ⚠️ ONE FACT SHORT OF PARITY, AND IT IS A PUBLISHED GAP RATHER THAN A CHOICE:
                # `srv_game_team` carries `opponent_team_slug` (0 null), `opponent_logo_url`
                # (6.1% null) and `opponent_rank` (99% null — unranked is a fact, AC-G.11) and
                # **publishes NO opponent record column at all**, checked against
                # information_schema. The Team cell shows a record; this one cannot, and a join
                # to fetch one is the thing G-2 forbids. **Named in A175's report as the gap.**
                # 🚨 A191 (cfdb-main-R-2000). THE SUMMARY ROW HAS NO OPPONENT AND MUST NOT
                # BE GIVEN ONE. The Team column already branches on `is_summary_row`; this one
                # did not, so the week-average row went through `_team_identity` with every
                # opponent field absent.
                #
                # 📊 WHAT THAT DREW, AND WHY IT LOOKED LIKE A DATA FAULT RATHER THAN A BUG:
                # `pd.concat` fills the missing columns with `NaN`, and `team_cell`'s
                # `row.get(display_field) or "—"` **does not catch NaN — a float NaN is
                # truthy** — so the literal string `nan` was printed, beside
                # `logo_or_monogram(NaN, …)`'s grey placeholder disc. The em-dash fallback that
                # exists for exactly this case was one truthiness test away from firing.
                #
                # ⚠️ BLANK, NOT "—". The Score column beside it already returns "" for this row
                # (`_team_score`, on the same NaN), so a dash here would make the benchmark row
                # read as two different kinds of absence in adjacent cells (AC-G.11).
                Col("opponent", "Opponent",
                    render=lambda r: ("" if r.get("is_summary_row") else _team_identity(
                        r, "", slug_field="opponent_team_slug",
                        display_field="opponent_team_display",
                        logo_field="opponent_logo_url", rank_field="opponent_rank"))),
                # A189: the result and the final, beside the teams they belong to.
                # Marc: *"Include the scores next to the teams"*.
                Col("points_for", "Score", render=_team_score,
                    title="Result and final score for this team's game"),
                # 🚨 ONE DENOMINATOR FOR ALL THREE COLUMNS, AND IT IS TOTAL'S MAX.
                # > **MARC:** *"Make them all proportionate and relative to the max of the Total
                # > column."* A per-column max would make a 90-yard rushing game draw as long as
                # a 500-yard passing game, which is the opposite of what the bars are for.
                Col("total_yards", "Total", kind="num",
                    render=lambda r: _spark_cell(r, "total_yards", d)),
                Col("rushing_yards", "Rush", kind="num",
                    render=lambda r: _spark_cell(r, "rushing_yards", d)),
                Col("passing_yards", "Pass", kind="num",
                    render=lambda r: _spark_cell(r, "passing_yards", d)),
            ], caption=("Ranked by total offense, with each team's record going into the "
                        "game. The Week average row is every team that played in an FBS game "
                        "that week \u2014 including the FCS side of one \u2014 not only the "
                        "teams shown above."),
                anchor="leaderboards",
                # A189: the frame is ordered by the SQL and carries a pinned summary row;
                # re-sorting here would move the average into the middle of the ranking.
                sortable="applied"),
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
        # 🚨 A175 (cfdb-main-R-1754). THE TRIO PER CATEGORY, ENUMERATED FROM LIVE SERVING
        # RATHER THAN GUESSED — A166 learned the hard way that it is `SACKS` and not `SACK`,
        # and this relation is not the one the workbook reads. `srv_player_game_log`, 2026:
        #
        #     passing    AVG · C/ATT · INT · QBR · TD · YDS      <- C/ATT, not COMPLETIONS
        #     receiving  AVG · LONG · REC · TD · YDS
        #     rushing    AVG · CAR · LONG · TD · YDS             <- AVG, not YPC
        #
        # ✅ So Marc's obvious trios all exist here: YDS · TD · INT for a passer, YDS · TD · REC
        # for a receiver, YDS · TD · CAR for a runner. 📋 **WHICH THREE IS A FOOTBALL QUESTION
        # and §2.1 puts it with him** — these ship, and A175's report renders the alternatives
        # so his answer picks between pictures rather than unblocking the work.
        #
        # ⚠️ THE FIRST IS THE PRIMARY and it decides the ORDER of the board. `YDS` keeps the
        # ranking the panel has always had.
        yardage = [(label, _fold_metrics(
            _player_board(scope, depth, (category,), types), types, depth), types)
            for label, category, types in (
                ("QB", "passing", ("YDS", "TD", "INT")),
                ("Receiving", "receiving", ("YDS", "TD", "REC")),
                ("Rushing", "rushing", ("YDS", "TD", "CAR")))]
        states.render_or_state(
            # ⚠️ THE CONCATENATION DECIDES THE STATE, THE THREE FRAMES DRAW THE GRID. The state
            # machinery asks one question — is there anything at all? — and three columns that
            # are each separately empty is the same answer as one empty board. The renderer
            # ignores the frame it is handed and reads the columns it closed over, which is why
            # a column that IS empty still draws its heading.
            pd.concat([frame for _label, frame, _types in yardage])
            if yardage else pd.DataFrame(),
            "srv_player_game_log",
            "The player yardage board would be here.",
            f"No player box scores for {scope.describe()}. Box scores start in 2024.",
            # ⚠️ THE PER-COLUMN TRIOS DIFFER, so the card reads its labels from the frame's
            # own `metric_*` columns rather than from one list passed down here.
            renderer=lambda _d: _player_card_grid(yardage, "yards"),
        )

        st.markdown("**Touchdowns**")
        st.caption("A different board from yardage, and mostly different names on it.")
        touchdowns = [(label, _player_board(scope, depth, (category,), ("TD",)), ())
                      for label, category in (("QB", "passing"),
                                              ("Receiving", "receiving"),
                                              ("Rushing", "rushing"))]
        states.render_or_state(
            pd.concat([frame for _label, frame, _types in touchdowns])
            if touchdowns else pd.DataFrame(),
            "srv_player_game_log",
            "The touchdown board would be here.",
            f"No player box scores for {scope.describe()}.",
            renderer=lambda _d: _player_card_grid(touchdowns, "touchdowns"),
        )

        st.markdown("**Defensive leaders**")
        st.caption("Tackles, tackles for loss and sacks — three stat types on one category, "
                   "which is a different split from the two boards above.")
        defence = [(label, _player_board(scope, depth, ("defensive",), (stat_type,)), ())
                   for label, stat_type in (("Tackles", "TOT"),
                                            ("Tackles for loss", "TFL"),
                                            ("Sacks", "SACKS"))]
        states.render_or_state(
            pd.concat([frame for _label, frame, _types in defence])
            if defence else pd.DataFrame(),
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
# ── A178 (cfdb-main-R-1854): +25% VERTICAL SPACE, AND THE FONTS WITH IT ─────────────────────
#
# > MARC, v10: "diagonal/straight lines, look much better. Give it 25% more vertial space.
# > Increase fonts accordingly."
#
# 420 -> 525 is his 25% exactly. ⚠️ **The fonts are scaled by the SAME factor rather than
# nudged**, because the thing he is buying is the ratio of ink to space: 25 ranks over 420px
# is a 16.8px pitch against an 11px font, and raising only the height would make the labels
# look smaller rather than the chart look roomier. At 525 the pitch is 21.0px and the font
# 13.75 -> 14, so the ratio is very nearly preserved (0.65 -> 0.67).
_BUMP_HEIGHT = 525
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
# 🚨 A176 (cfdb-main-R-1760). MARC REVERSED HIS OWN v04 INSTRUCTION, AND THE MEASUREMENT SAYS
# HE IS RIGHT — FOR A REASON NEITHER HE NOR THE PROMPT NAMED.
#
# > **v04:** *"Can we switch to a bump chart look where the changes to the lines are right
# > angles instead of diagonal lines."*
# > **v09:** *"Think we need to go to diagonal/straight lines instead of right angles b/c I
# > can't see what's going on with the overlaps."*
#
# 🚨 HIS STATED CAUSE IS NOT THE CAUSE, AND THAT MATTERED — the cure is the same either way, but
# only because the measurement went looking. A176 asked the three questions before touching
# this constant (cfdb-main-R-1249's rule), over AP Top 25, 2025 regular, 48 teams × 16 weeks:
#
#     teams sharing a rank with another (a poll tie)     4 team-weeks of 400   1.0%
#     drawn segments EXACTLY coincident with another     0 of 335              0.0%
#
# **There are no overlapping lines. Not one.** So "I can't see what's going on with the
# overlaps" cannot mean two teams drawn on top of each other — and a round that had flipped
# this constant to fix THAT would have been right by accident.
#
# 📊 WHAT IT DOES MEAN IS CROSSINGS, AND `step-after` MANUFACTURES THEM:
#
#     step-after   590 segments   868 crossings   1.47 per segment
#     linear       335 segments   389 crossings   1.16 per segment
#
# ⚠️ **A step splits every rank change into TWO segments — a horizontal hold and a vertical
# turn — and each vertical crosses every horizontal run between the two ranks.** A team falling
# from 5th to 20th draws a line straight through fifteen other teams' weeks. **The diagonal
# crosses 55% less ink and halves the segment count.**
#
# ⚠️ AND A164's ARGUMENT DOES NOT DIE QUIETLY; IT IS ANSWERED RATHER THAN DELETED.
# It rejected `step` and `step-before` because they *"draw a team at a rank it did not hold"* —
# `step-before` for a whole week, `step` for half of one. 🚨 **A DIAGONAL DOES THE SAME THING
# BETWEEN TICKS**, and that is a real cost, not a technicality: at week 6.5 a falling team is
# drawn at a rank no poll ever gave it.
#
# ✅ **THE TRADE IS MARC'S AND HE HAS MADE IT TWICE OVER.** The untruth is confined to the space
# BETWEEN two ticks, where no poll exists to contradict it, and the ticks themselves are still
# exact. What he gets back is a chart he can follow. **A164 was right about what the old
# constant meant and this is not a reversal of its reasoning — it is the same reasoning applied
# to a cost A164 never measured.**
#
#     step         the vertical falls at the MIDPOINT between two weeks — on no tick at all
#     step-before  the vertical falls at the EARLIER week, so the new rank is drawn a week EARLY
#     step-after   the line HOLDS the rank across its own week and turns at the NEXT week's tick
#     linear       one diagonal per change — exact at every tick, interpolated between them
_BUMP_INTERPOLATE = "linear"
# A178: the endpoint labels on the picture scale with the height, same 1.25.
_BUMP_LABEL_FONT = 14
_BUMP_TABLE_WIDTH = 250
# A178: 11 * 1.25 = 13.75, taken to 14 — see _BUMP_HEIGHT.
_BUMP_ROW_FONT = 14


def _scoreboard_lines(frame: pd.DataFrame) -> pd.DataFrame:
    """Two scoreboard strings per poll row — away over home — for the bump chart's tooltip.

    > **MARC, v11:** *"a hover that shows a simple scoreboard look (away over home) with
    > logo, name, record, and scores for the corresponding week."*

    ⚠️ COMPOSING PUBLISHED VALUES INTO ONE STRING IS RENDERING, AND §4.2.1 NAMES THIS CASE:
    *"composing two published values into one string… rendering, because joining creates no
    quantity"*. Nothing here is computed — away/home were resolved in the model, the records
    are `record_after` as published, and the scores are the scores.

    🚨 THREE ABSENCES, AND THEY ARE NOT THE SAME ABSENCE (AC-G.11):

        no game row at all      poll week 1 has no game week 0, and a bye leaves no row
        a game with no score    the poll was published ahead of a week that is not played yet
        a score                 the scoreboard

    ⚠️ AND EVERY ONE IS TESTED WITH `pd.isna`, NOT FOR TRUTHINESS. `NaN` is truthy (A191), so
    `if points` is true for a game that has not been played — which would print the word
    `nan` as a score. **A score of 0 is also falsy**, so truthiness fails at both ends: a
    shutout would render as "not yet played".
    """
    def line(display, record, points):
        if display is None or pd.isna(display):
            return ""
        record_text = "" if record is None or pd.isna(record) else f" ({record})"
        score = "" if points is None or pd.isna(points) else f"  {int(points)}"
        return f"{display}{record_text}{score}"

    away, home = [], []
    for _index, row in frame.iterrows():
        game_week = row.get("explained_by_game_week")
        if game_week is None or pd.isna(game_week):
            away.append("No game")
            home.append("")
            continue
        if (row.get("game_away_points") is None or pd.isna(row.get("game_away_points"))):
            away.append(f"Week {int(game_week)} — not yet played")
            home.append("")
            continue
        away.append(line(row.get("game_away_display"), row.get("game_away_record_after"),
                         row.get("game_away_points")))
        home.append(line(row.get("game_home_display"), row.get("game_home_record_after"),
                         row.get("game_home_points")))
    out = frame.copy()
    out["scoreboard_away"] = away
    out["scoreboard_home"] = home
    return out


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
    # 🚨 A190: THE SCOREBOARD COLUMNS TRAVEL WITH THE RANK ONTO THE FULL GRID. The merge is
    # what puts an explicit null in a team's unranked weeks (see above); the two scoreboard
    # strings have to come through the same merge or a hovered point would show the wrong
    # week's game — and on a GAP row they must be blank, which `_scoreboard_lines` gives them
    # because the poll columns are null there too.
    carried = ["team_display", "week", "rank", "scoreboard_away", "scoreboard_home"]
    data = grid.merge(_scoreboard_lines(frame)[carried],
                      on=["team_display", "week"], how="left")
    data["week"] = data["week"].astype(int)
    # ⚠️ A GAP ROW HAS NO GAME BECAUSE IT HAS NO POLL ROW, and `NaN` in a Vega tooltip renders
    # as the string "null". Blank is the honest answer for a week a team was not ranked.
    for column in ("scoreboard_away", "scoreboard_home"):
        data[column] = data[column].fillna("")

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
        # ── A190 (cfdb-main-R-1945): THE EXPLAINING GAME, ON THE HOVER ────────────────
        # ⚠️ TWO LINES OF TEXT, AND THE LOGO IS NOT HERE — see `_rank_bump`'s note for the
        # measurement that settled it. Vega-Lite's tooltip renders its values as TEXT.
        tooltip=[alt.Tooltip("team_display:N", title="Team"),
                 alt.Tooltip("week:O", title="Week"),
                 alt.Tooltip("rank:Q", title="Rank", format="d"),
                 alt.Tooltip("scoreboard_away:N", title="Away"),
                 alt.Tooltip("scoreboard_home:N", title="Home")])
    labels = alt.Chart(last).mark_text(align="left", dx=8,
                                       fontSize=_BUMP_LABEL_FONT).encode(
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
    start_labels = alt.Chart(first).mark_text(align="right", dx=-8,
                                              fontSize=_BUMP_LABEL_FONT).encode(
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


# 🚨 A196 (cfdb-main-R-2033). THE GRACE WINDOW THAT KEEPS ONE CANCELLED GAME FROM HOLDING
# THE GATE SHUT ALL SEASON.
#
# Marc's gate is "last week is done". Read literally — every FBS game whose kickoff has passed
# is completed — a game that will NEVER complete jams it permanently.
#
# 📊 MEASURED ACROSS THE WHOLE CORPUS: exactly ONE such game exists. App State vs Liberty,
# 2024 regular week 5, kickoff 2024-09-28, no points, `is_completed` false — **724 days past**.
# That is the Hurricane Helene cancellation, and under a strict rule it would have held 2024
# week 6's Looking Forward closed for the rest of the season and every season after.
#
# ✅ SO A GAME ONLY HOLDS THE GATE WHILE IT COULD STILL PLAUSIBLY FINISH: kickoff in the last
# seven days. Seven because that is one game week — once the next week's slate has started, an
# unfinished game from the week before is not coming back. ⚠️ **The number is stated rather
# than tuned**: the one real instance is 724 days out, so nothing in the corpus sits near this
# boundary and no choice between 2 and 7 days would change a single answer today.
_STALE_GAME_DAYS = 7


def _upcoming_game_week(scope):
    """The earliest week of this season with FBS games still unplayed, or None.

    🚨 A196 (cfdb-main-R-2034). THIS SECTION DOES NOT FOLLOW THE PAGE'S WEEK FILTER, AND THAT
    IS A DECISION RATHER THAN AN OVERSIGHT.

    ⚠️ **A reader looking back at week 2 still wants the UPCOMING week's games.** Looking
    Forward is about the real upcoming week; the filter above it is about the recap below it.
    The section's own heading names the week and its caption says the filter does not apply,
    because a panel that silently ignores a control the reader just moved is worse than one
    that never offered it.

    ⚠️ RETURNS None AT THE END OF THE REGULAR SEASON — every week played — and the caller says
    so plainly rather than guessing at a bowl week. Postseason scheduling is its own shape and
    this round does not pretend to know it.
    """
    frame = query("""
        select min(week) as week
        from srv_game
        where season = :season and season_type = :season_type
          and is_fbs_game and not is_completed
        limit 1
    """, {"season": scope.season, "season_type": scope.season_type})
    if frame is None or frame.empty:
        return None
    week = frame.iloc[0]["week"]
    return None if week is None or pd.isna(week) else int(week)


def _week_is_final(scope, week: int) -> bool:
    """Is every FBS game in `week` that could still finish, finished?

    See `_STALE_GAME_DAYS` for why "could still finish" is not the same as "has kicked off".
    """
    frame = query("""
        select count(*) as blocking
        from srv_game
        where season = :season and season_type = :season_type and week = :week
          and is_fbs_game and not is_completed
          and start_date < now()
          and start_date > now() - make_interval(days => :grace)
        limit 1
    """, {"season": scope.season, "season_type": scope.season_type, "week": int(week),
          "grace": _STALE_GAME_DAYS})
    if frame is None or frame.empty:
        return False
    return int(frame.iloc[0]["blocking"] or 0) == 0


def _poll_is_out(scope, week: int) -> bool:
    """Is the AP poll for this game week published?

    📊 A190 ESTABLISHED THE ALIGNMENT AND IT IS WHY THIS READS WEEK W RATHER THAN W-1: poll
    week W is published BEFORE game week W and reflects game week W-1. So "the new poll" for
    upcoming game week W is poll week W.

    ✅ AND `srv_game` ALREADY CARRIES THOSE RANKS. Proven against `srv_rankings` week 4: of
    the 15 week-4 fixtures whose home side is ranked, **15 of 15 agree with the poll's rank
    exactly**, and none carries a rank the poll does not have. So the Top 25 rule reads
    `home_rank`/`away_rank` off the game and needs no join.
    """
    frame = query("""
        select count(*) as ranked
        from srv_rankings
        where season = :season and poll_name = 'AP Top 25' and week = :week
        limit 1
    """, {"season": scope.season, "week": int(week)})
    if frame is None or frame.empty:
        return False
    return int(frame.iloc[0]["ranked"] or 0) > 0


def _high_value_games(scope, week: int, also_ids=None) -> pd.DataFrame:
    """The upcoming week's high-value games — Schedule's own query, filtered.

    ⚠️ THE DEFINITION IS NOT HERE. `is_high_value`, `is_top25_matchup` and
    `is_undefeated_close` are published on `srv_game` (A196) because "which games matter" is a
    definition and not a rendering (§4.2.1). The page passes a flag and adds no rule.

    🚨 AND THE COLUMN LIST IS NOT HERE EITHER, WHICH IS THE POINT. A196's first attempt wrote
    its own SELECT beside Schedule's and guessed two column names wrong — `venue_name` (it is
    `venue_display`) and `weather` (a synthetic name Schedule's `weather_cell` composes from
    three real columns). The page raised `UndefinedColumn` into `states.section` and drew one
    error card: **a handled failure that looks considered.** Rendering Schedule's columns from
    a different query than Schedule's is the mistake; there is now only one query.

    ⚠️ `division='fbs'` AND NO CONFERENCE FILTER ON PURPOSE. This section does not follow the
    page's filters (see `_upcoming_game_week`), so it asks for the same slate Schedule would
    show with its defaults and narrows it by the flag alone.
    """
    return schedule_table.rows(scope.season, int(week), scope.season_type,
                               conference=None, division="fbs", high_value_only=True,
                               also_ids=also_ids)


def _lf_kickoff(row) -> str:
    """`Fri 5:00 PM` — the day, then the time, on one line and without the zone.

    ⚠️ THE DAY COMES FROM THE SAME CONVERSION THE TIME DOES. Reading the day off `game_date`
    and the time off `start_date` would disagree for a late kickoff, which is R-643's family:
    one instant, converted once, is the only way the two halves can agree.
    """
    ts = row.get("start_date")
    if ts is None or pd.isna(ts):
        return fmt.EM_DASH
    local = fmt._local(ts)
    return f"{local:%a} {local.strftime('%-I:%M %p')}"


def _high_value_reason(row) -> str:
    """The tag that says WHY a game is on this list. It reads the flags and decides nothing.

    ⚠️ BOTH RULES CAN FIRE ON ONE GAME and the tag says so — USC vs Oregon in 2026 week 4 is a
    Top 25 matchup AND an undefeated side at a 3-point line. Showing only the first would make
    the second rule look narrower than it is.
    """
    # 🚨 A200: THE TAGS ARE SHORT BECAUSE THE COLUMN HAS TO FIT ON SCREEN, AND THE CAPTION
    # CARRIES THE FULL RULE. 📊 Measured by the clone method at 1440 with the sidebar open:
    # "Undefeated · close line" is 105.1px against "Undefeated · close" at 87.8px, and the
    # cell adds 8.8px of padding a side. The wording below is the widest ONE tag, because
    # the tags STACK when both rules fire.
    tags = []
    if bool(row.get("is_top25_matchup")):
        tags.append("Top 25")
    if bool(row.get("is_undefeated_close")):
        tags.append("Undefeated \u00b7 close")
    # ⚠️ A199: A GAME CAN BE BOTH HIGH-VALUE AND ADDED, AND THE TAGS SAY SO. Marc may paste a
    # game the rules already picked; showing only "Added by you" would hide why it qualifies
    # on its own, and showing only the rule would hide that he asked for it.
    if bool(row.get("is_added_by_you")):
        tags.append("Added by you")   # already the shortest of the three; left as Marc's words
    if not tags:
        return ""
    return ("<span class='cfdb-why'>"
            + "".join(f"<span class='cfdb-why-tag'>{html.escape(t)}</span>" for t in tags)
            + "</span>")


# ── A199 (cfdb-main-R-2065): THE GAMES A READER ADDS THEMSELVES ─────────────────────────
#
# > **MARC, v12:** *"making Looking Forward configurable, by providing a text input box on the
# > bottom of the nav bar that would allow end-user to paste games they want included"* — and
# > on how he would get the ids: *"I can go through the Schedule for the week and click to see
# > the matchups I'm interested in. I can use the matchup url querystring to extract the
# > game_id."*
#
# ⚠️ THE CAPS ARE STATED RATHER THAN GENEROUS. 2,000 characters is about forty Matchup URLs,
# and forty ids is five times the size of a normal high-value week — past that a reader is
# pasting something other than a shortlist, and the box says so instead of silently truncating.
_LF_MAX_CHARS = 2000
_LF_MAX_IDS = 40

# A bare id, or the `game_id=` of a Matchup link. ⚠️ THE PARAMETER NAME IS READ FROM MATCHUP
# RATHER THAN ASSUMED: `matchup.py:276` is `params.get("game_id")`, checked at this commit.
_LF_URL_ID = re.compile(r"game_id=(\d+)")
_LF_BARE_ID = re.compile(r"^\d+$")


def _parse_game_ids(text: str):
    """`(ids, unreadable_line_numbers, truncated)` from whatever the reader pasted.

    Accepts bare ids and Matchup URLs, separated by newlines, commas or spaces, in any mix.

    🚨 ONLY INTEGERS COME OUT. This is the one place on the site where reader text reaches a
    query, and it reaches it as a **bound integer array** — nothing here is ever formatted
    into SQL. A string like `1; drop table games` yields no id and one unreadable line, which
    is the same outcome as any other prose.

    ⚠️ LINE NUMBERS, NOT TOKEN NUMBERS, because a line is what the reader can see and point
    at. A line contributing no id at all is reported once, whatever it contains.
    """
    if not text:
        return [], [], False
    truncated = len(text) > _LF_MAX_CHARS
    ids, unreadable, seen = [], [], set()
    for number, line in enumerate(text[:_LF_MAX_CHARS].splitlines(), start=1):
        if not line.strip():
            continue
        found = False
        for token in line.replace(",", " ").split():
            match = _LF_URL_ID.search(token)
            if match is None and _LF_BARE_ID.match(token):
                match = _LF_BARE_ID.match(token)
                value = int(token)
            elif match is not None:
                value = int(match.group(1))
            else:
                continue
            found = True
            # ⚠️ DE-DUPLICATED, ORDER PRESERVED. The same game pasted twice is one game, and
            # a reader who pastes a URL and its id should not see the row twice.
            if value not in seen:
                seen.add(value)
                ids.append(value)
        if not found:
            unreadable.append(number)
    if len(ids) > _LF_MAX_IDS:
        ids, truncated = ids[:_LF_MAX_IDS], True
    return ids, unreadable, truncated


def _looking_forward_box(scope, week):
    """The sidebar box, and the `lf=` round trip. Returns the ids the reader asked for.

    ⚠️ IT IS DRAWN ON TODAY ONLY BECAUSE IT IS WRITTEN DURING TODAY'S RUN. `st.navigation`
    owns the sidebar, and a page adding to it during its own render lands below the nav —
    which is where Marc asked for it — without any other page being touched.

    🚨 THE LIST LIVES IN THE URL, WHICH IS THIS SITE'S OWN ANSWER TO "WHERE DOES VIEWER STATE
    GO" (AC-G.18). A refresh keeps it, a bookmark restores it, a shared link carries it, and
    **nothing is stored server-side, so no viewer can change what another sees.**
    """
    existing = params.get("lf") or ""
    key = "today_lf"
    # ⚠️ THE URL SEEDS THE BOX ONCE, THEN THE BOX OWNS IT. Re-seeding on every run would
    # fight the reader's typing; `st.session_state` is the widget's own memory and the URL is
    # the durable copy.
    if key not in st.session_state:
        st.session_state[key] = existing.replace(",", "\n")

    with st.sidebar:
        st.markdown("---")
        typed = st.text_area(
            "Add games to Looking Forward",
            key=key, height=90,
            help="Paste game_ids or Matchup page links, one per line or separated by commas.")

    ids, unreadable, truncated = _parse_game_ids(typed)

    # The URL follows the box. `set_params` writes only what changed, so a render that adds
    # nothing adds no history entry either (AC-G.13's note on the back button).
    params.set_params(lf=",".join(str(i) for i in ids) if ids else None)
    return ids, unreadable, truncated


def _looking_forward_feedback(week, asked, found_ids, unreadable, truncated) -> str:
    """What happened to what the reader pasted. Never silent (AC-G.11).

    ⚠️ A GAME OUTSIDE THE UPCOMING WEEK IS REPORTED BY ID, NOT DROPPED. That is also what
    happens to last week's `lf=` after the week rolls over: the link keeps working, and the
    box says the game is not a week-N game rather than quietly showing a shorter list.
    """
    missing = [i for i in asked if i not in found_ids]
    bits = []
    if asked:
        bits.append(f"Added {len(asked) - len(missing)}")
    if missing:
        shown = ", ".join(str(i) for i in missing[:3])
        more = f" and {len(missing) - 3} more" if len(missing) > 3 else ""
        bits.append(f"{len(missing)} not a week-{week} game ({shown}{more})")
    if unreadable:
        lines = ", ".join(str(n) for n in unreadable[:3])
        more = f" and {len(unreadable) - 3} more" if len(unreadable) > 3 else ""
        bits.append(f"{len(unreadable)} line{'s' if len(unreadable) > 1 else ''} "
                    f"unreadable (line {lines}{more})")
    if truncated:
        bits.append(f"input capped at {_LF_MAX_CHARS} characters / {_LF_MAX_IDS} games")
    return " \u00b7 ".join(bits)


# 🚨 A198 (cfdb-main-R-2050). CFBD PUBLISHES NO END TIME, SO THE BAR LENGTH IS A STATED
# ASSUMPTION AND THE CAPTION SAYS SO.
#
# ⚠️ **A bar that looks measured and is not would be worse than no bar.** Three and a half
# hours is the length every bar gets; nothing in the data supports a per-game estimate, and
# inventing one from the total line or the pace would dress a guess as a measurement.
_SLATE_GAME_MINUTES = 210

# The drawing's geometry. The label gutter is measured rather than chosen — see `_slate`.
_SLATE_ROW_PX = 26
_SLATE_BAR_PX = 13
_SLATE_LABEL_PX = 268
_SLATE_NETWORK_PX = 46
# 🚨 A201: THE REASON IS A COLUMN NOW, WITH A HEADER AND THREE FIXED SLOTS.
#
# > **MARC, v13:** *"sometimes the leftmost element is a Circle, triangle, or a +. Make the
# > same type vertically aligned… if a game isn't Top 25, replace the circle with a space."*
#
# ⚠️ A200 drew the marks left-packed, so the FIRST mark on a row was whichever rule happened
# to fire — a circle on one row, a triangle on the next, in the same x. ✅ A slot per reason,
# always the same x whether or not it is filled, is the first option Marc named and the
# cheapest of the three: the cell is a fixed-width SVG and the slot centres are constants, so
# the alignment is arithmetic rather than a layout that could drift.
_SLATE_WHY_PX = 54
_SLATE_SLOT_PX = 16
_SLATE_WIDTH = 900

# The graph cell's own coordinate space. It is stretched to whatever width the column gets,
# so this is a unit system rather than a pixel count.
_SLATE_PLOT = 300
_SLATE_PAD_TOP = 18


def _slate_rows(games: pd.DataFrame):
    """The SLATE's rows, grouped by local day, plus the ones with no known kickoff.

    > **MARC, v12:** *"Create a SLATE schedule for what games are on when (with network
    > info)"* — his own format for a daily run sheet: one row per event, time across the
    > x-axis, where to watch on each row, times Pacific.

    🚨 THE INSTANT IS CONVERTED ONCE, THROUGH `fmt`, AND NEVER RE-CONVERTED. `srv_game`
    publishes `start_date` as an instant carrying its own offset, and R-643 records what
    happened the last time something converted it a second time: **every kickoff on the site
    was four hours early for a season**, because a column had already been shifted to Eastern
    and the formatter shifted it again. `fmt._local` is the one conversion, and it RAISES on a
    naive value rather than guessing — so a double conversion cannot pass quietly here.

    ⚠️ A GAME WITH NO KNOWN KICKOFF GETS NO BAR. Drawing one at a placeholder time would put a
    fabricated slot on a run sheet, which is the one thing a run sheet must not have.
    📊 The state is real but has no 2026 instance: `kickoff_time_known` is false on 702 rows in
    2000 and on **0 of 71 week-4 games** — 0 across all of 2026, in fact — so this branch is
    exercised by a fixture rather than by the live page, and the report says so.
    """
    timed, untimed = {}, {}
    for _index, row in games.iterrows():
        start = row.get("start_date")
        known = row.get("kickoff_time_known")
        # ⚠️ `pd.isna`, NOT TRUTHINESS — `NaN` is truthy (A191) and `False` is falsy, so a
        # truthiness test would call an unknown kickoff known and a known one unknown.
        missing = start is None or pd.isna(start)
        if missing or (known is not None and not pd.isna(known) and not bool(known)):
            day = fmt.day(row.get("game_date"))
            untimed.setdefault(day, []).append(row)
            continue
        local = fmt._local(start)
        timed.setdefault(local.strftime("%A, %b %-d"), []).append((local, row))
    for day in timed:
        timed[day].sort(key=lambda pair: pair[0])
    return timed, untimed


# 🚨 A200 (cfdb-main-R-2083): THE SLATE'S REASON WAS COLOUR ONLY, AND ONLY TWO COLOURS.
#
# ⚠️ An added game drew the SAME grey as "Undefeated · close", and a game qualifying on BOTH
# rules drew one blue bar that said only "Top 25". So the chart could not be read back to the
# list beside it, which is the one thing a second view of the same frame has to do.
#
# ✅ A MARK PER REASON, AND THE MARKS COMBINE. Shapes rather than hues, because A198 checked
# this chart prints and **a legend keyed on colour alone is a blank legend on a laser
# printer**. The colour stays as the fast signal; the shape is what survives greyscale.
_SLATE_MARKS = (
    ("is_top25_matchup", "circle", "Top 25"),
    ("is_undefeated_close", "triangle", "Undefeated \u00b7 close"),
    ("is_added_by_you", "plus", "Added by you"),
)
_SLATE_MARK_PX = 16


def _slate_matchup(row) -> str:
    """`#1 Texas at #14 Tennessee` — the AP rank rides the name it belongs to.

    🚨 `NaN` IS TRUTHY, and 6 of the 20 rank cells in the real week-4 slate are NaN. `if rank`
    would print `#nan` on every unranked side, which is the defect class this project has paid
    for more often than any other.
    """
    def side(which) -> str:
        name = fmt.text(row.get(f"{which}_team_display"))
        rank = row.get(f"{which}_rank")
        if rank is None or pd.isna(rank):
            return name
        return f"#{int(rank)} {name}"
    return f"{side('away')} at {side('home')}"


def _slate_bar_class(row) -> str:
    """The bar's colour. ⚠️ ONE CLASS, BY PRECEDENCE — a bar has one fill, and the MARKS carry
    the whole truth when more than one rule fires."""
    if bool(row.get("is_top25_matchup")):
        return "cfdb-slate-bar-top"
    if bool(row.get("is_undefeated_close")):
        return "cfdb-slate-bar-und"
    if bool(row.get("is_added_by_you")):
        return "cfdb-slate-bar-added"
    return ""


def _slate_mark_shape(kind: str, cx: float, cy: float) -> str:
    """One mark, drawn at a centre. Shapes, so greyscale keeps them apart."""
    if kind == "circle":
        return f"<circle class='cfdb-slate-mark' cx='{cx:.1f}' cy='{cy:.1f}' r='4.2'/>"
    if kind == "triangle":
        return (f"<polygon class='cfdb-slate-mark' points='"
                f"{cx:.1f},{cy - 4.6:.1f} {cx + 4.6:.1f},{cy + 3.6:.1f} "
                f"{cx - 4.6:.1f},{cy + 3.6:.1f}'/>")
    return (f"<path class='cfdb-slate-mark cfdb-slate-mark-line' d='"
            f"M{cx - 4.4:.1f},{cy:.1f} H{cx + 4.4:.1f} "
            f"M{cx:.1f},{cy - 4.4:.1f} V{cy + 4.4:.1f}'/>")


def _slate_marks(row, esc) -> str:
    """The reason cell: three fixed slots, filled only where the rule fires.

    🚨 EVERY MARK OF A GIVEN TYPE SITS AT THE SAME x ON EVERY ROW, and it does so by
    arithmetic — slot *i* is always at `_SLATE_SLOT_PX * (i + 0.5)` in a fixed-width viewBox.
    ⚠️ A200 packed them left, so the leftmost glyph was a circle on one row and a triangle on
    the next and a reader could not scan the column.
    """
    parts = [f"<svg class='cfdb-slate-slots' viewBox='0 0 "
             f"{_SLATE_SLOT_PX * len(_SLATE_MARKS)} {_SLATE_SLOT_PX}' "
             f"width='{_SLATE_SLOT_PX * len(_SLATE_MARKS)}' height='{_SLATE_SLOT_PX}' "
             f"role='img' aria-label='{esc(_slate_reason_text(row) or 'no reason')}'>"]
    for index, (flag, kind, label) in enumerate(_SLATE_MARKS):
        if not bool(row.get(flag)):
            continue
        cx = _SLATE_SLOT_PX * (index + 0.5)
        parts.append(f"<g><title>{esc(label)}</title>"
                     f"{_slate_mark_shape(kind, cx, _SLATE_SLOT_PX / 2)}</g>")
    parts.append("</svg>")
    return "".join(parts)


def _slate_reason_text(row) -> str:
    """The reasons as words, for the hover and for the accessible label."""
    return " \u00b7 ".join(label for flag, _kind, label in _SLATE_MARKS
                           if bool(row.get(flag)))


def _slate_spread(row) -> str:
    """The market line, formatted the way the table above it formats the same column.

    🚨 `fmt.signed` WITH THE FIELD NAME, NOT A LOCAL `:+g`. The first build used `:+g` and the
    SLATE printed `+1` and `-3` beside a list printing `+1.0` and `-3.0` — the same number,
    two ways, eight rows apart. `fmt.signed` is what `Col(kind="signed")` calls, and passing
    the FIELD is what makes it pick that column's own decimal places.

    ⚠️ `pd.isna`, not truthiness: a pick-'em line is 0.0, which is falsy and is a real number.
    """
    return fmt.signed(row.get("spread_current"), "spread_current")


def _slate_link(row, esc, scope) -> str:
    """Marc's "Matchup hyperlink" — the same glyph the Schedule row uses, so one icon means
    one thing across the page.

    ⚠️ THE HREF COMES FROM `scope.link`, NOT FROM `params.link_here`. `link_here` rewrites the
    CURRENT page's url and has no page argument; Schedule's own Game cell uses `scope.link`,
    and using anything else here would be a second way to build the same link.
    """
    game_id = row.get("game_id")
    if game_id is None or pd.isna(game_id):
        return ""
    href = scope.link("matchup", game_id=int(game_id))
    return (f"<a class='cfdb-cell-link-alt' href='{esc(href)}' target='_self' "
            f"title='Open the matchup'><span class='cfdb-details'>"
            f"{table.DETAILS_GLYPH}</span></a>")


def _slate_tip(row, network: str) -> str:
    """One hover string for the bar, unchanged in content from A198/A200."""
    reason = _slate_reason_text(row)
    return (f"{_slate_matchup(row)} \u2014 {fmt.clock(row.get('start_date'))} on {network}"
            f" \u2014 {_slate_spread(row)}" + (f" \u2014 {reason}" if reason else ""))


def _slate_legend(esc) -> str:
    """🚨 ON THE CHART, NOT ONLY IN THE CAPTION. A198 put the reason in the caption and the
    marks were unreadable without it; a key that lives a paragraph away is a key nobody uses."""
    bits = []
    for _flag, kind, label in _SLATE_MARKS:
        bits.append(f"<svg class='cfdb-slate-key-mark' viewBox='0 0 12 12' "
                    f"width='12' height='12' aria-hidden='true'>"
                    f"{_slate_mark_shape(kind, 6, 6)}</svg>"
                    f"<span class='cfdb-slate-key-text'>{esc(label)}</span>")
    return "<div class='cfdb-slate-key'>" + "".join(bits) + "</div>"


def _slate(games: pd.DataFrame, esc, scope) -> str:
    """The SLATE: Schedule's own cells on the left, the day's time axis on the right.

    > **MARC, v13:** *"Re-use the layout from the inline schedule for the left side of the
    > SLATE table/graph (Away Logo, Rank Name, Record in column), same info for Home in a
    > column. Columns for Spread, O/U, WX, TV, Matchup hyperlink. Then the graph element. Give
    > the bars a thin medium graph outline to make them pop a bit. Remove the label b/c its on
    > the left."*

    🚨 TWO OF HIS SEVEN COLUMNS ARE NOT HERE, AND THE MEASUREMENT IS WHY (cfdb-main-R-2092).
    📊 At 1440 with the sidebar open the scroll box is 980px and his seven columns need
    **745.2px** of it, which leaves **176.8px** for the graph — an axis that cannot carry a
    day. Dropping **Wx** leaves 244.7px; dropping **O/U** as well leaves **302.8px**, which
    can. ⚠️ Cowork's own order was WX first then O/U, and the round took exactly that and no
    more. **Both numbers are still one click away on Matchup**, which the Game cell links.

    ⚠️ THE NETWORK IS IN THE TV COLUMN AND NOT BESIDE THE BAR. It was beside the bar when the
    bar carried the only identity on the row; now the row names itself, and printing the
    network twice would be the "not both" this was asked to avoid.

    ⚠️ ONE SVG PER ROW, SHARING THE DAY'S SCALE, rather than one SVG per day. The left of the
    row is HTML — those are Schedule's cells, reused rather than redrawn — so the graph has to
    live in a cell beside them. The gridlines are drawn in every row's own SVG at the same
    fractions, so they line up into continuous columns; the hour labels are drawn once, in the
    header cell.
    """
    if games is None or games.empty:
        return ""
    timed, untimed = _slate_rows(games)
    if not timed and not untimed:
        return ""

    out = ["<div class='cfdb-slate'>", _slate_legend(esc)]

    for day, entries in timed.items():
        first = min(local for local, _row in entries)
        last = max(local for local, _row in entries)
        start_hour = first.hour
        end_hour = last.hour + math.ceil((last.minute + _SLATE_GAME_MINUTES) / 60)
        span = max(end_hour - start_hour, 1)

        def frac(when) -> float:
            """Where an instant sits across the day's scale, 0..1."""
            minutes = (when.hour - start_hour) * 60 + when.minute
            return min(max(minutes / (span * 60), 0.0), 1.0)

        # ⚠️ EVERY HOUR WHEN THEY FIT, EVERY SECOND HOUR WHEN THEY DO NOT. 📊 The graph column
        # is ~302px at 1440 and a Saturday spans 13 hours, so an hourly label would get ~23px
        # for a ~14px glyph run — legible but touching. The step is computed from the span
        # rather than chosen, so a short Friday still gets every hour.
        step = 1 if span <= 8 else 2

        # 🚨 THE AXIS IS HTML, NOT SVG TEXT. The plot is stretched to its column with
        # `preserveAspectRatio='none'` so the bars keep the day's scale — and that same
        # stretch distorts GLYPHS. The first build drew the hours inside the plot's SVG and
        # they came out several times their size and horizontally smeared. Percent-positioned
        # spans take the same fractions and render as ordinary text.
        head = ["<div class='cfdb-slate-axis'>"]
        for hour in range(start_hour, end_hour + 1):
            if (hour - start_hour) % step:
                continue
            pct = 100.0 * (hour - start_hour) / span
            label = f"{(hour - 1) % 12 + 1}{'a' if hour < 12 else 'p'}"
            # ⚠️ THE FIRST AND LAST LABELS ARE ANCHORED BY THEIR EDGE, NOT THEIR CENTRE. A
            # centred span at 100% hangs half its width past the column and the render showed
            # "9p" clipped to "9"; at 0% it would hang off the left into the Why column.
            if pct >= 99.9:
                css, cls = "right:0", "cfdb-slate-hour cfdb-slate-hour-last"
            elif pct <= 0.1:
                css, cls = "left:0", "cfdb-slate-hour cfdb-slate-hour-first"
            else:
                css, cls = f"left:{pct:.2f}%", "cfdb-slate-hour"
            head.append(f"<span class='{cls}' style='{css}'>{label}</span>")
        head.append("</div>")

        rows_html = []
        for local, row in entries:
            x1 = _SLATE_PLOT * frac(local)
            x2 = _SLATE_PLOT * frac(local + pd.Timedelta(minutes=_SLATE_GAME_MINUTES))
            network = (fmt.text(row.get("network_abbreviation"))
                       or fmt.text(row.get("network")) or "TBA")
            tip = _slate_tip(row, network)
            bar = [f"<svg class='cfdb-slate-plot' viewBox='0 0 {_SLATE_PLOT} "
                   f"{_SLATE_ROW_PX}' preserveAspectRatio='none' role='img' "
                   f"aria-label='{esc(tip)}'>"]
            for hour in range(start_hour, end_hour + 1):
                gx = _SLATE_PLOT * (hour - start_hour) / span
                bar.append(f"<line class='cfdb-slate-grid' x1='{gx:.1f}' y1='0' "
                           f"x2='{gx:.1f}' y2='{_SLATE_ROW_PX}'/>")
            # ⚠️ `vector-effect` KEEPS THE OUTLINE ONE PIXEL. The SVG is stretched to the
            # column with `preserveAspectRatio='none'`, so a plain stroke-width would be
            # scaled horizontally and draw a fat left edge against a hairline top.
            bar.append(
                f"<rect class='cfdb-slate-bar {_slate_bar_class(row)}' "
                f"x='{x1:.1f}' y='{(_SLATE_ROW_PX - _SLATE_BAR_PX) / 2:.1f}' "
                f"width='{max(x2 - x1, 2):.1f}' height='{_SLATE_BAR_PX}' rx='2' "
                f"vector-effect='non-scaling-stroke'>"
                f"<title>{esc(tip)}</title></rect>")
            bar.append("</svg>")

            rows_html.append(
                "<tr>"
                f"<td class='cfdb-slate-team'>{schedule_table.team_with_record(row, 'away')}</td>"
                f"<td class='cfdb-slate-team'>{schedule_table.team_with_record(row, 'home')}</td>"
                f"<td class='cfdb-num'>{_slate_spread(row)}</td>"
                f"<td class='cfdb-slate-tv'>{esc(network)}</td>"
                f"<td class='cfdb-center'>{_slate_link(row, esc, scope)}</td>"
                f"<td class='cfdb-slate-why'>{_slate_marks(row, esc)}</td>"
                f"<td class='cfdb-slate-cell'>{''.join(bar)}</td>"
                "</tr>")

        out.append(f"<div class='cfdb-slate-day'>{esc(day)}</div>")
        # ⚠️ `table-layout:fixed` PLUS A COLGROUP, so the graph takes what is LEFT. With
        # `auto` and a 100%-wide graph cell the browser gave the graph the whole table and
        # pushed Schedule's columns off the left edge — measured, and visible in the first
        # render of this build.
        # 📊 The six widths are A201's own measurement of those same cells at 1440.
        out.append(
            "<div class='cfdb-scroll'><table class='cfdb-table cfdb-slate-table'>"
            "<colgroup>"
            "<col style='width:190px'><col style='width:222px'><col style='width:68px'>"
            "<col style='width:56px'><col style='width:52px'>"
            f"<col style='width:{_SLATE_WHY_PX}px'><col>"
            "</colgroup>"
            "<thead><tr>"
            "<th>Away</th><th>Home</th><th class='cfdb-num'>Spread</th><th>TV</th>"
            "<th class='cfdb-center'>Game</th><th class='cfdb-center'>Why</th>"
            f"<th class='cfdb-slate-cell'>{''.join(head)}</th>"
            "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>")

    for day, rows in untimed.items():
        # AC-G.11: a named state, not an empty axis and not a bar at a made-up time.
        names = ", ".join(f"{fmt.text(r.get('away_team_display'))} at "
                          f"{fmt.text(r.get('home_team_display'))}" for r in rows)
        out.append(f"<div class='cfdb-slate-tba'><b>{esc(day)} \u00b7 time TBA</b> "
                   f"{esc(names)}</div>")

    out.append("</div>")
    return "".join(out)


def _looking_forward(scope, depth: int) -> None:
    """The upcoming week's games worth watching, once the week before it is settled.

    > **MARC, v12:** *"the layout should be the same as Schedule, this section should be
    > pre-filtered to games we've identified as high-value. Look for Top 25 matchups.
    > Matchups with an undefeated FBS team and a ABS(spread) < 4"*

    > **MARC, on timing:** *"It has to be live after Saturday games are complete and the next
    > week of rankings is available. Can put up a splash note that it will be populated after
    > Rankings come out."*

    🚨 THE GATE IS DATA, NOT A CLOCK. Two conditions — the previous game week is settled, and
    the AP poll for the upcoming week is published — and the splash names whichever is still
    pending. ⚠️ **No empty table and no stale list from last week**, which are the two ways a
    section like this lies while looking fine.
    """
    with states.section("srv_game", dataset=DATASETS["srv_game"]):
        week = _upcoming_game_week(scope)
        if week is None:
            # AC-G.11: say WHICH absence. The regular season being over is a real state, and
            # it is not the same as the gate being shut.
            st.subheader("Looking forward")
            st.caption(
                f"Every {scope.season} regular-season week has been played. Bowl and playoff "
                f"fixtures are a different shape and this section does not guess at them.")
            st.markdown(f"For the full slate, see [Schedule]({scope.link('schedule')}).")
            return

        st.subheader(f"Looking forward \u00b7 week {week}")

        # ⚠️ THE BOX IS DRAWN WHATEVER THE GATE SAYS, because a reader can line games up
        # before the week opens — and it would be strange for the control to vanish exactly
        # when he is planning. What the gate decides is whether anything is RENDERED from it.
        added_ids, unreadable, truncated = _looking_forward_box(scope, week)

        pending = []
        if not _week_is_final(scope, week - 1):
            pending.append(f"week {week - 1} is not final yet")
        if not _poll_is_out(scope, week):
            pending.append(f"the AP Top 25 for week {week} is not out yet")

        if pending:
            # 🚨 THE SPLASH MARC ASKED FOR, AND IT NAMES WHAT IS MISSING. "Coming soon" would
            # leave a reader unable to tell a pipeline failure from a Tuesday.
            st.info(
                f"Week {week}'s games to watch will appear here once week {week - 1} is "
                f"final and the new AP Top 25 is out. Still pending: "
                f"{' and '.join(pending)}.")
            if added_ids or unreadable:
                st.caption(f"Your {len(added_ids)} added game(s) will show here once week "
                           f"{week} opens.")
            st.markdown(f"In the meantime, see the full slate on "
                        f"[Schedule]({scope.link('schedule')}).")
            return

        games = _high_value_games(scope, week, also_ids=added_ids)
        # 🚨 A199: THE FLAG IS COMPUTED HERE AND NOT IN dbt, AND THAT IS THE ONE PLACE THE
        # §4.2.1 LINE FALLS THE OTHER WAY. "Which games are high-value" is a definition the
        # whole site could share; "which games did THIS reader paste into THIS URL" cannot be
        # a published column — it has exactly one consumer, this render, for this viewer.
        if not games.empty:
            asked = set(added_ids)
            games = games.assign(
                is_added_by_you=games["game_id"].map(lambda g: int(g) in asked))
        # ⚠️ A200: THE CAPTION NOW CARRIES BOTH THINGS THE CELLS STOPPED SAYING — the full
        # wording of the "Undefeated · close" rule, and that every kickoff is Pacific.
        st.caption(
            "Top 25 matchups, and games where an undefeated FBS team meets a line inside "
            "four points. Kick-off times are Pacific. This section always shows the next "
            "week to be played \u2014 it does not follow the week filter above.")

        # ⚠️ THE SAME TABLE AS SCHEDULE, CALLED RATHER THAN COPIED. `lib/schedule_table` was
        # promoted out of `views/schedule.py` for exactly this (A196); a view may not import
        # another view, and a copy is two tables that agree until one of them changes.
        # 🚨 THE REASON COLUMN GETS A FIXED SHARE, AND TWO EARLIER ATTEMPTS DID NOT WORK.
        #
        # `table.column_layout` weighs a column by the STRIPPED TEXT LENGTH of its widest
        # cell. A game carrying both tags strips to about 37 characters, so the reason column
        # asked for **201.8px against a 32.5px need** — and squeezed Spread to 52.4px against
        # 70.5px, wrapping `+5.5` onto two lines. 📊 Measured at 1440: **88 wrapped body cells
        # against Schedule's 10**, the same table at the same width.
        #
        # ⚠️ APPENDING A px WIDTH TO SCHEDULE'S PERCENTAGES DID NOT FIX IT EITHER. Those
        # percentages already sum to 100, so a fixed column on the end is 124px ON TOP of a
        # full-width table and every other column shrinks to make room. The wrap count did not
        # move.
        #
        # ⚠️ SCALING SCHEDULE'S PERCENTAGES DOWN TO MAKE ROOM WAS THE THIRD ATTEMPT AND ALSO
        # WRONG. It fixed the spread — `+5.5` stopped breaking — but it makes every Schedule
        # column 12% narrower than Schedule's own, and `56.5` in O/U then splits instead.
        # **An eleventh column in a table sized for ten has to come from somewhere**, and
        # taking it from all ten is not "the same layout as Schedule".
        #
        # ✅ SO THE TABLE SCROLLS, WHICH IS THIS PAGE'S OWN PRECEDENT. A189 did exactly this
        # for Most Exciting on Marc's instruction — *"the last 6 columns get a fixed width and
        # the table will have a horizontal scroll instead of forcing them to be super
        # narrow"*. Schedule's columns keep Schedule's widths, unscaled, and the reason column
        # is added beyond them at a measured width: the widest single tag draws 105.1px and
        # the cell adds 8.8px of padding a side. The tags STACK when both rules fire, so the
        # width is the widest ONE tag rather than the pair.
        _WHY_COLUMN_PX = 106

        def render(rows):
            columns = schedule_table.columns(scope)

            # 🚨 A200: THE TWO SCORE COLUMNS COME OUT WHILE NOTHING IN THE FRAME HAS BEEN
            # PLAYED, AND THAT IS WHAT MAKES THE REASON READABLE WITHOUT SCROLLING.
            #
            # 📊 MEASURED at 1440 with the sidebar open, before this change: the scroll box is
            # 980px and the table is 1022.9px, so the Why column sat 42.9px PAST the right
            # edge. ⚠️ Cowork read that as the tags being clipped; the clone method says they
            # are not — 0 of 12 clipped at either width. **The column was off-screen, not cut**,
            # and the two defects have different fixes.
            #
            # ⚠️ AND SHORTENING THE TAGS CANNOT CLOSE IT: it buys 18.3px of a 47.6px gap (the
            # gap includes the 4.7px the kickoff cell needs below). A196 already measured that
            # scaling Schedule's percentages down to make room breaks the O/U cell, so the
            # width has to come from a column rather than from all of them.
            #
            # ✅ These two are 96.4px between them and, on a list of games that have not
            # kicked off, every cell in both reads "—". A column that can only render one
            # value for every row is not information, and dropping them leaves 67px of spare
            # width rather than a table that has to be dragged sideways.
            #
            # 🚨 THEY COME BACK THE MOMENT A GAME IN THE WEEK IS COMPLETE. The upcoming week
            # can hold a Tuesday game that is already final, and hiding a real score to save
            # width would be the trade this comment exists to refuse.
            # 🚨 A200 / R-1977: THE KICKOFF CELL CARRIES ITS DAY, AND ONLY ON THIS PAGE.
            #
            # `fmt.clock` says in its own docstring that it is "for a table already grouped by
            # day" — which Schedule is, and Looking Forward is not. So the Friday game sat at
            # the top of the list with nothing saying it was a Friday.
            #
            # 📊 AND THE ZONE SUFFIX IS WHAT MADE IT WRAP: measured by the clone method, the
            # cell's content box is 80px and "12:30 PM PDT" needs 90px, so 4 of 10 rows drew
            # on two lines. "Sat 12:30 PM" is 84.7px and the widest of the week,
            # "Sat 10:30 AM", is 84.3px — both inside a 103px column.
            #
            # ⚠️ THE ZONE IS NOT DROPPED, IT MOVES TO THE CAPTION. Every kickoff on this page
            # is Pacific, so saying so eleven times costs a wrap to repeat what one sentence
            # settles. ✅ AND `schedule_table.columns()` IS NOT TOUCHED: Schedule keeps its own
            # day headings and its own "12:30 PM PDT", byte for byte.
            columns = [
                Col("start_date", "Kickoff", render=lambda r: (
                    f"{_lf_kickoff(r)}{schedule_table.neutral_glyph(r)}"))
                if c.field == "start_date" else c
                for c in columns]

            played = bool(rows["is_completed"].any()) if "is_completed" in rows else False
            if not played:
                columns = [c for c in columns
                           if c.field not in ("away_points", "home_points")]

            layout = table.column_layout(rows, columns) + [f"{_WHY_COLUMN_PX}px"]
            columns.append(Col("why", "Why", render=_high_value_reason))
            # ⚠️ `anchor` IS NOT OPTIONAL HERE — A141 anchored every table on this page and
            # `test_every_table_render_that_takes_an_anchor_is_the_one_that_draws` holds it.
            # It goes on the `table.render` that DRAWS, not on the `states.render_or_state`
            # around it: A141 shipped five broken panels by putting it on the wrapper, where
            # `states.section` caught the TypeError and drew a considered-looking failure card.
            return table.render(
                rows, columns, caption="",
                layout=layout,
                anchor="looking-forward", scroll=True,
                link_builder=lambda r: scope.link("matchup", game_id=r["game_id"]))

        states.render_or_state(
            games, "srv_game",
            "The week's games to watch would be here.",
            f"No games in week {week} meet the high-value rules yet.",
            renderer=render)

        # A199: never silent (AC-G.11) — say what happened to what was pasted.
        note = _looking_forward_feedback(
            week, added_ids,
            set(int(g) for g in games["game_id"]) if not games.empty else set(),
            unreadable, truncated)
        if note:
            st.caption(note)

        # ── A198 (cfdb-main-R-2051): THE SLATE, BELOW THE LIST ────────────────────────────
        #
        # > **MARC, v12:** *"Create a SLATE schedule for what games are on when (with network
        # > info)"*, and on placement: *"The SLATE chart should be below the Schedule
        # > layout."*
        #
        # ⚠️ ONE GATE, NOT TWO. It is drawn inside the same branch as the list, from the same
        # frame, so it cannot appear while the splash is showing and cannot disagree with the
        # table above it about which games qualify. An empty frame draws nothing at all —
        # `states.render_or_state` has already said the honest empty above.
        slate = _slate(games, esc=html.escape, scope=scope)
        if slate:
            st.markdown("**Slate**")
            st.markdown(slate, unsafe_allow_html=True)
            st.caption(
                f"Kick-off times Pacific. Each bar runs "
                f"{_SLATE_GAME_MINUTES // 60}h {_SLATE_GAME_MINUTES % 60:02d}m from kick-off "
                f"\u2014 a fixed allowance, not a measured end time, which CFBD does not "
                f"publish. Hover a bar for the matchup, network, line and why it qualified.")

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
    # 🚨 A189 (cfdb-main-R-1926). THE LEGEND SITS ON THE RADIO'S ROW, AT A QUARTER WIDTH.
    #
    # > **MARC:** *"Legend button is too big. Can you move it to be inline with the leaderboard
    # > depth? and reduce size to 1/4 of page width, or some other method to constrain the size
    # > to something reasonable."*
    #
    # ⚠️ A COLUMN RATIO, NOT A PIXEL GUESS. `st.popover(use_container_width=True)` is what made
    # the button full-width; the flag is kept and the CONTAINER is narrowed instead, so the
    # button fills a quarter of whatever the page is rather than a number that is right at one
    # viewport. `[3, 1]` is the quarter Marc asked for.
    depth_col, legend_col = st.columns([3, 1], vertical_alignment="bottom")
    with depth_col:
        depth = st.radio("Leaderboard depth", DEPTHS, index=0, horizontal=True,
                         key="today_depth", help="How many rows each leaderboard shows.")
    with legend_col:
        # ⚠️ THE LEGEND MOVED UP FROM BELOW THE TAB BAR, which is a visible change to the page's
        # order and is exactly what was asked for. Its CONTENTS are untouched.
        _legend(_completed_games(scope))

    _tab_bar(slug)
    # 🚨 A144. THE LEGEND BUTTON SITS UNDER THE TAB BAR, ABOVE THE PANELS THAT USE THE MARKS —
    # Marc: *"Need the legend button to help with the icons"*. `st.popover` is Schedule's own
    # control for the same job, so the site has one legend affordance rather than two (§4.3).
    #
    # ⚠️ IT IS DRAWN FOR EVERY TAB THOUGH ONLY SOME PANELS CARRY MARKS, and that is the cheaper
    # of two wrongs: a legend that appears and disappears as a reader moves between tabs reads as
    # a rendering fault, and `LEGEND_GROUPS_DRAWN` already guarantees it never explains a mark
    # this page cannot produce.
    # ⚠️ TODAY'S OWN FRAME, not a second query for two constant columns. `query` is
    # cache-backed, so on the recap tab this is the same call the panels make and costs
    # nothing; elsewhere it is one cached read of at most 400 rows. The alternative — a
    # dedicated `select upset_margin_big …` — would be a second source for a number the page
    # already has in hand, which is the drift §4.3 exists to stop.
    #
    # ✅ A189: the call MOVED to the radio's row above; it is not drawn twice.
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
