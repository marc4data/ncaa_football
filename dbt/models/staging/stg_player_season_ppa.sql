-- Player PPA for a season: one row per (season, player), average and total side by side.
--
-- TWO SCALES, AND HERE THEY SHARE EVERY FIELD NAME. `averagePPA.all` is PPA per play;
-- `totalPPA.all` is PPA accumulated over the season. Both objects carry the identical eight
-- keys, so the prefixes are the only thing distinguishing 0.352 from 114.748 — the same
-- player, the same statistic, different scales. A model that flattened them without
-- prefixing would silently keep whichever came last.
--
-- THIS ENDPOINT SPELLS CONFERENCES DIFFERENTLY FROM EVERY OTHER ONE. It reports `B1G`,
-- `B12`, `AAC` where /ppa/teams, /ppa/games and the ratings endpoints all report `Big Ten`,
-- `Big 12`, `American Athletic`. Anything filtering `conference = 'Big 12'` across staging
-- models gets rows from all of them EXCEPT this, and gets no error — just a quietly empty
-- result for one source.
--
-- The abbreviation is carried verbatim rather than translated, because staging represents
-- the endpoint and a mapping table is a mart's concern. It is called out here, in the model
-- docs and in the coverage matrix's own record so the next person meets it before the join
-- rather than after.

{% set splits = ['all', 'pass', 'rush', 'firstDown', 'secondDown', 'thirdDown',
                 'standardDowns', 'passingDowns'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ppa_players_season') }}
    where status_code = 200

),

exploded as (

    select filename, {{ json_array_elements('payload') }} as row_json
    from successful_fetches

),

deduped as (

    select row_json
    from (
        select
            row_json,
            row_number() over (
                partition by
                    {{ json_get_string('row_json', 'season') }},
                    {{ json_get_string('row_json', 'id') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'season') }} as int) as season,
    {{ json_get_string('row_json', 'id') }}                  as player_id,
    {{ json_get_string('row_json', 'name') }}                as player_name,
    {{ json_get_string('row_json', 'position') }}            as position,
    {{ json_get_string('row_json', 'team') }}                as team,
    -- ABBREVIATED on this endpoint alone. See the header.
    {{ json_get_string('row_json', 'conference') }}          as conference_abbreviation

{%- for source_key, prefix in [('averagePPA', 'average_ppa'), ('totalPPA', 'total_ppa')] %}
    {%- for metric in splits %},
    {{ safe_numeric(json_get_nested_string('row_json', [source_key, metric])) }}
        as {{ prefix }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}

from deduped
