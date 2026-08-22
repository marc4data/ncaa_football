# cfdb — Site Information Architecture & Layout Options

**Date:** 2026-08-17
**Purpose:** Competitive IA review (ESPN / CBS Sports / NCAA.com) → proposed cfdb site map, with 2–3 layout options per section, constrained to what Streamlit can actually render.
**Status:** Draft for review. Mockup format not yet chosen.

---

## 0. Research caveat (read this first)

ESPN, CBS, and NCAA.com are all heavily client-rendered. Roughly half the pages returned **no extractable content** to automated fetching. Everything below is split into what was **verified** (the page actually returned its structure) and what was **inferred from URL patterns or not verified at all**. Where a claim is unverified it is marked. Nothing here is a confident guess dressed up as fact.

| Site | Verified | Not verified |
|---|---|---|
| ESPN | Scoreboard, Standings, Player Stats, Total QBR, Team page + Roster | Schedule, Team Stats, Teams index, Rankings, SP+ tables, Recruiting (robots-blocked), Game/box score/PBP |
| CBS | Scores, Schedule, Standings, Stats, Teams, Rankings, **Odds**, Expert Picks | Playoff bracket (JS), player-stat columns (robots-blocked) |
| NCAA.com | Nav/IA, Rankings (AP + CFP), CFP Bracket structure, scoreboard JSON schema | Scoreboard page, Standings, Stats leaderboards, CFP Schedule |

---

## 1. What the three sites actually do

### 1.1 ESPN — the parity target

**Nav:** Scores · Schedule · Standings · Stats · Teams · Rankings · Total QBR · SP+ · Player Rankings

Verified specifics worth stealing:

- **Every filter is in the URL.** Uniform grammar: `/{section}/_/week/{n}/year/{yyyy}/seasontype/{1|2|3}/group/{conf_id}`. Every view is deep-linkable and bookmarkable. *This is the single most portable idea on the page and Streamlit supports it via `st.query_params`.*
- **Consistent conference filter everywhere.** The identical list (All/FBS, ACC, American, Big 12, Big Ten, CUSA, FBS Indep., MAC, Mountain West, Pac-12, SEC, Sun Belt) appears on scoreboard, standings, stats, and QBR. Learn the control once, use it everywhere.
- **Standings doubles as a rankings surface.** Two-band table: *Conference* (W, L, PF, PA) and *Overall* (W, L, PF, PA, HOME, AWAY, STRK, **AP**, **USA**). Poll rank lives right in the standings row.
- **Scoreboard cards carry betting + key stat lines**, not just the score: spread, over/under, passing/rushing/receiving leader lines, and three links (Gamecast, Box Score, Highlights).
- **Leaderboards cap at 50 rows** and use a two-level tab structure: primary (Offense / Defense / Scoring / Special Teams) → sub-category (Passing / Rushing / Receiving).
- **Total QBR page:** tabs *Season Leaders · Weekly Leaders · All-Time Bests*; columns `RK · Name · QBR · PAA · PLAYS · EPA · PASS · RUN · SACK · PEN · RAW`.
- **CFB team pages have only four tabs** — Home, Schedule, Statistics, Roster. No depth chart, no injuries (that's ESPN's NFL product). Team Home is a module stack: header (record + conference standing + coach) → schedule list → conference standings snippet → team stats with **national rank per metric** → news → recruiting commits with ESPN grade → awards.
- **SP+ is not a page.** It is republished as a Bill Connelly *article*, with a new story ID every week and part of the run behind ESPN+. There is no filterable SP+ table on ESPN. **This is an obvious gap you can beat trivially.**
- **Season depth is uneven:** stats 2004–2026, QBR 2004–2025, standings only 2015–2025.

### 1.2 CBS Sports — the betting-adjacent ideas

