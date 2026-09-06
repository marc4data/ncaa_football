{{ config(severity='error') }}
-- A GUARD NOBODY HAS SEEN REJECT ANYTHING IS A GUARD NOBODY HAS TESTED (R-391).
--
-- The inverse of a normal data test: this fails when the guard finds NOTHING. The overround
-- band exists because 417 rows across 9 games sit outside it -- one at 0.7692, which is an
-- arbitrage and therefore impossible, and 416 between 1.3384 and 1.9980, which is a 100%
-- vig and therefore not a price. If a refactor silently made is_overround_plausible always
-- true, every other test here would still pass and the flag would be decoration.
--
-- Deliberately asserts "> 0 rejected", not an exact count: the count grows as data lands and
-- pinning it would make this fail for the wrong reason every week.
select 'the overround guard rejected nothing, so it is not guarding' as failure
where (select count(*) from {{ ref('fct_market_probability') }}
       where not is_overround_plausible) = 0
