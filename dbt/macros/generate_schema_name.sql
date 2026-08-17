{#
  Route models to layer schemas instead of one shared namespace.

  dbt's default prepends the target schema to any custom schema (`public_marts`), which
  would keep the layers entangled in the name rather than separating them. This override
  returns the configured schema verbatim, so `staging` and `marts` are real schemas in
  both Postgres and Unity Catalog — and a grant on one layer is a one-liner rather than a
  pattern match over table names.

  Models without a +schema config fall back to the target schema, which is what the CI
  fixture and any ad-hoc model use.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