- **Odds are an attribute of a game, not a separate vertical.** Spread and total render inline on every scoreboard card and every schedule row, next to the TV network.
- **Expanded ⇄ Compact density toggle** on the scoreboard. On a 60-game Saturday this is high-value and nearly free.
- **One shared filter vocabulary** across Scores, Schedule, and Odds (`All Games · Top 25 · All FBS · All FCS` + every conference).
- **Rankings table has a "Next Game" column** — rank plus who they play next, no click required.
- **Team stats have a Team ⇄ Opponent toggle** — same category viewed as "what we did" vs "what we allowed." Cleaner than duplicating offense/defense category lists.
- **Expert Picks is an experts × games matrix** with a Straight Up ⇄ ATS toggle and **two records per expert (week + season, W-L-push)**, shown honestly including sub-.500 (144-150-5).
- **Every team row exposes four fixed links** (Team / Stats / Roster / Schedule) instead of one.
- **Honest counter-point on the Odds page:** it is a *slate board*, not an analytics tool. One unnamed book. No line movement. No consensus/public %. No book-vs-book comparison. Treat CBS as the floor for odds, not the model.

### 1.3 NCAA.com — the archival ideas

- **Rankings template adapts columns to the poll.** AP/Coaches show `RANK · SCHOOL · POINTS · RECORD · PREVIOUS`; the CFP variant simply **drops POINTS** because voting points don't exist there. One template, no empty columns.
- **First-place votes rendered inline** in the school cell — "Indiana (66)" — saving a whole column.
- **Recency stated as "Through Games DEC. 6, 2025,"** not "Week 15." Unambiguous in a sport with byes.
- **Bracket year is in the URL** (`/brackets/football/fbs/2025`) — every past bracket is a permanent page, plus a dedicated print view.
- **Bracket cells attach an editorial headline** to each completed game next to the score, so the bracket doubles as a recap index.
- **Bracket-awareness is in the data model**, not the UI: their scoreboard feed carries `seed`, `bracketRound`, `bracketRegion`, `bracketId` on every game, so a postseason game is never a special case.
- **History is top-level nav** (records, winningest programs, stadiums, championships).
- No odds, no picks, no betting — deliberate abstention as the governing body.

---

## 2. CFBD data reality check

This is the part that constrains everything. Verified against CFBD v2 public docs (no live key available, so field lists come from the generated OpenAPI/Python-client docs).

| cfdb Section | CFBD endpoint(s) | Available? | The honest note |
|---|---|---|---|
| Scores | `/games`, `/scoreboard`, `/games/teams` | ✅ Yes | Includes line scores, attendance, excitement index, pre/postgame Elo & win prob |
| Schedule | `/games` (`completed == false`), `/calendar`, `/games/media` | ✅ Yes | No separate schedule endpoint; `/games/media` gives TV/streaming |
| Standings | `/records` | ⚠️ **Partial** | **No `/standings` endpoint exists.** You get W-L splits (total/conference/home/away/neutral/regular/post) but **no ordering, no tiebreakers, no clinch flags** — that's your dbt logic to write |
| Stats (team) | `/stats/season`, `/stats/season/advanced`, `/ppa/teams`, `/teams/ats` | ✅ Yes | Advanced adds success rate, explosiveness, line yards, havoc, standard/passing-down splits, `excludeGarbageTime` toggle |
| Stats (player) | `/stats/player/season`, `/games/players`, `/player/usage` | ✅ Yes | ⚠️ `/stats/player/season` returns **EAV/long shape** with the value as a *string* — budget a pivot + typing layer in dbt |
| Rankings | `/rankings` | ✅ Yes | AP Top 25, Coaches Poll, Playoff Committee Rankings, with `firstPlaceVotes` and `points` |
| SP+ Rankings | `/ratings/sp`, `/ratings/sp/conferences` | ✅ Yes | `rating`, `ranking`, `secondOrderWins`, `sos`, plus offense/defense/specialTeams. Also available: SRS, Elo, **FPI**, and CFBD's own CORE rating |
| **Total QBR** | — | ❌ **No** | **CFBD does not expose Total QBR. It's an ESPN proprietary metric with no CFBD endpoint.** See §2.1 |
| Player Rankings | `/recruiting/players`, `/recruiting/teams`, `/talent`, `/player/portal`, `/draft/picks` | ✅ Yes | Recruiting + transfer portal + 247 composite talent + NFL draft outcomes. No NIL data, no live commit feed |
| Odds / betting | `/lines`, `/teams/ats`, `/metrics/wp/pregame` | ⚠️ **Partial** | Spread, total, moneyline — **open and current only, no timestamped movement history**, no juice on spread/total, no props. *If you want a line-movement chart you must poll `/lines` on a schedule and build your own time series* |
| Play-by-play / drives | `/plays`, `/drives`, `/plays/stats`, `/live/plays` | ✅ Yes | ⚠️ `/plays` requires **both year and week** — a full-season backfill is ~15+ calls per season per filter. Plan quota |
| Win probability | `/metrics/wp/pregame`, `/metrics/wp` | ✅ Yes | Pregame model is spread-anchored. **No playoff-odds / conference-title simulation endpoint** — that's yours to build off SP+/Elo |
| Venues / weather / coaches / rosters | `/venues`, `/games/weather`, `/coaches`, `/roster` | ✅ Yes | Venue has lat/lon, elevation, dome, grass. ⚠️ `/games/weather` has historically been tier-gated — verify against your key |
| Opponent-adjusted metrics | `/wepa/team/season`, `/wepa/players/passing|rushing|kicking` | ✅ Yes | The layer that matters for modeling: `/ppa/*` is raw EPA, `/wepa/*` is opponent-adjusted |

