# cfdb 046 — where everything is, for the register

**From:** Code · **To:** Cowork · **Date:** 2026-09-05
**Status:** a catch-up. Nothing here asks for work; it asks for the register to be made true.

Marc: *"Can you draft a prompt for Cowork so that it catches up and records where everything is?"*

The register stops at **R-259**. Since then thirteen PRs have merged and one is open. Every
number below is cited in code and every claim is measured — the file each one lives in is
named so Cowork can verify rather than take this document's word.

---

## PART 0 — R-275, WHICH IS THE REASON THIS DOCUMENT EXISTS

Prompt 044 asked what R-260, R-261 and R-262 were. It was answered in chat and never reached
the register, so prompt 045 asked again as R-275. **Here it is in a form that can be pasted.**

| # | What it was | Cited in |
|---|---|---|
| R-260 | **The Market block on the Scores sheet.** Twelve columns between Result and 1st downs: ATS margin, the cover verdict and line-implied points, per team, from the closing line always and the opening line only where it differs. Required twelve new columns on `srv_game_team`. | `dbt/models/serving/srv_game_team.sql` |
| R-261 | **The game band painted onto the cells** rather than drawn by a conditional format. Two rounds of CF were invisible on Marc's screen; a painted fill is a real `cellXfs` entry a test can read back. Cost: it no longer follows a re-sort, which is why `Game #` is in the sheet as data. | `site/lib/workbook.py` |
| R-262 | **Cover verdicts as words** — Yes / No / Push / Pending — instead of ■ □ ══, on Scores only. Schedule keeps the glyphs: they sit in a dense block sharing one legend, where Scores has two cover columns among 151. | `site/lib/workbook.py` |

### And a numbering collision, resolved

R-263 and R-264 were assigned **in code, without register entries** — the same failure. Cowork
then issued R-263…R-271 for prompt 044. Per the R-181/R-182 precedent the sanctioned numbers
won and the self-assigned ones moved:

- **R-263** → the Excel Export page describing the workbook it builds. Now cited nowhere in
  code; it survives only in PR #121's title. **Cowork's R-263 (the backfill ask) became R-275.**
- **R-264** (self-assigned, the deploy rewrite) → **R-273**. Prompt 044's R-264 (the export
  reorder) keeps the number.
- **R-272 was never used.** It is free.

---

## PART 1 — WHAT SHIPPED, R-255 TO R-293

All merged to `main` and deployed unless marked otherwise.

### The Scores export sheet
| # | |
|---|---|
| R-255 | Scores veers off Schedule onto `srv_game_team` — game × team grain, so a game is two rows |
| R-256 | `regular` before `postseason`; a plain sort puts January's bowls above September |
| R-257 | Banding on a real `Game #` column, not row position |
| R-258 | One header fill per category band, measured for contrast and dichromatic separation |
| R-259 | 2dp on that sheet only; naturally-integer columns measured over 110,879 rows |
| R-264 | The v2 order — a permutation, 144 in 144 out, seven keys to a new **Ancillary** band |
| R-265 | Freeze moves to `Pts for` |
| R-266 | `srv_game_team` gains identity and provenance — 14 additive columns |

### The Scores page
| # | |
|---|---|
| R-267 | The stacked scoreboard. The stacking **is** the grain — no pivot, no pairing logic |
| R-268 | Six tabs over the colour bands, mapped from `SCORES_BLOCKS` |
| R-269 | Horizontal scrolling. `width:100%` + percentage colgroups **cannot** overflow |
| R-270 | Compound default sort; a user sort stacks on it via stable mergesort |
| R-271 | Footer: "About Marc" with an inline SVG globe |
| R-278 | Completed games only — a **parameter on the shared statement**, not a second query |
| R-279 | `HIDDEN_ON_PAGE` as a **partition** of the sheet, not "at most one tab" |
| R-280 | The page printed the season as `2,025` |
| R-281 | The scroll container had no height — the horizontal bar sat ~5,300px below the fold |
| R-282 | Header labels set a **floor** under column width. 29,843px → 13,354px, 55% narrower |
| R-283 | The tab now lives in the URL |
| R-284 | Logo and rank, via `team_cell` / `team_link` |
| R-285 | `record_before_display`, joined on **all four** keys |
| R-286 | Pregame/postgame Elo — already in the warehouse, never surfaced at this grain |
| R-287 | **996 team anchors, one destination, zero carrying a team** |
| R-288 | The matchup links worked and were invisible |
| R-289 | Workbook hyperlinks with the slug column **named**, not derived |
| R-290 | Four columns into the Game block; pregame-only on Schedule |
| R-293 | One click, one history entry |

### Infrastructure
| # | |
|---|---|
| R-273 | Faster, safer deploys (was self-assigned R-264) |
| R-274 | The distribution band withdrawn from the Schedule page — presentation only |
| R-291 | The Data dictionary sheet — **open in PR #127** |

---

## PART 2 — FINDINGS WORTH A DECISION-LOG LINE

Six of these are the project's own recurring failure — *a true fact about the wrong object* —
and they are recorded because the pattern is more valuable than any one instance.

**1. `deploy_main.sh` was not deploying `origin/main`.** The pipeline half reset the droplet
to main; the site half tarred the **local working directory**. Deploying from a feature branch
put un-merged code on the live site, which happened for about twenty minutes on 4 September.

**2. The deploy rebuilt 95 models to ship one** — 328s against 18s, measured. `state:modified+`
is both faster and **stricter**: the old directory diff could not see an upstream mart or macro
change, and its own comment said so.

**3. …and that fix introduced a staleness.** The catalogue models declare no ref on what they
describe, so `state:modified+` can never select them. `srv_game_team` had 223 columns and the
dictionary knew 203. Fixed with a second pass in PR #127.

