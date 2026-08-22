# cfdb — Phase 1 model specification

**Written:** 2026-08-18 · **Status:** BUILT — this documents what exists, not a proposal
**Governing:** decision log 2026-08-18 "BUILD NOW" · `cfdb_model_reconciliation.md` ·
`cfdb_team_identity_spec.md`

Built and validated in one arc, per the BUILD NOW directive. **160/160 dbt nodes pass on
Postgres and 160/160 on Databricks.** The three live marts are untouched and still serving
the site.

---

## 0. What exists now

| Layer | Schema | Objects |
|---|---|---|
| staging | `staging` | 8 (3 pre-existing + `stg_conferences`, `stg_venues`, `stg_calendar`, `stg_game_team_stat`, `stg_lines`) |
| dimensional | `marts` | 10 new + 3 untouched `mart_*` |
| serving | `serving` (new) | 6 |

### Row counts, both engines

| Object | Grain (uniqueness key) | Postgres | Databricks |
|---|---|---|---|
| `dim_team` | (season, team_id) | 34,061 | 34,061 |
| `dim_conference` | (season, conference_id) | 219 | 219 |
| `dim_venue` | venue_id | 844 | 844 |
| `dim_season` | season | 157 | 157 |
| `dim_week` | (season, season_type, week) | 424 | 424 |
| `dim_provider` | provider_key | 3 | 3 |
| `fct_game` | game_id | 110,102 | 110,102 |
| `fct_game_team` | (game_id, team_id) | 220,204 | 220,204 |
| `fct_team_record` | (season, team_id) | 30,221 | 30,221 |
| `fct_betting_line` | (game_id, provider_key, snapshot_ts) | 7,489 | 7,285 * |
| `srv_schedule` | game_id | 110,102 | 110,102 |
| `srv_scoreboard` | game_id | 110,102 | 110,102 |
| `srv_standings` | (season, team_id) | 30,221 | 30,221 |
| `srv_teams_index` | (season, team_id) | 34,061 | 34,061 |
| `srv_team_game_log` | (game_id, team_id) | 220,204 | 220,204 |
| `srv_line_movement` | (game_id, provider_key, snapshot_ts) | 7,489 | 7,285 * |

\* Not a model difference — a raw-input difference. The snapshot DAG's load task writes to
Postgres only (13 lines files); Databricks is loaded manually and has 11. The models agree;
the inputs do not. Registered below.

### Surrogate keys
`macros/surrogate_key.sql`, dispatched. md5 over `'||'`-joined parts with `~null~` as the null
token — `('a', null)` and `('a', '')` must not collide, and coalescing to empty string would
make them the same key. Every `dim_` carries a `*_sk` and retains its natural key; facts carry
both, because the natural id is what a human debugging a row recognises.

### Layer enforcement
`ci/check_layering.py` now knows three layers: sources are read only by staging, marts build
on staging, **serving builds on marts**. A `srv_` view reaching into staging fails the build.

---

## 1. The findings this build produced

Five things the data told us that no amount of specification would have.

### 1.1 CFBD returns the string `'#null'` for missing colours
Not JSON null — the literal seven characters. 29 primaries and 317 alternates in 2025.
Parsed as hex it yields garbage. Normalised in `stg_teams` via `clean_hex`; nothing
downstream ever sees it.

### 1.2 `color_source` had to be per-surface, and my first version was misleading
One label for two surfaces reported `adjusted` for teams whose primary was fine on light and
only needed blending on dark — overstating how often a brand colour is altered. Split into
`color_source_light` / `color_source_dark`, with `color_source` retained as the worse of the
two for the data-quality view.

The truthful picture for 2025: **615 of 681 teams keep their primary colour on the light
surface.** Adjustment concentrates almost entirely on dark (337 teams). The light theme is
brand-faithful; the dark theme is where the design assumption strains.

### 1.3 The 2020 season was played in spring, and we never fetched it
`/calendar` carries four season types, not two: `regular`, `postseason`, and the 2020-only
**`spring_regular` / `spring_postseason`** — FCS moved its 2020 season to spring 2021.