### 2.1 The Total QBR problem — decide this before building

Total QBR is ESPN's proprietary metric. CFBD has no `/qbr` route in the v2 spec, the Python client, or any wrapper. (Confirming evidence: `cfbfastR` sources QBR from `espn_cfb_qbr()`, an ESPN scrape, kept in a separate ESPN namespace from every `cfbd_*` function. Note CFBD *does* republish ESPN's FPI, so ESPN-sourced data isn't categorically absent — QBR specifically is.)

Three options, in the order I'd recommend them:

1. **Build a "QB Rating" page from CFBD substitutes and name it your own thing.** `/wepa/players/passing` (opponent-adjusted passer EPA) + `/ppa/players/season` (EPA per play, pass/rush/down splits) + `/player/usage`. This is arguably a *better* portfolio story than mirroring QBR — you're building a metric, not copying one. Column set could mirror ESPN's shape: `RK · Name · Team · cfdbQB · wEPA · Plays · EPA/play · Pass · Run · Sack · Usage`.
2. **Scrape ESPN's QBR endpoint** the way `cfbfastR` does. Gets you literal parity. Adds a fragile non-CFBD dependency and a second data contract to maintain — and it's the kind of thing a hiring manager may probe on legal/ToS grounds.
3. **Drop the section.** Least interesting.

My recommendation is **(1)**, and I'd label the column honestly on the page ("cfdb QB Score — opponent-adjusted EPA, not ESPN Total QBR") rather than implying parity.

### 2.2 Other honest gaps to design around

- **Standings ordering and tiebreakers are yours to write.** Real dbt work, and a good thing to be able to talk about.
- **No line-movement history.** If you want an opening→current→close chart, you need an Airflow DAG polling `/lines` on a cadence and storing snapshots. *This is actually a strong portfolio artifact — a genuine slowly-changing-dimension problem with a real business reason.*
- **No playoff-odds simulation.** You'd build a Monte Carlo off SP+/Elo. Also a good showcase.
- **No juice/vig on spreads and totals**, which limits true no-vig fair-line computation for spreads. Moneylines are present, so no-vig implied probability *is* computable from the two-way moneyline.
- **Provider list on `/lines`** (documented downstream as consensus, Caesars, numberfire, teamrankings) should be **treated as unverified** and confirmed against a live response with your key.

---

## 3. Proposed cfdb site map

Nav order follows ESPN, with the betting section inserted where CBS puts it (early, not buried).

```
cfdb
├── Home / Today
├── Scores                (week scoreboard, historical)
├── Schedule              (upcoming + full season)
├── Rankings              (AP · Coaches · CFP · SP+ · cfdb Power)
├── Standings             (conference, with tiebreak logic)
├── Stats
│   ├── Team Leaders      (Team ⇄ Opponent toggle)
│   └── Player Leaders    (Offense/Defense/Scoring/Special Teams)
├── Teams
│   └── Team page         (Overview · Schedule · Stats · Roster · Trends)
├── Players
│   ├── Player page       (season, game log, usage, play-level drill-down)
│   └── QB Score          (cfdb metric — the Total QBR substitute)
├── Matchups              (head-to-head, pregame form, model prediction)
├── Recruiting            (team classes · player rankings · transfer portal)
├── ▶ Betting  ◀          [the differentiator — see §5]
│   ├── Odds Board
│   ├── Edge Finder       (model line vs market, ranked by edge)
│   ├── Model Performance (backtest, CLV, ATS record by segment)
│   └── Line Movement     (requires your own snapshot pipeline)
├── CFP Bracket           (year in URL, permanent pages)
└── About / Methodology   [portfolio-critical — see §6]
```

