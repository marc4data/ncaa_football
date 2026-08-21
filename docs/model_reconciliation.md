# cfdb — Model Proposal vs. Repo Reconciliation

**Audit date:** 2026-08-17 · **Scope:** read-only · **Auditor:** Claude Code
**Proposal reviewed:** `cfdb_page_to_mart_matrix.xlsx` (32 tables: 12 dims, 20 facts; 14 gaps)

Every grain claim below was verified against the model SQL **and** against row counts in the
live database. Where I could not verify something, it says **unverified** rather than a guess.

---

## The headline finding

**The proposal's `fct_game` and the repo's `mart_team_schedule` are not the same table, and
the proposal treats them as if they were.**

| | Grain | Rows |
|---|---|---|
| Proposal `fct_game` (PARTIAL) | one row per game | — |
| Repo `mart_team_schedule` | **one row per game × team** | 220,204 |
| Repo `staging.stg_games` | one row per game | 110,102 |

220,204 is exactly 2 × 110,102, confirmed by `count(distinct (game_id, team_id)) = 220204`
and `count(distinct game_id) = 110102`. The team-game spine the proposal schedules as
`fct_game_team` for **Phase 2** already exists and has been in production since 2026-08-15.
Meanwhile the one-row-per-game grain that `fct_game` describes exists only as a **staging
view**, not a mart.

Consequences if the proposal is built as written:

1. `fct_game_team` (P2) would **duplicate** `mart_team_schedule`, which is already live,
   tested with 9 tests, and serving the site.
2. `fct_game` (P1) would be a genuinely new table — but the proposal marks it PARTIAL, which
   implies most of the work is done. It is not: no mart at that grain exists.
3. Any page wired to "fct_game" expecting one row per game would double-count if pointed at
   `mart_team_schedule`.

---

## (a) Repo inventory

### dbt project — present
`dbt/dbt_project.yml`, project `cfdb_dbt`, profile `cfdb_profile`.
`model-paths: ["models"]`, `test-paths: ["tests"]`. Default materialization **view**;
marts override to **table**. Schema-per-layer configured (`staging` → `staging`,
`marts` → `marts`) via a `generate_schema_name` override that returns the schema verbatim.

### Models — 6 total. No intermediate layer exists.

| Layer | Model | Materialization | Rows | Verified grain |
|---|---|---|---|---|
| staging | `stg_teams` | view | 34,061 | team × season |
| staging | `stg_games` | view | 110,102 | game |
| staging | `stg_raw_manifest` | view | 1,747 | API response (file) |
| marts | `mart_team_schedule` | table | 220,204 | **game × team** |
| marts | `mart_team_season_record` | table | 30,221 | team × season |
| marts | `mart_data_freshness` | table | 64 | **endpoint** |

**There is no `dim_*` or `fct_*` naming convention in this repo at all.** Nothing is modelled
as a conformed dimension. There are no surrogate-key dimensions, no SCD2 tables, no date
dimension.

### Tests — 45 total, every model covered

7 singular tests (`dbt/tests/`) plus generic tests in `_models.yml`. Per model:
`mart_team_season_record` 11, `mart_team_schedule` 9, `stg_games` 9, `stg_teams` 5,
`mart_data_freshness` 4, `stg_raw_manifest` 4. **Zero models without tests.**

Notable singular tests: `assert_wins_equal_losses_per_season`,
`assert_games_played_reconciles_to_schedule`, `assert_schedule_matches_games`,
`assert_date_only_seasons_are_not_timezone_shifted`, `assert_no_request_lost_its_data`.

### Airflow — present, running

5 DAG files. 4 registered and unpaused; `example_dag.py` and `ingest_to_postgres_dag.py`
are scaffold files whose imports are wrapped in a bare `try:` and therefore **never
register** (they fail silently rather than erroring).

| DAG | Schedule | Purpose |
|---|---|---|
| `cfbd_lines_snapshot` | `@daily` | one `/lines` snapshot of the week in play |
| `cfbd_results_refresh` | Sun 12:00 UTC | results week + prior week, then load → dbt run → dbt test |
| `cfbd_pregame_refresh` | Tue 12:00 UTC | lines + ratings for the upcoming week, same chain |
| `cfbd_alerting_selftest` | manual | fails on purpose to prove alerting |

### Docker Compose — three stacks

