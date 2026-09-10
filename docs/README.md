# cfdb — the paper trail

**cfdb** is a college football analytics platform: CFBD's API → Airflow → dbt → Postgres →
a Streamlit site behind Cloudflare Access. It serves 110,634 games back to 1869, seventeen
pre-joined serving views, and predictions from models trained on a licensed feature store.

This folder is not documentation *of* the code. It is the record of **how the decisions got
made** — including the ones that were wrong, and what changed when they were.

> ## ⚠️ THIS FOLDER IS A DATED SNAPSHOT, NOT THE LIVE RECORD
>
> **Snapshot date: 2026-08-21. Stamped 2026-09-09 (A081/R-254).**
>
> Everything here is a copy of a document that lives and keeps changing elsewhere. The copies
> were taken on **21 August 2026** and have not been refreshed since. `decision_log.md` below
> is **134 KB against a live 403 KB**; `prompts/` stops at round 025 while the project is past
> round 080.
>
> **That is deliberate.** The ruling is *stamp rather than refresh* — a paper trail's value is
> that it shows what was known **at the time**, and continuously rewriting it to match the
> present destroys exactly the thing it is for. A reversal is only legible if the original
> claim is still readable.
>
> **What this means for you:** read it as a record of the build's first month, not as a
> description of the system today. Where a document here contradicts the code, **the code is
> right and this is history.**
>
> ⚠️ **One file was RETIRED rather than stamped, on 2026-09-09**: `page_to_mart_matrix_v3.xlsx`
> was wrong about statuses, grains and Phase 1 scope, and **a stamped wrong file is still
> wrong**. A date makes a stale document honest; it cannot make an incorrect one honest.
>
> ⚠️ **`working_agreement.md` still says the pipeline runs "everything local via Docker
> Compose".** It has not been true since the droplet migration of 27–30 August, and believing
> it cost one build round outright. It is kept, stamped, because that mistake is part of the
> record — see the note at the top of that file.

## The five worth reading, in order

| | | |
|---|---|---|
| 1 | [decision_log.md](decision_log.md) | Every architectural decision, newest last, with the reasoning at the time. Several are reversals. |
| 2 | [requirements.md](requirements.md) | 215 numbered acceptance criteria. Testable, and most of them are tested. |
| 3 | [publication_boundary.md](publication_boundary.md) | Two licences — CFBD's and a commercial modelling pack's — and exactly what may be published under each. Written before anything was built. |
| 4 | [srv_sample_review.md](srv_sample_review.md) | A column-by-column audit of all seventeen serving views. What auditing your own data actually looks like. |
| 5 | [prompts/](prompts/) | Twenty-four rounds of instruction and reply, unedited. The whole build, as it was driven. |

## What went wrong, and what we changed

Three defects shared one shape, and finding the shape mattered more than fixing any of
them. A JSON accessor returned `null` on a type mismatch and every team logo silently
vanished — masked by a fallback that was doing 100% of the work. A dbt selector resolved to
six models, so a nightly refresh rebuilt nothing the site reads and reported success. A
sanitiser stripped an `onclick`, so every table row rendered a pointer cursor attached to
nothing. **All three were green and useless: something upstream removed a thing that still
looked present, and every check confirmed it had *run* rather than that it had *produced*
anything.**

The fix that generalised was a rule about controls: **a guard must not be scoped by the
mechanism it checks.** The parity test that would have caught the selector bug was itself a
dbt test, so narrowing the selector narrowed the guard in the same motion — it did not fail,
it was never asked. Guards now run outside the thing they guard, and each one is proved by
deliberately breaking it before it is trusted.

The habit underneath both: **ask the data rather than encoding the rule.** When predictions
begin, which teams played, whether a rating is a forecast — all read from the warehouse, not
from a constant somebody has to remember to change.

## Also here

`roadmap.md` · `model_reconciliation.md` · `phase1_model_spec.md` ·
`site_ia_and_layouts.md` (a competitive review of ESPN, CBS and NCAA.com) ·
`team_identity_spec.md` · `wireframe_v03.html` (clickable, eighteen pages) ·
`working_agreement.md` (how two AI agents divided strategy from implementation) ·
`feedback/` (four rounds of walking the live site) · two spreadsheets.

## The site

Live at a private hostname behind Cloudflare Access, with an email allowlist — the
publication boundary depends on it not being open, so access is by request rather than by
link. The code that builds it is this repository; the data it serves belongs to
[CollegeFootballData.com](https://collegefootballdata.com) and is not redistributed here.

The modelling pack that trained the predictions is licensed, personal-use, and is **not** in
this repository — see `publication_boundary.md`. Its licence permits describing the work and
discussing the results, which is what these documents do.
