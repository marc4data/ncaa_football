-- srv_drive must hold exactly as many rows as fct_drive.
--
-- THE FAILURE THIS CATCHES IS AN INNER JOIN. srv_drive left-joins dim_team twice — for the
-- rail and for the endzone — and either one written as an inner join would silently drop
-- every drive involving a team not in /teams. The page would render a game with possessions
-- missing from the middle of it and look entirely healthy doing so.
--
-- The cross join to mart_as_of is the other way to lose the lot: if the 'game' domain row ever
-- disappears, this returns zero rows and the count goes to nothing.
select
    fct.n as fct_drive_rows,
    srv.n as srv_drive_rows
from (select count(*) as n from {{ ref('fct_drive') }}) fct
cross join (select count(*) as n from {{ ref('srv_drive') }}) srv
where fct.n <> srv.n
