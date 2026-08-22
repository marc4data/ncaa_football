-- Every segment srv_model_performance can produce is actually produced.
--
-- The view stacks five cuts, and four of them exist only to answer a question the headline
-- table cannot: does the model decay through the season, where is it confident and wrong,
-- does its own confidence label separate anything, and is a 70% worth 70 cents. Each cut is
-- a branch of a union with its own filter, and a branch that silently yields nothing looks
-- exactly like a cut nobody asked about.
--
-- The `conference` branch was that on the first run: the CI fixture's prediction payloads
-- carried no home_conference, so the branch was never exercised, and the whole segment was
-- absent from the build with nothing to say so.
--
-- Written as a left-anti selection against a literal list rather than a count, so a failure
-- names the missing segment instead of reporting a number that has to be looked into.
with expected(segment_type) as (
    select 'overall'     union all
    select 'week'        union all
    select 'conference'  union all
    select 'confidence'  union all
    select 'probability'
),
present as (
    select distinct segment_type from {{ ref('srv_model_performance') }}
)
select e.segment_type
from expected e
left join present p on p.segment_type = e.segment_type
where p.segment_type is null
  -- An empty view is a different failure with a different fix: no predictions have been
  -- loaded at all, which the freshness signal already reports. Without this guard the test
  -- would fail five times over on a clean database and get muted.
  and exists (select 1 from present)
