# cfdb — site feedback 02

**Second walkthrough · Week 0 week · pass 01 is archived as `cfdb_site_feedback_01.md`**

Same tags. Shorthand is fine.

| Tag | Means |
|---|---|
| `B` | **Broken** — errors, doesn't load, dead link |
| `W` | **Wrong** — works, but the number/label/behaviour is incorrect or misleading |
| `C` | **Confusing** — correct, but a user wouldn't understand it |
| `M` | **Missing** — should be here, isn't |
| `A` | **Add** — wasn't in requirements, would be good to have |
| `G` | **Good** — worth keeping, or worth knowing it landed well |
| `M` | **MOdify** — Modify to improve site functionality |
| `!` | **Week-0 blocker** |

**New this time: every page has a `☐ didn't get to it` box.** Pass 01 had eight blank sections and I
couldn't tell "nothing to say" from "never opened it". Tick the box and blank means something.

---

# PART A — did pass 01's fixes actually land?

Do this first. Ten minutes, and it's the highest-value part of the pass — **a fix that reverted is
worse than one never made**, because everyone's stopped looking at it.

| # | What was reported | What should now be true | ✓ / note |
|---|---|---|---|
| 1 | No hyperlinks anywhere | Every game row → Matchup. Every team name → Team page. **Middle-click a row — does it open a real URL in a new tab?** | |
| 2 | Season filter reverted on navigation | Set 2025 on Standings, walk to Stats, Schedule, Teams — it holds | |
| 3 | Filters buried in the sidebar | Horizontal bar under the page title, above the fold | |
| 4 | Matchup from nav showed an arbitrary list | A real picker — filter bar, grouped by day, searchable by team | |
| 5 | Non-FBS noise | Schedule and Scores only show games where **either** team is FBS. "All divisions" still widens it | |
| 6 | Footer attribution not a link | "Data sourced from the CollegeFootballData API", clickable. LinkedIn and marc4data.netlify.app present | |
| 7 | `srv_schedule` shown as a raw table name | "Dataset: Schedule", linked to its Data Dictionary entry | |
| 8 | Kickoff cell word-wrapped | Time only in the cell, day carried by the group header | |
| 9 | Margin had decimals | Integers | |
| 10 | Upset indicator too wide | `!` / `!!` / `!!!` by degree | |
| 11 | Mascot column | Gone | |
| 12 | H/A column | `@ Opponent` instead | |
| 13 | Excel columns showing `#######` | Widths sized from the data, header rows excluded | |

**Anything above that didn't land, or landed and broke something else:**

```


```

---

# PART B — expected states, don't log these

Still correctly empty or degraded:

| Where | Expected |
|---|---|
| Today, Matchup — prediction blocks | Empty with a Week-5 explanation. CFBD doesn't ship 2026 features until Week 5 |
| Edge Finder | 2025 backtest only, chipped out-of-sample. Hit-rate slider and calibration Degraded |
| Model Performance | 2025 held-out split. A 7th model shown as **not loaded** |
| Stats — scope/basis toggle | Degraded. Adjusted metrics are v1.5 |
| Team page — Trends | Degraded, naming a **fetch** change, not a model |
| Team page — Roster · Players page | Degraded / no body. `dim_athlete` not built |
| Line Movement | Thin. Needs ≥2 snapshots per game |
| Standings — division | Nothing at all for ~122 of 136 teams. Post-realignment most conferences have none |
| Ratings on Team page | SP+ and FPI only, **labelled projections**. Elo/SRS/PPA are results-derived — zero rows until games happen |
| Scores, records, box scores | Empty until Thursday |

**Known outstanding, already on the list — no need to re-report:** dark-theme green · the
unexplained info circle · viewer-local timezone (deferred past Week 0) · Methodology copy · Rankings
sortable headers · bye-week rows · Team page out of nav.

---

# PART C — global

**Time and dates** *(should now be Pacific, including the "as of" stamp)*
- [ ] Kickoff times in Pacific with the zone shown — "7:30 PM PDT"
- [ ] "As of" stamp in Pacific, not UTC
- [ ] Dates read "Aug 20, 2026"
- [ ] Worth a sanity check against ESPN for one game — **they publish Eastern, so a 3-hour difference is correct, not a bug**

