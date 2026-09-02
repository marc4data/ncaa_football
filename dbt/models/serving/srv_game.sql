-- THE game-grain serving view: one row per game. R-076.
--
-- NAMED FOR ITS GRAIN, NOT FOR A PAGE. This replaces srv_schedule and srv_scoreboard, which
-- were one row per game over fct_game apiece — the same grain over the same fact, split by
-- which page read them.
--
-- THE COST OF THAT SPLIT WAS ALREADY PAID. srv_scoreboard took team display names off
-- dim_team, which is season-scoped and does not list every Division II visitor an FBS side
-- schedules; 12,168 of 110,634 rows rendered an em dash for the team and the string "None"
-- for the winner. srv_schedule took the same name off fct_game and had zero nulls. One
-- column, two implementations, one of them shipped broken. The fix went into srv_scoreboard's
-- header rather than into the thing that made two implementations possible.
--
-- MEASURED WHILE MERGING, and it is the same shape a second time: `home_rank` had two
-- implementations too. srv_schedule read g.home_rank off fct_game; srv_scoreboard rebuilt it
-- with its own ap_rank CTE over fct_poll_rank. fct_game ALREADY joins fct_poll_rank for the
-- AP Top 25 — the CTE was re-deriving what the spine hands it. They agreed exactly (11,982
-- populated on both, zero disagreements across 110,879 games), which is precisely the state
-- the team name was in before it drifted. The CTE is dropped and the spine's column kept.
--
-- THE GRAIN RULE (Marc, ratified 2026-09-02): "Can't add game.team grain to a table that is
-- at game grain." Anything finer than one row per game arrives as its own view — see
-- srv_game_team — or as a DERIVED summary computed in dbt and named so the derivation shows.
-- The box-score columns below are the second kind: sums across both teams, not team rows.

with latest_line as (

    -- Most recent line of all, for the "current" market number. Distinct from pre_kick below,
    -- which answers a different question and must not be conflated with it.
    select game_id, spread, over_under
    from (
        select b.*, row_number() over (partition by b.game_id
                                       order by b.snapshot_ts desc, b.provider_key) as recency
        from {{ ref('fct_betting_line') }} b
    ) r where recency = 1

),

latest_prediction as (

    -- Prefer a model that populates predicted_margin: six of seven models are probability
    -- models, so ordering by recency alone loses the margin almost every time.
    select game_id, predicted_margin, predicted_home_win_probability, model_name
    from (
        select p.*, row_number() over (
                   partition by p.game_id
                   order by case when p.predicted_margin is not null then 0 else 1 end,
                            p.prediction_ts desc, p.model_version desc) as recency
        from {{ ref('fct_prediction') }} p
    ) r where recency = 1

),

game_box as (

    -- Game-grain totals derived from the team-grain box score. A DERIVED summary, which the
    -- grain rule permits; the team rows themselves live in srv_game_team.
    select
        game_id,
        sum(total_yards)    as total_yards_both_teams,
        sum(rushing_yards)  as rushing_yards_both_teams,
        sum(passing_yards)  as passing_yards_both_teams,
        sum(turnovers)      as turnovers_both_teams,
        count(*) filter (where total_yards is not null) as teams_with_box_score
    from {{ ref('fct_game_team') }}
    group by game_id

),

pre_kick as (

    -- The last line recorded BEFORE kickoff, and its provenance. Our snapshot history begins
    -- 2026-08-15, so for an older game the only line held is whatever CFBD returned when we
    -- fetched it — a real market number whose timestamp is our FETCH time, not a pre-kickoff
    -- observation. Calling both "close" would conflate a line we watched with one we were
    -- told about, which is why basis travels with the number.
    select game_id, spread, provider_key, snapshot_ts, basis from (
        select
            b.game_id, b.spread, b.provider_key, b.snapshot_ts,
            case when b.snapshot_ts <= g.start_date then 'observed_before_kickoff'
                 else 'as_recorded_by_cfbd' end as basis,
            row_number() over (
                partition by b.game_id
                order by case when b.snapshot_ts <= g.start_date then 0 else 1 end,
                         b.snapshot_ts desc, b.provider_key
            ) as recency
        from {{ ref('fct_betting_line') }} b
        join {{ ref('fct_game') }} g on g.game_id = b.game_id
    ) ranked where recency = 1

)

