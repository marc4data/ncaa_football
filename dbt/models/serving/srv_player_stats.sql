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
-- ⚠️ A177: TWO STAGES, BECAUSE A WINDOW CANNOT BE NESTED INSIDE A WINDOW. `is_top_50_in_category`
-- is an aggregate over `rank_desc`, which is itself a window — Postgres rejects
-- `bool_or(rank() over (...)) over (...)` outright ("window function calls cannot be nested"),
-- so the ranks are computed in `ranked` and the category flag is a second window over them.
-- The column list and every existing definition are unchanged; only the shape around them is.
with ranked as (
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

    -- ── TOP 50 IN THE CATEGORY, WHICH IS NOT TOP 50 IN A STATISTIC (A177, cfdb-main-R-1769) ─
    --
    -- 🚨 THE TWO READINGS DIFFER BY A FACTOR OF THREE AND THE WORKBOOK WANTED THE OTHER ONE.
    -- `rank_desc <= 50` above is top 50 *in this statistic*. A175 pivoted the sheets by
    -- category and got a table 28.8% full of holes, because a player top-50 in passing YARDS
    -- is usually not top-50 in passing COMPLETIONS, and the pivot wants every statistic for
    -- every player the category admits.
    --
    -- 📊 A177 RE-MEASURED A175's FIGURES BEFORE BUILDING ON THEM (§6) AND THEY RECONCILE
    -- EXACTLY, 2025, summed over the ten categories:
    --
    --     rows where rank_desc <= 50 (per STATISTIC)     3,539   -> a 28.79% full pivot
    --     rows where this flag is true (per CATEGORY)   12,292   -> 100.0% full, same shape
    --
    -- ⚠️ AND IT FITS `ROW_CAP`, WHICH WAS THE OPEN QUESTION. The prompt's worry was that
    -- `defensive` is 60,445 rows unfiltered; flagged it is **2,821**, the largest of the ten,
    -- against a cap of 5,000. Nothing has to be truncated to ship the full version.
    --
    -- ⚠️ A WINDOW, NOT A SELF-JOIN, AND THAT IS THE WHOLE POINT OF PUBLISHING IT. The page
    -- could only get this by reading the relation twice, which `check_contract` counts as two
    -- relations (AC-G.3). One extra partition here costs the build nothing and removes the
    -- join from every consumer.
    --
    -- ⚠️ IT READS `rank_desc`, SO IT INHERITS THAT COLUMN'S DIRECTION. A category where a low
    -- value is the good one (fumbles lost) flags its WORST players — the same asymmetry
    -- `rank_asc` exists beside `rank_desc` to expose, and the same reason this view refuses to
    -- decide which way a stat reads. A consumer that wants the other end has `rank_asc`.
    -- (the expression itself is the outer select below.)
    s.class_year_display,
    s.height_display,
    s.weight_pounds,
    s.jersey,
    ao.as_of_ts
from {{ ref('fct_player_season_stat') }} s
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'player_stats') ao
)
select
    ranked.*,
    bool_or(rank_desc <= 50)
        over (partition by season, stat_category, player_id) as is_top_50_in_category
from ranked
