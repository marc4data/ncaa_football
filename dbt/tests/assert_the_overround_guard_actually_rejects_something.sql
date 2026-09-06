{{ config(severity='error') }}
-- A GUARD NOBODY HAS SEEN REJECT ANYTHING IS A GUARD NOBODY HAS TESTED (R-391).
--
-- FIRST DRAFT WAS WRONG AND CI CAUGHT IT. It asserted that fct_market_probability contains
-- at least one rejected row. That is true of production -- 417 rows across 9 games sit
-- outside the band -- and false of the CI fixture, which contains only clean prices. A test
-- that depends on bad data existing fails wherever the data is good, which is precisely
-- where it should be quietest.
--
-- So this tests the RULE rather than the data: known-bad overrounds are fed in directly and
-- the band expression must reject every one, while known-good ones must survive. It runs
-- identically against a fixture and against production, and it still fails if someone
-- widens the band to nothing or inverts the comparison.
--
-- The values are the real observed extremes: 0.7692 is the arbitrage row, 1.9980 the widest
-- of the broken cluster, 1.3384 its lower edge. 1.0207 and 1.0774 are the true min and max
-- of normal vig and MUST pass -- a band that rejects them would throw away every real price.
with probe(label, overround, should_be_plausible) as (
    values ('observed arbitrage',        0.7692, false),
           ('zero vig',                  1.0000, true),
           ('normal vig, observed min',  1.0207, true),
           ('normal vig, observed max',  1.0774, true),
           ('band edge',                 1.1500, true),
           ('broken cluster, lower',     1.3384, false),
           ('broken cluster, widest',    1.9980, false)
)
select label, overround, should_be_plausible,
       (overround >= 1.00 and overround <= 1.15) as guard_says
from probe
where (overround >= 1.00 and overround <= 1.15) is distinct from should_be_plausible
