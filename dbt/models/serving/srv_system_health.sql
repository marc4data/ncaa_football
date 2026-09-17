{{ config(tags=['postgres_only']) }}
-- Postgres-only. This model's source is cfdb's own telemetry, written directly to Postgres
-- by src/*.py rather than landed as a CFBD response, so it has no Databricks equivalent and
-- the analytics build excludes it by tag. Operational history belongs where the operations
-- are; the analytics warehouse has no use for dbt test outcomes.
-- System Overview page: one row per health signal, unioned across four sources.
--
-- A union rather than four views because the page asks one question — is anything wrong —
-- and answering it from four tables would put the judgement in the app. `severity` is
-- assigned here so the page sorts by it without knowing what any of the signals mean.
--
-- Airflow run history is deliberately absent: nothing outside Airflow should read Airflow's
-- metadata database, and task outcomes are visible in its own UI.
--
-- 🚨 A162: THAT PARAGRAPH USED TO END "and in the failure alerts", AND THAT HALF WAS FALSE.
-- On 2026-09-16 `cfbd_midweek_results.dbt_run` failed at 13:56Z and the alert could not leave
-- the host — "SMTP is blocked outbound here … NOTHING LEFT THIS HOST", with ALERT_WEBHOOK_URL
-- unset. **The first human to learn of it was Marc, from a review, roughly twenty hours later**,
-- and the five rounds that followed — a wedged warehouse, a 95x regression, a working day
-- blocked — all rested on that silence. Detection worked; notification did not (§6).
--
-- ✅ SO THE `pipeline` SIGNAL BELOW EXISTS, AND IT DOES NOT BREAK THE BOUNDARY ABOVE. It reads
-- `ops.pipeline_heartbeat` — **cfdb's own telemetry, written by this project's own code**,
-- which is exactly what the first paragraph of this file says this model is made of. Airflow's
-- metadata database is still untouched.
--
-- ⚠️ AND ITS LIMIT IS STATED ON THE PAGE, NOT ONLY HERE: **a page is PULL, NOT PUSH.** It
-- shortens how long before someone who looks finds out. It does not wake anybody, and it is
-- not a substitute for ALERT_WEBHOOK_URL.
with freshness as (
    select
        'freshness'                                        as signal_type,
        endpoint                                           as subject,
        case when lost_its_data then 'error'
             when hours_since_last_success > 168 then 'warn'
             else 'ok' end                                 as severity,
        case when lost_its_data
             then 'Endpoint used to return rows and its latest response is empty'
             else 'Last loaded ' || cast(round(hours_since_last_success) as {{ dbt.type_string() }})
                  || ' hours ago' end                      as detail,
        last_success_at                                    as observed_at
    from {{ ref('mart_data_freshness') }}
),
tests as (
    select
        'data_quality'                                     as signal_type,
        test_name                                          as subject,
        -- 🚨 THREE OUTCOMES, NOT TWO. R-701's census.
        --
        -- This read `case when is_passing then 'ok' else 'error' end`, and `is_passing` is
        -- `status in ('pass','success')` — so a dbt test with `severity='warn'` that returned rows
        -- was rendered on the status board as an ERROR. Measured: 66 such rows, including
        -- `assert_line_scores_reconcile_to_the_final_score`, which warns on nearly every scores
        -- run and was doing so again today with 53 rows.
        --
        -- ⚠️ A `warn` IS NOT A FAILURE BY CONSTRUCTION — dbt was told not to fail the build on it,
        -- so calling it an error on the board is the same class of defect R-412 was: the signal
        -- reaches a reader that cannot tell two things apart. `KNOWN_SEVERITIES` in
        -- ci/check_health_signals.py has carried a `warn` level all along and this signal never
        -- emitted one.
        --
        -- ⚠️ AND `skipped` IS NEITHER. A test that did not run has published no result, which is
        -- what 'unknown' means here — the same reading the quota signal gives an absent threshold.
        case when status in ('pass', 'success') then 'ok'
             when status = 'warn'              then 'warn'
             when status = 'skipped'           then 'unknown'
             else 'error' end                              as severity,
        case when status in ('pass', 'success') then 'Passing'
             when status = 'skipped'           then 'Did not run in the last invocation'
             else cast(failures as {{ dbt.type_string() }}) || ' row(s)'
                  || case when status = 'warn' then ' (warning only)' else ' failing' end
             end                                           as detail,
        generated_at                                       as observed_at
    from {{ ref('fct_dq_test_result') }}
    -- Latest invocation only. History is what the fact is for; the page is a status board.
    where recency_rank = 1
),
quota as (
    select
        'quota'                                            as signal_type,
        resource                                           as subject,
        case when pct_used is null then 'unknown'
             when pct_used > 90 then 'error'
             when pct_used > 70 then 'warn'
             else 'ok' end                                 as severity,
        case when pct_used is null
             -- Databricks publishes no threshold, so "unknown" is the honest severity and
             -- the detail says why rather than implying the number is missing by accident.
             then 'No published limit; ' || cast(used_value as {{ dbt.type_string() }})
                  || ' ' || unit || ' consumed'
             else cast(pct_used as {{ dbt.type_string() }}) || '% of '
                  || cast(limit_value as {{ dbt.type_string() }}) || ' ' || unit end as detail,
        observed_at
    from {{ ref('fct_api_usage') }}
    where observed_at = (select max(observed_at) from {{ ref('fct_api_usage') }} f2
                         where f2.resource = {{ ref('fct_api_usage') }}.resource)
),
documentation as (
    select
        'documentation'                                    as signal_type,
        layer                                              as subject,
        case when min(case when is_documented then 1 else 0 end) = 1 then 'ok'
             else 'warn' end                               as severity,
        cast(sum(case when is_documented then 1 else 0 end) as {{ dbt.type_string() }}) || ' of '
            || cast(count(*) as {{ dbt.type_string() }}) || ' columns documented' as detail,
        cast(null as {{ type_timestamp_tz() }})            as observed_at
    from {{ ref('dim_field_metadata') }}
    group by layer
),

-- Deploy drift. Added after production spent a day building a dbt project with 39 models
-- while development had 56 — no error and no alert, because a pinned tree that requires a
-- person to advance it is a tree that will be stale again. Latest observation only; the
-- history is in the staging model.
deployment as (
    select
        'deployment'                                       as signal_type,
        'airflow deploy tree'                              as subject,
        severity,
        detail,
        observed_at
    from {{ ref('fct_deploy_status') }}
    where recency_rank = 1
),

-- 🚨 BETTING LINES FOR GAMES THE SCHEDULE DOES NOT CONTAIN. R-701.
--
-- A109 made srv_odds_board's join to fct_game an INNER join, because a board line with no teams
-- on either side is unrenderable and it had stopped the scores publish for nineteen and a half
-- hours. That fix was right AND IT CONVERTED A LOUD FAILURE INTO A SILENT ABSENCE: before, a
-- withdrawn fixture produced a visibly broken row and a red test; now it produces no row at all
-- and a green suite. Nothing in dbt/tests/ counts what that join removes —
-- `assert_every_serving_row_names_its_team` can only see the rows that are there.
--
-- ⚠️ A NUMBER SOMEBODY READS, NOT A GUARD THAT FAILS THE BUILD. The cause is CFBD withdrawing a
-- game it had already published — measured on 401866625, Campbell vs Western Carolina, where 82 of
-- 93 landed week-1 responses carry the game and the newest does not. That is not ours to fix and
-- it must not stop a publish a second time, so this is `warn` at worst and never `error`.
--
-- ⚠️ AC-G.32: ZERO IS A REAL ANSWER. This block always emits exactly one row, so the count renders
-- as `0` rather than vanishing when it is fine. A health metric that disappears when healthy is
-- the same defect one level up.
-- ── A162: HAS THE PIPELINE STOPPED PUBLISHING? ─────────────────────────────────────────────
--
-- 🚨 A STALE HEARTBEAT IS A STOPPED PUBLISH, AND THAT IS TRUE OF THE WIRING AS IT IS TODAY —
-- verified in the DAGs rather than assumed: both `weekly_refresh_dag.py` and
-- `scores_refresh_dag.py` end `... >> dbt_test >> publish >> beat`. **The beat is downstream of
-- the publish**, so it cannot advance while the publish is failing.
--
-- ⚠️ THE CHARTER'S §2.3 STILL SAYS "heartbeat is not downstream of dbt_test, so the DAG kept
-- beating throughout". That described the wiring of 2026-09-11 and no longer describes the
-- code; the chain above is what is in the repository now. **Said here because a stale rule and
-- a live model disagreeing is how the next reader gets it wrong.**
--
-- 📊 THE BUDGET AND THE LATEST BEAT BOTH COME FROM `fct_pipeline_heartbeat`, WHICH IS WHERE
-- THE GRAIN CHANGE BELONGS (ci/check_layering.py rule 3: serving reads marts, never sources).
-- That model carries the note on why the budgets are restated from `ci/check_heartbeats.py`
-- and which test holds the two in step.
pipeline as (
    select
        'pipeline'                                         as signal_type,
        heartbeat_name                                     as subject,
        case when extract(epoch from (now() - last_beat)) > budget_seconds then 'error'
             when extract(epoch from (now() - last_beat)) > budget_seconds * 0.75 then 'warn'
             else 'ok' end                                 as severity,
        case when extract(epoch from (now() - last_beat)) > budget_seconds
             then 'PUBLISH HAS STOPPED — last completed '
                  || cast(round(extract(epoch from (now() - last_beat)) / 3600) as {{ dbt.type_string() }})
                  || ' hours ago, past its '
                  || cast(round(budget_seconds / 3600.0) as {{ dbt.type_string() }})
                  || ' hour budget. The beat is downstream of publish_to_serving, so this '
                  || 'cadence is not reaching serving.'
             else 'published '
                  || cast(round(extract(epoch from (now() - last_beat)) / 3600) as {{ dbt.type_string() }})
                  || ' hours ago; budget '
                  || cast(round(budget_seconds / 3600.0) as {{ dbt.type_string() }})
                  || ' hours' end                          as detail,
        last_beat                                          as observed_at
    from (
        select heartbeat_name, last_beat_at as last_beat, budget_seconds
        from {{ ref('fct_pipeline_heartbeat') }}
    ) beats
    -- A cadence nobody has budgeted is not silently rated 'ok'; it is left out, and the
    -- budget guard is what makes its absence a test failure rather than a quiet gap.
    where budget_seconds is not null
),

orphan_market as (
    select
        'market_integrity'                                 as signal_type,
        'lines with no scheduled game'                     as subject,
        case when orphans = 0 then 'ok' else 'warn' end    as severity,
        cast(orphans as {{ dbt.type_string() }})
            || ' betting line(s) name a game_id absent from fct_game'
            || case when orphans = 0 then ''
                    else ' — withdrawn upstream; srv_odds_board omits them' end
                                                           as detail,
        cast(null as {{ type_timestamp_tz() }})            as observed_at
    from (
        select count(*) as orphans
        from {{ ref('fct_betting_line') }} b
        where not exists (
            select 1 from {{ ref('fct_game') }} g where g.game_id = b.game_id
        )
    ) counted
)

select
    {{ surrogate_key(['signal_type', 'subject']) }} as system_health_sk,
    signal_type, subject, severity, detail, observed_at,
    ao_src.as_of_ts
from (
    select * from freshness
    union all select * from tests
    union all select * from quota
    union all select * from documentation
    union all select * from deployment
    union all select * from orphan_market
    union all select * from pipeline
) combined
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'ops') ao_src
