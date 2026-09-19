-- A177 (cfdb-main-R-1771). `srv_team_week.record_before_display` must be the SAME string
-- `fct_team_record_week` holds for that exact (season, season_type, week, team) — and it must
-- be the LEADING-INTO record, not the one including the week's own game.
--
-- 🚨 THE JOIN IS FOUR EQUALITIES AND THREE OF THEM ARE EASY TO GET RIGHT. `week` is the one
-- that is not: this view and that fact are both built on the `dim_team_week` spine, so a join
-- that dropped `season_type` would still match ~everything in a regular season and quietly
-- mispair a postseason row, where week numbers restart at 1 and a bowl game would collect an
-- October record.
--
-- ⚠️ AND IT PINS THE OFF-BY-ONE FROM THE OTHER END. `wins`/`losses` on that fact are the
-- leading-into counts (a `1 preceding` frame); `wins_after` is the including one. If this
-- column were ever re-sourced from the wrong pair it would still be a valid "W-L" string, and
-- this is what would say otherwise.
select
    w.season, w.season_type, w.week, w.team_id,
    w.record_before_display as published,
    r.current_record        as the_fact_says,
    r.wins, r.losses, r.wins_after, r.losses_after
from {{ ref('srv_team_week') }} w
join {{ ref('fct_team_record_week') }} r
  on  r.season      = w.season
  and r.season_type = w.season_type
  and r.week        = w.week
  and r.team_id     = w.team_id
where w.record_before_display is distinct from r.current_record
