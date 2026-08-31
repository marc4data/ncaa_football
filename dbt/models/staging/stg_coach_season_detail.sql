-- One row per (coach, season, team) — the rich version, from /coaches/seasons.
--
-- SAME GRAIN AS stg_coach_season, VERY DIFFERENT CONTENT. /coaches publishes the record;
-- /coaches/seasons publishes the record PLUS team metrics, recruiting, poll resume, split
-- records by venue and game type, scoring, CFP outcome and the following season's draft
-- haul. Thirty-six fields against nineteen, and it is the deepest nesting outside the box
-- scores: coach{}, team{}, teamMetrics{yearOverYear{}}, recordSplits{five identical blocks}.
--
-- Both models are kept because they are separate endpoints with separate raw tables and they
-- do not cover the same seasons — /coaches is fetched for 141 seasons back to 1886,
-- /coaches/seasons for three. Merging them would make the coverage matrix report on a model
-- rather than on the endpoints.
--
-- RECORD SPLITS ARE FIVE COPIES OF ONE SHAPE — conference, postseason, home, away, neutral,
-- each with games/wins/losses/ties/winPercentage. Generated from one list so a `home_wins`
-- that reads `away.wins` is unrepresentable rather than merely unlikely.
--
-- `winPercentage` IS NULL WHERE GAMES IS ZERO, which is most neutral-site and postseason
-- splits. Kept null rather than coerced to 0: no games played and every game lost are not
-- the same season.

{% set split_metrics = ['games', 'wins', 'losses', 'ties', 'winPercentage'] %}
{% set splits = ['conference', 'postseason', 'home', 'away', 'neutral'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_coaches_seasons') }}
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
                    {{ json_get_nested_string('row_json', ['coach', 'id']) }},
                    {{ json_get_string('row_json', 'year') }},
                    {{ json_get_nested_string('row_json', ['team', 'id']) }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_nested_string('row_json', ['coach', 'id']) }} as int) as coach_id,
    {{ json_get_nested_string('row_json', ['coach', 'firstName']) }}       as first_name,
    {{ json_get_nested_string('row_json', ['coach', 'lastName']) }}        as last_name,
    cast({{ json_get_string('row_json', 'year') }} as int)                 as season,
    cast({{ json_get_nested_string('row_json', ['team', 'id']) }} as int)  as team_id,
    {{ json_get_nested_string('row_json', ['team', 'school']) }}           as school,
    {{ json_get_nested_string('row_json', ['team', 'conference']) }}       as conference,

    cast({{ json_get_string('row_json', 'games') }} as int)  as games,
    cast({{ json_get_string('row_json', 'wins') }} as int)   as wins,
    cast({{ json_get_string('row_json', 'losses') }} as int) as losses,
    cast({{ json_get_string('row_json', 'ties') }} as int)   as ties,
    {{ safe_numeric(json_get_string('row_json', 'winPercentage')) }}   as win_percentage,
    cast({{ json_get_string('row_json', 'preseasonRank') }} as int)    as preseason_rank,
    cast({{ json_get_string('row_json', 'postseasonRank') }} as int)   as postseason_rank,
    {{ safe_numeric(json_get_string('row_json', 'srs')) }}             as srs,
    {{ safe_numeric(json_get_string('row_json', 'spOverall')) }}       as sp_overall,
    {{ safe_numeric(json_get_string('row_json', 'spOffense')) }}       as sp_offense,
    {{ safe_numeric(json_get_string('row_json', 'spDefense')) }}       as sp_defense,
    -- Whether CFBD considers the season fully attributed to this coach. A false here means
    -- the record is shared with an interim and should not be read as one person's season.
    cast({{ json_get_string('row_json', 'attributionComplete') }} as boolean)
                                                                       as attribution_complete,

    {{ safe_numeric(json_get_nested_string('row_json', ['teamMetrics', 'spSpecialTeams'])) }}
        as sp_special_teams,
    {{ safe_numeric(json_get_nested_string('row_json', ['teamMetrics', 'strengthOfSchedule'])) }}
        as strength_of_schedule,
    {{ safe_numeric(json_get_nested_string('row_json', ['teamMetrics', 'secondOrderWins'])) }}
        as second_order_wins,
    {{ safe_numeric(json_get_nested_string('row_json', ['teamMetrics', 'fpi'])) }} as fpi,
    -- Deltas against the previous season, not absolute values.
    {{ safe_numeric(json_get_nested_string('row_json', ['teamMetrics', 'yearOverYear', 'wins'])) }}
        as year_over_year_wins,
    {{ safe_numeric(json_get_nested_string('row_json', ['teamMetrics', 'yearOverYear', 'srs'])) }}
        as year_over_year_srs,
    {{ safe_numeric(json_get_nested_string('row_json', ['teamMetrics', 'yearOverYear', 'spOverall'])) }}
        as year_over_year_sp_overall,

    cast({{ json_get_nested_string('row_json', ['recruiting', 'rank']) }} as int)
        as recruiting_rank,
    {{ safe_numeric(json_get_nested_string('row_json', ['recruiting', 'points'])) }}
        as recruiting_points,
    {{ safe_numeric(json_get_nested_string('row_json', ['recruiting', 'talent'])) }}
        as recruiting_talent,

    cast({{ json_get_nested_string('row_json', ['pollResume', 'bestRank']) }} as int)
        as poll_best_rank,
    cast({{ json_get_nested_string('row_json', ['pollResume', 'weeksRanked']) }} as int)
        as poll_weeks_ranked,
    cast({{ json_get_nested_string('row_json', ['pollResume', 'weeksTopTen']) }} as int)
        as poll_weeks_top_ten

{%- for split in splits %}
    {%- for metric in split_metrics %},
    {%- if metric == 'winPercentage' %}
    {{ safe_numeric(json_get_nested_string('row_json', ['recordSplits', split, metric])) }}
        as {{ snake_case(split) }}_{{ snake_case(metric) }}
    {%- else %}
    cast({{ json_get_nested_string('row_json', ['recordSplits', split, metric]) }} as int)
        as {{ snake_case(split) }}_{{ snake_case(metric) }}
    {%- endif %}
    {%- endfor %}
{%- endfor %},

    cast({{ json_get_nested_string('row_json', ['scoring', 'pointsFor']) }} as int)
        as points_for,
    cast({{ json_get_nested_string('row_json', ['scoring', 'pointsAgainst']) }} as int)
        as points_against,
    {{ safe_numeric(json_get_nested_string('row_json', ['scoring', 'averagePointDifferential'])) }}
        as average_point_differential,

    cast({{ json_get_nested_string('row_json', ['cfp', 'appeared']) }} as boolean)
        as cfp_appeared,
    cast({{ json_get_nested_string('row_json', ['cfp', 'seed']) }} as int) as cfp_seed,
    {{ json_get_nested_string('row_json', ['cfp', 'outcome']) }}           as cfp_outcome,

    -- The draft that FOLLOWED this season, so the year is season + 1.
    cast({{ json_get_nested_string('row_json', ['draftFollowingSeason', 'year']) }} as int)
        as draft_year,
    cast({{ json_get_nested_string('row_json', ['draftFollowingSeason', 'totalPicks']) }} as int)
        as draft_total_picks,
    cast({{ json_get_nested_string('row_json', ['draftFollowingSeason', 'firstRoundPicks']) }} as int)
        as draft_first_round_picks
from deduped
