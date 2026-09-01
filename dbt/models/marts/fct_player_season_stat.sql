{{ config(materialized='table') }}

-- One row per (season, player, category, stat type). Long, matching the source.
--
-- 1,453,075 rows over 23 seasons, 2004-2026: 65,181 players, 30 stat types across 10
-- categories. This is the deepest player history in the warehouse and the primary fact
-- behind the Players page.
--
-- LONG RATHER THAN WIDE, for the reason srv_team_stats is long: CFBD's stat types are
-- open-ended and it adds to them. A wide table needs a code change to show a new stat and
-- silently omits it until somebody notices. The page's stat picker is a WHERE clause.
--
-- THE DIMENSION DOES NOT COVER THIS FACT, AND THE GAP IS 20 SEASONS WIDE.
--
-- dim_athlete is built from /roster, which cfdb holds for 2024-2026 only. This fact runs
-- back to 2004. Measured match rates against dim_athlete on (season, player_id, team):
--
--   2024   99.99%
--   2025  100.00%
--   2026   11.77%     <- rosters land through the season; stats are already accumulating
--   <=2023  0.00%     <- no roster feed exists for those seasons at all
--
-- So identity is carried ON THIS FACT — name, position, team, conference all arrive on the
-- stat row — and dim_athlete is joined only to ENRICH. An inner join would delete two
-- decades of player history to satisfy a foreign key, which is the tail wagging the dog.
--
-- The same reasoning gives the slug: derived here from name and player id rather than read
-- off dim_athlete, so a 2007 season page links exactly as well as a 2025 one. It matches
-- dim_athlete.athlete_slug by construction wherever both exist.
--
-- THE JOIN IS ON THREE COLUMNS, NOT TWO. dim_athlete's grain includes team because ten
-- players appear on two rosters in one season. Joining on (season, player_id) alone would
-- duplicate every stat row for those ten. Verified: the three-column join returns exactly
-- 1,453,075 rows, so it neither multiplies nor drops.
--
-- RANKS ARE NOT HERE. They live in srv_player_stats, following srv_team_stats — ranking is
-- a presentation concern computed over whatever population the page is showing, and the
-- fact should not privilege one.

with stats as (

    select * from {{ ref('stg_player_season_stat') }}

),

enriched as (

    select
        s.*,
        a.athlete_sk,
        a.team_id,
        a.class_year_display,
        a.height_display,
        a.weight_pounds,
        a.jersey
    from stats s
    -- Three columns. See the header: two would fan out the dual-roster players.
    left join {{ ref('dim_athlete') }} a
        on  a.season    = s.season
        and a.player_id = s.player_id
        and a.team      = s.team

)

select
    {{ surrogate_key(['season', 'player_id', 'stat_category', 'stat_type']) }}
        as player_season_stat_sk,
    season,
    player_id,
    player_name,
    -- Derived here, not read off the dimension, so pre-2024 seasons still link. Name AND
    -- id, because 1,343 name-and-season combinations map to more than one athlete.
    {{ to_slug('player_name') }} || '-' || player_id      as player_slug,
    position,
    team,
    team_id,
    conference,

    stat_category,
    stat_type,
    -- Every one of the 1,453,075 values parses as a number; measured, not assumed. The raw
    -- string is kept anyway, so a type CFBD starts sending in another shape stays visible
    -- rather than silently becoming null.
    {{ safe_numeric('stat_raw') }}                        as stat_value,
    stat_raw,

    athlete_sk,
    -- Whether dim_athlete had a row. FALSE for every season before 2024 and most of 2026 —
    -- an absent roster feed, not a broken join. See the header.
    athlete_sk is not null                                as has_athlete_dimension,
    class_year_display,
    height_display,
    weight_pounds,
    jersey
from enriched
