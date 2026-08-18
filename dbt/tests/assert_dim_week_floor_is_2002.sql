-- dim_week covers 2002+ because CFBD publishes no /calendar before then, while fct_game
-- covers 1869+. That floor bounds every week-grain join and is asserted rather than left as
-- folklore: if CFBD ever extends coverage this fails, which is correct — the constraint must
-- be re-documented, not silently widened.
select min(season) as earliest_week_season, 2002 as expected_floor
from {{ ref('dim_week') }}
having min(season) <> 2002
