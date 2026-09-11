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
import select_list


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
    assert len(parsed) == 101
    assert not select_list.unnameable_items(matchup.COLUMNS)
    assert all(name.replace("_", "").isalnum() for name in parsed), \
        f"the parse produced something that is not an identifier: {sorted(parsed)}"
    if "--" not in matchup.COLUMNS and "/*" not in matchup.COLUMNS:
        assert parsed == _naive(matchup.COLUMNS), (
            "with no comment in the block the two parses must agree, or this round changed "
            "WHAT the guards check rather than only how they read it")
