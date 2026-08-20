-- One row per (season, team, rating system). Five systems, unpivoted to a long shape.
--
-- LONG RATHER THAN WIDE, and the reason is the grain check that preceded this model. The
-- five systems do not share a shape: SP+ carries offence, defence, special teams and
-- strength of schedule; SRS carries one number; PPA carries offence and defence only. A
-- wide table would be a column per system per component, mostly null, and would need
-- altering every time CFBD adds a system. Long means a new system is a new branch here and
-- nothing downstream changes.
--
-- THE NAME `fct_team_week_rating` WAS NOT BUILT, deliberately. It asserts week grain, and
-- the grain check against CFBD's own spec says only one of these five can provide it:
--
--   /ratings/elo    accepts week and seasonType   -- weekly-capable
--   /ratings/sp     year, team                    -- season only
--   /ratings/srs    year, team, conference        -- season only
--   /ratings/fpi    year, team, conference        -- season only
--   /ppa/teams      year, team, conference        -- season only
--
-- And Elo has been LANDED season-only — every file carries `{"year": ...}` and no week — so
-- a week-grain model today would be one real column and four fabricated ones. Forward-
-- filling a season-final SP+ across fourteen weeks would produce a convincing time series
-- that never happened, which is the same class of defect as a 0-0-0 record for a season
-- nobody has played.
--
-- So the grain is (season, team, system) with `rating_scope` saying what it is, and the
-- model is named for what it holds.
--
-- LATEST FETCH ONLY, per season. Ratings are re-fetched on the revisionist cadence, so the
-- raw layer holds six 2026 responses today and every one is a complete list. Without the
-- dedup this produced 834 SP+ rows for 138 teams — six copies of each, which would have
-- averaged out to a plausible number while every count on the page was six times too big.
{{ config(tags=['ratings']) }}

with sp_fetches as (
    select
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_ratings_sp') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null
),
sp as (
    select season, {{ json_array_elements('payload') }} as payload
    from sp_fetches where recency = 1
),
srs_fetches as (
    select
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_ratings_srs') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null
),
srs as (
    select season, {{ json_array_elements('payload') }} as payload
    from srs_fetches where recency = 1
),
elo_fetches as (
    select
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_ratings_elo') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null
),
elo as (
    select season, {{ json_array_elements('payload') }} as payload
    from elo_fetches where recency = 1
),
fpi_fetches as (
    select
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_ratings_fpi') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null
),
fpi as (
    select season, {{ json_array_elements('payload') }} as payload
    from fpi_fetches where recency = 1
),
ppa_fetches as (
    select
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_ppa_teams') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null
),
ppa as (
    select season, {{ json_array_elements('payload') }} as payload
    from ppa_fetches where recency = 1
),

unioned as (

    -- SP+. The only system that publishes a PRESEASON PROJECTION, which is why it is the
    -- one with 2026 rows before a ball has been kicked.
    select season, 'sp_plus' as rating_system,
           {{ json_get_string('payload', 'team') }}       as team,
           {{ json_get_string('payload', 'conference') }} as conference,
           {{ safe_numeric(json_get_string('payload', 'rating')) }}      as rating,
           {{ safe_numeric(json_get_string('payload', 'ranking')) }}     as rating_rank,
           {{ safe_numeric(json_get_nested_string('payload', ['offense', 'rating'])) }}
               as offense_rating,
           {{ safe_numeric(json_get_nested_string('payload', ['defense', 'rating'])) }}
               as defense_rating,
           {{ safe_numeric(json_get_nested_string('payload', ['specialTeams', 'rating'])) }}
               as special_teams_rating,
           {{ safe_numeric(json_get_string('payload', 'sos')) }}         as strength_of_schedule,
           {{ safe_numeric(json_get_string('payload', 'secondOrderWins')) }}
               as second_order_wins
    from sp

    union all

    select season, 'srs',
           {{ json_get_string('payload', 'team') }},
           {{ json_get_string('payload', 'conference') }},
           {{ safe_numeric(json_get_string('payload', 'rating')) }},
           {{ safe_numeric(json_get_string('payload', 'ranking')) }},
           null, null, null, null, null
    from srs

    union all

    select season, 'elo',
           {{ json_get_string('payload', 'team') }},
           {{ json_get_string('payload', 'conference') }},
           {{ safe_numeric(json_get_string('payload', 'elo')) }},
           null, null, null, null, null, null
    from elo

    union all

    -- FPI. Also a preseason projection, and its components live under `efficiencies`
    -- rather than at the top level.
    select season, 'fpi',
           {{ json_get_string('payload', 'team') }},
           {{ json_get_string('payload', 'conference') }},
           {{ safe_numeric(json_get_string('payload', 'fpi')) }},
           null,
           {{ safe_numeric(json_get_nested_string('payload', ['efficiencies', 'offense'])) }},
           {{ safe_numeric(json_get_nested_string('payload', ['efficiencies', 'defense'])) }},
           {{ safe_numeric(json_get_nested_string('payload', ['efficiencies', 'specialTeams'])) }},
           null, null
    from fpi

    union all

    -- PPA is predicted points added per play: an efficiency measure rather than a team
    -- strength rating, so it has no overall number of its own. `rating` carries offence,
    -- which is the figure a reader means by "their PPA", and both components are kept.
    select season, 'ppa',
           {{ json_get_string('payload', 'team') }},
           {{ json_get_string('payload', 'conference') }},
           {{ safe_numeric(json_get_nested_string('payload', ['offense', 'overall'])) }},
           null,
           {{ safe_numeric(json_get_nested_string('payload', ['offense', 'overall'])) }},
           {{ safe_numeric(json_get_nested_string('payload', ['defense', 'overall'])) }},
           null, null, null
    from ppa

)

select
    season,
    rating_system,
    team,
    conference,
    rating,
    rating_rank,
    offense_rating,
    defense_rating,
    special_teams_rating,
    strength_of_schedule,
    second_order_wins
from unioned
where team is not null
