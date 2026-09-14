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
--     5  srv_game_team_leader                   308,232
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
--     play_number   MONOTONIC and always present. The chart POSITIONS on this — it has no gaps,
--                   no ties and no restarts, so a line drawn on it cannot fold back on itself.
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
-- ⚠️ `home_win_probability` IS PUBLISHED AS THE FEED GIVES IT, 0 TO 1, AND IS NOT SCALED TO 0-100.
-- §4.2.1 forbids the PAGE multiplying, and it does not have to: an Altair axis takes `format='%'`
-- and renders 0.62 as 62%, which is a rendering instruction rather than arithmetic. A second
-- column holding the same number times a hundred would be 291,548 more values carrying no
-- information, and two columns that must agree.
select
    {{ surrogate_key(['w.game_id', 'w.play_id']) }}      as game_win_probability_play_sk,
    w.game_id,
    w.play_id,
    -- POSITION: monotonic, always present, and what the line is drawn against.
    w.play_number,
    -- ANNOTATION: what a reader recognises. Null on the one play with no stg_play match.
    p.period,
    -- ⚠️ NULL, NOT FALSE, WHERE THE PERIOD IS UNKNOWN. "This play was not in overtime" and "we do
    -- not know which period this play was in" are different facts, and `period >= 5` on a null
    -- yields null, which is the honest answer rather than a confident `false`. AC-G.32.
    case when p.period is not null then p.period >= 5 end as is_overtime,
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
