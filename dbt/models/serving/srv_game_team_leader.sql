-- Who led a game, per team, per stat. ONE ROW PER game x team x stat_category x stat_type —
-- one row per question asked, not one per player. R-534.
--
-- WHY THIS EXISTS. Nothing in serving could answer "who led this game" and B076 proved it
-- rather than working around it: srv_player_stats ranks the SEASON and carries no game_id, so
-- it answers a different question; srv_player_game_log is the right grain and carries no
-- ordering at all. One game returns 507 rows across 70 players and 50 category/type pairs, so
-- "who led" is a window function — and CLAUDE.md puts a computation upstream, not in a
-- display-only app. B declined to compute it in the page and declined to stub it, which is
-- why this is a serving object and not a panel.
--
-- ⚠️ THE RANKING IS srv_player_stats's, CARRIED ACROSS RATHER THAN REINVENTED. Two ranking
-- implementations that agree until they quietly do not is this project's signature defect and
-- prompt 030 removed two instances of it. All four ideas come over unchanged — rank_desc,
-- rank_asc, percentile and rank_population — and the reasons in that model's comments apply
-- here without amendment:
--
--   BOTH DIRECTIONS, because "the warehouse does not know which way a given stat reads and
--   the page must not decide with arithmetic". Interceptions thrown and interceptions caught
--   are both rankable and read opposite ways.
--
--   rank_population, because "without it '40th' is unreadable — 40 of 2,000 and 40 of 45 are
--   different statements". It bites harder here: a game-team-category group is often 2 or 3
--   players, so "2nd" without "of 3" is close to meaningless.
--
-- ⚠️ IT IS A SERVING-LAYER WINDOW OVER THE MART, WITH NO NEW MART, because that is exactly
-- what srv_player_stats does over fct_player_season_stat. Following the precedent rather than
-- deciding again.
--
-- ⚠️ PARTITIONED PER TEAM, which srv_player_stats does NOT do — it partitions by
-- (season, stat_category, stat_type) with no team, correct for a season leaderboard and wrong
-- here. Every other block on Matchup is one column per side: the scoreline, B074's pairings,
-- B076's box score. A per-GAME leader would break that symmetry for one category and buy
-- nothing a reader cannot get by reading both columns. B076 measured this and reported the
-- data supported it.
--
-- ⚠️ THE GRAIN IS ONE ROW PER GROUP, AND THAT IS THE WHOLE REASON THIS IS A SEPARATE OBJECT.
-- MEASURED, after two designs were built and thrown away:
--
--   per-player, capped top 3 either direction   1,201,737 rows   90% of the fact
--   per-player, capped top 1 either direction     959,247 rows   72% of the fact
--   ONE ROW PER GROUP (this)                      296,629 rows   22% of the fact
--
-- A per-player "leaders" view is srv_player_game_log with four columns bolted on, at a grain
-- serving already covers — the defect the grain rule exists to stop — and NO CAP MAKES IT
-- SMALLER, because 48% of (game, team, category, type) groups contain exactly ONE player and
-- 67% contain three or fewer. There is no leaders subset to extract from a group of one.
--
-- So the grain moves instead of the filter: one row per question, carrying the answer. That
-- is genuinely not srv_player_game_log's grain, it is a fifth the size, and a page reads one
-- row instead of sorting fifty.
--
-- ⚠️ IT CARRIES BOTH ENDS, for the both-directions reason above. A stat that reads best-LOW,
-- interceptions thrown, has its leader in `lowest_*`; one that reads best-high has it in
-- `highest_*`. The page picks the end that reads as good for that stat, which is the decision
-- the warehouse cannot make and the app must not make with arithmetic.
with ranked as (

    select
        g.game_id, g.season, g.week, g.season_type, g.game_date,
        g.team_id, g.team, g.conference, g.home_away,
        g.opponent, g.opponent_team_id,
        g.player_id, g.player_slug, g.player_name,
        g.stat_category, g.stat_type, g.stat_value, g.stat_raw,
        rank() over (partition by g.game_id, g.team_id, g.stat_category, g.stat_type
                     order by g.stat_value desc nulls last)       as rank_desc,
        rank() over (partition by g.game_id, g.team_id, g.stat_category, g.stat_type
                     order by g.stat_value asc nulls last)        as rank_asc,
        round(cast(percent_rank() over (
            partition by g.game_id, g.team_id, g.stat_category, g.stat_type
            order by g.stat_value asc nulls last) as numeric), 4) as percentile,
        count(*) over (partition by g.game_id, g.team_id, g.stat_category, g.stat_type)
                                                                  as rank_population
    from {{ ref('fct_player_game_stat') }} g

),

-- ⚠️ min() rather than a second window, so a TIE resolves deterministically instead of
-- picking whichever row the planner happened to order first. Two players on 2 receptions is
-- ordinary; a page that shows a different one on each load is not.
collapsed as (

    select
        game_id, team_id, stat_category, stat_type,
        max(season) as season, max(week) as week, max(season_type) as season_type,
        max(game_date) as game_date, max(team) as team, max(conference) as conference,
        max(home_away) as home_away, max(opponent) as opponent,
        max(opponent_team_id) as opponent_team_id,
        max(rank_population) as rank_population,

        min(player_name)  filter (where rank_desc = 1) as highest_player_name,
        min(player_slug)  filter (where rank_desc = 1) as highest_player_slug,
        min(player_id)    filter (where rank_desc = 1) as highest_player_id,
        max(stat_value)   filter (where rank_desc = 1) as highest_stat_value,
        min(stat_raw)     filter (where rank_desc = 1) as highest_stat_raw,
        count(*)          filter (where rank_desc = 1) as highest_tied_players,

        min(player_name)  filter (where rank_asc = 1)  as lowest_player_name,
        min(player_slug)  filter (where rank_asc = 1)  as lowest_player_slug,
        min(player_id)    filter (where rank_asc = 1)  as lowest_player_id,
        min(stat_value)   filter (where rank_asc = 1)  as lowest_stat_value,
        min(stat_raw)     filter (where rank_asc = 1)  as lowest_stat_raw,
        count(*)          filter (where rank_asc = 1)  as lowest_tied_players
    from ranked
    group by game_id, team_id, stat_category, stat_type

)

select
    {{ surrogate_key(['c.game_id', 'c.team_id', 'c.stat_category', 'c.stat_type']) }}
        as game_team_leader_sk,
    c.game_id, c.season, c.week, c.season_type, c.game_date,
    c.team_id, c.team, c.conference, c.home_away, c.opponent, c.opponent_team_id,
    c.stat_category, c.stat_type,
    c.highest_player_name, c.highest_player_slug, c.highest_player_id,
    c.highest_stat_value, c.highest_stat_raw, c.highest_tied_players,
    c.lowest_player_name, c.lowest_player_slug, c.lowest_player_id,
    c.lowest_stat_value, c.lowest_stat_raw, c.lowest_tied_players,
    -- The n the leader led. "Led the team" out of two players and out of eleven are different
    -- statements, and srv_player_stats carries this column for exactly that reason.
    c.rank_population,
    ao.as_of_ts
from collapsed c
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'player_game') ao
