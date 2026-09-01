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
    -- `team` or `opponent`. CFBD ships the opponent variant of a statistic as a SEPARATE
    -- stat with an `Opponent` suffix, so without this the picker lists firstDowns and
    -- firstDownsOpponent as unrelated entries and a reader has to know the convention.
    -- Derived in the fact, not here and not in the page — see fct_team_season_stat.
    s.stat_scope,
    -- The statistic with its scope stripped, so a page can put what a team did beside what
    -- it allowed. Without it the two live under different names and nothing joins them.
    s.stat_base_name,
    -- `raw` on every row today. /stats/season is unadjusted; opponent-adjusted figures come
    -- from a different endpoint and a different fact, and charting one against the other
    -- would compare two different things.
    s.stat_basis,
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
    ) as numeric), 4) as percentile,
    ao_src.as_of_ts,
    t.team_slug,
    t.team_display,
    t.logo_source_url as logo_url,
    t.conference
from {{ ref('fct_team_season_stat') }} s
left join {{ ref('dim_team') }} t on t.season = s.season and t.team_id = s.team_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'stats') ao_src
where s.stat_value is not null
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
