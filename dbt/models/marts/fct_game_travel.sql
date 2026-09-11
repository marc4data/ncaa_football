{{ config(materialized='table') }}

-- One row per (game, team): how far that team travelled and how long they had to rest.
--
-- The Matchup page listed travel and elevation as blocked because "dim_venue has no join key
-- to fct_game, which carries a venue NAME and no usable venue id". /games/weather turned out
-- to carry venueId on every row, matching dim_venue 6,847 of 6,847, so the key existed all
-- along on an endpoint nobody had read. This model is what that unlocked.
--
-- TWO MEASURES WITH DIFFERENT COVERAGE, AND THE MODEL DOES NOT AVERAGE OVER THE DIFFERENCE.
--
--   rest_days     computable for every game, from the schedule alone
--   travel_miles  needs coordinates for BOTH venues, so 2024+ and only where weather landed
--
-- Reporting travel as 0 where a venue is unknown would be the null-not-zero mistake this
-- project keeps finding: 0 miles means "played at home", and it must not also mean "we do not
-- know". Unknown stays null.
--
-- ⚠️ EVERY MEASURE SHIPS IN THE READER'S UNIT AND IN THE SOURCE'S (R-634). Marc asked for miles
-- and feet; CFBD supplies metres. The conversion is a multiplication, so it is here rather than
-- in the page — and both units come off ONE unrounded measurement, so they cannot disagree.
--
-- HOME VENUE IS DERIVED, NOT DECLARED. CFBD has no "this team's stadium" field, so a team's
-- home venue for a season is the venue it played most of its non-neutral home games at. That
-- is a mode rather than a lookup, and it is the honest construction: a team that splits a
-- season between two stadiums gets the one it actually used most, and a team with no home
-- game on record gets none rather than a guess.
--
-- NEUTRAL SITES COUNT AS TRAVEL FOR BOTH SIDES. A bowl game is a trip for everyone, and the
-- home/away label on it is a scheduling artefact rather than a fact about geography.
--
-- REST IS WITHIN A SEASON. The gap between a bowl game and the next September is not rest in
-- any sense a reader means, so the first game of a season has null rest days rather than a
-- number counted from the previous one.

with home_venue as (

    -- The venue a team played most of its non-neutral home games at, per season.
    -- Counted first, THEN ranked. A window function cannot be nested inside another
    -- window's ORDER BY, so the tempting single-pass version does not compile — and the
    -- two-step form is clearer about what a mode actually is.
    select season, team_id, venue_id, latitude, longitude, elevation_m
    from (
        select
            season, team_id, venue_id, latitude, longitude, elevation_m,
            row_number() over (
                partition by season, team_id
                -- Most-used venue first; venue_id only to make ties deterministic across
                -- engines rather than because a lower id means anything.
                order by home_games desc, venue_id
            ) as rank_for_team
        from (
            select
                w.season,
                g.home_team_id      as team_id,
                w.venue_id,
                -- Constant per venue, so any aggregate picks the same value; min is the
                -- cheapest way to carry it through the group by.
                min(w.latitude)     as latitude,
                min(w.longitude)    as longitude,
                min(w.elevation_m)  as elevation_m,
                count(*)            as home_games
            from {{ ref('fct_game_weather') }} w
            join {{ ref('fct_game') }} g on g.game_id = w.game_id
            where not g.is_neutral_site
              and w.venue_id is not null
              and w.latitude is not null
            group by w.season, g.home_team_id, w.venue_id
        ) counted
    ) ranked
    where rank_for_team = 1

),

scheduled as (

    select
        gt.game_team_sk,
        gt.game_id,
        gt.team_id,
        gt.team,
        gt.opponent_team_id,
        gt.opponent,
        gt.season,
        gt.week,
        gt.season_type,
        gt.game_date,
        gt.is_home,
        gt.is_neutral_site,
        gt.is_completed,
        -- Within season and team. See the header: a cross-season gap is not rest.
        lag(gt.game_date) over (
            partition by gt.season, gt.team_id order by gt.game_date, gt.game_id
        ) as previous_game_date
    from {{ ref('fct_game_team') }} gt

),

located as (

    select
        s.*,
        w.venue_id                          as game_venue_id,
        w.venue                             as game_venue,
        w.latitude                          as game_latitude,
        w.longitude                         as game_longitude,
        w.elevation_m                       as game_elevation_m,
        h.venue_id                          as home_venue_id,
        h.latitude                          as home_latitude,
        h.longitude                         as home_longitude,
        h.elevation_m                       as home_elevation_m
    from scheduled s
    left join {{ ref('fct_game_weather') }} w on w.game_id = s.game_id
    left join home_venue h
        on h.season = s.season and h.team_id = s.team_id

),

