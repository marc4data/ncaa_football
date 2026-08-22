# Claude Code prompts — cfdb

Three prompts, in order. **A and B are independent — run them as separate sessions, in either order or both today.** C is gated on A finishing.

Paths assume:
- Docs / decisions: `/Users/marcalexander/projects/ai_orchestrator_claude/ncaa_football/claude_work/`
- Code: `/Users/marcalexander/projects/ai_orchestrator_claude/ncaa_football/claude_code/`

---

## Standing context block

Consider pasting this at the top of **every** cfdb Claude Code session. It's also worth folding into `claude_code/CLAUDE.md` so you stop having to paste it.

```
## cfdb — standing context

Division of labour ("church vs state"):
- Strategy, decisions and design docs live in ../claude_work. That folder is the source of
  truth for WHAT to build and WHY. Do not put production code there.
- All code lives in this repo. You implement within decisions already made; you do not
  re-litigate them. If a decision looks wrong, SAY SO and stop — do not quietly do something
  else.

Authoritative documents (read before acting, in ../claude_work):
- CLAUDE.md ................................ project rules
- decision_log.md .......................... settled decisions, newest last
- roadmap.md ............................... phasing
- cfdb_page_to_mart_matrix.xlsx ............ the dimensional model (7 sheets)
- cfdb_wireframe_v02.html .................. the 17 site screens this model serves
- cfdb_site_ia_and_layouts.md .............. IA rationale + CFBD endpoint coverage

Settled decisions you must work within:
- Naming: fct_* / dim_* in the warehouse. Serving layer is pre-joined wide srv_* tables.
- Streamlit is display-only: single-table SELECT + WHERE. No joins, no metric math in the app.
- dbt owns all transforms, metric definitions and tests. Airflow owns reliability only —
  no business logic in DAGs.
- Scope: FBS spine. Non-FBS teams that play an FBS opponent exist as dim_team stubs
  (name, conference, logo, is_fbs = false) with no deep stats.
- Play-by-play scope: 2024, 2025, 2026 only.
- CFBD API keys are server-side only, never client-side, never committed.

IMPORTANT — how much to trust the matrix:
cfdb_page_to_mart_matrix.xlsx is a PROPOSAL. It was written from three object names
(mart_data_freshness, mart_team_schedule, mart_team_season_record) with no schema inspected,
and from CFBD's public docs with no live API calls. Rows marked ASSUMED or PARTIAL are
inferences. Verify before you build on them, and report anything that contradicts the doc
rather than silently conforming to it.
```

---

## PROMPT A — Reconciliation audit (read-only, do this first)

```
Read the standing context block above first.

TASK: Reconcile the proposed dimensional model against what actually exists in this repo.
This is a READ-ONLY audit. Do not create, rename, drop or modify any model, table, DAG or
config. The deliverable is a report.

Step 1 — Discover. Inventory this repo without assuming anything about its state:
  - Is there a dbt project? Where is dbt_project.yml, what are the model paths, what
    materializations and schemas are configured?
  - What models exist? List every .sql model with its layer (staging/intermediate/mart).
  - Is Airflow present? What DAGs exist and what do they do?
  - Is there a Docker Compose stack? What services?
  - Where does data land today — Databricks, Postgres, both, neither?
  - What tests exist (dbt tests, schema.yml coverage)?
  - Are there notebooks or scripts doing transforms outside dbt?
  Report what you find plainly, including "none" where that is the answer.

Step 2 — Read the model proposal. Open ../claude_work/cfdb_page_to_mart_matrix.xlsx
(use openpyxl or pandas; it has 7 sheets). The Dimensions and Facts sheets list 32 proposed
tables with grain, source endpoints, status and design notes. The Gaps_Risks sheet lists 14
known issues.

Step 3 — Reconcile. For each of the 32 proposed tables, determine:
  - Does something equivalent exist? Under what name?
  - If yes: does its actual GRAIN match the proposed grain? This matters more than the name.
    Report the real grain, verified from the SQL — not guessed from the model name.
  - What columns does it actually have vs what the proposal assumes?
  - Does it have tests? Which?
Specifically resolve the three tables the proposal marks LIVE or PARTIAL
(mart_team_season_record, mart_team_schedule, mart_data_freshness) and the two marked ASSUMED
(dim_team, dim_conference) — those five are pure inference right now.

Step 4 — Report. Write ../claude_work/cfdb_model_reconciliation.md containing:
  a) Repo inventory from Step 1.
  b) A table: proposed table | exists? | actual name | actual grain | grain matches? | notes
  c) DELTAS — every place the proposal is wrong about reality. Be specific and blunt. If the
     proposal invented a table that duplicates something already built, say so. If an existing
     model has a different grain than proposed, that is the most important finding in the
     report and should be at the top.
  d) DECISIONS NEEDED — anything you cannot resolve without Marc. Do not guess.
  e) A recommended revision to the Phase 1 build list based on what actually exists.

Constraints:
  - Read-only. No writes anywhere except that one report file.
  - Do not run dbt build / run / seed. `dbt parse`, `dbt ls`, `dbt compile` and reading
    manifest.json are fine.
  - Where you are uncertain, write "unverified" rather than a confident guess. An honest
    unknown is more useful to me than a plausible wrong answer.
```

---

## PROMPT B — Line snapshot DAG (time-critical, independent of A)

