{{ config(materialized='table') }}

-- One row per (season, player, TEAM). Season-scoped, like dim_team and for the same reason:
-- every page asks "what was true in season X", and a player's team, class, height and weight
-- all move between seasons.
--
-- TEAM IS IN THE GRAIN BECAUSE A PLAYER CAN BE ON TWO ROSTERS IN ONE SEASON. That is
-- stg_roster's finding and it survives into the dimension unchanged — a mid-season move
-- leaves the player listed by both schools, same id, same name, two rows, both true. Keying
-- on (season, player_id) would look correct on any sample missing those cases and would
-- silently drop one row per transfer.
--
-- THE TEAM ID IS NULLABLE, AND THAT IS NOT A JOIN FAILURE.
--
-- stg_roster carries a team NAME and no id, so the id is resolved against dim_team by name
-- within season. Measured: 99.32% / 99.45% / 100.00% for 2024 / 2025 / 2026, and every one
-- of the 321 misses is a school like Virginia Lynchburg, Warner or Ave Maria — NAIA and
-- Division II programmes that appear on a roster feed but are legitimately absent from
-- CFBD's /teams response.
--
-- This is exactly the case team_identity() was written for: /games and /rosters know who
-- played, /teams knows who is an FBS programme, and the first set is larger. An inner join
-- here would drop 321 real athletes to make a number look tidy. They keep their row, their
-- name and a null team_id, and `is_listed_team` says which is which.
--
-- THE SLUG CARRIES THE PLAYER ID, BECAUSE NAMES COLLIDE FAR MORE THAN THEY LOOK LIKE THEY
-- WOULD. 1,343 (season, first name, last name) combinations map to more than one athlete —
-- there are nine distinct Jayden Williamses, eight Jalen Smiths and seven Cam Smiths in the
-- roster feed. A name-only slug would route all nine to one page and no test on a small
-- sample would catch it.
--
-- CLASS YEAR IS 1-4 OR IT IS UNKNOWN — CFBD SOMETIMES SENDS THE SEASON INSTEAD.
--
-- stg_roster's header already warns that the wire's `year` is the class year and not the
-- season. It is worse than that: on 2,451 rows the field holds the SEASON after all, and
-- always the row's own season — 1,336 rows of "2024" in 2024 and 1,115 of "2025" in 2025,
-- plus 46 zeros. 2026 is clean, so this is an upstream inconsistency rather than a rule.
--
-- Anything outside 1-4 is therefore treated as unknown rather than mapped. `class_year_raw`
-- keeps whatever arrived, so the anomaly stays visible instead of being laundered into a
-- plausible-looking freshman.

with roster as (

    select * from {{ ref('stg_roster') }}

),

resolved as (

    select
        r.*,
        t.team_id,
        t.team_slug   as dim_team_slug,
        t.team_display as dim_team_display,
        t.conference,
        t.classification,
        t.logo_source_url,
        t.color_on_light,
        t.color_on_dark
    from roster r
    left join {{ ref('dim_team') }} t
        on t.season = r.season and t.school = r.team

),

named as (

    select
        *,
        -- Both parts are populated on every row in the feed, but a trailing space from a
        -- missing half would render as a stray gap, so the join is trimmed.
        trim(coalesce(first_name, '') || ' ' || coalesce(last_name, '')) as full_name,
        -- 1-4 only. See the header: anything else is CFBD sending the season.
        case when class_year between 1 and 4 then class_year end as class_year_clean
    from resolved

)

select
    {{ surrogate_key(['season', 'player_id', 'team']) }} as athlete_sk,
    season,
    player_id,
    full_name,
    first_name,
    last_name,
    -- Name AND id. Nine Jayden Williamses share the first half; only the id separates them.
    {{ to_slug('full_name') }} || '-' || player_id        as athlete_slug,

    team,
    team_id,
    -- The dimension does not cover the roster's key space; fall back to the roster's own
    -- name so a non-FBS athlete still renders and still links somewhere honest.
    coalesce(dim_team_slug, {{ to_slug('team') }})        as team_slug,
    coalesce(dim_team_display, team)                      as team_display,
    -- Whether dim_team had a row. FALSE means an NAIA or Division II programme absent from
    -- /teams, not a broken join — see the header.
    team_id is not null                                   as is_listed_team,
    conference,
    classification,
    logo_source_url,
    color_on_light,
    color_on_dark,

    position,
    jersey,
    class_year_clean                                      as class_year,
    -- What arrived on the wire, kept so the upstream anomaly stays countable.
    class_year                                            as class_year_raw,
    case class_year_clean
        when 1 then 'FR' when 2 then 'SO' when 3 then 'JR' when 4 then 'SR'
    end                                                   as class_year_display,

    height_inches,
    -- Feet and inches, assembled here rather than in the app: a height is one fact with a
    -- conventional rendering, the same argument as record_display on srv_standings.
    case when height_inches is not null
         then cast(height_inches / 12 as {{ dbt.type_string() }}) || '-'
              || cast(height_inches % 12 as {{ dbt.type_string() }}) end as height_display,
    weight_pounds,

    home_city,
    home_state,
    home_country,
    -- Null rather than a lone comma when the city is missing, so the page renders an em dash
    -- (AC-G.32) instead of stray punctuation.
    case when home_city is not null and home_state is not null
         then home_city || ', ' || home_state
         else coalesce(home_city, home_state) end         as hometown_display,
    home_latitude,
    home_longitude,
    home_fips_code,
    -- JSON array. The bridge back to stg_recruit; see stg_roster's header.
    recruit_ids
from named
