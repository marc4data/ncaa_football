"""R-669 — the select-list parse, and the two ways a comment could blind it.

🚨 THE FALSE NEGATIVE IS WHY THIS ROUND HAPPENED. A102 hit the loud half: it put an explanatory
`--` line inside `COLUMNS` and the market-card guard went RED on a column that IS selected.
⚠️ The same parse fails silently the other way, and that half had never been seen.

Every expectation below was checked against the live driver on 2026-09-11 — `select <block>
from srv_game limit 0`, reading `cursor.description`. ⚠️ THE TESTS THEMSELVES ARE OFFLINE. A101
spent R-662/R-667 removing the suite's database dependency and a guard that only runs where
there is a tunnel is a guard that stops running, so Postgres validated the parser once and the
parser runs alone. The validation table is in the B088 report.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

import select_list  # noqa: E402


# The block that produced BOTH failures at once, measured. Postgres selects
# game_id, season, spread, home_moneyline — and NOT favorite_definitions_disagree, which is
# inside the comment.
BLINDING_COMMENT = """
    game_id, season,
    spread,
    -- dropped for now, favorite_definitions_disagree, restore with R-999
    home_moneyline
"""

REAL = {"game_id", "season", "spread", "home_moneyline"}


def _naive(sql):
    """The parse this round replaced. Kept so the tests can show what it did."""
    return {c.strip() for c in sql.replace("\n", " ").split(",") if c.strip()}


# --- 🚨 the silent half ------------------------------------------------------------------------

def test_a_COMMENTED_OUT_column_is_NOT_reported_as_selected():
    """🚨 THE ONE THAT MATTERS, AND THE ONE NOBODY HAD SEEN.

    A comment mentioning a column name between commas puts that name in the naive parse's
    "selected" set. The query does not select it, `row.get()` returns None on every load, and
    the guard written to catch exactly that says nothing.

    ⚠️ THIS IS B083's SHIPPED DEFECT WALKING BACK IN THROUGH ITS OWN GUARD. The market card
    read `favorite_definitions_disagree`, the SELECT never asked for it, and the caption was
    dead on all 70 games it existed for.
    """
    assert "favorite_definitions_disagree" in _naive(BLINDING_COMMENT), (
        "this fixture is meant to reproduce the naive parse's blind spot and no longer does")
    assert "favorite_definitions_disagree" not in select_list.selected_names(BLINDING_COMMENT)


def test_a_column_AFTER_a_comment_is_still_found():
    """The loud half — A102's case. `home_moneyline` follows the comment and is selected."""
    assert "home_moneyline" not in _naive(BLINDING_COMMENT), (
        "this fixture no longer reproduces the false positive it was written for")
    assert "home_moneyline" in select_list.selected_names(BLINDING_COMMENT)


def test_the_whole_block_matches_what_POSTGRES_SELECTS():
    """Both directions in one assertion, against the driver's own answer."""
    assert select_list.selected_names(BLINDING_COMMENT) == REAL
    assert _naive(BLINDING_COMMENT) != REAL, "the naive parse would have passed this"


# --- the shapes Part 2 required it survive -----------------------------------------------------

def test_a_block_comment_containing_commas_invents_no_columns():
    """A088 measured this family: a comma in a block comment invented one column name per
    comma, turning 153 column names into 156 fragments of prose."""
    sql = "game_id, /* season, week, all removed */ spread, over_under"
    assert select_list.selected_names(sql) == {"game_id", "spread", "over_under"}


def test_a_function_call_with_a_comma_inside_is_ONE_column():
    sql = "game_id, coalesce(spread, over_under) as fallback_number, season"
    assert select_list.selected_names(sql) == {"game_id", "fallback_number", "season"}


def test_an_alias_names_the_column_and_the_expression_does_not():
    """⚠️ `spread as the_spread` SELECTS `the_spread`. A guard that recorded `spread` would
    report a column the row does not carry — a false negative wearing a true name."""
    sql = "game_id, spread as the_spread, over_under ou"
    assert select_list.selected_names(sql) == {"game_id", "the_spread", "ou"}


