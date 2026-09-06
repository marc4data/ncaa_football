<!--
THE PROJECT'S SHARED COLUMN DEFINITIONS. Reference them with {{ doc('<name>') }}.

WHY THIS FILE EXISTS. Before it, the project had no doc blocks at all — 972 description lines
in dbt/models/serving/_models.yml and not one of them shared. The cost is measurable and it
compounds: `season` is documented on TWENTY tables in FOURTEEN different wordings, `as_of_ts`
on twenty-four in eleven, `week` on thirteen in seven. persist_docs pushes every one of those
wordings into the database, and srv_data_dictionary reads them straight back out — so the
site's Data Dictionary page shows the same column explained fourteen different ways.

Every new model repeats the same five fields and adds five more rows to that debt. This file
is the mechanism that stops the count growing; paying down the 57 existing copies is a
separate change, because it rewrites text currently published on the site.

WHERE IT LIVES, AND WHY HERE. At the models/ root rather than under serving/, because
`season`, `season_type`, `week` and `as_of_ts` are used from marts/ as well, and the
conversion PR will reference them from both. A file under serving/ would make that PR start
by moving this one. dbt resolves doc() by BLOCK NAME across the whole project regardless of
which file or directory defines it, so the location is a question of tidiness, not
reachability — verified by `dbt parse` with the blocks referenced from models/serving/.

THE TEXT IS THE CONTRACT. These wordings carry decisions that were expensive to reach — read
`span` and `bin_count` before editing either. Change one here and it changes everywhere,
which is the point and also the risk.
-->


{% docs season %}
Playing season, identified by the calendar year the season begins in.
{% enddocs %}

{% docs season_type %}
Segment of the season — `regular`, `postseason`. ⚠️ Week numbers restart per season type, so `week` is only unique within (season, season_type).
{% enddocs %}

{% docs week %}
Week number within the season and season type. ⚠️ Not unique on its own — always read with `season` and `season_type`.
{% enddocs %}

{% docs span %}
Which games the figures cover: `week` is that week's own games; `season_to_date` is every STRICTLY EARLIER week in the same season and season type, so the reference figure never contains the thing being referenced. ⚠️ Week 1 therefore has no season-to-date row at all — an Empty state, not a zero. Named `span` because `window` is reserved in Postgres and `period` means quarters here.
{% enddocs %}

{% docs metric %}
Which measured quantity the distribution describes. One row per metric per week per span per day.
{% enddocs %}

{% docs as_of_date %}
The day this row's figures were computed for. One row per day, immutable once the week locks, so the history answers “how did this move as kickoff approached” — a recomputed-on-read view never can.
{% enddocs %}

{% docs as_of_ts %}
When the data behind this row was last successfully loaded, per its domain in `mart_as_of`. The “data as of” a page shows (AC-G.35) — sourced from this column, never from `now()` in the app.
{% enddocs %}

{% docs bin_min %}
Lower edge of the histogram's range for this metric. Configured per metric, NOT derived from the week's data, so the picture is comparable week to week. Values below it are counted in `below_min_count`, never clipped.
{% enddocs %}

{% docs bin_max %}
Upper edge of the histogram's range for this metric. Configured, not derived; values above it are counted in `above_max_count`, never clipped.
{% enddocs %}

{% docs bin_incr %}
Width of one bin — `(bin_max - bin_min) / bin_count`. Carried on the row so the picture is reproducible from the row alone.
{% enddocs %}

{% docs bin_count %}
Number of bins. ⚠️ Measured (R-197) and free to change, which is why the counts travel as a delimited string rather than fixed `bin_01..bin_10` columns.
{% enddocs %}
