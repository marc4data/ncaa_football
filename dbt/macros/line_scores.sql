{#
  --- quarter-by-quarter scores out of CFBD's line-score array ---------------------------

  /games ships home_line_scores / away_line_scores as a JSON array of per-period points. The
  column is non-null on every row and that is misleading: 64,254 rows hold an EMPTY array and
  1,850 hold JSON null. Only 44,775 carry actual periods, from 2001 onward.

  EVERY MACRO HERE GUARDS ON jsonb_typeof FIRST, and the guard is not defensive decoration.
  Postgres may evaluate a function before the WHERE clause that was meant to protect it —
  under parallel query it demonstrably does — so `where typeof = 'array'` outside the call
  raises "cannot get array length of a scalar" on the JSON-null rows. The guard has to be
  inside the expression, which is why these are macros rather than inline SQL repeated
  fourteen times.
#}

{% macro line_score_period(column, period) -%}
    {{ return(adapter.dispatch('line_score_period', 'cfdb_dbt')(column, period)) }}
{%- endmacro %}

{% macro default__line_score_period(column, period) -%}
    case when jsonb_typeof({{ column }}) = 'array'
              and jsonb_array_length({{ column }}) >= {{ period }}
         then ({{ column }} ->> {{ period - 1 }})::int end
{%- endmacro %}

{% macro databricks__line_score_period(column, period) -%}
    try_cast(get(from_json({{ column }}, 'array<int>'), {{ period - 1 }}) as int)
{%- endmacro %}


{# Everything past regulation, summed. Periods reach 13 in this data — nine overtimes — so a
   column per period would invent nine of them or truncate a long game. NULL, not 0, when a
   game has no periods recorded at all: zero would claim it went to regulation and stopped. #}
{% macro line_score_overtime(column) -%}
    {{ return(adapter.dispatch('line_score_overtime', 'cfdb_dbt')(column)) }}
{%- endmacro %}

{% macro default__line_score_overtime(column) -%}
    case when jsonb_typeof({{ column }}) = 'array' and jsonb_array_length({{ column }}) > 4
         then (select sum(value::int)
               from jsonb_array_elements_text({{ column }}) with ordinality t(value, ord)
               where ord > 4)
         when jsonb_typeof({{ column }}) = 'array' and jsonb_array_length({{ column }}) > 0
         then 0 end
{%- endmacro %}

{% macro databricks__line_score_overtime(column) -%}
    aggregate(slice(from_json({{ column }}, 'array<int>'), 5, 100), 0, (acc, x) -> acc + x)
{%- endmacro %}


{# How many periods were recorded. NULL where none were, so a page can tell "went to 2OT"
   from "we do not hold the quarters for this game". #}
{% macro line_score_periods(column) -%}
    {{ return(adapter.dispatch('line_score_periods', 'cfdb_dbt')(column)) }}
{%- endmacro %}

{% macro default__line_score_periods(column) -%}
    case when jsonb_typeof({{ column }}) = 'array' and jsonb_array_length({{ column }}) > 0
         then jsonb_array_length({{ column }}) end
{%- endmacro %}

{% macro databricks__line_score_periods(column) -%}
    nullif(size(from_json({{ column }}, 'array<int>')), 0)
{%- endmacro %}
