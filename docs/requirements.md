# cfdb — Site requirements

**Version 1.3 · 20 August 2026 · builds to wireframe v0.3**

> **v1.3 `[A 08-20c]` — build order narrowed and split into two tracks.** v1.2's completeness pass
> depended on facts v1.2 itself deferred, so it could not complete. Scope restated as *complete with
> respect to built facts*; deferred facts render Degraded. All 18 page sections now carry a readiness
> line, per AC-G.56. `prediction_interval_low`/`high` has no source and will not be invented.
>
> **v1.2 `[A 08-20b]` — amended after Claude Code's column-level audit.** The reconciliation
> answered *existence*; this document then treated existence as *readiness*. 104 of 135 required
> serving columns are absent. A readiness definition is added below, the build order is rewritten,
> and four page-level corrections are applied. v1.2 changes carry `[A 08-20b]`.
>
> **v1.1 — amended after Claude Code's Task 1 reconciliation (PR #18).** Changes carry an `[A 08-20]`
> marker. Two of my inferences were wrong, three acceptance criteria were unbuildable as written,
> and one framing error is corrected below. The reconciliation is the most useful thing this
> document has produced so far — it worked exactly as Task 1 intended.

The contract Claude Code builds the Streamlit site against. Eighteen pages, each specified as:
which serving view it reads, which columns that view must expose, which controls the page carries,
how it behaves in the four states, and a numbered list of statements that must be true before the
page is done.

---

## How to read this document

**Acceptance criteria are testable statements, not aspirations.** Each is written so it can be
answered yes or no by running the page or querying the view. `AC-4.3` means page 4, criterion 3.
Where a criterion can be expressed as a dbt test or a Python assertion, it should be — the wording
is deliberately close to executable.

**Column names in this document are requirements on the serving layer, not descriptions of it.**
Where a view already exists with a different name for the same thing, **the built name wins** and
this document is amended — say so in the build report rather than renaming a live column. Where the
view does not exist yet, these names are the contract.

**Precedence.** `decision_log.md` > this document > `roadmap.md` > the wireframe. The wireframe
shows intent and layout; where its pixels and this document's text disagree, this document is the
requirement. Where this document and a recorded decision disagree, the decision wins and this
document is wrong.

**What this document is not.** It does not specify dbt model SQL, does not choose Streamlit
component libraries, and does not describe the transform tier. It stops at the serving boundary in
one direction and at "the user can see and do this" in the other.

---

## Serving-view inventory — reconciled against the database `[A 08-20]`

**v1.0 carried inferences. This is fact**, from Claude Code's Task 1 reconciliation and
`srv_sample.xlsx` (15 sheets + INDEX, ~/projects/…/ncaa_football/, outside the repo).

**Fifteen views are built.** Six that v1.0 called Blocked or Confirmed absent turned out to exist —
Tasks 4, 5 and 6 landed before this document was read. **Two that v1.0 inferred built do not
exist**, and those are the ones that cost something.

| View | Backs | Grain | Reality | v1.0 said |
|---|---|---|---|---|
| `srv_schedule` | Schedule | game | **built** | confirmed built ✓ |
| `srv_scoreboard` | Scores | game | **built** | inferred built ✓ |
| `srv_standings` | Standings | team × season | **built** | inferred built ✓ |
| `srv_teams_index` | Teams | team × season | **built** | inferred built ✓ |
| `srv_team_game_log` | Team page | team × game | **built** | inferred built ✓ |
| `srv_edge_finder` | Edge Finder | game × market | **built** | confirmed built ✓ |
| `srv_model_performance` | Model Performance | model_version × segment | **built** | confirmed built ✓ |
| `srv_line_movement` | Line Movement | game × provider × snapshot | **built** | inferred built ✓ |
| `srv_today_edges` | Today | game (current week) | **built — 211 rows** | confirmed absent ✗ |
| `srv_matchup` | Matchup | game | **built — 110,634 rows** | confirmed absent ✗ |
| `srv_rankings` | Rankings | team × season × week | **built — 49,798** | blocked ✗ |
| `srv_rankings_compare` | Rankings | team × season × week | **built — 37,004** | blocked ✗ |
| `srv_team_stats` | Stats | team × season × stat | **built — 177,876** | blocked ✗ |
| `srv_data_dictionary` | Data Dictionary, Excel | table × column | **built — 957** | blocked ✗ |
| `srv_system_health` | System Overview | varies | **built — 224** | blocked ✗ |
| **`srv_team_overview`** | **Team page** | team × season | **ABSENT** | inferred built ✗✗ |
| **`srv_odds_board`** | **Odds Board** | game × provider | **ABSENT** | inferred built ✗✗ |
| `srv_player_stats` | Players | player × season | absent | blocked ✓ |
| `srv_player_game_log` | Players | player × game | absent | blocked ✓ |

**The two absences are the finding that matters.** v1.0's Task 3 listed Team page and Odds Board
among the pages that "render fully". Neither can — their primary views do not exist. They join the
build list below.

### Column names — the built name wins `[A 08-20]`

Applied throughout this document. Where a page section still shows a v1.0 name, the table below
governs.

| v1.0 name | Built name | Note |
|---|---|---|
| `model_attribution_text` | `attribution` | mechanical rename |
| `line_captured_at` | `snapshot_ts` / `line_snapshot_ts` | mechanical rename; the per-view spelling is whichever the view uses |
| `is_out_of_sample` | `is_out_of_sample_week` | **not purely mechanical — see below** |

**`is_out_of_sample_week` is a week-level flag, not a prediction-level one.** For AC-12.5's purpose
— separating backtest figures from live ones — a week-level flag is sufficient and arguably more
honest, since out-of-sample-ness is a property of the training cut rather than of an individual row.
Adopted as-is. **But the UI copy must say "out-of-sample week", not "out-of-sample prediction"**,
because those are different claims and only one of them is true.

### The framing error in v1.0, corrected `[A 08-20]`

v1.0 said **"13 of 18 pages render."** That was a statement about *data readiness* — which views
exist — and I let it read as a statement about the *site*. It is not. The deployed app is a 100-line
single-page prototype reading `mart_*` directly; against Part 0 it has `cache_data` and nothing
else. No `st.navigation`, no `st.Page`, no `query_params`, no `color_on_light`, no attribution, no
explicit `LIMIT`.

**Two counts, and they must never be conflated again:**

| | Count |
|---|---|
| Pages whose data exists in `serving` | **15 of 18** views built; 16 of 18 pages have their primary |
| Pages the deployed site actually renders | **1**, and it does not read `serving` at all |

The strangler cutover has happened for the transform tier and **has not happened for the site**.
That is the single largest piece of remaining work, and this document previously understated it.

---

## Readiness — the definition this document lacked until v1.2 `[A 08-20b]`

**Three times now, this document has taken the cheapest available signal as evidence of readiness,
and three times it has been wrong in the same direction.**

| Round | Signal taken as readiness | What it actually proved | Cost |
|---|---|---|---|
| v0 spec | three object names | those names existed | specified `fct_game_team` as new; it was already production, 220,204 rows |
| v1.0 | "the page renders" | nothing about the database | `srv_team_overview` and `srv_odds_board` marked built; both absent |
| v1.1 | "the view exists" | the view exists | **104 of 135 required columns absent — 77%** |

The pattern is not carelessness about any one fact. It is a **standing willingness to treat the
easiest observable as the thing I actually need to know.** The fix is not "check more carefully" —
that has failed three times. The fix is a definition with a gate in it.

### The definition

A page is **BUILDABLE** only when all three hold:

1. **Exists** — its primary view is in `serving` on both engines.
2. **Complete** — the view carries every column its page section lists as required, verified
   column-by-column against `information_schema`, not by inspection.
3. **Published** — the view is on the droplet and readable by the app's role.

Anything less is **NOT BUILDABLE**, and the page section says which of the three failed. There is no
intermediate state called "data ready", and v1.1's use of that phrase is withdrawn — it meant only
(1) and was read as all three.

### What the gap actually is

From Claude Code's column-level audit:

| View | Required | Present | Missing |
|---|---|---|---|
| `srv_matchup` | 31 | 7 | **24** |
| `srv_model_performance` | 17 | 1 | **16** |
| `srv_today_edges` | 23 | 8 | **15** |
| `srv_edge_finder` | 19 | 4 | **15** |
| `srv_team_stats` | 16 | 3 | **13** |
| `srv_rankings` | 17 | 5 | **12** |
| `srv_schedule` | 12 | 3 | **9** |
| | **135** | **31** | **104** |

**The most-missed are structural, not incidental**, which is why this is a build step rather than a
punch list:

- **`as_of_ts` — absent from all seven.** AC-G.35 requires it on every page.
- **`start_date_et` — absent from four.** AC-G.34 requires Eastern display with the zone applied in
  dbt.
- **`*_slug` — absent from three, and there is no slug column anywhere in `dim_team`.** AC-G.14
  forbids deriving it in Python. **Every deep link on the site is blocked on one dbt change.**
- **`attribution` / `model_version_key` — absent from three.** Already flagged at AC-G.41.

### The new criteria

**AC-G.53** — No page is built until its primary view passes a **column-completeness check**: an
automated comparison of the view's `information_schema` columns against its required list in this
document, reported as present/missing. Run it, do not eyeball it.
**AC-G.54** — `as_of_ts` exists on every `srv_` view and is `not_null`-tested. A page cannot satisfy
AC-G.35 otherwise.
**AC-G.55** — `dim_team` carries a `team_slug` column, lowercase and hyphenated, and every
game-grain and team-grain serving view exposes it. `Texas A&M` → `texas-am` is a dbt decision, and
AC-G.14 is unmeetable until this exists.
**AC-G.56** — Every page section in Parts 1–4 states its readiness as **Exists / Complete /
Published**, three booleans, refreshed whenever the reconciliation is re-run. A page section
carrying a stale readiness line is a defect in this document.

---

# Part 0 — The global contract

Everything in Part 0 applies to all eighteen pages. A page-level section only mentions these rules
when it varies from them.

## 0.1 Architecture — the three rules that shape everything else

**G-1. The site reads `serving` and nothing else.** No page issues a query against `raw`, `staging`
or `marts`. Already enforced three ways — the droplet's `search_path`, the locked `cfdb_read` role,
and the CI layering guard — so a violation is a bug in one of those, not a style problem.

**G-2. Every query is a single-table `SELECT … WHERE … ORDER BY … LIMIT`.** No joins in Streamlit.
If a page needs two things side by side, the serving view carries both columns. When a page seems to
need a join, that is a serving-view change request, not app code.

**G-3. No metric arithmetic in the app.** Percentages, ranks, percentiles, deltas, edges, ROI,
records, cover flags and any figure a user could quote back are computed in dbt and arrive as
columns. Streamlit formats and filters; it does not calculate.

> **Why G-3 is worth defending under deadline pressure.** The same number appearing on Edge Finder,
> Model Performance and the Excel export must be the same number. Three re-derivations of one
> formula is how definitions drift, and the drift is silent. This is exactly why `home_cover_edge`
> was moved out of the serving view and into `fct_prediction` — derive once, consume everywhere.

