{{ config(materialized='table') }}

-- One pregame win probability per game, with the provenance of when it was taken. R-079.
--
-- A MART RATHER THAN A CTE IN THE SERVING VIEW, and the layering guard is what said so:
-- serving builds on marts, marts build on staging. The first version of this lived inside
-- srv_game and read stg_game_pregame_wp directly; ci/check_layering.py failed the build and
-- was right to. Choosing WHICH snapshot represents a game is a business rule, and business
-- rules belong in a mart where a second consumer can reuse them rather than re-derive them —
-- which is the whole thesis of the prompt this model was written under.
--
-- THE PICK IS "LATEST AT OR BEFORE KICKOFF", FALLING BACK TO WHATEVER EXISTS.
--
-- A strict pre-kickoff rule would return almost nothing. Measured: 1,891 games carry a
-- pregame probability and only 131 of them have a snapshot taken at or before kickoff — all
-- 131 in 2026, because cfdb's snapshotting began 2026-08-15. Every 2024 and 2025 row was
-- observed after the game had finished.
--
-- So `basis` travels with the number, exactly as it does for betting lines:
--   observed_before_kickoff   cfdb sampled it while the game was still ahead
--   as_recorded_by_cfbd       a real figure whose timestamp is our FETCH time, not a
--                             pre-kickoff observation
-- Calling both "pregame" without the distinction would present a number we were told about
-- afterwards as one we watched, which is the same conflation the lines model refuses.
--
-- NINE DISTINCT SNAPSHOT TIMESTAMPS EXIST IN TOTAL. This is a VALUE, not a movement series,
-- and nothing downstream should be built as though it were one.

select
    {{ surrogate_key(['game_id']) }} as game_pregame_wp_sk,
    game_id,
    home_win_probability,
    snapshot_ts,
    basis
from (
    select
        w.game_id,
        w.home_win_probability,
        w.snapshot_ts,
        case when w.snapshot_ts <= g.start_date then 'observed_before_kickoff'
             else 'as_recorded_by_cfbd' end as basis,
        row_number() over (
            partition by w.game_id
            order by case when w.snapshot_ts <= g.start_date then 0 else 1 end,
                     w.snapshot_ts desc
        ) as recency
    from {{ ref('stg_game_pregame_wp') }} w
    join {{ ref('fct_game') }} g on g.game_id = w.game_id
) ranked
where recency = 1
