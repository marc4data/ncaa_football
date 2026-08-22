# Claude Code prompt — Model Pack integration

Paste the fenced block whole.

---

```
Read ../claude_work/decision_log.md first. The newest entry (2026-08-19 later, "SHIFT GEARS:
Model Pack acquired") is the governing decision and supersedes any earlier phase label for
fct_prediction. The entry above it ("NORTH STAR set") is the sequencing.

CONTEXT: Marc purchased the CFB Model Training Pack — 2026 Edition and extracted it to
cfdb_model_pack/ in this repo. The .zip is also in the repo root. Integrating its prediction
output into the data tier is now the priority: it is what takes Edge Finder and Model Performance
from blocked to rendering, completing 17 of 17 pages serving real data.

=== TASK 0 — .gitignore, FIRST, before anything else touches git ===

Marc asked for a *.zip pattern. That is NOT sufficient and the licence is why.

cfdb_model_pack/LICENSE is personal, non-commercial, original-purchaser-only. It explicitly
prohibits uploading the pack files to a repository and sharing its contents with non-purchasers.
The extracted notebooks, training_data.csv and guides are the licensed material — the zip is just
the wrapper.

Do:
  - .gitignore the ENTIRE cfdb_model_pack/ directory, plus *.zip, plus model_outputs/.
  - Verify nothing from the pack is already tracked: `git log --all --name-only | grep -i model_pack`
    and `git ls-files | grep -i -E 'model_pack|\.zip'`. If ANY pack file has been committed —
    even once, even on a branch — STOP and tell me before doing anything else. History rewriting
    is a decision for Marc, not a drive-by.
  - Add a short note in README or CLAUDE.md that the pack is licensed, local-only, and must never
    be committed.

The repo is private today, but going public has been discussed in the decision log, and a private
repo carrying licensed data in its history is a landmine that a later .gitignore does not defuse.

=== TASK 1 — the sign convention. Get this right or everything downstream is silently wrong. ===

The pack uses, consistently across dataset, notebooks, exports and leaderboard:

    margin     = away_points - home_points        <-- AWAY MINUS HOME
    negative margin means the HOME team won
    home_cover = True when margin < spread
    spread     negative means the HOME team was favoured

`margin = away - home` is INVERTED from the intuitive convention and from how the site's
Proj/Pred/PTL vocabulary reads. If any model assumes home-minus-away, every cover flag, every edge
and every ATS figure flips sign — and still looks completely plausible.

DECIDED: adopt the pack's convention VERBATIM through raw and staging. Do not flip it in transit.
If a serving view wants a home-perspective margin, derive it there as a separate, explicitly named
column (margin_home_perspective) with a comment. A silent flip mid-pipeline is the worst outcome.

Write a dbt test that pins the convention: on completed games, assert
(margin < 0) == (home_points > away_points). If someone later "fixes" the sign, that test fails.

ALSO: this closes a question open since 2026-08-17 — `spread` means CLOSING SPREAD, NEGATIVE MEANS
HOME FAVOURED, per the pack's own Data Info Sheet. Update dim_field_metadata: move `spread` from
UNKNOWN to DOCUMENTED, citing the pack. Keep the nuance — "closing" applies to completed games in
training_data.csv; the Tier-3 weekly drops are forward-looking, so the sign convention carries but
the word "closing" does not.

=== TASK 2 — fct_prediction, built to the pack's contract ===

cfdb_model_pack/Prediction_Export_Schema_2026.md is a 42-column contract that every notebook
writes to. ADOPT IT ESSENTIALLY VERBATIM. Do not invent a schema — this is a load job, not a
design job, and the contract already carries nearly every column Edge Finder and Model Performance
need (home_win_probability_edge, home_cover_edge, confidence_bucket,
market_implied_home_win_probability, brier_score_component, log_loss_component, margin_error,
absolute_margin_error, home_win_correct, cover_correct).

Grain: game_id × model_name × model_version × split, plus prediction_ts.
The pack's grain is game_id + model_name + split; model_version and prediction_ts are ours, so
in-season re-scoring APPENDS rather than overwrites and Model Performance can never be silently
rewritten by a retrain.

Build:
  - raw landing for model_outputs/*.csv (seven files, named in the schema doc)
  - stg_predictions — typed, sign convention preserved, split preserved
  - fct_prediction — the 42 columns plus our grain additions
  - dim_model_version — model_name, model_family, trained_at, split definition, feature-set
    version. Seven families ship: linear margin, random forest scores, XGBoost WP, fastai WP,
    logistic WP, SHAP XGBoost, stacked ensemble.

Tests: uniqueness on the full grain; not_null on keys; the sign-convention test from Task 1; and a
test that a written (game_id, model_name, model_version, split) row is never mutated.

=== TASK 3 — Week 0–4 honesty, built in from the start ===

Pack coverage: 5,133 games, 86 fields, seasons 2016–2019 and 2021–2025 (2020 excluded),
REGULAR SEASON FROM WEEK 5 ONWARD — because the opponent-adjusted inputs need game history before
they mean anything. Default split: train ≤2023, validate 2024, test 2025.

Consequence: there is NO in-sample analogue for early-season games. Predictions for Weeks 0–4 of
2026 are extrapolation, not inference — and the season opens 2026-08-27.

Carry a flag on fct_prediction (is_out_of_sample_week, or equivalent) set for regular-season weeks
below the pack's training floor. srv_edge_finder must expose it so the page can label those rows
and keep them below the default actionable threshold. Do not let a Week 1 edge render identically
to a Week 8 edge.

=== TASK 4 — serving views, so the pages actually render ===

srv_edge_finder and srv_model_performance, per the north-star set. Plus wire fct_prediction into
srv_matchup, srv_scoreboard, srv_schedule and srv_today_edges as the secondary it already is in
the matrix — those pages render today and get richer, they are not blocked.

=== ATTRIBUTION — a licence requirement, not a nicety ===

The licence prohibits presenting modified models or outputs as official CollegeFootballData.com
predictions. Edge Finder, Model Performance, Matchup and Methodology must attribute clearly:
cfdb's own predictions, built on a licensed training pack, not CFBD's. Put the wording in the
serving layer or the page config so it cannot be forgotten.

=== CONSTRAINTS ===

  - Everything here is NEW OBJECTS THAT NOTHING READS. Per the BUILD NOW entry that is not
    runtime-path work and carries no date constraint. It does not wait for Sep 7.
  - If dbt selectors/tags are not yet protecting the production refresh from a half-finished new
    model, do that first — it is a one-time change that makes all of this safe to build at any time.
  - Do NOT run the notebooks as part of the pipeline in this task. Marc runs them locally per the
    pack instructions; we ingest model_outputs/*.csv. Automating the training loop is a separate
    decision.
  - Show dbt build output and row counts. Do not report success without them.
  - Anything you cannot resolve goes in DECISIONS NEEDED rather than a guess.
```

---

## Why these four tasks, in this order

**.gitignore first** because it is the only irreversible one. A licensed dataset committed even
once lives in history, and the fix at that point is a rewrite rather than an ignore rule. The
check for existing tracked files matters more than the ignore pattern.

**The sign convention second** because `margin = away - home` is the kind of defect that produces
confidently wrong numbers rather than errors. Every cover flag and every ATS figure would flip and
still look reasonable. The pinning test is what stops a well-meaning later "fix".

**The 42-column contract is the reason this moves fast.** It already contains the no-vig column,
the Brier and log-loss components, both edge columns and the confidence bucket — nearly the whole
Edge Finder and Model Performance wireframe. Adopting it verbatim removes a design round-trip.

**And the Week 0–4 limitation is the one to build in now rather than discover in September.** The
pack trains from Week 5 onward because opponent-adjusted inputs need history. The season opens
Aug 27. Without the flag, the first four weeks of edges look exactly as confident as the rest.
