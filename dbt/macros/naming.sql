{#
  --- camelCase wire key -> snake_case column name --------------------------------------

  CFBD ships camelCase; the warehouse is snake_case. The advanced stats models need sixty of
  these each, split symmetrically between an `offense` and a `defense` object with identical
  inner shapes.

  Deriving the column name from the wire key rather than writing both out is the point. A
  hand-written version of those models is a hundred and twenty near-identical lines, and the
  failure it invites is not a typo — a typo does not compile. It is `defense_ppa` reading
  `offense.ppa`, which compiles, runs, tests green, and is wrong in a way no null check finds.
  Deriving both sides from one list makes that error unrepresentable.

  totalPPA -> total_ppa, dbHavocEvents -> db_havoc_events, ppa -> ppa.

  `modules.re` is dbt's exposed Python re; consecutive capitals stay together, which is why
  PPA becomes one word rather than p_p_a.
#}
{% macro snake_case(name) -%}
    {{- modules.re.sub('([a-z0-9])([A-Z])', '\\1_\\2', name) | lower -}}
{%- endmacro %}
