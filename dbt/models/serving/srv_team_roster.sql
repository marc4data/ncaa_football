-- Team page, Roster section: one row per player on a team's roster in a season.
--
-- 68,357 rows across 2024-2026, which is every season cfdb holds a roster feed for. A team
-- page for 2019 has no roster and says so rather than rendering an empty table — /roster is
-- `recent` scope and that is not a defect.
--
-- Straight off dim_athlete with no aggregation: the dimension's grain is already
-- (season, player, team), which is exactly a roster. The section exists as its own view
-- rather than as columns on srv_team_overview because that view is one row per team-season
-- and this is many rows per team-season — a different grain is a different relation, and the
-- site reads one relation per query.
--
-- Ordered by position then jersey in the page rather than here, because a serving table has
-- no inherent order and a page that relies on one is relying on a coincidence.
select
    a.athlete_sk,
    a.season,
    a.player_id,
    a.athlete_slug                as player_slug,
    a.full_name,
    a.first_name,
    a.last_name,
    a.team,
    a.team_id,
    a.team_slug,
    a.team_display,
    a.conference,
    a.classification,
    a.is_listed_team,
    a.position,
    a.jersey,
    a.class_year,
    a.class_year_display,
    a.height_inches,
    a.height_display,
    a.weight_pounds,
    a.home_city,
    a.home_state,
    a.hometown_display,
    ao.as_of_ts
from {{ ref('dim_athlete') }} a
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'team') ao
