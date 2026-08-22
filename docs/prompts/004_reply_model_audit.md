# Reply to Claude Code

Paste the fenced block.

---

```
Answer to your question: NEITHER of the two options as framed. Build the four unblockers, not the
fct_team_week_rating slice — and no reconciliation doc is needed, Cowork has already re-phased.

Read ../claude_work/decision_log.md first. The newest entry (2026-08-19, "NORTH STAR set") is the
authoritative sequencing and supersedes the phase labels in any matrix you have seen.

=== THE NORTH STAR, stated once so it stops getting re-derived ===

Real data serving EVERY page of the website, as soon as possible, so the site can be built out and
then iterated on. Not after Sep 7. Now. Model fidelity, phase purity and enrichment are all
subordinate to that. A page that renders thinly is a page we can iterate on; a page that does not
render is not.

=== CORRECTION TO YOUR ANALYSIS: "pages blocked" was counted as pages TOUCHED ===

The matrix distinguishes P (primary — sets the page's grain; the page cannot render without it)
from S (secondary — a column set; the page renders thinner without it). Recomputed on that basis:

  11 of 17 pages RENDER TODAY.
  6 are blocked, each by exactly one missing primary:

    Rankings          <- fct_poll_rank (+ dim_poll)      raw on disk
    Stats             <- fct_team_season_stat            raw on disk
    Data Dictionary   <- dim_field_metadata              dbt schema.yml; input generated 8/18
    System Overview   <- fct_dq_test_result              dbt already writes run_results.json
    Edge Finder       <- fct_prediction (+ dim_model_version)
    Model Performance <- fct_prediction (+ dim_model_version)

fct_team_week_rating is PRIMARY ON ZERO PAGES. It enriches nine and blocks none. It is the biggest
single enrichment in the backlog and it should be built — but it converts no page from broken to
working, so it is not the path. Your ranking optimised the wrong metric.

=== BUILD THIS, IN THIS ORDER ===

  1. fct_poll_rank + dim_poll        -> Rankings renders
  2. fct_team_season_stat            -> Stats renders
  3. dim_field_metadata              -> Data Dictionary renders
  4. fct_dq_test_result              -> System Overview renders
  5. fct_prediction + dim_model_version -> Edge Finder + Model Performance render

Seven tables. 11/17 -> 17/17. None needs a new API call. Marc is obtaining the Model Starter
Package and expects it within a day or two, several days before first games — so item 5 is
scheduled, not deferred. Build 1-4 now; 5 lands when the package does.

For dim_field_metadata: ../claude_work/cfdb_data_dictionary.xlsx is the generated upstream input
(CFBD OpenAPI v5.24.0 — 74 endpoints and 289 parameters fully described, but only 4 of 1,017
FIELDS carry vendor prose, so the field descriptions are ours to author). Descriptions belong in
dbt schema.yml with persist_docs, not maintained separately.

=== THE FREEZE, for the third time ===

Every table above is a NEW OBJECT THAT NOTHING READS. Per the 2026-08-18 BUILD NOW entry that is
not runtime-path work and carries no date constraint. It does not wait for Sep 7 and it does not
wait for Aug 27.

Your instinct that there is risk here is not wrong — you have just been reaching for the wrong
control. The real hazard is that a new model can fail the `dbt build` that ALSO refreshes the live
marts. Fix that structurally, not with a calendar: use dbt selectors or tags so the production
refresh runs an explicit selection and a half-finished new model is incapable of breaking it.
Do that first if it is not already true — it makes everything after it safe to build at any time.

=== DECISIONS YOU ASKED FOR, CLOSED ===

- srv_* as TABLES, confirmed. Views cannot ship through the publish path (pg_dump ships the
  definition, not rows). The "views rather than tables" aside in an earlier log entry was Cowork's
  error, not a real ambiguity. Materialising is also correct on its merits — pay the join cost
  once at build, not per page render.
- dim_season: already built, keep it.
- dim_venue: already built, keep it. Note for the record that its value is lat/lon and elevation
  feeding travel and elevation-delta features (backlog A1, marked V1), not the venue string on
  four pages — it was nearly deferred for the wrong reason.
- is_power_conference: DROP the column. No page in wireframe v0.2 needs it, "power conference" is
  historically unstable, and CFBD has no such flag. Define it season-scoped the day a page needs it.
- tiebreak_rank: accept your simple rule (conf win pct -> overall win pct -> point differential)
  WITH tiebreak_basis labelling it, and add head-to-head as the FIRST tiebreaker — the data is
  already in fct_game and H2H is the near-universal first rule, so omitting it is wrong in the most
  common case (exactly two teams tied).
- Line-snapshot deletion test: take the raw_manifest comparison, not a new audit table. Agreed with
  your lean — fewer moving parts and stg_raw_manifest already exists.
- Box-score column set: your 12 of 35 is fine. Under-selecting is cheap to re-pivot; over-selecting
  adds width forever. Revisit when Stats and Matchup need more.

=== ALSO OPEN, not blocking ===

The Airflow working-tree bind mount has now caused two incidents (the live schedule silently
reverting to @daily during a checkout, and branches being a deployment hazard). "Merge quickly" is
a habit, not a mitigation. Cheapest real fix: bind-mount a separate git worktree pinned to main and
develop in the primary tree. Raise it if you disagree; otherwise queue it.
```
