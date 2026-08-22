# cfdb — the paper trail

**cfdb** is a college football analytics platform: CFBD's API → Airflow → dbt → Postgres →
a Streamlit site behind Cloudflare Access. It serves 110,634 games back to 1869, seventeen
pre-joined serving views, and predictions from models trained on a licensed feature store.

This folder is not documentation *of* the code. It is the record of **how the decisions got
made** — including the ones that were wrong, and what changed when they were.

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

`request_register.md` (including nine requests that were dropped, and why) ·
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