**Filter visibility** *(the thing I flagged hardest)*
- [ ] When a filter is inherited from another page, **can you tell from looking at the page?**
- [ ] Is a non-default value marked so it stands out?
- [ ] Is there a way back to "current season" without editing the URL?

**Navigation**
- [ ] Two destinations per row — can you tell which is which **before** clicking?
- [ ] Back button behaves
- [ ] Any dead end — a page you land on with no way onward?

**Chrome**
- [ ] Theme toggle, both directions, on a data-heavy page
- [ ] Logos and monograms consistent
- [ ] Anything still showing a raw `srv_` / `fct_` name front of house

```




```

---

# PART D — per page

Tick the box if you didn't open it.

### 1 · Today ☐ didn't get to it
*Opening slate is Sep 5. Market data was ~24% populated.*
```
M Remove the date portion in the Kickoff field.  Only use the Time element (PDT)
M Don't need the srv_ called out on every table within the page (sub-grouped by date).  The one at the very top covers it.
B No TV or media data
A Needs standard filters
A Can we standardize the column size or split Pct so that each table is consistent and the column breaks are consistent?  It's a much cleaner look for the end-user and easier to read the full page
```

### 2 · Schedule ☐ didn't get to it
*FBS filter is new. Links are new.*
```
M Remove Venue information from the table.  We will get venue details from Matchup
A a column with an indicator to flag games played at a neutral site.  
A Weather icon (sun, wind, cloud, snow, fold in wind if appropriate, plus expected temp
Links to the Data Dictionary aren't taking directly to the table referenced
```

### 3 · Scores ☐ didn't get to it
**This is the one that matters most this week — first real games Thursday.** Switch to a completed
2025 week and check the post-game render before Thursday proves it live.
Links to the Data Dictionary aren't taking directly to the table referenced
```
C Add an indicator to show who won. (e.g. ▶︎)
M I like the new Upset column, What's the split between !, !!, and !!!.  Where does the end-user see that?

```

### 4 · Rankings ☐ didn't get to it
*2026 preseason polls. Sortable headers and week tabs are known-outstanding.*
```
A Needs filters
A Compare tab should have table headers that sort the table when clicked on
A Links to the Data Dictionary aren't taking directly to the table referenced
```

### 5 · Standings ☐ didn't get to it
*Seven columns landed: streak, last-5, home/away splits, ATS.*
```
? No Week filter in Standings.  It is possible to include that?  If so, then we should be able add a bump chart to show how the season unfolds.
```

### 6 · Stats ☐ didn't get to it
```
B No Filters shown or declared, even if it's filtered from the previous page I navigated from
If there are multiple tables on the same page and they have the same field layout, keep the column widths consistent for all the tables 
```

### 7 · Teams ☐ didn't get to it
*Conference filter, the double-name bug, the info circle. Oklahoma Panhandle is Division II — check
whether the FBS filter removed it before reporting the bug again.*
```
If there are multiple tables on the same page and they have the same field layout, keep the column widths consistent for all the tables 
B No Weeks filter
```

### 8 · Team page ☐ didn't get to it
*Reached from Teams or any team link. Ratings block shows SP+/FPI as projections.*
If there are multiple tables on the same page and they have the same field layout, keep the column widths consistent for all the tables 
```
A Include a row for bye week.  
A /Schedule/ High-level statistics for each game (yards earned (total, run, pass), yards giving (total, run, pass), net turnovers, penalty yards
```

### 9 · Matchup ☐ didn't get to it
*Try both routes: from a game row, and cold from nav into the picker.*
```
C The layout for the top section with the teams is bad.  Have a team on the left, then venue information in the middle, then name of the home team on the right.  Not natural.  Use standard Away @ Home layout.  Keep the venue information.  Add Weather.  Include ranking, if a team is ranked.
C Take it out of the Nav pane.  It doesn't need to be searchable, it's a click-through asset.  
```

