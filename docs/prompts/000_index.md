# cfdb — prompt index

Every prompt handed to Claude Code, in order. Replies to Code's reports share the sequence because
they *are* prompts — the numbering follows the conversation, so sorting this folder by name replays
the whole thread.

**Convention:** `cfdb_prompt_###_<short description>.md` · shared sequence · next is **025**.

| # | File | Date | What it asked for | Outcome |
|---|---|---|---|---|
| 001 | `first_code_prompts` | 17 Aug | First set — model reconciliation audit (Prompt A) and follow-ons | Audit came back and corrected the `fct_game` / `fct_game_team` inversion |
| 002 | `revised_cadence_rename_lines` | 17 Aug | B1 lines cadence gate, B2 `fct_`/`dim_` rename, B3 lines modelling | Cadence gate landed; rename decided for before 27 Aug |
| 003 | `phase1_model_spec` | 18 Aug | Phase-1 dimensional model spec | 571-line spec delivered; SCD2 on `dim_team` challenged and dropped |
| 004 | `reply_model_audit` | 18 Aug | Response to the spec — `srv_` as tables not views, BUILD NOW | Settled the tables-vs-views inconsistency |
| 005 | `model_pack_integration` | 19 Aug | Integrate the CFB Model Training Pack; licence assessment | Contract-shaped loader built against a CI fixture |
| 006 | `reply_model_pack` | 19 Aug | Response after the notebooks ran | 3,402 predictions loaded, 6 of 7 models |
| 007 | `build_the_site` | 20 Aug | **The build contract** — hands over requirements v1.0 + wireframe v0.3; Task 1 reconciliation, `srv_sample.xlsx` | Found two absent views and that the app was a 100-line prototype reading `mart_*` |
| 008 | `reply_reconciliation` | 20 Aug | Accepts the reconciliation; decides Edge Finder ships degraded, Stats ships raw-only | Requirements → v1.1 |
| 009 | `reply_column_audit` | 20 Aug | Accepts the column audit — 104 of 135 columns absent | Requirements → v1.2; readiness definition added |
| 010 | `reply_go_narrowed_scope` | 20 Aug | **GO.** Narrowed A1 scope, two-track build order | Requirements → v1.3; A1 started |
| 011 | `reply_a4_progress` | 21 Aug | Excel Export split out as A5; deploy-staleness guard as A6 | Both adopted |
| 012 | `reply_fixes_landed` | 21 Aug | The `->> '0'` silent-null class; two sweeps; alarm-testing generalised | Sweeps taken; A6 alarm caught a 9-commit-stale deploy tree next day |
| 013 | `reply_calibration` | 21 Aug | Calibration compression and its consequence for Edge Finder; `AC-G.32` / `AC-G.33` amended | Superseded by 014 — calibration parked until Week 5 |
| 014 | `week0_readiness` | 21 Aug | Post-game rehearsal against completed 2025; results-refresh cadence; Matchup → Odds Board → Line Movement; B1 | Rehearsal found 2 defects and cleared the sign convention on screen; `+tag:production` found resolving to 6 models, none of them serving views |
| 015 | `deploy_key_and_publish` | 22 Aug | Dedicated restricted deploy key decided; publish as a downstream task of the dbt build with row-count verification; the "green and useless" guard | Premise check paid off — Docker socket was the real root path; Postgres moved to loopback. Cowork's `sql <text>` verb caught as an allowlist bypass |
| 016 | `parity_gate_and_standings` | 22 Aug | Parity-gate rule amended (which side is right, never make them match); the seven Standings columns that ship without B1 | Standings shipped 7 of 9; ATS moved to `fct_team_record`, proved faithful on 22,993 team-seasons first |
| 017 | `self_defeating_guards_and_b1` | 22 Aug | A guard must not be scoped by the mechanism it checks; `sync_freshness` signal; check B1's grain before building it | Grain check paid off — `fct_team_week_rating` unbuildable, shipped as `fct_team_rating` with `rating_scope` |
| 018 | `payload_hygiene_and_week0` | 23 Aug | Two sweeps — aggregate rows in member payloads, and natural-key uniqueness on every fact; `is_projection`'s second job; a user walkthrough for Marc | Sweep 2 found 3 duplicate SRS keys in a model shipped an hour earlier; `rating_population` added |
| 019 | `dedup_precedence_and_noisy_checks` | 23 Aug | Which copy wins in the SRS dedup; AC-16.6's 665 warnings per build fail Code's own false-positive rule | — |
| 020 | `walkthrough_findings` | 23 Aug | Marc's site walkthrough — the deep-link contract was never built; filters don't persist; Matchup-from-nav is broken; FBS-only scope decided | Links WERE built — Streamlit's sanitiser stripped the `onclick`. Real anchors now. Filters carried into hrefs; Matchup got a picker; FBS spine cut 2025 to 888 of 3,745 games |
| 021 | `second_pass` | 24 Aug | Invisible filter state upgraded to `W!`; timezone → configured Pacific; Team page out of nav; Data Dictionary anchors + schema tabs (with the raw-preview boundary) | — |
| 022 | `feedback02` | 24 Aug | Feedback 02 itemised as F2-01…F2-34; theme + timezone unified as one preferences store; Matchup out of nav (Cowork conceded); column-width consistency is the most-repeated item | — |
| 023 | `repo_public_scan` | 24 Aug | Two phases: pre-flight scans before going public, then a curated `docs/` bringing the decision log, requirements, register and all prompts into the repo | **All three scans CLEAN** — no pack content, no secrets, no bulk data has ever been committed; `.gitignore` covered `.env` from commit 1. Found: droplet IP in 3 tracked files, and an `*.xlsx` ignore blocking the `docs/` spreadsheets |
| 024 | `go_public` | 24 Aug | **Current.** Green light. Infra scrub, `!docs/*.xlsx` exception, `api-docs.json` gitignored explicitly — and **a pre-commit hook instead of moving the pack**, since the model paths are live | — |

