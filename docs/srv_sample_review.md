# Review — `srv_sample.xlsx`

**17 serving views · 18 sheets · profiled column-by-column, 20 August 2026**

A1 landed and it landed well. The column counts are far above the audit that prompted it —
`srv_matchup` 7 → 74, `srv_today_edges` 8 → 52, `srv_edge_finder` 4 → 43, `srv_schedule` 3 → 44.
`as_of_ts` is on **all 17 views at 100%**. Slugs, contrast colours and de-vig all verify. Both
previously-absent views (`srv_team_overview`, `srv_odds_board`) exist.

**Section 1 below is a correction to my first reading of this file, not a finding.** The rest
stands.

---

## 1. CORRECTED — no 2026 predictions is **expected**, and the rule is already in the data

**My original reading of this was wrong.** I found that `srv_today_edges` (211 games, 2026 week 1)
has 0% on every model column and called it the headline emergency. Marc's correction: **CFBD does
not ship 2026 feature files until Week 5**, because the models need several weeks of current-season
performance before they can say anything about how *this year's* teams actually play. The training
notebooks were run last night; the models exist. What is missing is 2026 **feature data to score**,
and it is missing on purpose.

So the fact was right and the interpretation was wrong — the same error I have now made four times
on this project: observe something true, conclude what it means without checking the domain
constraint.

### The rule is already a column, and it is in the wrong views

`srv_edge_finder` carries **`training_week_floor`, constant at 5** across all 1,000 sampled rows.
That is exactly this rule, already encoded as data rather than folklore.

It is **absent from `srv_today_edges` and `srv_matchup`** — the two views that most need it, because
those are precisely the views that will be empty for the first four weeks and have to explain why.

**Add `training_week_floor` to both.** Then the Empty state is driven by data instead of a hardcoded
"Week 5" string, and it stays correct if the floor ever changes.

### What this actually changes — mostly for the better

**Four weeks of runway.** Predictions are not needed until roughly 1 October, not 5 September. That
materially de-risks Track A: the shared foundation and the 18 pages have real time.

**Weeks 1–4 are a designed state, not a degraded one.** This is the distinction the four-state
contract exists for, and it is worth getting right because it **recurs every single season**:

| Page | Weeks 1–4 |
|---|---|
| Odds Board | **Full.** Pure market data, no model dependency |
| Line Movement | **Full.** Same |
| Schedule, Scores, Standings, Teams, Team page, Rankings, Stats | **Full.** No model dependency |
| Today | **Slate + market renders.** Prediction strip shows the Week-5 explanation |
| Matchup | **Everything but the model block.** Market, venue, form, history all render |
| Model Performance | **Full** — it shows the 2025 backtest, already labelled as such |
| Edge Finder | **The only page with nothing to show.** An edge is model-minus-market; without a model there is no page |

**This is Empty, not Degraded.** Degraded means we have not built something. Empty-with-a-reason
means the data does not exist yet and here is why. Weeks 1–4 are the second, and the copy should say
so plainly — *"Model predictions begin in Week 5. The 2026 model needs several weeks of current-season
results before it can forecast this year's teams."* That sentence is a credibility asset, not an
apology: it says the model refuses to guess before it knows anything.

**Edge Finder needs a decision.** It is dark for a month. Either it carries the Week-5 explanation as
its whole page, or it is hidden from nav until Week 5 — and per AC-G.51 we do not hide pages, so it
carries the explanation. Worth confirming that is the intent rather than assuming.


---

## 2. Verified good — do not re-litigate these

