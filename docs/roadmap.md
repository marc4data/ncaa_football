# cfdb Roadmap

**Status: ADOPTED — drafted by Claude Code 2026-08-14; reviewed, amended, and adopted by
Cowork (Marc) the same day.** Ownership sits with Cowork per the division of labor in
`CLAUDE.md`. Amendments from review: M0 wording corrected, M3 unserialized from M2,
Bucket C narrowed for PBP/drives, `/lines` decided in-scope with daily in-week monitoring,
serving/hosting added to the open decisions register. The Week 0 verification closed
2026-08-14 (Claude Code): **no Week 0 exists** — but the check surfaced two dating errors
and one structural surprise that move dates earlier. See the deadline section.

**AMENDED 2026-08-19 (Cowork).** This doc had not been touched since 2026-08-17 and had
drifted behind six major decisions. Amendments below are marked **[A 08-19]**. Where this
doc and `decision_log.md` disagree, **the decision log wins** — it is dated and append-only;
this one is a living plan. The most consequential change: the project now has an explicit
**north star** (see the section immediately below) that outranks milestone ordering.

Companion docs: `CLAUDE.md` (what and why — source of truth), `decision_log.md` (why,
dated), `cfdb_publication_boundary.md` (what may appear on the site), `setup_checklist.md`
(phase-1 setup, complete), `setup_execution_plan.md` (how, phase-1 setup only).

## Why this doc exists

Until now the plan lived in three places with three numbering schemes — the architecture
table's "phase 1", the checklist's §1–§6, and the execution plan's Steps 0–7 — and nothing
described what happens after setup. A reference to "step 7" resolved in one doc and
dead-ended in another. This file is the single list. The only prior milestone list
(`claude_code/project_setup_actions.md`, two entries, plus a project board that was never
created) is superseded by this one and can be retired.

---

## The north star — outranks everything below  **[A 08-19]**

> **Real data serving EVERY page of the website, as soon as possible, so the site can be
> built out and then iterated on.**

Model fidelity, phase purity, enrichment and dimensional orthodoxy are all **subordinate**
to that. Where a decision trades page-readiness against elegance, page-readiness wins.

The metric is **pages that RENDER**, not tables that exist. As of 2026-08-19: **11 of 17
pages render**; 6 are blocked, each by exactly one missing primary fact. The seven-table
**NEXT set** closes that gap — see `cfdb_page_to_mart_matrix_v3.xlsx` and the 2026-08-19
decision-log entry. Milestone ordering below is historical context; the NEXT set is the
current priority.

**The freeze rule is now an evidence rule, not a calendar rule** (2026-08-18):

| Change class | Constraint |
|---|---|
| New objects nothing reads | **No freeze.** Build any time. |
| Cutover of a page to a new view | Gated on the **parity test passing**, not a date |
| Runtime changes with no parity proof | Date-gated: before 2026-08-27 or after 2026-09-07 |

---

## The deadline that shapes everything

**The 2026 season's first games are 2026-08-27** — thirteen days out. The first **FBS**
games are 2026-08-29, fifteen days out.

### Week 0: verified and closed (Claude Code, 2026-08-14)

> **[A 08-19] Terminology note.** This finding still stands: **CFBD has no Week 0** — it
> folds the early slate into Week 1. But "Week 0" is used *colloquially* in the decision log
> and by ESPN/NCAA.com to mean the 2026-08-27 → 08-30 opening slate. Both are true; they are
> different vocabularies. When reading either doc: **CFBD week numbering has no zero; the
> opening-weekend slate is called Week 0 in prose.** The cadence anchor and the Week 0
> validation window both key off the first game date (2026-08-27), not a week label.

**CFBD has no Week 0.** The 2026 calendar runs weeks 1–15; 2024 ran 1–16. The colloquial
Week 0 slate is **folded into Week 1** — proven against 2024 data already in our warehouse,
where the Aug 24 Week 0 Saturday (6 games) carries `week = 1` alongside the Aug 29–31
games. There is no separate week to include or exclude, so no scope decision is needed.

Two corrections the check produced along the way:

1. **`/calendar` is not authoritative for first-game dates.** It reports
   `firstGameStart = 2026-08-29`, but `/games?year=2026` lists 69 games on or before that
   date, starting **2026-08-27 (Thu)**. The early ones are FCS/D-II; `/calendar` appears
   FBS-oriented. Date anything operational off `/games`, not `/calendar`.
2. **Week 1 is a twelve-day, two-Saturday window: 2026-08-27 → 2026-09-07, 211 games.**
   Week 2 is a normal three-day window (Sep 11–13). A pipeline scheduled "once per CFBD
   week" would leave the Aug 29 FBS opening slate unpulled until Sep 7. **Schedule by
   calendar day (e.g. every Sunday), not by CFBD week boundary** — C2's current + prior
   week pattern handles the overlap either way. Open register entry below.

### What must be true, and when

Everything before kickoff is preparation that gets harder once games start; everything
after is either running live or backfilling. CFBD retains history, so a missed week isn't
lost data — but "the pipeline has run weekly all season" is the story worth telling in an
interview, and it only starts once.

