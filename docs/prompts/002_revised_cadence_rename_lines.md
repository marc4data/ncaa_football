# Claude Code prompts — revised after the reconciliation audit

**Supersedes Prompt B in `cfdb_claude_code_prompts.md`.** That prompt assumed the line-snapshot
DAG did not exist. It does — live since 2026-08-15 at `@daily`.

## Sequencing and why

| | Prompt | Window | Risk | Why this order |
|---|---|---|---|---|
| **B1** | Lines cadence gate + load step | **Before Aug 20** | Low | Irreversible data loss accrues daily. Smallest change, highest urgency, done alone so nothing else can delay it. |
| **B2** | `fct_*` / `dim_*` rename | Before Aug 27 | **High** | Breaking change to a running site. Only after B1 is verified. |
| **B3** | `stg_lines` → `fct_betting_line` | Any time | Low | Not on the runtime path. Can follow the season start. |

**The date that actually binds is Aug 20, not Aug 27.** Your rule is "daily until 7 days before
the first game," the season starts Aug 27, so the switch is **Aug 20 — three days out**. The gate
must be in place before then or the first week of the switch is missed.

**On doing the rename before Aug 27:** I recommended after Sep 7 and you chose before Aug 27 —
your call, and the argument for it (3 tables now versus 30 later) is sound. Two mitigations worth
taking: land it **early in the window with days of buffer**, not on the 26th, and make it a
**single atomic commit** with the publish job updated in the same change. A rename that half-lands
during game week is the bad outcome.

---

## PROMPT B1 — Lines cadence gate (do this first, before Aug 20)

```
Read ../claude_work/cfdb_model_reconciliation.md first — your own audit from the previous
session. It is the source of truth about this repo, not the matrix workbook.

CONTEXT: cfbd_lines_snapshot has been live since 2026-08-15 at @daily. CFBD's /lines returns
only the opening and current line with no timestamps between, so intraday movement CANNOT be
backfilled. At @daily we capture one point per day and permanently lose the rest. Closing Line
Value — the fastest honest read on whether a prediction model has real edge — depends on this
history existing.

DECISION MADE (Marc, 2026-08-17): the cadence is CONFIGURABLE and season-aware.
  - Daily outside the active season window.
  - Every 4 hours from 7 days before the season's first game.
  - Season starts 2026-08-27, so the switch date is 2026-08-20 — THREE DAYS FROM NOW.

TASK 1 — Implement the cadence gate.

Design constraint: do NOT implement this by editing the schedule seasonally. A schedule that has
to be changed twice a year is a runtime-path edit twice a year, and it will eventually be
forgotten. Instead:
  - Schedule the DAG permanently at the FINEST cadence: 0 */4 * * * (UTC).
  - Gate execution with a short-circuit at the top of the DAG. Inside the active window every
    run proceeds; outside it, only the 00:00 UTC run proceeds. Net effect is daily off-season,
    4-hourly in-season, with no schedule change ever again.

Requirements:
  - The decision must be a PURE FUNCTION, unit-testable without Airflow. Something like
    should_snapshot(now_utc, config) -> bool. Write tests for it: inside window, outside window
    at 00:00, outside window at 04:00, and the boundary day itself.
  - Config must be external to the code — an Airflow Variable, or a small config file. Not a
    literal buried in the DAG. Include: season first-game date, lead_days (7), and a season END
    date.
  - SEASON END MATTERS AND I HAVE NOT SPECIFIED IT. Without an end date the DAG polls 4-hourly
    through February for games that do not exist. Propose a sensible end (national championship
    plus a small buffer) and tell me what you chose — do not silently omit it.
  - LOG THE DECISION ON EVERY RUN, including skips. A short-circuit that skips silently is
    indistinguishable from a broken DAG when you look at it in March. The log line should say
    which branch it took and why.
  - Consider deriving the first-game date from data already in the warehouse rather than
    hardcoding it annually. If that adds a database dependency to what is currently a pure fetch
    DAG, say so and recommend against it — a fetch DAG that can fail because Postgres is down is
    worse than one config value updated each August.

TASK 2 — Load on the snapshot run.

Your audit found the lines DAG fetches but does not load; loading happens only in the weekly
DAGs, so the warehouse can lag the files on disk by up to a week. The raw files are the durable
history, so nothing is lost — but anything built on fct_betting_line would be stale.

Add the load step to the snapshot DAG. Keep it a SEPARATE task from the fetch, so a load failure
never prevents the next fetch from capturing history. The fetch is the irreversible part; the
load can always catch up.

VERIFICATION — do not report success without showing me:
  - The unit tests passing, with the boundary cases named.
  - A dry-run or `airflow tasks test` proving the gate returns the expected branch for: today
    (2026-08-17, pre-switch), 2026-08-20 at 04:00 UTC (post-switch), and 2026-08-20 at 00:00 UTC.
  - The DAG parsing clean: `airflow dags list-import-errors` empty.
  - Row counts before and after a manual load run, proving the backlog of 2 unloaded files
    cleared.

CONSTRAINTS:
  - This touches the weekly runtime path. Land it, verify it, and tell me it is done — do not
    bundle any other change into this session.
  - No business logic in the DAG beyond the gate itself.
  - Do not rename anything in this session. That is B2.
```

