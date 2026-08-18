{{ config(materialized='table') }}

-- One row per (season, team_id). SEASON-SCOPED, NOT SCD2.
--
-- Per-season scoping answers "what was true in season X", which is the question every page
-- asks. True SCD2 would answer "what was true on date D" and express mid-season changes;
-- conference realignment happens between seasons, so the extra machinery would buy nothing
-- and cost a validity-interval join on every fact.
--
-- Contrast-safe colour variants are computed here rather than in the app (identity spec D2).
-- The ladder is: primary if it clears 3:1 against the surface, else the alternate, else the
-- primary blended toward black (light surface) or white (dark surface) in fixed steps, else
-- a neutral grey. `color_source` records which rung was used — it is how you find the teams
-- whose brand colour is being altered, and it belongs in a data-quality view.

{% set light_surface_luminance = 0.9757 %}   {# #fcfcfb #}
{% set dark_surface_luminance  = 0.0116 %}   {# #1a1a19 #}
{% set neutral_on_light = '#6b6b68' %}
{% set neutral_on_dark  = '#9a9a96' %}
{% set min_contrast = 3.0 %}

with teams as (

    select * from {{ ref('stg_teams') }}

),

scored as (

    select
        t.*,
        case when t.color_raw is not null
             then {{ contrast_vs('t.color_raw', light_surface_luminance) }} end as primary_on_light,
        case when t.color_raw is not null
             then {{ contrast_vs('t.color_raw', dark_surface_luminance) }} end  as primary_on_dark,
        case when t.alt_color_raw is not null
             then {{ contrast_vs('t.alt_color_raw', light_surface_luminance) }} end as alt_on_light,
        case when t.alt_color_raw is not null
             then {{ contrast_vs('t.alt_color_raw', dark_surface_luminance) }} end  as alt_on_dark,
        -- Fixed blend rungs rather than an iterative loop: unrolled steps are expressible
        -- identically in both engines, and four rungs is enough to clear 3:1 from any
        -- starting colour.
        {% for f in [0.25, 0.45, 0.65, 0.85] %}
        {{ blend_hex('t.color_raw', 0, f) }}   as dark_blend_{{ loop.index }},
        {{ blend_hex('t.color_raw', 255, f) }} as light_blend_{{ loop.index }},
        {% endfor %}
        1 as _keep
    from teams t

),

resolved as (

    select
        s.*,
        case
            when s.primary_on_light >= {{ min_contrast }} then s.color_raw
            when s.alt_on_light     >= {{ min_contrast }} then s.alt_color_raw
            {% for i in range(1, 5) %}
            when s.color_raw is not null
             and {{ contrast_vs('s.dark_blend_' ~ i, light_surface_luminance) }} >= {{ min_contrast }}
                then s.dark_blend_{{ i }}
            {% endfor %}
            else '{{ neutral_on_light }}'
        end as color_on_light,
        case
            when s.primary_on_dark >= {{ min_contrast }} then s.color_raw
            when s.alt_on_dark     >= {{ min_contrast }} then s.alt_color_raw
            {% for i in range(1, 5) %}
            when s.color_raw is not null
             and {{ contrast_vs('s.light_blend_' ~ i, dark_surface_luminance) }} >= {{ min_contrast }}
                then s.light_blend_{{ i }}
            {% endfor %}
            else '{{ neutral_on_dark }}'
        end as color_on_dark,
        -- Per surface, because the resolution is per surface. A single label collapsed both
        -- and reported 'adjusted' for teams whose primary was fine on light and only needed
        -- blending on dark — which overstated how often a brand colour is altered.
        case
            when s.color_raw is null then 'fallback'
            when s.primary_on_light >= {{ min_contrast }} then 'primary'
            when s.alt_on_light     >= {{ min_contrast }} then 'alternate'
            {% for i in range(1, 5) %}
            when {{ contrast_vs('s.dark_blend_' ~ i, light_surface_luminance) }} >= {{ min_contrast }} then 'adjusted'
            {% endfor %}
            else 'fallback'
        end as color_source_light,
        case
            when s.color_raw is null then 'fallback'
            when s.primary_on_dark >= {{ min_contrast }} then 'primary'
            when s.alt_on_dark     >= {{ min_contrast }} then 'alternate'
            {% for i in range(1, 5) %}
            when {{ contrast_vs('s.light_blend_' ~ i, dark_surface_luminance) }} >= {{ min_contrast }} then 'adjusted'
            {% endfor %}
            else 'fallback'
        end as color_source_dark
    from scored s

)

select
    {{ surrogate_key(['r.season', 'r.team_id']) }} as team_sk,
    r.season,
    r.team_id,
    r.school,
    r.mascot,
    r.abbreviation,
    r.conference,
    c.conference_sk,
    r.division,
    r.classification,
    r.classification = 'fbs' as is_fbs,
    r.city,
    r.state,
    r.color_raw,
    r.alt_color_raw,
    r.color_on_light,
    r.color_on_dark,
    r.color_source_light,
    r.color_source_dark,
    -- The worse of the two rungs, for the data-quality view: how far from brand is this
    -- team rendered at its worst.
    case
        when 'fallback' in (r.color_source_light, r.color_source_dark) then 'fallback'
        when 'adjusted' in (r.color_source_light, r.color_source_dark) then 'adjusted'
        when 'alternate' in (r.color_source_light, r.color_source_dark) then 'alternate'
        else 'primary'
    end as color_source,
    r.logos,
    -- The 500px light variant is the one the site renders. logo_path stays null until the
    -- fetch-and-cache task exists (identity spec D3) — the column is here so the app never
    -- changes shape when caching lands.
    {{ json_get_string('r.logos', '0') }} as logo_source_url,
    cast(null as {{ dbt.type_string() }}) as logo_path
from resolved r
left join {{ ref('dim_conference') }} c
    on c.season = r.season
   and c.conference_name = r.conference
