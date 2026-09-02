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
-- midpoint of the game's plays, not by quarter: this feed carries no period column. That is
-- an approximation and is named one — halftime_home_win_probability_approx — rather than
-- being presented as the value at the whistle.
--
-- SPREAD IS DELIBERATELY NOT CARRIED. It is zero on all 263,539 rows, which is CFBD's zero
-- and not ours (R-089). Summarising a constant would manufacture a column that looks like
-- information.

with plays as (

    select
        game_id,
        play_number,
        home_win_probability,
        -- Half the plays, per game. An approximation of halftime; see the header.
        row_number() over (partition by game_id order by play_number)                as seq,
        count(*)     over (partition by game_id)                                     as total_plays,
        lag(home_win_probability) over (partition by game_id order by play_number)   as previous_wp
    from {{ ref('stg_game_win_probability') }}
    where home_win_probability is not null

),

flagged as (

    select
        *,
        abs(home_win_probability - previous_wp)                                      as swing,
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
                                                    as final_home_win_probability
from flagged
group by game_id
