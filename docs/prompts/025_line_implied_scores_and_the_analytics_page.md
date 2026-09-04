# cfdb 025 — line-implied scores, a season-to-date window, and an Analytics page

**From:** Code · **To:** Cowork · **Date:** 2026-09-03
**Status:** findings and a proposal. Nothing here is built. Four register entries requested,
**R-200 to R-203**, numbered to follow R-199.

**Context:** the distribution spec (`cfdb_weekly_distribution_spec.md`) is otherwise current —
§3.8 is settled, the bin work is R-197, the one-renderer decision is R-198. This document adds a
metric pair Marc proposed that is better than the ones the spec currently leads with, answers a
formula concern he raised about it, and proposes a home for the output.

---

## 1. Marc's proposal, and why it belongs at the top of the metric list

> *"Between the Spread and the Over/Under, you can derive what the scores should be for the
> expected winner and loser. Do the distribution on each of those. That will shift drastically
> between weeks 1, 2, 3 and then weeks 5+ when teams shift from loading easy non-conference games
> and get into conference play, which is why I think it's important to calculate it weekly."*

Two derived values per game:

    line-implied favourite score  =  (total + |spread|) / 2
    line-implied underdog score   =  (total − |spread|) / 2

**The claim was tested before it was accepted.** FBS regular-season games, 2024 and 2025,
closing line where held, `n = 1,930`.

### 1.1 The seasonal shift is real and it replicates across seasons

| Phase | 2024 fav / dog | 2025 fav / dog | Gap 2024 | Gap 2025 |
|---|---|---|---|---|
| Weeks 1–3 (non-conference) | 36.8 / 16.6 | 37.3 / 16.0 | 20.3 | 21.3 |
| Week 4 (transition) | 32.7 / 19.2 | 34.0 / 18.7 | 13.5 | 15.3 |
| Weeks 5+ (conference) | 31.3 / 21.2 | 31.2 / 21.1 | **10.1** | **10.1** |

Two independent seasons landing on 10.1 to the tenth of a point in conference play. Week by week
the implied underdog climbs **15.7 → 21.8** and the implied favourite falls **38.2 → 30.7**, both
monotone through week 5, both drifting back as the cupcake games return in weeks 11–13.

This is the strongest argument yet for the weekly grain, and it is Marc's, not ours. It also means
the week-over-week sparkline strip has a reproducible arc to show rather than noise — which the
current metric list does not guarantee.

### 1.2 The finding that reorders the spec's metric list

§3.4 worries that signed `spread` "will barely move week to week" and adds `spread_abs` to fix it.
**It aimed at the wrong column.**

| Metric | Week 1 mean | Week 8 mean | Swing |
|---|---|---|---|
| `total` | 53.9 | 52.5 | **−1.4** |
| `spread_abs` | 22.5 | 8.9 | −13.6 |
| `implied_favourite` | 38.2 | 30.7 | −7.5 |
| `implied_underdog` | 15.7 | 21.8 | +6.1 |

**The over/under is the inert metric.** It is nearly constant all season. Everything that changes
is in how the total gets *split*, and an O/U distribution hides that completely: week 1 and week 8
have near-identical total distributions describing entirely different football.

Recommended reordering of §3.4:

| Rank | Metric | Role |
|---|---|---|
| 1 | `implied_favourite` | headline — the split, in points |
| 2 | `implied_underdog` | headline — the half that moves most |
| 3 | `spread_abs` | the same information compressed to one number |
| 4 | `total` | **the control.** Carry it precisely because it does not move |
| 5 | `spread` (signed) | home-field advantage; keep, but it is not the story |
| 6 | `temperature_f` | unchanged, settled at §3.8 |

`total` earns its place by being flat: a reader who sees three metrics swinging and one holding
still learns something the three alone do not tell them.

### 1.3 These must be model rows, not page arithmetic

Worth stating because it looks like a shortcut. **You cannot derive the distribution of
`(total + |spread|)/2` from the distribution of `total` and the distribution of `spread`.** That
requires the joint distribution — the per-game pairing — which an aggregate has thrown away.

Each derived metric is its own aggregation over game rows. Two more `metric` values on the
existing grain, computed in dbt. Cheap, and non-negotiable as to where.

---

## 2. R-201 — Marc's "trickery" concern, answered: there is none

> *"Have to do a little trickery for Home/Away and to figure out who is favored."*

A reasonable worry, and the answer is that the sign does the work. `srv_game.spread` is
home-perspective, negative favouring home. So:

    implied_home = (total − spread) / 2        -- signed spread. no abs, no CASE.
    implied_away = (total + spread) / 2

No branch, no "who is favoured" lookup. The favourite/underdog pair is then just the larger and
smaller of the two, which is where `abs()` comes from — it is a consequence, not a separate rule.

**Verified against all 1,930 games, zero exceptions:**

