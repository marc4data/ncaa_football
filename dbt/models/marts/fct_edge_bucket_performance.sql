{{ config(materialized='table', tags=['predictions']) }}

-- Hit rate by how big the edge was. One row per (model, version, split, market, bucket).
--
-- The question the Edge Finder cannot answer without it: the page lets a reader filter to
-- edges above some size, and nothing on it says whether a bigger edge has ever been a better
-- bet. A slider without this is an invitation to assume it does.
--
-- MARKETS ARE STACKED LONG BECAUSE THEIR UNITS ARE NOT COMPARABLE. A spread edge is in
-- points and a moneyline edge is a probability; bucketing them on one scale would produce a
-- table that sorts but does not mean anything. `market` and `edge_unit` say which is which,
-- and a consumer that does not filter on market gets two incompatible grains stacked.
--
-- A "HIT" IS THE MODEL'S OWN PICK BEING RIGHT, not the home team winning. cover_correct and
-- home_win_correct are already model-relative upstream, which is what makes a hit rate below
-- 50% meaningful rather than merely a home-field artefact.
--
-- ONLY GRADED GAMES COUNT. An ungraded prediction is not a miss, and counting it as one
-- would drag every rate toward zero as the season's unplayed fixtures accumulate.
--
-- THE SAMPLE IS SMALL AND THE MODEL SAYS SO RATHER THAN HIDING IT. 1,106 graded cover
-- predictions across six models means individual buckets hold tens of games, not thousands.
-- `bucket_games` is carried so no rate is ever readable without its n, and
-- `is_thin_sample` marks the cells where the rate is noise. Thirty is a convention, not a
-- statistical claim, and it is named here so a page cannot quietly pick a friendlier one.

with graded as (

    select
        model_name, model_version, model_family, split, season,
        is_out_of_sample_week,
        'spread'                                    as market,
        'points'                                    as edge_unit,
        abs(home_cover_edge)                        as edge_magnitude,
        case when cover_correct then 1 else 0 end   as is_hit
    from {{ ref('fct_prediction') }}
    where home_cover_edge is not null
      and cover_correct is not null

    union all

    select
        model_name, model_version, model_family, split, season,
        is_out_of_sample_week,
        'moneyline',
        'probability',
        abs(home_win_probability_edge),
        case when home_win_correct then 1 else 0 end
    from {{ ref('fct_prediction') }}
    where home_win_probability_edge is not null
      and home_win_correct is not null

),

bucketed as (

    select
        g.*,
        -- Two bucket ladders, because the two units are not comparable. Boundaries are
        -- conventional round numbers rather than quantiles of this dataset: quantile
        -- buckets would move every time the model is re-scored, so a bucket's meaning
        -- would change under a reader who had learned it.
        case when market = 'spread' then
                 case when edge_magnitude < 1  then '0-1 pts'
                      when edge_magnitude < 2  then '1-2 pts'
                      when edge_magnitude < 3  then '2-3 pts'
                      when edge_magnitude < 5  then '3-5 pts'
                      when edge_magnitude < 7  then '5-7 pts'
                      else '7+ pts' end
             else
                 case when edge_magnitude < 0.025 then '0-2.5 pp'
                      when edge_magnitude < 0.05  then '2.5-5 pp'
                      when edge_magnitude < 0.10  then '5-10 pp'
                      when edge_magnitude < 0.20  then '10-20 pp'
                      else '20+ pp' end
        end                                         as edge_bucket,
        case when market = 'spread' then
                 case when edge_magnitude < 1 then 1 when edge_magnitude < 2 then 2
                      when edge_magnitude < 3 then 3 when edge_magnitude < 5 then 4
                      when edge_magnitude < 7 then 5 else 6 end
             else
                 case when edge_magnitude < 0.025 then 1 when edge_magnitude < 0.05 then 2
                      when edge_magnitude < 0.10 then 3 when edge_magnitude < 0.20 then 4
                      else 5 end
        end                                         as bucket_order
    from graded g

)

select
    {{ surrogate_key(['model_name', 'model_version', 'split', 'market', 'edge_bucket']) }}
        as edge_bucket_sk,
    model_name,
    model_version,
    model_family,
    split,
    market,
    edge_unit,
    edge_bucket,
    bucket_order,
    count(*)                                        as bucket_games,
    sum(is_hit)                                     as bucket_hits,
    round(100.0 * sum(is_hit) / count(*), 1)        as hit_rate_pct,
    -- SPREAD ONLY, AND THAT RESTRICTION IS THE WHOLE POINT OF THE COLUMN.
    --
    -- Break-even against a standard -110 spread price is 52.38%, so "is this better than a
    -- coin flip" is the wrong question and the right one has a specific number. But that
    -- number is a SPREAD convention: moneyline bets are priced per game, a 77% hit rate on
    -- heavy favourites can lose money and a 40% hit rate on underdogs can make it, so
    -- subtracting 52.38 from a moneyline rate would produce a confident, meaningless figure.
    -- NULL is the honest answer there, and computing it anyway is how a page ends up
    -- ranking two markets against a threshold only one of them has.
    case when market = 'spread'
         then round(100.0 * sum(is_hit) / count(*) - 52.38, 1) end
                                                    as edge_over_break_even_pct,
    round(cast(avg(edge_magnitude) as numeric), 3)  as mean_edge_magnitude,
    -- Thirty is a convention, not a statistical claim. Named here so no page picks a
    -- friendlier threshold, and so the number is arguable in one place.
    count(*) < 30                                   as is_thin_sample,
    sum(case when is_out_of_sample_week then 1 else 0 end) as out_of_sample_games
from bucketed
group by model_name, model_version, model_family, split, market, edge_unit,
         edge_bucket, bucket_order
