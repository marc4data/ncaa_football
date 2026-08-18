-- A new sportsbook must surface LOUDLY, not quietly become a dimension member or vanish.
-- Every provider_raw CFBD returns has to resolve to a canonical provider_key; an unmapped
-- value fails the build and forces a deliberate mapping decision.
select distinct provider_raw, count(*) as line_rows
from {{ ref('stg_lines') }}
where provider_key is null
group by provider_raw
