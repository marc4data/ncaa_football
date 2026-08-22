{{ config(materialized='table') }}

-- One row per (season, team). Derived from the game spine, not from /records.
--
-- CFBD has no standings endpoint. /records exists and is landed, but it is used as a
-- RECONCILIATION TEST against this derivation rather than as the source — two independent
-- derivations that must agree is a stronger data-quality artifact than trusting one.
--
-- tiebreak_rank is cfdb's own ordering logic, and the page must be able to say so.
-- tiebreak_basis names the rule applied so the UI can label it rather than implying an
-- official standing.

with team_games as (

    select *
    from {{ ref('fct_game_team') }}
    where is_completed
      and points_for is not null
      and points_against is not null

),

aggregated as (

    select
        season,
        team_sk,
        team_id,
        count(*)                                                   as games_played,
        count(case when points_for > points_against then 1 end)    as wins,
        count(case when points_for < points_against then 1 end)    as losses,
        count(case when points_for = points_against then 1 end)    as ties,
        count(case when is_conference_game and points_for > points_against then 1 end) as conference_wins,
        count(case when is_conference_game and points_for < points_against then 1 end) as conference_losses,
        sum(points_for)                                            as points_for,
        sum(points_against)                                        as points_against,
        -- The name comes from the GAME SPINE, which is complete, not from the dimension,
        -- which is not. dim_team is built from CFBD's /teams response and has no row for a
        -- Division II side that merely appeared on someone's schedule, so `school` was NULL
        -- on 7,482 of 30,475 team-seasons — and every view reading it inherited that.
        -- max() rather than min() is arbitrary; fct_game_team carries one name per team_id.
        max(team)                                                  as team_name,

        -- SEASON TOTALS, offensive side. R-002 / R-003 / R-032.
        sum(total_yards)                                           as yards_for,
        sum(rushing_yards)                                         as rushing_yards_for,
        sum(passing_yards)                                         as passing_yards_for,
        sum(turnovers)                                             as giveaways,
        sum(penalty_yards)                                         as penalty_yards,
        count(*) filter (where total_yards is not null)            as games_with_box_score
    from team_games
    group by season, team_sk, team_id

),

-- Against-the-spread record. MOVED HERE FROM srv_team_overview, where it was computed in
-- the serving layer and would have had to be computed a second time for Standings.
--
-- Two derivations of one definition is the defect this project keeps finding — the Scores
-- page deriving a winner the view already carried, disagreeing on 1 game in 295. A record
-- is a business definition and belongs in a fact, read by every view that shows it.
--
-- Sign convention, stated because it governs the whole calculation: margin is away minus
-- home, and the home side covers when margin < spread.
ats as (
    -- Against-the-spread record, from the game spine and the closing line. Computed here
    -- because AC-5.3/AC-G.2 forbid the app assembling records from components.
    --
    -- Sign convention, stated because it governs the whole calculation: margin is
    -- away - home, and the home side covers when margin < spread.
    select
        t.season,
        t.team_id,
        sum(case when t.covered then 1 else 0 end)                      as ats_wins,
        sum(case when t.covered is false then 1 else 0 end)             as ats_losses,
        sum(case when t.covered is null and t.spread is not null then 1 else 0 end) as ats_pushes,
        sum(case when t.is_favorite and t.covered then 1 else 0 end)    as ats_fav_wins,
        sum(case when t.is_favorite and t.covered is false then 1 else 0 end) as ats_fav_losses,
        sum(case when not t.is_favorite and t.covered then 1 else 0 end) as ats_dog_wins,
        sum(case when not t.is_favorite and t.covered is false then 1 else 0 end) as ats_dog_losses
    from (
        select
            g.season,
            g.home_team_id as team_id,
            l.spread,
            l.spread < 0   as is_favorite,
            case when g.away_points - g.home_points < l.spread then true
                 when g.away_points - g.home_points > l.spread then false end as covered
        from {{ ref('fct_game') }} g
        join (
            select game_id, spread from (
                select b.*, row_number() over (partition by b.game_id
                                               order by b.snapshot_ts desc, b.provider_key) as r
                from {{ ref('fct_betting_line') }} b
            ) x where r = 1
        ) l on l.game_id = g.game_id
        where g.is_completed and l.spread is not null

        union all

        select
            g.season,
            g.away_team_id as team_id,
            -1 * l.spread,
            l.spread > 0,
            case when g.away_points - g.home_points > l.spread then true
                 when g.away_points - g.home_points < l.spread then false end
        from {{ ref('fct_game') }} g
        join (
            select game_id, spread from (
                select b.*, row_number() over (partition by b.game_id
                                               order by b.snapshot_ts desc, b.provider_key) as r
                from {{ ref('fct_betting_line') }} b
            ) x where r = 1
        ) l on l.game_id = g.game_id
        where g.is_completed and l.spread is not null
    ) t
    group by t.season, t.team_id
),

