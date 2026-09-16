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
-- 🚨 `halftime_home_win_probability_approx` AND `final_home_win_probability` ARE GONE — A140,
-- AND THE REASON THEY LASTED THIS LONG WAS A CLAIM NOBODY CHECKED.
--
-- A117 declined to fix the halftime approximation and wrote why: *"the column is published, a
-- page reads it, and silently changing what a published number MEANS is worse than leaving an
-- honestly-named approximation in place."* 📊 **MEASURED AT `origin/main` BEFORE A140 TOUCHED
-- ANYTHING: neither column is selected by `srv_game`, neither is in `_models.yml`, and
-- `git grep` finds them in exactly one file — this one.** Zero pages, zero tests, zero
-- consumers. The sentence that kept them was false when it was written.
--
-- ⚠️ BOTH WERE ALSO BUILT ON `row_number() over (order by play_number)`, so both inherited
-- cfdb-main-R-916. **A column nobody reads, computed wrongly, is not a defect a reader can
-- meet — it is dead weight that a future round will trust**, and A140 is the round that would
-- otherwise have had to correct and carry them.
--
-- ✅ AND IT IS STILL §3.3's SHAPE, AT ZERO COST RATHER THAN NOT APPLYING: EXPAND was never
-- needed, MIGRATE is empty because there is nobody to migrate, CONTRACT is this deletion.
-- Saying that is the difference between following the rule and skipping it.
--
-- ❌ NEITHER IS REPLACED. A136 already publishes better answers to both questions:
-- `win_probability_curve_reaches_final_score` says whether the curve finished at all — it does
-- not on 99 of 1,898 games — and `winner_mean_win_probability` says how far behind the eventual
-- winner was. A "final" probability that is on the wrong side of the result for 94 games is not
-- repaired by sorting it.
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

