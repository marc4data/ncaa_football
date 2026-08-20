{#
  Assert that a column is populated at least `min_rate` of the time.

  Written because of the logo bug, which is the case no existing test could have caught.
  `dim_team.logo_source_url` was 100% NULL across 34,061 rows and passed every test in the
  project, because nothing asserted it had values. The accessor was wrong (`->>` addresses
  an object key; the source was an array), Postgres answered NULL rather than raising, and
  the monogram fallback rendered so cleanly that the site looked finished.

  Rate, not `not_null`, and the distinction is the whole point. 3.6% of teams legitimately
  have no logo — defunct programs CFBD has no asset for. A `not_null` test on that column
  fails on every run forever, and a test that always fails is a test somebody mutes. Then
  the real regression arrives and nobody sees it. The threshold has to sit below the honest
  floor and above the broken one, and there is a lot of room between 96% and 0%.

  Blank counts as unpopulated. An empty-string URL is exactly as broken as a null one, and
  a string-typed extraction is how a JSON accessor returns "found nothing" in the other
  dialect — `get_json_object` yields NULL, but an upstream coalesce or a cast can turn that
  into ''. Casting to text makes the check work on any type without a per-type branch.

  Args:
    min_rate    fraction in [0, 1]. Set it from measured reality with headroom, not from a
                round number that happens to sit above today's value.
    row_filter  optional SQL predicate, for when the honest rate differs by cohort — the
                site serves 2002+, and coverage there is not coverage across 1897+.

  Returns at most one row, carrying the numbers, so the failure names the actual rate
  instead of a count of offending rows.

  On thresholds and the CI fixture: the fixture's teams are 100% populated, so it proves the
  accessor resolves and the test is wired — not that the tolerance works. The tolerance is
  proven by production, which sits at 96.4% with real gaps and passes nightly. Deriving a
  threshold from a four-row fixture would mean picking it from {0, 25, 50, 75, 100}, which
  is calibration by arithmetic accident rather than by measurement.
#}
{% test populated_rate(model, column_name, min_rate=0.9, row_filter=none) %}

with measured as (
    select
        count(*) as total_rows,
        count(case
                when {{ column_name }} is not null
                 and cast({{ column_name }} as {{ dbt.type_string() }}) <> ''
                then 1
             end) as populated_rows
    from {{ model }}
    {% if row_filter %}where {{ row_filter }}{% endif %}
)
select
    '{{ column_name }}' as tested_column,
    {{ "'" ~ (row_filter | replace("'", "''")) ~ "'" if row_filter else "null" }} as row_filter,
    total_rows,
    populated_rows,
    cast({{ min_rate }} as numeric) as min_rate,
    cast(populated_rows as numeric) / total_rows as actual_rate
from measured
-- An empty relation is a different failure with a different fix, and `count(*) = 0` would
-- otherwise divide by zero. Emptiness is already covered by the freshness signals.
where total_rows > 0
  and cast(populated_rows as numeric) / total_rows < {{ min_rate }}

{% endtest %}
