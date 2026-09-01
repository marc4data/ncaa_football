-- Players page: season stats, one row per player x season x category x stat type.
--
-- The page's primary view and the one the registry names as its blocker. Long, matching the
-- fact, for the reason srv_team_stats is long: CFBD's stat types are open-ended and a wide
-- table would silently omit whatever it adds next.
--
-- RANKS ARE COMPUTED HERE, NOT IN THE FACT. Ranking within (season, category, stat type) is
-- exactly the window function the app is forbidden to run, and it is a presentation concern —
-- the fact should not privilege one population over another.
--
-- COLUMNS ARE DELIBERATELY NARROWER THAN THE FACT. Serving tables are pg_dump'd and shipped
-- over a ~20 Mbit/s link on every publish, and that upload is already the pipeline's most
-- fragile step. stat_raw, athlete_sk and the dimension-coverage flag are all real columns on
-- fct_player_season_stat and none of them are things a page renders, so they stay behind.
--
-- Zero-valued rows are KEPT. 38.1% of the fact is zeros, and dropping them would halve this
-- table — but "0 interceptions" is a fact about a season and its absence is not. A page that
-- cannot distinguish a zero from an unrecorded stat is the em-dash-versus-nought confusion
-- this project has fixed three times elsewhere.
select
    s.player_season_stat_sk,
    s.season,
    s.player_id,
    s.player_slug,
    s.player_name,
    s.position,
    s.team,
    s.team_id,
    s.conference,
    s.stat_category,
    s.stat_type,
    s.stat_value,
    -- Both directions, because the warehouse does not know which way a given stat reads and
    -- the page must not decide with arithmetic. Same reasoning as srv_team_stats.
    rank() over (partition by s.season, s.stat_category, s.stat_type
                 order by s.stat_value desc nulls last)      as rank_desc,
    rank() over (partition by s.season, s.stat_category, s.stat_type
                 order by s.stat_value asc nulls last)       as rank_asc,
    round(cast(percent_rank() over (
        partition by s.season, s.stat_category, s.stat_type
        order by s.stat_value asc nulls last) as numeric), 4) as percentile,
    -- The n the rank was computed over. Without it "40th" is unreadable — 40 of 2,000 and
    -- 40 of 45 are different statements.
    count(*) over (partition by s.season, s.stat_category, s.stat_type)
                                                             as rank_population,
    s.class_year_display,
    s.height_display,
    s.weight_pounds,
    s.jersey,
    ao.as_of_ts
from {{ ref('fct_player_season_stat') }} s
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'stats') ao
