{{ config(
    materialized='incremental',
    unique_key='betting_line_sk',
    incremental_strategy='append'
) }}

-- One row per (game, provider, snapshot_ts). APPEND-ONLY.
--
-- This is the only table in the project whose history cannot be rebuilt. A full refresh
-- would recompute from whatever /lines returns today and collapse every historical snapshot
-- to the current value, destroying the movement series that Closing Line Value depends on.
-- Incremental append, and no DAG may run this with --full-refresh.
--
-- spread and formatted_spread are BOTH kept and are NOT reconciled. They disagree
-- historically and neither is known authoritative; a test asserting they agree would fail
-- on known-bad data, which is noise rather than signal. The consumer chooses.

with lines as (

    select * from {{ ref('stg_lines') }}
    -- One row per book per snapshot: see stg_lines for the duplicate-spelling case.
    where provider_row_rank = 1
    {% if is_incremental() %}
      and snapshot_ts > (select coalesce(max(snapshot_ts), '1900-01-01') from {{ this }})
    {% endif %}

)

select
    {{ surrogate_key(['l.game_id', 'l.provider_key', 'l.snapshot_ts']) }} as betting_line_sk,
    {{ surrogate_key(['l.game_id']) }} as game_sk,
    l.game_id,
    p.provider_sk,
    l.provider_key,
    l.provider_raw,
    l.snapshot_ts,
    l.season,
    l.week,
    l.season_type,
    l.spread,
    l.formatted_spread,
    l.spread_open,
    l.over_under,
    l.over_under_open,
    l.home_moneyline,
    l.away_moneyline
from lines l
left join {{ ref('dim_provider') }} p on p.provider_key = l.provider_key