def test_a_case_expression_is_one_column_named_by_its_alias():
    sql = ("game_id, case when spread < 0 then 'home' else 'away' end as favored_side, season")
    assert select_list.selected_names(sql) == {"game_id", "favored_side", "season"}


def test_a_comma_inside_a_string_literal_is_text_and_not_a_separator():
    sql = "game_id, case when spread < 0 then 'a, b' else 'c' end as label, season"
    assert select_list.selected_names(sql) == {"game_id", "label", "season"}


def test_a_DASH_DASH_inside_a_string_literal_does_not_start_a_comment():
    """⚠️ MEASURED AND CURRENTLY MOOT, WHICH IS WORTH SAYING RATHER THAN LEAVING IMPLIED.
    `COLUMNS` holds zero quote characters today, so no string literal exists in the block this
    guards. The parse handles it because the next person to add a `case … then 'x' end` should
    not have to discover that it did not."""
    sql = "game_id, case when spread < 0 then 'home -- favored' else 'away' end as note, season"
    assert select_list.selected_names(sql) == {"game_id", "note", "season"}


def test_a_qualified_name_reports_the_column_not_the_table():
    assert select_list.selected_names("g.spread, g.over_under") == {"spread", "over_under"}


# --- the honesty rule --------------------------------------------------------------------------

def test_an_expression_with_no_alias_is_DECLINED_rather_than_guessed():
    """🚨 GUESSING IS HOW A FALSE NEGATIVE GETS BACK IN. `count(*)` with no alias is named by
    Postgres, not by the text; inventing `count` would put a name in the selected set that the
    query never produces, which is the exact failure this module exists to remove."""
    sql = "game_id, count(*), spread"
    assert select_list.selected_names(sql) == {"game_id", "spread"}
    assert select_list.unnameable_items(sql) == ["count(*)"]


def test_the_CALENDAR_columns_block_names_every_column_the_circles_need():
    """🚨 cfdb-wta-R-1026. `_CALENDAR_COLUMNS` HAD NO GUARD AT ALL, AND B124 MEASURED WHAT THAT
    COSTS: **removing a column from that SQL turned exactly ONE test of 130 red.**

    The other 129 stayed green because the panel's harness stubs `query` and hands back a fixture
    frame that still carried the column — so against live serving the page would have drawn every
    circle open, **silently and correctly-looking**, with the suite behind it.

    ✅ SO IT GETS WHAT `COLUMNS` HAS ABOVE: a parse, a pinned answer, and nothing unnameable.
    ⚠️ **THE SET IS PINNED RATHER THAN THE COUNT**, which is the one improvement on the older
    guard: a round that drops `opponent_classification` and adds `opponent_conference` keeps the
    count at 18 and changes what the page can draw. A count cannot see a swap.

    ⚠️ AND A BUMP WITHOUT A REASON IS WORSE THAN NO GUARD — see `COLUMNS`'s own comment history,
    which records 101 → 103 → 104 and why each moved. **Add the name to the right group below
    with the round that needed it.**
    """
    from views import matchup
    parsed = select_list.selected_names(matchup._CALENDAR_COLUMNS)
    expected = {
        # the grain, and the leakage bound cfdb-wta-R-1000 put on it
        "team_id", "week", "game_date",
        # the hover: Marc's *"the Week #, Opponenet Rank, Name, Record, Final Score"* (B118/B119)
        "is_home", "opponent_abbreviation", "opponent_team_display", "opponent_rank",
        "record_before_display", "points_for", "points_against",
        # the six per-game figures the three sections draw their circles from (R-899)
        "total_yards", "rushing_yards", "passing_yards",
        "total_yards_allowed", "rushing_yards_allowed", "passing_yards_allowed",
        # which absence a missing figure is (B118)
        "game_figures_state",
        # ── 🚨 B149 (cfdb-wta-R-2701): Marc's per-team season table READS THIS CALENDAR ────
        #
        # > **MARC, v15:** *"add a table for each teams schedule w/high-level stats"*
        #
        # ⚠️ **IT DELIBERATELY DID NOT OPEN A SECOND `srv_game_team` READ.** The calendar
        # already fetched both teams in one query AND already carried the leakage bound
        # `game_date < :before` — and on the *Before the game* tab that bound is
        # cfdb-wta-R-1000, the defect Marc found live: *"It shouldn't present data that
        # transpired during the game."* **A fresh read would have shipped without it.**
        # ✅ So the seven stats and the played flag joined the read that was already here.
        "first_downs", "turnovers", "penalty_yards",
        "offense_ppa", "offense_rushing_plays_total_ppa",
        "offense_passing_plays_total_ppa", "cumulative_ppa_overall_total",
        "offense_success_rate", "offense_explosiveness",
        # whether this game has been played — the table shows played games only
        "has_box_score",
        # cfdb-wta-R-994: Marc's fill rule — filled when THAT game's opponent was FBS
        "opponent_classification",
    }
    assert parsed == expected, (
        f"`_CALENDAR_COLUMNS` no longer selects what the circles read. "
        f"missing {sorted(expected - parsed)}; unexpected {sorted(parsed - expected)}. "
        f"⚠️ The panel's tests CANNOT see this — they stub `query` and return a fixture frame "
        f"whatever the SQL says (B124's break 4: one test of 130 went red). If the change is "
        f"deliberate, move the name here WITH its reason; do not delete the assertion.")
    # 18 -> 28: B149 (cfdb-wta-R-2701) added the nine season-table stats plus `has_box_score`
    # to the read that already existed rather than opening a second one — see the group above
    # and its leakage-bound reason.
    assert len(parsed) == 28
    assert not select_list.unnameable_items(matchup._CALENDAR_COLUMNS)


