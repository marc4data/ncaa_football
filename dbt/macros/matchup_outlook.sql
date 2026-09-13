{#
  R-722. How hard is this matchup for one team's offense, as a three-way classification.

  ONE MACRO RATHER THAN THREE COPIES, AND THAT IS THE POINT. The rule is Marc's and it applies
  identically to rushing, passing and total; written out three times it is three places for the
  0.2 to drift apart, and the threshold is the number he is most likely to move. `staging_grains`
  and `serving_models` are the same argument one layer over: a rule that repeats is a rule that
  disagrees with itself eventually.

  🚨 THE BRANCH ORDER IS LOAD-BEARING, NOT COSMETIC. `challenging` is a strict subset of
  `contested` — every game satisfying the ratio also satisfies `Gained > Allowed` — so evaluating
  `contested` first would make `challenging` unreachable and the column would silently lose a
  whole value. `assert_matchup_outlook_is_exhaustive_and_exclusive` is what makes that checkable
  rather than reviewable.

  ⚠️ THE ARGUMENTS ARE COLUMN EXPRESSIONS, INTERPOLATED — so this macro is for MODEL code with
  trusted literals and never for anything a reader supplies.

  gained  : this team's own per-game production
  allowed : what the opponent's defense has been conceding per game
#}
{% macro matchup_outlook(gained, allowed) %}
    case
        when {{ gained }} is null or {{ allowed }} is null then null
        when {{ gained }} < {{ allowed }} then 'favorable'
        when {{ gained }} > {{ allowed }}
             and ({{ gained }} - {{ allowed }}) / {{ gained }} > 0.2 then 'challenging'
        else 'contested'
    end
{% endmacro %}