measured as (

    -- ⚠️ EACH DISTANCE IS COMPUTED ONCE HERE AND RENDERED TWICE BELOW. R-634: Marc asked for
    -- "all distance measurements in miles, elevation measurements in feet", and the tempting
    -- shortcut is `travel_km * 0.621371` in the select below — which multiplies a figure that
    -- has ALREADY been rounded to one decimal. That makes the miles column disagree with its
    -- own kilometres column by up to a tenth of a kilometre's worth of miles, for no reason.
    -- Round once per unit, from the same unrounded measurement.
    select l.*,
           -- Great-circle distance from the team's own home venue to where this game was
           -- played. Haversine, spelled out rather than taken from an extension so it compiles
           -- on both engines. 6371 km is the mean Earth radius; the error from treating the
           -- planet as a sphere is a few tenths of a percent, far below anything a
           -- rest-and-travel story turns on.
           --
           -- NULL when either end is unknown, never 0. Zero here means the team played at home.
           case when game_latitude is not null and home_latitude is not null
                then cast(
                     2 * 6371 * asin(sqrt(
                         power(sin(radians(cast(game_latitude as {{ dbt.type_numeric() }})
                                           - cast(home_latitude as {{ dbt.type_numeric() }})) / 2), 2)
                       + cos(radians(cast(home_latitude as {{ dbt.type_numeric() }})))
                       * cos(radians(cast(game_latitude as {{ dbt.type_numeric() }})))
                       * power(sin(radians(cast(game_longitude as {{ dbt.type_numeric() }})
                                           - cast(home_longitude as {{ dbt.type_numeric() }})) / 2), 2)
                     )) as {{ dbt.type_numeric() }})
           end                                            as travel_km_unrounded,

           -- Altitude gained relative to home. Denver is the reason this is signed rather than
           -- absolute: arriving 1,500 m higher and 1,500 m lower are different experiences, and
           -- a magnitude would erase which one happened.
           case when game_elevation_m is not null and home_elevation_m is not null
                then cast(game_elevation_m - home_elevation_m as {{ dbt.type_numeric() }})
           end                                            as elevation_change_m_unrounded
    from located l

)

select
    {{ surrogate_key(['game_id', 'team_id']) }}           as game_travel_sk,
    game_team_sk,
    game_id,
    team_id,
    team,
    opponent_team_id,
    opponent,
    season,
    week,
    season_type,
    game_date,
    is_home,
    is_neutral_site,
    is_completed,

    game_venue_id,
    game_venue,
    game_latitude,
    game_longitude,
    game_elevation_m,
    home_venue_id,
    home_latitude,
    home_longitude,
    home_elevation_m,

    -- ── R-634: THE READER'S UNITS ARE MILES AND FEET ──────────────────────────────────────
    --
    -- Marc, 2026-09-11: "all distance measurements in miles, elevation measurements in feet."
    -- 🚨 A UNIT CONVERSION IS A MULTIPLICATION, SO IT BELONGS HERE AND NOT IN THE PAGE. B085
    -- raised this and correctly refused to do it in Streamlit — the same rule that keeps
    -- `yards / games_counted` out of matchup.py.
    --
    -- ⚠️ THE METRIC COLUMNS STAY FOR NOW, AND THAT IS A HANDOVER RATHER THAN A DUPLICATION.
    -- §3 rule 3.1: a shared change ships the column and the default; the call site is the
    -- other session's to consume on its own round. `site/views/matchup.py` reads travel_km
    -- and elevation_change_m TODAY, so deleting them here would break a live page belonging
    -- to session B. Once B reads the miles/feet columns, dropping the metric pair is a
    -- one-line follow-up — and it should happen, because two units of one measurement is a
    -- column pair that invites a reader to compare them.
    --
    -- The factors are exact by definition, not approximations: an international mile is
    -- 1.609344 km exactly, and an international foot is 0.3048 m exactly. Written as the
    -- reciprocals used here rather than as divisions so the arithmetic reads in one direction.
    round(travel_km_unrounded, 1)                         as travel_km,
    round(travel_km_unrounded / 1.609344, 1)              as travel_miles,

    round(elevation_change_m_unrounded, 1)                as elevation_change_m,
    -- Feet to the nearest whole foot: a tenth of a foot is below the precision of the source
    -- elevation and printing it would claim accuracy this does not have.
    round(elevation_change_m_unrounded / 0.3048, 0)       as elevation_change_ft,

    -- The two absolute elevations the change is derived from, in the reader's unit as well.
    -- Carried because "3,000 ft higher than home" and "at 7,000 ft" are different facts and a
    -- reader asking about altitude usually wants the second one.
    round(cast(game_elevation_m as {{ dbt.type_numeric() }}) / 0.3048, 0) as game_elevation_ft,
    round(cast(home_elevation_m as {{ dbt.type_numeric() }}) / 0.3048, 0) as home_elevation_ft,

    previous_game_date,
    -- Null on a team's first game of a season, which is an absence of a previous game rather
    -- than a long rest.
    case when previous_game_date is not null
         then {{ days_between('game_date', 'previous_game_date') }}
    end                                                   as rest_days,
    -- The reader-facing bucket. A short week is the thing people actually ask about, and
    -- the boundaries are the conventional ones rather than anything derived here.
    case when previous_game_date is null then 'season opener'
         when {{ days_between('game_date', 'previous_game_date') }} <= 5 then 'short week'
         when {{ days_between('game_date', 'previous_game_date') }} <= 8 then 'normal week'
         when {{ days_between('game_date', 'previous_game_date') }} <= 14 then 'extra rest'
         else 'long layoff' end                           as rest_bucket
from measured
