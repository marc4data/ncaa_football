-- Team page, Roster section: one row per player on a team's roster in a season.
--
-- 68,357 rows across 2024-2026, which is every season cfdb holds a roster feed for. A team
-- page for 2019 has no roster and says so rather than rendering an empty table — /roster is
-- `recent` scope and that is not a defect.
--
-- Straight off dim_athlete with no aggregation: the dimension's grain is already
-- (season, player, team), which is exactly a roster. The section exists as its own view
-- rather than as columns on srv_team_overview because that view is one row per team-season
-- and this is many rows per team-season — a different grain is a different relation, and the
-- site reads one relation per query.
--
-- Ordered by position then jersey in the page rather than here, because a serving table has
-- no inherent order and a page that relies on one is relying on a coincidence.
select
    a.athlete_sk,
    a.season,
    a.player_id,
    a.athlete_slug                as player_slug,
    a.full_name,
    a.first_name,
    a.last_name,
    a.team,
    a.team_id,
    a.team_slug,
    a.team_display,
    a.conference,
    a.classification,
    a.is_listed_team,
    a.position,
    a.jersey,
    a.class_year,
    a.class_year_display,
    a.height_inches,
    a.height_display,
    a.weight_pounds,
    a.home_city,
    a.home_state,
    a.hometown_display,

    -- ── DOES THIS PLAYER HAVE A SEASON-STATS ROW? (A177, cfdb-main-R-1768) ─────────────────
    --
    -- 🚨 THE ROSTER LINKS EVERY NAME AND MOST OF THEM GO NOWHERE. A172 measured it and
    -- refused to guess from the page, which was right: whether a player resolves is a fact
    -- about another relation, and asking the page to find out is a join (G-2).
    --
    -- 📊 RE-MEASURED BY A177, AND THE NUMBERS MOVE AS A SEASON FILLS — which is the reason
    -- this is a published column rather than a constant anyone could hardcode:
    --
    --     season   roster rows   resolve to a season-stats row
    --     2024        22,843     60.63%   (A172 measured 56.84%)
    --     2025        30,072     48.04%   (A172 measured 45.38%)
    --     2026        31,070     40.89%   (A172 measured 38.89%)
    --
    -- ⚠️ A BOOLEAN, NOT A COUNT. The page's question is "does this name resolve", which is
    -- exactly what `table.team_link` refuses to answer blind — a link to an empty player page
    -- is worse than plain text, and a count would invite the page to decide a threshold.
    --
    -- ⚠️ A JOIN TO A DISTINCT SET, NOT A CORRELATED `exists`, AND THE DIFFERENCE WAS MEASURED
    -- RATHER THAN ASSUMED (§5.2). The first draft here was
    -- `exists (select 1 from fct_player_season_stat s where s.season = a.season and ...)`.
    -- 🚨 **It ran for ten and a half minutes against the real warehouse and held
    -- `AccessShareLock` on the fact while it did — blocking a live Airflow `dbt run` for four
    -- minutes until it was cancelled.** That is A106's incident exactly, caused by this line.
    -- The grouped form below answers the same question in seconds, because the distinct set is
    -- built once instead of being re-probed per roster row.
    --
    -- ⚠️ `distinct` IS LOAD-BEARING AND IS NOT DECORATION. `fct_player_season_stat` is one row
    -- per player x season x category x stat type, so joining it raw would multiply a roster by
    -- the number of statistics a player recorded. The distinct reduces it to the semi-join
    -- this needs and keeps the view one row per roster place.
    ps.player_id is not null      as has_player_stats,

    ao.as_of_ts
from {{ ref('dim_athlete') }} a
left join (
    select distinct season, player_id from {{ ref('fct_player_season_stat') }}
) ps on ps.season = a.season and ps.player_id = a.player_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'roster') ao
