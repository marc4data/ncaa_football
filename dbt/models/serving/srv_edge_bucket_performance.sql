{{ config(tags=['predictions']) }}
-- Edge Finder, track record: has a bigger edge ever actually been a better bet?
--
-- The page lets a reader filter to edges above some size. Without this section a slider is
-- an invitation to assume that bigger is better, and the measured answer is that it is not.
--
-- FILTER ON market. A spread edge is in points and a moneyline edge is a probability, and
-- the two are stacked long here because bucketing them on one scale would produce a table
-- that sorts but does not mean anything.
--
-- edge_over_break_even_pct IS NULL FOR MONEYLINE ON PURPOSE. The 52.38% figure is a -110
-- SPREAD convention; moneyline bets are priced per game, so a 77% hit rate on heavy
-- favourites can lose money and subtracting a fixed threshold from it would be a confident,
-- meaningless number.
select
    e.edge_bucket_sk,
    e.model_name,
    e.model_version,
    e.model_family,
    e.split,
    e.market,
    e.edge_unit,
    e.edge_bucket,
    e.bucket_order,
    e.bucket_games,
    e.bucket_hits,
    e.hit_rate_pct,
    e.edge_over_break_even_pct,
    e.mean_edge_magnitude,
    e.is_thin_sample,
    e.out_of_sample_games,
    mv.attribution,
    ao.as_of_ts
from {{ ref('fct_edge_bucket_performance') }} e
left join {{ ref('dim_model_version') }} mv
    on mv.model_name = e.model_name and mv.model_version = e.model_version
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'prediction') ao
