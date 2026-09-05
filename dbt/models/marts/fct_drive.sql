{{ config(materialized='table') }}

-- One row per drive. The layer between a game and its plays, and the spine the Matchup
-- drive chart is drawn on.
--
-- `stg_drive` has been landed and idle since 2026-08-15 — the idle-staging-model pattern the
-- modelling policy predicts and accepts. Staging is exhaustive, marts are demand-driven, and
-- the demand arrived with the Matchup post-game tab.
--
-- SCOPE IS 2024-2026, MEASURED RATHER THAN ASSUMED. /drives is `recent` scope, the same as
-- /plays, and the raw manifest confirms it: four full-season fetches (2024 and 2025, regular
-- and postseason) plus 2026 week 1. A Matchup page for a 2019 game therefore has no drives,
-- and that must READ as correct — see srv_drive, which carries the scope boundary as columns
-- so the page can say "cfdb holds drives from 2024" instead of rendering an empty chart.
--
-- THE SOURCE HAS NO SEASON AND NO WEEK, exactly as /plays does not. Both are resolved from
-- fct_game here, the same job fct_play and fct_player_game_stat do. Anything filtering drives
-- by season without this mart is joining to the game spine by hand.
--
-- TEAM IDS ARE RESOLVED TOO. The payload names offense and defense as strings; dim_team turns
-- those into ids within season. Null where the team is not in /teams — the usual non-FBS case
-- and not a join failure, which is why the join is LEFT and the drive is kept.
--
-- ==========================================================================================
-- THE COORDINATE DECISION, AND THE MEASUREMENT THAT SETTLES IT
--
-- `stg_drive` kept both `yardline` and `yards_to_goal` and declined to choose, because "which
-- one is 'the' field position depends entirely on whose drive it is". The drive chart is what
-- decides it, and the data says which one unambiguously.
--
-- MEASURED over all 78,502 drives in the raw layer, with ZERO exceptions:
--
--     is_home_offense = true    yardline + yards_to_goal = 100   (39,108 of 39,108)
--     is_home_offense = false   yardline = yards_to_goal         (39,127 of 39,127)
--
-- The 267 away-offense drives that satisfy BOTH are all at yardline 50, where the two
-- formulas coincide. There is no third case.
--
-- So `yardline` IS AN ABSOLUTE STADIUM COORDINATE IN THE HOME TEAM'S FRAME — 0 is the home
-- team's own goal line — and `yards_to_goal` is offense-relative. They are not two spellings
-- of one number; they are two different measurements, and half the rows disagree by
-- construction rather than by defect.
--
-- `yards_from_own_goal = 100 - yards_to_goal` is therefore the only coordinate on which both
-- bands of the chart can be drawn driving right. Drawn on `yardline` instead, the away band
-- would MIRROR the home band — and the defect would read as a rendering fault while being a
-- units fault. One column, read by both bands, is what makes "align horizontally perfectly"
-- structural instead of a page-side convention that drifts.
--
-- BOTH MEASUREMENTS ARE CARRIED FORWARD ANYWAY. Staging kept them deliberately and this mart
-- does not get to destroy the evidence; the invariant above is asserted as a test, and a test
-- needs both sides of it to exist.
-- ==========================================================================================

with drives as (

    select * from {{ ref('stg_drive') }}

),

with_game as (

    -- INNER JOIN, deliberately. A drive whose game is not in fct_game has no season, no week
    -- and no home team, so it cannot be placed on a chart or filtered by season.
    --
    -- ⚠️ NOT YET MEASURED. /drives covers 3,343 distinct game ids and every one of them ought
    -- to be in fct_game, but this has not been run against a warehouse — see the B046 report.
    -- assert_srv_drive_keeps_every_drive checks fct against srv, NOT stg against fct, so a
    -- drop here would be silent. First build should compare stg_drive's row count to
    -- fct_drive's and say whether the number moved.
    select
        d.*,
        g.season,
        g.week,
        g.season_type,
        g.game_date,
        g.start_date,
        g.is_completed,
        g.is_neutral_site,
        g.venue,
        g.home_team_id,
        g.away_team_id,
        g.home_team,
        g.away_team
    from drives d
    join {{ ref('fct_game') }} g on g.game_id = d.game_id

),

