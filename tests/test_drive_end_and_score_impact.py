"""A224 — the two claims `srv_drive`'s new columns make, guarded where CI can see them.

CI HAS NO WAREHOUSE, so the data claims live in two singular dbt tests
(`assert_the_offense_end_is_the_drives_own_gain`,
`assert_score_impact_says_whether_to_believe_it`) which run inside `dbt build` against the
fixture and against production. Those assert the arithmetic on real rows.

🚨 WHAT THEY CANNOT SEE IS THE THING THIS ROUND IS ACTUALLY RISKING: that the model's
`score_impact` rule is a SECOND OPINION rather than `matchup.py`'s rule MOVED. Both copies
exist at once for one round — A224 publishes the column, a later session-B round deletes the
page's `_drive_score_impact` and reads it — and during that window nothing compares them.
📊 If they disagree, the page's suppressed count changes when B swaps over, and the only
symptom is a different number of em dashes on a chart nobody is diffing.

⚠️ `site/views/matchup.py` IS SESSION B's FILE (§3.2.2) AND THIS TEST ONLY READS IT. It is
the specification here, not the subject: the page shipped the rule first, B151 asked for it
upstream, and the model is required to agree with it.
"""
import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import select_list                                   # noqa: E402
from views import matchup                            # noqa: E402

FCT_DRIVE = (ROOT / "dbt" / "models" / "marts" / "fct_drive.sql").read_text(encoding="utf-8")
SRV_DRIVE = (ROOT / "dbt" / "models" / "serving" / "srv_drive.sql").read_text(encoding="utf-8")
SRV_GAME_TEAM = (ROOT / "dbt" / "models" / "serving" / "srv_game_team.sql").read_text(
    encoding="utf-8")

# The five columns A224 adds to srv_drive, and the one it adds to srv_game_team.
NEW_DRIVE_COLUMNS = ("offense_end_yards_from_own_goal", "offense_end_yardline",
                     "is_offense_end_on_field", "score_impact", "is_score_impact_coherent")


def _expression(alias, sql=FCT_DRIVE):
    """The SQL expression `fct_drive` aliases to `alias`, comments stripped.

    Reads the model's own text rather than a copy of it. `select_list.strip_comments` is
    A102's helper and exists because a `--` line mentioning a column can blind a naive parse
    in BOTH directions (R-669) — this file would otherwise be the third guard to carry its
    own broken split.
    """
    body = select_list.strip_comments(sql)
    for item in select_list.split_items(body):
        if select_list.output_name(item) == alias:
            return re.sub(r"\s+", " ", item).rsplit(" as ", 1)[0].strip()
    raise AssertionError(f"fct_drive selects no column aliased {alias!r}")


# ==========================================================================================
# PART 2 — THE PAGE'S RULE, MOVED RATHER THAN REINVENTED
# ==========================================================================================

def test_the_models_legal_impact_set_is_the_pages_frozenset_exactly():
    """🚨 THE ONE PARAMETER THAT CAN DRIFT SILENTLY WHILE BOTH COPIES EXIST.

    `_DRIVE_LEGAL_IMPACTS` is what a scoring play can put on a board from the offense's point
    of view — a safety, a field goal, a touchdown alone or with either conversion, either
    sign, or nothing. It reached the page because a render caught a FIELD GOAL worth -4
    passing guard 1; it reaches the model because B151 asked for the arithmetic upstream.

    ⚠️ A SET IS THE EASY THING TO GET NEARLY RIGHT. Dropping 8, or adding 1 because a safety
    "looks like" one, changes the suppression rate by a few hundred drives and changes no
    test that counts columns. Compared as SETS, so ordering and formatting are free.
    """
    literal = re.search(r"in \(([-0-9, ]+)\)", _expression("is_score_impact_coherent"))
    assert literal, "the legal-impact set is no longer an `in (...)` list in fct_drive.sql"
    model_set = {float(v) for v in literal.group(1).split(",")}
    assert model_set == set(matchup._DRIVE_LEGAL_IMPACTS), (
        f"fct_drive allows {sorted(model_set)}; matchup._DRIVE_LEGAL_IMPACTS is "
        f"{sorted(matchup._DRIVE_LEGAL_IMPACTS)}")


