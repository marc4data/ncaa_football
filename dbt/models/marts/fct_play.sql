{{ config(materialized='table') }}

-- One row per play. 583,641 plays, 2024-2026 — play-by-play is `recent` scope by decision.
--
-- The spine the Players page's drill-down sits on, and the finest grain in the warehouse.
--
-- THE SOURCE HAS NO SEASON AND NO WEEK. /plays is fetched per season and week, but the rows
-- it returns carry neither — only a game id. Both are resolved here from fct_game, the same
-- job fct_player_game_stat does for the box score. Anything filtering plays by season
-- without this mart is joining to the game spine by hand.
--
-- TEAM IDS ARE RESOLVED TOO. The payload names the offense and defense as strings; dim_team
-- turns those into ids within season, so a play can be attributed to a team without a name
-- comparison. Null where the team is not in /teams, which is the usual non-FBS case and not
-- a join failure.
--
-- DOWN AND DISTANCE ARE PRE-FORMATTED AND PRE-BUCKETED, because the drill-down filters on
-- them and the app is not allowed to compute (G-3). `down_distance_display` is the string a
-- reader expects; `distance_bucket` is what a filter actually needs, since "3rd and long" is
-- the question people ask and "3rd and 7" is not.

with plays as (

    select * from {{ ref('stg_play') }}

),

with_game as (

    select
        p.*,
        g.season,
        g.week,
        g.season_type,
        g.game_date,
        g.start_date,
        g.is_neutral_site,
        g.venue
    from plays p
    join {{ ref('fct_game') }} g on g.game_id = p.game_id

),

resolved as (

    select
        w.*,
        o.team_id as offense_team_id,
        d.team_id as defense_team_id
    from with_game w
    left join {{ ref('dim_team') }} o on o.season = w.season and o.school = w.offense
    left join {{ ref('dim_team') }} d on d.season = w.season and d.school = w.defense

)

select
    {{ surrogate_key(['play_id']) }}                      as play_sk,
    play_id,
    game_id,
    drive_id,
    drive_number,
    play_number,
    season,
    week,
    season_type,
    game_date,
    start_date,
    is_neutral_site,
    venue,

    offense,
    offense_team_id,
    offense_conference,
    offense_score,
    defense,
    defense_team_id,
    defense_conference,
    defense_score,
    home_team,
    away_team,

    period,
    clock_minutes,
    clock_seconds_part,
    clock_seconds,
    offense_timeouts,
    defense_timeouts,

    yardline,
    yards_to_goal,
    down,
    distance,
    yards_gained,
    is_scoring_play,
    play_type,
    play_text,
    ppa,
    wallclock_at,

    -- What a reader expects to see. Assembled here rather than in the app, the same argument
    -- as record_display: a down and distance is one fact with a conventional rendering.
    -- Null when down is null or 0 — kickoffs and some special-teams plays have no down, and
    -- "0th and 10" is not a thing.
    case when down between 1 and 4
         then cast(down as {{ dbt.type_string() }}) ||
              case down when 1 then 'st' when 2 then 'nd' when 3 then 'rd' else 'th' end
              || ' and ' ||
              -- Goal-to-go is a distance to the end zone, not a yardage, and reads that way.
              case when distance >= yards_to_goal then 'Goal'
                   else cast(distance as {{ dbt.type_string() }}) end
    end                                                   as down_distance_display,
    -- What a filter needs. "3rd and long" is the question a reader asks; "3rd and 7" is not.
    -- Boundaries are the conventional ones rather than anything derived, and are named here
    -- so a page cannot pick different ones.
    case when down is null or down = 0 then null
         when distance >= yards_to_goal then 'goal to go'
         when distance <= 3 then 'short'
         when distance <= 7 then 'medium'
         else 'long' end                                  as distance_bucket,
    -- Field zone, for the same reason. Red zone is the one every reader knows.
    case when yards_to_goal is null then null
         when yards_to_goal <= 20 then 'red zone'
         when yards_to_goal <= 50 then 'opponent territory'
         else 'own territory' end                         as field_zone,

    -- ==========================================================================================
    -- WHERE THE PLAY ENDED. A170 (cfdb-main-R-1323), for Marc's v19 ask: "borders around the
    -- yards gained by plays > 10 yards long". A border is a SEGMENT, and a segment needs two
    -- ends; this view published one. The subtraction lives here rather than in the page because
    -- §4.2.1 says arithmetic between two columns goes upstream, and because the frame conversion
    -- below is band-dependent and getting it backwards is B133's mirrored-band defect.
    --
    -- THE COORDINATE DECISION IS fct_drive's, RE-MEASURED AT PLAY GRAIN RATHER THAN INHERITED.
    -- fct_drive proved `yardline` is an absolute STADIUM coordinate in the HOME team's frame
    -- over 78,502 drives. The same invariant holds over these plays with ZERO exceptions:
    --
    --     offense = home_team    yardline + yards_to_goal = 100   (317,520 of 317,520)
    --     offense = away_team    yardline = yards_to_goal         (312,372 of 312,372)
    --
    -- The 8,140 plays satisfying both are at the 50, where the formulas coincide.
    --
    -- SO `yards_from_own_goal` IS THE ONLY COORDINATE BOTH BANDS CAN BE DRAWN ON DRIVING RIGHT,
    -- exactly as it is for drives. Drawn on `yardline`, the away band mirrors. A play segment
    -- and the drive bar it sits inside MUST share this coordinate or the border will not land
    -- on the bar.
    -- ==========================================================================================
    100 - yards_to_goal                                   as start_yards_from_own_goal,
    yards_to_goal - yards_gained                          as end_yards_to_goal,
    100 - (yards_to_goal - yards_gained)                  as end_yards_from_own_goal,
    case when offense = home_team
         then 100 - (yards_to_goal - yards_gained)
         else       (yards_to_goal - yards_gained) end    as end_yardline,

    -- 🚨 `yards_gained` IS A FIELD-POSITION DELTA ON SCRIMMAGE PLAYS AND SOMETHING ELSE ENTIRELY
    -- ON KICKS AND TURNOVERS, so the end coordinate is not always meaningful — and this flag is
    -- what lets a page say so instead of drawing a lie. Named and shaped after srv_drive's
    -- `is_end_on_field`, which suppresses the BAR and keeps the ROW for the same reason.
    --
    -- MEASURED over all 629,892 plays: 12,067 (1.9%) land off the field, and they are not a
    -- scatter of bad rows — they are CATEGORIES:
    --
    --     Field Goal Good      7,497 of 7,558   99.2%   yards_gained is the KICK DISTANCE
    --     Field Goal Missed    2,394 of 2,425   98.7%   (which includes the end zone)
    --     Pass Interception Return 234 of 3,462  6.8%   the yards belong to the DEFENSE
    --     Kickoff / returns / penalties          the rest, all small
    --
    -- Rush is 83 of ~200,000 and Pass Reception 81 — so the coordinate is sound for precisely
    -- the plays Marc's border is about, and honest about the ones it is not.
    coalesce(yards_to_goal - yards_gained between 0 and 100, false)
                                                          as is_end_on_field
from resolved
