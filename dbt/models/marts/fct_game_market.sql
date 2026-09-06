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
    t.snapshot_ts                   as total_at_close_ts,

    -- ============================================================================
    -- "FAVOURITE" IS NOT ONE THING, AND NOTHING RECORDED WHICH ONE A ROW MEANT (R-393).
    --
    -- The Looking Back recap lists derive it two different ways without saying so. Two of
    -- them rank on the SPREAD (points missed, points covered by); the third ranks on
    -- market-implied win probability, which comes from the MONEYLINE. A single column called
    -- `favorite` would silently mean one of two things depending on which list read it.
    --
    -- THEY DISAGREE, MEASURED: of 114 completed 2026 games carrying both, 2 disagree.
    -- One is the -100000 sentinel (R-391 nulls it, so that one resolves itself). The other is
    -- Nevada -1 vs Western Kentucky, where the moneyline had the AWAY side favoured — and
    -- that game is currently #2 on the "favourites that covered" list. Under the moneyline
    -- definition it is not on that list at all; it is an underdog winning by 35.
    --
    -- So both derivations are carried, with the prefix holding the provenance per
    -- cfdb-metric-naming, and a flag where they part company. No column here is named bare
    -- `favorite`: the page picks a definition and says which, and the disagreement is
    -- countable rather than invisible.
    --
    -- Spread convention, verified rather than assumed: from the HOME perspective, negative =
    -- home favoured (Missouri -55.5 vs Arkansas-Pine Bluff; home won by 40).
    -- ============================================================================
    case when coalesce(s.spread, l.spread) < 0 then 'home'
         when coalesce(s.spread, l.spread) > 0 then 'away' end   as spread_favorite_side,

    -- A MORE NEGATIVE MONEYLINE IS THE SHORTER PRICE. Null-safe on purpose: a book that posts
    -- one side only must not make that side the favourite by default.
    case when l.home_moneyline is null or l.away_moneyline is null then null
         when l.home_moneyline < l.away_moneyline then 'home'
         when l.away_moneyline < l.home_moneyline then 'away' end as moneyline_favorite_side,

    -- Null when either derivation is unavailable — NOT false. "They agree" and "we cannot
    -- tell" are different answers and collapsing them is how the disagreement got missed.
    case when coalesce(s.spread, l.spread) is null
              or coalesce(s.spread, l.spread) = 0
              or l.home_moneyline is null or l.away_moneyline is null
              or l.home_moneyline = l.away_moneyline then null
         else (case when coalesce(s.spread, l.spread) < 0 then 'home' else 'away' end)
              is distinct from
              (case when l.home_moneyline < l.away_moneyline then 'home' else 'away' end)
    end                                                          as favorite_definitions_disagree
from latest l
-- FULL OUTER throughout: a game can hold a total and no spread, or a closing line and no
-- current one. A left join from any single side would silently drop the others, which is the
-- same class of quiet loss R-142 fixed inside the total's own ranking.
full outer join spread_close s on s.game_id = l.game_id
full outer join total_close  t on t.game_id = coalesce(l.game_id, s.game_id)