-- 🚨 A136 ADDS THE COMEBACK MEASURE, AND IT IS THE ONLY COLUMN HERE THAT NEEDS TO KNOW WHO WON.
--
-- Marc, 2026-09-15: "averages the win probability for each team in a game (win probability, play
-- by play) and then look for big disparity between low win probability (behind the whole game),
-- but were successful in the end (Texas of Ohio State)."
--
--     winner_mean_win_probability   THE EVENTUAL WINNER'S mean win probability across the whole
--                                   curve. LOW = the winner was behind for most of the game.
--                                   Ohio State @ Texas, 2026 week 2: 0.2291, the lowest of the
--                                   86 games that week and the game Marc named.
--
-- 🚨 IT IS NOT `mean_distance_from_even_fourth_quarter_onward` AND THE TWO MUST NEVER BE READ AS
-- VARIANTS OF EACH OTHER. That column measures how CLOSE the game stayed late and is symmetric —
-- it does not know who won. This one measures how far BEHIND the eventual winner was, over the
-- whole game, and is meaningless without the result. A102 spent a round on two columns whose
-- names differed by a phrase and whose meanings differed entirely; this note is the toll.
--
-- ⚠️ ONE COLUMN, NOT A DIFFERENCE OF TWO. The loser's mean is 1 minus this by construction, so a
-- second column holding it would be 1,898 values carrying no information and two numbers that
-- must agree. `mean_home_win_probability` is published beside it because it is the raw curve
-- property the winner-mean is derived FROM — it is what makes this auditable, and it is what a
-- chart would shade with. ❌ A PAGE MUST NOT RE-DERIVE THE WINNER MEAN FROM IT (§4.2.1).
--
-- ✅ PER PLAY, NOT PER UNIT OF CLOCK, AND THE ALTERNATIVE WAS MEASURED RATHER THAN DISMISSED.
-- A clock-weighted mean — each play's probability held until the next play's elapsed time —
-- was built and compared on all 1,898 games: mean absolute difference 0.0108, maximum 0.1399,
-- Pearson 0.9963, and on 2026 week 2 the two orderings share ten of their top ten with one
-- swap and a worst rank move of 9 places of 86. 🚨 THE DECIDING ARGUMENT IS NOT THE AGREEMENT,
-- IT IS OVERTIME: an overtime play has no clock, so a clock-weighted mean silently DROPS the
-- most dramatic part of exactly the games this column exists to find. It would also inherit
-- the feed's play ordering, and a mean does not — see below.
--
-- ✅ AND A MEAN IS ORDER-INDEPENDENT, WHICH MATTERS MORE HERE THAN IT LOOKS. A136 measured that
-- the feed's own `play_number` is NOT chronological in 336 of 1,898 games: 795 consecutive pairs
-- step BACKWARDS on the elapsed-clock axis and 165 step backwards in period. Every column above
-- that uses `lag`, `row_number` or "the last play" inherits that; `avg` does not.
--
-- 🚨🚨 AND THE FEED HAS A SECOND DEFECT THAT WOULD HAVE PUT A 44-15 BLOWOUT THIRD ON A
-- BIGGEST-COMEBACKS LIST, SO THE GUARD IS PUBLISHED BESIDE THE MEASURE:
--
--     win_probability_curve_reaches_final_score   whether the curve's OWN scoreboard ever reaches
--                                                 the game's final score. FALSE on 99 of 1,898
--                                                 games (5.2%).
--
-- ⚠️ A truncated curve leaves the trailing side's low probability as its last word, so the mean
-- sits low and the game reads as a comeback. 📊 MEASURED: those 99 games are 5.2% of the
-- population and FIVE OF THE TWENTY-FIVE LOWEST winner means — a 3.8x enrichment at exactly the
-- end of the ranking a page would show. Coastal Carolina @ UTSA (2024 week 1) is the worst of
-- them: UTSA won 44-15 and its curve ends with the home side at 0.0012.
--
-- ✅ THE FLAG IS COMPUTED FROM `max(home_score)` AND `max(away_score)`, WHICH IS ORDER-INDEPENDENT
-- ON PURPOSE. A "last play" test would have been wrong on the 336 games above, and would have
-- been a guard with the same defect as the thing it guards.
--
-- ⚠️ A136 DID NOT FIX THE FEED AND DID NOT NARROW ANY EXISTING COLUMN. 94 of 1,898 games carry a
-- final published probability on the wrong side of the actual result and 78 are internally
-- inconsistent on their own last row.
--
-- ── A140, cfdb-main-R-916: THE ORDER, AND WHICH COLUMNS ACTUALLY DEPEND ON IT ──────────────
--
-- 🚨 THE AFFECTED SET IS FIVE PUBLISHED COLUMNS, NOT THREE. Every round since A136 has repeated
-- *"`lead_changes`, `final_home_win_probability` and `halftime_home_win_probability_approx`"*.
-- 📊 Measured by reading the model rather than the sentence: the columns built from `lag()` are
--
--     lead_changes                                  published, and today.py's FIRST SORT KEY
--     lead_changes_fourth_quarter                   published, ranked on
--     lead_changes_overtime                         published, shown as a column
--     largest_single_play_swing                     published, shown as a column   ← unnamed until now
--     largest_single_play_swing_fourth_quarter      published, and cited by name in _models.yml
--
-- and the two that were named carry ZERO consumers and are deleted above. **The two nobody
-- mentioned are the ones a reader has been looking at**, and `largest_single_play_swing` is the
-- worst affected of all: it moves on 76 games against `lead_changes`'s 64.
--
-- ⚠️ EVERYTHING ELSE HERE IS ORDER-INDEPENDENT AND STAYS EXACTLY AS IT IS — the minimum, the
-- maximum, the range, the play counts and A136's two means all read one row at a time or
-- aggregate without a neighbour. That is why the expand is five columns and not fifteen.
--
-- ✅ THE CORRECTED COLUMNS ARRIVE BESIDE THE OLD ONES AS `*_by_clock`, AND THE SUFFIX IS MEANT
-- TO LAST. It names the ORDER the measure is computed along, exactly as `_fourth_quarter` names
-- the window — and it stays true even if CFBD ever fixes the feed, at which point the two would
-- simply agree. `_v2` would have told a future reader nothing about why there are two.

