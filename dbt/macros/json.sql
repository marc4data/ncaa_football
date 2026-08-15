{#
  Cross-dialect JSON access.

  Resolves the standing register item: raw payloads are JSON, every staging model unpacks
  them, and the unpacking was written in Postgres dialect (`->>`, `->`,
  `jsonb_array_elements`). Left alone, the M4 Databricks migration would grow with every
  model added. These macros mean staging is written once and the dialect is a detail of
  which implementation `adapter.dispatch` selects.

  Every macro parenthesises what it emits. Postgres binds `->>` looser than `||`, so an
  unparenthesised expression silently reassociates at the call site — caught here by a
  compile error, but it would just as easily have produced wrong values.

  Postgres implementations are the default and reproduce the previous SQL exactly — the
  refactor onto them is verified data-neutral by checksum, not by inspection.

  Databricks implementations are written against Spark SQL semantics but are UNVERIFIED
  until the M4 target exists. They are deliberately included now so the dialect gap is
  visible and reviewable rather than discovered during the migration.

  The standing rule holds: JSON unnesting stays confined to staging. If a mart needs these
  macros, the model is in the wrong layer.
#}

{# --- Extract a scalar (text) value by key ------------------------------------------- #}
{% macro json_get_string(column, key) -%}
    {{ return(adapter.dispatch('json_get_string', 'cfdb_dbt')(column, key)) }}
{%- endmacro %}

{% macro default__json_get_string(column, key) -%}
    ({{ column }} ->> '{{ key }}')
{%- endmacro %}

{% macro databricks__json_get_string(column, key) -%}
    (get_json_object({{ column }}, '$.{{ key }}'))
{%- endmacro %}


{# --- Extract a nested object, to be read from again --------------------------------- #}
{% macro json_get_object(column, key) -%}
    {{ return(adapter.dispatch('json_get_object', 'cfdb_dbt')(column, key)) }}
{%- endmacro %}

{% macro default__json_get_object(column, key) -%}
    ({{ column }} -> '{{ key }}')
{%- endmacro %}

{% macro databricks__json_get_object(column, key) -%}
    (get_json_object({{ column }}, '$.{{ key }}'))
{%- endmacro %}


{# --- Extract a scalar from a nested object ------------------------------------------ #}
{% macro json_get_nested_string(column, path) -%}
    {{ return(adapter.dispatch('json_get_nested_string', 'cfdb_dbt')(column, path)) }}
{%- endmacro %}

{% macro default__json_get_nested_string(column, path) -%}
    ({{ column }} -> '{{ path[0] }}' ->> '{{ path[1] }}')
{%- endmacro %}

{% macro databricks__json_get_nested_string(column, path) -%}
    (get_json_object({{ column }}, '$.{{ path[0] }}.{{ path[1] }}'))
{%- endmacro %}


{#
  --- Expand a JSON array into rows ---------------------------------------------------

  The one macro that is not a drop-in expression: the dialects disagree about *where*
  unnesting happens. Postgres returns a set from a function usable in the select list;
  Spark uses explode(). Both are used the same way here — as a select-list expression
  producing one row per element — which is why the call sites are identical.

  Spark needs the array's element type, hence from_json(..., 'array<string>'); each element
  then comes back as a JSON string that the accessors above can read.
#}
{% macro json_array_elements(column) -%}
    {{ return(adapter.dispatch('json_array_elements', 'cfdb_dbt')(column)) }}
{%- endmacro %}

{% macro default__json_array_elements(column) -%}
    jsonb_array_elements({{ column }})
{%- endmacro %}

{% macro databricks__json_array_elements(column) -%}
    explode(from_json({{ column }}, 'array<string>'))
{%- endmacro %}