**Deltas vs. your table:**

| Your column | Change | Why |
|---|---|---|
| Total QBR | → **QB Score** | CFBD has no QBR; build your own from wEPA (§2.1) |
| — | + **Matchups** | Already in your project notes; it's the natural home for the model prediction |
| — | + **Betting** (4 sub-pages) | Your "weekly betting opportunities" ask |
| — | + **CFP Bracket** | NCAA has it, CBS has it, it's cheap, and postseason is when traffic peaks |
| — | + **About / Methodology** | Portfolio project — this page is where you win the interview |
| — | + **Recruiting** | Your "Player Rankings" row is really this; CFBD covers it well |

---

## 4. Layout options per section (Streamlit-constrained)

Streamlit primitives assumed available: `st.dataframe` with `column_config` (ImageColumn for logos, ProgressColumn, LinkColumn, NumberColumn formatting, pinned columns) and row-selection via `on_select`; `st.tabs`; `st.columns`; `st.metric` with delta; `st.container(border=True)`; `st.expander`; `st.segmented_control` / `st.pills` / `st.radio(horizontal=True)`; `st.plotly_chart` / `st.altair_chart`; `st.query_params` for deep links; `st.fragment` for partial reruns; `st.dialog` for modals; `st.cache_data`; `st.html` for custom card markup; `st.navigation` / `st.Page` for multipage.

*⚠️ One thing to verify against your installed Streamlit version: top-positioned navigation (`st.navigation(..., position="top")`) is a relatively recent addition. If it isn't in your version, the fallback is sidebar nav — which is fine but reads less like ESPN.*

---

### 4.1 Scores

| Option | Approach | Trade-off |
|---|---|---|
| **A — Card grid (ESPN/CBS style)** | `st.columns(3)` of `st.container(border=True)`, each a game: teams + rank + record, score, spread/total, model pick badge, link to game page | Most familiar, most "real site." Custom HTML via `st.html` needed for tight layout. Slow to render 60 cards unless you paginate/fragment |
| **B — Dense table** | Single `st.dataframe` with logo columns (`ImageColumn`), score, spread, model line, edge; row-select opens detail | Fastest to build, sorts and filters for free, scales to a full Saturday. Least visually distinctive |
| **C — Hybrid with density toggle** | `st.segmented_control("View", ["Cards", "Compact"])` switching between A and B — CBS's Expanded/Compact idea | **Recommended.** Small extra cost, demonstrably thoughtful UX, and the compact mode is what *you'd* actually use on a 60-game slate |

**Controls (shared, see §4.11):** Season · Week · Conference · Division · "Ranked only" toggle.

---

### 4.2 Schedule

| Option | Approach | Trade-off |
|---|---|---|
| **A — Date-grouped rows** | Loop date headers, `st.dataframe` per day. Columns: Away, Home, Kickoff, TV, Venue, Spread, Model Line, Edge | Mirrors CBS closely. Multiple small tables = more reruns |
| **B — One flat sortable table** | Full week/season in one `st.dataframe` with a Date column | Sorts and filters across the whole set; loses the day rhythm |
| **C — Calendar heatmap + drill** | Altair week-by-day grid sized by game count, click a day → table | Visually distinctive but low information density for the effort |

**Recommendation:** B as the default with a "Group by day" toggle producing A.

---

### 4.3 Rankings

ESPN has no SP+ table at all and NCAA's rankings are plain HTML tables. This is a section you can straightforwardly beat.