- `docker-compose.yml` — transform Postgres
- `docker-compose.airflow.yml` — Airflow 3.3.1 (api-server, scheduler, dag-processor), custom image with dbt
- `deploy/docker-compose.yml` — droplet: serving Postgres, Streamlit site, cloudflared tunnel

### Where data lands — **both engines, fully**

| | Raw | Staging | Marts |
|---|---|---|---|
| Transform Postgres | `raw.*` — 65 tables | `staging.*` — 3 | `marts.*` — 3 |
| Databricks (`workspace`) | `raw.*` — 65 tables | `staging.*` — 3 | `marts.*` — 3 |
| Serving Postgres (droplet) | none by design | none by design | `marts.*` — 3 |

Raw corpus: 1,716 files / 64 endpoints / ~3.04M records in Postgres; 1,717 files in
Databricks (one extra lines snapshot). Both engines run the same dbt models via dispatched
macros; parity was previously verified by checksum.

### Transforms outside dbt — **none**

No notebooks anywhere in the repo. `src/` holds 11 modules, all ingestion, loading,
alerting or publishing — none transform data. Loaders write raw only.

---

## (b) Reconciliation — all 32 proposed tables

Grain column reports **verified reality**, not the proposal's claim.

### Dimensions (12)

| Proposed | Exists? | Actual name | Actual grain | Grain matches? | Notes |
|---|---|---|---|---|---|
| `dim_team` | **Partially** | `staging.stg_teams` (view) | team × season, 34,061 | **Yes, by accident** | Grain matches "team per season-affiliation". But it is a staging view, not a dim; no surrogate key, no `valid_from`/`valid_to`. Proposal assumes `logos[]`, `color`, `alternate_color` — **none of these columns exist** in the model, though they are present in the raw payload. |
| `dim_conference` | **No** | — | — | — | Proposal marks ASSUMED; that is wrong. Conference is a **text attribute** on `stg_teams`. No conference table exists in any layer. Status should be NOT BUILT. |
| `dim_venue` | No | — | — | — | `raw.raw_venues` landed (1 response). Not modelled. |
| `dim_season` | No | — | — | — | Nothing derived. Seasons range 1869–2026 in `stg_games`. |
| `dim_week` | No | — | — | — | `raw.raw_calendar` landed, **26 seasons only (2002+)** — CFBD serves no calendar before 2002 (probed 2026-08-15). Proposal does not mention this floor. |
| `dim_coach` | No | — | — | — | `raw.raw_coaches` landed, 141 seasons (1886+). |
| `dim_athlete` | No | — | — | — | `raw.raw_roster` landed (3 responses). |
| `dim_poll` | No | — | — | — | `raw.raw_rankings` landed (1936+). |
| `dim_provider` | No | — | — | — | **Provider list now verified — see DELTAS.** |
| `dim_model_version` | No | — | — | — | No ML in repo at all. |
| `dim_stat_category` | No | — | — | — | `raw.raw_stats_player_season` landed. EAV shape unverified by me. |
| `dim_field_metadata` | No | — | — | — | dbt `schema.yml` descriptions exist on all 6 models; nothing generates a dictionary table. |

### Facts (20)

