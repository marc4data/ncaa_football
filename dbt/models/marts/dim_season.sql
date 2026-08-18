{{ config(materialized='table') }}

-- One row per season.
--
-- Deliberately thin. This exists so `season` is a joinable key with attributes rather than
-- an integer scattered across every fact, and so a page can ask "which seasons do we have,
-- and what is the current one" without scanning the game spine.

with games as (

    select
        season,
        min(start_date) as first_game_at,
        max(start_date) as last_game_at,
        count(*)        as game_count,
        max(case when season_type = 'postseason' then 1 else 0 end) as has_postseason_flag
    from {{ ref('stg_games') }}
    group by season

)

select
    season,
    cast(season as {{ dbt.type_string() }}) as season_label,
    {{ to_utc_date('first_game_at') }} as first_game_date,
    {{ to_utc_date('last_game_at') }}  as last_game_date,
    game_count,
    has_postseason_flag = 1 as has_postseason,
    season = (select max(season) from games) as is_current_season
from games
