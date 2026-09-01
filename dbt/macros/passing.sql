{#
  --- The metric set every /passing/* endpoint shares -------------------------------------

  All five passing endpoints report the same thirteen measures. players/season and
  players/games carry them at the top level; teams/season and teams/games nest them under
  `offense` and `defense`. Defining the list once means the five models cannot drift apart
  over a metric, and adding an upstream field is one edit.

  THE `*AttemptsAvailable` COUNTS ARE DENOMINATORS, NOT TOTALS, AND THEY MATTER.
  Measured across the landed 2025-2026 data: air yards are charted for 44.9% OF ATTEMPTS.
  So `averageDepthOfTarget` is an average over slightly under half the passes, not over
  `attempts`, and reading it as a season-wide figure overstates its basis by more than
  double. Every model in this family carries the availability counts beside the averages for
  exactly that reason, and any mart computing a rate from them should divide by the
  availability count rather than by attempts.
#}
{% macro passing_metrics() %}
    {{ return([
        'attempts', 'completions', 'incompletions', 'interceptions', 'completionRate',
        'airYardsAttemptsAvailable', 'totalAirYards', 'averageDepthOfTarget',
        'totalYardsAttemptsAvailable', 'totalYards',
        'yardsAfterCatchAttemptsAvailable', 'totalYardsAfterCatch', 'averageYardsAfterCatch',
    ]) }}
{% endmacro %}
