-- The dim_athlete join must not multiply or drop a stat row.
--
-- fct_player_season_stat joins dim_athlete on three columns because the dimension's grain
-- includes team: ten players appear on two rosters in one season, and a two-column join on
-- (season, player_id) would silently double every stat row belonging to them — around 300
-- rows, invisible in a 1.45M-row total and wrong in every aggregate built on it.
--
-- The loss direction matters just as much: an inner join would delete 20 seasons of player
-- history to satisfy a foreign key dim_athlete cannot supply before 2024.
--
-- Both are caught by asserting exact parity with the source.
with source_rows as (select count(*) as n from {{ ref('stg_player_season_stat') }}),
     fact_rows   as (select count(*) as n from {{ ref('fct_player_season_stat') }})
select source_rows.n as staging_rows, fact_rows.n as fact_rows
from source_rows, fact_rows
where source_rows.n <> fact_rows.n