**4. A view rebuilt by one DAG was deleting a model owned by another.** dbt's Postgres view
materialisation ends with `drop view … cascade`. `cfbd_scores_refresh` rebuilds `fct_game_market`
every two hours; `int_week_metric_value` was a view on it. Four consecutive lines runs failed.
**CI could not see it** — one `dbt build` from empty never rebuilds a parent under a child.

**5. Two wrong sources for the theme, in sequence.** `prefers-color-scheme` answers what the
OS prefers; `st.context.theme` answers what the app renders but **one rerun late**. Tokens now
derive from `Canvas`/`CanvasText`, which follow the `color-scheme` Streamlit sets.

**6. Opacity applies to the whole cell.** `.cfdb-table th { opacity:.65 }` was harmless until
the header became sticky, at which point it could not hide anything sliding under it.

**7. Redundant query-param writes were doubling browser history.** Streamlit **pushes** on a
Python-side write. `matchup.py` wrote 2 identical params on arrival, `filters.game_scope()` 5
on every render. Back needed two presses.

**8. Twenty columns were undocumented** and the new dictionary sheet would have advertised it.
Six were Code's from this round; fourteen were `srv_game`'s, pre-existing. Both views are now
371 of 371 authored — which needed **two dbt passes**, the ordering constraint demonstrating
itself.

---

## PART 3 — DATA FACTS WORTH KEEPING

- **CFBD's Elo does not move for a game against an unrated opponent.** All 125 such games in
  2025 have a delta of exactly 0, against 18 of 1,524 rated matchups. A zero beside an FCS
  opponent means *"this did not count"*, not *"the rating happened not to change"*.
- **Elo coverage is 92.8% of 2025 FBS rows** — and that gap is entirely non-FBS teams:
  133 of 133 FBS rows have a rating, 0 of 33 FCS rows do.
- **Possession does not always sum to 60:00.** Of 3,411 games with both rows populated, 3,261
  total exactly 60, 14 exceed it (overtime) and 136 fall short. The column surfaces it.
- **The line moved on 85% of 2025 FBS games** — spread on 753 of 888, total on 756. The
  "only when different" rule suppresses far less than it sounds like.
- **Line movement changed the cover verdict on 190 of 3,200 graded rows** (5.9%).
- **The AP Top 25 is the only poll joined** (`fct_game.sql`), and the Scores page now says so.

---

## PART 4 — OPEN, AND WHOSE CALL IT IS

**Marc's, outstanding:**
1. **The 151st column.** He ratified 144. It is now 151: +rank, record, pregame, postgame
   (R-290), +`matchup_url` **export-only, which he can still veto**, +`elo_delta`, +`won`.
2. **A seventh tab.** Six tabs cover seven bands; Ancillary rides at the far right of Game
   Results. A seventh is a one-line change.
3. **R-290c — pregame Elo on the Schedule PAGE.** Not started. The ask was to *measure the
   real estate and propose*, not to decide. The Excel half shipped.
4. **`ALERT_WEBHOOK_URL`.** Still empty. Needs a Slack or Discord incoming webhook — **not** a
   healthchecks URL. Without it the droplet can report silence but not failure detail.
5. **SMS alerting.** Raised 2026-09-05 and **tabled by Marc** — "I'd like to table that for
   now." Recorded so it is not lost. Suggest a number.

**Recorded, deferred by Marc's own sequencing:**
- **R-292** — this table style as a third option on Schedule, contingent on Scores being right.

**Code's, raised and not yet actioned:**
- **`/opt/cfdb-pipeline/docker-compose.yml` exists only on the droplet.** It is in no compose
  file in the repo and `deploy_main.sh` does not sync it. Production config in exactly one
  unversioned place — the same class the deploy script's header was written about. It has now
  been hand-edited twice.
- **Three stale mirrors in `docs/`**, reported under R-254 and not acted on.
  `page_to_mart_matrix_v3.xlsx` names 4 views that do not exist and omits 11 that do,
  including `srv_game`. Recommendation was **delete**; `data_dictionary.xlsx` is a different
  artefact (a CFBD OpenAPI seed) and should stay.
- **`distribution.panel()` and `thumbnail()` are called by nothing** after R-274. Deliberate —
  Marc's requirements are coming and will likely land on Scores.

---

## PART 5 — THE STATE OF ALERTING, WHICH CHANGED TODAY

| Path | Status |
|---|---|
| healthchecks.io — `scores_refresh` 2h/3h | **live**, matches the repo's own 5h budget |
| healthchecks.io — `lines_snapshot` 4h/5h | **live**, confirmed by the real 08:00 DAG run |
| GitHub dead-man's switch | live; reports only tasks whose **latest** run failed |
| Email from the droplet | **impossible** — outbound SMTP blocked on every port |
| Webhook (failure detail) | **not configured** |

The blocker was never the URLs. The pipeline's compose lists every variable explicitly, so
`.env` alone would have left `ping()` printing *"no monitor configured"* while everything
looked configured.

**Silence is now detected. Failure detail still cannot leave the box.**

---

## WHAT COWORK IS ASKED TO DO

1. Backfill **R-260, R-261, R-262** (Part 0) and record the R-263/R-264/R-273 resolution.
2. Add **R-264…R-293** to the register from Part 1. R-272 is free; R-276 and R-277 were never
   used by Code.
3. Take Part 2 into the decision log — particularly (3), where a Code improvement introduced a
   regression, and (4), the CI blind spot.
4. Give the tabled **SMS** item a number.
5. Rule on Part 4's five open questions, or hand them back with a sequence.
