"""Tests for the warehouse-time meter.

The meter exists because Databricks Free Edition's quota is undisclosed and its failure
mode is a shutdown, so the only warning available is our own trend. Two properties matter:
it must record a failed run (which still burned warehouse time, usually more), and it must
never break the pipeline it is measuring.
"""
import json

import pytest

from src import warehouse_usage


def test_a_successful_run_is_recorded(tmp_path):
    log = tmp_path / "usage.jsonl"
    with warehouse_usage.measured("dbt_run", path=log, models=160):
        pass

    entry = json.loads(log.read_text().strip())
    assert entry["operation"] == "dbt_run"
    assert entry["outcome"] == "success"
    assert entry["models"] == 160
    assert entry["elapsed_seconds"] >= 0


def test_a_failed_run_is_recorded_and_the_error_still_propagates(tmp_path):
    """A failure burned warehouse time too — often more, having paid the cold start first.

    Recording only successes would understate consumption in exactly the situation where
    consumption matters, and swallowing the error would hide the failure.
    """
    log = tmp_path / "usage.jsonl"
    with pytest.raises(RuntimeError):
        with warehouse_usage.measured("dbt_run", path=log):
            raise RuntimeError("warehouse died mid-build")

    entry = json.loads(log.read_text().strip())
    assert entry["outcome"] == "failed"


def test_an_unwritable_log_does_not_break_the_work(tmp_path):
    """Instrumentation must never be the thing that fails the pipeline."""
    unwritable = tmp_path / "file.txt"
    unwritable.write_text("not a directory")
    ran = []
    with warehouse_usage.measured("dbt_run", path=unwritable / "nested" / "usage.jsonl"):
        ran.append(True)
    assert ran == [True]


def test_summary_totals_across_runs(tmp_path):
    log = tmp_path / "usage.jsonl"
    for _ in range(3):
        with warehouse_usage.measured("dbt_run", path=log):
            pass
    with pytest.raises(ValueError):
        with warehouse_usage.measured("dbt_run", path=log):
            raise ValueError("boom")

    result = warehouse_usage.summary(log)
    assert result["runs"] == 4
    assert result["failed_runs"] == 1
    assert result["total_seconds"] >= 0
    assert result["first_at"] and result["last_at"]


def test_summary_survives_a_malformed_line(tmp_path):
    """One truncated write must not blind the whole meter."""
    log = tmp_path / "usage.jsonl"
    log.write_text('{"elapsed_seconds": 10, "at": "x", "outcome": "success"}\n'
                   '{"elapsed_seconds": tru\n'
                   '{"elapsed_seconds": 5, "at": "y", "outcome": "success"}\n')
    result = warehouse_usage.summary(log)
    assert result["runs"] == 2
    assert result["total_seconds"] == 15.0


def test_summary_with_no_log_is_zero_not_an_error(tmp_path):
    assert warehouse_usage.summary(tmp_path / "missing.jsonl")["runs"] == 0
