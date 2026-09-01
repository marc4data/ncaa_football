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


{# --- Extract a scalar from a nested object ------------------------------------------

  ARBITRARY DEPTH, because two was not enough and the old version failed silently.

  This read `path[0]` and `path[1]` and ignored everything after. A three-element path
  therefore returned a two-level lookup — an OBJECT rendered as text, not the scalar asked
  for — with no error anywhere. Nothing needed three levels until the advanced stats models,
  where `offense.standardDowns.ppa` is the normal shape and there are sixty of them.

  Empty paths raise rather than compiling to something that reads the whole column.
#}
{% macro json_get_nested_string(column, path) -%}
    {{ return(adapter.dispatch('json_get_nested_string', 'cfdb_dbt')(column, path)) }}
{%- endmacro %}

{% macro default__json_get_nested_string(column, path) -%}
    {%- if path | length == 0 -%}
        {{ exceptions.raise_compiler_error("json_get_nested_string needs at least one key") }}
    {%- endif -%}
    ({{ column }}
    {%- for key in path[:-1] %} -> '{{ key }}'{% endfor %} ->> '{{ path[-1] }}')
{%- endmacro %}

{% macro databricks__json_get_nested_string(column, path) -%}
    {%- if path | length == 0 -%}
        {{ exceptions.raise_compiler_error("json_get_nested_string needs at least one key") }}
    {%- endif -%}
    (get_json_object({{ column }}, '$.{{ path | join('.') }}'))
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


{# --- Nth element of a JSON ARRAY, as text ------------------------------------------------
  Distinct from json_get_string, which addresses an OBJECT KEY. On an array, Postgres's
  `->> '0'` looks for a key named "0", finds none, and returns NULL — silently, because a
  missing key and a null value are the same answer.

  That is exactly how every logo on the site went missing: dim_team.logos held a populated
  array of CDN URLs on all 34,061 rows, logo_source_url extracted element 0 with the key
  accessor, and the monogram fallback fired 100% of the time. The fallback was working, so
  nothing looked broken — the site simply had no logos.
#}
{% macro json_array_element_string(column, index) -%}
    {{ return(adapter.dispatch('json_array_element_string', 'cfdb_dbt')(column, index)) }}
{%- endmacro %}

{% macro default__json_array_element_string(column, index) -%}
    ({{ column }} ->> {{ index }})
{%- endmacro %}

{% macro databricks__json_array_element_string(column, index) -%}
    get_json_object({{ column }}, '$[{{ index }}]')
{%- endmacro %}


{# --- An exploded array ELEMENT that is itself a scalar, as text --------------------------

  For endpoints returning a bare array of strings — /stats/categories is the whole payload,
  no wrapping object. After json_array_elements, Postgres hands back a `jsonb` scalar and
  Spark hands back the string, so reading it needs the dialect split even though nothing is
  being addressed by key.

  `#>> '{}'` is the empty path: "extract this whole value as text". Casting with ::text
  instead would keep JSON's quotes, giving `"passing"` rather than passing — which does not
  fail, it just silently poisons every join and filter downstream.
#}
{% macro json_scalar_text(column) -%}
    {{ return(adapter.dispatch('json_scalar_text', 'cfdb_dbt')(column)) }}
{%- endmacro %}

{% macro default__json_scalar_text(column) -%}
    ({{ column }} #>> '{}')
{%- endmacro %}

{% macro databricks__json_scalar_text(column) -%}
    ({{ column }})
{%- endmacro %}


{# --- Nth element of a JSON array, as an OBJECT you can keep reading ------------------------

  json_array_element_string returns the element as TEXT, which ends the chain: you cannot ask
  it for a key afterwards. This returns the element still typed as JSON, so it composes —
  json_get_string(json_array_element_object(col, 0), 'seed').

  Needed for fixed-width arrays, where the position IS the meaning and exploding to rows would
  be wrong. A CFP matchup has exactly two slots and they are ordered; flattening them to
  slot_1 / slot_2 answers "who played whom" directly, where long form makes every caller
  self-join to ask it.

  Use it only where the array's length is part of the schema. For an open-ended array —
  stat categories, athletes, logos — json_array_elements is the right tool and this is not.
#}
{% macro json_array_element_object(column, index) -%}
    {{ return(adapter.dispatch('json_array_element_object', 'cfdb_dbt')(column, index)) }}
{%- endmacro %}

{% macro default__json_array_element_object(column, index) -%}
    ({{ column }} -> {{ index }})
{%- endmacro %}

{% macro databricks__json_array_element_object(column, index) -%}
    (get_json_object({{ column }}, '$[{{ index }}]'))
{%- endmacro %}
