{{ config(severity='warn') }}
-- THE WAREHOUSE-ONLY HALF OF THE SWEEP. severity = warn: these must not stop the site (R-420).
--
-- Same list, same grains, same query -- only the consequence differs. A duplicate in
-- stg_draft_pick or stg_rating_fpi is a real defect and still surfaces on every run, in the
-- alert payload R-412 built. It no longer freezes a site that never reads it.
--
-- Membership is the complement of site_facing_staging(), derived from the graph, so a model
-- promoted into a serving view's ancestry moves to the error half on the next run without
-- anyone editing a list.

{#- STATIC DEPENDENCY HINTS, AND THEY ARE LOAD-BEARING (R-420).
    dbt parses in two passes. During PARSING `execute` is false, so site_facing_staging()
    returns an empty list, the conditional below emits no ref() at all, and dbt records this
    test as depending on nothing. At RUN time the refs appear and dbt refuses outright:
    "dbt was unable to infer all dependencies ... This typically happens when ref() is placed
    within a conditional block."
    So every model is ref'd unconditionally here, registering the full dependency set
    statically while the SELECTION below stays derived from the graph. The hints come from the
    same shared list, so they cannot drift from what they cover. -#}
{% for model, grain in staging_grains() %}
-- depends_on: {{ ref(model) }}
{%- endfor %}

{%- set site_facing = site_facing_staging() -%}
{%- set selected = [] -%}
{%- for model, grain in staging_grains() -%}
  {%- if (model in site_facing) == false -%}
    {%- do selected.append((model, grain)) -%}
  {%- endif -%}
{%- endfor -%}

{% if selected | length == 0 %}
select null as model_name, null as grain, null as duplicate_keys where false
{% else %}
{% for model, grain in selected %}
select
    '{{ model }}'                                 as model_name,
    '{{ grain | join(", ") }}'                    as grain,
    count(*)                                      as duplicate_keys
from (
    select {{ grain | join(', ') }}
    from {{ ref(model) }}
    group by {{ grain | join(', ') }}
    having count(*) > 1
) d
having count(*) > 0
{% if not loop.last %}
union all
{% endif %}
{% endfor %}
{% endif %}
