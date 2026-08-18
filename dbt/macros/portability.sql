{#
  Cross-dialect helpers for the non-JSON Postgres-isms in these models.

  Scope discipline: only constructs that genuinely differ between Postgres and Spark get a
  macro. Several others were simply rewritten in portable SQL instead, because a macro that
  wraps something both dialects already accept is indirection without benefit:

    distinct on (k) ... order by k, x desc  ->  row_number() over (partition by k order by x desc)
    count(*) filter (where c)               ->  count(case when c then 1 end)
    a is not distinct from b                ->  a = b or (a is null and b is null)
    x::int                                  ->  cast(x as int)

  Like the JSON macros, Databricks implementations are written against Spark SQL semantics
  and are UNVERIFIED until the M4 target exists.
#}

{# --- Local calendar date from a UTC timestamp --------------------------------------- #}
{% macro to_local_date(ts, tz='America/New_York') -%}
    {{ return(adapter.dispatch('to_local_date', 'cfdb_dbt')(ts, tz)) }}
{%- endmacro %}

{% macro default__to_local_date(ts, tz) -%}
    cast({{ ts }} at time zone '{{ tz }}' as date)
{%- endmacro %}

{% macro databricks__to_local_date(ts, tz) -%}
    to_date(from_utc_timestamp({{ ts }}, '{{ tz }}'))
{%- endmacro %}


{# --- Calendar date in UTC, for date-only values ------------------------------------- #}
{% macro to_utc_date(ts) -%}
    {{ return(adapter.dispatch('to_utc_date', 'cfdb_dbt')(ts)) }}
{%- endmacro %}

{% macro default__to_utc_date(ts) -%}
    cast({{ ts }} at time zone 'UTC' as date)
{%- endmacro %}

{% macro databricks__to_utc_date(ts) -%}
    to_date({{ ts }})
{%- endmacro %}


{# --- Time-of-day, used to detect date-only values ----------------------------------- #}
{% macro utc_time_of_day(ts) -%}
    {{ return(adapter.dispatch('utc_time_of_day', 'cfdb_dbt')(ts)) }}
{%- endmacro %}

{% macro default__utc_time_of_day(ts) -%}
    cast({{ ts }} as time)
{%- endmacro %}

{% macro databricks__utc_time_of_day(ts) -%}
    date_format({{ ts }}, 'HH:mm:ss')
{%- endmacro %}


{# --- Hours between two timestamps --------------------------------------------------- #}
{% macro hours_between(later, earlier) -%}
    {{ return(adapter.dispatch('hours_between', 'cfdb_dbt')(later, earlier)) }}
{%- endmacro %}

{% macro default__hours_between(later, earlier) -%}
    extract(epoch from ({{ later }} - {{ earlier }})) / 3600.0
{%- endmacro %}

{% macro databricks__hours_between(later, earlier) -%}
    (unix_timestamp({{ later }}) - unix_timestamp({{ earlier }})) / 3600.0
{%- endmacro %}


{# --- Timestamp-with-zone type name --------------------------------------------------
  Not interchangeable by accident: Postgres `timestamp` is zone-*less*, so naming the type
  wrongly would silently change what every date conversion in the marts means.
#}
{% macro type_timestamp_tz() -%}
    {{ return(adapter.dispatch('type_timestamp_tz', 'cfdb_dbt')()) }}
{%- endmacro %}

{% macro default__type_timestamp_tz() -%}
    timestamptz
{%- endmacro %}

{% macro databricks__type_timestamp_tz() -%}
    timestamp
{%- endmacro %}


{# --- nth part of a delimited string (1-indexed) --------------------------------------
  Needed because /games/teams ships compound stats as strings: thirdDownEff "4-9",
  totalPenaltiesYards "6-45", possessionTime "31:24".
#}
{% macro split_at(col, delim, index) -%}
    {{ return(adapter.dispatch('split_at', 'cfdb_dbt')(col, delim, index)) }}
{%- endmacro %}

{% macro default__split_at(col, delim, index) -%}
    split_part({{ col }}, '{{ delim }}', {{ index }})
{%- endmacro %}

{% macro databricks__split_at(col, delim, index) -%}
    element_at(split({{ col }}, '\\{{ delim }}'), {{ index }})
{%- endmacro %}


{# --- integer cast that tolerates the box score's untidiness ---------------------------
  /games/teams ships stats as free text: possessionTime arrives as " 00:00 " with padding,
  and a split can yield an empty part. Trim-and-nullif turns those into NULL instead of a
  failed cast. A genuinely non-numeric value still errors, which is correct — silent
  coercion of an unexpected format is how a stat column fills with zeros nobody questions.
#}
{% macro safe_int(expr) -%}
    cast(nullif(trim(cast({{ expr }} as {{ dbt.type_string() }})), '') as int)
{%- endmacro %}
