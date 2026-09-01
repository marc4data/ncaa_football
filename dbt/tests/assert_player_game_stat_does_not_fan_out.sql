-- The game, team and athlete joins must not multiply or drop a box-score row.
--
-- Three left joins and one inner join sit between the source and this fact, and each is a
-- fan-out risk: dim_team is unique per (season, team_id) but joined by NAME, dim_athlete's
-- grain includes team, and fct_game is joined on an id that must be unique.
--
-- The inner join to fct_game is the loss risk — it matched 100.00% when built, but a game
-- arriving in the box-score feed before the game spine has it would silently drop every
-- player in it. Exact parity catches both directions.
with source_rows as (select count(*) as n from {{ ref('stg_game_player_stat') }}),
     fact_rows   as (select count(*) as n from {{ ref('fct_player_game_stat') }})
select source_rows.n as staging_rows, fact_rows.n as fact_rows
from source_rows, fact_rows
where source_rows.n <> fact_rows.n
