"""A291 (cfdb-main-R-5043). The status board must not publish a stale verdict as current.

🚨 WHAT THIS GUARDS, AND IT HAPPENED. On 2026-11-02 `srv_system_health` published
`scores_refresh · error · "PUBLISH HAS STOPPED — last completed 24 hours ago"` from a build
taken 2026-11-01 14:00Z. The cadence had beaten 42 minutes before a human read the board.
The verdict was not wrong about the past; it was SILENT ABOUT BEING A SNAPSHOT.

📊 THE MECHANISM IS A CADENCE MISMATCH OF TWO ORDERS OF MAGNITUDE. `srv_system_health` is
rebuilt by exactly one task — `weekly_refresh_dag.py`'s catalogue step — which fires Tuesday,
Thursday and Sunday. The `scores_refresh` budget it reports on is FIVE HOURS. So a verdict
about a five-hour cadence is routinely three days old, and every "N hours ago" in `detail`
is measured against a clock the reader cannot see.

⚠️ WHY THE GUARD IS IN PYTHON AND NOT IN dbt, because this is the part that is easy to get
wrong twice. A290 fixed the sibling defect (`deployment` publishing a 67-day-old `ok`) with a
build-time SQL branch, and that worked because the evidence came from ANOTHER table and could
already be old when the board was built. Here the evidence is the build clock itself:
`current_timestamp - current_timestamp` is zero on every build, so a SQL staleness branch
could never evaluate true. That is R-760 exactly — an assertion nothing the code can produce
could satisfy — so the model PUBLISHES the stamp and the page JUDGES it against its own
clock, which is the only clock that exists at read time.

Three things are asserted, and the first is the one that would have caught the incident:

  1. An over-age verdict produces a STALE banner whose text names the age.
  2. A fresh verdict does not, so the banner is not permanent decoration.
  3. An ABSENT or NULL stamp produces SILENCE, never reassurance (AC-G.11) — a reader on an
     older published tree must not be told the board is current by a branch that simply
     could not evaluate.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "site"))

from views import system  # noqa: E402

MODEL = REPO / "dbt" / "models" / "serving" / "srv_system_health.sql"
MACRO = REPO / "dbt" / "macros" / "health_verdict.sql"


def board(computed_at, rows=2):
    """A board whose rows all carry the same verdict stamp."""
    return pd.DataFrame({
        "signal_type": ["pipeline"] * rows,
        "subject": [f"cadence_{i}" for i in range(rows)],
        "severity": ["error"] * rows,
        "detail": ["PUBLISH HAS STOPPED — last completed 24 hours ago"] * rows,
        "observed_at": [pd.Timestamp("2026-10-31 14:00:15+00:00")] * rows,
        "verdict_computed_at": [computed_at] * rows,
        "as_of_ts": [pd.Timestamp("2026-11-01 14:00:00+00:00")] * rows,
    })


NOW = pd.Timestamp("2026-11-02 18:00:00+00:00")


def test_an_over_age_verdict_is_flagged_stale():
    """THE INCIDENT, REPRODUCED: a verdict 28 hours old must not read as current."""
    built = pd.Timestamp("2026-11-01 14:00:00+00:00")
    stale, note = system._verdict_note(board(built), now=NOW)

    assert stale is True, (
        "a verdict 28 hours old was NOT flagged stale. This is the exact row that was on "
        "the board on 2026-11-02 saying PUBLISH HAS STOPPED about a cadence that had beaten "
        "42 minutes earlier.")
    # R-843: the pinned value must MOVE under the break. The age is the thing that matters,
    # so the message has to carry it rather than being a generic warning.
    assert "28 hours ago" in note, f"the banner does not name the verdict's age: {note!r}"
    assert "snapshot" in note


def test_the_banner_names_the_absolute_column_to_read_instead():
    """A warning that does not say what to do instead spends attention without paying it."""
    _, note = system._verdict_note(board(pd.Timestamp("2026-10-30 14:00:00+00:00")), now=NOW)
    assert "Observed" in note, (
        "the stale banner must point the reader at `observed_at`, which is an absolute "
        f"timestamp and therefore still true however old the build is. Got: {note!r}")


def test_a_fresh_verdict_is_not_flagged():
    """Not permanent decoration — the quiet branch has to be reachable too."""
    fresh = NOW - pd.Timedelta(hours=1)
    stale, note = system._verdict_note(board(fresh), now=NOW)
    assert stale is False
    assert "1 hour ago" in note


def test_the_boundary_is_the_shortest_budget_on_the_board():
    """VERDICT_STALE_HOURS is derived, not chosen: scores_refresh's budget is five hours."""
    assert system.VERDICT_STALE_HOURS == 6
    just_inside = NOW - pd.Timedelta(hours=system.VERDICT_STALE_HOURS) + pd.Timedelta(minutes=1)
    just_outside = NOW - pd.Timedelta(hours=system.VERDICT_STALE_HOURS) - pd.Timedelta(minutes=1)
    assert system._verdict_note(board(just_inside), now=NOW)[0] is False
    assert system._verdict_note(board(just_outside), now=NOW)[0] is True