| Date | Days out | What must be true |
|---|---|---|
| 2026-08-20 | 6 | Endpoint scope + cadence decided (M1) — ✅ done early |
| ~~2026-08-24~~ | — | ~~Daily `/lines` pull live~~ — **SUPERSEDED [A 08-19].** Delivered early (live 2026-08-15). Replaced by the season-aware cadence below. |
| **2026-08-20** | **binding** | **[A 08-19] Lines cadence gate live** — schedule flips from daily to **every 4 hours** seven days before the first game. Window 2026-08-20 → 2027-01-27 (CFP championship 2027-01-25 + UTC overrun). Implemented as a permanent `0 */4 * * *` schedule with a short-circuit outside the window, so no seasonal schedule edit is ever needed again. |
| 2026-08-27 | 13 | Results capture live if FCS/D-II openers are in scope |
| 2026-08-28 | 14 | 2024–2025 historical backfill loaded and tested (M2) |
| **2026-08-29** | **15** | **Results capture live for the first FBS slate (M3)** |
| 2026-09-07 | 24 | First complete CFBD week; first full unattended weekly cycle validates |

---

## Milestones

| # | Milestone | Status | Gate |
|---|---|---|---|
| M0 | Phase 1 setup + ingestion spike | ✅ Complete 2026-08-14 | — |
| M1 | Endpoint scope + cadence decision | ✅ Ratified 2026-08-14 (amended) | 2026-08-20 |
| M2 | Historical backfill (2024–2025) | ✅ Complete 2026-08-14 (full-breadth sweep; Cowork-reviewed 2026-08-15) | 2026-08-28 |
| M3 | Weekly pipeline live in Airflow | 🔶 **Built + shaken out 2026-08-14; live validation PENDING** — the unattended-cycle criterion needs Week 1 (first slate 8/27–29; first full cycle Sep 7) | **2026-08-29** |
| **M2b** | **Analyst data horizon: 2026 framework + curated full history + first analyst models** | ✅ **Complete — accepted by Cowork 2026-08-16** (all three exit criteria verified against the repo; 156 seasons, zero failures; date-only timezone bug found + fixed + tested) | Before Week 1 for the 2026 framework; full history ASAP after |
| M4 | Databricks becomes the transform target | ▶ **UNBLOCKED 2026-08-16 (Marc)** — runs in parallel with M3 validation, under the weekly-path change freeze (see M4 section) | Before M6 |
| M5 | Serving layer: marts published to Postgres | ▶ **UNBLOCKED from M4 (Marc, 2026-08-16)** — starts on hosting decision (research underway) | ASAP |
| M6 | Streamlit site + Cloudflare Access | ▶ **Hosted stack LIVE 2026-08-16 at `<site-host>`** — tunnel Healthy; **edge auth fully verified** (allowed-email test ✅, stranger test ✅ 2026-08-16). Remaining: site content/features + launch criteria. | ASAP |
| M7 | Model predictions on the site | Blocked on M5 | — |

### M0 — Phase 1 setup + ingestion spike ✅

Docker/Postgres, GitHub repo with Actions and secrets, Databricks account, CI (flake8 +
pytest, governance guards, manual CFBD smoke test), and an end-to-end dbt slice
(raw → staging → marts, 22 tests, two reconciliation tests). Every acceptance criterion in
`setup_checklist.md` passes **except the Databricks `dbt debug` stretch item — no
Databricks dbt target exists yet. That criterion moves to M4, where it belongs.**

### M1 — Endpoint scope + cadence decision ✅

**Ratified by Cowork (Marc) 2026-08-14, ahead of the 2026-08-20 gate, with two
amendments:** (1) Bucket C narrowed — completed weeks of the current season are immutable,
so `/plays`/`/drives` pull current + prior week rather than the whole season; (2) `/lines`
decided in scope with **daily monitoring during game week** (see Bucket D). Of the original
open questions, #2 and #3 are resolved by these amendments; #1 (volume) was measured and
closed 2026-08-14; #4 (manifest vs Airflow as backfill state) moves to M2 design.

**Exit criteria (met):** every endpoint the project will use is classified into one of the
four cadence buckets below, with a written reason; endpoints not needed for phase-1 site
features are explicitly out of scope.

**Why now and not later:** cadence determines DAG structure, and the DAG has to exist
before Week 1. Deciding after the season starts means rewriting a running pipeline.

**Scope discipline — AMENDED 2026-08-15 (Marc; reverses the ratified 2026-08-14 wording).**
Original: endpoint scope is *pulled* by what the site needs to show. Reversed for the
capture layer: **raw capture is now maximal** — the full sweepable API surface (63 of 74
registry endpoints) is landed, for maximum analytic and reporting capability. Measured
cost made this cheap to say yes to: 332 calls / 1.0 GB raw / 180 MB Postgres for two full
seasons — 0.5% of monthly quota. The demand-driven principle *moves down a layer* rather
than dying: **dbt modeling stays pulled** by what the site or a concrete analysis consumes,
and expensive per-game fan-outs stay opt-in behind the same test (see register). Operative
cadence source of truth is now the declarative registry in `src/endpoints.py`; this
appendix documents the rationale, not the runtime config.

