{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only`, AND A GUARD SAID SO BEFORE A GAME DAY DID — R-672, caught by
-- `test_no_test_straddles_the_gated_dags_refresh_boundary` on this test's first full run.
--
-- It compares `srv_game_win_probability_play` against `stg_game_win_probability`, and
-- `cfbd_scores_refresh` REBUILDS THE STAGING MODEL BUT NOT THE SERVING ONE — the curve is on the
-- weekly publish list, because a completed game's curve never changes and its source endpoint
-- (`metrics/wp`) is fetched on Sundays and Thursdays only. So a two-hourly run would compare a
-- FRESH source against a STALE output, report a difference that is a cadence artifact rather than
-- a defect, and stop that DAG's publish. That is R-672 exactly.
--
-- ⚠️ AND THE BLUNT TAG IS THE CORRECT ONE HERE, as it is for the leader tests: no gated DAG
-- rebuilds both sides, so `scores_refresh_only` would claim a coverage that does not exist.
-- Nothing real is lost — the weekly `+tag:production` build runs this at exactly the cadence the
-- data changes.
--
-- R-724. The curve must be drawable: within a game, `play_number` must be a strictly increasing
-- sequence with no duplicates, because that is the axis the chart positions on.
--
-- 🚨 THE DEFECT THIS EXISTS FOR IS A SORT, AND IT LEAVES EVERY ROW REAL AND EVERY COUNT RIGHT.
-- `play_id` in this feed is a STRING — it comes out of the raw JSON through `json_get_string` —
-- so ordering or de-duplicating on it sorts LEXICALLY: play 10 lands before play 2, the line
-- folds back on itself, and nothing else in the project notices. The row count is right. The
-- games are right. Every probability is a real probability. The picture is wrong.
--
-- ⚠️ SO "THE RIGHT NUMBER OF ROWS CAME BACK" CANNOT SEE IT, and neither can a null check, the
-- documentation guard, or the publish row-count verification. What catches it is asserting the
-- SEQUENCE: that reading the curve in the order the chart will read it produces play numbers
-- that only ever go up.
--
-- ⚠️ AND IT ASSERTS UNIQUENESS IN THE SAME PASS. A duplicated `play_number` within a game would
-- give the chart two y values for one x — a vertical segment a reader reads as an instant swing
-- that never happened.
--
-- 🚨 AND MONOTONICITY ALONE IS NOT ENOUGH — THE FIRST VERSION OF THIS TEST ONLY CHECKED THAT, AND
-- IT WOULD HAVE PASSED THE BREAK IT WAS WRITTEN FOR. A table has no inherent order, so this test
-- re-sorts by `play_number` before looking; a model that RECOMPUTED `play_number` from a play_id
-- sort — `row_number() over (order by play_id)`, the edit somebody makes when they think the
-- feed's numbering "has gaps" — produces 1..N, perfectly monotonic, with every probability
-- attached to the WRONG POSITION. The picture zig-zags and this assertion smiles at it.
--
-- ✅ SO THE SECOND CLAIM IS THE LOAD-BEARING ONE: each published play must carry the SAME
-- play_number and the SAME probability as the feed row with that play_id. That is an independent
-- recomputation against the source rather than a property of the output, and it is what makes a
-- reordering visible.
--
-- ⚠️ Measured before writing it: `play_id` is `text` and the ids are NOT fixed width — lengths run
-- 5, 6, 11, 12 and 18 — so a lexical sort really does scramble. Ordering the feed by `play_id`
-- yields 10,051 rows whose play_number fails to advance, against 0 for the control.
--
-- ONE GROUPED PASS, NOT A CORRELATED SUBQUERY PER ROW — A097, A106 and A120 all paid for that
-- shape. `lag()` over the game partition is a single ordered scan, and the source comparison is a
-- hash join on a unique key.
with sequenced as (

    select
        game_id,
        play_number,
        lag(play_number) over (partition by game_id order by play_number) as previous_play_number,
        count(*)         over (partition by game_id, play_number)         as rows_at_this_play_number
    from {{ ref('srv_game_win_probability_play') }}

),

-- EACH PUBLISHED PLAY AGAINST THE FEED ROW IT CAME FROM, keyed on play_id, which is unique in
-- both. A reassigned play_number or a probability attached to the wrong play shows up here and
-- nowhere else.
against_source as (

    select
        v.game_id,
        v.play_id,
        v.play_number                as published_play_number,
        w.play_number                as source_play_number,
        v.home_win_probability       as published_wp,
        w.home_win_probability       as source_wp
    from {{ ref('srv_game_win_probability_play') }} v
    left join {{ ref('stg_game_win_probability') }} w
           on w.play_id = v.play_id

)

select game_id, play_number, previous_play_number, rows_at_this_play_number,
       null::text as play_id, null::integer as source_play_number,
       case
         when rows_at_this_play_number > 1
           then 'two rows share a play number, so the chart has two y values for one x'
         else 'the curve does not advance — a lexical sort on play_id produces exactly this'
       end as rule
from sequenced
where rows_at_this_play_number > 1
   or (previous_play_number is not null and play_number <= previous_play_number)

union all

select game_id, published_play_number, null::integer, null::bigint,
       play_id, source_play_number,
       case
         when source_play_number is null
           then 'a published play has no feed row with that play_id'
         when published_play_number is distinct from source_play_number
           then 'the published play_number is not the feed''s — the curve has been renumbered'
         else 'the published probability is not the feed''s for that play'
       end as rule
from against_source
where source_play_number is null
   or published_play_number is distinct from source_play_number
   or published_wp is distinct from source_wp