| Proposed | Exists? | Actual name | Actual grain | Grain matches? | Notes |
|---|---|---|---|---|---|
| `fct_game` | **No (mart)** | `staging.stg_games` (view) | game, 110,102 | Grain exists, **not as a mart** | Proposal marks PARTIAL. No mart at this grain. Would need promotion from staging or a new mart. |
| `fct_game_team` | **YES — already built** | `marts.mart_team_schedule` | **game × team, 220,204** | **Yes** | Marked NOT BUILT / P2 in the proposal. It is live, tested (9 tests), and serving the site. Sourced from `/games`, so it has schedule + result columns but **no box-score columns** (`/games/teams` is landed in raw but unused). |
| `fct_game_team_advanced` | No | — | — | — | `raw.raw_stats_game_advanced`, `raw.raw_ppa_games` landed. |
| `fct_team_week_rating` | No | — | — | — | Ratings endpoints landed (`sp`, `elo`, `srs`, `fpi`, `core`). Proposal calls this the most important fact; **nothing exists**. |
| `fct_team_season_stat` | No | — | — | — | `raw.raw_stats_season` landed (1869+). |
| `fct_team_record` | **YES** | `marts.mart_team_season_record` | team × season, 30,221 | **Yes** | Marked LIVE — correct. **But the source differs:** proposal says `/records`; the model computes W-L-T from `stg_games` by unpivoting home/away. `/records` is landed in raw and **not used**. No `tiebreak_rank` column exists. |
| `fct_poll_rank` | No | — | — | — | `raw.raw_rankings` landed. |
| `fct_betting_line` | No (mart) | — | — | — | **Raw is accruing**: 12 snapshot files on disk, 10 loaded. Snapshot DAG live since 2026-08-15. No staging or mart model. |
| `fct_prediction` | No | — | — | — | No ML anywhere. |
| `fct_drive` | No | — | — | — | `raw.raw_drives` landed (6 responses, 2024–2026). |
| `fct_play` | No | — | — | — | `raw.raw_plays` landed — **36 files, ~570k play rows for 2024**. Proposal marks V1.5 and warns the backfill is expensive; a substantial part is already paid for. |
| `fct_player_game_stat` | No | — | — | — | `raw.raw_games_players` landed (36 files). |
| `fct_player_season_stat` | No | — | — | — | `raw.raw_stats_player_season` landed (48 files, largest endpoint at ~420 MB). |
| `fct_team_talent` | No | — | — | — | `raw.raw_talent` landed. Zero-vs-null issue unverified by me. |
| `fct_returning_production` | No | — | — | — | `raw.raw_player_returning` landed. |
| `fct_game_weather` | No | — | — | — | **Not tier-gated — see DELTAS.** |
| `fct_bet` | No | — | — | — | Manual entry; nothing exists. |
| `fct_pipeline_run` | **No** | `marts.mart_data_freshness` | **endpoint, 64** | **NO — different grain** | Proposal says freshness "appears to cover the freshness slice". It does not cover *pipeline runs*: the grain is one row per **API endpoint**, built from `raw_manifest` (API responses), **not from Airflow metadata**. No table records task runs. |
| `fct_dq_test_result` | No | — | — | — | dbt writes `run_results.json` per run; nothing persists it. |
| `fct_api_usage` | No | — | — | — | `/info` reports quota live; nothing logs it. |

**Score: of 32 proposed tables, 2 exist as marts at the proposed grain
(`fct_team_record`, `fct_game_team`), 2 exist at a different grain or layer than proposed
(`fct_game`, `fct_pipeline_run`), 1 exists as a staging view mistaken for a dimension
(`dim_team`), and 27 do not exist.**

---

## (c) DELTAS — where the proposal is wrong about reality

Ordered by consequence.

### 1. `fct_game_team` is already built; building it again would duplicate a live table
Marked NOT BUILT, Phase 2, sourced from `/games/teams`. Reality: `mart_team_schedule` has
exactly the proposed grain (game × team, 2 per game), 220,204 rows, 9 tests, and is the
table the live site reads. It lacks box-score columns because it is built from `/games`.
**The correct work is to add box-score columns to the existing mart, not to create a second
table at the same grain.**

### 2. `fct_game` is marked PARTIAL but no mart at that grain exists
The one-row-per-game grain exists only as `staging.stg_games`, a view. PARTIAL overstates
progress. This is a real Phase-1 build (or a promotion of staging to a mart), not a finish-off.

### 3. `fct_pipeline_run` ≠ `mart_data_freshness` — different grain, different source
Proposal: one row per Airflow task run, from Airflow metadata.
Reality: `mart_data_freshness` is one row per **endpoint** (64 rows), derived from
`raw_manifest` — i.e. it describes **API responses**, not task runs. It answers "how old is
this endpoint's data" and "did an endpoint stop returning rows". It cannot answer "did last
Sunday's DAG succeed". **Nothing in the repo persists Airflow run history outside Airflow's
own metadata database.**

### 4. `dim_conference` is marked ASSUMED; it does not exist in any form
Conference is a `text` column on `stg_teams` and on `mart_team_schedule`
(`conference`, `opponent_conference`). There is no conference entity, no key, no attributes.
ASSUMED implies "probably already covered"; the correct status is NOT BUILT.

