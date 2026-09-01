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
    -- SCOPE IS IN THE NAME, AND CFBD IS CONSISTENT ABOUT IT.
    --
    -- The opponent variant of a statistic is a SEPARATE stat with an `Opponent` suffix:
    -- firstDowns and firstDownsOpponent are two entries, not one stat with a flag. Measured
    -- across all 63 stat names: 31 carry the suffix, 32 do not, and every one of those 32
    -- has a matching Opponent counterpart except `games`, which is a count of fixtures and
    -- correctly has none.
    --
    -- Deriving this in the APP would be the app inventing a dimension the warehouse does not
    -- have, which is why the Stats page refused to. Deriving it HERE is different: it is a
    -- documented transformation with a test behind it, and
    -- assert_every_team_stat_has_its_opponent_counterpart fails loudly the first time CFBD
    -- names something differently — which is exactly the failure the page was right to fear
    -- and wrong to be unable to detect.
    case when s.stat_name like '%Opponent' then 'opponent' else 'team' end as stat_scope,
    -- The statistic itself, with scope stripped, so a page can put a team's figure beside
    -- what it allowed. Without this the two live under different names and nothing joins them.
    case when s.stat_name like '%Opponent'
         then left(s.stat_name, length(s.stat_name) - length('Opponent'))
         else s.stat_name end                                          as stat_base_name,
    -- RAW ON EVERY ROW TODAY, and the column exists so that stays visible rather than
    -- assumed. /stats/season returns unadjusted totals; opponent-adjusted figures come from
    -- /stats/season/advanced and land in a different fact. A page charting an adjusted
    -- number against a raw one would be comparing two different things, and a constant here
    -- is what lets it check rather than guess. Same reasoning as rating_scope on
    -- fct_team_rating, which is 'season' on every row for the same kind of reason.
    'raw'                                                              as stat_basis,
    s.stat_value_raw,
    -- Numeric where the value permits it, null where it does not. Both are kept so a page
    -- can display the source text while a chart uses the number.
    {{ safe_numeric('s.stat_value_raw') }} as stat_value,
    t.team_id is null as is_unresolved_team
from {{ ref('stg_team_season_stat') }} s
left join {{ ref('dim_team') }} t
    on t.season = s.season and t.school = s.school
