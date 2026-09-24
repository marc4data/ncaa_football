-- WHISKERS REACH AN OBSERVATION, NOT A FORMULA.
--
-- matplotlib's `whis=1.5` convention — which `plot_distribution` uses and which this model
-- reproduces — puts the whisker at the most extreme value still WITHIN 1.5*IQR of the box.
-- The naive reading computes q1 - 1.5*IQR and draws the whisker there, which produces
-- whiskers extending past the data. That looks like a bug and is one. **The first two
-- clauses below are that check, they have never fired, and they are untouched.**
--
-- ══ A230 (cfdb-main-R-3017): TWO CLAUSES REMOVED, AND NOT BECAUSE THEY WERE INCONVENIENT ══
--
-- 🚨 THIS ASSERTION USED TO ALSO READ `whisker_lo > p25 or whisker_hi < p75` — "the box is
-- inside the whiskers". On 2026-09-24 it went RED on 44 rows and stopped the publish for
-- fourteen hours, because `dbt_test` gates `publish` (§2.3).
--
-- ⚠️ THE MODEL WAS NOT WRONG. A230 reconstructed all 44 rows from the raw member values in
-- `int_week_metric_value` and REPRODUCED every published figure exactly, 44 of 44. The
-- whiskers are correct. **The removed clauses asserted a property that is false, for two
-- INDEPENDENT reasons — and one of them has nothing to do with sparse data:**
--
--   1. AN INTERPOLATED QUARTILE IS NOT AN OBSERVATION. `p25`/`p75` interpolate between
--      actual values; a whisker IS an actual value. Season 1878 week 5 `winning_points`
--      holds [0, 1, 3]: p75 interpolates to 1.5, the fences are [-0.375, 2.625], and the
--      largest real value inside them is 1. So `whisker_hi` (1) < `p75` (1.5) — correctly.
--
--   2. AN OUTLIER UNDER SKEW PUSHES A WHISKER PAST A QUARTILE, AT ANY SAMPLE SIZE. Season
--      1875 week 6 holds [1, 6, 6, 6]: p25 is 4.75, the low fence is 2.875, the 1 is a
--      genuine outlier, and `whisker_lo` correctly sits at 6 — above p25. 📊 **All 44 rows
--      carry `outlier_count > 0`.** This reason is not about historical data or small
--      samples; it is about what a Tukey whisker means.
--
-- ✅ WHY IT SURFACED NOW, MEASURED RATHER THAN GUESSED (cfdb-main-R-3016): A214 added
-- `winning_points` and `losing_points`, the first two metrics on this model derived from the
-- GAME SCORE rather than from a betting line or the weather. Every earlier metric is
-- market- or weather-derived and so has no rows before 2024; these two have data back to
-- 1869. 📊 On their first run they wrote 4,029 pre-2024 rows EACH, while the six older
-- metrics still hold exactly 0. Nothing widened the model's season range — a new metric
-- simply reached data that was always there.
--
-- 🚨 REPLACED, NOT MERELY DELETED, AND THE REPLACEMENTS ARE STRICTLY STRONGER WHERE IT
-- COUNTS. The old pair's stated job was to catch "a transposed pair of columns". Clauses 3
-- and 4 below catch a transposition DIRECTLY — of the whiskers and of the quartiles — rather
-- than inferring it. Clauses 5 and 6 are the invariant the old pair was reaching for and
-- could not express: **a whisker that sits inside the data range must have excluded
-- something, so there must be an outlier to show for it.** A whisker wrongly pulled in is
-- exactly what that catches, and it holds at every sample size and on every distribution.
--
-- 📊 All six clauses return 0 rows over all 10,190 rows of the built model.
select season, season_type, week, span, metric, as_of_date,
       min_value, whisker_lo, p25, p75, whisker_hi, max_value, outlier_count
from {{ ref('fct_week_metric_distribution') }}
where
    -- 1-2. the original check: a whisker may never reach past the data
    whisker_lo < min_value
 or whisker_hi > max_value
    -- 3-4. transposition, caught directly
 or whisker_lo > whisker_hi
 or p25 > p75
    -- 5-6. a whisker inside the data range has to have excluded something
 or (whisker_lo > min_value and coalesce(outlier_count, 0) = 0)
 or (whisker_hi < max_value and coalesce(outlier_count, 0) = 0)
