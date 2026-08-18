{{ config(materialized='table') }}

-- One row per (season, season_type, week).
--
-- `season_type` is part of the key, never an afterthought column: Postseason Week 1 is not
-- Regular Season Week 1, and collapsing them silently merges the opening slate with the
-- national championship.
--
-- KNOWN CONSTRAINT: CFBD serves no /calendar before 2002, so this dimension covers 25 of
-- the 157 seasons in fct_game. Any week-grain join loses everything earlier. That floor is
-- asserted by a test rather than left as folklore — if CFBD ever extends coverage the test
-- fails, which is correct: the constraint must be re-documented, not silently widened.

select
    {{ surrogate_key(['season', 'season_type', 'week']) }} as week_sk,
    season,
    season_type,
    week,
    start_at,
    end_at,
    first_game_at,
    last_game_at,
    {{ to_utc_date('start_at') }} as start_date,
    {{ to_utc_date('end_at') }}   as end_date
from {{ ref('stg_calendar') }}
