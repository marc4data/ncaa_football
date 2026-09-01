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


{# --- Whole days between two DATES ------------------------------------------------------
  Postgres subtracts dates directly and yields an integer; Spark has no `-` operator for
  dates at all and needs datediff(). Same question, no shared syntax — which is what the
  dispatch is for.

  DATES, not timestamps. Rest between games is counted in calendar days, and doing it on
  timestamps would make a Saturday night kickoff followed by a Saturday noon kickoff read as
  six days instead of seven.
#}
{% macro days_between(later, earlier) -%}
    {{ return(adapter.dispatch('days_between', 'cfdb_dbt')(later, earlier)) }}
{%- endmacro %}

{% macro default__days_between(later, earlier) -%}
    ({{ later }} - {{ earlier }})
{%- endmacro %}

{% macro databricks__days_between(later, earlier) -%}
    datediff({{ later }}, {{ earlier }})
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


{# --- numeric value from free text, or NULL ---------------------------------------------
  CFBD's /stats/season declares `statValue` as anyOf[string, number], so a value that looks
  numeric usually is and occasionally is not. Postgres tests with its `~` regex operator,
  which Spark does not have at all; Spark's `try_cast` expresses the same intent natively
  and more cheaply. Same question, no shared syntax — the case dispatch exists for.
#}
{% macro safe_numeric(col) -%}
    {{ return(adapter.dispatch('safe_numeric', 'cfdb_dbt')(col)) }}
{%- endmacro %}

{% macro default__safe_numeric(col) -%}
    case when {{ col }} ~ '^-?[0-9]+(\.[0-9]+)?$' then cast({{ col }} as numeric) end
{%- endmacro %}

{% macro databricks__safe_numeric(col) -%}
    try_cast({{ col }} as decimal(38,10))
{%- endmacro %}


{# --- Python-style boolean text to a real boolean ----------------------------------------
  The pack's CSV exports are written by pandas, so booleans arrive as "True"/"False" and an
  EMPTY string means not-applicable — a push on the spread, or a field the model does not
  populate. Coercing blank to false would turn "no cover result" into "did not cover", which
  is a wrong answer rather than a missing one, so blanks stay NULL.
#}
{% macro text_to_boolean(col) -%}
    case
        when {{ col }} is null or trim({{ col }}) = '' then null
        when lower(trim({{ col }})) in ('true', 't', '1')  then true
        when lower(trim({{ col }})) in ('false', 'f', '0') then false
    end
{%- endmacro %}


{# --- American moneyline to raw implied probability --------------------------------------
  Includes the vig: the two sides of a real market sum to more than 1, and that overround is
  the book's margin. Removing it is a separate, named step — see fct_market_probability.

      +150  ->  decimal 2.50  ->  0.400
      -200  ->  decimal 1.50  ->  0.667

  Zero is not a valid moneyline and would divide by zero, so it is treated as absent.
#}
{% macro moneyline_to_implied(col) -%}
    case
        when {{ col }} is null or {{ col }} = 0 then null
        when {{ col }} > 0 then 100.0 / ({{ col }} + 100.0)
        else (-1.0 * {{ col }}) / ((-1.0 * {{ col }}) + 100.0)
    end
{%- endmacro %}


{# --- URL slug from a display name -------------------------------------------------------
  AC-G.14: slugs are a dbt decision, never string manipulation in the app, because the app
  must not own an identifier the database uses. `Texas A&M` -> `texas-am`.

  Order matters. Ampersands and periods are removed rather than replaced with a separator,
  so `Texas A&M` gives `texas-am` and not `texas-a-m`; everything else non-alphanumeric
  becomes a hyphen, runs collapse, and leading/trailing hyphens are trimmed. Written the
  same way in both dialects because the regex flavours agree on these classes.
#}
{% macro to_slug(col) -%}
    {{ return(adapter.dispatch('to_slug', 'cfdb_dbt')(col)) }}
{%- endmacro %}

{% macro default__to_slug(col) -%}
    trim(both '-' from
      regexp_replace(
        regexp_replace(lower(trim({{ col }})), '[&.'']', '', 'g'),
        '[^a-z0-9]+', '-', 'g'))
{%- endmacro %}

{% macro databricks__to_slug(col) -%}
    trim('-',
      regexp_replace(
        regexp_replace(lower(trim({{ col }})), '[&.\']', ''),
        '[^a-z0-9]+', '-'))
{%- endmacro %}


{# --- UTC timestamp rendered in a display zone, keeping it a timestamp -------------------
  AC-G.34: kickoff times are published Eastern, so the display zone is applied in dbt and
  the app never converts. Distinct from to_local_date, which drops the time.
#}
{% macro to_local_timestamp(ts, tz='America/New_York') -%}
    {{ return(adapter.dispatch('to_local_timestamp', 'cfdb_dbt')(ts, tz)) }}
{%- endmacro %}

{% macro default__to_local_timestamp(ts, tz) -%}
    ({{ ts }} at time zone '{{ tz }}')
{%- endmacro %}

{% macro databricks__to_local_timestamp(ts, tz) -%}
    from_utc_timestamp({{ ts }}, '{{ tz }}')
{%- endmacro %}