| Check | Result |
|---|---|
| `as_of_ts` on every view | **17 of 17 at 100%.** AC-G.54 met |
| Team slugs | `alabama`, `east-carolina`, `auburn` — lowercase, hyphenated, from a column. AC-G.14 met **where present** (see §3) |
| Contrast colours | `color_on_light` `#0c2340` / `color_on_dark` `#f26522` for Auburn, with `color_source` = `alternate`. AC-G.26 met, and `color_source` is exposed per AC-7.2 |
| Eastern time | `start_date` 16:00 → `start_date_et` 12:00. Correct EDT offset, applied in dbt. AC-G.34 met |
| De-vig | −10000 / +1600 → `market_implied_home_win_probability` 0.9439, `devig_method` = `multiplicative`. **Arithmetic verifies exactly.** Raw moneylines preserved alongside |
| Attribution as data | Full string present on `srv_edge_finder` and `srv_model_performance` at 100% — "cfdb model, built on a licensed CFB Model Training Pack (2026 Edition). Not an official CollegeFootballData.com prediction." |
| `description_status` | Live with real values: 276 `authored`, 724 `UNDOCUMENTED`. Not a placeholder |
| Dictionary covers serving | `layer` = serving 525, dimensional 385, staging 90 |
| System health has content | 224 signals: data_quality 153, freshness 66, documentation 3, quota 2. Severity 220 ok / 3 warn / 1 unknown |

**The model numbers I have been quoting verify exactly against the view:**

| Model | MAE | Mean error | SU | ATS | n |
|---|---|---|---|---|---|
| `ridge_margin_expanded` | **11.750** | +0.684 | **73.5%** | **51.4%** | 567 / 553 scored |
| `random_forest_score` | 12.765 | +0.907 | 68.8% | 48.6% | 567 / 553 |

One thing worth noticing that nobody has mentioned: **mean margin error is +0.68 against an MAE of
11.75.** Bias is about 6% of error — the model is close to unbiased, it is just imprecise. That is a
meaningfully better failure mode than a model that leans, and it is a fair thing to say on the
Methodology page.

---

## 3. Real defects — five

### 3.1 Logos are 0% populated. Everywhere.

`logo_url`, `home_logo_url`, `away_logo_url`, `logo_source_url`, `logo_path` — **null in all six
views that carry them**, across every sampled row. Not a season artefact; `srv_teams_index` and
`srv_team_overview` are team-grain and still empty.

AC-G.27 and AC-G.28 are unmeetable. Every game card, every table row, every team header. The
monogram fallback in AC-G.28 covers it visually, but if it fires 100% of the time then the site has
no logos at all and the fallback is the design rather than the safety net.

### 3.2 `ats_record_display` renders `0-0-0` for seasons that have not happened

851 of 1,000 sampled rows on `srv_team_overview` show `0-0-0` — every 2026 team. In the **same row**,
`wins`, `losses` and `record_display` are correctly **null**.

One table, two treatments of "hasn't happened yet." This is AC-G.32 and AC-G.6 exactly: a fabricated
zero where the honest value is null. A user reading `0-0-0` sees a team that has bet 0 and gone
0-0-0, not a season that has not started. `ats_wins` / `ats_losses` / `ats_pushes` have the same
problem, as do `ats_as_favorite_display` and `ats_as_underdog_display` at `0-0`.

### 3.3 `srv_model_performance` has no segment structure

6 rows — one per model. No `segment_type` / `segment_value`. This was in A1's scope and is the one
scope item that did not land.

Consequence: the by-week table, the by-conference breakdown, the edge-bucket table and the
calibration decile plot on Model Performance **have no source**. The page can render its headline KPI
row and the model registry, and nothing else.

### 3.4 Four of six models report `ats_accuracy_pct` as null with `cover_scored` = 0

Correct and honest — the win-probability models produce no margin, so they cannot be ATS-scored. But
the page must render `—`, not `0.0%`. Given 3.2 exists in a neighbouring view, this needs stating
rather than assuming.

### 3.5 Slug coverage is incomplete, and the gaps are the non-FBS stubs

`team_slug` is present on `srv_rankings`, `srv_team_overview`, `srv_team_stats`; `home_team_slug` /
`away_team_slug` on `srv_schedule`, `srv_odds_board`, `srv_today_edges`. **Absent** from
`srv_teams_index`, `srv_standings`, `srv_team_game_log`, `srv_scoreboard`, `srv_matchup`.

