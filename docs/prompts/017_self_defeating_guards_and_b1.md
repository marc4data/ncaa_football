# cfdb prompt 017 — the self-defeating guard, and B1

Read after the Standings merge. Nothing here blocks B1.

---

```
Today's revert is the fourth instance, and it has a shape the other three did not.

=== A GUARD SCOPED BY THE THING IT GUARDS CANNOT GUARD IT ===

Your sentence is the finding: "the divergence was created by a run that structurally could not
detect it."

Unpack why, because this generalises past dbt:

  The parity test is a dbt test. dbt tests run only for SELECTED models. srv_standings was not in
  the six-model selection. So the test did not fail — IT DID NOT RUN. And nothing distinguishes
  "passed" from "was never asked" in a green run summary.

  Narrowing the selector therefore narrowed the guard, silently and in the same motion.

THE RULE: a guard must not be scoped by the mechanism it checks.

A parity test selected by the production selector cannot protect against a bad production selector.
A freshness check that only runs when the pipeline runs cannot detect a pipeline that stopped. A
test that lives inside the thing it tests inherits that thing's failure modes — including "did not
happen."

You already built the correct answer before this fired: check_production_selector.py runs in CI,
against the manifest, OUTSIDE the dbt selection. That is what makes it a guard rather than a
participant. Worth stating explicitly in its docstring, because the next person to look at it will
wonder why it is not just a dbt test — and the answer is that a dbt test is exactly what it cannot
be.

One extension worth considering, cheap: have the run summary report tests SKIPPED as well as passed
and failed. A green summary that silently omits what it never asked is the same ambiguity as the
missing conference segment and the `->> '0'` null — an absence that renders as success.

Four instances now, and they share one sentence: EVERY ONE CHECKED THAT SOMETHING RAN AND NEVER
THAT IT PRODUCED ANYTHING — or in today's case, never that it was even asked.

=== BOTH SIDES CORRECT BEATS EXPECTED DIVERGENCE ===

You fixed mart_team_season_record in step rather than recording a divergence. That is better than
the amendment I wrote, and worth saying so: an expected divergence is a permanent explanation you
have to keep re-reading. Two correct sides need no explanation at all. Record divergences only when
the old side is genuinely being retired and fixing it would be wasted work.

=== THE ATS 0-0 -> NULL CASE IS THE THIRD STATE AT A FINER GRAIN ===

"A team that was an underdog in all eleven games was never a favourite, and 0-0 claims a record it
never had." That is AC-G.32's not-applicable state, found 34 times in a place neither of us was
looking.

And proving the move faithful across 22,993 team-seasons BEFORE repointing is the right way to move
a definition — the 34 differences being explainable is what makes it a move rather than a rewrite.
Make that the pattern for any future definition relocation: prove identity first, then explain every
difference, then repoint.

=== ASK THE DATA, DON'T ENCODE THE RULE — that's three ===

The scores DAG gating on whether a game actually kicked off, by asking the schedule rather than
encoding which days football is played, is the third instance of one good habit:

  dim_season.is_current       the site's default season
  training_week_floor = 5     when predictions begin
  "did a game kick off?"      when to refresh scores

All three replace a constant someone would have to remember to change. Make it the default question
for any new rule: is this knowable from the data we already have?

And "fails open in season — two wasted requests cost less than a stale scoreboard when Postgres
blips on a Saturday" is the right way to choose a fail direction: by cost asymmetry, stated. Keep
the reasoning in the docstring, not just the behaviour, so nobody "fixes" it later.

=== ONE THING ABOUT THE DATABRICKS SYNC, AND THEN LEAVE IT ===

Agreed: analytics tier, not user-facing, not worth chasing six days out.

But dual-engine checksum parity is one of the better engineering stories in this project, and if the
sync stays broken, that claim quietly becomes historical. A stale parity proof reads exactly like a
live one.

Cheap fix, no chasing required: add a `sync_freshness` signal to srv_system_health alongside the
other five. Then "we have dual-engine parity" is a statement with a timestamp on it. Whether to
actually repair the free-tier sync is a post-Week-0 decision for Marc, and possibly a "is dual-engine
still worth it" decision rather than a fix.

=== B1 — one thing to check before you build the grain ===

fct_team_week_rating. The name asserts week grain. Verify that is true of the SOURCES before
committing to it:

  /ratings/elo        takes a week parameter -- genuinely weekly
  /ratings/sp         year and team -- I believe season-level
  /ratings/srs        year and team -- I believe season-level
  /ppa/teams          year and week -- I believe weekly

I am not certain of those and you can settle it from the landed raw files in minutes. It matters
because the TEAM PAGE TRENDS TAB depends on it: if only Elo and PPA have weekly history, then Trends
is an Elo/PPA time series with SP+ and SRS as season markers, not a four-line chart. Better to know
that before building than to discover it when the chart has two flat lines.

If the sources are mixed, carry a `rating_scope` column (`season` | `week`) rather than
forward-filling a season value across weeks. A season-final SP+ repeated across fourteen weeks is a
fabricated time series -- the same class as ats_record_display showing 0-0-0, and it would look
completely convincing.

Everything else about B1 is settled: build from CFBD's landed ratings endpoints, never from the
pack's training_data.csv. It de-partials Team page (Ratings, Trends), Matchup and the team profile
percentiles, and in weeks 1-4 with no model to show, it is the most informative content the site
carries.
```

---

## The one I'd underline for Marc

Four "green and useless" findings in five days, and today's is the sharpest: **the guard didn't fail,
it wasn't asked.** A dbt test only runs for selected models, so narrowing the selector narrowed the
guard in the same motion — and nothing in a green run distinguishes "passed" from "never ran."

The general rule is worth more than the fix: **a guard must not be scoped by the mechanism it
checks.** Code had already built the right answer — `check_production_selector.py` runs in CI against
the manifest, outside dbt's selection — but it's worth being explicit about *why* it can't be a dbt
test, because that's exactly what someone will try to turn it into later.
