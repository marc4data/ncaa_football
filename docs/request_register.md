# cfdb — request register

**The durable list. Nothing leaves it until Marc marks it done or kills it.**

Every request Marc has made across every feedback pass, with a permanent ID and a round count.
Feedback passes check *against* this file; they do not replace it.

**Why this exists:** requests were being recorded in the "Backlog" section of a numbered prompt, and
prompts get superseded. Prompt 021 replaced prompt 020, and everything in 020's backlog vanished
without being rejected, deferred or built. **That is a Cowork process failure, not a Claude Code
one.** This file is the fix.

**Rounds open** counts feedback passes an item has survived without landing. **Any item at 3+ is a
process failure by definition** — it means the tracking, not the building, is what's broken.

---

## Status key

| | Meaning |
|---|---|
| ✅ | **Landed** — Marc has seen it working |
| 🔨 | **In flight** — in the prompt Claude Code is executing now |
| 📋 | **Queued** — in a live prompt, not yet built |
| ⚠️ | **DROPPED** — raised, never made it into a prioritised task. Cowork's failure |
| 💭 | **Deferred** — deliberately, with agreement |
| ❓ | **Unverified** — reported built, Marc hasn't confirmed |

---

## ⚠️ DROPPED — raised in pass 01, never reached a task

These are the ones causing the frustration. All were written into prompt 020's backlog and lost when
021 superseded it. **Rounds open: 2.**

| ID | Request | Raised | Note |
|---|---|---|---|
| R-001 | **Distribution sparkline** — inline histogram beside a percentile, 20 bins, current row's bin highlighted, ticks at lower/upper/mid | F1 ×2 | **You asked for this twice in one pass.** Pairs with `rating_population`: the histogram shows shape, the n says how many |
| R-002 | **KPI banner on Team page Overview** — season totals | F1, marked `M!` | **You flagged this a blocker and it was never scheduled** |
| R-003 | **Season totals on Teams** — yards, rushing, passing, and each allowed | F1 | |
| R-004 | **Glossary footer under the ratings table** — what each metric means | F1 | Would also answer "is SP+ good or bad at 17.6?" |
| R-005 | **Scores: total points column** | F1 | |
| R-006 | **Scores: total yards (both teams)** | F1 | |
| R-007 | **Scores: last-snapshot spread** | F1 | |
| R-008 | **Scores: did-the-favourite-cover indicator** | F1 | |
| R-009 | **Schedule: header note that a negative spread means home is favoured** | F1 | One line of copy |

---

## 🔨 IN FLIGHT — prompt 022, Claude Code is executing now

| ID | Request | Raised | Rounds | Was F2 |
|---|---|---|---|---|
| R-010 | Filter persistence — Scores → Rankings resets | F1, F2 | 2 | F2-01 |
| R-011 | Filter state invisible on the page | F1, F2 | 2 | F2-02 |
| R-012 | Filter bar on every data page, inapplicable filters disabled not absent | F2 | 1 | F2-03 |
| R-013 | Theme doesn't persist | F2 | 1 | F2-04 |
| R-014 | Data Dictionary links don't deep-link to the table | F1, F2 | 2 | F2-05 |
| R-015 | **Column widths inconsistent across tables on one page** | F2 ×5 | 1 | F2-06 |
| R-016 | Duplicate team name where no logo — Ohio Dominican, Northwestern (IA) | F1, F2 | 2 | F2-07 |
| R-017 | Footer: Built by Marc Alexander, website, email, LinkedIn | F2 | 1 | F2-08 |
| R-018 | Footer: replace the attribution sentence | F2 | 1 | F2-09 |
| R-019 | Matchup header → Away @ Home, venue centre, weather, rankings | F2 | 1 | F2-10 |
| R-020 | Matchup out of nav | F1, F2, +wireframe v0.2 | **3** | F2-11 |
| R-021 | Odds Board denser — provider radio, one row per game, market filters | F2 | 1 | F2-12 |
| R-022 | Today: kickoff = time only | F1, F2 | 2 | F2-15 |
| R-023 | Today: dataset name once, not per sub-table | F2 | 1 | F2-16 |
| R-024 | Today / Schedule: TV / network data | F1, F2 | 2 | F2-17 |
| R-025 | Schedule: remove venue column | F2 | 1 | F2-18 |
| R-026 | Schedule: neutral-site indicator | F1, F2 | 2 | F2-19 |
| R-027 | Schedule: weather icon + temp | F1, F2 | 2 | F2-20 |
| R-028 | Rankings: Compare tab headers sort | F1, F2 | 2 | F2-22 |
| R-029 | Scores: winner indicator | F1, F2 | 2 | F2-23 |
| R-030 | Scores: upset scale documented | F2 | 1 | F2-24 |
| R-031 | Team page: bye-week row (2002+) | F1, F2 | 2 | F2-28 |
| R-032 | Team page: per-game yards / turnovers / penalties | F1, F2 | 2 | F2-29 |
| R-033 | Standings by week + bump chart — **model change, not a filter** | F2 | 1 | F2-31 |
| R-034 | Data Dictionary → serving only | F2 | 1 | F2-32 |
| R-035 | Pipeline diagram — **Cowork's to draft** | F2 ×2 | 1 | F2-34 |

