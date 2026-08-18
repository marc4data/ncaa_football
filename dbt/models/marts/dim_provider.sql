{{ config(materialized='table') }}

-- One row per sportsbook.
--
-- Small, but load-bearing: without it, "DraftKings" and "Draft Kings" are two dimension
-- members and every provider-level comparison silently splits. provider_raw is preserved
-- on the fact so the original spelling is never lost.

with observed as (

    select
        provider_key,
        min(provider_raw)  as first_spelling,
        min(snapshot_ts)   as first_seen_at,
        max(snapshot_ts)   as last_seen_at,
        count(*)           as line_rows
    from {{ ref('stg_lines') }}
    where provider_key is not null
    group by provider_key

)

select
    {{ surrogate_key(['provider_key']) }} as provider_sk,
    provider_key,
    case provider_key
        when 'draftkings' then 'DraftKings'
        when 'espn_bet'   then 'ESPN Bet'
        when 'bovada'     then 'Bovada'
        else first_spelling
    end as provider_name,
    first_seen_at,
    last_seen_at,
    line_rows
from observed
