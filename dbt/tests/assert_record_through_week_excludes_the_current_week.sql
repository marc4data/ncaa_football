-- The record for week N must not contain week N's result. R-084.
--
-- THE SINGLE MOST LIKELY DEFECT IN THIS MODEL, and the one that looks right on every row
-- except the ones anyone checks. A running total framed `unbounded preceding and current row`
-- rather than `... and 1 preceding` produces a column that is wrong by exactly one game, on
-- every row, forever — and a Schedule page showing "9-2" beside the game that made it 9-2
-- reads perfectly plausibly.
--
-- Asserted structurally rather than against one team: for every row, the record leading into
-- the NEXT week must equal this row's record plus this week's actual results. If the current
-- week leaked into the running total, this identity breaks everywhere at once.
--
-- Bye weeks are included deliberately — a week with no game must carry the record forward
-- unchanged, which this identity also proves.
with weekly as (
    select
        r.season, r.team_id, r.season_type_ordinal, r.week,
        r.wins, r.losses, r.ties,
        coalesce(g.wins, 0)   as played_wins,
        coalesce(g.losses, 0) as played_losses,
        coalesce(g.ties, 0)   as played_ties,
        lead(r.wins)   over w as next_wins,
        lead(r.losses) over w as next_losses,
        lead(r.ties)   over w as next_ties
    from {{ ref('fct_team_record_week') }} r
    left join (
        select season, season_type, week, team_id,
               sum(case when won then 1 else 0 end)  as wins,
               sum(case when lost then 1 else 0 end) as losses,
               sum(case when tied then 1 else 0 end) as ties
        from (
            select season, season_type, week, home_team_id as team_id,
                   home_points > away_points as won, home_points < away_points as lost,
                   home_points = away_points as tied
            from {{ ref('fct_game') }}
            where is_completed and home_points is not null and away_points is not null
            union all
            select season, season_type, week, away_team_id,
                   away_points > home_points, away_points < home_points,
                   away_points = home_points
            from {{ ref('fct_game') }}
            where is_completed and home_points is not null and away_points is not null
        ) sides
        group by season, season_type, week, team_id
    ) g on g.season = r.season and g.season_type = r.season_type
       and g.week = r.week and g.team_id = r.team_id
    where r.has_completed_games
    window w as (partition by r.season, r.team_id
                 order by r.season_type_ordinal, r.week)
)
select season, team_id, week, wins, played_wins, next_wins, losses, played_losses, next_losses
from weekly
where next_wins is not null
  and (next_wins   <> wins   + played_wins
    or next_losses <> losses + played_losses
    or next_ties   <> ties   + played_ties)