resolved as (

    select
        w.*,
        o.team_id  as offense_team_id,
        df.team_id as defense_team_id
    from with_game w
    left join {{ ref('dim_team') }} o  on o.season = w.season and o.school = w.offense
    left join {{ ref('dim_team') }} df on df.season = w.season and df.school = w.defense

)

select
    {{ surrogate_key(['drive_id']) }}                       as drive_sk,
    drive_id,
    game_id,
    drive_number,

    season,
    week,
    season_type,
    game_date,
    start_date,
    is_completed,
    is_neutral_site,
    venue,

    offense,
    offense_team_id,
    offense_conference,
    defense,
    defense_team_id,
    defense_conference,
    -- The only link to home and away on this payload: the drive names its offense and defense
    -- by school and never as home or away. It is what puts a drive in the away band or the
    -- home band, and what makes the Defense split a re-source of the same rows rather than a
    -- second model.
    is_home_offense,
    home_team_id,
    away_team_id,
    home_team,
    away_team,
    -- Who the offense is driving AT. The endzone at x=100 belongs to this team in this band,
    -- which is what lets srv_drive attach the opposing side's logo, mascot and colour.
    case when is_home_offense then away_team_id else home_team_id end as opponent_team_id,
    case when is_home_offense then away_team    else home_team    end as opponent,

    plays,
    yards,
    is_scoring_drive,

    -- ---------------------------------------------------------------------------------------
    -- GEOMETRY. See the header for why yards_to_goal is the one the chart is drawn on.
    -- ---------------------------------------------------------------------------------------
    start_yardline,
    start_yards_to_goal,
    end_yardline,
    end_yards_to_goal,
    100 - start_yards_to_goal                               as start_yards_from_own_goal,
    100 - end_yards_to_goal                                 as end_yards_from_own_goal,

    -- A DRIVE CAN LOSE YARDS, so end < start is legitimate and is never clamped and never
    -- abs()'d — a sack-and-punt rendered as a forward bar is a lie about the game. Measured:
    -- 8,750 of 78,502 drives end behind where they started.
    (100 - end_yards_to_goal) < (100 - start_yards_to_goal) as is_negative_drive,

    -- WHAT IS *NOT* LEGITIMATE IS AN END POSITION OFF THE FIELD, and 118 drives (0.15%) have
    -- one: end_yards_from_own_goal ranges -78..193 in the raw layer, concentrated in
    -- 'Uncategorized' (80) and 'TD' (34). Two different CFBD defects sit underneath — a
    -- coordinate that overshoots the goal line on a scoring play, and rows where yardline and
    -- yards_to_goal carry the same number in the home frame.
    --
    -- FLAGGED RATHER THAN CLAMPED OR DROPPED. Clamping would silently redraw a real bar;
    -- dropping would lose a possession from a game's sequence. The page decides, and a flag is
    -- the only form that lets it: render the row, and treat the bar as unknown. Start
    -- positions are clean — 0 of 78,502 out of range — so only the end needs the flag.
    (100 - end_yards_to_goal) between 0 and 100             as is_end_on_field,

    -- ---------------------------------------------------------------------------------------
    -- CLOCK. BOTH FORMS OF "start time (of game)" ARE CARRIED, because the spec's phrase is
    -- ambiguous between them and one column each is cheaper than a round trip. Marc picks
    -- against a real render in pass 2.
    -- ---------------------------------------------------------------------------------------
    start_period,
    end_period,
    start_clock_minutes,
    start_clock_seconds,
    end_clock_minutes,
    end_clock_seconds,

    -- ⚠️ `start_clock_seconds` IS THE SECONDS COMPONENT OF mm:ss, NOT A TOTAL — the same trap
    -- stg_drive documents on `elapsed_seconds_part`. The total is derived here under a name
    -- that cannot be mistaken for it.
    start_clock_minutes * 60 + start_clock_seconds          as start_clock_seconds_remaining,
    end_clock_minutes * 60 + end_clock_seconds              as end_clock_seconds_remaining,

    -- FORM 1: the game clock at the snap, as a reader says it. "Q2 07:14".
    case
        when start_period between 1 and 4
            then 'Q' || cast(start_period as {{ dbt.type_string() }}) || ' '
                 || cast(start_clock_minutes as {{ dbt.type_string() }}) || ':'
                 || lpad(cast(start_clock_seconds as {{ dbt.type_string() }}), 2, '0')
        -- College overtime has no game clock, so a time there would be fiction. The period
        -- itself is the honest label. Measured: 326 drives at period >= 5, out to a 12th.
        when start_period = 5 then 'OT'
        when start_period > 5 then cast(start_period - 4 as {{ dbt.type_string() }}) || 'OT'
    end                                                     as start_clock_display,

    -- FORM 2: elapsed from kickoff, for an axis that wants a real number.
    --
    -- NULL OUTSIDE REGULATION rather than extrapolated. Overtime possessions are not 900
    -- seconds of anything, so (period-1)*900 would invent a duration that never elapsed;
    -- period 0 appears on 24 drives and is a source defect, not a period. drive_number
    -- orders those rows instead, which is why it is on the y-axis in the first place.
    case
        when start_period between 1 and 4
            then (start_period - 1) * 900
                 + (900 - (start_clock_minutes * 60 + start_clock_seconds))
    end                                                     as elapsed_from_kickoff_seconds,

    -- ---------------------------------------------------------------------------------------
    -- DURATION. Pre-formatted because a page formatting a duration is the app computing (G-3).
    -- ---------------------------------------------------------------------------------------
    elapsed_minutes,
    elapsed_seconds_part,
    elapsed_seconds,
    -- cast-to-int rather than floor(): Postgres integer division already truncates and
    -- floor() would hand back a numeric that renders as "2" on one engine and "2." on
    -- another. An int cast means the same string on both.
    cast(cast(elapsed_seconds / 60 as int) as {{ dbt.type_string() }}) || ':'
        || lpad(cast(mod(elapsed_seconds, 60) as {{ dbt.type_string() }}), 2, '0')
                                                            as elapsed_display,

    -- ---------------------------------------------------------------------------------------
    -- RESULT. `drive_result` is CFBD free text and it drives an ICON, so it gets a normalised
    -- key and a test that FAILS on anything unmapped — the same shape as the provider mapping
    -- decided 2026-08-17, after "DraftKings" and "Draft Kings" turned out to be two spellings
    -- that would have silently split a comparison.
    --
    -- ⚠️⚠️ THE VOCABULARY WAS MEASURED, NOT ASSUMED: 25 distinct values across 78,502 drives,
    -- and the important half of that is not the count.
    --
    -- A `TD` SUFFIX ON A TURNOVER OR A KICK MEANS THE *DEFENSE* SCORED. Measured by the score
    -- delta across each drive:
    --
    --     'INT TD'            430   defense scored on 398
    --     'FUMBLE RETURN TD'  196   defense scored on 164
    --     'PUNT TD'           100   defense scored on  99
    --     'PUNT RETURN TD'     90   defense scored on  90
    --     'FUMBLE TD'          60   defense scored on  52
    --     'MISSED FG TD'       13   defense scored on  13
    --     'DOWNS TD'            7   defense scored on   7
    --     'END OF HALF TD'      5   defense scored on   5
    --     'FG TD'               2   defense scored on   2
    --     'END OF GAME TD'      1   defense scored on   1
    --     'SF'                182   defense scored on 131  (a safety is 2 to the defense)
    --
    -- A chart that maps every value containing "TD" to an offensive-touchdown icon would put
    -- ~900 drives on the wrong side of the game. `scoring_side` is the column that stops it,
    -- and it is why the mapping is written out rather than pattern-matched on the string.
    drive_result,
    case drive_result
        when 'PUNT'             then 'punt'
        when 'TD'               then 'touchdown'
        when 'FG'               then 'field_goal'
        when 'DOWNS'            then 'downs'
        when 'INT'              then 'interception'
        when 'FUMBLE'           then 'fumble'
        when 'MISSED FG'        then 'missed_field_goal'
        when 'END OF HALF'      then 'end_of_half'
        when 'END OF GAME'      then 'end_of_game'
        when 'END OF 4TH QUARTER' then 'end_of_quarter'
        when 'SF'               then 'safety'
        when 'KICKOFF'          then 'kickoff'
        when 'BLOCKED PUNT'     then 'blocked_punt'
        when 'BLOCKED FG'       then 'blocked_field_goal'
        when 'Uncategorized'    then 'uncategorized'
        when 'INT TD'           then 'interception_return_td'
        when 'FUMBLE RETURN TD' then 'fumble_return_td'
        when 'FUMBLE TD'        then 'fumble_return_td'
        when 'PUNT TD'          then 'punt_return_td'
        when 'PUNT RETURN TD'   then 'punt_return_td'
        when 'MISSED FG TD'     then 'missed_field_goal_return_td'
        when 'DOWNS TD'         then 'downs_return_td'
        when 'FG TD'            then 'field_goal_return_td'
        when 'END OF HALF TD'   then 'end_of_half_return_td'
        when 'END OF GAME TD'   then 'end_of_game_return_td'
    end                                                     as drive_result_key,

    -- The icon FAMILY, so pass 2 picks glyphs per category and only overrides where it wants
    -- to. Deliberately coarser than the key: eleven keys collapse to one 'defensive score'.
    case
        when drive_result in ('TD', 'FG')                          then 'offensive score'
        when drive_result in ('INT TD', 'FUMBLE RETURN TD', 'FUMBLE TD', 'PUNT TD',
                              'PUNT RETURN TD', 'MISSED FG TD', 'DOWNS TD', 'FG TD',
                              'END OF HALF TD', 'END OF GAME TD', 'SF')
                                                                   then 'defensive score'
        when drive_result in ('INT', 'FUMBLE', 'DOWNS')            then 'turnover'
        when drive_result in ('PUNT', 'BLOCKED PUNT')              then 'punt'
        when drive_result in ('MISSED FG', 'BLOCKED FG', 'KICKOFF') then 'kick'
        when drive_result in ('END OF HALF', 'END OF GAME', 'END OF 4TH QUARTER')
                                                                   then 'clock'
        when drive_result = 'Uncategorized'                        then 'unknown'
    end                                                     as drive_result_category,

    -- WHO PUT POINTS ON THE BOARD, from the vocabulary rather than from the score delta.
    --
    -- The delta is what PROVED the mapping (see the counts above) but it is not what should
    -- drive it: the score fields are end-of-drive snapshots and pick up a PAT or a
    -- subsequent score, which is why plain 'TD' shows 698 drives where the defense's score
    -- also moved. The vocabulary is the cleaner signal and the icon follows it.
    case
        when drive_result in ('TD', 'FG')                          then 'offense'
        when drive_result in ('INT TD', 'FUMBLE RETURN TD', 'FUMBLE TD', 'PUNT TD',
                              'PUNT RETURN TD', 'MISSED FG TD', 'DOWNS TD', 'FG TD',
                              'END OF HALF TD', 'END OF GAME TD', 'SF')
                                                                   then 'defense'
    end                                                     as scoring_side,

    start_offense_score,
    start_defense_score,
    end_offense_score,
    end_defense_score
from resolved