---

## Not in this sequence

These are **living documents**, revised in place rather than appended to a thread. They carry
versions and amendment logs instead of an index number.

> **`cfdb_request_register.md` is the one to read first.** Every request Marc has made, with a
> permanent `R-` number and a count of passes it has survived. **Prompts cite R-numbers; feedback
> passes check the register.** It exists because requests recorded in a prompt's Backlog section were
> lost when the next prompt superseded it — nine items from pass 01 evaporated that way. Cowork
> updates it **before** writing each prompt, not after.

| File | What it is |
|---|---|
| `cfdb_site_requirements.md` | The build contract. **v1.3**, 213 acceptance criteria, amendment log in Appendix C |
| `cfdb_wireframe_v03.html` | 18 pages, clickable, light/dark |
| `decision_log.md` | Newest-first. **Wins over every other document**, including the requirements |
| `roadmap.md` | Amended in place, `[A 08-19]` markers |
| `cfdb_publication_boundary.md` | What may and may not appear on the site, by schema and table |
| `cfdb_srv_sample_review.md` | Column-by-column review of all 17 serving views |
| `cfdb_data_dictionary.xlsx` | Generated from the CFBD OpenAPI spec; upstream input to `dim_field_metadata` |
| `cfdb_page_to_mart_matrix_v3.xlsx` | Pages × facts/dims, with a "Renders today?" column |
| `cfdb_team_identity_spec.md` | Logos and colours as identity chrome, never data encoding |
| `cfdb_site_ia_and_layouts.md` | The original ESPN / CBS / NCAA competitive review |

---

## Two written but never sent

Both were folded into 007 rather than sent separately, so they hold no index number:
`cfdb_prompt_serving_databricks.md` and `cfdb_prompt_close_the_gap.md`.
