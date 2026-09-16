"""One command that answers the only question that matters: is the site stale?

    python -m src.pipeline_status

WHY THIS EXISTS (R-422). Marc learned the pipeline's state from an alert email, hours late,
and the email could not answer the question he actually had. Switch run #51 named two failed
publishes while the site was publishing fine, because two DAGs own tasks called
`publish_to_serving` with very different consequences: cfbd_scores_refresh publishes the site
every two hours, and cfbd_pregame_refresh publishes on a weekly cadence. One being red says
nothing about whether anyone can see fresh data.

So this does not report DAG health. It reports SITE STALENESS, and treats everything else as
supporting detail.

A NEW MODULE RATHER THAN EXTENDING deploy_status.py, deliberately. deploy_status answers
"which commit is deployed" -- a question about the worktree, read from git. This answers "is
what the site shows current" -- a question about publish recency, read from Airflow and the
warehouse. Same operator, different question, and merging them would make a module that has
to be told which one you meant.

Read-only. No new dependency, no service, no dashboard.
"""
import os
import sys
from datetime import datetime, timezone

# 🚨 "THE SITE IS REFRESHED BY cfbd_scores_refresh's PUBLISH AND NOTHING ELSE" IS WHAT THIS
# COMMENT USED TO SAY, AND cfdb-main-R-919 IS THAT SENTENCE BEING TOO STRONG.
#
# The two-hourly publish ships `hot=True` — the fast-moving views and nothing else. The other
# nine ship ONLY on a weekly DAG's full publish, and they are the bigger half:
#
# 📊 MEASURED IN THE WAREHOUSE 2026-09-15, re-measured rather than carried from A137:
#
#     published serving      34 tables   1,601 MB
#     HOT (two-hourly)       25 tables     597 MB   37.3%
#     HEAVY (weekly only)     9 tables   1,004 MB   62.7%
#
# ⚠️ AND ONE OF THEM IS A PAGE'S CONTENT, NOT A WAREHOUSE CONVENIENCE:
# `srv_game_team_leader_usage` is the Matchup card dots. During A137's outage it sat 10,466
# rows behind the warehouse while this command printed `SITE STALE: NO`.
#
# 🚨 BUT WHETHER A READER WOULD NOTICE WAS MEASURED, NOT ASSUMED, AND THE ANSWER IS NO — WHICH
# IS WHY THIS LINE REPORTS SCOPE RATHER THAN VISIBILITY.
#
# `matchup.py`'s `_card_dots` prints "No game-by-game usage held for this player." when the
# relation holds nothing for someone, so a stale table IS visible rather than silent. 📊 But
# that sentence is ALREADY on **6,715 of 21,087 card players in 2026 — 31.8%**, 32-40% per week,
# because 2026 usage coverage is partial (A113, R-718). ⚠️ So a reader cannot tell "the weekly
# publish is behind" from "the feed has not landed for this player", and the two look identical
# on the card.
#
# ✅ THE SUMMARY THEREFORE SAYS WHAT IS TRUE — nine views, 63% of serving, last published when —
# and does NOT claim the reader will see it. A line that promised visibility would be making
# the same over-claim one level down.
#
# ✅ SO THE VERDICT IS TWO VERDICTS. The command was never wrong about what it measured — its
# RED line did name the weekly task — but the SUMMARY collapsed them, and a summary line is the
# part a person reads at 7am.
SITE_PUBLISH = ("cfbd_scores_refresh", "publish_to_serving")

# The three DAGs that run the FULL publish. `weekly_refresh_dag.py` builds all three and calls
# `publish_all()` with no `hot` flag; `scores_refresh_dag.py` calls `publish_all(hot=True)`.
# Any of them landing makes the heavy half current, so the question is about the newest attempt
# across the set rather than about one named DAG.
WEEKLY_PUBLISH = (("cfbd_pregame_refresh", "publish_to_serving"),
                  ("cfbd_results_refresh", "publish_to_serving"),
                  ("cfbd_midweek_results", "publish_to_serving"))

# ⚠️ THE BODY STAYS THREE LINES. The other two weekly publishes are collected for the summary
# and not printed: `test_it_stays_short_enough_to_read` is a real constraint and the heavy
# verdict names whichever task failed, so nothing is hidden by leaving them out of the list.
GATED = (("cfbd_scores_refresh", "publish_to_serving"),
         ("cfbd_lines_snapshot", "publish_distributions"),
         ("cfbd_pregame_refresh", "publish_to_serving"))

