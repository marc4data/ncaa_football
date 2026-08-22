{#
  The measure list for srv_model_performance, written once.

  srv_model_performance aggregates the same eleven measures at five different cuts —
  overall, by week, by conference, by confidence bucket, and by predicted-probability decile
  for calibration. Repeating the list five times would mean five places to edit and four
  places to get it subtly wrong, and the failure would be invisible: a segment whose Brier
  score was averaged slightly differently still renders as a number.

  Not a model of its own, because it is a fragment of a select list rather than a relation.
  Not dispatched either — every function used here is standard SQL on both engines.

  Two things worth reading twice:

    count(x) vs sum(case when x)   `count(home_win_correct)` counts NON-NULL rows, which is
                                   the denominator, while the sum counts TRUE ones, which is
                                   the numerator. A push is blank in the prediction contract
                                   and must be excluded from cover accuracy rather than
                                   counted as a miss — those are different claims about a
                                   model and only one of them is true.

    actual_home_wins               counted here rather than derived on the page, so
                                   calibration reads the realised rate from the same
                                   denominator as the accuracy figure beside it.
#}
{% macro prediction_measures() -%}
    count(*)                                              as games,
    avg(absolute_margin_error)                            as mae,
    avg(margin_error)                                     as mean_margin_error,
    avg(brier_score_component)                            as brier_score,
    avg(log_loss_component)                               as log_loss,
    sum(case when home_win_correct then 1 else 0 end)     as winner_correct,
    count(home_win_correct)                               as winner_scored,
    sum(case when cover_correct then 1 else 0 end)        as cover_correct_count,
    count(cover_correct)                                  as cover_scored,
    avg(predicted_home_win_probability)                   as mean_predicted_probability,
    sum(case when actual_home_win then 1 else 0 end)      as actual_home_wins
{%- endmacro %}