| Identity | Result |
|---|---|
| `implied_home + implied_away = total` | 1930 / 1930 |
| `greatest(implied_home, implied_away) = (total + abs(spread))/2` | 1930 / 1930 |
| `least(implied_home, implied_away) = (total − abs(spread))/2` | 1930 / 1930 |
| Pick-ems (`spread = 0`, no favourite) | **0** |

Worked examples, 2025, the three largest spreads on the board:

| Away | Home | Spread | Total | Implied away | Implied home | Actual |
|---|---|---|---|---|---|---|
| Grambling | Ohio State | −55.5 | 62.5 | 3.5 | 59.0 | 0–70 |
| Arkansas-Pine Bluff | Texas Tech | −54.5 | 63.5 | 4.5 | 59.0 | 7–67 |
| Bethune-Cookman | Miami | −54.5 | 64.5 | 5.0 | 59.5 | 3–45 |

(All three are week 1–3 non-conference games. They are the phenomenon Marc described, rendered as
two numbers.)

**Two notes for the build:**

- **Pick-ems.** None exist in FBS 2024+ — the minimum `|spread|` observed is 1.0 — but a
  `spread = 0` game makes favourite and underdog identical and belongs in neither tail. Handle it
  as *both values equal*, not as an error, and do not filter it out.
- **A negative implied underdog score is impossible** and would mean `|spread| > total`. Zero
  occurrences today. Worth a dbt test: its first appearance is bad line data, and it would be
  invisible in the aggregate.

**Home/away versus favourite/underdog.** Both pairs are available from the same two columns. We
recommend shipping **favourite/underdog only**. The home/away cut has the same defect as signed
spread — it mostly measures home-field advantage and will look inert week to week. It costs two
more `metric` rows if Marc wants it later, and nothing in the grain forecloses it.

### 2.1 Naming — a licence point, not a style point

These are derived from **the market**, not from cfdb's model. Labelled "expected" or "projected"
they read as predictions, which is the one framing the training-pack licence cares about.

Use **"Line-implied favourite score"** and **"Line-implied underdog score"** throughout — column
labels, legend, axis titles, Excel headers. Metric keys `implied_favourite` / `implied_underdog`.

### 2.2 Which line, and the lock rule

Measured on `coalesce(spread_at_close, spread_current)` and `coalesce(total_at_close,
total_current)`, matching §3.6 exactly. The derived pair inherits the lock rule unchanged — live
numbers before kickoff, closing numbers after. Nothing extra to specify.

### 2.3 Bin edges — measured, with a result worth having

| Metric | min | p02 | p50 | p98 | max | negatives |
|---|---|---|---|---|---|---|
| `implied_favourite` | 18.5 | 22.4 | 31.5 | 52.0 | 59.5 | 0 |
| `implied_underdog` | 2.5 | 5.5 | 20.3 | 30.0 | 38.8 | 0 |

**A shared axis of 0–60 at increment 4.0 (15 bins) clips exactly zero on both metrics.**

That is better than a compromise. It means the two can be drawn on **one x-scale**, where the
horizontal gap between the two humps *is* the spread, and the pair converging through the season
is precisely the picture Marc is describing. One axis, one bin set, two metrics — and it composes
with R-198's one-renderer rule rather than fighting it.

Fifteen bins also sits inside R-197's revised bin-count guidance for a weekly `n` near 55.

---

## 3. R-202 — season-to-date is one column, not a second model

> *"There's an argument to also calculate a Season-to-Date that can be put at the top of the
> Schedule page for an overall reference."*

Agreed. Model it as a `window` value on the existing grain:

    season × season_type × week × window × metric × as_of_date
                                  ^^^^^^   'week' | 'season_to_date'

`week` stays populated on a season-to-date row as **the week it accumulates through**, so "STD as
of week 7" is an addressable row and the snapshot history keeps working for both windows.

Why one column rather than a second model:

- Same renderer, same bin edges, same `title` tooltip, same Empty state.
- The bin-exhaustiveness test (§6.2, `sum(bins) + below + above = n`) covers both for free.
- A separate model is a second implementation of one picture, which §3.7 already refuses to do for
  bin edges and R-198 refuses to do for the renderer.

**Row cost is modest** — one extra row per metric per week per `as_of_date`, i.e. a doubling of a
small table, not the 3× that the rejected `division` dimension would have cost.

**One semantic decision for Marc.** Season-to-date over *completed* weeks only, or including the
in-flight week? We recommend **completed weeks only**, so the reference line a reader compares
this week against does not already contain this week. `is_final` on the weekly rows makes that a
filter rather than new logic.

Placement composes with the week band rather than competing with it: the season-to-date strip is
the page header, the week band repeats per week when Week is set to All, and read together they
say *here is the season, here is this slate against it*.

---

## 4. R-203 — an Analytics page

> *"All of this is worth spinning up an analytics page that's available in the website, and adding
> a link to it on the schedule page and maybe others. Maybe there will be more interesting
> findings/subject areas, so this would just be 1 tab in that page."*