---

## 📋 QUEUED — in a live prompt, not built

| ID | Request | Raised | Rounds |
|---|---|---|---|
| R-036 | Team page out of nav | F2 | 1 |
| R-037 | Dark-theme green too bright; Cincinnati unreadable on dark | F1 | 2 |
| R-038 | The unexplained info circle — explain or remove | F1 | 2 |
| R-039 | Timezone → Pacific, including the as-of stamp | F2 | 1 |
| R-040 | Methodology copy — model authorship vs licence — **Cowork's to draft** | F1 | 2 |
| R-041 | Skipped-test reporting in the run summary | — | — |
| R-042 | `sync_freshness` signal so parity claims carry a timestamp | — | — |

---

## 💭 DEFERRED — agreed, with a reason

| ID | Request | Why |
|---|---|---|
| R-043 | Compact vs tiled toggle on Schedule / Scores | Real work; agreed post-Week-0 |
| R-044 | Data Dictionary row preview with filter builder | **Serving-tab only** — schema tabs + preview across layers would expose `raw.*`, which the publication boundary prohibits |
| R-045 | Viewer-local timezone | Custom component, new failure mode. Pacific default now; revisit after Week 0 |
| R-046 | Auth: Cloudflare Access temporary auth + purpose justification for non-allowlist visitors | Decided, not built. Post-Week-0 |
| R-047 | Public project page on marc4data.netlify.app | Post-Week-0 |
| R-048 | Static public tier for CFBD-derived pages | Post-Week-0. Licence-bounded: no pack output |
| R-060 | **Move `cfdb_model_pack/` out of the repo tree** — env-var the notebook and loader paths | Deferred until after the model-tuning round; those paths are live. **A pre-commit hook rejecting staged pack paths is the interim control.** Risk is low — the gitignore has held since commit 1 — but a mistaken commit becomes permanent once the repo is public |

---

## ✅ LANDED

| ID | Request | Confirmed |
|---|---|---|
| R-049 | Hyperlinks on rows and team names | Code reported; **F2 didn't contradict it** |
| R-050 | Filters moved to a horizontal bar under the title | Code reported |
| R-051 | FBS spine — either team FBS | Code reported, 888 of 3,745 in 2025 |
| R-052 | Footer attribution rendered as a link | Code reported |
| R-053 | Margin as integers | Code reported |
| R-054 | Mascot column removed | Code reported |
| R-055 | `@ Opponent` instead of an H/A column | Code reported |
| R-056 | Upset indicator `!` / `!!` / `!!!` | Code reported; **scale still undocumented — see R-030** |
| R-057 | Excel column widths | ✅ **Marc confirmed: "The column width changes are good"** |
| R-058 | Cloudflare Access session → one month | ✅ Marc did it |
| R-059 | Site usage stats → Cloudflare Web Analytics, not System Overview | Agreed both sides |

---

## The count

| | |
|---|---|
| ⚠️ Dropped | **9** |
| 🔨 In flight | 26 |
| 📋 Queued | 7 |
| 💭 Deferred | 7 |
| ✅ Landed | 11 |
| **Total tracked** | **60** |

**Items open 2+ rounds: 15. Items open 3 rounds: 1** (R-020, Matchup out of nav — asked at wireframe
v0.2, again in pass 01, again in pass 02, and Cowork argued against it twice).

---

## Rules for this file

1. **An item leaves only when Marc marks it landed, or explicitly kills it.** Not when a prompt is
   superseded, not when it's "in the backlog".
2. **Every prompt to Claude Code cites R-numbers.** A request without an R-number is untracked and
   will be lost — that is the failure this file exists to prevent.
3. **Every feedback pass checks this file**, it does not restate it.
4. **Rounds open is the accountability number.** 3+ means the process failed, not the builder.
5. **Cowork updates this file every round** — before writing the prompt, not after.