-- Splits, streak and last-five, from the same completed-game spine as the totals above.
--
-- All of these are DISPLAY STRINGS by the time they leave here, because AC-5.3 forbids the
-- app assembling "5-7" from two columns. A record is one fact with a conventional
-- rendering, not two numbers and a hyphen decided in Python.
-- What the opponent did, in the same games. The defensive half of R-002.
--
-- A separate aggregate rather than subtraction from a game total: fct_game_team already has
-- one row per team per game, so the opponent's yardage is that opponent's own row, keyed by
-- (game_id, opponent_team_id). Subtracting from a game total would need the game total to
-- exist, which it does not when only one box score landed.
allowed as (

    select
        g.season,
        g.team_id,
        sum(o.total_yards)                                as yards_allowed,
        sum(o.rushing_yards)                              as rushing_yards_allowed,
        sum(o.passing_yards)                              as passing_yards_allowed,
        sum(o.turnovers)                                  as takeaways,
        count(*) filter (where o.total_yards is not null) as games_with_opponent_box_score
    from team_games g
    join {{ ref('fct_game_team') }} o
      on o.game_id = g.game_id and o.team_id = g.opponent_team_id
    group by g.season, g.team_id

),

splits as (

    select
        season,
        team_id,
        count(*) filter (where is_home and not is_neutral_site
                         and points_for > points_against)              as home_wins,
        count(*) filter (where is_home and not is_neutral_site
                         and points_for < points_against)              as home_losses,
        count(*) filter (where not is_home and not is_neutral_site
                         and points_for > points_against)              as away_wins,
        count(*) filter (where not is_home and not is_neutral_site
                         and points_for < points_against)              as away_losses,
        -- A neutral-site game is neither a home game nor a road game, and counting it as
        -- either overstates one split. Bowls and kickoff classics are exactly the games a
        -- reader would notice in the wrong column.
        count(*) filter (where is_neutral_site)                        as neutral_games
    from team_games
    group by season, team_id

),

ordered as (

    select
        season,
        team_id,
        case when points_for > points_against then 'W'
             when points_for < points_against then 'L'
             else 'T' end                                              as outcome,
        row_number() over (partition by season, team_id
                           order by game_date desc, game_id desc)      as recency
    from team_games

),

-- The islands trick: within a team-season, subtracting a per-outcome sequence from the
-- overall sequence gives a constant for each unbroken run of the same result. The run
-- containing the most recent game is the current streak.
runs as (

    select
        o.*,
        o.recency - row_number() over (partition by o.season, o.team_id, o.outcome
                                       order by o.recency)             as run_id
    from ordered o

),

current_run as (
    select season, team_id, outcome, run_id from runs where recency = 1
),

streak as (

    select
        c.season,
        c.team_id,
        c.outcome,
        count(*)                                                       as streak_length
    from runs r
    join current_run c
      on c.season = r.season and c.team_id = r.team_id
     and c.run_id = r.run_id and c.outcome = r.outcome
    group by c.season, c.team_id, c.outcome

),

last_five as (

    select
        season,
        team_id,
        count(*) filter (where outcome = 'W')                          as last5_wins,
        count(*) filter (where outcome = 'L')                          as last5_losses,
        count(*) filter (where outcome = 'T')                          as last5_ties
    from ordered
    where recency <= 5
    group by season, team_id

),

with_team as (

    select
        a.*,
        coalesce(t.school, a.team_name) as school,
        t.conference,
        t.conference_sk,
        t.classification,
        t.team_sk is not null as is_listed_team
    from aggregated a
    left join {{ ref('dim_team') }} t
        on t.season = a.season and t.team_id = a.team_id

)

