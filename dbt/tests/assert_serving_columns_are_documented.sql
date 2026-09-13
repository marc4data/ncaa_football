-- Every serving column carries a description.
--
-- AC-16.6, rewritten. The previous version asserted that every serving column APPEARS in
-- the dictionary, which the model reads out of information_schema and therefore satisfies
-- by construction — it tested nothing. The criterion worth having is the one that is
-- currently false.
--
-- RAISED TO ERROR. It was warn while the debt stood at 634 undocumented serving columns —
-- a test that fails hundreds of times on day one gets muted rather than paid down, so warn
-- kept the number countable and visible on every run instead. That threshold has now been
-- cleared: dbt/models/serving/_models.yml documents all 634, and the honest way to keep it
-- there is to make the next undocumented column fail the build rather than add one more
-- line to a warning nobody reads.
--
-- This checks the SERVING layer only. Staging and dimensional coverage are still partial
-- and are not in scope here; widening it is a separate decision with a separate backlog.
{{ config(severity='error') }}

{#- 🚨 THE EDGE THAT MAKES THIS TEST MEAN WHAT IT SAYS. R-714 / CLAUDE.md §3.6.

    Without it this test depends on ONE node — `dim_field_metadata`, which `ref()`s nothing — so dbt
    is free to run it before the serving layer exists, and does. Measured on A106's own CI run:
    node 155 of 740, PASS in 0.07s, against `serving.srv_game` created at 683 of 740. It passed
    because there was nothing to check, and the Sunday publish stopped four hours later on the gap
    it had waved through.

    ⚠️ REF'D UNCONDITIONALLY, INSIDE A COMMENT. The comment keeps the refs out of the SQL; Jinja is
    rendered first, so `ref()` still registers. A conditional here would break inference outright —
    `assert_site_facing_staging_models_are_unique_on_their_grain` carries that lesson in full.

    ⚠️ AND THE EDGE IS ON THE TEST, NOT ON `dim_field_metadata`. That model's header states the
    design: a view "sidesteps the ordering question entirely… any downstream consumer still has to
    run after the models it documents; that constraint now lives in one place instead of being a
    property of this model's position in the DAG." Putting the edge on the model would put it back.
    The two generated tests on `dim_field_metadata.field_sk` are declared in YAML, where this idiom
    does not exist, and early execution makes them weaker rather than wrong. -#}
{% for model in serving_models() %}
-- depends_on: {{ ref(model) }}
{%- endfor %}

select table_schema, table_name, column_name
from {{ ref('dim_field_metadata') }}
where layer = 'serving'
  and column_description is null