def test_the_REAL_columns_block_parses_cleanly_and_names_everything():
    """⚠️ THE NEW PARSE MUST NOT MOVE THE CURRENT ANSWER — 101 names, the same 101 the driver
    returned on 2026-09-11, and nothing it had to decline.

    🚨 IT DELIBERATELY DOES NOT ASSERT `parsed == _naive(COLUMNS)`, AND THE STAGED BREAK IS WHY.
    The first version did, which was true today only because `COLUMNS` happens to carry no
    comments — so adding the very comment this round exists to allow turned this test red.
    A guard that fails when the thing it enables is used is not a guard, it is a tripwire on
    our own feet. The equality is asserted below only while the block is comment-free, which is
    the honest version of the same claim.
    """
    from views import matchup
    parsed = select_list.selected_names(matchup.COLUMNS)
    # 101 -> 103: R-605 selected market_implied_home_points / _away_points, built by
    # fct_market_probability and never shown until the board's fourth column.
    # 103 -> 104: cfdb-wta-R-1000 selected `game_date`. The Before-the-Game circles are bounded to
    # games that kicked off BEFORE this one, and the bound needs this game's own date — **it
    # cannot be derived from `start_date`, which is a UTC instant while `game_date` is the local
    # calendar date, and the two genuinely differ** (game 401856670: `game_date` 2026-09-12
    # against `start_date` 2026-09-13 02:15Z).
    # 104 -> 106: B149 (cfdb-wta-R-2702) selected `home_team_slug` / `away_team_slug`. Marc asked
    # the season table to be *"a tab that allows end-user to toggle between the teams"*, and
    # `st.tabs` is banned on this page (R-283 — it loses the tab on every link, and
    # `test_no_post_game_content_was_stubbed` enforces it). **The page's own bar carries the
    # choice in the URL instead, and `team` is already in `params.KNOWN`** — so the toggle needed
    # no `site/lib/` edit (session A's, §3.2.2) and this SELECT needed the two slugs.
    assert len(parsed) == 106
    assert not select_list.unnameable_items(matchup.COLUMNS)
    assert all(name.replace("_", "").isalnum() for name in parsed), \
        f"the parse produced something that is not an identifier: {sorted(parsed)}"
    if "--" not in matchup.COLUMNS and "/*" not in matchup.COLUMNS:
        assert parsed == _naive(matchup.COLUMNS), (
            "with no comment in the block the two parses must agree, or this round changed "
            "WHAT the guards check rather than only how they read it")
