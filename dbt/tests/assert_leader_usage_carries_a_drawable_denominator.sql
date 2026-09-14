{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` FOR THE REASON ITS SIBLINGS CARRY: it reads
-- `srv_game_team_leader_usage`, which is built from `game/box/advanced` — one API call per game,
-- fetched weekly rather than two-hourly. `ci/check_test_refresh_scope.py` is the guard that would
-- otherwise stop a gated DAG's publish, and R-672 is the round that found that class.
--
-- R-748, and this is the DBT HALF OF A RULE THAT WAS BEING ENFORCED IN THE WRONG PLACE.
--
-- `site/views/matchup.py`'s `_usage_dots` raises when `usage_total` or `usage_total_max_in_window`
-- is null. It is called from inside the Offense-vs-Defense panel, so ONE bad row takes down three
-- charts and nine cards, for every viewer, on a game day, with no alert — while the condition it
-- is defending against is a DATA defect that nobody would be told about.
--
-- ✅ THE RULE: ASSERT UPSTREAM, DEGRADE DOWNSTREAM. The build is where an impossible row should
-- announce itself, loudly, to us. The page is where it should quietly draw nothing. B099 reasoned
-- exactly this way eight hundred lines earlier for an unknown KPI format — draw nothing, fail
-- loudly in CI — and the raise inverted it.
--
-- 📊 MEASURED INDEPENDENTLY, HOURS APART, BY A120 AND B102, AND THEY AGREED: 0 nulls, 0 nulls, 0
-- zeroes of 159,418 rows. So this test is GREEN TODAY and is a tripwire rather than a repair —
-- which is the correct state for a condition the page currently raises on.
--
-- ⚠️ AND IT COVERS THE PUBLISHED SHARE FOR FREE. `usage_share_of_max` is
-- `usage_total / nullif(usage_total_max_in_window, 0)`, so it is null on exactly the rows this
-- test forbids and on no others. One assertion, both columns.
select
    game_id,
    team_id,
    player_id,
    usage_total,
    usage_total_max_in_window,
    usage_share_of_max,
    case
      when usage_total is null
        then 'a leader with no usage figure cannot be drawn'
      when usage_total_max_in_window is null
        then 'no ceiling in the window, so no circle can be sized'
      when usage_total_max_in_window = 0
        then 'a zero ceiling would divide by zero'
    end as rule
from {{ ref('srv_game_team_leader_usage') }}
where usage_total is null
   or usage_total_max_in_window is null
   or usage_total_max_in_window = 0
