{{ config(materialized='table', tags=['ratings']) }}
-- One row per (season, team, rating system). B1.
--
-- NOT `fct_team_week_rating`, and the name change is the finding rather than a preference.
-- The requirements assume week grain; CFBD's own spec says four of the five systems cannot
-- provide it, and the one that can — /ratings/elo — has only ever been fetched with a year.
-- Building a week-grain model today would mean forward-filling a season-final SP+ across
-- fourteen weeks, which fabricates a time series that never happened and would look
-- entirely convincing. Same class as an ats record of 0-0-0 for a season nobody played.
--
-- TWO FLAGS CARRY WHAT THE GRAIN CHECK FOUND, because both distinctions are invisible in
-- the numbers themselves and both change what a reader should conclude.
--
-- `rating_scope` — 'season' for every row today. It exists so that a weekly Elo backfill
-- adds rows rather than changing the meaning of existing ones, and so a page can ask for a
-- time series and get an honest empty answer instead of a flat line.
--
-- `is_projection` — whether the rating describes games PLAYED or games EXPECTED. This is
-- the one that matters in weeks 1 to 4, and it is not a property of the system alone: SP+
-- in August is a projection and SP+ in November is a measurement. It is derived from
-- whether the team has completed a game that season, which is the honest test and needs no
-- lookup table.
--
-- Measured today, 20 August 2026:
--   sp_plus  139 rows for 2026   projection
--   fpi      138 rows for 2026   projection
--   elo        0 rows for 2026   results-derived, nothing to compute yet
--   srs        0
--   ppa        0
--
-- So the ratings available before Week 0 are exactly the two that are FORECASTS. A page
-- showing a preseason SP+ beside an empty Elo without saying which is which would imply
-- they are the same kind of number.
with rated as (

    select
        r.season,
        r.rating_system,
        r.team,
        r.conference,
        r.rating,
        r.rating_rank,
        r.offense_rating,
        r.defense_rating,
        r.special_teams_rating,
        r.strength_of_schedule,
        r.second_order_wins
    from {{ ref('stg_team_rating') }} r
    -- SP+ publishes a synthetic `nationalAverages` row alongside the teams. It is a
    -- reference value, not a programme, and leaving it in a TEAM fact would put it on the
    -- Teams index, give it a team page, and — worst — include it in the percentile
    -- denominator, where it would shift every team's standing by a fraction that nobody
    -- would ever trace back. Excluded here rather than filtered per consumer.
    where r.team <> 'nationalAverages'

),

-- Has this team played a completed game this season? That is what makes a rating a
-- measurement rather than a forecast, and it is knowable from the game spine — no list of
-- which systems are projections, which would be wrong the first time one changed.
played as (

    select season, team_id, count(*) as completed_games
    from {{ ref('fct_game_team') }}
    where is_completed and points_for is not null
    group by season, team_id

)

select
    {{ surrogate_key(['r.season', 'r.rating_system', 'r.team']) }} as team_rating_sk,
    r.season,
    r.rating_system,
    -- The team dimension is joined for the id and the identity, but the NAME still comes
    -- from the ratings payload where dim_team has no row: /ratings covers programmes
    -- /teams does not list in every season, which is the same key-space mismatch that left
    -- 11% of the scoreboard unnamed.
    t.team_id,
    coalesce(t.school, r.team)      as school,
    coalesce(t.conference, r.conference) as conference,
    t.classification,
    r.rating,
    r.rating_rank,
    r.offense_rating,
    r.defense_rating,
    r.special_teams_rating,
    r.strength_of_schedule,
    r.second_order_wins,
    -- Season scope for every row today. See the header: this is a column rather than an
    -- assumption so a weekly backfill is additive.
    cast('season' as {{ dbt.type_string() }}) as rating_scope,
    cast(null as {{ dbt.type_int() }})        as week,
    coalesce(p.completed_games, 0) = 0        as is_projection,
    coalesce(p.completed_games, 0)            as completed_games_at_rating,

    -- Rank and percentile WITHIN (season, system, classification), computed here so no
    -- page ever orders by a rating and calls the row number a rank. Partitioned by
    -- classification because an FCS team's SRS is not comparable to an FBS team's, and
    -- SRS is the one system that publishes both — 266 rows against 137 for SP+.
    --
    -- Percentile is `percent_rank`, which puts the best team at 1.0 and the worst at 0.0,
    -- matching srv_team_stats so the two read the same way on one page.
    row_number() over (
        partition by r.season, r.rating_system, t.classification
        order by r.rating desc nulls last
    ) as rating_rank_computed,
    round(cast(percent_rank() over (
        partition by r.season, r.rating_system, t.classification
        order by r.rating asc nulls first
    ) as numeric), 4) as rating_percentile
from rated r
left join {{ ref('dim_team') }} t
    on t.season = r.season and t.school = r.team
left join played p
    on p.season = r.season and p.team_id = t.team_id
