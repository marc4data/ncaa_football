{#-
  🚨 A290 (cfdb-main-R-5012). A DEPLOY-TREE OBSERVATION STOPS BEING EVIDENCE WHEN IT GETS OLD.

  `srv_system_health` published `severity = ok` for SIXTY-SEVEN DAYS from one observation
  taken 2026-08-22, naming a commit 60+ commits behind `main`. The model whose entire job is
  to catch "production builds 39 models while development has 56" was reporting from August.
  R-843's exact shape: a guard never seen red is a claim.

  ⚠️ AND THE CAUSE WAS THE ABSENCE OF A WRITER, NOT A BROKEN ONE. `git log -S` across every
  ref finds no committed caller of `src/deploy_status.py`, ever. So the freshness bound is not
  defence in depth — it is the only thing between a dead writer and a green board.

  ⚠️ ONE HOME, TWO CALL SITES (R-574). The severity and the detail have to agree about what
  "stale" means, and two copies of one threshold is how they come to disagree. Both read
  `var('deploy_status_stale_days')`.

  ⚠️ EVALUATED WHERE IT IS READ, NOT WHERE IT IS WRITTEN. The staleness deliberately does NOT
  live in `fct_deploy_status`: that is a TABLE, so a verdict computed there would be exactly
  as stale as the table and would say "fresh" forever if the build stopped — which is the
  failure this is for. `srv_system_health` is also a table, so the verdict is re-evaluated on
  each rebuild; the lag is therefore at most one rebuild, and that is stated rather than
  implied.
-#}

{% macro deploy_observation_is_stale(observed_at) -%}
    (
        {{ observed_at }} is null
        or {{ observed_at }} < {{ dbt.current_timestamp() }}
                               - interval '{{ var("deploy_status_stale_days", 14) }} days'
    )
{%- endmacro %}


{% macro deploy_observation_severity(severity, observed_at) -%}
    case
        when {{ deploy_observation_is_stale(observed_at) }} then 'unknown'
        else {{ severity }}
    end
{%- endmacro %}


{% macro deploy_observation_detail(detail, observed_at) -%}
    case
        when {{ observed_at }} is null
            then 'No deploy-tree observation has ever been recorded'
        when {{ deploy_observation_is_stale(observed_at) }}
            then 'STALE: the newest deploy-tree observation is '
                 || cast(date_part('day', {{ dbt.current_timestamp() }} - {{ observed_at }})
                         as {{ dbt.type_int() }})
                 || ' days old, past the {{ var("deploy_status_stale_days", 14) }}-day '
                 || 'budget, so its verdict is no longer evidence. Last said: '
                 || coalesce({{ detail }}, '(no detail)')
        else {{ detail }}
    end
{%- endmacro %}
