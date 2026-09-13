{{ config(materialized='table') }}

-- The shape of a game's win-probability curve, at GAME grain. R-081.
--
-- stg_game_win_probability is PLAY grain — 263,539 rows over 1,715 games, about 154 per game.
-- The grain rule (Marc, 2026-09-02) sends it here rather than onto srv_game: "Can't add
-- game.team grain to a table that is at game grain", and play grain is finer still. It
-- arrives as a DERIVED summary, computed in dbt and named so the derivation is visible.
--
-- THIS IS THE HONEST VERSION OF THE EXCITEMENT INDEX THE SITE ALREADY SHOWS. fct_game carries
-- CFBD's excitement_index as a single number with no curve behind it. These columns are the
-- curve's own properties, computed from the plays, so a reader can see WHY a game was close
-- rather than being told that it was.
--
-- LEAD CHANGES ARE COUNTED ON THE WIN PROBABILITY CROSSING 0.5, not on the scoreboard
-- changing hands. Those are different events and the second is already derivable from the
-- play-by-play. A team can lead on the scoreboard while the model has the other side
-- favoured — a late one-score lead against a superior opponent with the ball — and it is
-- precisely that disagreement the column is worth counting.
--
-- WIN PROBABILITY AT THE HALF is taken as the last play with a play_number at or below the
-- midpoint of the game's plays, not by quarter: THIS FEED carries no period column. That is
-- an approximation and is named one — halftime_home_win_probability_approx — rather than
-- being presented as the value at the whistle.
--
-- ⚠️ A117 DID NOT "FIX" THAT APPROXIMATION, THOUGH IT NOW COULD. The period is joined in below,
-- so a true halftime value is one `case` away — but the column is published, a page reads it, and
-- silently changing what a published number MEANS is worse than leaving an honestly-named
-- approximation in place. §3.3's shape: that is an expand-migrate-contract, not a passing edit.
--
-- 🚨 THE PERIOD COMES FROM `stg_play`, JOINED ON `play_id` — R-718/R-709, and MARC DIAGNOSED THE
-- MECHANISM BEFORE IT WAS MEASURED: "stg_game_win_probability with stg_play for the time element."
-- A117 then confirmed the payload carries `homeWinProbability`, scores, down, distance, yard line
-- and text, and NO period at all.
--
--     join key            `play_id`, which is UNIQUE in both models — 629,892 of 629,892 in
--                         stg_play and 291,548 of 291,548 in stg_game_win_probability
--     grain in            PLAY, unchanged; the join cannot fan out
--     grain out           GAME, unchanged
--     coverage measured   291,547 of 291,548 win-probability plays match a play row, and every
--                         one that matches carries a period. 2026: 183 of 183 games.
--
-- ⚠️ ONE win-probability play in the whole warehouse has no matching play row, so every
-- period-scoped column below is computed from 99.9997% of the curve. `left join`, deliberately:
-- an inner join would silently drop that play from the WHOLE-GAME measures too, changing four
-- published columns to buy nothing.
--
-- 🚨 PERIODS RUN 1 TO 10, SO OVERTIME EXISTS AND IS NOT FOLDED INTO THE FOURTH QUARTER.
-- §4.3 — the name carries the window, and A102 spent a round on two names one prefix apart:
--
--     _fourth_quarter            period = 4 EXACTLY. What Marc asked for.
--     _fourth_quarter_onward     period >= 4, so a 2-OT thriller's finish is included.
--     _overtime                  period >= 5, carried SEPARATELY so it is visible rather than
--                                either silently included or silently dropped.
--
-- ⚠️ THE LEAD-CHANGE LAG IS TAKEN OVER THE WHOLE GAME AND ONLY THE COUNTING IS SCOPED. A crossing
-- on the first play of the fourth quarter is a fourth-quarter lead change, and computing the lag
-- inside a period-filtered set would discard exactly that event — the most dramatic one there is.
--
-- 🚨 COMPETITIVENESS IS MEASURED AS DISTANCE FROM EVEN, AND IT IS DELIBERATELY THRESHOLD-FREE.
-- A115 handed forward that swing and range promote FBS-vs-FCS mismatches, because one play moving
-- a probability that was already near certainty looks identical to a thriller. A band ("share of
-- plays within 0.10 of even") answers it but smuggles in a cutoff nobody measured, so what is
-- carried instead is the mean and the minimum of |wp - 0.5|:
--
--     mean_distance_from_even_fourth_quarter_onward   how close it was, and for how long, in one
--                                                    number. 0 = dead even throughout.
--     closest_to_even_fourth_quarter_onward          the closest it ever got, late.
--
-- ✅ MEASURED ON 2026 WEEK 2, AND IT SEPARATES THE ARTIFACT DECISIVELY: Central Connecticut @
-- Toledo ranks 3rd of 86 on largest swing and 59th of 86 on mean distance from even, late.
--
-- ⚠️ AND IT ALSO CORRECTED THE PREMISE IT WAS BUILT FOR. A115 named four games as mismatch
-- artifacts; only ONE is. Colgate @ Central Michigan, Gardner-Webb @ Liberty and South Florida @
-- Army rank 12th, 16th and 20th on this measure — interleaved with Marc's own seven, which spread
-- 5th to 24th. They were close games involving a non-FBS team, which is not the same thing as an
-- artifact. §2.4: a diagnosis is an inference, and this one did not survive being measured.
--
-- 🚨 THE LEAKAGE RULE DOES NOT APPLY TO ANY COLUMN IN THIS MODEL, AND A LATER ROUND MUST NOT
-- "FIX" IT. Every measure here is a POST-GAME fact about a finished game — how the curve actually
-- moved — not an input to a prediction about it. fct_player_leader_week's `1 preceding` frame and
-- fct_team_record_week's are point-in-time because a Matchup page reads them BEFORE kickoff. This
-- table is read afterwards, to say what happened. Scoping it to prior weeks would make every
-- column describe a different game.
--
-- SPREAD IS DELIBERATELY NOT CARRIED. It is zero on all 263,539 rows, which is CFBD's zero
-- and not ours (R-089). Summarising a constant would manufacture a column that looks like
-- information.

with plays as (

    select
        w.game_id,
        w.play_number,
        w.home_win_probability,
        -- The time element, from stg_play. See the header: joined on play_id, which is unique in
        -- both models, so this cannot change the play grain.
        p.period,
        -- Half the plays, per game. An approximation of halftime; see the header.
        row_number() over (partition by w.game_id order by w.play_number)                as seq,
        count(*)     over (partition by w.game_id)                                       as total_plays,
        lag(w.home_win_probability) over (partition by w.game_id order by w.play_number) as previous_wp
    from {{ ref('stg_game_win_probability') }} w
    left join {{ ref('stg_play') }} p
      on p.play_id = w.play_id
    where w.home_win_probability is not null

),

flagged as (

    select
        *,
        abs(home_win_probability - previous_wp)                                      as swing,
        -- How far from a coin flip this play was. 0 = dead even. Threshold-free, so no cutoff
        -- gets baked in here that a later reader cannot see.
        abs(home_win_probability - 0.5)                                              as distance_from_even,
        -- A crossing of the 0.5 line in either direction. Null previous_wp is the first play
        -- of a game and cannot be a crossing.
        case when previous_wp is null then 0
             when (previous_wp < 0.5 and home_win_probability >= 0.5)
               or (previous_wp >= 0.5 and home_win_probability < 0.5) then 1
             else 0 end                                                              as lead_change
    from plays

)

select
    {{ surrogate_key(['game_id']) }}                as game_wp_summary_sk,
    game_id,
    count(*)                                        as plays_with_win_probability,
    round(min(home_win_probability), 4)             as lowest_home_win_probability,
    round(max(home_win_probability), 4)             as highest_home_win_probability,
    -- How far the game travelled: the gap between the home side's best and worst moment.
    round(max(home_win_probability) - min(home_win_probability), 4)
                                                    as home_win_probability_range,
    round(max(swing), 4)                            as largest_single_play_swing,
    sum(lead_change)                                as lead_changes,
    round(max(case when seq <= total_plays / 2 then home_win_probability end), 4)
                                                    as halftime_home_win_probability_approx,
    round(max(case when seq = total_plays then home_win_probability end), 4)
                                                    as final_home_win_probability,

    -- ── THE FOURTH QUARTER ITSELF (period = 4), which is what Marc asked for ──────────────
    --
    -- ⚠️ EVERY COUNT BELOW IS NULL WHEN THE FEED NEVER REACHED THE FOURTH QUARTER, AND THAT IS
    -- AC-G.32 RATHER THAN TIDINESS. Three games of 1,898 have a truncated win-probability feed —
    -- Southern Miss @ Kentucky and UC Davis @ California (2024 week 1, 83 and 81 plays against a
    -- ~154 typical) and New Mexico @ Utah State (2024 week 8, 34) — so CFBD's curve stops before
    -- the fourth quarter begins. `sum(... else 0)` would report ZERO fourth-quarter lead changes
    -- for them, which claims we looked and found none. We did not look; there is nothing to look
    -- at. A zero here would rank those games above every genuine 0-lead-change blowout on any
    -- "fewest" ordering and would read as a measurement on any card.
    count(*) filter (where period = 4)               as plays_with_win_probability_fourth_quarter,
    case when count(*) filter (where period = 4) > 0
         then sum(case when period = 4 then lead_change else 0 end) end
                                                    as lead_changes_fourth_quarter,
    round(max(case when period = 4 then swing end), 4)
                                                    as largest_single_play_swing_fourth_quarter,
    round(max(case when period = 4 then home_win_probability end)
          - min(case when period = 4 then home_win_probability end), 4)
                                                    as home_win_probability_range_fourth_quarter,

    -- ── OVERTIME, SEPARATELY (period >= 5), so it is neither folded in nor dropped ────────
    --
    -- 🚨 AND THE GUARD IS THE FOURTH-QUARTER COUNT, NOT THE OVERTIME COUNT, which is the subtle
    -- half. "No overtime plays" means two completely different things:
    --
    --     the feed HAS a fourth quarter, and no OT plays   the game ended in regulation. 0 is a
    --                                                      FACT, and the overwhelming majority.
    --     the feed has NO fourth quarter                   we cannot even tell whether it went to
    --                                                      overtime. NULL.
    --
    -- A feed that reached the fourth quarter reached the end of regulation, so the fourth-quarter
    -- count is exactly the evidence that separates the two.
    count(*) filter (where period >= 5)              as plays_with_win_probability_overtime,
    case when count(*) filter (where period = 4) > 0
         then sum(case when period >= 5 then lead_change else 0 end) end
                                                    as lead_changes_overtime,

    -- ── COMPETITIVENESS: distance from even, threshold-free. See the header. ──────────────
    -- Whole game, for comparison against the late window.
    round(avg(distance_from_even), 4)                as mean_distance_from_even,
    -- The fourth quarter ONWARD, so a game decided in double overtime is not judged on its
    -- fourth quarter alone.
    round(avg(case when period >= 4 then distance_from_even end), 4)
                                                    as mean_distance_from_even_fourth_quarter_onward,
    round(min(case when period >= 4 then distance_from_even end), 4)
                                                    as closest_to_even_fourth_quarter_onward
from flagged
group by game_id
