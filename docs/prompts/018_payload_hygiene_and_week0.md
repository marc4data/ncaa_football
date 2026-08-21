# cfdb prompt 018 — two sweeps the ratings work implies, and a Week-0 walkthrough

Both sweeps are cheap and neither blocks the two items you already have queued.

---

```
The name was mine and it asserted a grain no source could supply. fct_team_week_rating went into the
requirements a week ago because "ratings change weekly" sounded obviously true, and I never checked
whether anything was fetched that way. Elo being weekly-CAPABLE but only ever fetched by year is
exactly the distinction I would have missed. fct_team_rating with rating_scope is right, and making
a weekly Elo backfill additive rather than a redefinition is the part that matters.

But the two catches in the payload work generalise well past ratings, and both are worth a sweep.

=== SWEEP 1 — AGGREGATE ROWS MIXED INTO MEMBER PAYLOADS ===

SP+ publishing a nationalAverages row inside a team-shaped response is a class, not an incident:
AN API PAYLOAD CAN CONTAIN SUMMARY ROWS THAT ARE NOT MEMBERS OF THE GRAIN.

Your description of the damage is the reason it deserves a sweep rather than a fix — it would have
landed on the Teams index, earned a team page, and sat in the percentile denominator, "shifting
every team's standing by an amount nobody would trace back." Silent, plausible, and it contaminates
a denominator rather than a value, so every number moves a little and none of them looks wrong.

Check the other 64 raw tables for the same shape. The candidates are anywhere CFBD might have
included a total, an average or an "all" bucket alongside the members — ratings, stats, drives,
recruiting aggregates. Grep the landed payloads for rows whose identity field is not a team, a game
or a player.

Where you find one, exclude it the way you did here — with the CI fixture carrying the poison row so
the EXCLUSION runs on every build, not just the fix. That is the fourth time you have proven
something by keeping the failure case alive rather than deleting it.

=== SWEEP 2 — THIS ONE I'D DO FIRST, BECAUSE IT APPLIES TO ALMOST EVERYTHING ===

834 SP+ rows for 138 teams. "Six copies average out to a plausible number while every count is six
times too big" is the sharpest sentence in this report, and here is why it generalises:

  A duplicate-fanout defect passes every MEAN-based check and fails only COUNT-based ones. Averages,
  percentiles and rankings all come out approximately right. Nobody looks at counts. So it survives
  review, survives eyeballing, and shows up as a rank that is subtly wrong six months later.

And the exposure is not specific to ratings — it is structural. THE REVISIONIST CADENCE MEANS THE
RAW LAYER HOLDS MULTIPLE RESPONSES FOR THE SAME ENTITY BY DESIGN. Lines are re-fetched 4-hourly.
Rankings, results and pregame all re-fetch weekly. Every fact built on top of any of those has the
same exposure, and only the ones you happened to check are proven clean.

THE SWEEP: a uniqueness test on the NATURAL KEY of every fact, not just the surrogate.

  fct_game                unique on game_id
  fct_game_team           unique on (game_id, team_id)
  fct_team_record         unique on (season, team_id)
  fct_team_season_stat    unique on (season, team_id, stat_name)
  fct_poll_rank           unique on (season, season_type, week, poll, team_id)
  fct_betting_line        unique on (game_id, provider_key, snapshot_ts)
  fct_team_rating         unique on (season, team_id, rating_system)
  fct_prediction          unique on (game_id, model_name, model_version)

A surrogate key built by hashing the natural key is unique BY CONSTRUCTION and proves nothing — if
the hash includes the fetch timestamp, six copies produce six distinct sks and the table looks fine.
The test has to name the business key.

My expectation is that most already pass and this is twenty minutes of confirmation. That is the
right outcome: the point is that "we checked" replaces "it looked fine." One of them failing would
be worth far more than the twenty minutes.

=== IS_PROJECTION IS BETTER THAN A LABEL, AND IT HAS A SECOND JOB ===

SP+ 139 · FPI 138 · Elo 0 · SRS 0 · PPA 0 is the whole weeks-1-4 story in one line: the only ratings
that exist before a game is played are the two that are forecasts. Deriving is_projection from
whether the team has a completed game rather than keeping a list of which systems are predictive is
the fourth instance of ask-the-data.

The second job, which the Team page should use deliberately: THE RATINGS BLOCK CHANGES CHARACTER
MID-SEASON. In week 0 everything on it is a forecast. Around week 5, SP+ and FPI become
results-informed AND Elo, SRS and PPA appear for the first time. A user who looks at Alabama in
August and again in October sees a different set of numbers with different meanings.

is_projection is what makes that legible instead of confusing — it explains why a number moved a
lot, and why new rows appeared. Worth rendering as a visible state on the block, not a footnote.

ONE THING TO WATCH WHEN THE OTHERS APPEAR: percentile denominators. Today SP+ percentiles are over
139 teams. When Elo arrives mid-season it may cover a different set, and a percentile computed over
a shifting denominator is AC-G.33 again — the rank must carry the n it was computed against, per
rating system, not a single site-wide team count.

=== YOUR TWO QUEUED ITEMS ARE THE RIGHT NEXT TWO ===

Skipped-test reporting, then sync_freshness. Both are the same idea as everything else this week:
make an absence visible. Then Standings carries the rating columns.

=== AND ONE FOR MARC, NOT YOU ===

Nobody has walked the site as a USER yet. Every check so far has been a page query, a row count or a
test — all correct, none of them the experience. Six days out, an hour of clicking through it on the
device he would actually use is likely to surface things no assertion will: a filter that resets, a
link that goes somewhere odd, a table that needs horizontal scrolling on a laptop, copy that reads
wrong.

That is his to do, not yours. I have flagged it.
```

---

## The one I'd do first

**Sweep 2.** Not because it's likely to find something — most of those facts probably pass — but
because of the failure signature. A duplicate fanout passes every mean-based check and fails only
count-based ones, and nobody looks at counts. It's the defect most likely to survive all the way to
someone quoting a wrong rank.

And the exposure is structural rather than incidental: the revisionist cadence means the raw layer
holds multiple responses for the same entity **by design**, so every fact built on a re-fetched
endpoint has it. Only the ones Code happened to check are proven clean.

Twenty minutes to turn "it looked fine" into "we asserted it."
