{{ config(tags=['postgres_only']) }}
-- Postgres-only telemetry; see stg_pipeline_heartbeat for why.
-- ONE ROW PER CADENCE: when it last reached serving, and the budget it is judged against.
--
-- The grain change is the point of this model existing rather than serving reading staging
-- directly (ci/check_layering.py rule 3): the raw table is append-only, one row per run, and
-- every consumer wants the LATEST beat per cadence. Doing that once here means the page, any
-- future alert and any future export all agree about what "last published" means.
--
-- 📊 THE BUDGETS ARE `ci/check_heartbeats.py`'s, NOT A SECOND SET. They are restated here
-- because that check runs on GitHub Actions in Python — deliberately outside the droplet, so a
-- monitor does not share fate with what it monitors — and this runs in the warehouse in SQL.
-- **There is no shared home for a number both of them need**, so
-- `tests/test_health_budgets.py` asserts the two agree and fails if either moves alone.
-- §4.2.1's question is "how many consumers can this number have"; the answer is two, in two
-- languages, on two machines, and a number with two homes needs a guard rather than a comment.
select
    heartbeat_name,
    max(beat_at)                                       as last_beat_at,
    -- ⚠️ MATCHED TO ci/check_heartbeats.py's CADENCES. Move both or neither.
    case heartbeat_name
        when 'scores_refresh' then 5 * 3600
        when 'lines_snapshot' then 9 * 3600
        when 'weekly_results' then 8 * 24 * 3600
        when 'weekly_pregame' then 8 * 24 * 3600
        when 'weekly_midweek' then 8 * 24 * 3600
    end                                                as budget_seconds
from {{ ref('stg_pipeline_heartbeat') }}
group by heartbeat_name