def test_the_model_cross_checks_the_delta_against_is_scoring_drive():
    """GUARD 1, which is the half a reader would not think to look for.

    The delta alone is computable and wrong: B133's render found a PUNT worth +7 and a
    TOUCHDOWN worth 0 from the published snapshots. What makes the column trustworthy is that
    `is_scoring_drive` is derived from the drive's RESULT rather than from the scoreboard, so
    the two are independent facts about one drive.

    ⚠️ Asserting the column merely EXISTS would pass on a flag that is `true` everywhere.
    """
    expression = _expression("is_score_impact_coherent")
    assert "is_scoring_drive" in expression, expression
    assert "coalesce" in expression, (
        "the flag must be total — a third state is an absence that does not say which "
        "absence it is (AC-G.11)")


@pytest.mark.parametrize("label,row,expected", [
    # The three shapes the overtime render actually caught, named as B133 named them.
    ("a punt worth +7",        dict(start_offense_score=0, end_offense_score=7,
                                    start_defense_score=0, end_defense_score=0,
                                    is_scoring_drive=False), False),
    ("a touchdown worth 0",    dict(start_offense_score=17, end_offense_score=17,
                                    start_defense_score=0, end_defense_score=0,
                                    is_scoring_drive=True), False),
    ("a field goal worth -4",  dict(start_offense_score=10, end_offense_score=10,
                                    start_defense_score=0, end_defense_score=4,
                                    is_scoring_drive=True), False),
    # And the ordinary shapes, which must survive both guards.
    ("a touchdown with a kick", dict(start_offense_score=0, end_offense_score=7,
                                     start_defense_score=0, end_defense_score=0,
                                     is_scoring_drive=True), True),
    ("a safety for the defense", dict(start_offense_score=3, end_offense_score=3,
                                      start_defense_score=0, end_defense_score=2,
                                      is_scoring_drive=True), True),
    ("a punt that scored nothing", dict(start_offense_score=14, end_offense_score=14,
                                        start_defense_score=7, end_defense_score=7,
                                        is_scoring_drive=False), True),
])
def test_the_models_own_sql_agrees_with_the_page_on_every_case(label, row, expected):
    """🚨 THE AGREEMENT TEST, AND IT EVALUATES THE MODEL'S TEXT RATHER THAN A COPY OF IT.

    R-768 is the trap this is written around: a test that builds its own frame, applies its
    own version of the rule and asserts the result is asserting that PYTHON WORKS. So the
    boolean expression below is LIFTED OUT OF `fct_drive.sql` and evaluated — if the model's
    rule changes shape, this test evaluates the new one, and if it changes MEANING this test
    goes red against the page.

    The translation is four mechanical token swaps (`<>`, `coalesce`, the `in (...)` list,
    `true`/`false`) and nothing else; anything cleverer would be a SQL parser, which
    `select_list`'s own header says not to build.
    """
    expression = _expression("is_score_impact_coherent")
    python = (expression
              .replace("<>", "!=")
              .replace(" = ", " == ")
              .replace("coalesce", "_coalesce")
              .replace("true", "True").replace("false", "False"))
    python = re.sub(r"in \(([-0-9, ]+)\)", lambda m: f"in ({m.group(1)},)", python)
    # A crash here is a real failure, not a passing test — R-758's third mode, made loud.
    compiled = compile(ast.Expression(ast.parse(python, mode="eval").body), "<fct_drive>",
                       "eval")

    def _coalesce(*values):
        return next((v for v in values if v is not None), None)

    model_says = eval(compiled, {"_coalesce": _coalesce}, dict(row))
    page_says = matchup._drive_score_impact(row) is not None

    assert model_says == expected, f"{label}: the model says {model_says}"
    assert model_says == page_says, (
        f"{label}: fct_drive says {model_says}, matchup._drive_score_impact says {page_says}")


