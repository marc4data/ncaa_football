{{ config(
    materialized='incremental',
    unique_key='betting_line_sk',
    incremental_strategy='append'
) }}

-- One row per (game, provider, snapshot_ts). APPEND-ONLY.
--
-- CORRECTION (2026-08-18): an earlier version of this comment said the history could not be
-- rebuilt and that --full-refresh must never run. That was wrong, and the distinction
-- matters.
--
-- What cannot be recovered is a snapshot never CAPTURED — that is the DAG's job, and once a
-- 4-hour window passes uncaptured the movement in it is gone. But every snapshot we did
-- capture is a separate immutable file in the raw layer, with its observation time in the
-- manifest. Rebuilding this table from raw therefore reconstructs the full series exactly:
-- 13 files on disk, 13 distinct snapshot_ts in the fact. A full refresh is SAFE.
--
-- The thing that must never happen is deleting raw files.
--
-- Incremental exists for cost, not safety: reprocessing every snapshot on every run would
-- grow linearly across a season for no benefit.
--
-- The filter is an ANTI-JOIN ON THE KEY, not a high-water mark on snapshot_ts. A timestamp
-- watermark silently skips late-arriving OLDER files forever: catch up an engine that lags,
-- and any snapshot older than the newest row already present is filtered out and never
-- appears. That is a permanent, silent omission caused by the filter rather than by the lag.
-- Keying on betting_line_sk makes arrival order irrelevant.
--
-- spread and formatted_spread are BOTH kept and are NOT reconciled. They disagree
-- historically and neither is known authoritative; a test asserting they agree would fail
-- on known-bad data, which is noise rather than signal. The consumer chooses.

with lines as (

    select * from {{ ref('stg_lines') }}
    -- One row per book per snapshot: see stg_lines for the duplicate-spelling case.
    where provider_row_rank = 1

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
{% if is_incremental() %}
where {{ surrogate_key(['l.game_id', 'l.provider_key', 'l.snapshot_ts']) }} not in (
    select betting_line_sk from {{ this }}
)
{% endif %}
