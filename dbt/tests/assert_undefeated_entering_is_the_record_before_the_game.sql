{{ config(severity='error') }}
-- A196 (cfdb-main-R-2036). "Undefeated entering the game" reads the record BEFORE it.
--
-- THE COLUMN CHOICE IS THE WHOLE RULE, AND THE WRONG ONE IS AVAILABLE AND PLAUSIBLE.
-- srv_game publishes home_wins/home_losses, which are SEASON-TO-DATE totals: Ohio State 2026
-- carries home_wins 2, home_losses 1 on weeks 1, 3, 4 and 6 alike. Using them would ask "is
-- this team undefeated NOW", which for a week-4 fixture is a fact from the future - and it
-- would look entirely reasonable in the SQL.
--
-- The flag instead reads fct_team_record_week joined at THIS game's week, whose wins/losses
-- lead INTO it. This test recomputes the rule from that mart and compares.
--
-- AND IT PINS THE OPENER CASE: a 0-0 side is untested, not unbeaten, so at least one game
-- must have been played. Without that clause every week-1 game qualifies, which is both wrong
-- and invisible - week 1 is exactly when nobody has a losing record yet.
with expected as (
    select
        g.game_id,
        g.spread_current,
        coalesce(
            abs(g.spread_current) < 4
            and (
                (g.home_classification = 'fbs'
                 and coalesce(rh.losses, 0) = 0 and coalesce(rh.wins, 0) >= 1)
             or (g.away_classification = 'fbs'
                 and coalesce(ra.losses, 0) = 0 and coalesce(ra.wins, 0) >= 1)
            ), false) as should_be,
        g.is_undefeated_close
    from {{ ref('srv_game') }} g
    left join {{ ref('fct_team_record_week') }} rh
        on  rh.season = g.season and rh.season_type = g.season_type
        and rh.week = g.week and rh.team_id = g.home_team_id
    left join {{ ref('fct_team_record_week') }} ra
        on  ra.season = g.season and ra.season_type = g.season_type
        and ra.week = g.week and ra.team_id = g.away_team_id
)
select game_id, spread_current, should_be, is_undefeated_close
from expected
where is_undefeated_close <> should_be