with plays as (

    select
        w.game_id,
        w.play_number,
        w.home_win_probability,
        -- A136: the curve's own scoreboard, so the outer select can ask whether the curve ever
        -- reached the game's final score. Carried here rather than joined later because it is
        -- the same row the probability came from.
        w.home_score,
        w.away_score,
        -- The time element, from stg_play. See the header: joined on play_id, which is unique in
        -- both models, so this cannot change the play grain.
        p.period,
        -- ── TWO LAGS, IN TWO DIFFERENT ORDERS, AND THAT IS THE WHOLE EXPAND (A140) ──────────
        --
        -- 🚨 `previous_wp` IS THE FEED'S ORDER AND IT IS WRONG. cfdb-main-R-916 measured
        -- `play_number` non-chronological on 336 of 1,898 games. It is kept, unchanged, because
        -- `srv_game` publishes five columns built from it and `today.py` ranks on one of them —
        -- §3.3's EXPAND: the corrected values arrive beside the old ones, nothing moves yet.
        lag(w.home_win_probability) over (partition by w.game_id order by w.play_number) as previous_wp,
        -- ✅ `previous_wp_by_clock` IS THE ORDER THE PLAYS HAPPENED IN. One definition, shared
        -- with `fct_game_win_probability_play`'s published coordinate — see `curve_order()`.
        lag(w.home_win_probability) over (
            partition by w.game_id
            order by {{ curve_order('p.period', 'p.clock_seconds', 'w.play_number') }}
        )                                                                                as previous_wp_by_clock
    from {{ ref('stg_game_win_probability') }} w
    left join {{ ref('stg_play') }} p
      on p.play_id = w.play_id
    where w.home_win_probability is not null

),

flagged as (

    select
        *,
        abs(home_win_probability - previous_wp)                                      as swing,
        abs(home_win_probability - previous_wp_by_clock)                             as swing_by_clock,
        -- How far from a coin flip this play was. 0 = dead even. Threshold-free, so no cutoff
        -- gets baked in here that a later reader cannot see.
        --
        -- ✅ AND IT NEEDS NO `_by_clock` TWIN, WHICH IS WORTH SAYING RATHER THAN LEAVING TO BE
        -- NOTICED: `distance_from_even` reads ONE play and is averaged, so it cannot depend on
        -- what came before it. The same goes for `lowest_`, `highest_`, `home_win_probability_range`
        -- and A136's two means. **Only the columns built from `lag()` are affected**, which is
        -- why this expand is five columns and not fifteen.
        abs(home_win_probability - 0.5)                                              as distance_from_even,
        -- A crossing of the 0.5 line in either direction. Null previous_wp is the first play
        -- of a game and cannot be a crossing.
        case when previous_wp is null then 0
             when (previous_wp < 0.5 and home_win_probability >= 0.5)
               or (previous_wp >= 0.5 and home_win_probability < 0.5) then 1
             else 0 end                                                              as lead_change,
        case when previous_wp_by_clock is null then 0
             when (previous_wp_by_clock < 0.5 and home_win_probability >= 0.5)
               or (previous_wp_by_clock >= 0.5 and home_win_probability < 0.5) then 1
             else 0 end                                                              as lead_change_by_clock
    from plays

),