# ==========================================================================================
# PART 1 — THE OFFENSE'S END IS THE DRIVE'S OWN GAIN, AND IT IS NOT `end_yardline`
# ==========================================================================================

def test_the_offense_end_is_derived_from_the_drive_gain_not_the_end_coordinate():
    """🚨 THE WHOLE POINT OF THE COLUMN, ASSERTED WHERE CI CAN SEE IT.

    `end_yards_to_goal` is the possession-CHANGE spot since 2026 — where the punt landed,
    where the return ended, the ensuing kickoff after a score. 📊 It equals the offense's own
    end on 90.3% of 2024 drives, 81.3% of 2025 and 40.9% of 2026, and on 0.9% of 2026 punts.
    **Deriving the new column from it would reproduce the defect it exists to route around**,
    and would look right on three quarters of the table while doing it.
    """
    for alias in ("offense_end_yards_to_goal", "offense_end_yards_from_own_goal"):
        expression = _expression(alias)
        assert "start_yards_to_goal" in expression and "yards" in expression, expression
        assert "end_yards_to_goal" not in expression, (
            f"{alias} is derived from the possession-change spot: {expression}")


def test_the_offense_end_is_never_clamped():
    """A DRIVE CAN LOSE YARDS AND THE BAR MUST RENDER BACKWARDS (R-306).

    📊 10.1% of 2024 drives, 10.1% of 2025 and 11.0% of 2026 end behind where they started,
    and 590 put the offense's end outside 0..100 at all. A `greatest`/`least` would hide every
    one of those and the column would look perfect — which is why the flag is a separate
    column and the value is left alone.
    """
    for alias in ("offense_end_yards_to_goal", "offense_end_yards_from_own_goal",
                  "offense_end_yardline"):
        expression = _expression(alias)
        for clamp in ("greatest", "least", "abs("):
            assert clamp not in expression, f"{alias} is clamped with {clamp}: {expression}"


def test_the_off_field_flag_names_the_offense_end_and_not_the_old_one():
    """📊 590 ROWS AGAINST 118, AND ONLY 38 IN BOTH — so reusing `is_end_on_field` would tell
    a reader that 118 rows are suspect when 590 are, and name the wrong ones."""
    expression = _expression("is_offense_end_on_field")
    assert "start_yards_to_goal" in expression, expression
    assert "end_yards_to_goal" not in expression, expression
    assert _expression("is_end_on_field") != expression, (
        "the two flags compute the same thing; one of them is wrong about which rows")


# ==========================================================================================
# WHAT SERVING ACTUALLY PUBLISHES — §2.2.1c.2's LESSON, ONE LAYER EARLIER
# ==========================================================================================

def test_srv_drive_publishes_every_new_column():
    """A column on `fct_drive` that `srv_drive` does not select is a column the site cannot
    read. R-1007 is this exact mistake in the other direction — a name that appeared in a
    model file, was consumed by an expression, and was never published."""
    published = select_list.selected_names(SRV_DRIVE)
    missing = [c for c in NEW_DRIVE_COLUMNS if c not in published]
    assert not missing, f"srv_drive does not publish {missing}"


def test_srv_game_team_publishes_the_kickoff_timestamp():
    """PART 3. `start_date` is what makes session B's leakage bound exact rather than nearly
    exact: 📊 60 team-games share a DATE with another game of the same team, 28 share the
    timestamp, and from 2024 on it is 1 collision by date and 0 by timestamp."""
    assert "start_date" in select_list.selected_names(SRV_GAME_TEAM)


def test_the_new_columns_are_documented():
    """⚠️ Every new column gets a one-paragraph description (the repo rule A214 added), and
    `persist_docs` puts it in the Data Dictionary a reader can open."""
    yaml_text = (ROOT / "dbt" / "models" / "serving" / "_models.yml").read_text(
        encoding="utf-8")
    for column in NEW_DRIVE_COLUMNS + ("start_date",):
        assert f"- name: {column}\n" in yaml_text, f"{column} carries no description"