```
Read the standing context block above first.

CONTEXT — why this is urgent: CFBD's /lines endpoint returns only the opening line and the
current line, with no timestamps in between. Line movement history therefore CANNOT be
backfilled. Every 4-hour window not captured is gone permanently, and Closing Line Value —
the fastest honest read on whether a prediction model has real edge — is uncomputable without
it. No page consumes this data until Phase 5. Build it anyway, now.

TASK: Stand up a 4-hourly snapshot pipeline for CFBD betting lines.

Step 1 — Discover. Inventory what exists before building: is Airflow present and running, is
there a Docker Compose stack, is there a dbt project, where does raw data land today, and how
are secrets currently handled? If Airflow is not stood up, say so and propose the smallest
thing that reliably runs every 4 hours — do not silently build a large orchestration layer I
did not ask for.

Step 2 — Verify two facts against the live API (I have an elevated-tier key; ask me for it or
tell me which env var to set). Both are currently UNVERIFIED in our design docs:
  a) What providers does /lines actually return? Documented downstream as consensus / Caesars /
     numberfire / teamrankings, but that list is stale. The fact's grain depends on the answer.
  b) Is /games/weather accessible on my tier? It has historically been Patreon-gated.
  Report both answers. They close two open items in Gaps_Risks.

Step 3 — Build the snapshot.
  Grain: one row per game x provider x snapshot_ts.
  Capture on every poll, including when nothing changed — "the line did not move" is itself
  information for CLV analysis, and the volume is trivial (~60 games x a few providers x 6
  polls/day).
  Store at minimum: game_id, provider, spread, spread_open, formatted_spread, over_under,
  over_under_open, home_moneyline, away_moneyline, snapshot_ts, ingested_at.
  Keep formatted_spread AND spread as separate columns — they are known to disagree in
  historical data and we do not yet know which is authoritative. Do not reconcile them; store
  both and let downstream choose.
  Append-only. Never update or delete a prior snapshot.
  Idempotent: re-running the same interval must not create duplicates.
  Schedule every 4 hours. Season-aware if that is cheap; do not over-engineer it.

Step 4 — Test it. dbt tests on the landed table: uniqueness on the grain, not_null on
game_id / provider / snapshot_ts, and a freshness check. Add schema.yml descriptions for
every column as you go — we are building a generated data dictionary and retro-documenting
later is miserable.

Step 5 — Prove it works. Run it at least twice and show me: row counts after each run, that
the second run did not duplicate the first, and a sample of rows. Do not tell me it works
without showing the output.

Constraints:
  - API key server-side only, via env var or .env. Never hardcoded, never committed. Add to
    .gitignore if not already.
  - No business logic in the DAG — land the data, let dbt transform it.
  - If you hit something that contradicts the design docs, stop and tell me rather than
    working around it.
```

---

## PROMPT C — Phase 1 build (only after A is done and I've reviewed it)

```
Read the standing context block above first, then read
../claude_work/cfdb_model_reconciliation.md — the audit from the previous session. Its
findings override the matrix wherever they disagree.

TASK: Build the Phase 1 tables per the revised list in the reconciliation report.

Baseline P1 scope from the matrix (12 tables — expect the audit to have changed this):
  dims:  dim_team, dim_conference, dim_venue, dim_season, dim_week, dim_provider,
         dim_field_metadata
  facts: fct_game, fct_team_record, fct_betting_line (built in session B),
         fct_pipeline_run, fct_dq_test_result

Sequence:
  1. Renames first, while cheap: mart_team_season_record -> fct_team_record,
     mart_team_schedule -> fct_game (schedule slice), mart_data_freshness ->
     fct_pipeline_run. Confirm against the audit that these mappings are actually correct
     before renaming anything. If the audit says a grain differs, raise it — do not force
     the rename.
  2. Then dimensions, then facts.

Design requirements that are not negotiable:
  - dim_team is SCD2 on conference. A single current-conference column makes every historical
    standing and conference filter wrong for prior seasons. Use /conferences/affiliations and
    /conferences/changes.
  - dim_week keys on season_type. PostSeason Week 1 is NOT Regular Season Week 1.
  - dim_team carries logos[], color, alternate_color, mascot, abbreviation, is_fbs. Cache
    logo images rather than hotlinking the third-party CDN.
  - Non-FBS opponents get stub rows (is_fbs = false), no deep stats.
  - fct_team_record: CFBD has NO standings endpoint. Conference ordering and tiebreakers are
    our own logic. Put a tiebreak_rank column in the model, test it, and make sure whatever
    consumes it can label it as cfdb logic rather than official.
  - dim_field_metadata is generated from dbt schema.yml with persist_docs — never
    hand-maintained. It feeds both the website page and the Excel export, so they cannot
    drift. Include a per-field status so fields whose meaning is unconfirmed (e.g. `spread`
    in the CFBD weekly training CSVs) are marked unknown rather than given a plausible guess.
  - fct_dq_test_result must be able to represent the three issues we already know about:
    spread source disagreement, null talent values (zero is missing, not zero — Air Force),
    and a garbled team-name encoding artifact.

Every model needs: a schema.yml entry with a description for every column, a uniqueness test
on its declared grain, and not_null on its keys. A model without those is not done.

Show me `dbt build` output and row counts. Do not report success without it.
```

---

## Notes on using these

- **A and B in parallel is fine** — different files, no overlap. B is the one with a clock on it.
- **Read A's report before running C.** The whole point of the audit is that C's scope may be wrong.
- When Claude Code reports a delta that contradicts a decision, bring it back to the Cowork session rather than deciding in the code repo — that's the boundary working as intended.
- Prompt C deliberately does *not* include the renames as a fait accompli. If the audit shows `mart_team_schedule` has a different grain than `fct_game`, forcing the rename would bury the problem.
