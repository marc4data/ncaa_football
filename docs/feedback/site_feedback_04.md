# cfdb — site feedback 04

**Fourth pass · now checks against `cfdb_request_register.md`**

---

## What changed about how this works

Your requests were being tracked inside numbered prompts. Prompts get superseded, so **nine items
from pass 01 were lost** — including one you marked `M!`. That's the reason things keep not
appearing, and it was a tracking failure, not a build one.

There is now a **register** — `cfdb_request_register.md` — that carries every request with a
permanent `R-` number and a count of how many passes it has survived. Nothing leaves it until you
say so.

**This pass checks that register.** It doesn't restate your requests; it asks whether they happened.

Tags, with the collision from pass 02 fixed:

`B` broken · `W` wrong · `C` confusing · `M` missing · `MOD` modify · `A` add · `G` good · `!` blocker

---

# PART A — the nine that were dropped

**Raised in pass 01, never scheduled.** Prompt 022 doesn't contain them either — I wanted you to see
the list before deciding what happens to them, rather than quietly folding them into the next batch.

**Mark each: `NOW` build it next · `LATER` real but not urgent · `KILL` I don't want it any more.**

| ID | Request | NOW / LATER / KILL |
|---|---|---|
| R-001 | Distribution sparkline beside percentiles — 20 bins, current bin highlighted *(you asked twice)* | |
| R-002 | KPI banner of season totals on Team page Overview *(you marked this `M!`)* | |
| R-003 | Season totals on Teams — yards, rushing, passing, and each allowed | |
| R-004 | Glossary footer under the ratings table | |
| R-005 | Scores: total points | |
| R-006 | Scores: total yards, both teams | |
| R-007 | Scores: last-snapshot spread | |
| R-008 | Scores: did-the-favourite-cover indicator | |
| R-009 | Schedule: header note — negative spread means home is favoured | |

**Anything else from an earlier pass you remember asking for and haven't seen?** That's the real test
of whether the register caught everything.

```


```

---

# PART B — the 26 in prompt 022

`✓` landed · `✗` didn't · `~` partly · `?` couldn't tell. **`~` and `?` matter as much as `✗`.**

## Blockers

| ID | Request | ✓ ✗ ~ ? | Note |
|---|---|---|---|
| R-010 | Filter survives Scores → Rankings | | |
| R-011 | Filter state visible on the page | | |
| R-012 | Filter bar on every page, inapplicable ones disabled | | |
| R-013 | Theme persists — **check tomorrow, not on refresh** | | |
| R-014 | Data Dictionary links land on the table | | |

## Most-repeated

| ID | Request | ✓ ✗ ~ ? | Note |
|---|---|---|---|
| R-015 | Column widths consistent across tables on one page | | |
| R-016 | Ohio Dominican / Northwestern (IA) — name twice | | |
| R-017 | Footer: name, website, email, LinkedIn | | |
| R-018 | Footer: attribution sentence replaced *(CFBD link still present?)* | | |

## Matchup and Odds Board

| ID | Request | ✓ ✗ ~ ? | Note |
|---|---|---|---|
| R-019 | Matchup header: Away @ Home, venue, weather, rankings | | |
| R-020 | Matchup out of nav *(3 passes open)* | | |
| R-021 | Odds Board denser — provider radio, one row per game, filters | | |

## Page-level

| ID | Page | Request | ✓ ✗ ~ ? |
|---|---|---|---|
| R-022 | Today | kickoff = time only | |
| R-023 | Today | dataset name once | |
| R-024 | Today / Schedule | TV / network | |
| R-025 | Schedule | venue column removed | |
| R-026 | Schedule | neutral-site indicator | |
| R-027 | Schedule | weather icon + temp | |
| R-028 | Rankings | Compare headers sort | |
| R-029 | Scores | winner indicator | |
| R-030 | Scores | upset scale documented | |
| R-031 | Team page | bye-week row | |
| R-032 | Team page | per-game yards / turnovers / penalties | |

## Bigger

| ID | Request | ✓ ✗ ~ ? | Note |
|---|---|---|---|
| R-033 | Standings by week + bump chart | | |
| R-034 | Data Dictionary → serving only | | |
| R-035 | Pipeline diagram *(mine)* | | |

---

# PART C — queued but not in 022

Still open. Tick if any landed anyway.

| ID | Request | ✓ ? |
|---|---|---|
| R-036 | Team page out of nav | |
| R-037 | Dark-theme green / Cincinnati on dark | |
| R-038 | The info circle — explained or gone | |
| R-039 | Timezone Pacific, including the as-of stamp | |
| R-040 | Methodology copy *(mine)* | |

---

# PART D — four pages, three passes, never opened

Two of these are the ones you said you'd show a recruiter. **Fifteen minutes.**

### Model Performance ☐ still didn't
```

```
### System Overview ☐ still didn't
```

```
### Edge Finder ☐ still didn't
```

```
### Line Movement ☐ still didn't
```

```

---

# PART E — first live football

Everything here has only ever been tested against 2025.

- [ ] Finals appear after a game ends — **how long after?**
- [ ] A home win shows a **negative** margin
- [ ] Cover / no-cover / push all distinct; push ≠ pending
- [ ] Standings records moved
- [ ] Team page game log filled in
- [ ] The as-of stamp is honest about staleness

**Watch for:** results refresh runs Thursday midday and Sunday. **If Saturday morning still shows
Thursday's games as scheduled, the light scores DAG isn't catching them** — that's the finding of the
weekend.

```


```

---

# PART F — devices

Blank three passes running. **Five minutes on your phone.**

| | Phone |
|---|---|
| Today | |
| Schedule | |
| Odds Board | |

**Verdict:** ☐ unusable, keep out of scope · ☐ close, worth fixing · ☐ fine already

---

# PART G — new

Only what's **not** already an R-number.

**New defects**
```

```
**New wants**
```

```

---

# The three questions

Unanswered twice now, and they're the part I can't get any other way.

**1. Now that games have been played — would you use this on a Saturday instead of ESPN, for anything?**
```

```
**2. What did you try to do and couldn't?**
```

```
**3. Worst thing right now?** *01: missing hyperlinks.*
```

```
