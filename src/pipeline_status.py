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

# The site is refreshed by cfbd_scores_refresh's publish and nothing else. The other DAGs'
# publishes matter for the warehouse and the weekly marts; they do not make the site current.
SITE_PUBLISH = ("cfbd_scores_refresh", "publish_to_serving")
GATED = (("cfbd_scores_refresh", "publish_to_serving"),
         ("cfbd_lines_snapshot", "publish_distributions"),
         ("cfbd_pregame_refresh", "publish_to_serving"))

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
    with _connect(os.getenv("CFDB_AIRFLOW_DB", "airflow")) as conn, conn.cursor() as cur:
        for dag, task in GATED:
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


def render(rows, failing):
    out = []
    for row in rows:
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
    out.append("")
    out.append(f"  SITE STALE: {'YES' if stale else 'NO'}  "
               f"— last published {_fmt(minutes)}, {why}")
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
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
