{#
  Deterministic surrogate key from natural key parts.

  No dbt_utils in this project, and adding the dependency for one macro is not worth the
  version surface. md5 over a joined string works identically in Postgres and Spark.

  The null token matters: ('a', null) and ('a', '') must not collide. Coalescing to an
  empty string would make them the same key, which is the kind of bug that shows up as a
  duplicate row months later and is very hard to trace back to here.
#}
{% macro surrogate_key(parts) -%}
    {{ return(adapter.dispatch('surrogate_key', 'cfdb_dbt')(parts)) }}
{%- endmacro %}

{% macro default__surrogate_key(parts) -%}
    md5(concat_ws('||'
        {%- for part in parts -%}
        , coalesce(cast({{ part }} as text), '~null~')
        {%- endfor -%}
    ))
{%- endmacro %}

{% macro databricks__surrogate_key(parts) -%}
    md5(concat_ws('||'
        {%- for part in parts -%}
        , coalesce(cast({{ part }} as string), '~null~')
        {%- endfor -%}
    ))
{%- endmacro %}
