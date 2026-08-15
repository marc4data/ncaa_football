-- Seasons before CFBD recorded kickoff times store every game at midnight UTC as a
-- date-only value. Converting those to a local timezone moves them back a day, which
-- silently misdates 60% of all games ever played. This asserts we do not.

select
    s.season,
    s.game_id,
    s.game_date,
    g.start_date
from {{ ref('mart_team_schedule') }} s
join {{ ref('stg_games') }} g on g.game_id = s.game_id
where not s.kickoff_time_known
  and s.game_date <> (g.start_date at time zone 'UTC')::date