@pytest.mark.parametrize("frame", [
    pytest.param(pd.DataFrame(), id="empty_board"),
    pytest.param(None, id="no_frame"),
])
def test_an_empty_board_says_nothing_rather_than_all_clear(frame):
    stale, note = system._verdict_note(frame, now=NOW)
    assert (stale, note) == (False, "")


def test_a_board_without_the_column_is_silent_not_reassuring():
    """AC-G.11. A reader on an older published tree gets no claim at all.

    🚨 THE BRANCH THAT MUST NOT EXIST IS "column missing, therefore fine". That is how
    R-3766 rendered NULL freshness as `ok` — an absence evaluated as an all-clear.
    """
    df = board(pd.Timestamp("2026-11-01 14:00:00+00:00")).drop(columns=["verdict_computed_at"])
    stale, note = system._verdict_note(df, now=NOW)
    assert (stale, note) == (False, ""), (
        "a board with no verdict stamp must produce NO message. Saying 'verdict computed "
        "just now' when the column is absent would be a fabricated reassurance.")


def test_a_null_stamp_is_silent_too():
    stale, note = system._verdict_note(board(pd.NaT), now=NOW)
    assert (stale, note) == (False, "")


def test_the_model_publishes_the_stamp_through_the_macro():
    """ONE HOME (R-574): the stamp is the macro's, and the model must not inline its own."""
    sql = MODEL.read_text(encoding="utf-8")
    assert "health_verdict_computed_at()" in sql, (
        "srv_system_health must publish verdict_computed_at through the macro")
    assert "as verdict_computed_at" in sql
    assert "health_verdict_anchored(" in sql, (
        "the pipeline detail's relative figures must be anchored to the build clock")


def test_the_macro_does_not_carry_a_second_copy_of_the_threshold():
    """R-574, stated as a test because the obvious 'fix' is to add a dbt var beside it.

    A threshold in `health_verdict.sql` AND in `system.py` would be one number in two
    languages, and only one of them can ever fire (the SQL one cannot — see this file's
    header). The macro owns the STAMP; the page owns the JUDGEMENT.
    """
    macro = MACRO.read_text(encoding="utf-8")
    assert "stale_hours" not in macro, (
        "health_verdict.sql has grown a staleness threshold. It cannot fire at build time "
        "and it duplicates site/views/system.py's VERDICT_STALE_HOURS.")


def test_the_page_still_asks_for_the_column_it_judges():
    """A guard against the cheapest wrong fix: dropping the column from the query.

    If `verdict_computed_at` leaves the select list, `_verdict_note` takes its absent-column
    branch and goes permanently silent — every test above still passes and the feature is
    gone. That is §6's mode-2 failure, so it gets its own assertion.
    """
    page = (REPO / "site" / "views" / "system.py").read_text(encoding="utf-8")
    query_text = page.split('select signal_type', 1)[1].split('"""', 1)[0]
    assert "verdict_computed_at" in query_text, (
        "system.py no longer selects verdict_computed_at, so _verdict_note can never see a "
        "stamp and the stale banner is unreachable.")


def test_the_fresh_beat_branch_does_not_claim_a_publish():
    """🚨 cfdb-main-R-5048. §2.3's asymmetry, as a test, because a reader believed the old text.

    Measured live 2026-11-02: this signal published
    `scores_refresh · ok · "published 2 hours ago"` while `publish_to_serving` had not
    succeeded since 2026-10-31 13:04Z — 54 hours against a five-hour budget.

    `heartbeat` carries `trigger_rule=NONE_FAILED` on purpose, so it beats on a deliberate
    cadence SKIP as well as a success. cfdb-main-R-4109: a STALE beat IS a stopped publish,
    but a FRESH beat is NOT a working publish. The fresh branch therefore may not use the
    word, and the test pins the direction rather than the sentence.
    """
    sql = MODEL.read_text(encoding="utf-8")
    pipeline = sql.split("pipeline as (", 1)[1].split("orphan_market as (", 1)[0]
    fresh = pipeline.split("else 'last beat", 1)
    assert len(fresh) == 2, (
        "the fresh-beat branch no longer starts 'last beat' — if it has gone back to "
        "'published', that is cfdb-main-R-5048 returning")
    assert "'published '" not in pipeline, (
        "the pipeline signal claims 'published' from a number that measured a BEAT. A fresh "
        "beat is not a working publish (cfdb-main-R-4109).")


def test_the_stale_beat_branch_still_shouts_about_the_publish():
    """The other half of the asymmetry — and the half it would be easy to flatten.

    The cheapest way to satisfy the test above is to scrub the word 'publish' from the whole
    CTE, which would ALSO silence the one branch that is entitled to say it. A stale beat
    genuinely is a stopped publish, because the beat sits downstream of publish_to_serving
    and cannot advance past a failure.
    """
    sql = MODEL.read_text(encoding="utf-8")
    pipeline = sql.split("pipeline as (", 1)[1].split("orphan_market as (", 1)[0]
    assert "'PUBLISH HAS STOPPED" in pipeline, (
        "the over-budget branch must still name the stopped publish — a stale beat IS a "
        "stopped publish (§2.3), and flattening both branches loses the real alarm.")
