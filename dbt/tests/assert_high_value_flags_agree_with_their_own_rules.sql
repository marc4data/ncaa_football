{{ config(severity='error') }}
-- A196 (cfdb-main-R-2035). The three high-value flags say what their own inputs say.
--
-- MARC, v12: "Look for Top 25 matchups. Matchups with an undefeated FBS team and a
-- ABS(spread) < 4". This re-derives both rules from the columns the flags are built from and
-- fails on any row where the published flag and the rule disagree.
--
-- WHY RE-DERIVE RATHER THAN PIN NAMED GAMES. Anchors pin what they can see and are silent
-- where the game is absent (2.3.3) - and CI's fixture is a deliberate sample that holds
-- neither of A196's hand-picked week-4 fixtures. A property recomputed from the same row runs
-- everywhere, on every season in the corpus, and cannot be vacuous: it fires on any row at
-- all where the flag and its inputs part company.
--
-- THE BOUNDARY IS THE POINT. `< 4` is strict: a 3.5-point line qualifies and a 4.0 line does
-- not. That is the one place this rule can be wrong by a rounding, so it is recomputed with
-- the same strict comparison rather than described.
--
-- NOT re-derived here: "undefeated" needs the record LEADING INTO the game, and srv_game
-- publishes only the display string for that (home_team_record_display). Parsing a string to
-- check a boolean would test the parser. The undefeated half is asserted in
-- assert_undefeated_entering_is_the_record_before_the_game, against the mart that holds the
-- numbers.
select
    game_id,
    season,
    week,
    home_rank,
    away_rank,
    spread_current,
    is_top25_matchup,
    is_high_value
from {{ ref('srv_game') }}
where
    -- both ranked, and only then
    is_top25_matchup <> (home_rank is not null and away_rank is not null)
    -- the union rule
    or is_high_value <> coalesce(is_top25_matchup or is_undefeated_close, false)
    -- a flag must never be null; a page filtering on one would drop the row silently
    or is_top25_matchup is null
    or is_undefeated_close is null
    or is_high_value is null
    -- the close rule cannot fire without a line, nor outside the strict boundary
    or (is_undefeated_close and spread_current is null)
    or (is_undefeated_close and abs(spread_current) >= 4)
