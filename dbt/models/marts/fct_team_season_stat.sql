{{ config(materialized='table', tags=['stats']) }}
-- One row per team x season x stat name. Accumulating snapshot: CFBD revises the season
-- total as games are played, and we hold the latest fetch rather than a history.
--
-- Grain note. The matrix specifies `team x season x through_week`. That column is not
-- obtainable from this endpoint as we call it: /stats/season accepts startWeek/endWeek
-- parameters and we request neither, so every row is the full-season-to-date figure.
-- `through_week` is therefore omitted rather than invented — adding it as a constant would
-- imply a slice we never asked for.
--
-- The join hazard: /stats/season carries the team NAME and no team id, so the id has to be
-- recovered from dim_team on (season, school). Unmatched rows are kept with a null
-- team_sk rather than dropped — an unresolvable name is a data-quality signal, and
-- discarding it would hide a school CFBD renamed mid-history.
select
    {{ surrogate_key(['s.season', 's.school', 's.stat_name']) }} as team_season_stat_sk,
    s.season,
    t.team_id,
    {{ surrogate_key(['s.season', 't.team_id']) }} as team_sk,
    s.school,
    s.conference_name,
    s.stat_name,
    s.stat_value_raw,
    -- Numeric where the value permits it, null where it does not. Both are kept so a page
    -- can display the source text while a chart uses the number.
    {{ safe_numeric('s.stat_value_raw') }} as stat_value,
    t.team_id is null as is_unresolved_team
from {{ ref('stg_team_season_stat') }} s
left join {{ ref('dim_team') }} t
    on t.season = s.season and t.school = s.school
