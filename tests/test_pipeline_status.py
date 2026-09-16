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

from src.pipeline_status import heavy_verdict, render

NOW = datetime.now(timezone.utc)


def _row(dag, task, last_success_min, last_state, last_real_state, last_run_min=None):
    """⚠️ `last_run` DEFAULTS TO THE SUCCESS AGE RATHER THAN TO NOW — A139.

    `heavy_verdict` picks the NEWEST weekly attempt, and a fixture where every row ran "now"
    makes that choice a tie broken by list order. A fixture whose defaults hide the thing under
    test is R-744's family, so the timestamps here are distinct on purpose.
    """
    minutes = last_run_min if last_run_min is not None else (last_success_min or 0)
    return {"dag": dag, "task": task,
            "last_success": NOW - timedelta(minutes=last_success_min) if last_success_min else None,
            "last_state": last_state, "last_real_state": last_real_state,
            "last_run": NOW - timedelta(minutes=minutes)}


def _rows(site_state, site_real, minutes=250):
    return [_row("cfbd_scores_refresh", "publish_to_serving", minutes, site_state, site_real),
            _row("cfbd_lines_snapshot", "publish_distributions", 10, "success", "success"),
            _row("cfbd_pregame_refresh", "publish_to_serving", 60 * 24 * 7, "failed", "failed")]


def test_a_gated_skip_is_not_stale_however_long_ago_it_published():
    """The false alarm this command must never produce."""
    text, stale = render(_rows("skipped", "success", minutes=600), [])
    assert stale is False, text
    # ⚠️ A139 SPLIT THE VERDICT IN TWO (cfdb-main-R-919). The claim this test makes is unchanged —
    # a gated skip is not staleness — but the verdict it reads is now named `hot`, because
    # collapsing the hot and weekly publishes into one word is what let this command print NO
    # while a page's own content sat 10,466 rows behind the warehouse.
    assert "hot: NO" in text
    assert "gated" in text


def test_a_failed_publish_is_stale_however_recent():
    text, stale = render(_rows("failed", "failed", minutes=5), [])
    assert stale is True, text
    assert "hot: YES" in text


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
    """⚠️ THE BUDGET WENT FROM 10 TO 11 AND THE EXTRA LINE IS THE POINT OF cfdb-main-R-919, not
    slack: the summary is two lines because collapsing the hot and weekly publishes into one
    verdict is what created the defect. The body is still three rows — the other two weekly
    publishes are collected for the verdict and deliberately not printed.
    """
    text, _ = render(_rows("success", "success", 30),
                     [(f"assert_{i}", i, NOW) for i in range(9)])
    assert len(text.splitlines()) <= 11, f"{len(text.splitlines())} lines:\n{text}"


# --- A139: the weekly publish gets its own verdict (cfdb-main-R-919) ----------------------

def _with_weekly(site_state, site_real, pregame, results=None, midweek=None):
    """The three body rows plus the other two weekly publishes `collect` now fetches."""
    rows = [_row("cfbd_scores_refresh", "publish_to_serving", 30, site_state, site_real),
            _row("cfbd_lines_snapshot", "publish_distributions", 10, "success", "success"),
            _row("cfbd_pregame_refresh", "publish_to_serving", *pregame)]
    if results:
        rows.append(_row("cfbd_results_refresh", "publish_to_serving", *results))
    if midweek:
        rows.append(_row("cfbd_midweek_results", "publish_to_serving", *midweek))
    return rows


def test_the_weekly_publish_gets_its_own_verdict_and_it_is_not_the_site_verdict():
    """🚨 cfdb-main-R-919, AND IT IS THE COMPLEMENT OF THE R-417 TEST ABOVE, NOT ITS CONTRADICTION.

    R-417 was right that a red weekly publish does not make the SITE stale: the two-hourly
    publish is what refreshes the pages a reader loads most. ⚠️ But it ships `hot=True` — 25
    views, 597 MB — and the OTHER NINE, 1,004 MB and **62.7% of published serving**, go only on a
    weekly DAG's full publish. One of them is `srv_game_team_leader_usage`, the Matchup card
    dots.

    📊 A137 IS THE PROOF: during that outage this command printed `SITE STALE: NO` while
    `srv_game_team_leader_usage` sat **10,466 rows** behind the warehouse and `srv_player_play`
    sat **33,921** behind.

    ✅ SO BOTH VERDICTS APPEAR AND NEITHER IS ALLOWED TO SPEAK FOR THE OTHER.
    """
    text, stale = render(_with_weekly("success", "success", (60 * 24 * 7, "failed", "failed")), [])
    assert stale is False, "the hot half is fine and must still say so"
    assert "hot: NO" in text
    assert "weekly: YES" in text, (
        "the weekly half is red and the summary said nothing about it — that is R-919")
    assert "cfbd_pregame_refresh did not publish" in text, "and it names which one"
    assert "63% of serving" in text, "and what it costs, so the line is actionable"


def test_the_newest_weekly_attempt_decides_rather_than_a_named_dag():
    """⚠️ THREE DAGs RUN THE FULL PUBLISH — `weekly_refresh_dag.py` builds all three and calls
    `publish_all()` with no `hot` flag. Any of them landing makes the heavy half current, so a
    verdict keyed to one named DAG would read RED for six days out of seven.

    Here `cfbd_pregame_refresh` failed a week ago and `cfbd_results_refresh` published an hour
    ago: the heavy half is current and the line must say so.
    """
    rows = _with_weekly("success", "success",
                        (60 * 24 * 7, "failed", "failed", 60 * 24 * 7),
                        results=(60, "success", "success", 60))
    stale, last_ok, culprit = heavy_verdict(rows)
    assert stale is False, "the newest attempt succeeded, so the heavy half is current"
    assert culprit is None
    text, _ = render(rows, [])
    assert "weekly: NO" in text


def test_a_weekly_publish_with_no_run_on_record_is_unknown_rather_than_fine():
    """🚨 AC-G.11 IN A STATUS LINE: "nothing has ever run" and "everything is current" are
    different facts and a tool that prints NO for both is the class this command exists to end.
    """
    rows = [_row("cfbd_scores_refresh", "publish_to_serving", 30, "success", "success"),
            _row("cfbd_lines_snapshot", "publish_distributions", 10, "success", "success")]
    stale, last_ok, culprit = heavy_verdict(rows)
    assert stale is None and last_ok is None and culprit is None
    text, _ = render(rows, [])
    assert "weekly: UNKNOWN" in text
    assert "no run on record" in text


def test_the_heavy_verdict_is_not_an_elapsed_time_threshold():
    """🚨 R-422's FALSE ALARM, ONE CADENCE OVER. A weekly publish is "late" six days out of seven;
    a tool that called that stale would reproduce exactly the noise that trained everyone to
    ignore the alerts, which is the thing this module was built to end.

    ✅ The rule is the same one the hot half uses: did the LAST ATTEMPT publish.
    """
    six_days = 60 * 24 * 6
    rows = _with_weekly("success", "success", (six_days, "success", "success"))
    stale, last_ok, _culprit = heavy_verdict(rows)
    assert stale is False, "six days old and successful is a weekly cadence, not staleness"
    assert last_ok > 60 * 24 * 5, "and the age is still reported honestly"
