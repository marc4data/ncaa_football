-- Rankings page, long by poll: one row per poll x season x week x team.
--
-- Long rather than wide because the page's poll tabs are a filter, not a computation —
-- the app selects WHERE poll_name = ... and renders. Wide would force the app to know
-- which columns exist, and the poll list is not stable across eras.
select
    r.poll_rank_sk,
    r.season,
    r.season_type,
    r.week,
    r.poll_name,
    p.division        as poll_division,
    p.is_committee    as poll_is_committee,
    p.display_order   as poll_display_order,
    r.rank,
    r.team_id,
    r.school,
    r.conference_name,
    r.first_place_votes,
    r.points,
    r.is_final,
    r.is_receiving_votes,
    t.color_raw       as color_primary,
    t.color_on_light,
    t.color_on_dark,
    t.logo_path,
    ao_src.as_of_ts,
    {{ team_identity('t', 'r.school') }},
    t.logo_source_url as logo_url,
    t.conference,

    -- ══ A190 (cfdb-main-R-1943): THE GAME THAT EXPLAINS THE MOVE INTO THIS POLL WEEK ══════
    --
    -- MARC, v11: "bring in srv_game as a left join... a hover that shows a simple scoreboard
    -- look (away over home) with logo, name, record, and scores for the corresponding week."
    --
    -- THE JOIN IS HERE AND NOT IN THE PAGE. Streamlit is single-table SELECT + WHERE (4.2.1),
    -- so a page-side join is the thing the display-only contract forbids outright.
    --
    -- WHICH WEEK'S GAME? POLL WEEK N REFLECTS GAME WEEK N-1, ESTABLISHED FROM THE DATA
    -- RATHER THAN ASSUMED. Poll release dates are not in the warehouse (R-1848), so A188's
    -- method was used: a team ranked in poll week N that loses in game week N falls in poll
    -- week N+1. Measured on 2026 AP:
    --
    --     game week 2   3 ranked teams lost   3 of 3 fell in poll week 3
    --     game week 3   5 ranked teams lost   4 fell and 1 dropped out of poll week 4
    --
    -- AND THE COMPETING ALIGNMENT WAS TESTED, NOT JUST THE FAVOURED ONE. If poll week N
    -- reflected game week N, those week-3 losers would have fallen in poll week 3 --
    -- instead 5 of 5 HELD OR ROSE there, because poll week 3 was published before they
    -- played. One exception exists and is explained: Louisville lost 38-41 at #9 Ole Miss in
    -- game week 1 and held #24, which is ordinary polling for a close loss to a top-10 side.
    --
    -- SO poll week 1 HAS NO EXPLAINING GAME and must not invent one -- there is no game week
    -- 0. The left join leaves it null and the page renders "No game", which is also the bye
    -- and future-week answer.
    case when eg.game_team_sk is not null then r.week - 1 end   as explained_by_game_week,
    -- Away over home, resolved HERE so the page orders nothing. `is_home` is the ranked
    -- team's own row, so it says which side of the pair that team is.
    -- 🚨 EVERY ONE OF THESE IS GATED ON THE GAME EXISTING, AND THE FIRST VERSION WAS NOT.
    -- `case when eg.is_home then A else B end` falls to B when `eg.is_home` is NULL, so a
    -- poll row with NO explaining game published the RANKED TEAM'S OWN NAME in the away
    -- slot. Measured after the first publish: explained_by_game_week was null on all 25 of
    -- 2026 AP poll week 1, exactly right -- while game_away_display was non-null on all 100
    -- rows. The page never showed it (it branches on explained_by_game_week first), which is
    -- what made it invisible: a column that reads as data and is an artefact of a CASE.
    case when eg.game_team_sk is null then null
         when eg.is_home then og.team_display else t.team_display end
                                                                as game_away_display,
    case when eg.game_team_sk is null then null
         when eg.is_home then og.logo_source_url else t.logo_source_url end
                                                                as game_away_logo_url,
    case when eg.game_team_sk is null then null
         when eg.is_home then rw_o.record_after else rw_t.record_after end
                                                                as game_away_record_after,
    case when eg.game_team_sk is null then null
         when eg.is_home then eg.points_against else eg.points_for end
                                                                as game_away_points,
    case when eg.game_team_sk is null then null
         when eg.is_home then t.team_display else og.team_display end
                                                                as game_home_display,
    case when eg.game_team_sk is null then null
         when eg.is_home then t.logo_source_url else og.logo_source_url end
                                                                as game_home_logo_url,
    case when eg.game_team_sk is null then null
         when eg.is_home then rw_t.record_after else rw_o.record_after end
                                                                as game_home_record_after,
    case when eg.game_team_sk is null then null
         when eg.is_home then eg.points_for else eg.points_against end
                                                                as game_home_points,
    eg.result                                                   as game_result_for_team
from {{ ref('fct_poll_rank') }} r
left join {{ ref('dim_poll') }} p on p.poll_sk = r.poll_sk
left join {{ ref('dim_team') }} t on t.season = r.season and t.team_id = r.team_id
-- A190: the explaining game, at poll week - 1. LEFT, because poll week 1 has no game week 0,
-- a bye leaves no row, and a poll published ahead of an unplayed week has nothing to show.
--
-- FAN-OUT, MEASURED RATHER THAN ASSUMED, AND THE FIRST DRAFT OF THIS COMMENT WAS WRONG.
-- It asserted "fct_game_team is unique on (season, season_type, week, team_id), so this
-- cannot fan out". It is NOT unique: 2,093 duplicate groups exist. Two real causes --
--
--   postseason      every playoff game is week 1, so a finalist has four rows there
--   a double week   Abilene Christian genuinely played Lamar AND Texas Tech in 2026 week 1
--
-- and 234 groups sit in 2026 regular alone. The exposure reaches real poll rows: 24 in the
-- 2026 FCS Coaches Poll, and 2 in the 2023 AP Top 25. Left unhandled this view would have
-- gained duplicate poll rows -- the exact grain break A190 was told to add a test for, and
-- the test would have caught it, which is not the same as not causing it.
--
-- SO THE JOIN PICKS EXACTLY ONE GAME: the LAST of the explaining week by date, which is the
-- one most immediately behind the poll's release. Ties on date break on game_id so the
-- choice is deterministic rather than whatever the planner returns.
left join (
    select gt.*,
           row_number() over (
               partition by gt.season, gt.season_type, gt.week, gt.team_id
               order by gt.game_date desc, gt.game_id desc) as rn
    from {{ ref('fct_game_team') }} gt
) eg
       on eg.season = r.season
      and eg.season_type = r.season_type
      and eg.week = r.week - 1
      and eg.team_id = r.team_id
      and eg.rn = 1
left join {{ ref('dim_team') }} og
       on og.season = r.season and og.team_id = eg.opponent_team_id
-- The record AFTER that game, which is what a scoreboard explaining a move should show.
-- `record_after` is fct_team_record_week's own column and srv_game already reads it the same
-- way (srv_game.sql:860) -- not a second formatting of wins/losses in this file.
left join {{ ref('fct_team_record_week') }} rw_t
       on rw_t.season = r.season and rw_t.season_type = r.season_type
      and rw_t.week = r.week - 1 and rw_t.team_id = r.team_id
left join {{ ref('fct_team_record_week') }} rw_o
       on rw_o.season = r.season and rw_o.season_type = r.season_type
      and rw_o.week = r.week - 1 and rw_o.team_id = eg.opponent_team_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'rankings') ao_src