### M2 — Historical backfill (2024–2025)

**Exit criteria:** 2024 and 2025 fully landed in raw and loaded to Postgres for every
"historical" endpoint; staging/marts rebuilt; reconciliation tests pass per season; a
documented rerun procedure.

Includes the fix already identified: **`/teams` is season-scoped.** `/teams?year=2024`
returns 2024-correct affiliations (Boise State = Mountain West, NDSU = MVFC/FCS) where the
unparameterized call returns today's. Backfill pulls one `/teams` per season and
`stg_teams` gains a `season` column, retiring the anachronism flagged in the spike.

Play-by-play and drives are 2024/2025/2026 only, per the data scope in `CLAUDE.md`.

### M3 — Weekly pipeline live in Airflow

**Exit criteria:** an Airflow DAG runs the weekly refresh end to end on a schedule, with
retries and failure alerting; a full cycle completes unattended against Week 1; freshness
("data as of X") is recorded where the site can read it.

**Not serialized behind M2:** DAG development needs nothing from the finished backfill —
build and test it against the spike's data while M2 runs. Only the final unattended
validation cycle depends on M2 being done. (Amended at review: the original draft
serialized M2 → M3 with one day of slack.)

Airflow owns scheduling/retries/alerting only — no transforms in DAGs. Three cadences to
model (amended from two): a **results refresh** after games complete, a **pre-game
refresh** for forward-looking data (ratings) before the next slate, and a **daily in-week
lines pull** (per the M1 lines decision) — small, fast, and the only daily schedule in
the system.

**Schedule decided (Cowork/Marc, 2026-08-15): fixed calendar days — results refresh
Sunday morning + Tuesday morning sweep.** Sunday captures the Thu–Sat slate while it's
fresh; Tuesday catches Monday games (Labor Day week) and early stat corrections. Not
CFBD week boundaries: Week 1 is a twelve-day, two-Saturday window, so a per-CFBD-week
trigger would sit idle through the Aug 29 opening slate until Sep 7. Full weekly cadence
picture: daily in-week `/lines`, Sunday + Tuesday results, pre-game refresh before each
slate (day set during DAG design).

~~Carry-over from setup: `docker-compose.airflow.yml` still has
`AIRFLOW__CORE__FERNET_KEY: 'change-me'`~~ — ✅ resolved in the M3 build (key generated
into `.env`, never in the image).

**Cowork review, 2026-08-15 — status: BUILT AND SHAKEN OUT; live validation pending.**
Delivered and verified: registry-driven Sunday/Tuesday DAGs (fetch → load → dbt run →
dbt test; failing tests fail the run), daily lines snapshot capturing pre-opener movement
(the 8/24 constraint is already met), two-channel never-raise alerting with a self-test
CLI/DAG, and a freshness + empty-response-detection layer (`mart_data_freshness`,
per-request regression test) that closed a real silent-failure hole the shakeout itself
exposed — 17 of 23 endpoints returning empty 200s under a green DAG. The one criterion
nobody can satisfy before Week 1 exists is "a full cycle completes unattended against
Week 1": **M3 closes when the Sep 7 cycle completes clean** (first partial evidence
8/27–29). Pre-validation punch list: (1) configure + test SMTP alerting
(`python -m src.alerting --check` / `--test`) — unattended failure alerts that only write
to a local file aren't alerts; (2) merge `m2/historical-backfill` to `main` via PR — M2
and M3 both live unmerged, and PR-by-convention is our substitute for branch protection.

### M2b — Analyst data horizon (added 2026-08-15, Marc; work order for Claude Code)

**Why:** Marc is starting analysis of the upcoming season *now*, ahead of the site. The
sweep landed 2024–25 at depth, but two horizons are missing: the 2026 season framework
(the season is on the calendar and its structure should be queryable today), and long-arc
program history at the season level. Not disruptive to M3/M4 — this rides the existing
registry + backfill machinery and touches no DAG.

**Exit criteria, in priority order:**

1. **2026 framework landed (before Week 1).** Bucket A season-scoped pulls run for 2026 —
   `teams?year=2026`, `roster`, `coaches`, plus `/rankings` (preseason polls are out) —
   and `/games?year=2026` re-pulled for schedule updates. Acceptance: any team's 2026
   schedule, week by week, is answerable from Postgres. (Some of this is landed already —
   audit what exists via `raw_manifest` before pulling.)
2. **Curated full-history backfill.** A `history` attribute is added to the endpoint
   registry (`full` | default `recent`), keeping depth declarative and auditable. The
   ratified full-history set — pull every season each endpoint actually serves; the
   endpoint's own availability bounds the depth:
   `games`, `records`, `rankings`, `teams` (season-scoped), `coaches`, `stats/season`,
   `stats/season/advanced`, `stats/player/season`, `wepa/team/season`,
   `ppa/players/season`, and the `draft/*` tables (picks + its static lookups).
   Amendments to this list are one registry line + one decision-log line.
   Everything not listed stays at current 2024+ scope; PBP/drives/lines and per-game
   fan-outs are explicitly unchanged.