| Option | Approach | Trade-off |
|---|---|---|
| **A — Poll tabs** | `st.tabs(["AP", "Coaches", "CFP", "SP+", "cfdb Power"])`, each a table. Adopt NCAA's adaptive columns: POINTS and first-place votes only where they exist | Simple, honest, matches how users think |
| **B — Side-by-side comparison** | One table, one column per poll, sorted by a chosen poll; a "Disagreement" column = max spread across polls | **The differentiator.** "Which teams are the polls most wrong about?" is a question no competitor answers |
| **C — Movement chart** | Altair line chart of rank-by-week for selected teams, multiselect-driven | Great in a portfolio demo, thin as a daily-use page |

**Recommendation:** A as the base, plus B as a "Compare Polls" tab and C as a "Movement" tab. Steal NCAA's *"Through games DEC. 6, 2025"* recency label and CBS's *Next Game* column.

---

### 4.4 Standings

| Option | Approach | Trade-off |
|---|---|---|
| **A — Two-band table (ESPN)** | Conference W-L-PF-PA + Overall W-L-PF-PA-HOME-AWAY-STRK-AP. Streamlit has no true column groups — fake it with prefixed headers (`Conf W`, `Ovr W`) | Most information per row. Header naming gets clunky |
| **B — Conference tabs** | `st.tabs` per conference, one clean table each | Cleanest. Loses cross-conference comparison |
| **C — Expected vs. actual** | Add CFBD's `expectedWins` and Elo/SP+ next to actual record, with a "luck" delta column | **Recommended add-on.** Nobody else shows this and it demonstrates the analytics layer |

**Recommendation:** B for structure + A's column set + C's luck column. And be upfront in the UI that **tiebreakers are computed by cfdb** since CFBD supplies none.

---

### 4.5 Stats (Team & Player)

Mirror ESPN's two-level tab structure, add CBS's Team⇄Opponent toggle.

| Option | Approach | Trade-off |
|---|---|---|
| **A — ESPN leaderboard clone** | Primary `st.tabs` (Offense/Defense/Scoring/Special Teams) → `st.segmented_control` sub-category → sortable table, top 50 | Safe, familiar, fast |
| **B — Query-builder table** | One table, multiselect the stat columns you want, sort/filter any of them, min-attempts slider | More powerful, less discoverable. This is what an analyst actually wants |
| **C — Percentile / distribution view** | Each stat shown as a `ProgressColumn` percentile bar plus an Altair distribution with the selected player marked | Best-looking; most work |

**Recommendation:** A as default with a **"Raw ⇄ Adjusted"** toggle (`/stats/season` vs `/wepa/*`) — a one-click demonstration that you understand opponent adjustment. B behind an "Advanced" tab.

---

### 4.6 Teams / Team page

ESPN's CFB team page has exactly four tabs. Proposed: **Overview · Schedule · Stats · Roster · Trends**.

