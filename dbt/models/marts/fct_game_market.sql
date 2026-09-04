-- THE MARKET FOR ONE GAME: the latest line, and the closing line, in one row.
--
-- TWO QUESTIONS THAT MUST NOT BE CONFLATED, which is why both live here rather than one
-- being derived from the other. "What is the market saying now" is the newest snapshot of
-- all; "what will the result be judged against" is the last snapshot BEFORE KICKOFF. They
-- are the same number for a game that has not started and different for one that has.
--
-- EXTRACTED FROM `srv_game`, WHERE IT WAS TWO CTEs, BECAUSE A SECOND CONSUMER ARRIVED.
--
-- The weekly distribution models need exactly this rule — a game contributes its closing
-- number once it has kicked off — and the only place it existed was inside a serving view.
-- Marts cannot read serving (ci/check_layering.py rule 3), so the choice was to copy the
-- logic down a layer or move it. Copying would have made three implementations of one
-- definition, which is the defect this repo spent two rounds removing from the upset
-- thresholds and one from the legend.
--
-- The comments below are the originals from srv_game; the reasoning did not change, only
-- where it lives.
--
-- WHY THE SPREAD AND THE TOTAL RANK SEPARATELY (R-142). Not every betting-line row carries an
-- over_under, so taking the total from whichever row won the SPREAD's ranking nulls it
-- whenever that row happens to be spread-only — a missing number that looks like an absent
-- market. Ranking rows that have a total first is the fix, and it needs its own window.
--
-- WHY `basis` TRAVELS WITH EACH NUMBER. Our snapshot history begins 2026-08-15, so for an
-- older game the only line held is whatever CFBD returned when we fetched it — a real market
-- number whose timestamp is our FETCH time, not a pre-kickoff observation. Calling both
-- "close" would conflate a line we watched with one we were told about.

with latest as (

    -- Most recent line of all, for the "current" market number.
    select game_id, spread, over_under, spread_open, over_under_open,
           home_moneyline, away_moneyline, provider_key, snapshot_ts
    from (
        select b.*, row_number() over (partition by b.game_id
                                       order by b.snapshot_ts desc, b.provider_key) as recency
        from {{ ref('fct_betting_line') }} b
    ) r where recency = 1

),

spread_ranked as (
    select
        b.game_id, b.spread, b.provider_key, b.snapshot_ts,
        case when b.snapshot_ts <= g.start_date then 'observed_before_kickoff'
             else 'as_recorded_by_cfbd' end as basis,
        row_number() over (
            partition by b.game_id
            order by case when b.snapshot_ts <= g.start_date then 0 else 1 end,
                     b.snapshot_ts desc, b.provider_key
        ) as recency
    from {{ ref('fct_betting_line') }} b
    join {{ ref('fct_game') }} g on g.game_id = b.game_id
),

total_ranked as (
    select
        b.game_id, b.over_under, b.provider_key, b.snapshot_ts,
        case when b.snapshot_ts <= g.start_date then 'observed_before_kickoff'
             else 'as_recorded_by_cfbd' end as basis,
        row_number() over (
            partition by b.game_id
            order by case when b.snapshot_ts <= g.start_date then 0 else 1 end,
                     b.snapshot_ts desc, b.provider_key
        ) as recency
    from {{ ref('fct_betting_line') }} b
    join {{ ref('fct_game') }} g on g.game_id = b.game_id
    where b.over_under is not null
),

spread_close as (select * from spread_ranked where recency = 1),
total_close  as (select * from total_ranked  where recency = 1)

-- FULL OUTER JOIN, not a left join from the spread. A game can hold a total and no spread —
-- rare, but a left join would silently drop the total in that case, which is the same class
-- of quiet loss R-142 fixed inside the total's own ranking.
select
    coalesce(l.game_id, s.game_id, t.game_id)  as game_id,
    {{ surrogate_key(['coalesce(l.game_id, s.game_id, t.game_id)']) }} as game_sk,

    l.spread                        as spread_current,
    l.over_under                    as total_current,
    l.spread_open,
    l.over_under_open,
    l.home_moneyline,
    l.away_moneyline,
    l.provider_key                  as current_provider_key,
    l.snapshot_ts                   as line_snapshot_ts,

    s.spread                        as spread_at_close,
    s.provider_key                  as spread_at_close_provider,
    s.basis                         as spread_at_close_basis,
    s.snapshot_ts                   as spread_at_close_ts,

    t.over_under                    as total_at_close,
    t.provider_key                  as total_at_close_provider,
    t.basis                         as total_at_close_basis,
    t.snapshot_ts                   as total_at_close_ts
from latest l
-- FULL OUTER throughout: a game can hold a total and no spread, or a closing line and no
-- current one. A left join from any single side would silently drop the others, which is the
-- same class of quiet loss R-142 fixed inside the total's own ranking.
full outer join spread_close s on s.game_id = l.game_id
full outer join total_close  t on t.game_id = coalesce(l.game_id, s.game_id)
