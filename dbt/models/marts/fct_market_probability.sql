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