# What the heavy half costs if it is behind, for the summary line. Kept beside the list it
# describes so the two cannot drift apart silently.
HEAVY_VIEWS = 9
HEAVY_SHARE = "63% of serving"

# ⚠️ STALENESS IS NOT ELAPSED TIME, AND THE FIRST DRAFT OF THIS GOT IT WRONG.
#
# It flagged "SITE STALE: YES" on a quiet Tuesday because the last publish was 4.1 hours old.
# But cfbd_scores_refresh is CADENCE-GATED: when no games need refreshing it skips deliberately,
# and a skip is the pipeline working, not failing. An elapsed-time threshold turns every quiet
# midweek into a false alarm -- which is the exact class of noise that trained everyone to
# ignore the alert emails in the first place, arriving in the tool built to replace them.
#
# The honest question is not "how long since a publish" but "did the last attempt that was
# ALLOWED to publish actually publish". A gated skip is not an attempt.
GATE_SKIPPED = ("skipped", "upstream_skipped", "removed", None)


def _connect(database):
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("CFDB_WAREHOUSE_HOST", "127.0.0.1"),
        port=int(os.getenv("CFDB_WAREHOUSE_PORT", "15433")),
        dbname=database,
        user=os.getenv("PG_USER", "cfdb"),
        password=os.getenv("PG_PASSWORD", "cfdb"),
        connect_timeout=15)


def _age(then):
    if then is None:
        return None
    return (datetime.now(timezone.utc) - then).total_seconds() / 60.0


def _fmt(minutes):
    if minutes is None:
        return "never"
    if minutes < 90:
        return f"{minutes:.0f}m ago"
    if minutes < 60 * 48:
        return f"{minutes / 60:.1f}h ago"
    return f"{minutes / 1440:.1f}d ago"


def collect():
    """Everything the report needs, as plain data so the formatting stays testable."""
    rows, failing = [], []
    # GATED first so the body keeps its order; the weekly pair is appended for the summary.
    wanted = list(GATED) + [pair for pair in WEEKLY_PUBLISH if pair not in GATED]
    with _connect(os.getenv("CFDB_AIRFLOW_DB", "airflow")) as conn, conn.cursor() as cur:
        for dag, task in wanted:
            cur.execute("""
                select max(end_date) filter (where state = 'success')                as last_ok,
                       (array_agg(state order by end_date desc nulls last))[1]        as last_state,
                       (array_agg(state order by end_date desc nulls last)
                          filter (where state not in ('skipped','upstream_skipped','removed'))
                       )[1]                                                           as last_real_state,
                       max(end_date)                                                  as last_any
                from task_instance where dag_id = %s and task_id = %s""", (dag, task))
            last_ok, last_state, last_real, last_any = cur.fetchone()
            rows.append({"dag": dag, "task": task, "last_success": last_ok,
                         "last_state": last_state, "last_real_state": last_real,
                         "last_run": last_any})
    with _connect(os.getenv("PG_DB", "cfdb")) as conn, conn.cursor() as cur:
        # Only what is failing NOW: rank each test's results and keep the newest.
        cur.execute("""
            select split_part(unique_id, '.', 3), failures, generated_at
            from (select unique_id, failures, generated_at, status,
                         row_number() over (partition by unique_id
                                            order by generated_at desc) as recency
                  from raw.raw_dbt_test_result) ranked
            where recency = 1 and status in ('fail', 'error')
            order by failures desc nulls last""")
        failing = cur.fetchall()
    return rows, failing


