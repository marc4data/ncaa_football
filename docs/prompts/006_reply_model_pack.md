# Reply to Claude Code — Model Pack round 1

```
Read the newest entry in ../claude_work/decision_log.md (2026-08-19 evening) — it answers your
decision and lifts the postgres_only tag.

VERDICT ON THE LICENCE: predictions may be built on BOTH engines. Lift postgres_only and restore
srv_schedule's prediction columns.

Reasoning, so you can apply the same test to future cases:
  1. The licensed dataset is never uploaded to either engine — training_data.csv is not loaded
     anywhere, only model_outputs/. This was never a question about the pack; it is a question
     about derived output.
  2. Derived output is explicitly permitted: "Use the data, notebooks, and generated outputs for
     personal analysis, academic research, or private projects."
  3. The 42-column export is NOT a substantial portion of the dataset. It carries game identity,
     actuals, spread and model output. NONE of the pack's 86 training features appear in it — no
     adjusted EPA, no Elo, no talent. It cannot reconstruct the dataset.
  4. The prohibition is on uploading PACK FILES to a notebook platform. Predictions are not pack
     files, and the workspace is single-user Databricks Free Edition — private, not shared.

The architectural cost was the tiebreaker. Having to write srv_schedule's prediction columns and
revert them is exactly the signal that the cautious reading was wrong: keeping predictions
Postgres-only creates a permanent class of serving views that cannot build uniformly, and puts a
hole in the checksum-verified dual-engine parity.

Unchanged: the pack stays out of git and off both engines. Your choice to carry attribution as
DATA in dim_model_version and srv_model_performance — so a page cannot render the numbers without
it — is better than the page-config approach Cowork proposed, and is adopted as the pattern.

=== WHAT TO DO NEXT ===

1. Lift postgres_only; restore srv_schedule's prediction columns; verify both engines build and
   the checksum parity still holds.

2. Build srv_matchup and srv_today_edges. They are the last two serving views standing between
   the prediction data and the pages that consume it, and both underlying pages already render —
   this is enrichment, not unblocking, but it is cheap now that fct_prediction exists.

3. The Airflow worktree pin. Two incidents, still open, and we are 8 days from kickoff. A git
   checkout should not be able to change production scheduling. Bind-mount a separate worktree
   pinned to main and develop in the primary tree.

=== NOTED, NO ACTION ===

Your sign-convention verification was the right shape — checking the 74.4% / 31.4% home win rate
split by spread sign is a SEMANTIC check that would catch a convention which was arithmetically
self-consistent but backwards. Arithmetic alone would not have. Same for proving the tests detect
by flipping a row. Keep doing both.

model_version as the export's SHA-256 prefix is clean — idempotent reload and append-only
re-scoring fall out of it for free.

Confirming Task 3 from the data rather than the doc ("no regular-season row before week 5; the
week-1 rows are postseason") is exactly the season_type trap we recorded earlier, caught in the
wild.

=== THE CRITICAL PATH IS NOW MARC'S ===

model_outputs/ does not exist — so nothing is validated against real model output yet, only
against the synthetic export and the CI fixture. That was the right way to build it. It also means
no further design work stands between here and Edge Finder + Model Performance rendering: Marc
runs the notebooks, then python -m src.load_predictions.

If there is anything about that handoff you would make easier — a make target, a validation
command that reports contract conformance before load, a dry-run mode — say so now rather than
after the first real run.
```
