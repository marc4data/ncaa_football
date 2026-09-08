"""`python -m src.pipeline_status` must not repeat the false alarm it was built to end.

R-422. Switch run #51 reported two failed publishes while the site was publishing fine,
because two DAGs own a task called `publish_to_serving` and only one of them refreshes the
site. This command exists to answer the one question that email could not: is the site stale?

THE TEST THAT MATTERS IS THE GATED ONE. The first draft called the site stale after three
hours of elapsed time. cfbd_scores_refresh is cadence-gated and skips deliberately when no
games need refreshing, so on a quiet Tuesday that printed YES while everything was working --
the same false-alarm class that trained everyone to ignore the alerts, arriving inside the
tool meant to replace them. Staleness now asks whether the last attempt that was ALLOWED to
run actually published.
"""
from datetime import datetime, timedelta, timezone

from src.pipeline_status import render

NOW = datetime.now(timezone.utc)


def _row(dag, task, last_success_min, last_state, last_real_state):
    return {"dag": dag, "task": task,
            "last_success": NOW - timedelta(minutes=last_success_min) if last_success_min else None,
            "last_state": last_state, "last_real_state": last_real_state,
            "last_run": NOW}


def _rows(site_state, site_real, minutes=250):
    return [_row("cfbd_scores_refresh", "publish_to_serving", minutes, site_state, site_real),
            _row("cfbd_lines_snapshot", "publish_distributions", 10, "success", "success"),
            _row("cfbd_pregame_refresh", "publish_to_serving", 60 * 24 * 7, "failed", "failed")]


def test_a_gated_skip_is_not_stale_however_long_ago_it_published():
    """The false alarm this command must never produce."""
    text, stale = render(_rows("skipped", "success", minutes=600), [])
    assert stale is False, text
    assert "SITE STALE: NO" in text
    assert "gated" in text


def test_a_failed_publish_is_stale_however_recent():
    text, stale = render(_rows("failed", "failed", minutes=5), [])
    assert stale is True, text
    assert "SITE STALE: YES" in text


def test_a_red_weekly_publish_does_not_make_the_site_stale():
    """R-417's actual defect: two DAGs, one task name, very different consequences."""
    text, stale = render(_rows("success", "success", minutes=30), [])
    assert stale is False, text
    assert "RED cfbd_pregame_refresh" in text, "the weekly publish should still show as red"


def test_failing_tests_are_named_with_row_counts():
    text, _ = render(_rows("success", "success", 30),
                     [("assert_thing", 744, NOW), ("assert_other", 221, NOW)])
    assert "assert_thing (744 rows)" in text
    assert "assert_other (221 rows)" in text


def test_it_stays_short_enough_to_read():
    text, _ = render(_rows("success", "success", 30),
                     [(f"assert_{i}", i, NOW) for i in range(9)])
    assert len(text.splitlines()) <= 10, f"{len(text.splitlines())} lines:\n{text}"
