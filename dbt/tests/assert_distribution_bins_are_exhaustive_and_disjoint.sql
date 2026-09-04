-- THE SINGLE MOST VALUABLE TEST ON THE DISTRIBUTION MODELS.
--
-- Every value that counted towards `n` must land in exactly one bin, or be counted in one of
-- the two tails. If it does not, the histogram and the statistics beside it describe
-- different sets of games — and nothing about that is visible: the sparkline still draws, the
-- median is still a real number, and the picture is quietly wrong.
--
-- It catches the whole family of edge bugs at once: an off-by-one on bin_index, a half-open
-- boundary applied at the wrong end, the maximum value falling outside the last bin because
-- the range is [lo, hi) all the way up, a metric whose edges do not match between the two
-- models, and a span present in one model and absent from the other.
select
    d.season, d.season_type, d.week, d.span, d.metric, d.as_of_date,
    d.n,
    coalesce(sum(b.games), 0) as binned,
    d.below_min_count,
    d.above_max_count
from {{ ref('fct_week_metric_distribution') }} d
left join {{ ref('fct_week_metric_distribution_bin') }} b
       on  b.season = d.season and b.season_type = d.season_type
       and b.week = d.week and b.span = d.span
       and b.metric = d.metric and b.as_of_date = d.as_of_date
group by d.season, d.season_type, d.week, d.span, d.metric, d.as_of_date,
         d.n, d.below_min_count, d.above_max_count
having coalesce(sum(b.games), 0) + d.below_min_count + d.above_max_count <> d.n