So the Teams index and Standings — two of the most natural places to click a team — cannot deep-link.

Separately, on the week-1 slate: `away_team_slug` 95.7%, `away_abbreviation` 94.8%,
`away_color_on_light` 95.7%. **About 9 of 211 opening-week games have an away team with no
`dim_team` row** — the non-FBS opponent stubs. Expected under the division-scope decision, but the
stub needs a slug or those rows cannot link and will render an uncoloured, unabbreviated opponent.

---

## 4. Expected nulls — NOT defects. Do not spend time here.

The sample is sorted season-descending, so most sheets are **2026 games with `is_completed = False`**.
These are correctly null and would be wrong if populated:

- **Results:** `home_points`, `away_points`, `actual_margin`, `winner`, `is_upset`, `attendance`,
  `result`, `margin`, and all box-score columns on `srv_team_game_log`
- **Post-game metrics:** `excitement_index`
- **Polls:** `home_rank` / `away_rank`, and `ap_rank` / `coaches_rank` / `committee_rank` at ~31% on
  `srv_rankings_compare` — no 2026 polls yet
- **Records:** `wins` / `losses` / `record_display` / `conference_standing` at 31% on
  `srv_team_overview` and `srv_teams_index` — that 31% is precisely the 2025 portion of the sample
  (316 of 1,000 rows)
- **`division` at 7.9%** — most conferences no longer have divisions. The UI must handle absence as
  normal, not as missing data

**`srv_edge_finder`'s sparse prediction columns are structural, not gaps.** `predicted_margin` is
27.4% populated — and the market split is moneyline 726 / spread 274, with the two margin-producing
models contributing exactly 274 rows. Margin models feed the spread market, win-probability models
feed the moneyline market. The view is coherent; the page just must not show all six models at once
or it is mostly em-dashes.

---

## 5. Open questions — flagged, not concluded

1. **`is_default_actionable` is `True` for 100% of rows** in both `srv_edge_finder` (1,000) and
   `srv_today_edges` (211). If it is always true it filters nothing. Is it meant to select one model,
   and is it not yet doing so?
2. **Two different documentation-coverage numbers in one workbook.** `srv_system_health` reports
   "239 of 385 columns documented" (62%); `srv_data_dictionary` shows 27.6% documented over 1,108
   rows. Different denominators — 385 looks like the dimensional layer only. Whichever the page
   quotes should be the one AC-16.3 renders, and the other should say what it is scoped to.
3. **`srv_edge_finder` totals 3,366 rows; predictions are 567 × 6 = 3,402.** A 36-row shortfall,
   probably games with no line. Worth a one-line explanation rather than an investigation.
4. **`network` is 0% on the week-1 slate**, 17 days out. TV assignments for opening weekend normally
   exist by now. Landed-but-unmodelled, or genuinely absent upstream?
5. **`srv_matchup`'s market and model blocks are 100% null** — but the sample is 2026 weeks 7–12,
   where no lines exist and no predictions have been made. **This file cannot tell us whether
   `srv_matchup` is populated for 2025.** One query settles it; do not assume either way.

---

## 6. What I would do with this

**Scoring the 2026 fixtures is not an action item — it is a calendar event.** Week 5 data arrives
from CFBD, it goes through the trained models, and the existing `load_predictions` path picks it up.
Nothing to schedule except the reminder.

**So Track B's order stands as written, with `fct_team_week_rating` first.** In the meantime:

1. **Logos** — one dbt change, unblocks AC-G.27/28 across six views
2. **Slugs onto the five views that lack them**, plus a slug for non-FBS stubs
3. **Null the ATS displays** where no games have been played
4. **`segment_type` / `segment_value` on `srv_model_performance`** — the one A1 item outstanding
5. **`training_week_floor` onto `srv_today_edges` and `srv_matchup`** — so the Week-5 empty state is
   data-driven rather than a hardcoded string

Items 1–3 are small, and together they are the difference between pages that render and pages that
render *correctly*. Item 4 is the only one that is real work.
