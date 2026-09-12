"""The health board's two ends, held to each other. R-701.

A109 found that `cfdb_heartbeat.sh` had emitted `failed_test|<name>|<failures>|<age>` since R-412
and that `ci/check_heartbeats.py` never parsed it — so the name Marc needed was on the wire for
nineteen and a half hours while the alert said only which TASK failed. The contract test that
should have caught it pinned the one shape that already existed and stopped there.

A110's census asked where else that is true. This file is the answer for the health board, whose
pairs are:

    marts.fct_dq_test_result.status  ->  srv_system_health's `data_quality` severity
    srv_system_health.severity       ->  ci/check_health_signals.py KNOWN_SEVERITIES
    srv_system_health.signal_type    ->  ci/check_health_signals.py declared_signal_types()
    ci/fixtures.sql                  ->  the checker's "never escalates" rule

Asserted on the files' own text, because there is no warehouse in CI at collection time.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "dbt" / "models" / "serving" / "srv_system_health.sql"
CHECKER = ROOT / "ci" / "check_health_signals.py"
FIXTURES = ROOT / "ci" / "fixtures.sql"
DQ_FACT = ROOT / "dbt" / "models" / "marts" / "fct_dq_test_result.sql"


def _severities_the_model_emits() -> set:
    """Every literal the model assigns to `severity`, from its own CASE expressions."""
    sql = MODEL.read_text(encoding="utf-8")
    return set(re.findall(r"then '([a-z_]+)'", sql)) | set(re.findall(r"else '([a-z_]+)'", sql))


def _known_severities() -> set:
    code = CHECKER.read_text(encoding="utf-8")
    match = re.search(r"KNOWN_SEVERITIES = \{([^}]*)\}", code)
    assert match, "KNOWN_SEVERITIES moved; this contract can no longer be checked"
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


def test_every_severity_the_model_emits_is_one_the_checker_knows():
    """The R-412 shape: an emitter producing a value its reader has no branch for.

    The checker's colour map and sort order are built around KNOWN_SEVERITIES, so a severity
    outside it renders as an unstyled row that no alarm branch counts.
    """
    emitted = _severities_the_model_emits()
    known = _known_severities()
    assert emitted, "parsed no severities out of the model — has the CASE shape changed?"
    assert emitted <= known, (
        f"srv_system_health can emit {sorted(emitted - known)}, which "
        f"ci/check_health_signals.py does not know about")


def test_the_data_quality_signal_distinguishes_warn_from_fail():
    """🚨 THE CENSUS FINDING THIS FILE EXISTS FOR.

    The block read `case when is_passing then 'ok' else 'error' end`, and `is_passing` is
    `status in ('pass','success')` — so a dbt test with `severity='warn'` that returned rows was
    shown on the status board as an ERROR. Measured on 2026-09-12: FOUR signals were reading
    error when they were warnings, including assert_line_scores_reconcile_to_the_final_score at
    53 rows, which warns on nearly every scores run.

    A warn is non-failing BY CONSTRUCTION — dbt was told not to fail the build on it. Calling it
    an error is the same defect as not reading it at all: the reader cannot tell two things apart.
    """
    sql = MODEL.read_text(encoding="utf-8")
    block = re.search(r"tests as \((.*?)\n\),", sql, re.S)
    assert block, "the data_quality block moved or changed shape"
    body = block.group(1)

    assert "'warn'" in body, (
        "the data_quality signal no longer emits 'warn'; a warning-severity dbt test would be "
        "shown as an error again, which is what R-701 fixed")
    for status in ("'pass'", "'warn'", "'skipped'"):
        assert status in body, (
            f"status {status} is not named explicitly, so it falls into the else branch and is "
            f"reported as an error — a test that did not run is not a test that failed")


def test_the_dq_fact_still_carries_the_raw_status():
    """The mapping above reads `status`, not `is_passing`. If the fact stopped carrying the raw
    status this would silently fall back to the two-way behaviour."""
    sql = DQ_FACT.read_text(encoding="utf-8")
    assert re.search(r"^\s*status,", sql, re.M), (
        "fct_dq_test_result no longer exposes `status`; srv_system_health's three-way severity "
        "depends on it")


def test_every_declared_signal_type_can_escalate_in_the_fixture():
    """ci/check_health_signals.py FAILS a declared signal that emits rows and never reaches warn
    or error — so a new signal needs a fixture row that trips it, or CI goes red.

    Narrow on purpose: this asserts the market_integrity counter R-701 added has its trigger,
    because that signal reads `ok` on healthy data and would otherwise never exercise its alarm.
    """
    sql = MODEL.read_text(encoding="utf-8")
    declared = set(re.findall(r"'([a-z_]+)'\s+as\s+signal_type", sql))
    assert "market_integrity" in declared, (
        "the market_integrity signal is gone; nothing counts betting lines whose game the "
        "schedule does not contain, which is the absence A109's inner join created")

    fixtures = FIXTURES.read_text(encoding="utf-8")
    assert '"id": 9099' in fixtures, (
        "the orphan betting line fixture is gone, so market_integrity can only ever read `ok` "
        "in CI and its alarm branch is never exercised")
