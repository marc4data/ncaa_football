-- The other half of R-127, and the reason it is a separate test.
--
-- Widening the guard so a team that has not played yet gets 0-0 could easily widen it to
-- EVERYONE, and a rule that never discriminates is indistinguishable from no rule — this
-- project has shipped that exact failure before (a colour-source hint that fired on all 34,061
-- rows). If this returns zero rows the Division II protection has quietly evaporated.
--
-- Measured when written: 6,125 of 485,005 rows (1.3%) are legitimately unknown.
select count(*) as unknown_rows
from {{ ref('fct_team_record_week') }}
where not record_is_known
having count(*) = 0
