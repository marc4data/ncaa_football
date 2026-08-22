# cfdb — site feedback 03

**Third walkthrough · verification pass · passes 01 and 02 archived alongside**

---

## Tags — one correction from pass 02

You added `M` for **Modify** but `M` was already **Missing**, so two of your notes were ambiguous.
Split them:

| Tag | Means |
|---|---|
| `B` | **Broken** — errors, doesn't load, dead link |
| `W` | **Wrong** — works, but the number/label/behaviour is incorrect or misleading |
| `C` | **Confusing** — correct, but a user wouldn't understand it |
| `M` | **Missing** — should be here, isn't |
| `MOD` | **Modify** — exists, change how it works or looks |
| `A` | **Add** — wasn't in requirements, would be good to have |
| `G` | **Good** — keep it, or worth knowing it landed |
| `!` | **Blocker** |

---

# PART A — the 34 items from pass 02

Every item you raised, by the ID Claude Code is reporting against. **Mark each one**: `✓` landed ·
`✗` didn't · `~` partly · `?` couldn't tell.

**A `~` or a `?` is as useful as a `✗`.** Half-landed is the state that gets forgotten.

## Blockers

| ID | What you said | ✓ ✗ ~ ? | Note |
|---|---|---|---|
| F2-01 | Season/week reset going Scores → Rankings | | |
| F2-02 | Stats shows no filter state even when inherited | | |
| F2-03 | Filter bar missing on Today, Rankings, Teams | | |
| F2-04 | Theme reverts to System/Dark after you chose Light | | |
| F2-05 | Data Dictionary links don't land on the table | | |

**Check F2-04 properly — close the browser, come back tomorrow.** A preference that survives a
refresh but not a new session is the failure mode, and it takes a day to see.

## Most-repeated item

| ID | What you said | ✓ ✗ ~ ? | Note |
|---|---|---|---|
| F2-06 | Column widths inconsistent across tables on one page *(you said this 5×)* | | |
| F2-07 | Ohio Dominican / Northwestern (IA) — name twice, hover circle | | |
| F2-08 | Footer: Built by Marc Alexander, website, email, LinkedIn | | |
| F2-09 | Footer: replace the attribution sentence with "Really cool site, check it out!" | | |

For F2-09 — **confirm the CollegeFootballData link itself is still there.** You were replacing the
sentence about attribution, not the attribution.

## Matchup and Odds Board

| ID | What you said | ✓ ✗ ~ ? | Note |
|---|---|---|---|
| F2-10 | Matchup header → Away @ Home, venue centre, weather, rankings | | |
| F2-11 | Matchup out of the nav | | |
| F2-12 | Odds Board: provider radio, one row per game, denser, market filters | | |

## Page-level

| ID | Page | What you said | ✓ ✗ ~ ? | Note |
|---|---|---|---|---|
| F2-13 | Today | filter bar | | |
| F2-14 | Today | column widths | | |
| F2-15 | Today | kickoff = time only | | |
| F2-16 | Today | dataset name once, not per sub-table | | |
| F2-17 | Today | no TV / media data | | |
| F2-18 | Schedule | remove venue column | | |
| F2-19 | Schedule | neutral-site indicator | | |
| F2-20 | Schedule | weather icon + temp | | |
| F2-21 | Rankings | filter bar | | |
| F2-22 | Rankings | Compare tab headers sort | | |
| F2-23 | Scores | winner indicator | | |
| F2-24 | Scores | upset scale documented somewhere | | |
| F2-25 | Stats | column widths | | |
| F2-26 | Teams | filter bar, week disabled not absent | | |
| F2-27 | Teams | column widths | | |
| F2-28 | Team page | bye-week row *(2002+ only)* | | |
| F2-29 | Team page | per-game yards / turnovers / penalties | | |
| F2-30 | Team page | column widths | | |

## Bigger, may not have landed

| ID | What you said | ✓ ✗ ~ ? | Note |
|---|---|---|---|
| F2-31 | Standings by week + bump chart *(model change, not a filter)* | | |
| F2-32 | Data Dictionary → serving only | | |
| F2-33 | Odds Board dataset name not a link | | |
| F2-34 | Pipeline diagram *(mine to draft)* | | |

---

# PART B — the four pages nobody has looked at

Marked "didn't get to it" **both times**. Two of them are the ones you'd show a recruiter.

**Fifteen minutes total. If you do nothing else in this pass, do this.**

### Model Performance ☐ still didn't
*You named this a recruiter page. Does it read as honest measurement, or as an apology? Is it obvious
the numbers are a 2025 backtest? Is the missing 7th model visible as a row?*
```

```

### System Overview ☐ still didn't
*Also a recruiter page. Six signal types now including deploy staleness. Does a green board look like
"everything passed" or like "nothing ran"?*
```

```

### Edge Finder ☐ still didn't
*Dark for real content until Week 5. Does the page explain itself, or look broken?*
```

```

### Line Movement ☐ still didn't
*Needs ≥2 snapshots per game. By now there should be some.*
```

```

---

# PART C — first live weekend

**Games have been played.** Everything below has only ever been tested against 2025.

- [ ] Scores on Thursday night / Saturday — do finals appear, and how long after the whistle?
- [ ] A home win shows a **negative** margin
- [ ] Cover chips: cover / no-cover / push all distinct, push ≠ pending
- [ ] Standings records moved
- [ ] Team page game log filled in for a team that played
- [ ] The "as of" stamp tells you honestly how stale the page is

**The one to watch:** results refresh runs Thursday midday and Sunday. A Thursday-night game may sit
unresolved until Sunday unless the light scores DAG is picking it up. **If Saturday morning still
shows Thursday's games as scheduled, that's the finding of the weekend.**

```




```

---

# PART D — devices

Blank twice. **Five minutes on your phone settles whether sub-768px stays out of scope.**

| | Phone |
|---|---|
| Today | |
| Schedule | |
| Odds Board | |

Page scrolls sideways = bad. Table scrolls in its own box = fine.

**Verdict:** ☐ unusable, keep out of scope · ☐ close, worth fixing · ☐ fine already

```

```

---

# PART E — anything new

Only things **not** already on the list above.

**New defects**
```


```

**New wants**
```


```

---

# The three questions

Unanswered in pass 02 — and the answers are the part I can't get any other way.

**1. Now that games have been played, would you use this on a Saturday instead of ESPN — for anything?**
```

```

**2. What did you try to do and couldn't?** Not what's missing. What you *reached for*.
```

```

**3. Worst thing about it right now?** *01: missing hyperlinks. 02: unanswered.*
```

```
