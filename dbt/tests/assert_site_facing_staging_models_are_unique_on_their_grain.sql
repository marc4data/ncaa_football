{{ config(severity='error') }}
-- Every staging model holds one row per the grain its documentation claims.
--
-- WHY STAGING NEEDS THIS AND NOT JUST THE FACTS. Staging is where the raw layer's
-- multiplicity is resolved, so it is where the resolution can be wrong, and a duplicate
-- introduced here is inherited by every mart downstream. The fact-level sweep
-- (assert_facts_are_unique_on_their_natural_key) catches the consequence one layer late,
-- after the fan-out has already been joined into something.
--
-- THE SPECIFIC FAILURE THIS EXISTS FOR. Staging models dedup with
-- `row_number() over (partition by params ...)`, which keeps the newest response PER REQUEST.
-- That is correct only while different requests return disjoint entities. It held for /games
-- until a season-scoped fetch was added next to the week-scoped ones; the two overlapped,
-- params-level dedup could not see it, and 211 duplicate game_ids reached fct_game. The fix
-- was a second dedup on the entity id — but the same shape is present in every model that
-- partitions by params, and nothing was watching the others.
--
-- Checked when this test was written, against the landed corpus: /games/teams held 3,414
-- games across 35 param sets and /games/players 3,413, with no id appearing in two fetches.
-- Disjoint TODAY. This is the tripwire for the day a season-scoped fetch is added.
--
-- Enumerating the class rather than testing one model at a time is deliberate. Six separate
-- outages in four days came from patching one instance of a defect class at a time; the
-- lesson recorded then was to enumerate the class before the third patch.
--
-- stg_rating_core DECLARES FOUR KEYS, NOT TWO. /ratings/core publishes the rating AS OF a
-- point in the season, so its grain is (season, team, through_season_type, through_week).
-- The landed data holds exactly one as-of point per season today, which is precisely the
-- condition under which a (season, team) declaration passes every build and starts silently
-- dropping rows the moment CFBD serves a second one.
--
-- Note for anyone editing the list below: it is a single Jinja expression, so NO comment
-- syntax works inside it — neither `--` nor `{# #}`. Both are compilation errors. Comments
-- about individual entries belong up here.
-- ==========================================================================================
-- THE SITE-FACING HALF OF THE SWEEP. severity = error: these gate the publish (R-420).
--
-- Split from the warehouse-only half on Marc's ruling of 2026-09-08. One duplicate anywhere
-- in the old 70-model sweep stopped BOTH two-hourly publishes, because dbt's default
-- indirect_selection is `eager` -- a singular test is selected when ANY of its parents is.
-- A duplicate in stg_draft_pick could stop the site from updating.
--
-- The membership test is DERIVED, not pasted: site_facing_staging() walks depends_on from
-- every `production`-tagged node. A hardcoded list would be wrong the day a serving view
-- gains an ancestor, and wrong in the safe-looking direction.
--
-- ⚠️ If the derivation returns nothing -- during parsing, or if the graph shape changes --
-- this test selects nothing and passes vacuously, while its warn-severity twin picks up
-- every model. That fails safe for the PUBLISH and loud in the ALERT, which is the right way
-- round, and assert_the_staging_sweep_covers_every_model catches the vacuum itself.
-- ==========================================================================================

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
  {%- if (model in site_facing) == true -%}
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