`src/backfill.py` only ever requests `regular` and `postseason`, so those games were never
ingested. The reconciliation test against `/records` found it: 21 team-seasons diverge,
including Sam Houston's 10-0 FCS title run, which is absent from our game spine entirely.

**This is an ingestion gap, not a model defect.** Registered below.

### 1.4 CFBD emits DraftKings twice in the same response
`DraftKings` and `Draft Kings` appear for the same game and snapshot, with identical spread,
formatted spread and total — but the `Draft Kings` row carries **null moneylines**. 56
game-snapshots affected.

They are one book, so mapping them to one key creates a genuine grain collision. Resolved in
`stg_lines` by keeping the most complete row, tie-broken by canonical spelling, and proven
safe by `assert_provider_dedup_is_lossless`: the discarded row must never carry a value the
kept row lacks. Without that test this would be silent data loss dressed as deduplication.

### 1.5 Division II/III records diverge from CFBD's own `/records`
Six 2025 teams differ by exactly one game, in both directions. That is CFBD disagreeing with
itself at the lowest classifications — `/records` and `/games` do not agree on which games
count for a D-III team playing outside its division. The reconciliation test is scoped to
FBS/FCS; widening it would mean a permanently red test, which is worse than no test.

---

## 2. The parity tests — the cutover gate

Two `srv_` views replace live marts. Both parity tests **pass today**.

| Test | Compares | Result |
|---|---|---|
| `assert_parity_srv_standings` | `srv_standings` vs `mart_team_season_record`, 14 shared columns | PASS |
| `assert_parity_srv_team_game_log` | `srv_team_game_log` vs `mart_team_schedule`, 24 shared columns | PASS |

### Why `EXCEPT` and not a join
A join on the grain key with `=` gives **false passes on nulls**: `null = null` is unknown, so
a differing-but-null column is skipped and the row reads as identical. `EXCEPT` uses
`IS NOT DISTINCT FROM` semantics — nulls equal nulls, nulls differ from values — which is
exactly what row identity means. No `coalesce` anywhere: coalescing would mask a genuine
null-vs-value difference.

### The comparison contract

| Concern | Rule |
|---|---|
| Column set | The **intersection** — every column the mart has. A column added to `srv_` is fine; a column missing fails. |
| Column order | `EXCEPT` is positional, so both sides list columns explicitly and identically. Never `select *`. |
| Types | Explicit casts per column, so `int` vs `bigint` or numeric scale is not read as a data difference. |
| Floats | `win_pct` rounded to the mart's declared 3dp before comparison. |
| Nulls | Handled by `EXCEPT` semantics. |
| Row order | Irrelevant — set semantics. |

### What a failure reports
Offending rows labelled `missing_from_srv` or `extra_in_srv`, with the grain key and every
compared value. **A changed value produces two rows sharing a key** — the signature of a
modified row rather than an added or dropped one.

Proven to detect: perturbing one team's win count surfaced exactly that pair.

```
missing_from_srv 2024 team=197 wins=3
extra_in_srv     2024 team=197 wins=4
```

### Scaffolding, deliberately
When a `srv_` view takes over and its mart is dropped, its parity test is deleted **in the
same commit**. A parity test against a dropped model is a broken build; one kept against a
frozen copy asserts agreement with something no longer maintained.

---

## 3. Week 0 readiness (2026-08-27 → 08-30)

Week 0 is FCS-heavy on Thursday and Friday, which makes it a real test of the non-FBS
opponent path rather than a formality.

### What will actually be exercised

| Object | Exercised how | What I expect |
|---|---|---|
| `fct_game` | ~20 new games appear as `/games` refreshes | Fine. 2026 rows already present as futures; `is_completed` flips. |
| `fct_game_team` | 2 rows per game; box scores appear only after play | `has_box_score = false` on Thursday, true within a day. **This is the column to watch.** |
| `fct_team_record` | First non-zero 2026 records | Reconciliation vs `/records` may diverge briefly — CFBD updates the two endpoints at different times. |
| `dim_team` | 2026 already loaded, 684 teams | Stable. Colour coverage on FCS teams is the risk. |
| `fct_betting_line` | 4-hourly from 08-20 | The volume test. ~6 snapshots/day × 4 days. |
| `srv_*` | All six rebuild on each dbt run | Parity tests must keep passing as data changes. |