**AC-G.1** — A grep of the Streamlit source finds zero occurrences of ` JOIN ` in any SQL string.
**AC-G.2** — A grep finds no arithmetic operator applied to two DataFrame columns outside of
formatting helpers. Division by 100 for a percent display is formatting; `a / b` producing a rate is
a violation.
**AC-G.3** — Every SQL string in the app names exactly one relation, and that relation starts
`srv_`.
**AC-G.4** — Attempting to query `marts.dim_team` as the app's database user raises a permission
error. This is a test, and it should be in CI.

> **`[A 08-20b]` Today this criterion describes the only thing the site CAN read.** `publish_marts.py`
> ships exactly three tables (`mart_team_schedule`, `mart_team_season_record`, `mart_data_freshness`)
> into a `marts` schema on the droplet, and **there is no `serving` schema there at all.** AC-G.4 is
> unmeetable — and its inverse is currently true — until publishing is extended to `serving`. That
> is now build step 2.

## 0.2 The four states — every page, every section

Every data-bearing section of every page is in exactly one of four states. Getting these right is
most of what separates a site that looks trustworthy from one that does not.

| State | When | What renders |
|---|---|---|
| **Loading** | Query in flight | Skeleton at the final layout's dimensions — never a spinner that collapses the layout |
| **Empty** | Query succeeded, zero rows | A sentence saying what would be here and why it is not, plus the control most likely to fix it |
| **Degraded** | Section's source view absent or its column all-null | The rest of the page renders normally; this section states which table it is waiting on |
| **Error** | Query raised | Plain-language message, the view name, a retry control. Never a stack trace |

**The distinction that matters most is Empty versus Degraded.** "No games match your filters" and
"the rankings table has not been built" look identical if both render as a blank panel, and they
mean opposite things — one is the user's doing and one is ours. They must never render alike.

**AC-G.5** — Every section renders a distinct, non-blank state in all four cases. Verified by
forcing each: filter to an impossible combination (Empty), rename the view in a scratch schema
(Degraded), revoke select (Error).
**AC-G.6** — No page shows `0`, `—`, `NaN`, `None` or an empty table where the honest answer is "not
built yet".
**AC-G.7** `[A 08-23]` REFINED — A Degraded section names the specific missing object so the user can
read the blocker off the screen without asking. **Which name depends on where it renders:**

| Where | Shows |
|---|---|
| **Front of house** | A **friendly dataset name, hyperlinked to its Data Dictionary entry** — "Dataset: Schedule" |
| **Back of house** (System Overview) and any blocker naming an unbuilt object | The **literal identifier** in code font — `srv_schedule`, `fct_edge_bucket_performance` |

> **`[A 08-23]`** v1.3 said "in code font" everywhere. That is right when the reader is a builder and
> the exact identifier is the point; it is wrong on a page a member of Marc's group is reading.
**AC-G.8** — A Loading skeleton occupies the same height as the loaded content, so the page does not
jump.
**AC-G.9** — An Error state never renders a traceback, a connection string, a host name or a
credential.

## 0.3 Deep links — the URL is the state

Every page's full state is reconstructible from its URL via `st.query_params`. This is what makes a
row click meaningful, a bookmark durable and a shared link honest.

**Canonical parameter names.** Use these everywhere; do not invent per-page synonyms.

| Param | Type | Example | Applies to |
|---|---|---|---|
| `season` | int | `2026` | all data pages |
| `week` | int | `1` | week-scoped pages |
| `season_type` | enum | `regular` \| `postseason` | week-scoped pages |
| `team` | slug | `alabama` | team pages |
| `opponent` | slug | `georgia` | Matchup, head-to-head |
| `game_id` | int | `401628459` | Matchup, Line Movement |
| `player_id` | int | `4432577` | Players |
| `conference` | slug | `sec` | index and list pages |
| `division` | enum | `fbs` \| `fcs` \| `all` | index and list pages |
| `poll` | slug | `ap` \| `coaches` \| `cfp` | Rankings |
| `market` | enum | `spread` \| `total` \| `moneyline` | betting pages |
| `provider` | slug | `draftkings` | Odds Board, Line Movement |
| `model` | slug | `ridge_margin_expanded` | prediction pages |
| `tab` | slug | `gamelog` | tabbed pages |
| `stat_scope` | enum | `team` \| `opponent` | Stats |
| `stat_basis` | enum | `raw` \| `adjusted` | Stats |

**AC-G.10** — For each page, setting every applicable parameter and reloading reproduces the exact
view, including the selected tab.
**AC-G.11** — An unknown parameter is ignored silently. An out-of-range known parameter (week 99,
team `atlantis`) renders the page's Empty state with a message naming the bad value — it never
raises and never silently substitutes a default.
**AC-G.12** — Changing a control updates the URL without a full rerun loop or a flash of the
previous state.
**AC-G.13** — Every clickable row navigates by writing query params, never by mutating session state
alone. A middle-click or copy-link on any clickable row yields a working URL.
**AC-G.14** — `team` and `conference` slugs are lowercase, hyphenated, and come from a column in
`dim_team` / `dim_conference` — never string-manipulated in the app. `Texas A&M` → `texas-am` is a
dbt decision, not a Python one.

> **`[A 08-20b]` There is no slug column anywhere in `dim_team`.** This criterion is not merely
> unmet, it is unmeetable, and **every deep link on the site depends on it** — which makes one small
> dbt change a prerequisite for the entire query-param layer. See AC-G.55.

## 0.4 Filters — one contract, applied identically everywhere

**Placement `[A 08-23]` — CHANGED.** Global filters (season, week, classification) render as a
**persistent horizontal bar at the top of every data page, above the fold**, under the page title.
Page-local filters join the same row. Never in the sidebar — that is nav.

> **`[A 08-23]` v1.3 put global filters in the sidebar. That was wrong**, and Marc's walkthrough
> found it: every sports site puts season and week controls at the top of the content because that
> is where the eye lands, and burying them under the nav means a user does not find them at all.

**Persistence.** Global filters persist across page navigation via query params. Page-local filters
reset when you leave the page — the exception is Edge Finder's thresholds, which persist because
they encode a betting posture rather than a view.

**Cascade.** Selecting a conference restricts the team list. Selecting a season restricts the week
list to weeks that season actually has. Cascades are driven by distinct values in the serving view,
never by a hardcoded list in Python.

**Defaults.** Season = current per `dim_season.is_current`. Week = current per
`dim_week.is_current`, falling back to the most recent week with any completed game. Division = FBS.
Conference = all. **No default is a literal in the app** — every one reads a flag column.

**AC-G.15** — With `dim_season` advanced to the next season, the site's default season changes with
no code change.
**AC-G.16** — Every filter's option list is populated by a `SELECT DISTINCT` on the page's own
serving view, so an option that would return zero rows is never offered.
**AC-G.17** — Clearing all filters returns the page to its default state, not to an empty state.
**AC-G.18** — Filter state round-trips through the URL (see AC-G.10).
**AC-G.18b** `[A 08-24]` NEW — **A persistent filter must be visible.** The filter bar renders its
current values on **every** page that has one, including values inherited from another page. Any
value that is **not the default is visually marked**, and a one-click reset is offered whenever
anything is off-default.

> **`[A 08-24]` Persisting silently is worse than not persisting.** Marc filtered Standings to 2025,
> navigated to Stats, and found it still filtered with nothing on the page saying so. Not persisting
> was a bug; persisting invisibly is **a way to be confidently wrong** — a user reads 2025 numbers
> as current. The URL carrying the state is not the same as the page showing it.
**AC-G.20b** `[A 08-23]` NEW — **cfdb is an FBS site.** `classification` defaults to FBS
everywhere, and **a game is in scope when EITHER team is FBS**, not both. Non-FBS teams remain as
opponents with names, colours and slugs — they simply get no index row, no standings row and no team
page. This is a global filter with a default, **not a hardcoded `WHERE`**: a user can still widen it.

**AC-G.19** — Week 0 is representable. The 2026 season's first games are Thursday 27 August and CFBD
treats 27 Aug – 7 Sep as Week 1; the filter must render whatever `dim_week` contains rather than
assuming weeks start at 1.

## 0.5 Status chips — fixed width, glyph plus colour

One component, used everywhere a categorical outcome appears. Fixed width, same shape regardless of
label, glyph first, colour second.

| Class | Glyph | Use |
|---|---|---|
| `y` | ✓ | Cover, Win, Bet, Yes, Pass (a passing test) |
| `n` | ✗ | Did not cover, Loss, No bet, No |
| `w` | – | Push, Pending, Unknown, Backtest-only |
| `p` | ▲ | Positive edge, improvement |
| `r` | ✗ | Failure, error, stale |

**AC-G.20** — Chip width is identical across all labels. "Cover" and "DNC" occupy the same box.
**AC-G.21** — Every chip's meaning survives conversion to greyscale — verified by screenshotting a
page with a greyscale filter applied and confirming each chip is still readable.
**AC-G.22** — No status is communicated by colour alone anywhere on the site, chips included.
**AC-G.23** — Chip text is never the only accessible label; each carries a title/aria label spelling
out the full meaning.

## 0.6 Team identity — chrome, never encoding

Logos and colours identify; they never carry value. This is the single easiest way to make a data
site lie, so it gets a hard rule.

**AC-G.24** — No chart maps a quantity to a team colour. Value is encoded by position, length, or a
sequential/diverging ramp that is not team-derived.
**AC-G.25** — Team colour appears only as: a left border or accent rule on a team's own card, a
header band on a Team page, or a legend swatch identifying a series. Never a bar fill representing a
number.
**AC-G.26** — Text drawn over a team colour uses `color_on_light` / `color_on_dark` from `dim_team`,
which are computed for contrast in dbt. The app never computes contrast.
**AC-G.27** — Logos are served from cfdb's own cache, never hotlinked to a third party.
**AC-G.28** — A team with no logo renders a monogram at the identical footprint. The layout does not
shift, and no broken-image glyph ever appears.
**AC-G.29** — Both light and dark themes are legible for all 130+ FBS teams. Spot-check the known
hard cases: teams whose primary is near-black, near-white, or a mid grey.

## 0.7 Numbers, nulls and time

**AC-G.30** — Every numeric column is right-aligned and set in the monospace face, so columns of
figures compare vertically.
**AC-G.31** — Decimal precision is fixed per column, never per value: margins and spreads 1 dp,
percentages 1 dp, MAE 2 dp, EPA 3 dp, currency 2 dp. `7` renders `7.0` where its column is 1 dp.
**AC-G.32** `[A 08-21b]` REVISED — **Three states, not two.** Null renders `—` (em dash). Zero
renders `0`. **Not-applicable renders `n/a`** with a hover explaining why. Never `None`, `NaN`,
`null` or blank, and all three states are visually distinguishable.

> **`[A 08-21b]` The third state was missing and it cost something.** Four models have
> `cover_scored = 0` — they produce no margin, so they *cannot* be ATS-scored. Rendered as a bare em
> dash they read as **missing data**, which invites the question "when will this fill in?" The
> answer is never, and the cell should say so. "We don't have it yet" and "this doesn't apply here"
> are different claims and the page must not conflate them.

**AC-G.33** `[A 08-21b]` REVISED — Any rank, percentile or hit rate renders with its `n` adjacent,
**and the `n` shown must be the denominator the rate was actually computed over** — not a
neighbouring count that happens to be nearby.

