{{ config(materialized='table') }}

-- The win-probability CURVE, per play, for a completed game. R-724.
--
-- 🚨 THIS MART EXISTS BECAUSE `ci/assert_layer_boundaries` REFUSED THE FIRST ATTEMPT, AND IT WAS
-- RIGHT. A121 first wrote the curve as a serving view reading `stg_game_win_probability` and
-- `stg_play` directly, on the precedent of `srv_game_team_leader` being "a serving-layer window
-- over the mart, with no new mart". ⚠️ THAT PRECEDENT DOES NOT APPLY HERE, and the difference is
-- the point: that view had a mart at its grain to window over. This one does not —
-- `fct_game_win_probability_summary` collapses the curve to ONE ROW PER GAME, so at PLAY grain
-- there was no mart at all and the serving view was reaching past an empty layer rather than
-- skipping a full one.
--
-- ✅ `Only staging reads sources; marts build on staging; serving builds on marts.` The join to
-- `stg_play` for the period belongs HERE, and the serving view reads this.
--
-- ONE ROW PER (game_id, play), which is the grain the chart draws. Marc: "We need win probability
-- graphs for the games." A118 shipped the ESPN links and the quarter scoreboard and correctly did
-- not attempt this, because until now the curve stopped at STAGING: only the game-level SUMMARY
-- reached serving, through `fct_game_win_probability_summary` and `srv_game`.
--
-- 🚨 COWORK'S NOTE ON THIS OBJECT SAID "that would be the largest object in serving" AND IT IS
-- FALSE — measured before building, across all 32 serving models:
--
--     1  srv_player_stats                     1,521,532
--     2  srv_player_game_log                  1,410,331
--     3  srv_player_play                        375,925
--     4  srv_team_week                          375,594
--     5  srv_game_team_leader                   308,232   <- RETIRED, A132 (R-841)
--     6  THIS MODEL                             291,548   <- sixth of thirty-three
--     7  srv_game_team                          225,350
--
-- ✅ SO IT IS BUILT WHOLE AND NOTHING IS DOWNSAMPLED. A thinned curve is a DIFFERENT CHART and a
-- reader cannot tell that they are looking at one: the peaks a reader is drawn to are exactly the
-- points a sampler drops. Pruning an object that does not need pruning would have cost that for
-- nothing.
--
-- 🚨 THE X AXIS IS THE DESIGN DECISION, NOT THE Y, AND BOTH HALVES ARE CARRIED:
--
--     play_number   MONOTONIC, UNIQUE and dense within a game — a DERIVED ordinal, see the
--                   column below. ⚠️ A183: it is no longer the feed's raw number, because the
--                   feed's is not tie-free. The feed's own label is published beside it as
--                   `source_play_number`.
--                   🚨 AND THIS IS NO LONGER THE AXIS THE CHART POSITIONS ON — A136 moved that to
--                   `elapsed_from_kickoff_seconds`, and `site/lib/winprob.py` says so in its own
--                   docstring. This is the ORDER a play has, and inside an overtime period it is
--                   still the only order there is.
--     period        WHAT A READER RECOGNISES. The chart ANNOTATES with this — quarter boundaries,
--                   and the overtime band. A reader does not think in play numbers.
--     is_overtime   so a chart can shade or separate overtime rather than letting it read as a
--                   longer fourth quarter. A118 established that overtime must never be folded
--                   onto the fourth quarter, and a curve is where that would be least visible.
--
-- ⚠️ THE PERIOD COMES FROM `stg_play`, JOINED ON `play_id`, BECAUSE THIS FEED CARRIES NO PERIOD AT
-- ALL — A117 measured that, and Marc diagnosed the mechanism before it was measured:
-- "stg_game_win_probability with stg_play for the time element."
--
-- ⚠️ AND THE JOIN IS A `left join` DELIBERATELY. Exactly ONE play of 291,548 has no matching
-- `stg_play` row, and `fct_game_win_probability_summary` already made this choice for the same
-- play. An inner join would drop it — and a curve missing a play because of a join is a worse
-- outcome than a null period on one row, because the reader cannot see the absence.
--
-- 📊 COVERAGE, IN ROWS AND IN GAMES, AND IT IS BOUNDED BY A SETTLED DECISION rather than by this
-- model: play-by-play scope is 2024-2026 only.
--
--     season   plays    games   no period   overtime plays   overtime games
--     2024    139,052     912           0             381               34
--     2025    124,486     803           0             345               33
--     2026     28,010     183           1              61                3
--     total   291,548   1,898           1             787               70
--
-- 🚨 SO A 2019 GAME HAS NO CURVE, AND THAT IS A SCOPE DECISION RATHER THAN MISSING DATA. AC-G.11:
-- the page must say WHICH absence it is — "outside the play-by-play window" reads differently from
-- "this game has no win probability", and a 2024+ game with no rows here is the second.
--
-- ⚠️ THE HEADER OF `stg_game_win_probability` SAYS 263,539 ROWS OVER 1,715 GAMES AND THAT IS STALE.
-- Current, measured today: 291,548 over 1,898. The staging figure predates A115's metrics/wp
-- cadence and A117's catch-up. Not corrected here — that is that model's header to fix, and
-- editing it would put this round in a file it has no other business in.
--
-- 🚨 THE LEAKAGE RULE DOES NOT APPLY TO THIS VIEW, AND A LATER ROUND MUST NOT "FIX" IT.
-- `fct_player_leader_week` is point-in-time by construction — `rows between unbounded preceding
-- and 1 preceding` — because a preview card is read BEFORE kickoff. This object is the other side
-- of that line: it describes a COMPLETED game and is read afterwards, to say what happened.
-- Scoping it to prior weeks would make every row describe a different game. (A120 wrote this same
-- sentence for the post-game leader twin; the two read as one rule on purpose.)
--
-- 📊 A136 MEASURED THE SHAPE OF OVERTIME, BECAUSE A MAX OF ONE IS A DIFFERENT DRAWING PROBLEM
-- FROM A MAX OF FOUR. Of the 70 games with overtime plays:
--
--     overtime periods   games   overtime plays   min / mean / max plays
--            1             50          447            1 /  8.9 / 20
--            2             19          318            8 / 16.7 / 28
--            3              1           22           22 / 22.0 / 22
--
-- ⚠️ SO THE LONGEST GAME IN THE WAREHOUSE RUNS TO THREE OVERTIMES, AND ONE OVERTIME PERIOD
-- CARRIES AS FEW AS ONE WIN-PROBABILITY PLAY. A chart sized for the longest game in a week
-- leaves a regulation game short of the right-hand edge; A136's report carries that cost.

