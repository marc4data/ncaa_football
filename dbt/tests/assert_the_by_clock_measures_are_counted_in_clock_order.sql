{{ config(tags=['full_refresh_only']) }}
-- A140, cfdb-main-R-916. The `*_by_clock` columns must be what you get from a curve read in the
-- order its plays happened, and NOT what you get from the order the feed lists them in.
--
-- 🚨 TAGGED `full_refresh_only` FOR THE REASON A136's OWN TEST WAS REWRITTEN. `cfbd_scores_refresh`
-- rebuilds `fct_game_win_probability_summary` and NOT the play-grain curve, so on a hot run this
-- compares two relations with different fetch times and measures the gap between them rather than
-- the thing it is about. Full authority on the weekly `+tag:production` build, which rebuilds both.
--
-- 🚨 A PRESENCE ASSERTION CANNOT SEE THIS DEFECT, WHICH IS WHY IT SURVIVED TO NOW. The old and the
-- new columns are integers on the same grain in the same range: every not-null, every accepted
-- range, every row count passes on both. The only thing that separates them is the ORDER, so the
-- test has to reach the order.
--
-- ✅ CLAIM 1 REACHES IT FROM A DIFFERENT RELATION, WHICH IS WHAT KEEPS IT FROM BEING A RESTATEMENT.
-- The summary derives its ordering INLINE from `stg_play`'s period and clock, through
-- `curve_order()`. This recomputes the same crossings over `fct_game_win_probability_play`'s
-- PUBLISHED `elapsed_from_kickoff_seconds` — a different model, a different column, the same
-- claim about which play came first. A window ordered wrongly in the summary disagrees; a macro
-- broken in one place disagrees.
--
-- ⚠️ AND THE ANCHORS EXIST BECAUSE CLAIM 1 ALONE WOULD NOT SURVIVE BOTH SIDES BEING WRONG
-- TOGETHER. They are pinned to numbers measured out of RAW STAGING with the ordering written by
-- hand, before either column existed:
--
--     401761598  Memphis at Georgia State, 2025 week 2
--                the feed publishes 25 lead changes and a 0.6704 largest swing
--                along the clock the game had 11 and 0.2401
--     401635615  the game in the register: play_number 0-3 are fourth-quarter plays at
--                3,528-3,590 seconds and play_number 4 is a first-quarter play at 23 seconds
--                the feed publishes 6 lead changes; along the clock it had 5
--
-- 🚨 R-843 — EACH ANCHOR MOVES UNDER THE BREAK IT IS WRITTEN FOR. Re-order the new windows by
-- `play_number` and 11 becomes 25, 0.2401 becomes 0.6704, 5 becomes 6. ❌ AND NONE OF THEM IS
-- KEYED ON A VALUE THE DEFECT CONTROLS (cfdb-wta-R-944): the expected numbers are literals in
-- this file, not readings from a column the ordering produces.
with recomputed as (

    select
        game_id,
        sum(crossing)                                  as lead_changes_by_clock,
        round(max(swing), 4)                           as largest_single_play_swing_by_clock
    from (
        select
            game_id,
            case when previous is null then 0
                 when (previous < 0.5 and home_win_probability >= 0.5)
                   or (previous >= 0.5 and home_win_probability < 0.5) then 1
                 else 0 end                            as crossing,
            abs(home_win_probability - previous)       as swing
        from (
            select
                game_id,
                home_win_probability,
                lag(home_win_probability) over (
                    partition by game_id
                    order by elapsed_from_kickoff_seconds nulls last, play_number
                )                                      as previous
            from {{ ref('fct_game_win_probability_play') }}
        ) ordered
    ) crossings
    group by game_id

),

published as (

    select
        game_id,
        lead_changes,
        lead_changes_by_clock,
        largest_single_play_swing,
        largest_single_play_swing_by_clock,
        lead_changes_fourth_quarter,
        lead_changes_fourth_quarter_by_clock,
        lead_changes_overtime,
        lead_changes_overtime_by_clock
    from {{ ref('fct_game_win_probability_summary') }}

)

-- CLAIM 1 — the same crossings, derived from the published coordinate on the play-grain mart.
select
    p.game_id,
    p.lead_changes_by_clock::text                              as published,
    r.lead_changes_by_clock::text                              as expected,
    'the by-clock count disagrees with the published curve''s own order' as rule
from published p
join recomputed r on r.game_id = p.game_id
where p.lead_changes_by_clock is distinct from r.lead_changes_by_clock

union all

select
    p.game_id,
    p.largest_single_play_swing_by_clock::text,
    r.largest_single_play_swing_by_clock::text,
    'the by-clock swing disagrees with the published curve''s own order'
from published p
join recomputed r on r.game_id = p.game_id
where p.largest_single_play_swing_by_clock is distinct from r.largest_single_play_swing_by_clock

union all

-- CLAIM 2 — the anchors, measured out of raw staging before either column existed.
select
    game_id,
    lead_changes_by_clock::text,
    '11',
    'Memphis at Georgia State: the feed says 25 crossings, the clock says 11'
from published
where game_id = 401761598 and lead_changes_by_clock is distinct from 11

union all

select
    game_id,
    largest_single_play_swing_by_clock::text,
    '0.2401',
    'Memphis at Georgia State: the feed says a 0.6704 swing, the clock says 0.2401'
from published
where game_id = 401761598
  and largest_single_play_swing_by_clock is distinct from 0.2401

union all

select
    game_id,
    lead_changes_by_clock::text,
    '5',
    'game 401635615: the feed says 6 crossings, the clock says 5'
from published
where game_id = 401635615 and lead_changes_by_clock is distinct from 5

union all

-- CLAIM 3 — NULL DISCIPLINE TRAVELS WITH THE TWIN. The period-scoped counts are null exactly
-- when the feed never reached the fourth quarter, and that fact is about the DATA rather than
-- about the ordering, so the new column must be null in exactly the same places. A twin that
-- coalesced them to zero would claim we counted a quarter whose data stops in the third.
select
    game_id,
    coalesce(lead_changes_fourth_quarter_by_clock::text, 'null'),
    coalesce(lead_changes_fourth_quarter::text, 'null'),
    'the fourth-quarter twin is null in a different place from its original'
from published
where (lead_changes_fourth_quarter is null) <> (lead_changes_fourth_quarter_by_clock is null)
   or (lead_changes_overtime is null) <> (lead_changes_overtime_by_clock is null)
