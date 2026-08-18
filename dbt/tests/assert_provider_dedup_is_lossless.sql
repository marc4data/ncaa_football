-- The provider dedup in stg_lines discards rows. This proves it discards nothing of value:
-- for every duplicate group, the row we drop must not carry a non-null value where the row
-- we keep is null. If it ever does, the dedup rule is wrong and we are losing data quietly.

with ranked as (
    select * from {{ ref('stg_lines') }}
),

kept as (
    select game_id, provider_key, snapshot_ts,
           spread, over_under, home_moneyline, away_moneyline, formatted_spread
    from ranked where provider_row_rank = 1
),

dropped as (
    select game_id, provider_key, snapshot_ts,
           spread, over_under, home_moneyline, away_moneyline, formatted_spread
    from ranked where provider_row_rank > 1
)

select
    d.game_id, d.provider_key, d.snapshot_ts,
    'dropped row carries data the kept row lacks' as issue
from dropped d
join kept k
  on k.game_id = d.game_id
 and k.provider_key = d.provider_key
 and k.snapshot_ts = d.snapshot_ts
where (k.spread is null and d.spread is not null)
   or (k.over_under is null and d.over_under is not null)
   or (k.home_moneyline is null and d.home_moneyline is not null)
   or (k.away_moneyline is null and d.away_moneyline is not null)
   or (k.formatted_spread is null and d.formatted_spread is not null)