> **`[A 08-21b]` My criterion was underspecified and produced a real defect.** Model Performance
> showed the ATS percentage beside `games` = 567 while the rate was computed over `cover_scored` =
> 553. Pushes are correctly excluded from both numerator and denominator; the *displayed* n included
> them. **Both numbers were individually correct.** Placing them adjacent asserted a relationship
> that did not hold.
>
> This is a **composition defect** — the same class as the `->> '0'` silent null, where every
> component behaved correctly and the assembly was wrong. They are invisible to component-level
> testing by construction, which is why the criterion has to name the relationship rather than the
> parts.
**AC-G.34** `[A 08-24]` REVISED AGAIN — Timestamps display in **one configured default timezone —
currently `America/Los_Angeles`** — with the zone abbreviation shown, **including the "as of" stamp**.
The timezone is **a config value, never a literal in page code**, so viewer-local later is a change
to how that value resolves rather than a hunt through the codebase.

> **`[A 08-24]`** Viewer-local (below) is deferred past Week 0 on Claude Code's recommendation: a
> custom component is a new failure mode four days out. Pacific is Marc's own zone and the site's
> primary reader. **This cuts against convention** — ESPN and CBS publish kickoffs in Eastern — which
> is exactly why the zone abbreviation is non-optional. "7:30 PM PDT" is unambiguous; "7:30 PM" is
> not.

**Deferred target** — timestamps in the **viewer's local timezone** with the zone abbreviation shown. Dates render **"Aug 20, 2026"**; times render **"7:30 PM PDT"**. On a view
already grouped by day, the kickoff cell carries **time only**. Storage stays UTC.

> **`[A 08-23]` Implementation wrinkle, flagged rather than hidden:** Streamlit renders server-side
> and does not know the viewer's timezone unaided. Options, cheapest first — (1) a one-time JS read
> of `Intl.DateTimeFormat().resolvedOptions().timeZone` persisted like a filter; (2) a timezone
> picker in the filter bar defaulting to Eastern; (3) client-side formatting. **If all three cost
> more than they look, fixed Eastern with the zone clearly shown is a defensible v1** for a US
> college football site — but the long date format and time-only-in-grouped-views changes stand
> either way.
**AC-G.35** — Every page carries an "as of" timestamp sourced from a freshness column in its own
serving view — not from `now()` in the app. The user must be able to tell stale data from fresh
data.

## 0.8 Caching and performance

**AC-G.36** — Query results are cached with `st.cache_data`, keyed on the full parameter set.
**AC-G.37** — Cache TTL is 300 s during a live scoring window and 3600 s otherwise, driven by the
same season-aware cadence logic the DAG uses — not by a duplicate rule in the app.
**AC-G.38** — No page issues more than 4 distinct queries on first paint.
**AC-G.39** — Every list or table query carries an explicit `LIMIT`. `fct_play`-derived views are
never queried without a game or player filter.
**AC-G.40** — First paint under 2 s on a warm cache, under 5 s cold, measured on the production
droplet. **`[A 08-20]` The criterion is stated with its filter, not without it:** a page whose view
exceeds ~10,000 rows must reach it *with its primary key filter applied*. `srv_matchup` is 110,634
rows × 65 columns and must never be queried without `game_id`; an unfiltered open is a defect, not a
performance miss.

## 0.9 Attribution — carried as data

**AC-G.41** — Every page rendering a prediction also renders the attribution string sourced from
`dim_model_version` through the serving view. It is a column, not page config, so a page cannot draw
the numbers without it.

> **`[A 08-20]` This criterion is currently FALSE and is a build item, not a check.** `attribution`
> exists only on `srv_model_performance`. `srv_edge_finder`, `srv_matchup` and `srv_today_edges` all
> render predictions without it. The fix is a join to `dim_model_version` on each — cheap, and it
> must land before or alongside the shared attribution component, because that component has nothing
> to read otherwise.
**AC-G.42** — The string states plainly that these are cfdb's own predictions built on a licensed
CFB Model Training Pack, and are **not** official CollegeFootballData.com predictions.
**AC-G.43** — CFBD attribution appears in the site footer on every page. Optional under their terms;
we do it anyway.
**AC-G.44** — A prediction-bearing view with a null attribution column fails a dbt `not_null` test.
The guarantee is in the model, not in a code review.

## 0.10 Accessibility and responsive behaviour

**AC-G.45** — All body text meets WCAG AA contrast in both themes.
**AC-G.46** — Every control is reachable and operable by keyboard, in a sensible tab order.
**AC-G.47** — Tables carry proper header semantics and a caption naming the source view.
**AC-G.48** — At 1024 px the sidebar collapses and no table scrolls horizontally without an obvious
affordance. Below 768 px is out of scope for v1 and the site says so rather than degrading silently.

## 0.11 Navigation

**AC-G.49** `[A 08-24]` REVISED — Nav is built with `st.navigation` / `st.Page`, grouped as
wireframe v0.3: Overview · Games & teams · Betting · Deliverable · Reference · Back of house.
**Team page is NOT in the nav** — it is a drill-through reached from Teams and from every team link
on the site.

> **`[A 08-24]` Why Team page comes out and Matchup stays.** Matchup had **no index** — nothing
> enumerated games as a way of choosing one, so removing it would have left it unreachable except by
> luck; it got a picker instead. **Team page has an index: Teams *is* the picker** — searchable,
> conference-filtered, 681 cards. A nav entry landing on an arbitrary team is strictly worse than the
> index that already exists. The page count stays 18; this is a nav decision, not a scope one, and
> AC-G.51 governs **blocked** pages, not drill-throughs.
**AC-G.50** — Within-page sections use `st.tabs`; tab selection is reflected in the `tab` query
param.
**AC-G.51** — A page whose primary table is missing still appears in the nav, in its Degraded state,
naming its blocker. **Blocked pages are not hidden.** A site that hides what it cannot do teaches
the user nothing; one that says "Rankings is waiting on `fct_poll_rank`" is a portfolio asset.
**AC-G.52** — Back-of-house pages sit in their own nav group. Everything is behind Cloudflare Access
already, so this is organisation rather than security.

## 0.12 The rule for anything not covered here

If a requirement is genuinely ambiguous, **do not guess** — implement the narrower reading, ship it,
and put the question in a DECISIONS NEEDED block in the build report. A narrow implementation that
is wrong is cheap to widen; a wide one that is wrong has to be found first.

---

# Part 1 — Games & teams

---

## Page 1 — Today

**Purpose.** The Thursday landing page. What is on today, what the model likes, what changed since
yesterday. Front of house only — nothing about pipeline internals, which live on System Overview.

**Primary view.** `srv_today_edges` — grain: game, current week. **`[A 08-20]` Built — 211 rows.**
**Readiness `[A 08-20b]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** See the readiness section; "data ready" is withdrawn. See the corrected framing in the inventory section: view built ≠ page rendered.

> `[A 08-20]` v1.0 called this view absent and specified a Degraded prediction section. It exists.
> Build the page fully. Note the row count: 211 is a current-week slate, so an out-of-season or
> out-of-window query legitimately returns zero and must render **Empty**, not Degraded.

### Required columns

| Column | Type | Notes |
|---|---|---|
| `game_id` | bigint | deep-link key |
| `season`, `week`, `season_type` | int/int/text | |
| `start_date_et` | timestamp | display zone applied in dbt |
| `home_team_slug`, `away_team_slug` | text | link keys |
| `home_team_display`, `away_team_display` | text | |
| `home_logo_url`, `away_logo_url` | text | cfdb-cached |
| `home_color_on_light`, `home_color_on_dark` | text | contrast-safe |
| `home_record_display`, `away_record_display` | text | pre-formatted `5-2 (3-1)` |
| `home_rank`, `away_rank` | int | null when unranked |
| `venue_display`, `is_neutral_site` | text/bool | |
| `network` | text | |
| `spread_current`, `spread_open` | numeric | home-negative convention |
| `total_current` | numeric | |
| `predicted_margin` | numeric | **home-negative**, matching `margin = away − home` |
| `home_cover_edge` | numeric | from `fct_prediction`, not re-derived |
| `home_win_probability`, `market_implied_home_win_probability` | numeric | |
| `devig_method` | text | |
| `is_out_of_sample_week` | bool | |
| `model_version_key`, `attribution` | text | AC-G.41 |
| `excitement_index` | numeric | |
| `as_of_ts` | timestamp | AC-G.35 |

### Controls

Date selector (defaults to today, Eastern) · division · conference · a "predictions only" toggle
that hides games with no model row.

### Acceptance criteria

**AC-1.1** — With no games today, the page renders an Empty state naming the next date that has
games and offering a control to jump there. It does not render an empty table.
**AC-1.2** — Until `srv_today_edges` exists, every prediction element renders Degraded, naming
`srv_today_edges`, while the schedule strip renders normally from `srv_schedule`. The page is
useful, and honest about what is missing.
**AC-1.3** — Every game card links to `Matchup?game_id=…`.
**AC-1.4** — `predicted_margin` sign convention is verified on screen: a home favourite shows a
negative predicted margin and a negative spread, and the two point the same way. This is the defect
most likely to make every downstream number confidently wrong.
**AC-1.5** — Rank badges render only when `home_rank`/`away_rank` is non-null; an unranked team shows
no badge, not `—` in a badge.
**AC-1.6** — The page issues at most 2 queries on first paint.
**AC-1.7** — No pipeline, dbt, freshness or DQ content appears anywhere on this page.
**AC-1.8** — Attribution renders wherever a prediction renders (AC-G.41).

### Out of scope for v1

Live in-game scoring, win-probability graphs, social/news content.

---

## Page 2 — Schedule

**Purpose.** The full slate for a week, filterable, scannable, and the primary route into Matchup.

**Primary view.** `srv_schedule` — grain: game. **Confirmed built.**
**Readiness `[A 08-20c]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** Published is ✗ for *every* page until `serving` is on the droplet.

### Required columns

`game_id` · `season` · `week` · `season_type` · `start_date_et` · `home_team_slug` ·
`away_team_slug` · display names · logo URLs · `home_conference`, `away_conference` ·
`is_conference_game` · `is_neutral_site` · `venue_display` · `network` · `spread_current` ·
`total_current` · `predicted_margin` · `home_win_probability` · `is_completed` ·
`home_points`, `away_points` · `as_of_ts`

### Controls

Season · week · season type · conference · division · "conference games only" · text search on team
name.

### Acceptance criteria

**AC-2.1** — Grain is exactly one row per game. A game appears once, never once per team. This is
the grain inversion that was previously specified backwards; a `count(*)` on the view equals the
game count for the filtered scope, not twice it.
**AC-2.2** — Games are grouped by day, in kickoff order within a day, with day headers.
**AC-2.3** — Each row shows a pre-game state before kickoff and a post-game state after, driven by
`is_completed` — one row, two render paths, no separate component.
**AC-2.4** — A neutral-site game shows a neutral-site flag rather than a home/away framing. Full
venue detail is on Matchup, not here.
**AC-2.5** — Row click → `Matchup?game_id=…`. Team name click → `Team?team=…`. The two targets are
visually distinct so the user knows which they are about to hit.
**AC-2.6** — Non-FBS opponents render as stubs with name and conference, never as a blank or a
broken link.
**AC-2.7** — Filtering to a conference with no games that week yields the Empty state, naming the
filter that caused it.
**AC-2.8** — Every column header on a tabular layout sorts, and sort state survives in the URL.
**AC-2.9** — Team colour appears only as an accent rule, never as a fill encoding any value
(AC-G.24).