### 10 · Odds Board ☐ didn't get to it
*Wide table. Not opened in pass 01.*
```
A name of the srv_ table does not link to the Data Dictionary at all, much less to the specific table (srv_odds_board)
M this table should have a radio button to choose which Provider is used.  Then remove the subgrouping by game, so it's a much more concise listing of the games and the odds.  Matchup detail, should just be an inline hyperlink to the Matchup page.  Add an icon or make all the elements the hyperlink.  Needs to be much more dense. No need to subgroup tables and include the start/end time.  This page will be accessed in the days leading into the kickoff.  It would be good to add some filters or sorting capabilities to look at sections of games (spread, total, etc)
```

### 11 · Edge Finder X didn't get to it
*Not opened in pass 01. Does it explain itself, or look broken?*
```

```

### 12 · Model Performance X didn't get to it
*Not opened in pass 01, and it's one of the three you named for recruiters. Does it read as honest
measurement or as an apology?*
```

```

### 13 · Line Movement X didn't get to it
```

```

### 14 · Excel Export X didn't get to it
*Column widths fixed. Anything else?*
```
The column width changes are good.  
Don't think we've mastered this.  There will probably be more datasets included, but this is a great start and proves what's possilble.  
```

### 15 · Data Dictionary ☐ didn't get to it
*Anchors and schema tabs may not have landed yet.*
```
Don't see the tabls for the different levels of the data pipeline.  Don't understand why anything below src_ is included.  A look into the dbt data lineage would be helpful, or a diagram of the movement would also be good, but can't vlioate the concept that only fully processed and curated data is available on this site.  And that's what needs to be documented well.
```

### 16 · Methodology ☐ didn't get to it
*Copy rewrite is mine and pending — flag anything else.*
```
Can we draft a more visual diagram of data flowing through the pipelines, DQ checks, transformations, API calls vs Droplet, security on the site, all the different things that factored into the Change Log document?
```

### 17 · System Overview X didn't get to it
```

```

### 18 · Players X didn't get to it
*Expected: no body.*
```

```

---

# PART E — devices

Blank in pass 01. **Five minutes on your phone is enough** — and it settles whether sub-768px stays
out of scope for v1.

| | Phone | Tablet |
|---|---|---|
| Today | | |
| Schedule | | |
| Odds Board *(wide)* | | |

Does the **page** scroll sideways (bad), or does the **table** scroll inside its own box (fine)?

**Verdict:** ☐ unusable, keep out of scope · ☐ close, worth fixing · ☐ fine already

```

```

---

# PART F

**Cross-cutting** — turned up on more than one page
```
Ohio Dominican, Northwestern (IA) don't have a icon and are repeating the team. name twice.
If there are multiple tables on the same page and they have the same field layout, keep the column widths consistent for all the tables (Schedule, Scores, Standings, Teams, Team Page, matchup)
A Links to the Data Dictionary aren't taking directly to the table referenced (Teams)
C! Footer, Change the Built by Marc Alexander, [Website]<link>, [Email icon]<marc4data@gmail.com>, [LinkedIn Icon]<link to Marc's linkedin page>
C! Footer, Replace this section of the footer "Attribution is optional under their terms; cfdb provides it anyway." with "Really cool site, check it out!"
B I chose 2025 and Week 12 on Scores and then navigate to Rankings and it resets to current week (2026 W1).  
It's night and the sight reverts back to System/Dark even though I explicitly chose Light Theme.  ONce I choose it, it should stick...not randomly default back to a different setting.  
Is there a config/user situation where once somebody logs in and chooses MDT, future visits and sessions go for MDT, and them choosing MDT doesn't impact other users that might want PDT or EDT? 
```f

**Copy and wording** — reads wrong, robotic, over- or under-explains
```


```

**Backlog** — wants, not defects
```


```

---

# The three questions

**1. Would you use this on a Saturday instead of ESPN, for anything?** Last time: *"That's the goal.
We aren't quite there yet, but there's potential."* What's changed?
```

```

**2. What did you try to do and couldn't?** Not what's missing — what you *reached for*.
```

```

**3. What's the single worst thing about it right now?** Last time: missing hyperlinks.
```

```