- **Overview:** `st.metric` row (Record, Conf rank, SP+ rank, cfdb Power) → next game card with model line → schedule-with-results list → team stats *with national rank per metric* (ESPN's pattern; `ProgressColumn` percentile reads better than a bare rank) → recruiting class snapshot.
- **Schedule:** game log with result, spread, ATS result, model prediction vs. actual — closes the loop between predictions and outcomes.
- **Stats:** Team⇄Opponent toggle, Raw⇄Adjusted toggle, per-game vs. total toggle.
- **Roster:** CFBD `/roster` gives Name, POS, HT, WT, Class, hometown + lat/lon. Hometown coords make a `st.pydeck_chart` recruiting-footprint map essentially free — a nice, cheap demo moment.
- **Trends** *(cfdb-only)*: EPA/play by week, success rate rolling average, ATS record by situation.

**Teams index:** CBS's pattern — conference-grouped, and every row exposing four destinations — beats a logo grid. In Streamlit: `st.dataframe` grouped by conference with `LinkColumn`s.

---

### 4.7 Players / QB Score

- **Player page:** header metrics → season stat table → game log → usage chart (`/player/usage` down-splits) → **play-level drill-down** (`/plays/stats` attributed plays, filterable by down/distance/result). The play-level drill is what your project notes call for and what nobody in the comp set offers publicly.
- **QB Score page:** ESPN's QBR shape — tabs *Season · Weekly · All-Time* — with your own columns (§2.1). **Label it honestly as not-QBR.**

---

### 4.8 Matchups

Single page, two team selectors, then:

| Option | Approach |
|---|---|
| **A — Stacked comparison table** | Metric rows, two team columns, delta column. Simple, dense |
| **B — Diverging bar chart** | Altair diverging bars per metric, centered on national average. Reads instantly, looks great in a demo |
| **C — Radar/spider** | Familiar to sports fans; honestly a poor encoding — I'd skip it |

**Recommendation:** B for the headline comparison, A below it for detail, plus a model prediction block (projected score, win probability, spread vs. market, key factors) and a history-of-the-series table.

---

### 4.9 CFP Bracket

Steal NCAA wholesale: year in the URL (`?year=2025` via `st.query_params`), permanent per-year pages, editorial-style result line attached to each completed matchup.

**Streamlit caution:** there is **no native bracket component.** Three real options:

1. **Custom HTML/CSS via `st.html`** — a CSS-grid bracket. Full control, moderate effort, no dependencies. *Recommended.*
2. **Graphviz via `st.graphviz_chart`** — nearly free, but it will look like a graph, not a bracket.
3. **Round-by-round tables** — honest, ugly, five minutes.

---

### 4.10 Betting — see §5.

---

### 4.11 Cross-cutting: the shared filter contract

Steal ESPN's and CBS's shared-vocabulary discipline. **One filter component, identical everywhere:**

```
Season ▾   Week ▾   Division ▾   Conference ▾   [Ranked only ☐]
```

Implementation notes:

- Back every filter with `st.query_params` so **every view is a shareable URL** — ESPN's best structural idea, and it costs you almost nothing in Streamlit.
- Persist selections in `st.session_state` so moving Scores → Stats keeps the week and conference.
- Wrap in `st.fragment` so changing a filter reruns the table, not the page.
- One `@st.cache_data` layer over the serving-Postgres queries, keyed on the filter tuple.

---

## 5. Betting section (the differentiator)

This is where cfdb stops being an ESPN clone. CBS's odds page is a bare slate board — no line movement, no consensus, no book comparison. Everything below beats it, and every piece is a genuine data-engineering artifact you can talk about in an interview.

### 5.1 Odds Board
Table per game: Market Spread · Market Total · Market ML · **Model Spread · Model Total · Model Win%** · **Edge** · Recommendation. Sort by edge descending. Color-code edge with a diverging scale. Add CBS's per-row hide/remove.

### 5.2 Edge Finder *(the flagship page)*
The weekly picks screen:

- Filters: minimum edge threshold, conference, kickoff window, market type.
- Each row expands (`st.expander` or row-select → `st.dialog`) into **why**: the model's key drivers, relevant team splits, injury/weather context, historical hit rate for this edge bucket.
- **No-vig fair line** computed from the two-way moneyline, shown alongside the raw line. *Note: CFBD gives no juice on spread/total, so no-vig is computable from moneylines only — say so in the UI rather than implying otherwise.*
- Kelly-fraction sizing column (with a prominent staking disclaimer).

### 5.3 Model Performance *(the credibility page — do not skip this)*
A model with no honest scoreboard is a red flag to anyone technical.

- ATS record and ROI by week / conference / edge bucket / favorite-vs-dog / home-vs-away.
- **Closing Line Value** distribution — the metric that actually indicates skill, and the one that requires your own line-snapshot pipeline to compute at all.
- Calibration plot: predicted win probability vs. realized frequency, decile-binned.
- Backtest over 2024–2025 with the walk-forward methodology stated explicitly.
- Show the losing stretches. Hiding drawdowns is what a portfolio project should not do.

### 5.4 Line Movement
**Requires infrastructure CFBD does not give you.** `/lines` returns open + current only, no timestamps in between. To chart movement you need an Airflow DAG polling `/lines` on a cadence and writing snapshots.

That is a feature *and* an argument: it's a real slowly-changing-dimension problem with an obvious business justification, it shows off the orchestration layer, and it produces data no free competitor has. Worth doing — but it only accrues value going forward, so **start collecting early even if the page ships later.**

### 5.5 Honest constraints to state on the page
- Single-provider lines (CFBD's provider list is unverified — confirm with your key).
- No player props, no alternate lines.
- No juice on spreads/totals.
- Line movement only from the date you started snapshotting.

Stating these plainly is a feature in a portfolio context.

---

## 6. About / Methodology page

Portfolio-critical and easy to under-invest in. Should carry: architecture diagram (CFBD → Airflow → Databricks → dbt → Postgres → Streamlit), data freshness/last-load timestamps, dbt test results and lineage, model methodology and features, known limitations, and CFBD attribution. This is the page a hiring manager will actually read.

---

## 7. Build order (suggested)

| Phase | Ships | Why first |
|---|---|---|
| 1 | Shared filter contract, Scores, Schedule, Standings, Teams index | Proves the pipeline end-to-end on the simplest data |
| 2 | Team page, Rankings (incl. SP+), Stats leaderboards | Highest ESPN-parity value per unit of work |
| 3 | Matchups, Player pages, play-level drill-down | The drill-down your notes call for |
| 4 | **Line snapshot DAG** | ⚠️ **Start this in Phase 1 if possible** — it only accrues data going forward |
| 5 | Odds Board, Edge Finder, Model Performance | The differentiator |
| 6 | CFP Bracket, Recruiting, About/Methodology | Seasonal + portfolio polish |

---

## 8. Open questions for Marc

1. **Total QBR** — build your own QB Score from wEPA (recommended), scrape ESPN, or drop it?
2. **Line-movement snapshots** — start the polling DAG now in Phase 1, or defer and accept a later start date for the history?
3. **FCS coverage** — ESPN and CBS both carry FCS in filters. Include, or FBS-only? (Affects data volume meaningfully.)
4. **Recruiting depth** — team class rankings only, or individual player rankings + transfer portal too?
5. **Nav style** — top nav (needs a recent Streamlit) or sidebar?
6. **Home page** — a "Today" dashboard, or land straight on Scores?

---

## Sources

**ESPN:** [scoreboard](https://www.espn.com/college-football/scoreboard) · [standings](https://www.espn.com/college-football/standings) · [player stats](https://www.espn.com/college-football/stats/player) · [Total QBR](https://www.espn.com/college-football/qbr) · [Alabama team page](https://www.espn.com/college-football/team/_/id/333/alabama-crimson-tide) · [Alabama roster](https://www.espn.com/college-football/team/roster/_/id/333/alabama-crimson-tide) · [2026 SP+ rankings article](https://www.espn.com/college-football/story/_/id/48306284/2026-college-football-sp+-rankings-138-fbs-teams)

**CBS Sports:** [CFB hub](https://www.cbssports.com/college-football/) · [Odds](https://www.cbssports.com/college-football/odds/) · [Scoreboard](https://www.cbssports.com/college-football/scoreboard/) · [Schedule](https://www.cbssports.com/college-football/schedule/) · [Standings](https://www.cbssports.com/college-football/standings/) · [Stats](https://www.cbssports.com/college-football/stats/) · [Rankings](https://www.cbssports.com/college-football/rankings/) · [Teams](https://www.cbssports.com/collegefootball/teams/) · [Expert Picks](https://www.cbssports.com/college-football/picks/experts/)

**NCAA.com:** [FBS hub](https://www.ncaa.com/sports/football/fbs) · [AP Rankings](https://www.ncaa.com/rankings/football/fbs/associated-press) · [CFP Rankings](https://www.ncaa.com/rankings/football/fbs/college-football-playoff) · [CFP Bracket 2025](https://www.ncaa.com/brackets/football/fbs/2025)

**CFBD:** [API v2 GA announcement](https://blog.collegefootballdata.com/api-v2-is-now-in-general-availability/) · [GraphQL API post](https://blog.collegefootballdata.com/building-dynamic-queries-and-data-subscriptions-with-the-new-cfbd-graphql-api/) · [cfbd-python](https://github.com/CFBD/cfbd-python) · [apinext docs](https://apinext.collegefootballdata.com/) · [cfbfastR reference](https://cfbfastr.sportsdataverse.org/reference/index.html) · [cfbfastR espn_cfb_qbr](https://cfbfastr.sportsdataverse.org/reference/espn_cfb_qbr.html)