---

## Page 3 — Scores

**Purpose.** Completed and in-progress results, with the model's call alongside the outcome.

**Primary view.** `srv_scoreboard` — grain: game. Inferred built.
**Readiness `[A 08-20c]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** Published is ✗ for *every* page until `serving` is on the droplet.

### Required columns

Everything on Schedule, plus: `home_points`, `away_points` · `winner_team_slug` ·
`actual_margin` (**away − home**) · `spread_at_close` · `cover_result` (`home` \| `away` \| `push` \|
`pending`) · `total_result` (`over` \| `under` \| `push` \| `pending`) · `excitement_index` ·
`is_upset` · `home_rating_pre`, `away_rating_pre` · `attendance` · `as_of_ts`

### Acceptance criteria

**AC-3.1** — The sign convention holds on screen: where `actual_margin < 0`, the home team won. This
has been verified 3,402/3,402 in the data; the page must not undo it in display code.
**AC-3.2** — The winning team's row or half-card is shaded, and the shading is not the only signal —
the score itself is weighted too (AC-G.22).
**AC-3.3** — `cover_result` renders as a status chip, `push` distinct from `pending` (AC-G.20).
**AC-3.4** — An in-progress game shows a live state distinct from both scheduled and final. If live
data is not wired, in-progress games render as scheduled and the page says so — it never shows a
stale score as final.
**AC-3.5** — Results are grouped by day, most recent first.
**AC-3.6** — `is_upset` is a column, not an app-side comparison of ranks.
**AC-3.7** — Prediction columns render Degraded rather than blank for games with no model row.

---

## Page 4 — Rankings `[A 08-20]` **unblocked**

**Purpose.** Poll standings, week-over-week movement, and where the polls disagree.

**Primary views.** `srv_rankings` (49,798 rows) and `srv_rankings_compare` (37,004). **Both built.**
**Readiness `[A 08-20b]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** See the readiness section; "data ready" is withdrawn. See the corrected framing in the inventory section: view built ≠ page rendered.

> `[A 08-20]` `fct_poll_rank` landed with 49,798 rows. The page is no longer blocked on data.
> AC-4.1 (the Degraded state) is now unreachable and is retired.

### Required columns — `srv_rankings`

`season` · `week` · `poll_slug` · `poll_display` · `poll_release_date` · `rank` · `team_slug` ·
`team_display` · `logo_url` · `conference` · `first_place_votes` · `points` · `rank_prev_week` ·
`rank_delta` · `record_display` · `is_current_release` · `as_of_ts`

### Required columns — `srv_rankings_compare`

`season` · `week` · `team_slug` · `team_display` · one `rank_<poll>` column per active poll ·
`rank_spread` (max − min across polls, computed in dbt) · `poll_count` · `as_of_ts`

### Acceptance criteria

**AC-4.1** — ~~Degraded state~~ **RETIRED `[A 08-20]`** — the tables exist. Criterion numbering is
kept stable rather than renumbered, so AC-4.2 onward still mean what they meant.
**AC-4.2** — One tab per poll, plus a Compare tab. Tab selection lives in the URL.
**AC-4.3** — `rank_delta` renders with direction and magnitude, glyph plus number, never colour
alone.
**AC-4.4** — The Compare tab is fed by the pre-pivoted view. **No pivot happens in Streamlit**
(AC-G.2).
**AC-4.5** — `rank_spread` sorts, so "where do the polls disagree most" is one click.
**AC-4.6** — A team receiving votes but unranked is representable and visually distinct from a team
receiving none.
**AC-4.7** — The bump chart labels only the top N teams by default, with a control to add more.
Unlabelled lines are decoration, not data.
**AC-4.8** — Historical seasons are reachable by changing `season`, back to whatever the built fact
covers. The page states its own coverage range rather than failing on an early season.

---

## Page 5 — Standings

**Purpose.** Conference standings with the tiebreakers already resolved.

**Primary view.** `srv_standings` — grain: team × season. Inferred built.
**Readiness `[A 08-20c]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** Published is ✗ for *every* page until `serving` is on the droplet.

### Required columns

`season` · `team_slug` · `team_display` · `logo_url` · `conference` · `division` ·
`overall_wins`/`losses` · `conference_wins`/`losses` · `tiebreak_rank` · `win_pct` ·
`conference_win_pct` · `points_for`/`against` · `point_differential` · `current_streak_display` ·
`last_5_display` · `home_record_display` · `away_record_display` · `ats_record_display` ·
`sp_plus_rating` · `elo_rating` · `as_of_ts`

### Acceptance criteria

**AC-5.1** — `tiebreak_rank` is a column. **The app never sorts by business logic** — conference
tiebreakers are dbt's job and a Python `sort_values` implementing them is a defect.
**AC-5.2** — Teams group by conference, and by division where a conference has them.
**AC-5.3** — Records are pre-formatted strings from the view, not assembled in Python from a wins and
a losses column.
**AC-5.4** — Team click → Team page.
**AC-5.5** — A conference that realigned mid-history shows the membership for the selected season,
not today's. `stg_teams` is already team × season, so this is a filter, not a special case.
**AC-5.6** — Rating columns render Degraded rather than blank where `fct_team_week_rating` has no row.

---

## Page 6 — Stats `[A 08-20]` **unblocked, scope reduced**

**Purpose.** Team and player statistical leaders, raw and opponent-adjusted.

**Primary view.** `srv_team_stats` — **built, 177,876 rows.** Grain is team × season × stat, **long
by `stat_name` only.**
**Readiness `[A 08-20b]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** See the readiness section; "data ready" is withdrawn. See the corrected framing in the inventory section: view built ≠ page rendered.

> **`[A 08-20]` DECIDED — v1 ships raw team stats only.** `stat_scope` and `stat_basis` do not exist.
> Opponent-adjusted metrics are not modelled, and per the publication boundary they must be derived
> from CFBD's `/ratings` and `/ppa` endpoints — **never** read out of the pack's `training_data.csv`,
> however much easier that would be. That is real ingestion work, not a pivot.
>
> So: **Stats renders now**, from 177,876 rows of real team-season stats, with the four-way toggle
> rendering **Degraded** and naming what is missing. Opponent scope and adjusted basis move to
> **v1.5**. The alternative — holding the page until adjusted metrics land — trades a working page
> against a more complete one, and the north star says page-readiness wins.

`srv_player_stats` remains absent, correctly — Players is out of scope until step 7.

### Required columns — `srv_team_stats`

`season` · `through_week` · `team_slug` · `team_display` · `logo_url` · `conference` ·
`stat_scope` (`team` \| `opponent`) · `stat_basis` (`raw` \| `adjusted`) · `stat_category` ·
`stat_name` · `stat_value` · `stat_rank` · `stat_percentile` · `qualifying_n` · `games_played` ·
`as_of_ts`

**`[A 08-20]` v1.5, not v1.** When the adjusted metrics land, emit all four `stat_scope` ×
`stat_basis` combinations **as rows**. The toggles filter; they do not compute (AC-G.2). Until then
the toggle renders Degraded.

### Acceptance criteria

**AC-6.1** `[A 08-20]` REVISED — The page renders raw team-season stats. The scope/basis toggle
renders **Degraded**, naming the missing `stat_scope` and `stat_basis` columns and stating that
opponent-adjusted metrics are a v1.5 ingestion item. It does not render a toggle that silently does
nothing.
**AC-6.2** `[A 08-20]` DEFERRED to v1.5 — When the toggle is live it filters rows. Flipping to
`adjusted` changes `stat_value` because a different row is selected, never because Python adjusted
anything.
**AC-6.3** — Every rank renders with its `qualifying_n` and the qualifying threshold (AC-G.33).
**AC-6.4** — Percentile bars encode by length, never by team colour (AC-G.24).
**AC-6.5** — `through_week` is user-selectable, so "as of week 6" is reachable — mid-season stats are
a different question from final ones.
**AC-6.6** — Team and Player are separate tabs against separate views; no view carries both grains.
**AC-6.7** — A stat with no value for a team renders `—`, distinct from a genuine zero (AC-G.32).

---

## Page 7 — Teams

**Purpose.** The index. Find a team, see its shape at a glance, click through.

