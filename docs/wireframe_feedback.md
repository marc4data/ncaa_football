# cfdb wireframe v0.1 — Feedback

**How to use:** Fill in only what you care about. **Blank = fine as drawn.** Delete nothing; leave empty blocks alone so the structure stays stable across revisions.

- **Keep** — call out specifically what must survive v0.2 (so I don't "improve" it away)
- **Change** — modify what's there
- **Cut** — remove entirely
- **Add** — new element on this screen

**Worth your time:** what's on the page, what's cut, page merges/splits, nav order, column choices, what a page needs before it's useful.
**Not worth your time at this fidelity:** spacing, fonts, exact colors, wording polish. Streamlit overrides most of it.

When done, tell me and I'll ship **v0.2 + a change log**. Anything I disagree with I'll push back on rather than silently implement.

---

# PART 1 — Blocking decisions

These gate real work. Everything else can wait.

### D1. Which two marts are built today?
> *(so the wireframe can mark live vs aspirational instead of guessing)*

**Answer:**
mart_data_freshness
mart_team_schedule
mart_team_season_record
---

### D2. Is `spread` in `training_data_2025_weekNN.csv` the label or a feature?
Context: it carries half-point values (55 of 102 rows), so it's the **market line**, not a game margin. Those files have **no outcome column at all** — no points, no margin, no winner.

- [ ] **Label** — the model is trained to predict the market line
- [ ] **Feature** — the label is joined from `/games` separately
- [X] Not sure — let's dig into it

**Notes:**
I'm not sure what the field means, which is a little peak into another shortcoming of the current state of our project.  This is directly from a paid subscription file provided by CFDB.  There's got to be a data dictionary behind it.  I'm sure that I can track it down, especially when I re-subscribe for the 2026 season.  But we should consider that a requirement.  All fields in our marts (and probably upstream) should have metadata for all tables and fields in the data tier.  That information, a data dictionary, should be easily accessible to end-users using the site, or data scientists looking to use the marts for predicting outcomes.
---

### D3. `Spread` vs `Formatted Spread` disagree on 170/216 rows. Which is authoritative?

- [?] `Spread` is truth
- [?] `Formatted Spread` is truth
- [?] They're different things (opening vs current? different book?) — explain below
- [?] Unknown — needs investigation

**Notes:**
Not sure what file you are talking about.  I need more info to investigate.  
---

### D4. Nav style

- [ ] Top nav (needs a recent Streamlit — verify `st.navigation(position="top")` in your version)
- [ ] Sidebar nav (safe, works everywhere, reads less like ESPN)

Is it possible to do a sidebar Nav as presented in the wireframe, but once in a sidebar page, is it possible to sometimes have a topnav that is context specific to the horizontal tab the user is on?  Seems like it's possible as demonstrated on Teams Page
---

### D5. Who is the site actually for?
This changes several pages materially. Pick the primary.

- [ ] **Hiring managers** — Methodology and Model Performance get the investment; polish over breadth
- [ ] **You + your betting group** — Edge Finder and Excel get the investment; the rest can stay thin
- [X] **Both, equally** — most work; be honest about whether that's realistic

**Notes:**
Nobody is really concerned with anything lower than FBS.  Sometimes FBS opponents will compete against lower-level teams, so it's important to include those matchups, but don't see a lot of value in covering the D2 and D3 landscapes at large.  If there is noteworthy incremental gain by trimming down the underlying mart data model, it's worth considering the pros/cons of reducing the data landscape.  Conversely, if the data product covers all divisions of college football that's more compelling for the portfolio.
---

# PART 2 — Overall / cross-cutting

### Nav order and grouping
Currently: Today · Scores · Schedule · Rankings · Standings · Stats · Teams · Team page · Matchup · [Betting ×4] · Excel · CFP Bracket · Recruiting · Methodology

**Keep:**
**Change:** Matrchup is a drill-thru from Scores and Schedule.  Not sure it needs horizontal nav element...not sure if that's worth changing.  Shift Schedule above Scores.
**Cut:** Recruiting, CFP Bracket
**Add:**

### Shared filter contract
Currently: `Season · Week · Division · Conference · [Ranked only]`, identical on every page, backed by `st.query_params` so every view is a shareable URL, persisted in `st.session_state` across pages.

**Feedback:**
Yes - this is important to keep the drills/filters consistent across the pages.
### Vocabulary
Currently keeping your workbook terms site-wide: **Proj** (Vegas) · **Pred** (model) · **PTL** · **ATL** · **Cover/DNC**, with red = model below line, blue = above.


- [ Keep] Keep as-is
- [ ] Rename some for a public audience (which, and to what?)

**Notes:**
I like the consistent vocabulary, but need to think about using icons that use the same shape and use color to indicate yes/no b/c the longer strings are bigger and seem more important visually, and that's a bad way to present the information.
### Page count
18 screens is a lot for one person. Anything here you'd merge or drop outright?

**Notes:**

---

# PART 3 — Screen by screen

---
## 1. Today `P1`
KPI row (week, games, edges ≥3, season ATS, freshness) · biggest model-vs-market disagreements · pipeline health incl. the failing reconciliation · rankings movers.

**Keep:**
**Change:**
**Cut:**
**Add:**

*Open question: is showing your own failing data-quality check on the home page right, or too raw for a public site?*
Way too raw, this for me not the standard end-user.   it's very interesting but I consider that "back of house" information (restaurant terminology).  People on the site only get "front of house" information, dishes that are fully prepared for them and served up properly. The back of the house stuff is for me to fine tune things.  This is something like System Overview


---
## 2. Scores `P1`
Card grid with Cards ⇄ Compact toggle. Cards carry score, line, O/U, ATL/model badge.

**Keep:**
**Change:**
**Cut:**
**Add:** Use the mascot image where the square placeholder are.  Add some kind of visual indicator to show which team won (shading/background, or a little ◀︎, or similar.   Add what network/media is broadcasting the game.  Include Excitement score.  Should be clickable to see all the details about the matchup.  There should probably be a couple of different looks of the matchup.  Information we know going into the game about all the stats leading into the game.  Then stats for a game that is complete.  

**Notes:**

---
## 3. Schedule `P1`
Flat sortable table (toggle to day-grouped). Columns: Kick, Away, Home, TV, Venue, Spread, O/U, Pred Spr, Edge.

**Keep:**
**Change:**
**Cut:**
**Add:** Use the mascot image where the square placeholder are.  Add some kind of visual indicator to show which team won (shading/background, or a little ◀︎, or similar.  Include Excitement score.  Should be clickable to see all the details about the matchup.  There should probably be a couple of different looks of the matchup.  Information we know going into the game about all the stats leading into the game.  Then stats for a game that is complete.  


*Open question: is TV/venue worth carrying, or is it noise for your use case?*
Venue data is value-add, but can be details available in the matchup.  Really only need to add an indicator if the game is played at neutral site.

---
## 4. Rankings `P2`
Tabs: AP · Coaches · CFP · SP+ · Elo · Compare polls · Movement. Compare-polls table has a Spread (disagreement) column.

**Keep:**
**Change:**. Make the comparable table sortable by clicking the column header.  Adds some more flexibility/functionality to the table.  
**Cut:**
**Add:** For the movement table, I'd like to use Bump chart to see the race week-by-week

---
## 5. Standings `P1`
Conference tabs, ESPN two-band columns, plus xW / Luck / ATS.

**Keep:**
**Change:**
**Cut:**
**Add:**

---
## 6. Stats `P2`
Team/Player/Advanced tabs. Toggles: Team ⇄ Opponent, Raw ⇄ Adjusted, Overall/Rush/Pass, exclude garbage time.

**Keep:**
**Change:**
**Cut:**
**Add:**

---
## 7. Teams `P1`
Conference-grouped index, four destinations per row.

**Keep:**
**Change:**
**Cut:**
**Add:**

---
## 8. Team page `P2`
Tabs: Overview · Schedule · Stats · Roster · Trends. Game log shows prediction vs result. Percentile bars. Roster map.

**Keep:**
**Change:**
**Cut:**
**Add:**

---
## 9. Matchup `P3`
Proj/Pred/PTL table · recommendation block with historical hit rate · efficiency diverging bars · SHAP drivers.

**Keep:**
**Change:**
**Cut:**
**Add:**

---
## 10. Odds Board `P5`
Market vs model columns side by side, sorted by edge, no-vig column, per-row hide.

**Keep:**
**Change:**
**Cut:**
**Add:**

---
## 11. Edge Finder `P5`
Ranked edges with historical hit rate, Kelly sizing, expandable drivers/calibration/context. **Defaults most rows to "no bet."**

**Keep:**
**Change:**
**Cut:**
**Add:**

*Open question: is the conservative "no bet" default right, or do you want to see every edge and judge yourself?*
Can we make it configurable by a slider with a smaller number of steps between the reasonable boundaries. 
---
## 12. Model Performance `P5`
Real numbers from your workbook. ATS/SU/MAE/ROI KPIs · accuracy by week · calibration · CLV · segment breakdown.

**Keep:**
**Change:**
**Cut:**
**Add:**

*Open question: public, or behind the Cloudflare Access allowlist? Showing a 49.4% ATS publicly is defensible but it's your call.*
Everything is behind the Access allowlist.
---
## 13. Line Movement `P4 — DAG starts now`
Step line of market spread over time, model line as reference, steam moves, model-vs-close.

**Keep:**
**Change:**
**Cut:**
**Add:**

*Decision needed: snapshot cadence. Hourly is ~168 calls/week; every 4h is ~42. Against your monthly quota, which?*
Every 4 hours is fine

**Cadence:**

---
## 14. Excel Export `P5`
Sheets: Weekly Slate · Ballot · Model Edges · Team Profiles · Results · Performance · Line History · Field Definitions. Live formulas + assumptions block instead of hard-coded values.

**Keep:**
**Change:**
**Cut:**
**Add:**

*Open questions:*
- *Does the Ballot sheet need to stay byte-identical to what your group already uses, or can it improve?*
- *One workbook with 8 tabs, or separate downloads per context (slate / results / team profiles)?*

---
## 15. CFP Bracket `P6`
CSS-grid bracket, year in URL, model pick vs result per cell.

**Keep:**
**Change:**
**Cut:**
**Add:**

---
## 16. Recruiting `P6`
Team classes · player rankings · transfer portal · talent-vs-results scatter.

**Keep:**
**Change:**
**Cut:**
**Add:**

---
## 17. Methodology `P6`
Architecture diagram · live pipeline health · model description · known limitations · lineage · attribution.

**Keep:**
**Change:**
**Cut:**
**Add:**

---

# PART 4 — Features backlog

Mark each: **V1** (build it) · **L** (later) · **N** (no) · **?** (discuss). Add your own at the bottom — that section matters more than mine.

**Effort** is rough build cost. **Data** is whether CFBD actually supplies it today.

### A. Betting / model

| # | Feature | What it does | Effort | Data | Call |
|---|---|---|---|---|---|
| A1 | **Rest, travel & elevation features** | Days off, miles travelled, elevation change from `/venues` lat/lon + schedule. Classic situational-spot factors the market sometimes misprices | S | ✅ free join | V1 |
| A2 | **Weather-adjusted totals** | `/games/weather` — wind, precip, temp against total edges. Wind is the strongest known total signal | S | ⚠️ verify tier | V1 |
| A3 | **Model vs closing line (CLV)** | Did the market move toward your number? Fastest read on genuine edge | M | ⚠️ needs snapshot DAG | V1 |
| A4 | **Ensemble / model comparison** | Run your model beside SP+, Elo, FPI, CORE as baselines; show where yours adds value and where it doesn't | M | ✅ | V1 |
| A5 | **Bet log & bankroll tracker** | Record actual bets, stake, closing line, P&L. Turns the site from analysis into a system of record | M | ✅ own table | V1 |
| A6 | **Confidence intervals on predictions** | Prediction ± band instead of a false-precision point estimate. Given 14.1 margin MAE, this is arguably a correctness fix, not a feature | S | ✅ | V1 |
| A7 | **Halves / quarters markets** | 1H spreads and totals — thinner markets, softer lines | M | ❌ not in CFBD | N |
| A8 | **Situational splits explorer** | Model accuracy by rest, travel, ranked-vs-unranked, conference, favourite size — find where it actually works | M | ✅ | V1 |

### B. Analytics / stats

| # | Feature | What it does | Effort | Data | Call |
|---|---|---|---|---|---|
| B1 | **Play-level drill-down** | Filter plays by down/distance/result/personnel from `/plays` + `/plays/stats`. Already in your project notes | L | ✅ (week-scoped, quota-heavy) | V2 |
| B2 | **Drive-level efficiency** | Points per drive, scoring-opportunity rate, drive-start effects from `/drives` | M | ✅ | V1 |
| B3 | **Playoff odds Monte Carlo** | Simulate the rest of the season off SP+/Elo → CFP and conference-title odds. No CFBD endpoint; you'd build it | L | ⚠️ build it | V1 |
| B4 | **"Luck" / expected wins** | Actual vs expected record. Already drawn into Standings; could be its own page | S | ✅ | V1 |
| B5 | **Coach performance** | `/coaches` tenure vs SP+ and talent — over/under-performance relative to roster | M | ✅ | V2 |
| B6 | **Historical head-to-head** | Series history on the Matchup page | S | ✅ | V1 |
| B7 | **Game excitement index** | CFBD ships one per game — a "what should I watch" ranking. Fun, cheap, genuinely useful | S | ✅ | V1 | Excitement index comes after the game is played.  It's interesting to review best games of the week and season.
| B8 | **Returning production** | `/player/returning` — preseason signal for team change year over year | S | ✅ | V1 |

### C. Data engineering / portfolio

| # | Feature | What it does | Effort | Data | Call |
|---|---|---|---|---|---|
| C1 | **Public data-quality dashboard** | dbt test results, freshness, reconciliation, row counts — live. Strongest data-engineering signal on the site | M | ✅ | V1 |This is more for me.  Don't lead with it, but it's good to make it available.
| C2 | **Model version registry** | Which model version made which prediction, with performance per version. Makes retraining auditable | M | ✅ own table |V1  |
| C3 | **Backtest replay** | Pick any past week, see exactly what the site would have shown then — point-in-time correctness, demonstrated | L | ✅ (your CSVs are already as-of-week) | V1 |
| C4 | **API quota monitor** | Calls used vs tier limit. Small, and it shows you think about constraints | S | ✅ | V1 |
| C5 | **Lineage viewer** | Embedded dbt docs / DAG | S | ✅ | V1 |

### D. Delivery / UX

| # | Feature | What it does | Effort | Data | Call |
|---|---|---|---|---|---|
| D1 | **Weekly email digest** | Slate + edges + last week's results, auto-sent. Replaces the manual workbook email | M | ✅ | V1 |
| D2 | **Saved filter presets** | "My conferences", "edges only" as one-click views | S | ✅ | V1 |
| D3 | **Deep-link everything** | Every view a shareable URL via `st.query_params`. Already assumed in the design | S | ✅ | V1 |
| D4 | **Mobile-tolerable layout** | Streamlit degrades badly on phones. Worth a pass if you'll check edges from a couch | M | ✅ | N|
| D5 | **ESPN deep links** | CFBD `id` == ESPN gameId, so game links work with zero extra data | XS | ✅ | V1 |

### E. Your additions

| # | Feature | What it does | Notes |
|---|---|---|---|
| E1 | | | |
| E2 | | | |
| E3 | | | |
| E4 | | | |
| E5 | | | |

---

# PART 5 — Anything else

Things that don't fit above — worries, scope concerns, "this whole approach is wrong because…", timeline, whatever.
The Matchup page will be very important.  It's the tool where users will ultimately determine if they want to bet and what they want to bet.  You mentioned some capability to track betting, sounds interesting, but there's no guarantee user will bet using the services we are tracking, nor where we will have visibility to the vig.  So, sounds like a reach, but I'm intrigued.  
>
