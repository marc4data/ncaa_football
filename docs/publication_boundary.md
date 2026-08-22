# cfdb — Publication boundary

**What may appear on the website, what may not, and why.** Two different licences govern this
project and they have different rules. Getting them confused is the risk this document exists to
remove.

Decided 2026-08-19. Companion to the licence entries in `decision_log.md`.

---

## The two regimes

| | **CFBD API data** | **CFB Model Training Pack** |
|---|---|---|
| Licensor | CollegeFootballData.com | Rad Sports Analytics, LLC |
| Display on a website | **Permitted**, including commercial | n/a — the pack is not display content |
| Redistribution as raw data / mirror API | **Prohibited** | **Prohibited** |
| Derived / generated outputs | Permitted | **Permitted** for personal, academic or private projects |
| Commercial use | **Permitted** | **Prohibited** without written permission |
| Attribution | Optional but suggested | Must **not** present outputs as official CFBD predictions |

**The commercial asymmetry matters for the project's future.** CFBD data can be shown commercially;
Model Pack outputs cannot. If cfdb is ever monetised, the predictions have to come out or be
relicensed — CFBD data alone would be fine. Worth knowing before building a business on it.

---

## The structural rule that does most of the work

**The website reads the `serving` schema and nothing else.** That is already enforced three ways:
the droplet's `search_path`, the locked `cfdb_read` role, and the CI layering guard.

So the publication boundary *is* the contents of `serving`. Anything you do not want published
simply must not have a `srv_` view. Everything below is about what earns one.

---

## HARD EXCLUSIONS — never in `serving`, never on the site

| Object | Count | Why |
|---|---|---|
| `raw.*` — every table | 65 | Raw CFBD payloads. Serving these is functionally a mirror of the API, which both licences prohibit. |
| `raw.raw_manifest`, `stg_raw_manifest` | 2 | Operational metadata, and request URLs may embed the API key. Never leaves the transform tier. |
| Anything sourced from `cfdb_model_pack/training_data.csv` | 0 today | The pack **dataset**. Redistribution and repackaging are prohibited. **Currently nothing loads it. Keep it that way.** |
| Any `cfdb_model_pack/` file | — | Never loaded into any database, never committed, already `.gitignore`d. |
| `model_outputs/*.csv` as downloadable files | 7 | The *contents* may be served as data; the CSVs themselves are not a download. |

`staging.*` and `marts.*` are not on this list because they are excluded structurally — the site
cannot reach them. They are transform-tier objects, not publication decisions.

---

## PERMITTED — may earn a `srv_` view

| Content | Source | Basis |
|---|---|---|
| Scores, schedule, standings | CFBD `/games`, `/records` | CFBD permits displaying portions on a website |
| Rankings and polls | CFBD `/rankings` | same |
| Team & player stats, box scores, drives, plays | CFBD stats endpoints | same |
| Ratings — SP+, Elo, SRS, FPI, CORE, adjusted metrics | CFBD `/ratings/*`, `/wepa/*`, `/ppa/*` | same — **see the provenance rule below** |
| Betting lines and line movement | CFBD `/lines` | same. Displayed as context, not as a betting product |
| Venue, weather, conference, coach, team identity | CFBD reference endpoints | same |
| Predictions, edges, win probabilities | Marc's model output | Pack licence permits generated outputs for private projects. **Attribution required** |
| Model performance, calibration, backtest results | Derived from predictions + public outcomes | same |
| Data dictionary | dbt metadata + CFBD OpenAPI spec | Descriptive metadata about fields, not the data itself |

---

## THE PROVENANCE RULE — the subtle one

**The same number can be publishable or not, depending on where it came from.**

`adjusted_epa` fetched from CFBD's `/wepa/team/season` is API data → displayable.
The identical column read out of the pack's `training_data.csv` is pack data → not distributable.