**Primary view.** `srv_teams_index` — grain: team × season. Inferred built.
**Readiness `[A 08-20c]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** Published is ✗ for *every* page until `serving` is on the droplet.

### Required columns

`season` · `team_slug` · `team_display` · `mascot` · `abbreviation` · `logo_url` ·
`color_primary` · `color_on_light` · `color_on_dark` · `color_source` · `conference` · `division` ·
`venue_display` · `record_display` · `conference_record_display` · `sp_plus_rank` · `elo_rating` ·
`talent_rank` · `returning_production_pct` · `as_of_ts`

### Acceptance criteria

**AC-7.1** — Grouped by conference, alphabetical within, with a search box that filters as you type.
**AC-7.2** — `color_source` is exposed in the UI at least on hover, so a team whose colour was
defaulted rather than sourced is identifiable. Silent defaults become invisible data quality
problems.
**AC-7.3** — A missing logo renders a monogram at the same footprint (AC-G.28).
**AC-7.4** — Division filter switches between FBS, FCS and all; FBS is the default (AC-G.15).
**AC-7.5** — Card click → `Team?team=…&season=…`.
**AC-7.6** — Rating columns render Degraded where the rating fact has no row for that team-season.
**AC-7.7** — The page renders all 130+ FBS teams without pagination and without exceeding the paint
budget (AC-G.40).

---

## Page 8 — Team page

**Purpose.** One team, five tabs, everything cfdb knows about them this season.

**Primary views.** `srv_team_overview` (team × season) — **ABSENT** — and `srv_team_game_log`
(team × game) — built.
**Readiness `[A 08-20c]`.** `srv_team_game_log`: Exists ✓ · Complete ✗ · Published ✗. `srv_team_overview`: Exists ✗ — **NOT BUILDABLE.** Roughly half of `srv_team_overview`'s specified columns come from `fct_team_week_rating`, so it builds narrowed with its ratings section Degraded.

> **`[A 08-20]` This is one of the two inferences that cost something.** `srv_team_overview` carries
> the KPI header and the profile percentiles — the whole Overview tab. It has to be built, and it is
> now on the build list.
>
> The page is still worth building in this round: the Schedule tab renders fully from
> `srv_team_game_log`, and Overview renders **Degraded** naming `srv_team_overview`. That is exactly
> the per-tab degradation AC-8.2 already requires, so no new pattern is needed — the pattern was
> written for the Roster tab and now earns its keep twice.

### Required columns — `srv_team_overview`

Identity columns as Teams, plus: `record_display` · `conference_record_display` ·
`conference_standing` · `sp_plus_rating`/`rank`/`delta_vs_prev_week` · `elo_rating`/`delta` ·
`returning_production_pct`/`rank` · `ats_record_display` · `ats_as_favorite_display` ·
`ats_as_underdog_display` · `adj_epa_off`/`percentile` · `adj_epa_def`/`percentile` ·
`success_rate`/`percentile` · `points_per_drive`/`percentile` · `havoc_allowed`/`percentile` ·
`coach_display` · `as_of_ts`

### Required columns — `srv_team_game_log`

`team_slug` · `game_id` · `week` · `opponent_slug`/`display`/`logo_url` · `is_home` ·
`is_neutral_site` · `spread_for_team` · `predicted_margin_for_team` · `actual_margin_for_team` ·
`result_display` (`W 31-17`) · `ats_result` · `against_the_line` · `prediction_interval_low`/`high` ·
`is_completed` · `as_of_ts`

**Note the `_for_team` suffix.** This view is team-oriented, so every signed quantity is oriented to
the subject team, not to home. Mixing the two conventions in one view is how sign bugs get in.

### Acceptance criteria

**AC-8.1** — Five tabs — Overview, Schedule, Stats, Roster, Trends — with selection in the URL.
**AC-8.2** — Tabs whose source is missing render Degraded individually. **A blocked tab does not
block the page** — Roster is blocked on `dim_athlete` while Overview and Schedule render fully.
**AC-8.3** — Every signed quantity in the game log is oriented to the subject team, and this is
verified on a road game where the team is an underdog — the case where an orientation bug shows.
**AC-8.4** — An unplayed game shows the prediction with its interval and a `– pend` chip, never a
fabricated result.
**AC-8.5** `[A 08-20c]` REVISED — **No prediction interval exists anywhere in the model** — the
column appears zero times in the pack's export contract. It will **not** be derived to satisfy this
criterion: putting a confidence claim on screen that no model made is worse than the problem it
solves, and AC-8.5's own reasoning is why. Until a model emits one, render the point estimate with
**the model's MAE stated immediately beside it**. Where an interval does exist, render it.
**AC-8.6** — The team colour header band uses the contrast-safe text colour (AC-G.26).
**AC-8.7** — Game log rows click through to Matchup.
**AC-8.8** — Percentile bars carry their `n` (AC-G.33).
**AC-8.9** — Switching team via the URL alone reloads every tab's data for the new team, with no
stale panel left over from the previous one.

---

## Page 9 — Players · **BLOCKED · new in v0.3**

**Purpose.** One player, drilled into. Restored to v0.3 because `fct_play` and
`fct_player_game_stat` had zero referencing pages — a fact table nothing reads is either unjustified
or evidence of a missing page, and here it was the page.

**Primary views.** `srv_player_stats` (player × season) and `srv_player_game_log` (player × game).
**Blocked by.** `dim_athlete`, `fct_player_season_stat`, `fct_player_game_stat`, `fct_play`.
**Readiness `[A 08-20c]`.** Exists ✗ · Complete ✗ · Published ✗ — **NOT BUILDABLE**, and correctly last.
**Build order.** **Last.** Four tables, and unlike the other blocked pages not all of its raw data is
landed. The other four blocked pages each need one table off data already on disk.

### Required columns — `srv_player_stats`

`player_id` · `player_display` · `team_slug`/`display`/`logo_url` · `position` · `jersey` · `class` ·
`height`/`weight` · `season` · `games_played` · `stat_category` · `stat_name` · `stat_value` ·
`stat_rank_in_position` · `stat_percentile_in_position` · `qualifying_n` ·
`qualifying_threshold_display` · `usage_pct` · `as_of_ts`

### Required columns — `srv_player_game_log`

`player_id` · `game_id` · `week` · `opponent_slug`/`display`/`logo_url` · `is_home` ·
`result_display` · plus per-category stat columns · `epa_per_play` · `snaps` · `as_of_ts`

### Acceptance criteria

**AC-9.1** — The page renders Degraded until its tables exist, naming all four and stating plainly
that it is scheduled after the other four blocked pages.
**AC-9.2** — **The page always opens filtered to exactly one player.** It never renders an unfiltered
league-wide list. Without this the page becomes an unbounded scan of the largest fact tables in the
model.
**AC-9.3** — Four tabs — Overview, Game log, Splits, Plays.
**AC-9.4** — The Plays tab is lazy-loaded and always filtered to one player-game before any query
against a `fct_play`-derived view is issued (AC-G.39).
**AC-9.5** — Percentiles are computed in the serving view and always render with `n` and the
qualifying threshold (AC-G.33).
**AC-9.6** — Player search resolves to `player_id`, and the URL carries the id, not the name. Names
are not unique and are not stable.
**AC-9.7** — Game log rows click through to Matchup.
**AC-9.8** — A player who changed teams mid-career renders the team for the selected season, not the
current one.

### Out of scope for v1

Leaderboards, recruiting, transfer portal, injury status, snap-count charting.

---

## Page 10 — Matchup

**Purpose.** The decision surface. This is the page where a user decides whether to bet, which is why
it is deliberately the widest view in the model and why it keeps a nav slot rather than existing only
as a drill-through.

**Primary view.** `srv_matchup` — grain: game. **`[A 08-20]` Built — 110,634 rows × 65 columns.**
**Readiness `[A 08-20b]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** See the readiness section; "data ready" is withdrawn.

> `[A 08-20]` v1.0 called this absent. It exists, and it is the largest view in `serving`. **It must
> never be queried without a `game_id` filter** — see the amended AC-G.40. AC-10.1's Degraded
> fallback is retired.

### Required columns

Build it wide. Both teams' identity, both teams' ratings, the market, the model, the context.

| Group | Columns |
|---|---|
| Identity | `game_id` · `season` · `week` · `season_type` · `start_date_et` · `home_team_slug`/`display`/`logo_url`/`color_on_light`/`color_on_dark` · same for away |
| Venue | `venue_display` · `venue_city`/`state` · `is_neutral_site` · `is_dome` · `elevation_ft` · `capacity` · `surface` |
| Travel & rest | `home_rest_days`/`away_rest_days` · `away_travel_miles` · `elevation_delta_ft` |
| Weather | `temperature_f` · `wind_mph` · `wind_direction` · `precipitation_pct` · `weather_summary` · `is_weather_forecast` (vs observed) |
| Ratings | `home_sp_plus`/`rank` · `away_sp_plus`/`rank` · `home_elo`/`away_elo` · `home_srs`/`away_srs` · `home_adj_epa_off`/`def` · same for away · each with a percentile |
| Form | `home_record_display` · `away_record_display` · `home_last_5_display` · `away_last_5_display` · `home_ats_record_display` · `away_ats_record_display` |
| Market | `spread_open` · `spread_current` · `spread_move` · `total_open` · `total_current` · `total_move` · `home_moneyline` · `away_moneyline` · `provider_display` · `snapshot_ts` |
| Model | `predicted_margin` · `predicted_total` · `predicted_home_score`/`away_score` · `prediction_interval_low`/`high` · `home_win_probability` · `market_implied_home_win_probability` · `devig_method` · `home_cover_edge` · `home_win_probability_edge` · `is_out_of_sample_week` · `model_version_key` · `attribution` |
| History | `series_record_display` · `series_last_meeting_display` · `series_last_meeting_game_id` |
| Result | `is_completed` · `home_points`/`away_points` · `actual_margin` · `cover_result` · `total_result` |
| Meta | `as_of_ts` |

### Acceptance criteria

**AC-10.1** `[A 08-20]` REVISED — The page always queries `srv_matchup` **with a `game_id`
filter**. Arriving with no `game_id` renders a game-picker Empty state, never an unfiltered scan of
110,634 rows.
**AC-10.2** — The page is reachable directly from nav **and** by clicking any game row anywhere on
the site. Both routes land on the identical state.
**AC-10.3** — Every comparative row renders both teams symmetrically. A metric present for one team
and null for the other renders `—` on the null side rather than dropping the row.
**AC-10.4** — Team colours identify the two sides — an accent rule per column — and encode nothing.
Comparative bars use a neutral ramp (AC-G.24, AC-G.25).
**AC-10.5** — Spread and predicted margin are both stated in the home-negative convention, and the
page says which convention it is using. This is the single most misread number on the site.
**AC-10.6** — `snapshot_ts` renders next to the line. A line without a capture time is not
usable for edge, and the Formatted-Spread-versus-Spread divergence in the historical workbooks is
exactly what happens without it.
**AC-10.7** — `home_cover_edge` is read from the view. It is **not** recomputed here, even though the
formula is one subtraction (AC-G.2).
**AC-10.8** — `is_out_of_sample_week` renders as a chip wherever a model number appears.
**AC-10.9** — Weather shows whether it is forecast or observed, and a game far enough out to have no
forecast renders Empty, not zeroes.
**AC-10.10** — Series history links to the last meeting's Matchup page.
**AC-10.11** — After a game completes, the page shows prediction against outcome side by side. The
model's misses stay visible; nothing is hidden once it is wrong.
**AC-10.12** — Attribution renders (AC-G.41).
**AC-10.13** — Despite its width the page issues at most 2 queries (AC-G.38). Width is the view's
job, not the app's.

---

# Part 2 — Betting

---

## Page 11 — Odds Board

**Purpose.** Current lines across providers, with the model's number alongside.

**Primary view.** `srv_odds_board` — grain: game × provider, latest snapshot. **ABSENT.**
**Readiness `[A 08-20c]`.** Exists ✗ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** Buildable in full from `fct_betting_line`, which is populated — no deferred facts. It ships complete in step 1.

> **`[A 08-20]` The second costly inference.** Nothing else backs this page — unlike Team page there
> is no partial fallback, because the whole page *is* the provider comparison. It renders Degraded,
> in the nav, naming `srv_odds_board`, until the view is built.
>
> The underlying data exists — `fct_betting_line` is populated and `srv_line_movement` reads it — so
> this is a view to write, not ingestion. It sits alongside `srv_team_overview` in the build list.

### Required columns

`game_id` · `season`/`week` · `start_date_et` · team identity for both sides ·
`provider_key` · `provider_display` · `spread` · `spread_open` · `total` · `total_open` ·
`home_moneyline`/`away_moneyline` · `home_implied_probability`/`away_implied_probability` ·
`devig_method` · `snapshot_ts` · `is_latest_snapshot` · `predicted_margin` ·
`home_cover_edge` · `model_version_key` · `attribution` · `as_of_ts`

### Acceptance criteria

**AC-11.1** — One row per game per provider, and the board defaults to the latest snapshot per pair.
**AC-11.2** — `dim_provider` is joined on `provider_key`, never on a raw provider string. Provider
name variants are a dimension problem, not a display problem.
**AC-11.3** — Best available line per game is highlighted per market, and "best" is a column from the
view, not an app-side `max()`.
**AC-11.4** — `snapshot_ts` renders on every row (AC-10.6).
**AC-11.5** — A game with lines from only one provider renders normally rather than as a comparison
with blanks.
**AC-11.6** — Model columns render Degraded per row where no prediction exists.
**AC-11.7** — Row click → Matchup. Provider column click → Line Movement filtered to that game and
provider.
**AC-11.8** — The page renders as a table, not as cards. This is a scanning surface and density is
the point.

---

## Page 12 — Edge Finder

**Purpose.** Where the model and the market disagree, filtered to disagreements large enough and
historically reliable enough to act on.

