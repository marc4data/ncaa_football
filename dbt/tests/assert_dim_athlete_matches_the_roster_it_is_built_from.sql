-- dim_athlete must neither invent nor drop a roster row.
--
-- The dimension joins to dim_team by NAME to resolve a team id, and a name join is exactly
-- the shape that fans out silently when the right-hand side is not unique on the join key.
-- dim_team is one row per (season, team_id), so two teams sharing a school name in one
-- season would duplicate every athlete on that roster and nothing else here would notice.
--
-- Asserted as an exact row-count match against the source rather than as a uniqueness test,
-- because it catches the loss case too: an inner join slipping in would drop the 321 NAIA
-- and Division II athletes whose team is absent from /teams, and that is the specific
-- mistake this model's header argues against.
with source_rows as (select count(*) as n from {{ ref('stg_roster') }}),
     dim_rows    as (select count(*) as n from {{ ref('dim_athlete') }})
select source_rows.n as roster_rows, dim_rows.n as athlete_rows
from source_rows, dim_rows
where source_rows.n <> dim_rows.n