def heavy_verdict(rows):
    """`(stale, last_ok_minutes, culprit)` for the nine views that ship only on the weekly run.

    🚨 SAME RULE AS THE HOT HALF, DELIBERATELY: stale iff the LAST ATTEMPT that was allowed to
    run did not publish. An elapsed-time threshold here would reintroduce exactly the false
    alarm R-422 was built to end, one cadence over — a weekly publish is "late" for six days out
    of seven and that is the pipeline working.

    ⚠️ IT READS AIRFLOW, WHICH IS ITS DOCUMENTED BASIS AND ALSO ITS LIMIT: a publish run by hand
    outside a DAG is invisible here, so the verdict can say YES while the data is current. A137
    is exactly that case — it republished all 34 tables out of band and the failed task instance
    was never cleared. The honest reading is "Airflow has no record of a successful weekly
    publish since", which is what the line says.
    """
    weekly = [row for row in rows
              if (row["dag"], row["task"]) in WEEKLY_PUBLISH and row["last_run"] is not None]
    if not weekly:
        return None, None, None
    newest = max(weekly, key=lambda row: row["last_run"])
    successes = [row["last_success"] for row in weekly if row["last_success"] is not None]
    last_ok = _age(max(successes)) if successes else None
    stale = newest["last_real_state"] != "success"
    return stale, last_ok, (f"{newest['dag']}.{newest['task']}" if stale else None)


def render(rows, failing):
    out = []
    for row in rows:
        if (row["dag"], row["task"]) not in GATED:
            continue
        real = row["last_real_state"]
        marker = {"success": "ok "}.get(real, "RED") if real else "-- "
        gated = " (gated)" if row["last_state"] in GATE_SKIPPED and real == "success" else ""
        out.append(f"  {marker} {row['dag']}.{row['task']:<22} "
                   f"last ok {_fmt(_age(row['last_success']))}{gated}")
    if failing:
        out.append(f"  failing tests ({len(failing)}):")
        for name, count, _ in failing[:3]:
            out.append(f"      {name} ({count} rows)")
        if len(failing) > 3:
            out.append(f"      … and {len(failing) - 3} more")
    else:
        out.append("  failing tests: none")

    site = next(r for r in rows if (r["dag"], r["task"]) == SITE_PUBLISH)
    minutes = _age(site["last_success"])
    # Stale iff the last attempt that was allowed to run did not publish. A gated skip since
    # then is the pipeline deciding there was nothing to do, which leaves the site current.
    stale = site["last_real_state"] != "success"
    why = ("the last attempt did not publish" if stale
           else "gated since, nothing to refresh" if site["last_state"] in GATE_SKIPPED
           else "publishing on cadence")
    # 🚨 TWO VERDICTS, NOT ONE — cfdb-main-R-919. Collapsing them is what let this command print
    # `SITE STALE: NO` while a page's own content sat 10,466 rows behind the warehouse.
    heavy_stale, heavy_ok, culprit = heavy_verdict(rows)
    out.append("")
    out.append(f"  SITE STALE — hot: {'YES' if stale else 'NO'} "
               f"(last published {_fmt(minutes)}, {why})")
    if heavy_stale is None:
        out.append(f"               weekly: UNKNOWN "
                   f"({HEAVY_VIEWS} views, {HEAVY_SHARE} — no run on record)")
    else:
        # The task is always `publish_to_serving`; the DAG is the part that identifies it, and
        # the summary has to stay one glance long.
        detail = (f"last ok {_fmt(heavy_ok)}, {culprit.split('.')[0]} did not publish"
                  if heavy_stale else f"last published {_fmt(heavy_ok)}")
        out.append(f"               weekly: {'YES' if heavy_stale else 'NO'} "
                   f"({HEAVY_VIEWS} views, {HEAVY_SHARE} — {detail})")
    return "\n".join(out), stale


def main():
    try:
        rows, failing = collect()
    except Exception as exc:                                          # noqa: BLE001
        # A status command that cannot reach the warehouse must say so, not print "NO".
        print(f"  SITE STALE: UNKNOWN — cannot reach the warehouse: {exc}", file=sys.stderr)
        return 2
    text, stale = render(rows, failing)
    print(text)
    # ⚠️ EITHER HALF BEING STALE IS A NON-ZERO EXIT. `render`'s second value stays the HOT
    # verdict so `test_a_red_weekly_publish_does_not_make_the_site_stale` keeps asserting the
    # thing it was written for — R-417's defect, that two DAGs share a task name with very
    # different consequences. That claim is unchanged; what changed is that the weekly half is
    # no longer silent.
    heavy_stale, _ok, _culprit = heavy_verdict(rows)
    return 1 if (stale or heavy_stale) else 0


if __name__ == "__main__":
    sys.exit(main())
