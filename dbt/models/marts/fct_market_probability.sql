{{ config(materialized='table', tags=['market']) }}
-- The market's own win probability, with the vig removed.
--
-- Grain: one row per game x provider x snapshot, matching fct_betting_line. Derived and
-- ADDITIVE — the raw moneylines in fct_betting_line are never modified, so a second de-vig
-- method can be computed later and compared against this one without rewriting history.
--
-- DE-VIG METHOD: multiplicative normalisation (decision log 2026-08-20).
--
--     implied_home = (1/home_decimal) / ((1/home_decimal) + (1/away_decimal))
--
-- Chosen for explainability rather than accuracy. Shin's method and the power method model
-- favourite-longshot bias better, but the gain on a two-way market is small and the
-- explanation is long. For a project whose differentiator is honest measurement, a method
-- that can be stated in one line on the Methodology page outranks a marginally better one
-- that cannot. Its assumption — that the vig is proportional to implied probability — is
-- stated plainly rather than hidden.
--
-- `devig_method` is stored beside the probability so the choice is auditable in the data
-- and not only in this comment.
with raw_implied as (
    select
        betting_line_sk,
        game_id,
        provider_key,
        snapshot_ts,
        season,
        week,
        season_type,
        home_moneyline,
        away_moneyline,
        home_moneyline_is_sentinel,
        away_moneyline_is_sentinel,
        {{ moneyline_to_implied('home_moneyline') }} as raw_implied_home,
        {{ moneyline_to_implied('away_moneyline') }} as raw_implied_away
    from {{ ref('fct_betting_line') }}
)
select
    betting_line_sk,
    game_id,
    provider_key,
    snapshot_ts,
    season,
    week,
    season_type,
    home_moneyline,
    away_moneyline,
    raw_implied_home,
    raw_implied_away,
    -- The overround: how much more than 1.0 the two sides sum to. Exposed because it is the
    -- book's margin, and a market whose overround looks wrong is a market not to trust.
    raw_implied_home + raw_implied_away as overround,

    -- IS THIS PROBABILITY FIT TO RANK ON? A FLAG, NOT A FILTER (R-391).
    --
    -- One of the Looking Back lists ranks favourites that lost by pregame implied win
    -- probability. That list's whole purpose is "the most surprising result of the week", so
    -- a fabricated near-certainty sorts straight to the top of it. The de-vig cannot help:
    -- it NORMALISES, so a broken pair of prices still returns two numbers summing to 1 that
    -- look exactly like every other row.
    --
    -- A FLAG RATHER THAN A `where`. A row dropped inside this model is a row nobody can
    -- audit and nobody can count; downstream decides whether to exclude, and can say how
    -- many it excluded. The fact records what it saw.
    --
    -- THE BAND IS MEASURED, NOT ASSUMED. Across all 18,505 rows the observed distribution is
    -- bimodal with a clean gap: normal vig runs 1.0207 to 1.0774 (17,693 rows, 1,816 games),
    -- then nothing at all until 1.3384, above which sit 416 rows over 8 games reaching
    -- 1.9980 — a 100% vig, which is not a price. One row sits at 0.7692.
    --
    -- AN OVERROUND BELOW 1.0 IS AN ARBITRAGE, and arbitrages do not sit unclaimed on a public
    -- board; it means the input is broken, not that the market is sharp. 1.15 is the upper
    -- bound because it is comfortably above every real observation and comfortably below the
    -- broken cluster — the gap is wide enough that the exact cut does not matter.
    (raw_implied_home + raw_implied_away) >= 1.00
        and (raw_implied_home + raw_implied_away) <= 1.15   as is_overround_plausible,

    -- BOTH CHECKS ARE NEEDED AND THIS IS THE MEASUREMENT THAT SAYS SO: before this change,
    -- 930 rows across 22 games carried the sentinel AND a perfectly normal overround. An
    -- overround guard alone would have passed every one of them.
    --
    -- ⚠️ THIS FLAG SHOULD NOW ALWAYS BE FALSE HERE, and that is the point. stg_lines nulls
    -- the sentinel, so `raw_implied` is null and the `where` at the bottom of this model
    -- already excludes the row — the auditable record of what was seen lives in
    -- fct_betting_line, which keeps all 24,662 snapshots and carries the same two flags.
    -- The column is kept as a tripwire: assert_no_moneyline_sentinel_reaches_the_devig fails
    -- if the upstream null ever stops happening, rather than the sentinel silently returning
    -- to the top of the upset list.
    coalesce(home_moneyline_is_sentinel, false)
        or coalesce(away_moneyline_is_sentinel, false)      as has_moneyline_sentinel,
    not (coalesce(home_moneyline_is_sentinel, false) or coalesce(away_moneyline_is_sentinel, false))
        and (raw_implied_home + raw_implied_away) >= 1.00
        and (raw_implied_home + raw_implied_away) <= 1.15   as is_probability_usable,
    case when raw_implied_home is not null and raw_implied_away is not null
              and (raw_implied_home + raw_implied_away) > 0
         then raw_implied_home / (raw_implied_home + raw_implied_away)
    end as market_implied_home_win_probability,
    case when raw_implied_home is not null and raw_implied_away is not null
              and (raw_implied_home + raw_implied_away) > 0
         then raw_implied_away / (raw_implied_home + raw_implied_away)
    end as market_implied_away_win_probability,
    'multiplicative' as devig_method
from raw_implied
where raw_implied_home is not null and raw_implied_away is not null
