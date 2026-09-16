"""cfdb-main-R-916 — the win-probability curve's order, and the one expression that defines it.

`stg_game_win_probability.play_number` is NOT chronological. A136 measured 795 consecutive pairs
stepping BACKWARDS on the game clock across 336 of 1,898 games (17.7%), worst back-step −3,567
seconds. Everything built from `lag()` over that column inherits it.

🚨 THE DEFECT IS NOT VISIBLE IN ANY VALUE. The wrong and the right counts are integers on the same
grain in the same range, so the data tests that can see it live in dbt, against real rows
(`assert_the_by_clock_measures_are_counted_in_clock_order`). What THIS file guards is the thing a
dbt test cannot: that the expression defining the order stays in ONE place, and that the two dead
columns A140 deleted do not quietly come back.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MACRO = ROOT / "dbt" / "macros" / "elapsed_from_kickoff.sql"
PLAY = ROOT / "dbt" / "models" / "marts" / "fct_game_win_probability_play.sql"
SUMMARY = ROOT / "dbt" / "models" / "marts" / "fct_game_win_probability_summary.sql"


def _code(text: str) -> str:
    """SQL with `--` comment lines and Jinja comment blocks removed.

    🚨 A SOURCE-READING TEST MUST SCAN WHAT RUNS, NOT WHAT IS WRITTEN ABOUT IT. Every file here
    documents the arithmetic it must not repeat, so a raw grep for the expression finds the
    warning against it — A123 hit exactly this and the wrong repair was to delete the comment.
    """
    without_jinja = re.sub(r"\{#.*?#\}", "", text, flags=re.S)
    return "\n".join(line for line in without_jinja.splitlines()
                     if not line.lstrip().startswith("--"))


def test_the_clock_arithmetic_exists_in_exactly_one_place():
    """⚠️ TWO COPIES OF AN EXPRESSION THAT MUST AGREE IS THE DRIFT THIS PROJECT HAS PAID FOR FOUR
    TIMES IN TWO WEEKS — B098's `metric`, B099's `_CARD_KPIS`, B100's two delta renderers, A116's
    labels-as-data. A140 needed the same clock in a `lag()` window that
    `fct_game_win_probability_play` already publishes as a column, so it became a macro.

    ✅ THE ASSERTION IS THAT BOTH MODELS CALL IT AND NEITHER SPELLS IT OUT. Re-inlining is a
    one-line edit that looks harmless and leaves two definitions behind.
    """
    arithmetic = re.compile(r"-\s*1\s*\)\s*\*\s*900")

    assert arithmetic.search(_code(MACRO.read_text())), (
        "the macro must actually contain the arithmetic it exists to own")

    for model in (PLAY, SUMMARY):
        body = _code(model.read_text())
        assert not arithmetic.search(body), (
            f"{model.name} spells the clock arithmetic out again — call "
            f"elapsed_from_kickoff() instead, or there are two definitions to keep in step")
        assert "elapsed_from_kickoff(" in body or "curve_order(" in body, (
            f"{model.name} neither calls the macro nor inlines it — where does its clock come "
            f"from?")


def test_the_summary_counts_crossings_in_clock_order_and_keeps_the_old_one_beside_it():
    """§3.3's EXPAND, asserted at the source so a later round cannot collapse it by accident.

    ⚠️ BOTH WINDOWS HAVE TO BE THERE. The feed-ordered `lag` still feeds `lead_changes`, which
    `srv_game` publishes and `today.py` ranks on; the clock-ordered one feeds the `_by_clock`
    twins. Deleting either half turns an expand into a silent meaning change.
    """
    body = _code(SUMMARY.read_text())
    assert "order by w.play_number) as previous_wp" in body, (
        "the feed-ordered lag is gone — that is a CONTRACT, and it is gated on a deploy (§3.3.2)")
    assert "curve_order(" in body, "the clock-ordered lag is gone — the expand was undone"
    for column in ("lead_changes_by_clock", "largest_single_play_swing_by_clock",
                   "lead_changes_fourth_quarter_by_clock",
                   "largest_single_play_swing_fourth_quarter_by_clock",
                   "lead_changes_overtime_by_clock"):
        assert f"as {column}" in body, f"{column} is not emitted"


def test_the_two_dead_columns_do_not_come_back():
    """📊 A140 DELETED `final_home_win_probability` AND `halftime_home_win_probability_approx`
    BECAUSE NOTHING READ THEM — measured at `origin/main`: not selected by `srv_game`, not in
    `_models.yml`, present in exactly one file.

    🚨 AND THE REASON THEY LASTED WAS A CLAIM NOBODY CHECKED. A117 declined to fix the halftime
    approximation on the grounds that *"the column is published, a page reads it"*. It was not
    and one did not. ⚠️ A column nobody reads, computed wrongly, is dead weight a future round
    will trust — so this asserts the deletion rather than leaving it to a diff.
    """
    body = _code(SUMMARY.read_text())
    for column in ("final_home_win_probability", "halftime_home_win_probability_approx"):
        assert f"as {column}" not in body, (
            f"{column} is back. It had zero consumers and inherited cfdb-main-R-916; if a round "
            f"wants it, it is a NEW column with a definition somebody has asked for")

    # And nothing downstream may start selecting them either.
    for path in sorted((ROOT / "dbt" / "models" / "serving").glob("*.sql")):
        assert "final_home_win_probability" not in _code(path.read_text()), path.name
