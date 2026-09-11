"""R-641 / R-642 — the week's shared frame is built over the body of the league.

🚨 WHY THIS FILE EXISTS AS WELL AS THREE dbt TESTS. The dbt tests assert the invariant on
BUILT DATA, which is the real proof — and they only run against a warehouse. The staged
breaks for this round have to fire in `pytest -q`, alone and in the full suite, so the
structural half lives here and costs nothing: revert the axis to the extremes and this goes
red before anything is built.

⚠️ IT ASSERTS THE STRUCTURE, NOT A RECOMPUTED NUMBER. Reimplementing the nice-number rule in
Python would make a second source of truth for the axis, which is the thing the model exists
to be — so these read the model's own SQL and assert which columns the frame is derived from.
"""
import re
from pathlib import Path

import pytest

MODEL = (Path(__file__).resolve().parents[1]
         / "dbt" / "models" / "marts" / "fct_team_week_metric_distribution.sql")

# The two metric families this model carries, and every one is a yards-per-game figure. The
# zero floor in `frame_low` rests on exactly that, so the list is repeated here rather than
# imported: a test that reads its expectation out of the thing it checks cannot fail, which
# A089 proved by shipping one that did not.
EXPECTED_METRICS = {
    "total_yards_for_per_game", "total_yards_allowed_per_game",
    "rushing_yards_for_per_game", "rushing_yards_allowed_per_game",
    "passing_yards_for_per_game", "passing_yards_allowed_per_game",
}


@pytest.fixture(scope="module")
def sql():
    return MODEL.read_text()


def _limit_expression(sql, which):
    """The `as axis_min` / `as axis_max` select expression, comments stripped.

    Anchored on the `as axis_<which>` alias rather than on a line number, and the preceding
    `--` comment lines are dropped so that PROSE mentioning `max_value` cannot satisfy — or
    break — an assertion about the CODE. The comment above these two lines names both
    `min_value` and `max_value` deliberately, to say what the frame is NOT built over.
    """
    body = sql.split(f"as axis_{which}")[0]
    lines = [line for line in body.splitlines() if not line.strip().startswith("--")]
    # Everything back to the previous alias or the start of the final select.
    tail = []
    for line in reversed(lines):
        tail.append(line)
        if re.search(r"^\s*case when axis_step is not null", line):
            break
    return "\n".join(reversed(tail))


def test_the_axis_is_derived_from_the_whiskers_and_not_from_the_extremes(sql):
    """🚨 THE ROUND. An axis built over min_value/max_value squashes the league into its floor.

    Measured at 2026 regular week 2: `rushing_yards_for_per_game` ran [0, 600] because Army
    569, Navy 506, Rice 465 and Air Force 431 are in the data every week of every season, and
    103 of the 282 teams carrying a value sat in the bottom fifth of that frame.
    """
    for which, expected in (("min", "frame_low"), ("max", "frame_high")):
        expression = _limit_expression(sql, which)
        assert expected in expression, (
            f"axis_{which} must be derived from {expected} — the whiskers, floored at zero — "
            f"not from the week's extremes. Got:\n{expression}")
        for forbidden in ("min_value", "max_value"):
            assert forbidden not in expression, (
                f"axis_{which} is built over {forbidden}. That is the squash R-641 removed: "
                f"four triple-option academies stretch the frame for all 138 teams, and 36.5% "
                f"of the league lands in the bottom fifth of its own chart.")


def test_the_tick_step_is_derived_from_the_frame_that_is_actually_drawn(sql):
    """A step derived from a range nobody draws labels the ticks for a different chart."""
    step = sql.split("as axis_step")[0]
    step = "\n".join(line for line in step.splitlines()
                     if not line.strip().startswith("--"))
    step = step[step.rindex("select f.*,"):]
    assert "frame_high - frame_low" in step, (
        "axis_step must be derived from the frame it labels. Got:\n" + step)
    assert "max_value - min_value" not in step


def test_the_frame_floor_is_zero_because_every_metric_here_is_a_yardage(sql):
    """R-642. The AXIS is clamped; the value never is.

    ⚠️ Asserts BOTH halves, because clamping the data is the tempting wrong fix and it would
    satisfy a test that only checked the axis. `greatest(0, ...)` may appear exactly once in
    this model and it must be on the frame, not on a value.
    """
    assert re.search(r"greatest\(cast\(0 as \{\{ dbt\.type_numeric\(\) \}\}\), whisker_low\)",
                     sql), "frame_low must floor the whisker at zero"
    clamps = re.findall(r"greatest\s*\(", sql)
    assert len(clamps) == 1, (
        f"{len(clamps)} greatest() calls in this model. R-642 clamps the AXIS and nothing "
        f"else: a greatest() reaching a value turns a real -7.0 rushing average into a 0.0 "
        f"and loses a measurement to tidy a frame.")


def test_every_metric_on_the_shared_frame_is_a_yards_per_game_figure(sql):
    """The zero floor is only honest while that is true, and it is not self-evident.

    A signed metric — a margin, a differential, an EPA figure — added to the list would make
    `greatest(0, whisker_low)` silently cut the bottom off its distribution. The dbt test
    assert_a_yardage_axis_never_starts_below_zero catches it in built data; this catches it in
    the diff.
    """
    block = sql.split("{% set metrics = [")[1].split("] %}")[0]
    declared = set(re.findall(r"'([a-z_]+)'", block))
    assert declared == EXPECTED_METRICS, (
        f"the model's metric list changed: {declared ^ EXPECTED_METRICS}. Every metric on this "
        f"shared frame must be a yards-per-game figure, because frame_low floors the axis at "
        f"zero for all of them. Adding a signed metric means deciding the floor per metric.")
