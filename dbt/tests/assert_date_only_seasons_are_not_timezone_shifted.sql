{{ config(tags=['full_refresh_only']) }}
-- TAGGED `full_refresh_only`: excluded from cfbd_scores_refresh, which rebuilds one side of
-- this comparison and not the other. Full authority on the weekly +tag:production
-- build, which rebuilds both. See dags/scores_refresh_dag.py TEST_EXCLUDE.
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
  and s.game_date <> {{ to_utc_date('g.start_date') }}