-- ⚠️ `home_win_probability` IS PUBLISHED AS THE FEED GIVES IT, 0 TO 1, AND IS NOT SCALED TO 0-100.
-- §4.2.1 forbids the PAGE multiplying, and it does not have to: an Altair axis takes `format='%'`
-- and renders 0.62 as 62%, which is a rendering instruction rather than arithmetic. A second
-- column holding the same number times a hundred would be 291,548 more values carrying no
-- information, and two columns that must agree.
select
    {{ surrogate_key(['w.game_id', 'w.play_id']) }}      as game_win_probability_play_sk,
    w.game_id,
    w.play_id,
    -- ── POSITION ───────────────────────────────────────────────────────────────────────────
    --
    -- 🚨 A183 (cfdb-main-R-1871). CFBD BROKE THE PROPERTY THIS COLUMN PROMISES, AND THE TEST
    -- CAUGHT IT. `assert_the_win_probability_curve_is_ordered_by_play_number` failed on 52 rows:
    -- 26 pairs across 14 games where two plays carry the SAME feed `playNumber`.
    --
    -- 📊 DIAGNOSED FIRST, BECAUSE THE TWO CASES NEED OPPOSITE FIXES. In all 26 pairs the two rows
    -- have DIFFERENT `play_id`s — two real, different plays the feed numbered alike, not the same
    -- play twice. Game 401856693 play 109 is a missed field goal AND a 2-yard rush. **A dedupe
    -- would delete a real play and draw a different game**, so the fix has to keep both.
    --
    -- ⚠️ AND A MINIMAL TIE-BREAK WAS TRIED FIRST AND MEASURED IMPOSSIBLE, WHICH IS WHY THIS IS A
    -- RENUMBER. Shifting the second row of each tie into the gap above it (`play_number + rank-1`)
    -- would have touched 26 rows and left 1,947 games untouched — except the numbering is locally
    -- dense around every tie, so **all 26 shifts collided with a real play**. There is no integer
    -- tie-break that preserves the feed's values.
    --
    -- ✅ SO THE PUBLISHED NUMBER IS A DERIVED ORDINAL, AND THE FEED'S OWN LABEL IS KEPT BESIDE IT.
    -- Ordering by (the feed's number, then `play_id`) means **every play keeps its position
    -- relative to every other play** — this reorders nothing, it only makes the ties total. The
    -- feed's number was never dense anyway: of 1,973 games, ZERO start at 1 and ZERO have
    -- max = count, so no reader could have been reading it as "the Nth play".
    --
    -- 🚨 THE TIE-BREAK IS `play_id` AND IT IS COMPARED AS AN INTEGER, NOT LEXICALLY. `play_id` is
    -- `text` in this feed and the ids are not fixed width — they run from -22856 to
    -- 401858212104999901 — so `order by play_id` sorts play 10 before play 2. That is the EXACT
    -- defect the ordering test was written against; doing it here would have reintroduced it as
    -- the fix for it. ⚠️ It only decides the order WITHIN a tie, so it changes nothing else.
    --
    -- ⚠️ AND THE CAST WAS PROVEN TOTAL BEFORE BEING RELIED ON, because a cast that throws takes
    -- the whole build down. All 303,073 rows cast; `play_id !~ '^-?[0-9]+$'` returns ZERO.
    -- 📊 The first check used `^[0-9]+$` and reported 2,663 "non-numeric" ids — they are the
    -- SYNTHETIC NEGATIVE ids (-1000, -1001, …) and the regex was catching the minus sign, not a
    -- letter. A regex that answers a slightly different question than the one asked (§2.4).
    --
    -- ⚠️ NO TEST COVERAGE IS LOST BY RENUMBERING HERE. The ordering test's load-bearing branch
    -- compares the VIEW against THIS MART, not against staging — it was moved off staging for
    -- R-672's straddle — so it still proves the serving view did not resort or renumber. What it
    -- never checked, and still does not, is this mart against the feed; `source_play_number`
    -- below is what makes that checkable at all.
    row_number() over (partition by w.game_id
                       order by w.play_number, w.play_id::bigint)  as play_number,
    -- THE FEED'S OWN LABEL, UNCHANGED, so the renumber above is auditable rather than lossy.
    -- ⚠️ Not unique within a game — that is the whole finding. Do not order on it alone.
    w.play_number                                                  as source_play_number,
    -- ANNOTATION: what a reader recognises. Null on the one play with no stg_play match.
    p.period,
    -- ⚠️ NULL, NOT FALSE, WHERE THE PERIOD IS UNKNOWN. "This play was not in overtime" and "we do
    -- not know which period this play was in" are different facts, and `period >= 5` on a null
    -- yields null, which is the honest answer rather than a confident `false`. AC-G.32.
    case when p.period is not null then p.period >= 5 end as is_overtime,
    -- ── THE CLOCK, SO THE CURVE AND THE DRIVES CAN SHARE ONE X-AXIS ─────────────────────────
    --
    -- Marc, 2026-09-14: "Merge the into the data model so we can tell the story with Win % over
    -- the fixed time of the game." To draw the drives and the win-probability curve on ONE axis,
    -- both need the same time unit.
    --
    -- 🚨 THIS IS DELIBERATELY THE TWIN OF `fct_drive.elapsed_from_kickoff_seconds` — same name,
    -- same units (seconds from kickoff), same origin (kickoff = 0) and the same null rule. Two
    -- definitions of "elapsed" on one x-axis is the exact drift this project keeps paying for:
    -- B098's `metric`, B099's `_CARD_KPIS`, B100's two delta renderers, A116's labels-as-data.
    -- The whole point of the column is that two marks share an axis, so it cannot be a second
    -- definition of the thing they share.
    --
    -- 🚨🚨 AND THE ARITHMETIC IS NOT COPIED LITERALLY, BECAUSE `clock_seconds` MEANS THE OPPOSITE
    -- THING IN THE TWO SOURCES. This is the trap and it is worth the space:
    --
    --     fct_drive reads  start_clock_seconds   the SECONDS COMPONENT of mm:ss
    --                      -> so it must write   start_clock_minutes * 60 + start_clock_seconds
    --     stg_play carries clock_seconds         ALREADY minutes * 60 + seconds (stg_play:85-87)
    --                      clock_seconds_part    the component, if anyone wants it
    --
    -- ⚠️ `fct_drive`'s own comment names half of this already — "start_clock_seconds IS THE
    -- SECONDS COMPONENT OF mm:ss, NOT A TOTAL". Copying its expression onto `stg_play`'s columns
    -- would MULTIPLY A TOTAL BY 60, and the result would not look wrong: real integers on a
    -- plausible axis. A122 verified by hand instead, on three plays of Ohio State at Texas:
    --
    --     play 401856682189   period 1, 0:00    (1-1)*900 + (900-0)   =  900  = 15:00
    --     play 401856682418   period 3, 15:00   (3-1)*900 + (900-900) = 1800  = 30:00
    --     play 401856682479   period 3, 10:00   (3-1)*900 + (900-600) = 2100  = 35:00
    --
    -- ⚠️ NULL OUTSIDE REGULATION RATHER THAN EXTRAPOLATED — `fct_drive`'s rule, which governs
    -- this column because it is the same column: "Overtime possessions are not 900 seconds of
    -- anything, so (period-1)*900 would invent a duration that never elapsed."
    --
    -- 🚨 AND THE CONSEQUENCE FOR THE CURVE IS MEASURED RATHER THAN LEFT TO BE DISCOVERED: 787 of
    -- 291,548 rows (0.270%) go null, across 70 of 1,898 games (3.7%). A122 drew overtime by
    -- compressing 24 plays into 20 pixels of a 180-wide viewBox; on an ELAPSED axis those plays
    -- have no position at all. ✅ THIS ROUND PUBLISHES THE COLUMN AND STATES THAT. Redesigning
    -- the curve is a page round and it is B's file.
    --
    -- ⚠️ A140 MOVED THE EXPRESSION INTO `elapsed_from_kickoff()` AND CHANGED NOTHING ELSE.
    -- `fct_game_win_probability_summary` needs the same clock inside its `lag()` windows
    -- (cfdb-main-R-916), and two copies of an arithmetic expression that must agree is the
    -- drift this project has paid for four times in two weeks. The macro's header carries the
    -- `fct_drive` trap and A122's hand-verified plays; they are not repeated here.
    {{ elapsed_from_kickoff('p.period', 'p.clock_seconds') }}
                                                          as elapsed_from_kickoff_seconds,
    -- ── A136: THE OVERTIME COORDINATE, AND IT IS NOT A CLOCK ────────────────────────────────
    --
    -- Marc, 2026-09-15, on the chart's reference lines: "Start, 2nd, half (darker), 3rd, 4th
    -- (full, darker), each OT, Final" and "Games with overtime will be longer."
    --
    -- 🚨 THE REGULATION HALF WAS ALREADY FREE — 900 / 1800 / 2700 on the column above. THE
    -- OVERTIME HALF COULD NOT BE DRAWN AT ALL, because `elapsed_from_kickoff_seconds` is null
    -- for every overtime play and that decision is correct and is NOT being reversed: an
    -- overtime period is not 900 seconds of anything, and A118 established that overtime must
    -- never fold into a longer fourth quarter.
    --
    -- ✅ SO OVERTIME GETS ITS OWN COORDINATE, IN ITS OWN UNIT, WITH A NAME THAT CANNOT BE READ
    -- AS TIME:
    --
    --     overtime_axis_offset_periods   HOW FAR PAST THE END OF REGULATION THIS PLAY SITS,
    --                                    MEASURED IN OVERTIME PERIODS. 0.0 is the first play of
    --                                    the first overtime; 1.5 is halfway through the second.
    --                                    NULL in regulation.
    --
    -- 🚨 WHAT IT IS NOT, because the name is the load-bearing part of this column:
    --
    --     NOT a duration        its unit is PERIODS, not seconds. Nothing elapsed to produce it
    --     NOT elapsed clock     it is not comparable with elapsed_from_kickoff_seconds and must
    --                           never be added to it, coalesced with it, or plotted on its scale
    --     NOT a play index      it is continuous and bounded to its own period, so two plays in
    --                           different overtimes cannot collide
    --
    -- ✅ AND IT IS DELIBERATELY ONE COLUMN SCALED BY ONE CONSTANT AT THE PAGE (§4.2.1). The chart
    -- writes `x = 3600 + overtime_axis_offset_periods * BAND_WIDTH`, where BAND_WIDTH is a layout
    -- literal in the page — because how wide an overtime band should be is a DRAWING decision and
    -- has no business being frozen into the warehouse. A pair of columns the page had to combine
    -- would be arithmetic BETWEEN two published values, which is the thing §4.2.1 forbids.
    --
    -- ⚠️ THE REFERENCE LINE FOR OVERTIME k FALLS EXACTLY ON k - 1, and that is a property rather
    -- than a coincidence: the fraction is (n - 1) / count, so the FIRST play of each overtime
    -- sits exactly on the integer and the last sits strictly below the next one.
    --
    -- ⚠️ ORDERED BY `play_number`, WHICH IS THE ONLY ORDER AN OVERTIME PLAY HAS. Overtime carries
    -- no usable clock — A136 measured stg_play's period-5-and-up rows as taking six distinct
    -- clock values in total, essentially 0 and 900 — so there is nothing else to sort on. It is
    -- also the same order the published curve is already drawn in, so this coordinate is exactly
    -- as ordered as the line it positions, and no more.
    case when p.period >= 5 then p.period - 4 end          as overtime_period,
    case when p.period >= 5
         then (p.period - 5)
              + (row_number() over (partition by w.game_id, p.period
                                    order by w.play_number, w.play_id::bigint) - 1)
                / (count(*) over (partition by w.game_id, p.period))::numeric
    end                                                   as overtime_axis_offset_periods,
    -- THE VALUE, exactly as published. See the header on why it is not scaled.
    w.home_win_probability,
    -- IDENTITY, so a tooltip and a legend need no second query.
    w.home_team_id,
    w.home_team,
    w.away_team_id,
    w.away_team,
    -- THE STATE AT THAT PLAY — the tooltip's content.
    w.home_score,
    w.away_score,
    w.down,
    w.distance,
    w.yard_line,
    w.home_has_ball,
    -- ⚠️ CARRIED, AND THE WIDTH WAS MEASURED RATHER THAN GUESSED: 23 MB on disk across 291,548
    -- rows, averaging 78 characters and peaking at 770. That is 7% of `srv_player_stats`'s 306 MB
    -- and it is what makes a hovered point say what happened rather than only when it happened —
    -- which is the entire reason a reader hovers a win-probability curve.
    w.play_text
from {{ ref('stg_game_win_probability') }} w
-- LEFT, for the one play in 291,548 with no match. See the header.
left join {{ ref('stg_play') }} p
       on p.play_id = w.play_id
where w.home_win_probability is not null