-- R-079 IS A MART, NOT A CTE HERE. The first version of this view held the "latest snapshot
-- at or before kickoff" selection inline and read stg_game_pregame_wp directly.
-- ci/check_layering.py failed the build for it and was right to: serving builds on marts.
-- Choosing which snapshot represents a game is a business rule, and a business rule inside a
-- view is one a second consumer has to re-derive — which is the defect this whole prompt is
-- about. It lives in fct_game_pregame_wp and is joined below.

select
    g.game_sk,
    g.game_id,
    g.season,
    g.week,
    g.season_type,
    g.week_sk,
    g.game_date,
    g.start_date,
    -- AC-G.34: the display zone is applied here, never in the app.
    {{ to_local_timestamp('g.start_date') }} as start_date_et,
    g.kickoff_time_known,
    g.is_completed,
    g.is_conference_game,
    g.is_neutral_site,
    g.venue,
    -- Both spellings kept: srv_schedule exposed only venue_display and srv_scoreboard both,
    -- and the rename is not the place to drop a column somebody reads.
    g.venue                       as venue_display,
    g.network,
    -- R-080: short form from dim_broadcast_outlet, so the site and the workbook agree.
    g.network_abbreviation,
    g.attendance,
    g.excitement_index,
    g.is_upset,

    -- FBS SPINE. EITHER team, not both: a Division II visitor's trip to an FBS stadium is an
    -- FBS game, and requiring both would drop 20 of the 25 games on the opening Thursday.
    (g.home_classification = 'fbs' or g.away_classification = 'fbs') as is_fbs_game,

    g.home_team_id,
    -- The name comes from the GAME. dim_team is built from /teams and does not list every
    -- opponent an FBS side schedules; the slug falls back to a slug OF that name, because a
    -- null slug is a link to nowhere while a derived one reaches a page that renders Empty.
    g.home_team,
    {{ team_identity('h', 'g.home_team', 'home_') }},
    h.abbreviation                as home_abbreviation,
    h.conference                  as home_conference,
    h.color_on_light              as home_color_on_light,
    h.color_on_dark               as home_color_on_dark,
    h.logo_source_url             as home_logo_url,
    g.home_points,
    -- From the spine, which already joins fct_poll_rank for the AP Top 25. See the header.
    g.home_rank,

    g.away_team_id,
    g.away_team,
    {{ team_identity('a', 'g.away_team', 'away_') }},
    a.abbreviation                as away_abbreviation,
    a.conference                  as away_conference,
    a.color_on_light              as away_color_on_light,
    a.color_on_dark               as away_color_on_dark,
    a.logo_source_url             as away_logo_url,
    g.away_points,
    g.away_rank,

    -- Result, computed once so no page subtracts two numbers to find a winner.
    case
        when not g.is_completed then null
        when g.home_points > g.away_points then g.home_team
        when g.away_points > g.home_points then g.away_team
        else null
    end                                                    as winner,
    -- NULL, not zero, for a game with no result — so zero here means exactly one thing: the
    -- two teams finished level.
    case when g.is_completed and g.home_points is not null and g.away_points is not null
         then abs(g.home_points - g.away_points) end       as final_margin,
    g.away_points - g.home_points as actual_margin,   -- away minus home, per the convention
    case when g.is_completed and g.home_points is not null and g.away_points is not null
         then g.home_points + g.away_points end            as total_points,

    hr.wins as home_wins, hr.losses as home_losses,
    ar.wins as away_wins, ar.losses as away_losses,

    bx.total_yards_both_teams,
    bx.rushing_yards_both_teams,
    bx.passing_yards_both_teams,
    bx.turnovers_both_teams,
    -- 2 when both box scores landed, 1 when only one did, 0 when neither. A total built from
    -- one team is not a game total, and this is what lets a page say so.
    bx.teams_with_box_score,

    l.spread                      as spread_current,
    l.over_under                  as total_current,
    pk.spread                     as spread_at_close,
    pk.provider_key               as spread_at_close_provider,
    pk.basis                      as spread_at_close_basis,

    -- WHETHER THE FAVOURITE COVERED — distinct from which side covered. Four states, and
    -- pending is not push. A pick'em has no favourite at all, which is a real case here.
    case
        when not g.is_completed or g.home_points is null then 'pending'
        when pk.spread is null then null
        when pk.spread = 0 then 'no_favorite'
        when (g.away_points - g.home_points) = pk.spread then 'push'
        when pk.spread < 0 and (g.away_points - g.home_points) < pk.spread then 'yes'
        when pk.spread > 0 and (g.away_points - g.home_points) > pk.spread then 'yes'
        else 'no'
    end                                                    as favorite_covered,

    p.predicted_margin,
    -1 * p.predicted_margin       as predicted_margin_home_perspective,
    p.predicted_home_win_probability as home_win_probability,
    p.model_name                  as model_version_key,

    -- R-079. Pregame win probability, with the provenance of WHEN it was taken. Read
    -- pregame_wp_basis before quoting it: `as_recorded_by_cfbd` means the figure is real but
    -- was fetched after the game, which is not the same claim as a forecast.
    wp.home_win_probability       as pregame_home_win_probability,
    wp.basis                      as pregame_wp_basis,
    wp.snapshot_ts                as pregame_wp_snapshot_ts,

    -- R-078. Weather at the venue. Landed for 2024 onward only, so null for most of history —
    -- that renders as an em dash and is the honest state, not a defect.
    --
    -- is_indoors QUALIFIES EVERY OTHER WEATHER COLUMN. CFBD reports conditions at the
    -- venue's LOCATION, not inside it, so a domed game carries ordinary outdoor readings.
    -- Rendering "Rain, 41F" for a game played under a roof states something false.
    w.is_indoors,
    w.temperature_f,
    w.wind_speed_mph,
    w.precipitation_in,
    w.weather_condition_code,
    w.weather_condition,

    -- R-083. Per-game Elo, which is a per-WEEK Elo. No API call was needed; the games spine
    -- has carried this all along. Populated on 67,306 of 110,879 rows.
    g.home_pregame_elo,
    g.home_postgame_elo,
    g.away_pregame_elo,
    g.away_postgame_elo,

    -- R-082. Quarters, typed. Four columns plus an overtime SUM, because periods reach
    -- thirteen in this data and a column per period would either invent nine or truncate a
    -- triple-OT game. `periods` says how many there were so a page can render "2OT" honestly.
    -- Present from 2001; null before that, and null for the 60% of rows CFBD sends empty.
    g.home_q1, g.home_q2, g.home_q3, g.home_q4,
    g.home_overtime_points, g.home_periods,
    g.away_q1, g.away_q2, g.away_q3, g.away_q4,
    g.away_overtime_points, g.away_periods,

    -- R-084. THE RECORD AS IT STOOD GOING INTO THIS GAME'S WEEK.
    --
    -- NOT the same thing as home_wins / home_losses above, which are the SEASON-FINAL record
    -- from fct_team_record and are kept only because the merge drops nothing. Putting the
    -- season-final record beside a Week 3 game from a finished season is the composition
    -- failure this column exists to prevent, so a page showing a record on a game row must
    -- read these two and not those.
    --
    -- Named home_team_record_display, NOT home_record_display: srv_standings already uses
    -- that name for "record in home games", which is a different statement entirely. The
    -- collision was avoided deliberately.
    rw_home.current_record        as home_team_record_display,
    rw_away.current_record        as away_team_record_display,

    ao.as_of_ts
from {{ ref('fct_game') }} g
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
left join {{ ref('fct_team_record') }} hr on hr.season = g.season and hr.team_id = g.home_team_id
left join {{ ref('fct_team_record') }} ar on ar.season = g.season and ar.team_id = g.away_team_id
left join latest_line l on l.game_id = g.game_id
left join latest_prediction p on p.game_id = g.game_id
left join game_box bx on bx.game_id = g.game_id
left join pre_kick pk on pk.game_id = g.game_id
left join {{ ref('fct_game_pregame_wp') }} wp on wp.game_id = g.game_id
left join {{ ref('fct_game_weather') }} w on w.game_id = g.game_id
-- Record LEADING INTO this game's week, per side. Joined on the full grain including
-- season_type, because postseason week numbers restart at 1 and joining on week alone would
-- put a bowl game's record on an October fixture.
left join {{ ref('fct_team_record_week') }} rw_home
    on  rw_home.season = g.season and rw_home.season_type = g.season_type
    and rw_home.week = g.week and rw_home.team_id = g.home_team_id
left join {{ ref('fct_team_record_week') }} rw_away
    on  rw_away.season = g.season and rw_away.season_type = g.season_type
    and rw_away.week = g.week and rw_away.team_id = g.away_team_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