**Primary view.** `srv_edge_finder` — grain: game × bettable market. **Built, carrying 3,402 real
predictions.**
**Readiness `[A 08-20b]`.** Exists ✓ · Complete ✗ (4 of 19 columns) · Published ✗ — **NOT
BUILDABLE.** And when it is, it ships v1 without its calibration layer.

> **`[A 08-20]` DECIDED — ship degraded now, build the bucket model next.**
>
> `edge_bucket`, `bucket_hit_rate` and `bucket_n` **do not exist anywhere in the model.** There is
> no edge-bucket aggregation at all. `srv_model_performance` carries `games`, `winner_scored` and
> `cover_scored` — honest denominators, but at a different grain. Building the aggregation is a new
> mart model, not a column.
>
> This is uncomfortable, because the hit-rate slider is the control I argued hardest for: *"the one
> that actually protects you."* Shipping the page without it means shipping an edge list whose only
> filter is magnitude — and magnitude is the seductive number, not the protective one.
>
> The resolution: **ship the page with the magnitude slider, and render the hit-rate slider, the `n`
> column and the calibration panel as Degraded**, naming the missing model. A control that is
> visibly absent is honest. A control that silently defaults to 0 is a false protection, which is
> worse than no protection. Then build `fct_edge_bucket_performance` as the next data task.

### Required columns

`game_id` · `season`/`week` · `start_date_et` · team identity both sides · `market`
(`spread` \| `total` \| `moneyline`) · `line` · `provider_display` · `snapshot_ts` ·
`model_value` · `edge` · `edge_abs` · `edge_bucket` · `bucket_hit_rate` · `bucket_n` ·
`kelly_fraction` · `kelly_units` · `recommendation` (`bet` \| `pass`) · `is_out_of_sample_week` ·
`market_implied_home_win_probability` · `devig_method` · `home_win_probability` ·
`home_win_probability_edge` · `rest_days_home`/`away` · `travel_miles` · `elevation_delta_ft` ·
`weather_summary` · `model_version_key` · `attribution` · `as_of_ts`

### Controls

Week · market · conference · **minimum edge** (stepped slider) · out-of-sample-week filter.

**`[A 08-20]` Deferred to the follow-on build**, rendering Degraded until `fct_edge_bucket_performance`
exists: **minimum bucket hit rate** (stepped slider, default 52.4) and the "require n ≥ 30"
checkbox.

### Acceptance criteria

**AC-12.1** `[A 08-20]` REVISED — Sliders filter rows. **They compute nothing** (AC-G.2). Moving a
slider changes which rows show, never any value in them.
**AC-12.2** `[A 08-20]` DEFERRED — When the hit-rate slider exists it defaults to **52.4**, the
breakeven at −110. **It is never shipped defaulted to 0** — that is a control that looks like a
protection and is not one. Until the bucket model exists the slider renders Degraded rather than
disabled-at-zero.
**AC-12.3** `[A 08-20]` REVISED — The page **must not render a hit rate it cannot back with an `n`**.
Until `fct_edge_bucket_performance` exists, no hit rate renders on this page at all, and the
calibration panel states why. When it exists, `bucket_n` renders adjacent to `bucket_hit_rate` on
every row, always (AC-G.33) — a 17.9-point edge on n=11 is noise wearing a big number.
**AC-12.3b** `[A 08-20]` NEW — The page carries a visible statement that edges are currently ranked
by **magnitude only**, with no historical reliability filter, and that magnitude alone does not
indicate value. This is the copy that stands in for the missing control.
**AC-12.4** — The heading states how many games clear the current thresholds out of how many total.
**AC-12.5** — **`is_out_of_sample_week` renders as a chip on every row.** Every hit rate currently on this
page comes from the 2025 held-out test split, not from live betting. A backtest hit rate and a
realised hit rate must never render in identical styling.
**AC-12.6** — The page carries a persistent, visible statement that current figures are backtest
figures — not a tooltip, not a footnote.
**AC-12.7** — `devig_method` is displayed or reachable in one interaction wherever an implied
probability appears, and the Methodology page states the assumption in full.
**AC-12.8** — `kelly_units` renders `0.0u` rather than hiding the row when the recommendation is
pass. A zero-stake recommendation is information.
**AC-12.9** `[A 08-20]` REVISED — Row expansion shows drivers, edge-bucket calibration and context.
**Both the drivers panel (SHAP) and the calibration panel currently render Degraded**, each naming
what is missing. Neither is silently omitted — an absent panel that is labelled is information; an
absent panel that is invisible is a lie by omission.
**AC-12.10** — Threshold settings persist across navigation (§0.4), because they encode a posture
rather than a view.
**AC-12.11** — Attribution renders (AC-G.41).
**AC-12.12** — The page never states or implies that a filtered set is profitable. Surfacing more
rows is not the same as finding more value, and the copy says so.

---

## Page 13 — Model Performance

**Purpose.** Honest measurement. This page exists to measure, not to flatter, and its headline is
currently that the best model does not beat the market.

**Primary view.** `srv_model_performance` — grain: model_version × segment. **Confirmed built.**
**Readiness `[A 08-20c]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** Published is ✗ for *every* page until `serving` is on the droplet.

### Required columns

`model_version_key` · `model_display_name` · `attribution` · `trained_on_display` ·
`is_active` · `segment_type` (`overall` \| `week` \| `conference` \| `edge_bucket` \|
`favorite_underdog` \| `home_away` \| `calibration_decile`) · `segment_value` · `n_predictions` ·
`margin_mae` · `total_mae` · `su_accuracy` · `ats_hit_rate` · `roi_flat_1u` ·
`market_margin_mae` · `market_su_accuracy` · `predicted_mean` · `realized_mean` ·
`is_out_of_sample_week` · `sample_window_display` · `as_of_ts`

### Acceptance criteria

**AC-13.1** — Headline figures are read from the view. The page shows **margin MAE 11.75, SU 73.5%,
ATS 51.4%** for `ridge_margin_expanded` on the 2025 held-out split only if that is what the view
returns — if the numbers differ, **the view is right and this document is stale.** Report the
difference; do not hardcode either.

> **`[A 08-20b]` Right about the numbers, wrong about the shape.** `srv_model_performance` carries
> **1 of the 17 columns** this section requires — there is no `segment_type` / `segment_value`
> structure at all. The three figures quoted are what the view returns, so the document is accurate
> where it is checkable and wrong where it is not. The segment structure is part of the widening
> pass.
**AC-13.2** — Market comparison renders beside every model figure that has one.
**AC-13.3** — ATS below the 52.4% breakeven renders in the negative treatment. The page does not
soften a losing number.
**AC-13.4** — **The seventh model renders as a visible row marked not loaded**, not as a shorter
table. `fastai_wp_predictions.csv` was never written; a missing model is an absence the page states.
**AC-13.5** — `sample_window_display` renders next to every figure, so a held-out-split number is
never mistaken for a live-season number.
**AC-13.6** — Where the page compares the pack model to the prior model, it states that the
comparison is **directional rather than like-for-like** — different model, different sample window —
in the rendered page, not only in this document.
**AC-13.7** — By-week accuracy renders Empty until live 2026 results exist. It does not render the
held-out split on a week axis a user would misread as this season.
**AC-13.8** — Calibration plots `predicted_mean` against `realized_mean` by decile with a 45°
reference, both series from the view.
**AC-13.9** — Model registry lists every version with its prediction count and active flag, from
`dim_model_version`.
**AC-13.10** — CLV renders Degraded, naming the snapshot history it is waiting on.
**AC-13.11** — Attribution renders (AC-G.41), and `attribution` is `not_null`-tested in
dbt (AC-G.44).
**AC-13.12** — No figure on this page is computed in Python. Every one is a column (AC-G.2).

---

## Page 14 — Line Movement

**Purpose.** How a line moved between open and now, and eventually what that says about closing line
value.

**Primary view.** `srv_line_movement` — grain: game × provider × snapshot_ts. Inferred built.
**Readiness `[A 08-20c]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** Published is ✗ for *every* page until `serving` is on the droplet. Line history is also still accumulating.

### Required columns

`game_id` · `season`/`week` · team identity both sides · `provider_key`/`display` ·
`snapshot_ts` · `spread` · `total` · `home_moneyline`/`away_moneyline` · `is_opening_line` ·
`is_closing_line` · `spread_delta_from_open` · `predicted_margin` · `as_of_ts`

### Acceptance criteria

**AC-14.1** — With fewer than two snapshots for a game, the page renders Empty explaining that
movement needs at least two captures and naming the next capture time — it does not render a
one-point line.
**AC-14.2** — Time series are drawn per provider, with provider as the series legend.
**AC-14.3** — The model's number renders as a horizontal reference line, visually distinct from
market series.
**AC-14.4** — Opening and closing lines are flagged from columns, never inferred by taking min/max of
`snapshot_ts` in the app.
**AC-14.5** — The 4-hourly snapshot cadence is stated on the page, so a flat segment reads as "no
capture" rather than "no movement".
**AC-14.6** — Deep-linkable by `game_id` and `provider`.
**AC-14.7** — CLV renders Degraded until enough history exists, naming the dependency.

---

# Part 3 — Deliverable and reference

---

## Page 15 — Excel Export

**Purpose.** The take-away artifact — a rich, information-dense workbook of what the user is already
looking at.

**Primary views.** Whichever views back the sheets requested. No new views for export.
**Readiness `[A 08-20c]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** Sheets whose source is missing are omitted, not shipped empty.

### Scope rule — this is the feature closest to the licence line

CFBD prohibits redistribution as raw data, and a feature-rich workbook sits closer to that than a
rendered page does. Three things keep it comfortably inside:

1. **Exports are scoped to what the user can already see** — a week's slate, a team, a matchup, a
   season of results. **No "download all seasons", no full-corpus dump, no raw layer, ever.**
2. The site is behind Cloudflare Access with an email allowlist. Not public distribution.
3. Attribution on every sheet, plus the model disclaimer on any sheet carrying predictions.

If a future request sounds like "let me pull the whole database into Excel", that is the line and
the answer is no.

### Acceptance criteria

**AC-15.1** — Export scope is always bounded by the current filter set. There is no control that
exports beyond what the current filters describe.
**AC-15.2** — No sheet sources from `raw` or `staging`. Every sheet is a serving view (AC-G.3).
**AC-15.3** — Every sheet carries CFBD attribution in a fixed cell.
**AC-15.4** — Every sheet carrying predictions additionally carries the model disclaimer and the
`is_out_of_sample_week` flag per row.
**AC-15.5** — A blocked sheet is **omitted with a note on the index sheet naming what is missing**,
never shipped as an empty tab.
**AC-15.6** — The workbook opens without a repair prompt in Excel and in LibreOffice.
**AC-15.7** — Numeric cells are typed as numbers with the same precision as the site (AC-G.31), not
as strings.
**AC-15.8** — Column headers match the site's labels exactly, and the Data Dictionary sheet defines
each one from the same `srv_data_dictionary` the site page uses — so the workbook and the page
cannot drift.
**AC-15.9** — The index sheet states generation timestamp, filter scope, row counts per sheet, and
the model version.
**AC-15.10** — Filename encodes scope and date: `cfdb_week08_2026_20260820.xlsx`.
**AC-15.11** — Generation is under 10 s for a full week's slate.
**AC-15.12** — Formatting is native Excel — real headers, freeze panes, autofilter, conditional
formatting on edge and cover columns. The deliverable is meant to be worked in, not just read.

---

## Page 16 — Data Dictionary `[A 08-20]` **unblocked**

**Purpose.** What every field means, where it came from, and how confident we are in the definition.

**Primary view.** `srv_data_dictionary` — **957 rows.** `dim_field_metadata` — **also 957**.
**Readiness `[A 08-20b]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.**