select
    {{ surrogate_key(['w.season', 'w.team_id']) }} as team_season_sk,
    w.season,
    w.team_sk,
    w.team_id,
    w.school,
    w.conference,
    w.conference_sk,
    w.classification,
    w.is_listed_team,
    w.games_played,
    w.wins,
    w.losses,
    w.ties,
    w.conference_wins,
    w.conference_losses,
    w.points_for,
    w.points_against,
    w.points_for - w.points_against as point_differential,
    round(cast(w.wins as numeric) / nullif(w.games_played, 0), 3) as win_pct,
    -- Ordering within (season, conference). Real conference tiebreakers involve
    -- head-to-head and are conference-specific; this is the simple rule, labelled as such.
    case when w.conference is null then null else
        row_number() over (
            partition by w.season, w.conference
            order by
                cast(w.conference_wins as numeric)
                    / nullif(w.conference_wins + w.conference_losses, 0) desc nulls last,
                cast(w.wins as numeric) / nullif(w.games_played, 0) desc nulls last,
                (w.points_for - w.points_against) desc,
                w.school
        )
    end as tiebreak_rank,
    case when w.conference is null then null
         else 'conference_win_pct,overall_win_pct,point_differential,school_name'
    end as tiebreak_basis,

    -- Conference win percentage, null rather than zero for a team with no conference game
    -- played. An independent, or a team in week one, has not gone 0.000 in conference — it
    -- has no conference record at all, and those are different claims.
    round(cast(w.conference_wins as numeric)
          / nullif(w.conference_wins + w.conference_losses, 0), 3) as conference_win_pct,

    s.home_wins,
    s.home_losses,
    s.away_wins,
    s.away_losses,
    s.neutral_games,

    -- Pre-formatted, per AC-5.3. Null when nothing has been played: an unplayed split is
    -- not 0-0. That is the same manufactured-zero defect as the ats 0-0-0 that showed every
    -- 2026 team a record it had not earned.
    case when s.home_wins + s.home_losses > 0
         then cast(s.home_wins as {{ dbt.type_string() }}) || '-'
              || cast(s.home_losses as {{ dbt.type_string() }}) end as home_record_display,
    case when s.away_wins + s.away_losses > 0
         then cast(s.away_wins as {{ dbt.type_string() }}) || '-'
              || cast(s.away_losses as {{ dbt.type_string() }}) end as away_record_display,

    st.outcome        as current_streak_outcome,
    st.streak_length  as current_streak_length,
    -- "W3", "L2". A tie breaks a streak like anything else, so a T run renders as T1.
    case when st.outcome is not null
         then st.outcome || cast(st.streak_length as {{ dbt.type_string() }})
    end as current_streak_display,

    l5.last5_wins,
    l5.last5_losses,
    l5.last5_ties,
    case when l5.last5_wins + l5.last5_losses + l5.last5_ties > 0
         then cast(l5.last5_wins as {{ dbt.type_string() }}) || '-'
              || cast(l5.last5_losses as {{ dbt.type_string() }})
              || case when l5.last5_ties > 0
                      then '-' || cast(l5.last5_ties as {{ dbt.type_string() }})
                      else '' end
    end as last_5_display,

    -- ATS, pre-formatted. NULL rather than 0-0-0 where no game has been graded: an
    -- ungraded season has no against-the-spread record, and manufacturing one showed every
    -- 2026 team a record it had not earned.
    a.ats_wins,
    a.ats_losses,
    a.ats_pushes,
    case when a.ats_wins is not null and a.ats_wins + a.ats_losses + a.ats_pushes > 0 then
        cast(a.ats_wins as {{ dbt.type_string() }}) || '-'
            || cast(a.ats_losses as {{ dbt.type_string() }}) || '-'
            || cast(a.ats_pushes as {{ dbt.type_string() }}) end as ats_record_display,
    case when a.ats_fav_wins is not null and a.ats_fav_wins + a.ats_fav_losses > 0 then
        cast(a.ats_fav_wins as {{ dbt.type_string() }}) || '-'
            || cast(a.ats_fav_losses as {{ dbt.type_string() }}) end as ats_as_favorite_display,
    case when a.ats_dog_wins is not null and a.ats_dog_wins + a.ats_dog_losses > 0 then
        cast(a.ats_dog_wins as {{ dbt.type_string() }}) || '-'
            || cast(a.ats_dog_losses as {{ dbt.type_string() }}) end as ats_as_underdog_display,

    -- Season totals. R-002 / R-003 / R-032, one dbt change for three requests.
    w.yards_for,
    w.rushing_yards_for,
    w.passing_yards_for,
    w.penalty_yards,
    w.giveaways,
    -- AC-G.33: the n each total was computed over, carried beside it. Box scores are
    -- `recent` scope, so a 2025 team has yardage from about half its games and a 2019 team
    -- has none. Yards-per-game over `games_played` would be the composition defect we
    -- already shipped once.
    w.games_with_box_score,
    al.yards_allowed,
    al.rushing_yards_allowed,
    al.passing_yards_allowed,
    al.takeaways,
    al.games_with_opponent_box_score,
    -- Takeaways minus giveaways, team perspective, positive is good. Null unless BOTH sides
    -- were recorded — a margin from one half is not a margin.
    case when al.takeaways is not null and w.giveaways is not null
         then al.takeaways - w.giveaways end                        as turnover_margin
from with_team w
left join allowed al    on al.season = w.season and al.team_id = w.team_id
left join ats a         on a.season = w.season and a.team_id = w.team_id
left join splits s      on s.season = w.season and s.team_id = w.team_id
left join streak st     on st.season = w.season and st.team_id = w.team_id
left join last_five l5  on l5.season = w.season and l5.team_id = w.team_id