This is the right call, and it is cheap. The registry is data — `site/lib/registry.py` — so a page
is one `Page(...)` row plus a view module.

### 4.1 Shape

| | |
|---|---|
| Key / title | `analytics` · "Analytics" |
| Group | **a new `ANALYSIS` group.** Not Games, not Betting — the page is *about* the data rather than a view of it, and Marc expects more subject areas |
| Relation | `srv_week_distribution` — one relation, G-2 satisfied |
| Structure | `st.tabs`, tab 1 = **Line-implied scores**. Tabs 2+ are future findings |
| Entry point | A link on Schedule, from the week band and the season-to-date strip, deep-linking to the tab and carrying the current scope the way `GameScope.link()` does |

Tab 1 holds the full `panel()` rendering for each metric, the season-to-date comparison, and the
week-over-week strip that the thumbnails only hint at. It is where the picture gets the room the
Schedule header cannot give it.

### 4.2 Three things to get right

1. **This is page 19, and the nav has a threshold.** R-159 exists because a crowded sidebar made
   Streamlit collapse eight of eighteen pages behind "View 8 more". `st.navigation(nav,
   expanded=True)` is what holds it open. **Adding a nineteenth page must be re-checked against
   that**, measured in the deployed container per R-151, not assumed to be fine because the fix is
   already in.
2. **A tab is not a page, and Streamlit renders every tab eagerly.** Each tab's body executes on
   every rerun whether or not it is visible. This is not hypothetical: `views/performance.py`
   already puts a query inside each of four tabs, so Model performance pays four queries per
   interaction today. With one tab the Analytics page is free — **the caution is to decide the
   pattern before tab 2 lands**, because the cost arrives with the second tab and the existing
   precedent is the expensive shape. `st.tabs` is otherwise well-established here: `rankings.py`,
   `team.py` and `performance.py` all use it.
3. **The link from Schedule must carry scope.** Season, week, division, conference. A link that
   drops the season is the defect §1.4 of the Excel spec already records.

### 4.3 Readiness

The page is `exists / complete / published` **false** until `srv_week_distribution` is built and
published, and it should be registered that way from the start so the nav and the Degraded copy
say the same thing — which is what the registry is for. It becomes buildable when the model does.

---

## 5. Requested register entries

| # | Entry |
|---|---|
| **R-200** | **Line-implied favourite/underdog scores become the headline metric pair.** Marc's proposal, measured and confirmed: the fav/dog gap runs 20.3 → 10.1 across the season and **replicates to 0.1 across 2024 and 2025**. The finding that reorders §3.4 is that **`total` is the inert metric, not `spread`** — it swings −1.4 all season while the split swings 20+. `total` stays as the control. Must be model rows: the distribution of a derived value cannot be recovered from the distributions of its inputs |
| **R-201** | **No home/away branching is needed, and the concern that prompted it was worth raising.** Signed spread gives `implied_home = (total − spread)/2` with no `abs()` and no `CASE`; favourite/underdog is the greater/lesser of the pair. **Verified on 1,930 games, zero exceptions.** Ship favourite/underdog only. Name them "line-implied", never "expected" or "projected" — they are the market's numbers, not cfdb's. **Shared bin axis 0–60 at 4.0 clips zero on both**, so the pair shares one x-scale and the gap between the humps is the spread |
| **R-202** | **Season-to-date is a `window` column on the existing grain**, not a second model. `'week' \| 'season_to_date'`, `week` = the week accumulated through. One renderer, one bin set, existing tests cover both. **Open for Marc:** completed weeks only (recommended) or including the in-flight week |
| **R-203** | **An Analytics page, tabbed, new `ANALYSIS` group**, linked from Schedule with scope carried. One `Page(...)` row plus a view. **Three cautions:** it is page 19 and R-159's nav threshold must be re-measured in the deployed container; Streamlit tabs render eagerly, so guard the query cost before tab 2; the inbound link must carry season/week/division/conference |

---

## 6. Open questions for Marc

1. **Season-to-date over completed weeks only?** (§3). Recommended, so the reference does not
   contain the week being compared to it.
2. **Home/away implied scores as well as favourite/underdog?** (§2). Recommended against for now —
   two more rows whenever he wants them.
3. **Does `total` survive as a shown metric?** It is flat by design and that is the point, but it
   is a thumbnail slot in a band that R-197 already says may only fit two or three.
4. **Tab 1 only, or seed tab 2 with something?** The page is worth building for one tab; Marc
   mentioned more subject areas and it would be useful to know whether any is imminent.

---

## 7. What Code did not do

- **Did not edit either spec, or the register.** Both are Cowork's. Everything above is offered
  for folding in.
- **Did not build anything.** No model, no page, no registry row.
- **Every number here was measured against the DEPLOYED serving database**, not the local
  warehouse. That is R-151, and it is stated explicitly because the temperature error one document
  ago came from measuring the same class of question locally.
