-- Stats page: one row per team x season x stat.
--
-- Long, matching the fact. The page's stat picker is a WHERE clause, and CFBD serves 63
-- stat names that it adds to — a wide table would need a code change to show a new stat and
-- would silently omit it until someone noticed.
--
-- The rank columns are the reason this is a serving model rather than a view over the fact:
-- ranking within season and stat is exactly the kind of window function the app must not
-- run, and precomputing it is what lets the page sort without knowing any business rules.
select
    s.team_season_stat_sk,
    s.season,
    s.team_id,
    s.school,
    s.conference_name,
    s.stat_name,
    s.stat_value,
    s.stat_value_raw,
    t.classification,
    t.color_raw       as color_primary,
    t.color_on_light,
    t.logo_path,
    rank() over (partition by s.season, s.stat_name order by s.stat_value desc nulls last)
        as rank_desc,
    rank() over (partition by s.season, s.stat_name order by s.stat_value asc nulls last)
        as rank_asc,
    round(cast(percent_rank() over (
        partition by s.season, s.stat_name order by s.stat_value asc nulls last
    ) as numeric), 4) as percentile
from {{ ref('fct_team_season_stat') }} s
left join {{ ref('dim_team') }} t on t.season = s.season and t.team_id = s.team_id
where s.stat_value is not null
