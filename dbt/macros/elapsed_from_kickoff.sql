{#
  A140, cfdb-main-R-916. ONE DEFINITION OF THE REGULATION GAME CLOCK, because two models now
  need it and the second one needed it as an ORDER BY rather than as a column.

  🚨 IT IS A MACRO FOR THE REASON A120's `player_card_slots` IS ONE: the expression was about to
  exist twice. `fct_game_win_probability_play` publishes it as
  `elapsed_from_kickoff_seconds`; `fct_game_win_probability_summary` needs the same ordering
  inside its `lag()` and `row_number()` windows. Two copies of an arithmetic expression that
  must agree is precisely the drift this project has paid for four times in two weeks — B098's
  `metric`, B099's `_CARD_KPIS`, B100's two delta renderers, A116's labels-as-data.

  🚨🚨 AND THE ARITHMETIC IS NOT THE ONE `fct_drive` USES, WHICH IS THE TRAP THIS MACRO MUST NOT
  SPREAD. `stg_play.clock_seconds` is ALREADY minutes * 60 + seconds (stg_play:85-87);
  `stg_drive.start_clock_seconds` is the SECONDS COMPONENT of mm:ss, which is why `fct_drive`
  multiplies and this does not. Copying either expression onto the other's columns produces
  plausible integers on a plausible axis where every value is wrong.

  ⚠️ SO THIS MACRO IS FOR `stg_play`'s CLOCK AND NOTHING ELSE. It takes the two column
  expressions rather than a table alias so both call sites can pass their own, and the name
  says which lineage it belongs to. ❌ Do not call it with `fct_drive`'s columns.

  ⚠️ NULL OUTSIDE REGULATION, DELIBERATELY, and A118's rule is why: an overtime period is not
  900 seconds of anything, so `(period - 1) * 900` would invent a duration that never elapsed.
  787 of 291,548 rows go null on that boundary, plus the one play with no `stg_play` match.

  📊 VERIFIED BY HAND ON THREE PLAYS OF OHIO STATE AT TEXAS (A122's check, kept because it is
  the only thing here that is not an assertion about intent):

      play 401856682189   period 1, 0:00    (1-1)*900 + (900-0)   =  900  = 15:00
      play 401856682418   period 3, 15:00   (3-1)*900 + (900-900) = 1800  = 30:00
      play 401856682479   period 3, 10:00   (3-1)*900 + (900-600) = 2100  = 35:00

  period        the period column expression, e.g. `p.period`
  clock_seconds the stg_play clock TOTAL, e.g. `p.clock_seconds`
#}
{% macro elapsed_from_kickoff(period, clock_seconds) %}
    case
        when {{ period }} between 1 and 4
            then ({{ period }} - 1) * 900 + (900 - {{ clock_seconds }})
    end
{% endmacro %}


{#
  The ORDER a curve's plays actually happened in, for a `lag()` or `row_number()` window.

  🚨 cfdb-main-R-916: `stg_game_win_probability.play_number` IS NOT CHRONOLOGICAL. A136 measured
  795 consecutive pairs stepping BACKWARDS on the clock across 336 of 1,898 games (17.7%), worst
  single back-step −3,567 seconds. Game 401635615 carries fourth-quarter plays at `play_number`
  0-3 and a first-quarter play at 4.

  ✅ A138 PROVED THIS ORDERING ON THE CHART BEFORE IT WAS PUT IN A WINDOW — `today.py` draws the
  curve with `order by game_id, elapsed_from_kickoff_seconds nulls last, play_number`.

  ⚠️ `nulls last` IS EXPLICIT DOCUMENTATION, NOT A LOAD-BEARING CLAUSE, AND A140 MEASURED THAT
  RATHER THAN REPEATING IT. A138's comment and A138's report both called it load-bearing; a
  staged break removing it came back GREEN, because **`ORDER BY x` ASCENDING already puts NULLs
  LAST in Postgres** — it is DESC that puts them first, which is R-890's actual shape.

      order by x              ->  1, 2, null
      order by x nulls last   ->  1, 2, null
      order by x nulls first  ->  null, 1, 2      <- this one moves 43 rows
      order by x desc         ->  null, 2, 1

  ✅ IT STAYS ANYWAY, and for a reason rather than out of caution: the clause says out loud that
  the NULLs are overtime and belong at the END, so a later round that flips this to DESC has to
  notice it. **A comment would be ignored; a clause that has to be edited is not.**

  ⚠️ AND `play_number` SURVIVES AS THE TIE-BREAK, which is the one place it is still correct:
  inside an overtime period it is the only order a play has — `stg_play`'s period-5-and-above
  rows take six distinct clock values in total, so there is nothing else to sort on.
#}
{% macro curve_order(period, clock_seconds, play_number) %}
    {{ elapsed_from_kickoff(period, clock_seconds) }} nulls last, {{ play_number }}
{% endmacro %}
