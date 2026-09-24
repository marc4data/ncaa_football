-- A214. TWO METRICS IN ONE `axis_group` MUST BE DRAWN ON ONE AXIS, SO THEIR BOUNDS MUST AGREE.
--
-- > **MARC, v14:** *"histograms/box-whiskers of Winning Scores vs Losing Scores"*
--
-- 🚨 THE COMPARISON IS THE POINT, AND EQUAL BOUNDS ARE WHAT MAKE IT ONE. Rescaled to its own
-- maximum, a losing-score distribution looks very like a winning one; the whole reason to put
-- them side by side is that the winning distribution sits visibly to the right. That property
-- is not in the picture, it is in the two rows' `bin_min`, `bin_max` and `bin_count`.
--
-- ⚠️ WITHOUT THIS TEST THE SHARING IS A COINCIDENCE OF TWO HAND-TYPED NUMBERS. Someone widening
-- `winning_points` to 0-90 in `dbt_project.yml` gets a green build, a correct-looking chart, and
-- two axes that no longer mean the same thing — and nothing on the page can say so.
--
-- ⚠️ IT `ref()`s ITS SUBJECT (§3.6), so it is ordered after the model whose rows it reads rather
-- than free to run before the table exists.
--
-- 📊 AND IT IS NOT VACUOUS: `game_points` holds two members today, so the `having` clause has a
-- group with more than one row to be false about. A group of one cannot fail it, which is
-- correct — a metric on its own axis has nothing to disagree with.
select
    axis_group,
    count(distinct metric)     as metrics_in_group,
    count(distinct bin_min)    as distinct_bin_mins,
    count(distinct bin_max)    as distinct_bin_maxes,
    count(distinct bin_count)  as distinct_bin_counts,
    count(distinct domain_rule) as distinct_domain_rules
from {{ ref('fct_week_metric_distribution') }}
group by axis_group
having count(distinct bin_min) > 1
    or count(distinct bin_max) > 1
    or count(distinct bin_count) > 1
    or count(distinct domain_rule) > 1
