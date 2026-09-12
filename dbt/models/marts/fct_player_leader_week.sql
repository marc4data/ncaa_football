{{ config(materialized='table') }}

-- The three players leading a team in a metric GOING INTO each week. R-687.
--
-- One row per (season, season_type, week, team_id, panel, leader_rank). Top three only.
--
-- 🚨 THE OFF-BY-ONE IS THE ENTIRE POINT OF THIS MODEL, exactly as it is in
-- fct_team_record_week. The row for week N accumulates weeks strictly BEFORE N. The window frame
-- below ends at `1 preceding`, not `current row`, and that single word is the difference between
-- a leaderboard a Week 5 matchup page can show and one that has already read the Week 5 box
-- score. Marc's rule: "Can only include data through Week 4 in a Week 5 game."
--
-- 🚨 POINT-IN-TIME BY CONSTRUCTION, NOT BY A `where`. A092's precedent, and the reason this is a
-- mart rather than a filter in a serving view: "a leakage rule enforced by a filter is a rule one
-- careless join removes." There is no date or week predicate anywhere in this model. Delete any
-- line you like and the leakage rule survives, because it lives in the frame.
--
-- ⚠️ MARC'S PAIRING IS DELIBERATE. `panel` and `leader_metric` deliberately DISAGREE — the
-- passing panel is accompanied by RECEIVERS. fct_player_yardage_week's header carries the table
-- and the reason; this model ranks what that one measures and does not re-decide it.
--
-- ⚠️ WALK THE CALENDAR, NOT THE GAMES — fct_team_record_week's rule, and it bites harder here. A
-- receiver who last played in week 2 STILL LEADS the team through week 5, and a spine built from
-- his own games would carry no week-5 row for him and silently drop him from a leaderboard he
-- tops. The spine is crossed with every player the team has used, so every player has a row in
-- every week his team plays and the running total carries across byes and absences.
--
-- ⚠️ BUT THE SPINE IS THE WEEKS THE TEAM PLAYS, NOT EVERY WEEK ON THE CALENDAR, which IS a
-- deliberate departure from fct_team_record_week — that model walks all of them, correctly,
-- because a Schedule page filtered to a bye week still has to show a record. A leader row is only
-- ever read beside a GAME, so a bye-week row is one nothing can consume. The accumulation is
-- unaffected: a player can only gain yards in a week his team played, so summing over fixture
-- weeks and over calendar weeks give the identical number on every week that HAS a game. What
-- changes is the size, and not marginally — 400-odd non-FBS teams sit in dim_team_week for a
-- whole season because they played ONE FBS opponent.
--
-- ⚠️ THE ORDINAL STILL COMES FROM dim_team_week rather than being recomputed. The spine is
-- shared, not rebuilt; this narrows which of its rows are used and redefines nothing.
--
-- ⚠️ ORDER BY SEASON TYPE, THEN WEEK — never week alone. Postseason week numbers restart at 1, so
-- ordering on week would accumulate a bowl game in the middle of October.
--
-- ⚠️ TIES SHARE A RANK — `rank()`, not `row_number()`. Two receivers on 210 yards are jointly
-- second, and a page that picks one of them by accident of planner order shows a different name
-- on each load. `tied_players` is how it knows to write "T-2nd". A three-way tie for third
-- therefore returns more than three rows, which is the honest shape rather than a silent
-- truncation.
--
-- ⚠️ EVERY CTE BELOW READS A REAL TABLE, WHICH IS A PERFORMANCE DECISION WITH A MEASUREMENT
-- BEHIND IT. fct_player_yardage_week exists because the union that feeds it, written inline here,
-- either lost its statistics (materialised, `rows=1` estimates, nested loops, killed at ten
-- minutes) or was re-expanded on every reference (not materialised, nine scans of 1.27M rows,
-- killed at four). As a table it is 99,758 rows built in 7.3 seconds and the estimates are real.
with fixture_weeks as (

    select season, season_type, week, home_team_id as team_id
    from {{ ref('fct_game') }}
    where season >= 2024 and home_team_id is not null

    union

    select season, season_type, week, away_team_id
    from {{ ref('fct_game') }}
    where season >= 2024 and away_team_id is not null

),