### 5. `dim_team` is ASSUMED but is a staging view missing the columns the proposal relies on
`stg_teams` grain does match. But:
- It is a **view in `staging`**, not a dimension in `marts`.
- **No SCD2 machinery** — no `valid_from`/`valid_to`/`is_current`. Season-scoping gives
  per-season correctness, which is *not* the same as SCD2 (it cannot express a mid-season
  change, and there is no way to ask "what was true on 2024-10-01").
- The proposal states it "carries logos[], color, alternate_color, mascot, abbreviation".
  **Actual columns:** `season, team_id, team_season_key, school, mascot, abbreviation,
  conference, division, classification, city, state`. `logos`, `color`, `alternate_color`
  are **absent from the model** — they exist in the raw payload but were never selected.
  Any page assuming team colours or logos will find nothing.

### 6. `fct_team_record` is LIVE and correct on grain, but its source is not `/records`
The model computes W-L-T from `stg_games` by unpivoting home/away and aggregating. `/records`
is landed but unused. This matters because the proposal's HIGH gap ("CFBD has no standings
endpoint… own it with a `tiebreak_rank` column") assumes `/records` is the input. Reality:
records are **already derived**, and `tiebreak_rank` does not exist. Worth deciding whether
the derived figures should be reconciled against `/records` as a data-quality check.

### 7. The line-snapshot DAG already exists — but at `@daily`, not 4-hourly
Proposal P1 lists "Line snapshot DAG" as the thing to start first, and Facts specifies
`/lines (polled 4-hourly)`. Reality: `cfbd_lines_snapshot` has been live since 2026-08-15 at
`@daily`, with verified successful runs on 8/16 and 8/17.

Given the CRITICAL gap (line history cannot be backfilled), **the cadence gap is the live
risk**: every day at daily cadence permanently loses the intraday movement 4-hourly would
have captured. Changing `SCHEDULE` is a one-line edit — but it touches the weekly runtime
path, so under the standing freeze rule it lands **before Aug 27 or after Sep 7**.

### 8. `dim_provider` — the proposal's provider list is wrong; the real one is now verified
Proposal (MEDIUM, "UNVERIFIED"): *consensus / Caesars / numberfire / teamrankings*.
**Observed in 12 landed `/lines` responses:**

| Provider | Line rows |
|---|---|
| ESPN Bet | 3,199 |
| Bovada | 2,148 |
| DraftKings | 2,032 |
| **Draft Kings** | **64** |

None of the four guessed providers appear. And there is a **data-quality defect worth
catching now**: `DraftKings` and `Draft Kings` are the same book under two spellings.
Without normalisation in staging, `dim_provider` will have a duplicate member and any
provider-level comparison will silently split.

### 9. `fct_game_weather` is **not** tier-gated for this key
Proposal (MEDIUM): "historically Patreon-gated, verify before designing the Matchup weather
block." Verified: 4 responses, all HTTP 200, up to **3,176 rows**. The gap can be closed.

### 10. `fct_play` is further along than V1.5 implies
Proposal warns a season backfill is 15+ calls and defers to V1.5. Reality: `/plays` is
landed for 2024 — 36 files, ~570k rows — and the measured full cost for 2024–2026 was
~1,006,000 plays at ~0.87 GB and about two minutes of API time. The expensive part is
mostly done; what remains is modelling.

### 11. `dim_week` has a hard floor the proposal does not mention
`/calendar` returns nothing before **2002** (probed). `dim_week` therefore cannot cover
1869–2001, while `stg_games` covers 1869–2026. Any week-grain join across deep history will
lose ~130 seasons.

### 12. Raw lines snapshots lag the warehouse
12 snapshot files on disk; 10 loaded into Postgres. The lines DAG **fetches but does not
load** — loading happens only in the weekly DAGs. No data is lost, but `fct_betting_line`
built today would be up to a week stale relative to what has actually been captured.

---

## (d) DECISIONS NEEDED — I will not guess these

1. **What is `fct_game` meant to be?** Promote `stg_games` to a mart at one-row-per-game, or
   was `fct_game` intended to be the team-game spine that `mart_team_schedule` already is?
   These are different tables and the answer changes Phase 1.

2. **`fct_game_team`: extend or replace?** My reading is that box-score columns from
   `/games/teams` should be added to `mart_team_schedule`. Confirm — the alternative is two
   tables at identical grain, which I would not build without an explicit instruction.