---

## PROMPT B2 — The `fct_*` / `dim_*` rename (only after B1 is verified)

```
Read ../claude_work/cfdb_model_reconciliation.md first.

DECISION MADE (Marc, 2026-08-17): adopt fct_* / dim_* naming, and do it now while there are
only 3 marts rather than after Phase 1 adds a dozen more. This is a BREAKING CHANGE to a running
system — the Streamlit site reads these tables and the publish job lists them explicitly.

Renames, with the grain corrections your own audit established:
  mart_team_schedule      -> fct_game_team          (grain: game x team, 220,204 rows)
  mart_team_season_record -> fct_team_record        (grain: team x season, 30,221 rows)
  mart_data_freshness     -> fct_endpoint_freshness (grain: ENDPOINT, 64 rows)

Note the third is NOT fct_pipeline_run. Your audit established that it describes API responses,
not task runs. Naming it fct_pipeline_run would bake in the exact confusion the audit caught.
Nothing in the repo currently records Airflow run history; that remains unbuilt.

Do NOT rename stg_teams or stg_games. Staging keeps stg_* — the convention applies to marts.

TASK:
  1. Inventory every reference before changing anything: dbt models, _models.yml, singular tests,
     the publish job, the Streamlit app, deploy config, any DAG. Show me the list first.
  2. Rename in ONE atomic commit covering models, tests, publish job and app together. A
     half-landed rename during the week before the season is the failure mode to avoid.
  3. Run the full dbt build and the full test suite on BOTH engines — Postgres and Databricks.
     Your audit says parity was previously checksum-verified; confirm it still holds after.
  4. Verify the site still loads and reads the renamed tables.

VERIFICATION — do not report success without showing me:
  - The reference inventory from step 1.
  - `dbt build` output, both engines, all 45 tests passing.
  - Evidence the publish job succeeded end to end.
  - Confirmation the live site renders.

If ANY reference cannot be updated safely, stop and tell me before committing. A rollback plan
in the commit message is worth the thirty seconds.
```

---

## PROMPT B3 — `stg_lines` → `fct_betting_line` (not on the runtime path, can follow the season)

```
Read ../claude_work/cfdb_model_reconciliation.md first.

CONTEXT: /lines snapshots are accruing in raw but have no staging or mart model. Your audit
verified the real provider set, which differs entirely from what the design doc guessed:
  ESPN Bet 3,199 rows · Bovada 2,148 · DraftKings 2,032 · "Draft Kings" 64

TASK 1 — stg_lines, with provider normalisation.

The two DraftKings spellings are the same book and will silently split any provider-level
comparison. DECISION MADE (Marc/Cowork): do NOT blind-rename in place. Preserve the landed value
AND add a mapped key:
  - provider_raw   — exactly as landed, never modified
  - provider_key   — normalised ("Draft Kings" -> "DraftKings")
This keeps the mapping auditable and reversible. If the two spellings ever turn out to be
different books, no evidence has been destroyed.

Add a dbt test that FAILS when an unmapped provider_raw appears, so a new sportsbook surfaces
loudly instead of quietly becoming a new dimension member.

TASK 2 — fct_betting_line.
  Grain: game x provider x snapshot_ts. Append-only. Never update or delete a prior snapshot.
  Keep BOTH `spread` and `formatted_spread` as separate columns. They are known to disagree in
  historical data and we do not know which is authoritative; store both and let downstream
  choose. Do not reconcile them.
  Tests: uniqueness on the grain, not_null on keys, and a freshness check.
  Descriptions on every column in schema.yml — that is the convention here and every existing
  model already meets it.

TASK 3 — dim_provider, off stg_lines. Small, but it is the first real conformed dimension in the
repo, so get the pattern right: surrogate key, provider_raw preserved, provider_key normalised.

VERIFICATION: dbt build output, row counts, and proof that re-running does not duplicate rows.
Show me a sample of the same game across multiple snapshot_ts values so I can see movement is
actually being captured.
```

---

## What I have NOT done

- **The matrix workbook is now known-wrong and has not been regenerated.** Statuses, grains and
  Phase 1 in `cfdb_page_to_mart_matrix.xlsx` are superseded by the reconciliation report. Until
  it is rebuilt, **the report is authoritative and the workbook is not**. Worth a note at the top
  of the workbook, or regenerating it.
- **The team-colour gap is unresolved.** `dim_team` has no `logos`, `color` or
  `alternate_color` — they are in raw, never selected — while wireframe v0.2 leans on mascot
  marks and team-coloured accents throughout. Either the columns get added or the design changes.
- **The Player page question is still open**, and the audit changes its economics: `/plays` for
  2024 is already landed (~570k rows), and the measured full 2024–2026 cost is ~1M plays, ~0.87 GB,
  about two minutes of API time. It is much cheaper than the matrix assumed.
