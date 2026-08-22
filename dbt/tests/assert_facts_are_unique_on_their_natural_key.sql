-- Every fact holds one row per BUSINESS key. Not per surrogate key — that proves nothing.
--
-- A surrogate built by hashing the natural key is unique by construction. If the hash
-- includes anything that varies between fetches, six copies of a row produce six distinct
-- surrogates and `unique_<fact>_<fact>_sk` passes while the table is six times too big.
-- The test has to name the business key, which is why this is one singular test listing
-- them rather than a generic test on a column.
--
-- WHY THIS EXPOSURE IS STRUCTURAL RATHER THAN INCIDENTAL. The revisionist cadence means the
-- raw layer holds MULTIPLE RESPONSES FOR THE SAME ENTITY BY DESIGN — lines are re-fetched
-- four-hourly, rankings and results weekly. Every fact built on a re-fetched endpoint has
-- this exposure, and before this test only the ones somebody happened to check were known
-- clean.
--
-- THE FAILURE SIGNATURE IS WHY IT SURVIVES REVIEW. A duplicate fan-out passes every
-- mean-based check and fails only count-based ones. Averages, percentiles and rankings all
-- come out approximately right; nobody looks at counts. It shows up as a rank that is
-- subtly wrong months later.
--
-- Found on the first run: fct_team_rating, three keys across two seasons. CFBD's
-- /ratings/srs returns some schools twice — once with a conference and once with
-- `conference: null`, carrying an identical rating — so no average moved and every
-- percentile denominator was one too large. Fixed in stg_team_rating; the test is what
-- would have caught it on the day the model shipped.
{% set fact_keys = [
    ('fct_game',               ['game_id']),
    ('fct_game_team',          ['game_id', 'team_id']),
    ('fct_team_record',        ['season', 'team_id']),
    ('fct_team_season_stat',   ['season', 'team_id', 'stat_name']),
    ('fct_poll_rank',          ['season', 'season_type', 'week', 'poll_name', 'team_id']),
    ('fct_betting_line',       ['game_id', 'provider_key', 'snapshot_ts']),
    ('fct_market_probability', ['game_id', 'provider_key', 'snapshot_ts']),
    ('fct_team_rating',        ['season', 'team_id', 'rating_system']),
    ('fct_prediction',         ['game_id', 'model_name', 'model_version', 'split']),
    ('fct_api_usage',          ['resource', 'observed_at']),
    ('fct_deploy_status',      ['observed_at']),
    ('fct_dq_test_result',     ['invocation_id', 'unique_id']),
] %}

{% for fact, key in fact_keys %}
select
    '{{ fact }}'                                  as fact_name,
    '{{ key | join(", ") }}'                      as natural_key,
    count(*)                                      as duplicate_keys
from (
    select {{ key | join(', ') }}
    from {{ ref(fact) }}
    group by {{ key | join(', ') }}
    having count(*) > 1
) d
having count(*) > 0
{% if not loop.last %}
union all
{% endif %}
{% endfor %}
