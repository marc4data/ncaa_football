"""The reader-facing name for each serving view the site reads.

R-583. LIFTED OUT OF `views/today.py` UNCHANGED, AND THE MOVE IS THE WHOLE POINT.

Marc, 2026-09-10: *"for the pages we've been working on: Today, Matchups. Each block on the
page should include a small footnote, or header note indicating what dataset it's pulling
from. That will help me understand what's possible. I'll also use it to make sure we're
covering the major datasets in the Excel Export utility."*

A089 built the mechanism for Today and put this table in `today.py`, which is session A's
file. Matchup is session B's. 🚨 IF B DECLARED ITS OWN LABEL MAP THERE WOULD BE TWO TABLES
NAMING THE SAME VIEWS — `srv_game` and `srv_team_week` are read by both pages — AND THE FIRST
THING THEY WOULD DO IS DISAGREE. That is precisely what A089's design existed to prevent one
level down: the caption is emitted from `states.section`'s own `view` argument so that "a
caption that disagrees with the Error state under the same panel is now impossible to write,
because they are one string". Two label tables would reintroduce the drift at page grain.

⚠️ THIS IS A LABEL TABLE, NOT A PANEL-TO-VIEW TABLE, and the distinction is load-bearing.
Which view a panel reads is declared exactly once, in that panel's own `states.section(...)`
call — the place that has always known it. This answers a different question: what a reader
should be told that view IS.

AC-G.7 as amended: front of house says "Team box scores", not `srv_team_game_log`. The
identifier still travels, because `table.dataset_caption` renders the label as a link to
/dictionary?table=<view>, so the jargon is one click away and off the page.

⚠️ A KEY HERE THAT NO SECTION NAMES, OR A SECTION NAMING A VIEW ABSENT HERE, IS A DEFECT.
`tests/test_today_tabs.py` asserts both directions for Today. A page adopting this table
should assert the same, rather than trusting the dict to be complete for it.

⚠️ AND ADDING A KEY DOES NOT MAKE A CAPTION APPEAR. §3 rule 3.1: a shared-module change ships
the parameter and the default, and the call sites in another session's files are that
session's to consume on their own round. The five Matchup-only views below have labels and no
callers yet; B's round wires them.
"""

DATASETS = {
    # --- read by Today (A089) -----------------------------------------------------------
    "srv_game": "Game results and market lines",
    "srv_team_week": "Team form, by week",
    "srv_team_game_log": "Team box scores",
    "srv_player_game_log": "Player box scores",
    "srv_rankings": "AP and Coaches polls",
    # --- read by Matchup, labelled here so B consumes rather than copies (R-583) ---------
    # ⚠️ srv_game and srv_team_week are ALREADY ABOVE and Matchup reads both. That overlap is
    # the argument for this module existing rather than a duplication to tidy up.
    "srv_game_team": "Team box scores, one row per side",
    "srv_game_team_leader": "Game leaders, by player",
    "srv_game_weather": "Kickoff weather",
    "srv_game_travel": "Travel and rest",
    "srv_drive": "Drive-by-drive log",
    "srv_data_dictionary": "The data dictionary",
}