3. **Does `dim_team` need true SCD2?** Current per-season scoping answers "what was true in
   season X". True SCD2 answers "what was true on date D" and can express mid-season changes.
   The second is materially more work. Which do the pages actually need?

4. **Rename to `dim_*` / `fct_*`?** The repo has no dimensional naming convention. Adopting
   the proposal's names means renaming live tables the site reads and the publish job lists
   explicitly. Cheap now, expensive after more pages exist — but it is a breaking change to a
   running system, so it needs a decision rather than a drive-by.

5. **Lines cadence: stay `@daily` or move to 4-hourly before the season?** CRITICAL and
   irreversible — undone intraday history cannot be recovered. Freeze rule means before
   Aug 27 or after Sep 7. Also: 4-hourly is 6× the API calls and 6× the raw growth
   (measured: ~0.11 MB per week-scoped snapshot, so ~2.6 MB/day → ~320 MB/season).

6. **Should `fct_team_record` be reconciled against `/records`?** Records are currently
   derived from games. `/records` is landed and unused. A cross-check would be a strong
   data-quality test; it is also a new dependency.

7. **`dim_provider` normalisation:** is `Draft Kings` → `DraftKings` a safe mapping, or
   should both be preserved as distinct source values with a mapped surrogate?

8. **Player page** — the proposal's OPEN gap. Still open; nothing in this repo resolves it.

---

## (e) Recommended Phase 1 revision

The proposal's P1 is 12 tables (7 dims, 5 facts). Based on what exists, I would re-cut it.

### Drop from P1 — already built
- **`fct_game_team`** — exists as `mart_team_schedule`. Replace with a smaller task:
  *add box-score columns from `/games/teams` to the existing mart.*
- **`fct_team_record`** — exists as `mart_team_season_record`, tested. Remaining work is
  optional: `tiebreak_rank`, and a reconciliation test against `/records`.

### Reclassify — the proposal understates these
- **`dim_conference`** — ASSUMED → **NOT BUILT**. It is a genuine build.
- **`dim_team`** — ASSUMED → **PARTIAL**. Grain exists; needs promotion to marts, the
  missing colour/logo columns, and an SCD decision.
- **`fct_game`** — PARTIAL → **NOT BUILT** (pending decision 1).
- **`fct_pipeline_run`** — PARTIAL → **NOT BUILT**. `mart_data_freshness` does not cover it.

### Do first, because it is time-sensitive rather than large
1. **Decide and set the lines cadence** (decision 5). Irreversible loss accrues daily, the
   season starts 2026-08-27, and the freeze window closes on changes to the running path.
   This is a one-line change gated on a decision, not a build.
2. **Normalise provider names in staging** (`Draft Kings` → `DraftKings`) before
   `fct_betting_line` is modelled, so the defect never reaches a dimension.
3. **Load lines snapshots on the daily DAG**, or accept staleness knowingly (delta 12).

### Then build, in this order
4. `stg_lines` → `fct_betting_line` — the only CRITICAL accruing table with no model.
5. `dim_conference` — small, unblocks 12 pages per the proposal's own count.
6. `dim_team` promotion — move to marts, add `color`/`alternate_color`/`logos`, resolve SCD.
7. `dim_season`, `dim_week` — trivial, but record the **2002 floor** on `dim_week`.
8. `dim_venue` — raw already landed.
9. `fct_game` — only after decision 1.

### Defer out of P1
- **`dim_field_metadata`** — the proposal wants it generated from dbt. All 6 models already
  carry descriptions; `dbt docs generate` covers the need until there are more tables. Low
  value now, mechanical later.
- **`fct_dq_test_result`** — dbt already writes `run_results.json` every CI run and every
  DAG run; persisting it is easy but nothing consumes it yet.
- **`fct_pipeline_run`** — real work (Airflow metadata extraction), and the alerting path
  already surfaces failures by email and local log. Value is historical analysis, not
  operations.

### Unverified — flagged rather than guessed
- The EAV shape of `/stats/player/season` (proposal MEDIUM). Landed but not inspected.
- `fct_team_talent` zero-vs-null (proposal HIGH). Landed but not inspected.
- The spread vs formatted-spread disagreement (proposal HIGH) — that references an external
  performance-monitor workbook not present in this repo.
- Whether `/games/teams` box scores contain every column `fct_game_team_advanced` assumes.