**Never source a served model from the pack CSV, even when it is more convenient.** The pack ships
5,133 games of pre-assembled features and it is genuinely easier to read than re-deriving from the
API. That convenience is the trap. `fct_team_week_rating` must be built from the CFBD ratings
endpoints already landed in `raw`, not from the pack.

Practical control: no dbt model may declare a source that resolves to pack-derived data. Since the
pack is never loaded, this holds today by construction — the rule exists so nobody "optimises" it
later.

---

## THE FEATURE CLOSEST TO THE LINE: Excel Export

CFBD prohibits *"redistribution as raw data"*. A feature-rich workbook is closer to that than a
rendered page is, and it is the one planned feature where the boundary is a judgement call rather
than a structural fact.

Three things keep it comfortably inside:

1. **Scope exports to what the user can already see.** A week's slate, a team, a matchup, a season
   of results. **No "download all seasons", no full-corpus dump, no raw layer, ever.** The export
   is a convenience view of a page, not an alternate data channel.
2. **The site is behind Cloudflare Access** with an email allowlist. This is not public
   distribution; it is a private tool shared with a named group.
3. **Attribution on every sheet**, plus the model disclaimer on any sheet carrying predictions.

If a future feature request sounds like "let me pull the whole database into Excel", that is the
line, and the answer is no.

---

## ATTRIBUTION — required, and carried as data

- **CFBD:** attribution is optional under their terms. Do it anyway — it costs a line and it is
  the right posture for a portfolio project.
- **Model Pack:** presenting outputs as official CollegeFootballData.com predictions is
  **prohibited**. Edge Finder, Model Performance, Matchup and Methodology must state plainly that
  these are cfdb's own predictions, built on a licensed training pack.

Claude Code carries this as **data** in `dim_model_version` and `srv_model_performance`, so a page
cannot render the numbers without it. That is better than page config and is the adopted pattern —
apply it to any new prediction-bearing view.

---

## THE REPOSITORY IS A PUBLICATION CHANNEL TOO `[A 08-24]`

This document was written about the *website*. **A public GitHub repo is the same question through a
different door**, and the pack licence addresses it in more explicit terms than it addresses the site:

> *"You may not: … Upload the pack files to a **public repository**, shared drive, data marketplace,
> or notebook platform."*

**A public repository is named outright.** No interpretation required.

**As of 24 Aug 2026, 29 MB of pack files sit inside the repo tree** at
`claude_code/cfdb_model_pack/` — `training_data.csv` (7 MB), nine notebooks, `saved_models/` (19 MB),
`model_outputs/`. Gitignored, but a gitignore is a rule that can be broken by accident.

| Rule | |
|---|---|
| **The pack never enters a public repo** | Working tree *or* history. History is the whole repo once it is public. |
| **Move the pack out of the tree entirely** | A file that is not in the directory cannot be committed by any accident. Stronger than an ignore rule, and the licence's explicit naming of public repos earns the stronger control. |
| **`saved_models/` and `model_outputs/` are pack-DERIVED** | Permitted for "personal analysis, academic research, or private projects". **A public repo is not obviously a private project** — same reasoning that keeps prediction pages behind Access. |
| **Rotation is not available for licence breaches** | A leaked key can be rotated. A published licensed file cannot be un-published. |

**What IS explicitly permitted, and it is the part that matters for a portfolio:**

> *"Reference your analysis in public writing or discussion **without publishing the pack files**."*

Marc's own code, the architecture, the results, the write-up — all publishable. Only the pack itself
is not.

---

## Quick test for anything new

1. Is it in `serving`? If not, it cannot reach the site.
2. Where did the number come from — CFBD API, or the pack? Provenance decides.
3. Is it a *view of* the data, or a *copy of* the data? Views are display; copies are distribution.
4. Does it carry predictions? Then it carries attribution.
5. Would it still be fine if the site went public and commercial? If the answer changes, the
   Model Pack is the reason — flag it rather than assuming.
