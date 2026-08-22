# cfdb — site feedback

**Walkthrough capture · v1 · 23 Aug 2026 · four days to Week 0**

Type straight into this. Shorthand is fine — I'll turn it into prompts.

---

## How to use

Walk the site the way a member of your group would, not the way a builder would. Land on Today, follow whatever looks interesting, and write down what you notice **as you notice it**. Don't tidy as you go.

**Tag every note** with one letter and, if it matters this week, `!`:

| Tag | Means |
|---|---|
| `B` | **Broken** — errors, doesn't load, dead link |
| `W` | **Wrong** — works, but the number/label/behaviour is incorrect or misleading |
| `C` | **Confusing** — correct, but a user wouldn't understand it |
| `M` | **Missing** — should be here, isn't |
| `A` | **Add** — Wasn't in requirements, but would be good to havel |
| `G` | **Good** — worth keeping, or worth knowing it landed well |
| `!` | **Week-0 blocker** — would embarrass you on Thursday |

Example: `W! spread shows +7 for the home favourite — sign looks flipped on the card`

**`G` matters as much as the rest.** If something reads well I want to know, because the next twenty decisions should copy it.

---

## READ THIS FIRST — expected states, don't log these as defects

Four days out, a lot of the site is *correctly* empty. Logging expected behaviour burns your pass.

| Where | Expected | Why |
|---|---|---|
| Today — prediction strip | Empty, with a Week-5 explanation | CFBD doesn't ship 2026 features until Week 5 |
| Matchup — model block | Same | Same |
| Edge Finder | 2025 backtest rows only, chipped as out-of-sample | Nothing to predict yet |
| Edge Finder — hit-rate slider, `n`, calibration | Degraded, naming `fct_edge_bucket_performance` | Not built; deliberate |
| Model Performance | 2025 held-out split only; a 7th model shown as **not loaded** | `fastai_wp_predictions.csv` never written |
| Stats — team/opponent × raw/adjusted toggle | Degraded | Adjusted metrics are a v1.5 ingestion item |
| Team page — Trends | Degraded, naming a **fetch** change | Ratings are only ever fetched by season, not week |
| Team page — Roster | Degraded | `dim_athlete` not built |
| Players | No body | Deliberately last |
| Line Movement | Thin or empty | Needs ≥2 snapshots per game |
| Standings — division | **Nothing at all** for ~122 of 136 teams | Post-realignment most conferences have none |
| Scores, records, box scores | Empty for 2026 | No games played yet |
| Ratings on Team page | SP+ and FPI only, **labelled as projections** | Elo/SRS/PPA are results-derived; zero rows until games happen |

**If reality differs from this table, that IS worth logging** — tag it `W` and say so. This list is my model of the site, and it being wrong is useful information.

---

## GLOBAL — check once, not per page

Do this pass first. Ten minutes.

