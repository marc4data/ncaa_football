-- Players page: the play-level drill-down — one row per play a player is credited on.
--
-- The section the site IA calls out as the thing nobody in the comp set offers publicly:
-- attributed plays, filterable by down, distance and result.
--
-- Every filter the page offers is a COLUMN here, because the site reads one relation per
-- query with a WHERE and no joins (G-2) and does no arithmetic (G-3). down_distance_display,
-- distance_bucket and field_zone are all precomputed in fct_play for exactly this.
--
-- COVERAGE: /plays/stats caps at 2,000 records per request, so a week-scoped fetch returned
-- an arbitrary 11% of games. That is fixed at the source — the endpoint now fans out per
-- game — but this view is only as complete as what has landed. Absence here means "no stat
-- line landed for that play", never "the player did nothing".
select
    p.play_stat_sk,
    p.play_id,
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
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