3. **First analyst models (demand-driven modeling's first real demand):** a schedule mart
   (any team, any week, any season including 2026) and `mart_team_season_record` extended
   across the new history, both tested. Repo `CLAUDE.md` data-scope wording synced.

**Budget:** order of a few thousand `season`-strategy calls against a 75k monthly quota;
manifest skip-if-present makes reruns free. Raw growth modest (season-level tables are
small).

### M4 — Databricks becomes the transform target

**Exit criteria:** dbt profile has a working Databricks target; models run and test there;
Databricks is primary and Postgres-as-transform-target is retired to local dev only.

This has a **decided expiry condition** (decision log, 2026-08-14): Postgres-first dbt is
blessed as a prototyping convenience only, and Databricks must be primary *before any mart
feeds anything user-facing* — i.e. before M6. Every model added in Postgres dialect grows
the migration surface, so the Postgres-specific JSON SQL (`jsonb_array_elements`,
`distinct on`, `filter`) stays confined to staging.

**UNBLOCKED from M3 (Marc, 2026-08-16).** M3's remaining requirement is calendar, not
work, so holding M4 bought no risk reduction. M4 proceeds in parallel, sequenced to
protect the validation: (1) **cross-dialect JSON macro layer first** (resolves the
unnesting register item), so M2b's new staging models are born dialect-neutral;
(2) **refactor of existing models onto the macros lands before Aug 24**, so the freeze
window validates the code that will run all season; (3) **weekly-path change freeze
Aug 27 – Sep 7** — nothing that alters the running pipeline's runtime path merges in that
window except fixes; purely additive Databricks work (new dbt target, models running
there) is unconstrained throughout. Rationale: a Sep 7 failure must be unambiguous about
what failed.

### M5 — Serving layer: marts published to Postgres

> **[A 08-19] SUPERSEDED IN SHAPE, not intent.** The model is now **three layers**, not two:
> `stg_*` in `staging`, `dim_*`/`fct_*` in `marts`, and **`srv_*` in a new `serving` schema**
> on both engines. The site reads `serving`, not `marts` — `search_path` and the publish job
> move with it. Exit criteria below still hold with `serving` substituted for `marts`.
> Migration is **strangler with a parity test as the cutover gate**: the existing `mart_*`
> tables stay untouched and keep serving the site until a dbt test proves each `srv_` view is
> row-for-row identical to the mart it replaces. See the 2026-08-18 decision-log entry.
>
> **The `serving` schema is also the publication boundary** — see
> `cfdb_publication_boundary.md`. `raw.*` (all 65 tables), the manifest objects, and anything
> pack-derived must never reach it. The CI layering guard is doing licence work, not just
> hygiene.

**Exit criteria:** an Airflow task publishes final marts from the warehouse to serving
Postgres; the site's queries never touch warehouse compute; publish is idempotent.

**UNBLOCKED from M4 (Marc, 2026-08-16).** Rationale: the site reads marts in Postgres —
the serving contract — and the M4 parity verification proved mart contents are
engine-equivalent, so serving and site work are independent of which engine computes the
transforms. The later Databricks cutover changes the *producer* of the marts, invisible to
the *consumer*. In the interim, publish sources from the current transform Postgres; after
cutover it sources from Databricks — same contract, one config change to the publish task.
Publish job is additive (new DAG/task) and does not violate the Aug 27–Sep 7 weekly-path
freeze.

**Hosting decision** (see register): in active Cowork research as of 2026-08-16 — the
first recurring infra spend, against the $0–15/month guardrail. Cloudflare Access setup
comes due with it.

### M6 — Streamlit site + Cloudflare Access

**Exit criteria:** Streamlit reads only serving Postgres; team and matchup pages with
drill-down; every page shows data freshness; Cloudflare Access email allowlist in front;
CFBD credited. No metric computation in Streamlit — if the app needs a number, it belongs
upstream in dbt.

**Development starts NOW (Marc, 2026-08-16), ahead of hosted launch.** The presentation
layer is the heavy lift; it develops locally against the existing marts (correct shape,
real data — 156 seasons + the 2026 schedule) while M5 hosting/publish comes online in
parallel. The exit criteria above govern *launch*, not the start of development. New marts
the site needs are demanded through the standing demand-driven process.

### M7 — Model predictions on the site

> **[A 08-19] PROMOTED — no longer a late milestone.** `fct_prediction` is **primary** on
> Edge Finder and Model Performance, so M7 is in the **NEXT set**, not the tail. Left
> unscheduled, the build produces a well-engineered ESPN clone with no model in it.
>
> **The CFB Model Training Pack — 2026 Edition** was acquired 2026-08-19 and is the source,
> replacing the earlier "Model Starter Package scripts" framing. Four things govern it:
> 1. **The pack ships a 42-column export contract** (`Prediction_Export_Schema_2026.md`)
>    carrying nearly every column Edge Finder and Model Performance need. Adopted verbatim —
>    a load job, not a design job.
> 2. **The sign convention is inverted**: `margin = away_points − home_points`; a negative
>    margin means the HOME team won; `spread` negative means home favoured. Adopted verbatim
>    through raw and staging, pinned by test. Verified against all 5,133 training rows.
> 3. **Weeks 0–4 are out-of-sample.** The pack trains from regular-season Week 5 onward
>    because opponent-adjusted inputs need game history. Predictions before then are
>    extrapolation and carry `is_out_of_sample_week`, kept below the default actionable
>    threshold.
> 4. **Licence:** personal, non-commercial, original purchaser. The pack is gitignored and
>    never loaded to a database; **generated outputs are permitted** and may live on both
>    engines. Outputs must never be presented as official CollegeFootballData.com
>    predictions — attribution is carried as data so a page cannot render without it.
>
> **Commercial asymmetry worth knowing:** CFBD data may be displayed commercially; Model Pack
> outputs may not. If cfdb is ever monetised, predictions come out or get relicensed.

**Exit criteria:** Model Pack notebooks run locally against the pack's training data;
`model_outputs/*.csv` load into `fct_prediction` (grain: game_id × model_name ×
model_version × split, plus prediction_ts, append-only); predictions reach the site through
`serving`; the site shows them with honest accuracy framing.

Features come from dbt marts — no ad-hoc feature math inside model scripts. MLflow is a
later phase, not this one. **[A 08-19] Provenance rule:** never source a served model from
the pack's `training_data.csv`, even when convenient — the same metric from the CFBD API is
displayable, from the pack it is not.

---

## Appendix — endpoint cadence classification (M1, ratified)

**Drafted by Claude Code; ratified with amendments by Cowork (Marc) 2026-08-14.** The
classifying question is *when does this data stop changing?*

### Bucket A — Structural, season-scoped (one pull per season)

Pull once per season during backfill; pull once when a new season opens; never weekly.

| Endpoint | Note |
|---|---|
| `/teams?year=` | **Must be season-scoped** — affiliations change yearly. Verified. |
| `/conferences` | Rarely changes; refresh annually. |
| `/venues` | Refresh annually. |
| `/roster?year=` | Fixed once the season opens. |
| `/coaches?year=` | Fixed once the season opens. |

### Bucket B — Historical, immutable (one pull per completed season, never re-run)

A completed game's plays don't change. Backfill 2024–2025 once; re-pull only on a known
CFBD stat correction.

| Endpoint | Note |
|---|---|
| `/games?year=` | Completed seasons only. |
| `/drives?year=` | 2024–2026 only, per data scope. |
| `/plays?year=&week=` | Highest volume; one call per week (`week` is a required param, not a pagination scheme). 2024–2026 only. Measured — see open question #1. |
| `/games/teams`, `/games/players` | Box scores for completed games. |

### Bucket C — Weekly in-season (current season only)

Two different change patterns live here — the review split them (amendment, 2026-08-14):

**C1 — genuinely revisionist data: re-pull the full current season weekly.** Ratings and
cumulative stats revise retroactively, so append-only is wrong for them; staging's
latest-file-per-season rule handles the overlap.

| Endpoint | Note |
|---|---|
| `/games?year=2026` | Results refresh — one cheap season-scoped call. Also absorbs schedule growth: the 2026 schedule currently lists 1,638 games vs 2024's 3,747, because lower-division schedules aren't fully published yet. Expect the count to climb; not a bug. |
| `/rankings` | New poll weekly. |
| `/ratings/sp`, `/ratings/srs`, `/ratings/elo` | Revise retroactively — full-season re-pull, don't append. |
| `/stats/season`, `/stats/game/advanced` | Cumulative; same reasoning. |
| `/ppa/*` | Cumulative. |

**C2 — immutable-once-complete data: pull current week + prior week only.** Bucket B's
immutability logic applies *within* a season too: Week 3's plays don't change in Week 9.
The original draft re-pulled the whole current season weekly, which by Week 12 means
re-pulling eleven weeks of immutable PBP every week — the volume driver, for nothing.
The prior-week re-pull exists to catch stat corrections (this resolves original open
question #3). Consequence for staging: dedup for these endpoints is per **(season, week)**,
not per season — `distinct on (fetched_year, fetched_week)` where `stg_games` uses
`distinct on (fetched_year)`. Same idea, different key; easy to get wrong by copying the
existing model.

| Endpoint | Note |
|---|---|
| `/plays?year=2026&week=` | Current + prior week. Highest volume endpoint. |
| `/drives` (2026, by week) | Same pattern. |
| `/games/teams`, `/games/players` (2026) | Box scores; same pattern. |

### Bucket D — Pre-game / time-sensitive

Value decays fast; a stale pull is worse than none.

| Endpoint | Note |
|---|---|
| `/lines` | **Decided (Marc, 2026-08-14): in scope, displayed on the site, pulled DAILY during the week a game is played.** Line movement is itself the signal — action shifting toward/away from a team, or a major injury/player issue — so this endpoint breaks the latest-file-only staging rule: **staging keeps every snapshot** (keyed by fetch time), and movement across snapshots is first-class data a mart can expose (e.g. open → current → close per game). Runs on M3's daily schedule. |
| `/metrics/wp/pregame` | Pre-game win probability; pull before each slate. |

Note the CFBD terms posture for lines is the same as all other data: display on the site
is fine, redistribution is not. Lines are shown as context, not as a betting product.

### ~~Explicitly out of scope for phase 1~~ — RESCINDED 2026-08-15

`/draft/*`, `/recruiting/*`, `/player/portal`, `/talent` were excluded when scope was
site-pulled. Under the amended capture-maximal policy they are swept like everything else
(all returned real data at our tier). The exclusion that remains is *cost-based, not
topic-based*: per-game fan-outs (`/game/box/advanced`, `/metrics/wp`, ~15k calls per
two-season backfill) are built but not run — demand-driven, per the register.

### Open questions from the M1 draft — disposition at ratification (2026-08-14)

1. **Volume and rate limits** — ✅ *measured 2026-08-14 (Claude Code); no strategy needed.*
   Sampled 2024 weeks 1 and 8: 22,356 and 19,574 plays, 19.4 MB and 17.0 MB, ~2.4 s per
   fetch. Extrapolated over 3 seasons × 16 regular weeks:

   | Metric | 3 seasons |
   |---|---|
   | Plays | ~1,006,000 |
   | Raw JSON on disk | 0.87 GB |
   | Postgres after jsonb compression (~8.4×) | ~104 MB |
   | Total API fetch time | ~2 minutes |
   | Staging unnest across all of it | ~2 seconds (measured 85 ms for 41,930 plays) |

   No pagination beyond the per-week loop, no backoff, no resumability machinery. The
   one-blob-per-file raw design holds at this scale. Disk is the only thing to watch:
   ~280 MB per additional season. (±15% — two weeks sampled and averaged.)
2. **Betting lines** — *resolved:* in scope, displayed, daily in-week monitoring
   (Bucket D).
3. **Stat corrections** — *resolved:* folded into Bucket C2's current + prior week
   pull pattern.
4. **Manifest as scheduler** — *moved to M2 design.* Decide whether backfill
   skips-if-present via `RawManifest.exists()` or Airflow owns that state.

---

## Open decisions register

| Decision | Owner | Status |
|---|---|---|
| Endpoint scope + cadence (M1) | Cowork | ✅ Ratified 2026-08-14, amended (C split into C1/C2; lines daily). **[A 08-19] Lines cadence superseded — see season-aware row below.** |
| **Endpoint scope REVERSED: capture-maximal sweep** | Marc | ✅ Decided 2026-08-15 — full sweepable surface (63 endpoints) landed; out-of-scope list rescinded; demand-driven principle moves to the modeling layer. Registry (`src/endpoints.py`) is the operative cadence source. |
| Per-game fan-out (`/game/box/advanced`, `/metrics/wp`; ~15k calls) | Marc | ✅ Decided 2026-08-15 — **skip for now**; stays built and opt-in, runs only when a concrete analysis or site feature demands it. |
| Which dbt staging/marts to build beyond teams+games | Cowork | Demand-driven, standing. First two delivered with M2b (`mart_team_schedule`, extended `mart_team_season_record`); next models arrive when an analysis or M6 feature demands them. |
| Data horizon: 2026 framework now; full history for a curated dozen (+ `draft/*`) | Marc | ✅ Decided 2026-08-15 — see M2b; resolves CLAUDE.md's "depth TBD per feature" |
| JSON unnesting strategy: heavy multi-level payload → column work is coming (Marc heads-up 2026-08-15) | Claude Code proposes → Cowork reviews | Open — unnesting stays confined to staging (standing rule). Proposal wanted with the M2b models: cross-dialect dbt macros (`adapter.dispatch` for json extract/unnest) so staging models are dialect-neutral and the M4 Databricks migration stops growing with every model. Alternative: accept dialect SQL and pull M4 forward after M2b. |
| ~~Betting lines: display + daily in-week monitoring~~ | Marc | ⛔ **SUPERSEDED 2026-08-18** by the season-aware cadence. Daily captured one point per day and permanently lost intraday movement; CLV is uncomputable without it. In scope unchanged. |
| Week 0: does the 2026 calendar have one? | Claude Code verified 2026-08-14 | ✅ Closed — **no Week 0 exists in CFBD numbering**; early games fold into Week 1. **[A 08-19]** Terminology reconciled: "Week 0" is used colloquially for the 2026-08-27 → 08-30 opening slate. Both true, different vocabularies. |
| Weekly schedule: calendar-day or CFBD-week boundary? | Cowork | ✅ Decided 2026-08-15 — **fixed calendar days: Sunday results refresh + Tuesday sweep** (Monday games + stat corrections). |
| Lower-division (FCS/D-II) display scope | Cowork | Clarified 2026-08-15: the *pipeline* captures all divisions `/games` returns (already the ratified C1 design); what the *site* displays is an M6 presentation choice, deferred. |
| `/plays` volume strategy | Claude Code measured 2026-08-14 | ✅ Closed — no strategy needed; see appendix open question #1 |
| Serving/hosting: where always-on Postgres + Streamlit live; cost vs $0–15/mo guardrail | Marc | ✅ **Decided 2026-08-16: DigitalOcean Basic droplet, $6/mo, SFO region** — Docker Compose (serving Postgres + Streamlit + Cloudflare Tunnel), Cloudflare Access in front; upgrade to $12/2GiB only if memory pressure appears. M5 is GO. |
| Domain name for the site (needed by Cloudflare Access/Tunnel) | Marc | ✅ Done 2026-08-16 — **marc4data.com** registered via Cloudflare Registrar (zone auto-created, auto-renew on). Plan: cfdb site on a subdomain (e.g. `<site-host>`) behind Cloudflare Access; root available for the Netlify portfolio via CNAME. DO droplet also created (SFO, $6 Basic). Recurring total ≈ $7/mo vs $15 guardrail. **M5/M6 provisioning handoff to Claude Code is fully unblocked.** |
| Databricks PAT lacks `files` scope — Files API 403s; blocks `COPY INTO` volume upload | Marc | ✅ Closed 2026-08-17 — Files API now returns 200 on the token: the 403 was **scope propagation delay**, not a missing scope or Free Edition limit. `COPY INTO` volume path available for future loads. |
| Serving-db backups on the droplet | Claude Code | Open — nightly pg_dump (or equivalent) to the box + optional offsite copy; cheap insurance, define with the provisioning work. |
| Season-scoped `stg_teams` | Cowork | ✅ Ratified 2026-08-15 — implemented in the M2 backfill, reviewed |
| **M3 live validation** | Claude Code + Cowork | 🔶 Open — closes when the Sep 7 unattended cycle completes clean (first evidence 8/27–29). Pre-validation: SMTP alerting configured + tested; `m2/historical-backfill` merged to `main` via PR. |
| Postseason handling: weekly refresh hardcodes `seasonType: regular` for season-type endpoints | Claude Code | ▶ Endorsed 2026-08-16 to fix NOW (before unattended runs begin) — "before December" was a deadline, not a schedule. |
| Airflow local auth (`SIMPLE_AUTH_MANAGER_ALL_ADMINS=true`) | Cowork | Accepted 2026-08-15 as local-dev-only posture; MUST revisit if the Airflow stack ever binds beyond localhost. |
| Databricks target timing | Decided 2026-08-14 | Expiry: before M6 |
| Branch protection on `main` | Decided 2026-08-14 | N/A on Free private repo; PRs by convention |
| dbt tests in CI (needs Postgres service container) | Claude Code | 🔶 **[A 08-19] Appears delivered, confirm.** PR #11 added `ci/fixtures.sql` and a dbt job; CI caught six Phase-1 sources landing with no fixture data, which is exactly the gating this row asked for. Fixtures were rebuilt around hazards rather than happy paths. Mark ✅ once confirmed. |
| Retire `claude_code/project_setup_actions.md` | Cowork | ✅ Ratified 2026-08-14 — archived to `claude_work/archive/` |
| Retire `src/ingest_stub.py` | Claude Code | ✅ Approved for deletion 2026-08-16 — verified unreferenced. |
| M3 validation monitoring | Cowork | Scheduled 2026-08-16: Cowork check-ins Aug 30 (first genuine unattended Sunday run — alerting's proving day) and Sep 7 (Week 1 closes; M3 evaluated for close-out). |
| **Layer separation: schema-per-layer + locked serving** | Claude Code | ✅ **DELIVERED + accepted 2026-08-17** — schemas live in both engines (metadata-only migrations, checksum-verified data-neutral); `cfdb_read` role enforced at serving with every denial tested; `ci/check_layering.py` guard proven both directions; audit confirmed only marts ever reached serving. Landed before the Aug 27 freeze per the sequencing rule. See decision log. |
| Publish-into-Airflow: deploy-key decision | Marc + Cowork | **Open (2026-08-17)** — Claude Code needs a decision on how the publish job runs under Airflow (repo deploy key or alternative). Awaiting options; likely a read-only, single-repo GitHub deploy key. |

### Added 2026-08-18 / 08-19  **[A 08-19]**

| Decision | Owner | Status |
|---|---|---|
| **NORTH STAR: every page renders real data, now** | Marc | ✅ **Decided 2026-08-19.** Outranks milestone ordering. Metric is pages that RENDER (primary fact present), not tables that exist. 11 of 17 render; the seven-table NEXT set closes the gap. |
| **Freeze rule refined: evidence, not calendar** | Marc | ✅ Decided 2026-08-18. New objects nothing reads → no freeze. Cutover → gated on the parity test. Runtime changes with no parity proof → still date-gated. Cowork had wrongly applied the freeze to new construction, contradicting the strangler migration chosen to avoid exactly that. |
| **Three layers; `srv_` ratified; `serving` schema** | Marc | ✅ Decided 2026-08-18. `srv_` over `src_` (which reads as "source" beside `raw`). Own schema in both engines; publish job and `search_path` follow; CI layering guard extends. Finding that forced it: the three existing marts are **serving-shaped, not fact-shaped**. |
| **Strangler migration + parity test as cutover gate** | Marc | ✅ Decided 2026-08-18. `mart_*` untouched and serving the site until a dbt test proves each `srv_` view is row-for-row identical. Rejected in-place rename (breaks the live site at the moment of rename). Design uses `EXCEPT`, not a join — null semantics. |
| ~~Rename `mart_*` → `fct_*` before Aug 27~~ | Marc | ⛔ **SUPERSEDED 2026-08-18** — premised on the three tables being facts. They are not. Migration now gated on the dimensional layer existing, not on a date. |
| **Lines cadence: season-aware** | Marc | ✅ Decided 2026-08-18. Daily off-season, 4-hourly from 7 days before the first game. Window **2026-08-20 → 2027-01-27**. Permanent `0 */4 * * *` + short-circuit, so no seasonal schedule edit ever again. Gate landed and verified. |
| **`dim_team`: SCD2 REJECTED** | Cowork → Marc | ✅ Decided 2026-08-18. Season-scoping already answers realignment (which happens between seasons); no page asks "what was true on date D". Cowork originally specified SCD2; conceded to Claude Code's challenge. |
| **`fct_team_record`: derive from games; `/records` becomes a TEST** | Cowork | ✅ Decided 2026-08-18. Keeps internal consistency with the game spine; the reconciliation test is a stronger DQ artifact than a source swap. `tiebreak_rank` to be added — CFBD has no standings endpoint, so ordering is ours and the page must say so. |
| **`dim_provider` normalisation** | Cowork | ✅ Decided 2026-08-18. Preserve `provider_raw`, add mapped `provider_key`. No blind rename. Test must FAIL on an unmapped value. Real set verified: ESPN Bet, Bovada, DraftKings (+ "Draft Kings", a spelling variant). |
| **Player page returns to the wireframe** | Marc | ✅ Decided 2026-08-18. `fct_play` and `fct_player_game_stat` had zero pages referencing them. Economics changed: 2024 plays already landed; full 2024–26 measured at ~1M plays / ~0.87 GB / ~2 min API. Wireframe v0.3 owed. |
| **`spread` meaning — CLOSED** | Cowork | ✅ Closed 2026-08-19 by the Model Pack's own Data Info Sheet: **closing spread, negative means home favoured.** Open since 2026-08-17. Nuance: "closing" applies to completed games; the Tier-3 weekly drops are forward-looking, so the sign convention carries but "closing" does not. |
| **CFB Model Training Pack acquired** | Marc | ✅ 2026-08-19. Licensed, gitignored, never loaded to a database. 42-column export contract adopted verbatim. Inverted sign convention adopted verbatim and pinned by test. Weeks 0–4 flagged out-of-sample. See M7. |
| **Predictions permitted on BOTH engines** | Marc + Cowork | ✅ Decided 2026-08-19. `postgres_only` lifted. The pack dataset is never uploaded to either engine — only derived outputs, which the licence explicitly permits. The 42-column export contains none of the pack's 86 training features. Tiebreaker: postgres-only created serving views that could not build uniformly. |
| **Publication boundary defined** | Cowork | ✅ 2026-08-19 — `cfdb_publication_boundary.md`. `serving` IS the boundary. Hard exclusions: all 65 `raw.*` tables, the manifest objects, anything pack-derived. **Provenance rule:** same metric from the CFBD API is displayable; from the pack's `training_data.csv` it is not. |
| **Data dictionary source assessed** | Cowork | 🔶 Open, unblocked 2026-08-19. CFBD's OpenAPI spec documents **74/74 endpoints and 289/289 parameters** but only **4 of 1,017 fields**. `cfdb_data_dictionary.xlsx` generated as the skeleton; 151 Phase-1 fields need prose. Descriptions belong in dbt `schema.yml` with `persist_docs`. |
| **Airflow worktree pin** | Claude Code | 🔴 **Open — two incidents.** Airflow bind-mounts the working tree, so a `git checkout` changes production scheduling; the live schedule silently reverted to `@daily` once. "Merge quickly" is a habit, not a mitigation. Fix: bind-mount a worktree pinned to `main`, develop in the primary tree. |
| **Model Pack notebooks not yet run** | Marc | 🔴 **Open — the critical path.** `model_outputs/` does not exist, so the prediction pipeline is validated only against a synthetic export and CI fixtures. Marc runs notebooks 00 then 01–07, then `python -m src.load_predictions`. No design work stands between that and Edge Finder + Model Performance rendering. |
| **Excel export scoping rule** | Cowork | ✅ Rule decided 2026-08-19, implementation open. Exports scoped to what the user can already see — a week's slate, a team, a matchup, a season of results. **No full-corpus dump, no raw layer, no "download all seasons."** CFBD prohibits redistribution as raw data; this is the one feature where the boundary is judgement rather than structure. |
| **`srv_matchup` / `srv_today_edges` missing** | Claude Code | 🔶 Open — the last two serving views between prediction data and the Matchup/Today pages. Both pages render today; this is enrichment, not unblocking. |