### What I expect to break, specifically

1. **FCS teams with no colour.** 29 of 681 teams have no primary colour. Week 0 is
   FCS-heavy, so the `fallback` grey path gets its first real exposure. Not a failure — but
   if a Thursday slate renders as a wall of grey, that is the signal the identity spec
   anticipated.
2. **`has_box_score = false` for FCS games.** `/games/teams` coverage for lower divisions is
   unverified. If box scores never arrive for FCS games, `fct_game_team`'s stat columns stay
   null for most of Week 0 — correct behaviour, but it will look like a gap.
3. **Parity drift on the first completed games.** `mart_team_schedule` and `srv_team_game_log`
   derive `result` and `margin` through different code paths now. They agree today on 220,204
   historical rows; the first *newly completed* game is the real test.
4. **`tiebreak_rank` churn.** With one game played, conference ordering is nearly arbitrary.
   Expected, and why `tiebreak_basis` labels the rule.

### What I will be watching
The tests, not the dashboards: the two parity tests, `assert_no_unmapped_provider` (a new
sportsbook appearing for Week 0 lines is plausible), and `has_box_score` coverage by
classification.

---

## 4. Model surface — what I would cut

The brief asked for ceremony to be named.

**`dim_season` — I built it, and I would still cut it.** 157 rows of `season`, `season_label`,
`first_game_date`, `game_count`. Nothing joins to it. Every consumer already has `season` as
an integer on the fact, and no page shows a season attribute that
`select distinct season from fct_game` would not answer. It exists because dimensional
orthodoxy says a key should have a dimension, not because anything needs it. Cutting costs
nothing and removes an object from every future migration.

**`dim_venue` — keep, but it is not doing what its name implies.** `/games` carries the venue
*name* and no usable venue id, so it cannot be joined to `fct_game`. It stands alone as a
venue attribute lookup (capacity, dome, elevation) for a future weather block. That is real,
but it is not a conformed dimension until a join key exists.

**Everything else earns its place.** `dim_week` is bounded but honest; `dim_provider` is three
rows that prevent a silent split; the four additive `srv_` views are what the site reads.

---

## 5. DECISIONS NEEDED

1. **The 2020 spring-season ingestion gap.** `src/backfill.py` should add `spring_regular`
   and `spring_postseason` to `SEASON_TYPES` and re-backfill 2020. This is a runtime-path
   change to ingestion (new API calls, new raw files) — it is additive and safe, but it is
   not a "new object nothing reads", so I have not done it unilaterally. ~21 team-seasons of
   FCS history are currently wrong.
2. **Databricks lines lag.** The snapshot DAG loads Postgres only. Either add a Databricks
   load step, or accept that Databricks trails until a manual load — and say which, because
   `fct_betting_line` is the one table where lag is permanent data divergence rather than
   staleness.
3. **Cut `dim_season`?** My recommendation is yes (§4).
4. **`is_power_conference`** — I did **not** build it. It is cfdb's editorial judgement and
   CFBD has no such flag. Define the rule or leave it out.
5. **`tiebreak_rank` rule.** Currently conference win pct → overall win pct → point
   differential → school name. Real tiebreakers are head-to-head and conference-specific.
   Acceptable for Phase 1 with `tiebreak_basis` labelling it?
6. **Box-score column set.** I pivoted 15 of 35 categories. The other 20 remain available in
   `stg_game_team_stat`. Confirm, or name the pages needing more.

---

## 6. Unverified

- **`/games/teams` coverage for FCS/D-II.** Box scores exist for 3,340 games; whether Week 0's
  FCS games get them is unknown until Thursday.
- **`logo_path` is null everywhere** — the fetch-and-cache task (identity spec D3) is not
  built. The column exists so the app never changes shape.
- **Contrast macro on Databricks** builds and runs, but I have not compared colour *values*
  across engines row by row — only row counts. Float arithmetic could differ in the last
  decimal and change a rung near the 3:1 boundary.
- **`srv_` publish path untested.** The publish job still points at `marts`. Moving it is a
  cutover step, gated on parity, and deliberately not done here.