**Navigation**
- [y] All 18 pages in the sidebar, in six groups
- [ y] Blocked pages present, not hidden
- [ y Nothing 404s

**Theme**
- [C] Light and dark both legible - green is a little bright/contrasty on the dark mode
- [C] Team colours readable in both — spot-check a near-black (Army, Cincinnati), a near-white, a mid-grey - Cinncinnati doesn't not show well on the dark template

**Filters**
NOTE - Filters should be on the top of the page (above the fold)
- [C] Season/week defaults are current, not hardcoded - These should be more global, not per page.  
- [Y] Changing a filter updates the URL
- [ ] Filters survive navigating away and back
- [Y] Conference filter restricts the team list

**Deep links**
- [Y] Copy a URL, open in a new tab — same view
- [B!] Click a game row → correct Matchup - no hyperlink
- [b!] Click a team name → correct Team page - No hyperlink
- [?] Middle-click a row — does it open a real URL?

**Chrome**
- [Y] Logos load (should be ~96%; monogram for the rest, same size, no broken-image icon)
- [ ] Status chips same width regardless of label
- [Y] Every page has an "as of" timestamp, Yes but can you change the format to Aug 19, 2026 HH:MM AM Timezone (of the end-user)
- [C] Times are US Eastern with the zone shown - should dynamically match end-users timezone
- [Y] Nulls render `—`, never `0` or blank

**Speed**
- [ ] First load, cold: ______ sec. (It's fast)
- [ ] Navigating between pages: instant / laggy / _Instant, it's pretty snappy
**Notes:**

```
U Footer: "Data from [CollegeFootballData.com](https://collegefootballdata.com). Optional under their terms; we do it anyway" Isn't showing as a hyperlink.  Change it to Data Sourced from CollegeFootballData API
A! On each page, where the data model is indicated, it should be a hyperlink to the corresponding table in the Data Dictionary.  Probably change the presentation to be Dataset: Schedule (instead of srv_schedule). 
B! Everytime my session expires, it requires me to do a roundtrip to email and get a pin.  I was thinking once the email was verified, they would login in with a pwd...or some other method that is lighter than back to email on a daily basis.  I know we can change the session length, but are there better authentication options for this use case?
A! - Add LinkedIn icon that hyperlinks to https://www.linkedin.com/in/marc4data/. Also include a link to my website: https://marc4data.netlify.app/#

Change the default from Eastern timezone to Pacific.
As of Timestamp should be Pacific, not UTC
The hyperlink to Data Dictionary should take the end-user to the exact table (dataset) they clicked on, not just to the top of the Data Dictionary page.
Also think we should make tabs across the to indicate which schema.  Order them left to right for where they are in the pipeline.
Include a bunk row for bye week.  Maybe query something that builds out the structure of the season (season, week) and then left joins from that to build out the srv_team_overview so that it shows the bye week.
Team/Schedule add Total Years, Run Yards, Pass Yards, and Defense Yards, Net Turnovers
Clicking on a team in Schedule/Scores should take me to Matchup.  In Matchup, clicking on a team should take me to the Teams page.  Or add a little icon (Details, or something else) on Scores/Schedule that will hyperlink to the matchup and then clicking on the Team can go directly to the team.
Schedule/Score - compact vs tiled option (like CBS)
Rankings/Compare - column header should sort the table, add tabs for the week it's showing (so can easily get back to a previous week to see what the state was then).
I filtered Standings on Season - 2025 then navigated to Stats and it's still filtered to 2025, which I think is correct, but there's nothing on the page indicating the filter or the year.  URL shows it, but we can do better than that.
Teams: Oklahoma Panhandle doesn't have an icon and is showing the team name twice.  Think the icon might be causing the name showing twice.  Not having icon is a data issue from source, I'm assuming.  That's fine, but the double name presents bad.  There's a little circle that turns to a "?" on hover, and hyperlinks to team on a click.  Just make the team name the hyperlink.  Be consistent across the site.  Can we standardize the column split to be consistent across conferences?  
Team Page should not be in Nav Pane.  Only
Scores: Header for the Upset column should be Upset instead of "!"
```

---

# Per page

One line each on whether it did its job, then anything specific.

---

## 1 · Today
*Landing page. 211 games in week 1.*

Did it do its job? ______

Worth checking: market data was only ~24% populated at last look — do most games show no line, and does that read as "no line yet" or as broken? · Does the Week-5 message make sense to someone who doesn't know the pipeline?

```
C getting word wrap on the date time.  Each date is a seperate table, so know need to have the long form date time in the kickoff field, reduce to H:MM AM/PM.  Can we adjust for timezone the computer is running and show "All times are <enter timezone here>?  
C Timezone comment should apply to the Current As of Date in the header.
C 

```

## 2 · Schedule

Did it do its job? ______

Worth checking: **one row per game, not two** · day grouping and kickoff order · neutral-site games framed as neutral, not home/away · non-FBS opponents render with a name

```
M No games have TV field populated
M Clicking on a game should take you to Matchup page.  
A Add something in the header to help user understand that a negative spread means home team is favored, and + means Away is favored.
B! When I chose Season = 2025 to see some results so that I can see how it populated, then I naturally want to navigate to the other pages and see what they look like to, the Season filter reverts back the 2026 default. Season should be a global filter.   
A small indicator for Weather and show  temp
```

## 3 · Scores
*Post-game path was rehearsed against 2025 this week — first live run is Thursday.*

Did it do its job? ______

Worth checking: switch to a **completed 2025 week** and check winner shading, cover chips, push vs pending as distinct · opponent names on games against Division II teams (12,168 rows were null until two days ago) · a home win should show a **negative** margin

```
G I like the Upset column! but the indicator is taking up way more real estate than it needs to.  Maybe make it an "!", "!!", or "!!!" indicating to what degree.
A! There should be a global filter that defaults to FBS and includes games where either team is FBS. 
A! Add a small indicator nex to the score to indicate which team won 
C Margin - remove the decimal point
A Add Total Points
A last snapshot spread
A indicator if the favored team covered against the spread
A Add a column for Total Yards (value to include sum of both teams)
```

## 4 · Rankings

Did it do its job? ______

Worth checking: are 2026 preseason polls in yet, or is this empty · "receiving votes" distinct from unranked · Compare tab and the disagreement column · bump chart labelling

```


```

## 5 · Standings
*Seven new columns shipped yesterday.*

Did it do its job? ______

Worth checking: streak, last-5, home/away splits, ATS record · ATS should be **blank** for 2026, never `0-0-0` · division absent entirely for most conferences — does that look deliberate or broken? · sorting

```


```

## 6 · Stats

Did it do its job? ______

Worth checking: every rank shows its `n` · the degraded toggle — is it obvious *why* it's off, or does it look broken? · through-week selector

```


```

## 7 · Teams
*681 cards.*

Did it do its job? ______

Worth checking: logos ~96% — how visible are the ~4% monograms? · `color_source` reachable · search-as-you-type · does it feel long?

```
A! Conference Filter
C Filters should be across the top in the page, instead of on the bottom of the nav pane (apply to any page that has filters)
C what function is the little "info" button at the Team name supposed to provide?
B Remove the Mascot column, not a value add
A Add season totals for Yards, Running Yards, Passing Yards, and Yards Allowed, Running Yards Allowed, Passing Yards Allowed
M Clicking a Team should take user to the Team Page
```

## 8 · Team page
*Pick a team you know well. Ratings block is new.*

Did it do its job? ______

Worth checking: SP+ and FPI showing as **projections** — is that label clear? · two degraded tabs alongside working ones — confusing or fine? · percentile bars carry their `n` · header colour band legible in both themes

```
M! Overview Should have BAN/KPI banner for season total stats
A Schedule tab, include a row for the bye week.  
C! instead of H/A, if it's Away add an "@ " before the Opponent name
A Under the srv_team_rating table, there should be a footer with Glossary for the different metrics
A In addition to percentile, can you add column with an inline  histogram that demonstrates the distribution.  Break into 20 bins, include labeled tick marks at lower/upper boundaries and the mid point between 10 and 11 bin.
M Why don't we have the Athlete dimension?
```

## 9 · Players

Expected: no body. Anything else? ______

```


```

## 10 · Matchup
*Widest page. Reached by clicking a game.*

Did it do its job? ______

Worth checking: **arrive without a game_id** — picker, or something ugly? · both teams symmetrical · does the model block's absence read as "not yet" or "broken"? · venue/weather/travel present or absent

```
B If I navigate to this page directly, it has the top X games showing looks like it's sorted by date desc.  Totally not functional.
M Filter for Week/Conference
B Can navigate within the shown dataset functionally....might be the argument for not having it show in the Nav pane.  This is a drill-thru page that's only accessed when the gameid context is provided.

```

## 11 · Odds Board

Did it do its job? ______

Worth checking: capture time on every row · best line per game highlighted · a game with one provider — does it look wrong? · **wide table — how does it behave narrow?**

```


```

## 12 · Edge Finder
*2025 backtest only. Dark for real content until Week 5.*

Did it do its job? ______

Worth checking: is it obvious these are **backtest** rows, not live? · does the page explain itself, or look broken? · the magnitude slider with the hit-rate slider degraded beside it

```


```

## 13 · Model Performance
*The page that most carries the project's credibility.*

Did it do its job? ______

Worth checking: does it read as **honest measurement** or as an apology? · ATS below breakeven in the negative treatment · the missing 7th model as a visible row · em-dash, never `0.0%`, where a model can't be ATS-scored · calibration chart

```


```

## 14 · Line Movement

Did it do its job? ______

Worth checking: a game with <2 snapshots — does it say why? · is the 4-hourly cadence stated, so a flat line reads as "no capture" not "no movement"?

```


```

## 15 · Excel Export
*May not be built yet — it was split into its own task.*

Built? ______  If yes: does the workbook open clean, are numbers typed as numbers, is attribution on every sheet?

```
G - by large, this is pretty awesome!
B - need to add a feature that will automatically adjust the width of the columns b/c some of the fields are showing as ####### b/c they don't have enough space.  Others are too wide.  Might run into a problem b/c the first 2 rows have some header information that will make the first column WAY too wide if you use the autofit features.  Might have to auto fit, then INSERT 3 rows before freezing the panes.  See what you can do.  

```

## 16 · Data Dictionary

Did it do its job? ______

Worth checking: coverage is ~30% and **falling** — is that rendered honestly? · `UNDOCUMENTED` as a real value, not a blank · search

```
A Can we add a feature where they can press a button that will show top X rows of the table, with some basic query filtering functionality to adjust the recordset (drop-down for field, drop down for <,>,=, !=, then drop-down (for text fields) or freeform for number values?

```

## 17 · Methodology

Did it do its job? ______

Worth checking: **read it end to end as a stranger would** — this is the page that turns a dashboard into a portfolio piece · de-vig assumption stated plainly · sign conventions · the limitations section on the same page as the claims · "not official CollegeFootballData.com predictions"

```
G - in principle, this is a really good page.
W - https://<site-host>/methodology#what-the-model-is-and-what-it-is-not - this is not accurate.  We are using a starter pack as our starting point, but we are going to tune the model, which makes it our predictions.  We are using their feature store that has all of the adjusted data points, but the model will be ours once we start tweaking.

```

## 18 · System Overview

Did it do its job? ______

Worth checking: five or six signal types · deploy-staleness signal · a green board should say "every check passed", never look like "no checks ran"

```
G - this is really good!
A Some stats for website usage, or should I be using cloudflare for that?
```

---

# Responsive / device matrix

Requirements currently scope **below 768px as out for v1**. This pass tells you whether that's still right.

Walk the same five pages on each. Mark ✓ / ✗ / note.

| Page | Desktop | Laptop ~1280 | Tablet | Phone |
|---|---|---|---|---|
| Today | | | | |
| Schedule | | | | |
| **Odds Board** *(wide)* | | | | |
| **Matchup** *(widest)* | | | | |
| Standings | | | | |

Also spot-check: **Stats**, **Edge Finder**, **Data Dictionary** — all wide tables.

**What to watch for:** does the page body scroll sideways (bad), or does the table scroll inside its own container (fine)? Is the sidebar collapsed and reachable? Are chips and numbers still readable?

**Verdict on sub-768px:**  ☐ genuinely unusable, keep it out of scope   ☐ close enough to be worth fixing   ☐ fine already

```




```

---

# Cross-cutting notes

Things that turned up on more than one page.

```
Filters need to be more global
Should be a FBS website.  We don't need any of the other levels.  If a game includes and FBS and non-FBS, it should be included
Dynamically picking end-users timezone would be nice.  Date format should be Aug 20, 2026.  Time format H:MM AM/PM PDT


```

# Copy and wording

Anything that reads wrong, sounds robotic, over-explains, or under-explains.

```




```

# Ideas and backlog

Not defects — things you want that don't exist. No filter, write them all down.

```
Missing some hyperlinking to click on teams and get to details
What are the possibilities for adding infomative tootlips
There are some places where i'd like to add small graphic to indicate the distribution for the metric and where that particular record falls (histogram with 20 bins covering full range, highlight bin for current row (or team).  Label upper/lower tick marks and the middle tickmark too.



```

---

# The three questions worth answering last

**1. Would you use this on a Saturday instead of ESPN, for anything?** If yes, what. If no, what's missing.

```
That's the goal.  We aren't quite there yet, but there's potential
```

**2. If you showed this to someone hiring, which page would you open first — and which would you avoid?**

```
Not sure yet, but having the Data Dictionary, Methodology, and System Overview are good for the recruiters.
```

**3. What's the single worst thing about it right now?**

```
Missing hyperlinks, 
```
