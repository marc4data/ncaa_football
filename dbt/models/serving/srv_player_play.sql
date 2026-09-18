-- Players page: the play-level drill-down — one row per play a player is credited on.
--
-- The section the site IA calls out as the thing nobody in the comp set offers publicly:
-- attributed plays, filterable by down, distance and result.
--
-- Every filter the page offers is a COLUMN here, because the site reads one relation per
-- query with a WHERE and no joins (G-2) and does no arithmetic (G-3). down_distance_display,
-- distance_bucket and field_zone are all precomputed in fct_play for exactly this.
--
-- COVERAGE: /plays/stats caps at 2,000 records per request, so the original week-scoped
-- fetch returned an arbitrary 11% of games, skewed to whichever the API listed first. Fixed
-- at the source by fanning out per game: 375,925 rows over 1,884 games, with conference
-- coverage now even. The fan-out runs over completed FBS games, which is the project's
-- scope, so absence here means "cfdb did not ask about that game", never "the player did
-- nothing".
select
    p.play_stat_sk,
    p.play_id,
    -- A168 (cfdb-main-R-1316). THE DRIVE KEY, WHICH fct_play_stat HAS CARRIED ALL ALONG AND
    -- THIS VIEW SIMPLY DID NOT SELECT. Two pieces of work were blocked on its absence:
    -- B137's per-play borders on the Drives panel (Marc, v19: "add borders around the yards
    -- gained by plays > 10 yards ... what type and who gained the yards in the tooltip"), and
    -- cfdb-wta-R-1177's score_impact, researched by A158 and unbuilt since.
    --
    -- MEASURED BEFORE PUBLISHING, both of §2.5's questions: drive_id is NULL on 0 of 409,846
    -- rows (100.00%, and 100.00% in each of 2024, 2025 and 2026), and 100.00% of them join to
    -- a drive srv_drive actually publishes. So a play-level border draws on every play rather
    -- than on a subset nobody measured.
    p.drive_id,
    p.game_id,
    p.season,
    p.week,
    p.season_type,
    p.game_date,
    p.player_id,
    p.player_slug,
    p.player_name,
    p.team,
    p.team_id,
    p.conference,
    p.opponent,
    p.stat_type,
    p.stat,
    p.period,
    p.down,
    p.distance,
    p.yards_to_goal,
    -- ==========================================================================================
    -- A170 (cfdb-main-R-1323). WHERE THE PLAY IS ON THE FIELD — the coordinate B138 stopped at.
    --
    -- Marc, v19: "Is there a way to add borders around the yards gained by plays > 10 yards
    -- long?" B138 shipped the tooltip half and correctly refused the geometry: this view
    -- published ONE position (the snap), and a segment needs two ends. Computing the second in
    -- the page is arithmetic between two published columns, which §4.2.1 names outright.
    --
    -- 🚨 THE PROMPT ASKED FOR `start_yardline`/`end_yardline` AS "THE ABSOLUTE FRAME" AND THAT
    -- IS BACKWARDS — fct_play's own measurement says so, and A170 re-ran it at play grain:
    -- `yardline` is absolute in the HOME team's frame, so a segment drawn on it MIRRORS on the
    -- away band. `yards_from_own_goal` is the coordinate srv_drive's bar is drawn on, and a
    -- play segment must share it or the border will not land inside the bar it belongs to.
    -- Both frames are published, as srv_drive publishes both, so the page never converts.
    --
    -- NAMED EXACTLY AS srv_drive NAMES THEM. The one deliberate exception is that
    -- `start_yards_to_goal` is NOT added: `yards_to_goal` above IS that number and has been
    -- published under that name since this view was built. Renaming it is an expand -> migrate
    -- -> contract on a column the Players page filters on (§3.3); publishing a synonym beside it
    -- is the duplicate this project has been bitten by. It stays, and this comment is the map.
    -- ==========================================================================================
    p.start_yardline,
    p.start_yards_from_own_goal,
    p.end_yardline,
    p.end_yards_to_goal,
    p.end_yards_from_own_goal,
    -- 🚨 FALSE MEANS "yards_gained IS NOT A FIELD-POSITION DELTA ON THIS PLAY", not "bad row".
    -- 13,270 of 409,846 published rows (3.24%), and they are categories rather than a scatter:
    -- field goals, where yards_gained is the kick distance, are 12,234 of them, and the rest is
    -- mostly interception and kickoff returns, where the yards belong to the other team.
    -- The page draws the row and suppresses the SEGMENT, exactly as the Drives panel does with
    -- srv_drive.is_end_on_field.
    p.is_end_on_field,
    p.down_distance_display,
    p.distance_bucket,
    p.field_zone,
    p.play_type,
    p.play_text,
    p.yards_gained,
    p.is_scoring_play,
    p.ppa,
    ao.as_of_ts
from {{ ref('fct_play_stat') }} p
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'play') ao