spine as (

    select w.season, w.season_type, w.season_type_ordinal, w.week, w.team_id
    from {{ ref('dim_team_week') }} w
    join fixture_weeks f
      on  f.season      = w.season
      and f.season_type = w.season_type
      and f.week        = w.week
      and f.team_id     = w.team_id
    where w.season >= 2024

),

-- Every (player, panel) the team has used this season, independent of which weeks he played.
player_panel as (

    select distinct season, team_id, player_id, panel
    from {{ ref('fct_player_yardage_week') }}

),

player_spine as (

    select sp.season, sp.season_type, sp.season_type_ordinal, sp.week, sp.team_id,
           pp.player_id, pp.panel
    from spine sp
    join player_panel pp
      on  pp.season  = sp.season
      and pp.team_id = sp.team_id

),

running as (

    select
        ps.season, ps.season_type, ps.season_type_ordinal, ps.week, ps.team_id,
        ps.player_id, ps.panel,
        -- `1 preceding`, NOT `current row`. See the header: this is the leakage rule, and the
        -- staged break flips exactly this word.
        sum(coalesce(y.week_yards, 0)) over (
            partition by ps.season, ps.team_id, ps.player_id, ps.panel
            order by ps.season_type_ordinal, ps.week
            rows between unbounded preceding and 1 preceding)
            as yards_through_prior_week
    from player_spine ps
    left join {{ ref('fct_player_yardage_week') }} y
      on  y.season      = ps.season
      and y.season_type = ps.season_type
      and y.week        = ps.week
      and y.team_id     = ps.team_id
      and y.player_id   = ps.player_id
      and y.panel       = ps.panel

),

-- The `where` runs BEFORE these windows, which in Postgres it does: a player on zero yards
-- through the prior week is not a leader and must not occupy a rank. Week 1 therefore produces
-- no rows at all — the correct answer, rather than three players tied on nothing.
ranked as (

    select
        r.season, r.season_type, r.season_type_ordinal, r.week, r.team_id,
        r.player_id, r.panel, r.yards_through_prior_week,
        rank() over (partition by r.season, r.team_id, r.panel,
                                  r.season_type_ordinal, r.week
                     order by r.yards_through_prior_week desc)
            as leader_rank,
        count(*) over (partition by r.season, r.team_id, r.panel,
                                    r.season_type_ordinal, r.week)
            as qualified_players,
        count(*) over (partition by r.season, r.team_id, r.panel,
                                    r.season_type_ordinal, r.week,
                                    r.yards_through_prior_week)
            as tied_players
    from running r
    where r.yards_through_prior_week > 0

),

-- Name, slug and roster key resolved once per (season, team, player) and joined back only AFTER
-- the top three are chosen, so three text columns do not travel through four sorts.
player_identity as (

    select season, team_id, player_id,
           min(player_name) as player_name,
           min(player_slug) as player_slug,
           min(athlete_sk)  as athlete_sk
    from {{ ref('fct_player_yardage_week') }}
    group by season, team_id, player_id

)

select
    {{ surrogate_key(['rk.season', 'rk.season_type', 'rk.week', 'rk.team_id',
                      'rk.panel', 'rk.player_id']) }}
        as player_leader_week_sk,
    rk.season,
    rk.season_type,
    rk.season_type_ordinal,
    rk.week,
    rk.team_id,
    rk.panel,
    -- The pairing, restated as data on every row, so a page or a test can assert the crossing
    -- without reading prose.
    case rk.panel
        when 'passing' then 'receiving_yards'
        when 'rushing' then 'rushing_yards'
        when 'total'   then 'quarterback_total_yards'
    end as leader_metric,
    rk.leader_rank,
    rk.tied_players,
    rk.qualified_players,
    rk.player_id,
    pi.player_name,
    pi.player_slug,
    pi.athlete_sk,
    rk.yards_through_prior_week
from ranked rk
join player_identity pi
  on  pi.season    = rk.season
  and pi.team_id   = rk.team_id
  and pi.player_id = rk.player_id
where rk.leader_rank <= 3