> **`[A 08-20b]` v1.1's "957 / 834" was two build times, not two objects.** `dim_field_metadata` is
> a **view over the live catalog**, so its row count moves whenever a model is added. Both are 957
> today and both will change tomorrow. Never quote its count as a fixed figure.
>
> **Coverage is 30.5% — 292 of 957 columns described — down from 41.6%**, because views were added
> faster than descriptions were written. That number falling is not a regression in the data; it is
> the coverage metric working. The page should make a falling number visible rather than smoothing
> it.

### The coverage problem this page exists to solve

CFBD's OpenAPI spec documents **74 of 74 endpoints and 289 of 289 parameters, but only 4 of 1,017
fields.** Field descriptions are ours to author — **151 of them inside Phase 1.**
`cfdb_data_dictionary.xlsx` is the generated upstream input.

### Required columns

`schema_name` · `table_name` · `column_name` · `data_type` · `is_nullable` ·
`description` · `description_status` (`authored` \| `from_openapi` \| `inferred` \| `UNDOCUMENTED`) — **`[A 08-20b]` a NEW column; the view has only `is_documented` (boolean)** ·
`source_endpoint` · `source_field` · `unit` · `valid_values` · `example_value` ·
`is_phase_1` · `related_columns` · `last_reviewed_date` · `as_of_ts`

### Acceptance criteria

**AC-16.1** — Descriptions live in dbt `schema.yml` with `persist_docs`, so the site page and the
Excel sheet read the same source and cannot drift.
**AC-16.2** `[A 08-20b]` REVISED — **`UNDOCUMENTED` is a rendered, first-class value.** An honest
gap beats a plausible guess, and the page must never invent a definition to look complete. **This
requires a new `description_status` column** — the view currently carries only `is_documented`
(boolean), which cannot distinguish "we wrote this" from "CFBD wrote this" from "nobody has". The
four-value vocabulary is a build item, not a rename.
**AC-16.3** `[A 08-20b]` — The page shows documented-versus-total counts overall and for Phase 1,
so coverage is measurable rather than asserted. **It renders the current figure whatever it is** —
30.5% today, down from 41.6%. A coverage metric that only ever goes up is a metric someone is
managing rather than measuring.
**AC-16.4** — Filterable by schema, table and `description_status`; searchable by column name and by
description text.
**AC-16.5** — `source_endpoint` links to CFBD's documentation where one exists.
**AC-16.6** `[A 08-20b]` REWRITTEN — v1.1's version was **trivially true and tested nothing**: the
view reads `information_schema`, so every serving column appears by construction. The criterion
worth having is the one that is currently false —

> **Every column of every `srv_` view has a non-null `description`.** A serving column with no
> description fails a dbt test. Currently false for **69%** of them, and the failing test is the
> point: it converts a documentation backlog into a visible, countable debt rather than an
> intention.

Set the test's severity to `warn` until coverage clears a threshold you choose, then raise it to
`error`. A test that fails 665 times on day one gets muted; one that warns and is tracked gets
paid down.
**AC-16.7** — The Excel Data Dictionary sheet is generated from this same view (AC-15.8).
**AC-16.8** — `devig_method`'s entry states the multiplicative-normalisation assumption in full.

---

## Page 17 — Methodology

**Purpose.** How everything on the site is computed, in prose a non-specialist can follow. The page
that makes the difference between a dashboard and a portfolio piece.