curve as (

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
    -- ── THE SAME TWO, COUNTED IN THE ORDER THE PLAYS HAPPENED (A140) ─────────────────────
    --
    -- 📊 THE FEED'S ORDER DOES NOT MERELY SHUFFLE THESE — IT MANUFACTURES THEM. Memphis at
    -- Georgia State (2025 week 2) publishes **25 lead changes and a 0.6704 largest swing**;
    -- counted along the clock it had **11 and 0.2401**. Fourteen of those crossings are the
    -- feed jumping between quarters, not the game changing hands.
    --
    -- 📊 ACROSS ALL 1,898 GAMES: `lead_changes` moves on **64**, worst by **14**;
    -- `largest_single_play_swing` moves on **76**, worst by **0.4303**;
    -- `lead_changes_fourth_quarter` on **13**, worst by 4; `lead_changes_overtime` on **6**.
    round(max(swing_by_clock), 4)                   as largest_single_play_swing_by_clock,
    sum(lead_change_by_clock)                       as lead_changes_by_clock,

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
    -- The A140 twins, same window, clock order. See the whole-game pair above.
    case when count(*) filter (where period = 4) > 0
         then sum(case when period = 4 then lead_change_by_clock else 0 end) end
                                                    as lead_changes_fourth_quarter_by_clock,
    round(max(case when period = 4 then swing_by_clock end), 4)
                                                    as largest_single_play_swing_fourth_quarter_by_clock,
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
    case when count(*) filter (where period = 4) > 0
         then sum(case when period >= 5 then lead_change_by_clock else 0 end) end
                                                    as lead_changes_overtime_by_clock,

    -- ── COMPETITIVENESS: distance from even, threshold-free. See the header. ──────────────
    -- Whole game, for comparison against the late window.
    round(avg(distance_from_even), 4)                as mean_distance_from_even,
    -- The fourth quarter ONWARD, so a game decided in double overtime is not judged on its
    -- fourth quarter alone.
    round(avg(case when period >= 4 then distance_from_even end), 4)
                                                    as mean_distance_from_even_fourth_quarter_onward,
    round(min(case when period >= 4 then distance_from_even end), 4)
                                                    as closest_to_even_fourth_quarter_onward,

    -- ── A136: THE RAW CURVE MEAN, AND THE EVIDENCE THE CURVE FINISHED ────────────────────
    --
    -- Home perspective, whole game, every play weighted the same. See the header for why per
    -- play rather than per unit of clock, and why the loser's mean is not a second column.
    round(avg(home_win_probability), 4)              as mean_home_win_probability,
    -- The curve's OWN highest scoreboard, which the outer select compares against the game's
    -- final score. `max` rather than "the last play": 336 games of 1,898 have a feed whose
    -- play_number is not chronological, so anything reading "the last play" shares the defect
    -- it is supposed to detect.
    max(home_score)                                  as highest_home_score_on_the_curve,
    max(away_score)                                  as highest_away_score_on_the_curve
from flagged
group by game_id

)

select
    c.*,
    -- ── A136: THE COMEBACK MEASURE ───────────────────────────────────────────────────────
    --
    -- The eventual winner's mean win probability. LOW = behind for most of the game and won.
    --
    -- ⚠️ THE ONLY COLUMN IN THIS MODEL THAT NEEDS THE RESULT, which is why `fct_game` is joined
    -- at all. Mart-on-mart, game_id to game_id, one row to one row — `fct_game` is unique on
    -- game_id, so this cannot fan out, and `assert_srv_game_is_still_one_row_per_game` guards
    -- the downstream grain besides.
    --
    -- ⚠️ `left join`, matching the `stg_play` join above and for the same reason: a curve whose
    -- game the warehouse does not model keeps its row and loses only the columns that need it.
    -- Measured today: 0 of 1,898 curves are in that state, and 0 games are tied.
    --
    -- ⚠️ AND NULL WHILE A GAME IS STILL BEING PLAYED, WHICH IS AC-G.32 RATHER THAN TIDINESS.
    -- `srv_game` is on the HOT publish list and `fct_game` is rebuilt every two hours, so
    -- `home_points` and `away_points` are a LIVE scoreboard, not only a final one. Without this
    -- arm the column would name whoever happens to be ahead right now as "the winner" and flip
    -- sides mid-afternoon. 📊 Measured today: 0 of 1,898 games with a curve are incomplete —
    -- `metrics/wp` is fetched weekly for finished games — so this arm costs nothing and closes
    -- the one path the two-hourly cadence actually opens.
    case
        when not g.is_completed                         then null
        when g.home_points is null or g.away_points is null then null
        when g.home_points = g.away_points              then null
        when g.home_points > g.away_points              then c.mean_home_win_probability
        else round(1 - c.mean_home_win_probability, 4)
    end                                              as winner_mean_win_probability,
    -- 🚨 THE GUARD, AND IT IS NOT DECORATION — see the header. FALSE on 99 of 1,898 games, and
    -- those 99 are five of the twenty-five lowest winner means. A page ranking on the comeback
    -- measure without reading this will put a 44-15 blowout near the top of the list.
    case
        when not g.is_completed                         then null
        when g.home_points is null or g.away_points is null then null
        else c.highest_home_score_on_the_curve = g.home_points
         and c.highest_away_score_on_the_curve = g.away_points
    end                                              as win_probability_curve_reaches_final_score
from curve c
left join {{ ref('fct_game') }} g
       on g.game_id = c.game_id
