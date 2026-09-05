-- One row per drive. The relation the Matchup post-game Drives chart reads, and nothing else.
--
-- NAMED FOR ITS GRAIN, NOT FOR THE TAB THAT READS IT — the rule srv_game was renamed to
-- follow. The Defense split is the same rows re-sourced (a team's defensive drives are its
-- opponent's offensive drives, which is_home_offense already separates), so it is a second
-- reading of this view and not a second model.
--
-- WAITS FOR fct_drive RATHER THAN READING STAGING. ci/check_layering.py forbids a serving
-- model depending on staging, and the spec ruled on it directly: "Does the drive chart wait
-- for fct_drive, or does a first pass read staging? Wait."
--
-- EVERY FILTER AND EVERY LABEL THE PAGE NEEDS IS A COLUMN HERE (G-2, G-3): one relation, a
-- WHERE on game_id, no joins and no arithmetic in the app. That includes the two things a
-- chart normally computes on the fly and must not here — the mm:ss duration, and the band a
-- drive belongs to.
--
-- ==========================================================================================
-- THE SCOPE BOUNDARY IS CARRIED AS DATA, because "no drives" has to read as a state and not
-- as a defect.
--
-- Drives are 2024+ (`recent` scope). A Matchup page for a 2019 game gets zero rows, and zero
-- rows carry no columns to explain themselves — so the bounds ride on every row instead:
--
--   normal path   the rows are there; the footnote reads its own drives_min_season
--   empty path    `select drives_min_season, drives_max_season from srv_drive limit 1`
--
-- One table, no WHERE, no join, no math — inside the site's read rule, and it lets the page
-- say "cfdb holds drives from 2024" rather than rendering an empty chart. ⚠️ Pass 2 should
-- confirm that shape against the real page before it is treated as settled.
-- ==========================================================================================

with scope as (

    -- Constants, not a grain. Cross-joined below so a single-row read can reach them.
    select min(season) as drives_min_season,
           max(season) as drives_max_season
    from {{ ref('fct_drive') }}

)

select
    d.drive_sk,
    d.drive_id,
    d.game_id,
    d.drive_number,

    d.season,
    d.week,
    d.season_type,
    d.game_date,
    d.is_completed,

    -- ---------------------------------------------------------------------------------------
    -- BANDS. Away above home, per the layout, and pre-resolved so the page orders on a column
    -- rather than re-deriving the convention every render.
    -- ---------------------------------------------------------------------------------------
    d.is_home_offense,
    case when d.is_home_offense then 'home' else 'away' end as band,
    case when d.is_home_offense then 2 else 1 end          as band_order,

    -- ---------------------------------------------------------------------------------------
    -- THE RAIL: whose offense this band is. Logo and team name, rotated -90 by the page.
    -- ---------------------------------------------------------------------------------------
    d.offense,
    d.offense_team_id,
    d.offense_conference,
    {{ team_identity('ot', 'd.offense', 'offense_') }},
    ot.mascot                                              as offense_mascot,
    ot.logo_source_url                                     as offense_logo_url,

    -- ---------------------------------------------------------------------------------------
    -- THE ENDZONE AT x=100: the team being driven at. A different team in each band, which is
    -- what "endzones labelled with the opposing team" means once both offenses drive right.
    --
    -- THE DEGRADED STATE IS RESOLVED HERE, NOT IN THE APP. dim_team already walks the contrast
    -- ladder and lands on neutral grey when nothing clears 3:1, so a team WITH a row always
    -- has a readable colour. A team with NO row — a non-FBS opponent, absent from /teams — is
    -- the case the left join leaves null, and it gets the same neutral grey with color_source
    -- saying so. An endzone in fallback grey is correct; one in an unreadable team colour is
    -- not, and one in NULL is a crash.
    -- ---------------------------------------------------------------------------------------
    d.opponent_team_id,
    {{ team_identity('pt', 'd.opponent', 'opponent_') }},
    pt.mascot                                              as opponent_mascot,
    pt.logo_source_url                                     as opponent_logo_url,
    coalesce(pt.color_on_light, '#6b6b68')                 as opponent_color_on_light,
    coalesce(pt.color_on_dark,  '#9a9a96')                 as opponent_color_on_dark,
    coalesce(pt.color_source, 'fallback')                  as opponent_color_source,

    d.defense,
    d.defense_team_id,
    d.defense_conference,

    -- ---------------------------------------------------------------------------------------
    -- THE BAR. start -> end on ONE coordinate, so both bands share one x scale by construction
    -- rather than by convention. See fct_drive's header for the measurement that chose it.
    -- ---------------------------------------------------------------------------------------
    d.start_yards_from_own_goal,
    d.end_yards_from_own_goal,
    d.is_negative_drive,
    -- False on 118 of 78,502 drives, where CFBD's end coordinate lands off the field. The page
    -- renders the ROW and suppresses the BAR: a possession that is missing from a game's
    -- sequence is a worse lie than a bar that admits it does not know where it ended.
    d.is_end_on_field,
    -- Carried, not collapsed. Staging kept both measurements deliberately and the invariant
    -- between them is what proves the coordinate above is the right one.
    d.start_yardline,
    d.start_yards_to_goal,
    d.end_yardline,
    d.end_yards_to_goal,

    -- ---------------------------------------------------------------------------------------
    -- THE Y-AXIS: drive number, start time, duration. BOTH start-time forms are here because
    -- the spec's phrase is ambiguous between them; Marc picks one against a real render.
    -- ---------------------------------------------------------------------------------------
    d.start_period,
    d.end_period,
    d.start_clock_display,                -- "Q2 07:14"      — the clock at the snap
    d.elapsed_from_kickoff_seconds,       -- 1666            — elapsed from kickoff
    d.elapsed_seconds,
    d.elapsed_display,                    -- "2:14"          — duration, pre-formatted

    -- ---------------------------------------------------------------------------------------
    -- THE RESULT ICON. See fct_drive: a `TD` suffix on a turnover means the DEFENSE scored, so
    -- scoring_side is what keeps ~900 drives off the wrong side of the game.
    -- ---------------------------------------------------------------------------------------
    d.drive_result,
    d.drive_result_key,
    d.drive_result_category,
    d.scoring_side,
    d.is_scoring_drive,
    d.plays,
    -- ⚠️ `yards` IS NOT THE BAR'S LENGTH and must not be used to label it. It disagrees with
    -- the coordinate delta on 11,987 of 78,502 drives (15%) — 33% of touchdowns and 20% of
    -- interceptions — because the end coordinate is where a return finished while `yards` is
    -- what the offense gained. Both are correct; they measure different things.
    d.yards,
    d.start_offense_score,
    d.start_defense_score,
    d.end_offense_score,
    d.end_defense_score,

    s.drives_min_season,
    s.drives_max_season,

    ao_src.as_of_ts
from {{ ref('fct_drive') }} d
left join {{ ref('dim_team') }} ot on ot.season = d.season and ot.team_id = d.offense_team_id
left join {{ ref('dim_team') }} pt on pt.season = d.season and pt.team_id = d.opponent_team_id
cross join scope s
-- AC-G.35: the page's "as of" stamp is a COLUMN sourced from when this view's data was last
-- loaded, never from now() in the app.
--
-- ⚠️ 'game' IS THE CLOSEST HONEST DOMAIN, NOT THE RIGHT ONE. mart_as_of maps endpoints to
-- domains and has no row for 'drives', so this stamp is really "when /games last loaded".
-- Drives are fetched on the same cadence, so it is close — but it is not the same fetch, and
-- a drive chart could read fresher or staler than it is.
--
-- THE FIX IS ONE LINE — ('drives', 'drive') in mart_as_of's endpoint_domain list — AND IT IS
-- NOT IN THIS PROMPT'S FILES (Part 0b). Reported rather than made.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao_src
