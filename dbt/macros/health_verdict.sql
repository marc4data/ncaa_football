{#-
  🚨 A291 (cfdb-main-R-5043). THE BOARD'S VERDICT IS A SNAPSHOT AND IT DID NOT SAY SO.

  `srv_system_health`'s `pipeline` severity is computed from `now()` against a budget, and
  `srv_system_health` is a TABLE. So the verdict freezes at build time and is published as
  current for as long as the table stands.

  📊 MEASURED 2026-11-02, AND THE GAP IS WORSE THAN A LAG — IT IS A MISMATCH OF TWO ORDERS OF
  MAGNITUDE. `srv_system_health` is rebuilt by ONE task: `weekly_refresh_dag.py`'s catalogue
  step (`--select srv_data_dictionary srv_system_health`). The weekly cadences fire Tuesday,
  Thursday and Sunday — so the board is rebuilt every ~2-3 DAYS, while the `scores_refresh`
  budget it reports on is FIVE HOURS. A verdict about a five-hour cadence can therefore be
  three days old, and on 2026-11-02 the board was publishing
  `scores_refresh · error · "PUBLISH HAS STOPPED - last completed 24 hours ago"` from a
  build taken 2026-11-01 14:00Z. It had beaten 42 minutes earlier.

  🚨 AND THE RELATIVE NUMBER IS THE LIE, NOT ONLY THE SEVERITY. "last completed 24 hours ago"
  read 28 hours after the build means 52 hours, and nothing on the row said which clock the
  24 was measured against. A reader cannot correct a figure whose anchor is not published.

  ⚠️ WHY THIS IS NOT A290's SHAPE, STATED SO THE NEXT ROUND DOES NOT COPY THE WRONG MACRO.
  `deploy_observation.sql` degrades a verdict whose EVIDENCE came from another table, so at
  build time that evidence can already be old and a build-time branch can catch it. Here the
  evidence is the build clock ITSELF: `current_timestamp - current_timestamp` is zero on every
  build, so a build-time staleness branch is structurally incapable of ever firing. It would be
  R-760 exactly — an assertion nothing the code can produce could make true.

  ✅ SO THE VERDICT'S AGE IS PUBLISHED RATHER THAN JUDGED, and the judging happens where `now`
  actually exists: at read time, in the page. That keeps severity assignment in this model
  (which this model's own header requires - "the page sorts by it without knowing what any of
  the signals mean") and puts only the age rendering in the page.

  ⚠️ ONE HOME (R-574), AND THERE IS DELIBERATELY NO THRESHOLD VAR HERE. A threshold would have
  to be read by SQL and by Python to be useful, which is two homes in two languages — the exact
  drift R-574 forbids. The only threshold in this feature is the page's own render-time one,
  stated once in `site/views/system.py`. What this macro owns is the STAMP.

  📋 THE COMPLEMENTARY FIX IS NOT THIS ROUND'S AND IS NAMED RATHER THAN TAKEN: building
  `srv_system_health` on the scores cadence would bound the staleness at two hours instead of
  three days and is the root-cause repair. It is a DAG change with a rebuild cost, so it is
  cfdb-main-R-5047 and not a change made in passing.
-#}

{% macro health_verdict_computed_at() -%}
    {{ dbt.current_timestamp() }}
{%- endmacro %}


{#-
  Anchors a detail string that contains a relative figure to the clock that figure was
  measured against. Appended rather than interpolated so every existing branch keeps its
  wording and only gains the anchor.
-#}
{% macro health_verdict_anchored(detail, computed_at) -%}
    {{ detail }}
    || ' [measured '
    || to_char({{ computed_at }} at time zone 'UTC', 'YYYY-MM-DD HH24:MI')
    || 'Z - this row is a snapshot, not a live reading]'
{%- endmacro %}