**Primary view.** Largely static content, with `dim_model_version` and `dim_field_metadata` supplying
the parts that must not go stale.
**Readiness `[A 08-20c]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** Published is ✗ for *every* page until `serving` is on the droplet.

### Required sections

1. **Data sources and licences** — CFBD API and the CFB Model Training Pack, what each permits, and
   the commercial asymmetry: CFBD data may be displayed commercially, Model Pack outputs may not.
2. **The provenance rule** — the same number can be publishable or not depending on where it came
   from. `adjusted_epa` from CFBD's `/wepa/team/season` is displayable; the identical column read out
   of the pack's `training_data.csv` is not.
3. **Pipeline** — raw → staging → marts → serving, and why the site reads only the last one.
4. **The models** — what each predicts, what it was trained on, what its held-out performance is.
5. **De-vig** — multiplicative normalisation, the formula, and the assumption stated plainly: vig is
   proportional to implied probability. Also why: Shin's method and the power methods correct
   favourite–longshot bias better, but the gain on two-way markets is small and the explanation is
   long. **For a project whose differentiator is honest measurement, explainability outranks
   marginal accuracy.**
6. **Edge and Kelly** — the definitions, and the sample-size caveat.
7. **Sign conventions** — `margin = away − home`, spreads home-negative. Stated once, definitively.
8. **What the model does not do** — no injuries, no line-shopping across books beyond what is
   captured, no in-game updating.
9. **Known limitations** — including that the model does not beat the market.

### Acceptance criteria

**AC-17.1** — Model figures quoted in prose are **read from `dim_model_version` and
`srv_model_performance`**, not typed into the page. A number that can go stale is not allowed to be
static text.
**AC-17.2** — The de-vig section states the formula, the method name, and the assumption.
**AC-17.3** — Licence terms are stated accurately for both sources, including the commercial
asymmetry.
**AC-17.4** — The limitations section is on the same page as the performance claims, not linked from
it.
**AC-17.5** — The page states plainly that these are cfdb's own predictions and not official
CollegeFootballData.com predictions.
**AC-17.6** — Every term used elsewhere on the site is either defined here or linked to its Data
Dictionary entry.
**AC-17.7** — The page renders with no database dependency beyond the two views named, so it is never
the reason a deploy looks broken.

---

# Part 4 — Back of house

---

## Page 18 — System Overview `[A 08-20]` **unblocked**

**Purpose.** Is the pipeline healthy, is the data fresh, what failed. Back of house — nothing here
belongs on Today.

**Primary view.** `srv_system_health` — **built, 224 rows.** `fct_dq_test_result` carries 153.
**Readiness `[A 08-20b]`.** Exists ✓ · Complete ✗ · Published ✗ — **NOT BUILDABLE.** See the readiness section; "data ready" is withdrawn.

> `[A 08-20]` With 245/245 Postgres and 225/225 Databricks tests passing, this page currently has
> nothing to report as failing. AC-18.8 is the one that matters most in that state: **a green board
> must mean every check passed, not that no checks ran.**
>
> **`[A 08-20b]` This page now also owns the freshness signal.** The app's standalone freshness
> banner is retired (see the build order) in favour of per-page `as_of_ts` per AC-G.35. Detailed
> endpoint-level freshness belongs here, back of house, which is where AC-1.7 always said it
> belonged.

### Required sections and columns

| Section | Source | Key columns |
|---|---|---|
| Endpoint freshness | **`[A 08-20b]`** built as `mart_data_freshness`, not `fct_endpoint_freshness`. Needs a serving equivalent. | `endpoint` · `last_success_ts` · `hours_since` · `expected_cadence_hours` · `freshness_status` · `row_count_last_load` |
| dbt test results | `fct_dq_test_result` | `run_id` · `run_ts` · `model_name` · `test_name` · `status` · `failure_count` · `severity` |
| Data quality issues | `fct_dq_test_result` | `issue_type` · `affected_table` · `affected_rows` · `example_value` · `first_seen` · `status` |
| API usage | `fct_api_usage` | `endpoint` · `calls_this_month` · `tier_limit` · `pct_of_limit` |
| Pipeline runs | **`[A 08-20b]` `fct_pipeline_run` DOES NOT EXIST.** Nothing captures Airflow run history. Render the section Degraded per AC-18.7 — do not present a non-existent object as a source. | — |

### Acceptance criteria

**AC-18.1** `[A 08-20b]` REVISED — `fct_dq_test_result` exists (153 rows). The sections that render
Degraded are now the two whose sources do not: **pipeline runs** (`fct_pipeline_run` does not exist)
and **endpoint freshness** until a serving equivalent of `mart_data_freshness` is built. Each names
its own missing object.
**AC-18.2** — Freshness status is a column driven by `expected_cadence_hours`, not an app-side
comparison against a hardcoded threshold. Cadence is season-aware and the app must not duplicate that
logic.
**AC-18.3** — A failing dbt test renders with its model, test name and failure count — enough to act
on without opening a terminal.
**AC-18.4** — API usage renders against the tier limit as a proportion, so approaching the ceiling is
visible before it is hit.
**AC-18.5** — **No content from this page appears anywhere in front of house.**
**AC-18.6** — Nothing on this page renders a request URL, an API key, a connection string or any
`raw_manifest` content. Manifest objects never leave the transform tier (AC-G.9).
**AC-18.7** — Where Airflow run history is not captured, the section says so rather than rendering an
empty table implying no runs happened.
**AC-18.8** — A green board means every check passed, not that no checks ran. Zero rows renders as
"no results recorded", never as "all clear".

---

# Part 5 — Build order `[A 08-20c]` **narrowed, and split into two tracks**

**v1.2's step 1 could not complete as scoped.** It treated 104 missing columns as one homogeneous
widening. They are not: a large share depend on facts this same document scheduled *later* — some
after step 8, some not at all. `srv_team_overview` was the sharpest case, roughly half its columns
coming from `fct_team_week_rating`, which was deferred past step 8. **Step 1 blocked on step 8**, and
with everything queued behind one un-mergeable PR that is the one-pass decision's failure mode
arriving on day one rather than eventually.

**The one-pass decision stands. Its scope narrows.** The contract is restated:

> **Complete with respect to facts that exist today.** Anything sourced from a fact not yet built
> renders **Degraded**, naming the fact. That is what Part 0's Degraded state was written for, and
> using it here is not a compromise — it is the mechanism working.

Without the restatement, "no partially-contracted serving layer" is unachievable until step 8
regardless, so the phrase would be protecting nothing.

---

## TRACK A — the site. Nothing here waits on a fact that does not exist.

| # | Work | Notes |
|---|---|---|
| **A1** | **Serving completeness pass — one PR.** Everything derivable from built facts. | See the column list below |
| **A2** | **Publish `serving` to the droplet + repoint the app — ONE DEPLOY.** | Scoping `cfdb_read` to `serving` and revoking `marts` breaks the running app the instant it lands. v1.2 had these as separate steps; they ship together or in strict order inside one deploy. |
| **A3** | Shared foundation — four-state renderer, chip, query helper, team identity, query-param layer, formatter, attribution component, `st.navigation` nav | Built against real, complete-to-built-facts views |
| **A4** | **Build 17 pages.** Sections sourced from deferred facts render Degraded, naming the fact. | This is where the site exists |
| **A5** | **Excel Export — its own task `[A 08-21]`.** | Split out of A4 on Claude Code's recommendation, and it is right: 12 acceptance criteria, a workbook generator rather than a page, and **the closest thing on the site to the licence line**. Tailing it onto A4 guarantees it gets the least attention, and it is the one deliverable where the boundary is a judgement call rather than a structural fact. |
| **A6** | **Deploy-tree staleness guard `[A 08-21]`** — surface deploy SHA vs `main` SHA on System Overview as a `deployment` signal in `srv_system_health`. | See below |

### A1 — in scope

`team_slug` + display names + contrast-safe colour columns on `dim_team` · `as_of_ts` on every
`srv_` view · `start_date_et` · records · ranks from `fct_poll_rank` · `attribution` +
`model_version_key` on the three prediction views · `segment_type` / `segment_value` structure on
`srv_model_performance` · `description_status` on the dictionary chain · **`is_upset`** (now
derivable — `fct_poll_rank` exists; a **new column**, not an assumed one) · **`excitement_index`**
(112,272 raw games carry it, unmodelled) · **`network`** (a small staging model over the landed
`raw/games_media`; it was invisible in every prior build order) · **`srv_odds_board` in full** —
`fct_betting_line` is populated, so it has no deferred dependency.

### A1 — explicitly out of scope, rendering Degraded

`sp_plus_*`, `elo_*`, `srs_*` · `adj_epa_off/def`, `success_rate`, `havoc_allowed` ·
`temperature_f`, `wind_mph`, `weather_summary` · `home_rest_days`, `away_travel_miles`,
`elevation_delta_ft` · `coach_display` · `returning_production_pct`, `talent_rank`

**`srv_team_overview` is built narrowed** — identity, record, conference standing and ATS from built
facts; its ratings and profile block renders Degraded naming `fct_team_week_rating`.

### `prediction_interval_low` / `high` — no source, and not to be invented `[A 08-20c]`

The interval appears **zero times** in the pack's export contract. There is nothing to widen to.

**DECIDED: do not derive one.** AC-8.5's own reasoning — a bare point estimate overstates what an
11.75-point MAE knows — is precisely why a casually-invented interval is worse than none: it would
put a confidence claim on screen that no model made. **AC-8.5 is amended:** render the point estimate
with the model's MAE stated immediately beside it, and render an interval only where a model emits
one. Honest today, and it upgrades itself the day a quantile model ships.

---

## TRACK B — the facts. Runs in parallel. Gates nothing in Track A.

Raw is landed for most of these, so they are model-able now — but they are **new facts, not view
widening**, which is exactly the distinction v1.2 missed.

| # | Fact | Raw | Un-degrades |
|---|---|---|---|
| **B1** | **`fct_team_week_rating`** | `ratings_sp` 8 files + landed Elo/SRS | Matchup, Teams, Standings, Team page — **the single largest source of Degraded sections on the site** |
| B2 | `fct_game_weather` | `games_weather` 5 files | Matchup |
| B3 | Venue join key — `fct_game` carries a venue **name**, not an id | landed | rest / travel / elevation on Matchup and Edge Finder |
| B4 | `fct_team_talent`, `fct_returning_production` | landed | Teams, Team page |
| B5 | `dim_coach` | `coaches`, 142 | Team page |
| B6 | `fct_edge_bucket_performance` | derived | Edge Finder's hit-rate slider, `n`, calibration |
| B7 | CFBD `/ratings` + `/ppa` adjusted metrics — **never the pack CSV** | new calls | Stats four-way toggle |
| B8 | `dim_athlete`, `fct_player_season_stat`, `fct_player_game_stat`, `fct_play` | partial | **Players. 18 of 18.** |


### The parity gate — amended, because it can fail for the right reason `[A 08-22]`

The cutover gate was specified as *"a dbt test proves each `srv_` view is row-for-row identical to
the mart it replaces."* **That framing breaks the moment the new side gets better**, and it did:
`mart_team_season_record.school` inherited the `dim_team` null-identity defect, `srv_standings` was
fixed, and the gate failed on **14,964 rows because the serving view became more correct**.

Under a literal reading, the cheapest way to make that gate green is to **re-introduce the bug on the
new side**. That is a real hazard in a deadline week and it is this document's fault.

**THE RULE, amended: when parity fails, the question is WHICH SIDE IS RIGHT — never how to make them
match.**

| Situation | Action |
|---|---|
| New side wrong | Fix the new side. The gate did its original job. |
| **Old side wrong** | Fix the old side, or **retire it**. Record an **expected divergence** with row count and reason. **Never weaken the new side.** |
| Both wrong | Fix both; the gate was never the point. |

An expected divergence is **recorded, not suppressed**. A gate that can be silenced by making the new
thing worse is worse than no gate.

### The worktree pin's second-order effect `[A 08-21]`

The pin fixed *"a dev checkout silently changes production scheduling."* It created the opposite
failure: **production silently kept running old code.** The deploy tree sat on PR #17 while
development reached PR #19, so the nightly Databricks sync and the weekly refreshes were building a
dbt project containing **none of A1** — 39 models instead of 56.

Both failures are the same underlying thing: the deploy tree and the dev tree diverge. The pin
changed which *direction* the divergence runs, and pinning to `main` means **someone has to actively
move the pin** — a manual step with no alarm on it. `scripts/deploy_main.sh` is the step; A6 is the
alarm.

The guard is cheap and belongs where the page already exists. `srv_system_health` already carries
`signal_type` values `freshness`, `data_quality`, `documentation`, `quota`. Add **`deployment`** —
deploy SHA, `main` SHA, commits behind, severity escalating past a threshold. A divergence that is
visible is an inconvenience; one that is invisible spent days building the wrong project.

### `fct_team_week_rating` moves to the front of Track B `[A 08-20c]`

It has been deferred for four rounds on the grounds that it is **primary on zero pages**. That
reasoning was right about *blocking* and wrong about *value*. It blocks nothing from rendering and it
is the **largest single source of Degraded sections** across the finished site — four pages, and the
most-quoted numbers on each. It is B1.

---

# Appendix C — Amendment log

What changed, and why. Kept so the next reader can see which parts of this document have been
tested against reality and which have not. Newest first.

## v1.2 `[A 08-20b]` — the column-level audit

**The systemic finding, and the third instance of one pattern.** v1.1 answered *does the view
exist*. It then treated existence as readiness. **104 of 135 required serving columns are absent —
77%.** A readiness definition with a gate now sits ahead of Part 0, because "check more carefully"
has failed three times and a definition has not been tried.

**The build order was wrong in a way that would have surfaced on page 3 of 18.** v1.1's step 6
("build the pages") was not reachable after steps 1–5, because no step widened the views. There is
now a serving completeness pass in front of everything, taken in **one pass** by decision — one
parity run, no partially-contracted serving layer, and nothing downstream testable until it lands.

**Two things that were impossible rather than merely unmet:**

- `serving` **is not on the droplet.** `publish_marts.py` ships three tables into `marts`. AC-G.4's
  inverse is what is actually true today.
- **No slug column exists in `dim_team`**, and AC-G.14 forbids deriving one in Python. Every deep
  link on the site turns on one dbt change.

**The parity gate was overstated in the decision log and is corrected in Part 5.** Met for two of
three published marts. The third, `mart_data_freshness`, has no like-for-like pair — resolved by
**retiring the freshness banner** in favour of per-page `as_of_ts`, rather than by declaring a
supersession that no proof supports.

**Four page-level corrections.** Page 16's counts (both objects are 957, and `dim_field_metadata` is
a live-catalog view whose count moves), coverage restated at 30.5% and falling, AC-16.6 rewritten
because it was trivially true and tested nothing, and `description_status` identified as a new
column rather than a rename. Page 18's `fct_endpoint_freshness` is `mart_data_freshness` and
`fct_pipeline_run` does not exist. AC-13.1 is right about the numbers and wrong about the shape.

**What was left alone, on Claude Code's own assessment:** Part 0, the Edge Finder decision, the
provenance rule, the licence asymmetry. **Part 0 has now survived two reconciliations untouched** —
the strongest evidence available that it is the part of this document worth trusting.

## v1.1 `[A 08-20]` — the Task 1 reconciliation

**Two inferences were wrong.** `srv_team_overview` and `srv_odds_board` were marked "inferred built —
page renders". Neither exists. They are now build items 4 and 5. This is the exact failure mode the
confidence column was added to expose, and it worked — but it cost the Task 3 page list being wrong.

**Six views were built that the document called blocked or absent.** Harmless direction to be wrong
in, and the cause is simple: PR #18 landed between the document being written and being read.

**One framing error, and it is the one I would most want corrected.** "13 of 18 pages render" was a
claim about data readiness that read as a claim about the site. The deployed app is a 100-line
prototype reading `mart_*` with none of Part 0 implemented. View built ≠ page rendered, and this
document said otherwise.

**Three criteria were unbuildable as written**, all now revised rather than quietly dropped:
`bucket_n` and the edge-bucket layer do not exist (AC-12.1/12.2/12.3/12.9); `stat_scope` and
`stat_basis` do not exist and require CFBD ingestion (AC-6.1/6.2); AC-G.41 is false on three of four
prediction views.

**One criterion was underspecified rather than wrong.** AC-G.40's paint budget said nothing about
filters, and `srv_matchup` at 110,634 × 65 will not meet it unfiltered. The criterion now carries
its filter.

**Three column names changed to match the database.** `attribution`, `snapshot_ts`,
`is_out_of_sample_week`. The third is not a pure rename — it is a week-level flag rather than a
prediction-level one — and the UI copy must reflect that.

---

# Appendix A — Page numbering versus wireframe screen ids

The wireframe's screen ids are historical; this document numbers pages by nav order. Both are listed
so a reference in either direction resolves.

| Page | Wireframe id | | Page | Wireframe id |
|---|---|---|---|---|
| 1 Today | `s1` | | 10 Matchup | `s9` |
| 2 Schedule | `s2` | | 11 Odds Board | `s10` |
| 3 Scores | `s3` | | 12 Edge Finder | `s11` |
| 4 Rankings | `s4` | | 13 Model Performance | `s12` |
| 5 Standings | `s5` | | 14 Line Movement | `s13` |
| 6 Stats | `s6` | | 15 Excel Export | `s14` |
| 7 Teams | `s7` | | 16 Data Dictionary | `s15` |
| 8 Team page | `s8` | | 17 Methodology | `s16` |
| 9 Players | `s18` | | 18 System Overview | `s17` |

The change-log screen `s0` is wireframe apparatus and is not a site page.

---

# Appendix B — What is deliberately not specified

Listed so their absence reads as a decision rather than an oversight.

- **Live in-game scoring.** Needs a different ingestion cadence and a different failure model.
- **Below 768 px.** The site states the limitation rather than degrading silently (AC-G.48).
- **Authentication and authorisation.** Cloudflare Access handles it; the app has no user model.
- **Bet logging and bankroll tracking.** `fct_bet` exists in the model but no page owns it in v1.
- **Recruiting, transfer portal, injuries, news.** Cut in v0.2 and still cut.
- **Leaderboards.** Players is a drill-down by design (AC-9.2).
- **Any page reading `marts` directly.** Not an omission — a prohibition (AC-G.4).
