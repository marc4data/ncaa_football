# cfdb — College Football Data Platform

## What this project is

A portfolio-grade college football analytics platform built on the CollegeFootballData.com (CFBD) API. It powers a private website (friends and family only) showing model predictions and rich team/matchup dashboards, with drill-down to the drive and play level. The primary audience beyond friends and family is **potential employers**: every architectural decision should be one Marc can demo and defend in an interview.

## Marc's showcase scope

Marc is presenting himself as an expert in **Data Engineering, Analytics/BI, and Data Science/ML** — not full-stack web development. Therefore:

- Complexity budget goes into the pipeline, data modeling, testing, and analytics — not the frontend.
- The frontend stays thin and data-native (Python/SQL only). No custom React/JS app.
- Prefer tools and patterns Marc can discuss credibly over clever one-offs.

## Division of labor: church vs. state

Two Claude surfaces work on this project, with a hard boundary between them:

| Surface | Owns | Lives in |
|---|---|---|
| **Cowork (this folder)** | Strategy and governance: architecture decisions, research, vendor/cost evaluation, this CLAUDE.md, decision log, planning docs, reviewing results | `ncaa_football/claude_work` — **no production code in this folder** |
| **Claude Code (VS Code)** | All code: ingestion scripts, Airflow DAGs, the dbt project, ML scripts, Streamlit app, Docker Compose, tests, CI, code-level docs/READMEs | `ncaa_football/claude_code` (scaffolded, with its own CLAUDE.md) |

Rules for the boundary:

- Decisions are **made in Cowork and recorded here first**; Claude Code implements within them. If implementation reveals a decision needs to change, it comes back here before the code diverges.
- The code repo gets its **own CLAUDE.md** (engineering conventions, commands, repo layout), seeded from this document and kept consistent with it. This file remains the source of truth for *what and why*; the code repo's file covers *how*.
- Gray-area assignments: debugging and running pipelines → Claude Code. Exploratory data analysis → notebooks in the code repo (Claude Code), but conclusions that change direction get written up here. Cost tracking and platform/tier research → Cowork.

## Architecture (settled decisions — change only after discussion with Marc)

| Layer | Choice | Why |
|---|---|---|
| Source | CFBD REST API v2 (+ GraphQL, Tier 3+); Model Starter Package models | Marc has elevated-tier access |
| Ingestion | Python, landing raw API responses immutably | Replayable without re-pulling |
| Warehouse | **Databricks Free Edition** (Delta Lake, serverless) | $0, strong resume value (Spark/Delta/Unity Catalog) |
| Transforms | **dbt** (staging → marts), with tests and docs/lineage | Quality rigor + lineage demo |
| Orchestration | **Apache Airflow** in Docker | Fills a resume gap; adequate for weekly batch |
| ML | Model Starter Package **plain Python** (scikit-learn/XGBoost/fastai) run as pipeline tasks | Start with what's built; extend later |
| Serving DB | Small always-on **Postgres**; final marts published there | Website never wakes warehouse compute |
| Frontend | **Streamlit** reading serving Postgres | Interactive drill-down in pure Python |
| Access control | **Cloudflare Access** email allowlist in front of the site | Free ≤50 users; blocks strangers/bots at the edge |
| Phase 1 environment | Everything local via Docker Compose (Postgres + Airflow + dbt) | Validate rigor before spending on hosting |

The one-line story: **warehouse for analytics, Postgres for serving** — the site is isolated from warehouse compute and cost.

## Tool responsibilities (who owns what — resolves the gray areas)

| Responsibility | Owner | Explicitly NOT |
|---|---|---|
| Scheduling, dependencies, retries, run alerting | **Airflow** | No business logic or data transforms in DAGs |
| API pulls → immutable raw layer | **Python ingestion tasks** (called by Airflow) | No cleaning/reshaping at this stage |
| ALL raw → staging → marts transforms; metric definitions; schema/data tests; reconciliation checks; lineage | **dbt** (project lives in the code repo, edited in VS Code, runs against Databricks) | Databricks notebooks never do production transforms — exploration/prototyping only |
| Storage + SQL compute for analytics | **Databricks Free Edition** (Delta tables) | Not the website's query engine |
| Operational health: "did the job run, on time, without errors" | **Airflow** (alerting) | Data *correctness* belongs to dbt tests, not Airflow |
| Model training/scoring | **Model Starter Package Python scripts**, run as pipeline tasks; features come from tested dbt marts | No ad-hoc feature math inside model scripts; MLflow/Databricks ML is a possible later phase, not now |
| Publishing final marts + predictions to serving | **Airflow task** (warehouse → Postgres) | Postgres is read-only serving; no transforms there |
| Display: pages, filters, charts | **Streamlit** | No metric calculations — if Streamlit needs a computation, it belongs upstream in dbt |
| Keeping strangers out | **Cloudflare Access** | No auth code in the app |

Litmus test for new work: *data correctness lives in dbt, process reliability lives in Airflow, presentation lives in Streamlit.* If a piece of logic doesn't clearly fit its layer, stop and discuss before writing it.

## Data scope

- **Play-by-play and drives: 2024, 2025, and 2026 seasons only** (previous two + current).
- **Current-season framework lands as soon as the season exists** (decided 2026-08-15): schedule, rosters, coaches, rankings, and season-scoped teams for 2026 are pulled at season open, not deferred to in-season cadence. Any team's 2026 schedule must be answerable before Week 1.
- **Season-level history: full API depth for a curated set** (decided 2026-08-15; resolves the former "depth TBD per feature"): games, records, rankings, teams, coaches, stats/season, stats/season/advanced, stats/player/season, wepa/team/season, ppa/players/season, and draft/*. Each endpoint's own availability bounds its depth. Everything else stays at 2024+. The list lives in the endpoint registry (`history` attribute); amending it takes one registry line + one decision-log line.
- Weekly batch cadence during the season (results refresh + pre-game refresh + daily in-week lines snapshots); no live in-game data for now.

## Data quality rules (non-negotiable)

1. Raw layer is immutable — land API responses as-is; rebuild downstream from raw, never mutate it.
2. All loads are idempotent — upserts keyed on CFBD's own IDs; re-running a job must never create duplicates.
3. dbt tests on every mart: uniqueness, not-null, referential integrity on IDs.
4. Reconciliation checks: e.g., play/drive aggregates vs. reported team totals; game counts vs. the schedule endpoint. Discrepancies fail loudly, not silently.
5. Every dashboard shows data freshness ("data as of X"); pipeline failures must be visible, never swallowed.

## CFBD terms compliance (hard constraints)

- API key lives **server-side only** (env vars / secrets). Never in client code, notebooks committed to git, or logs.
- We may cache/store data and display it on the site, but must never redistribute raw data or act as a mirror/substitute API.
- Credit "CollegeFootballData.com" on the site (optional per terms, but we do it).

## Working agreements

- **Discuss before executing.** Ask Marc before going down a new execution path or changing a settled decision. Present options with honest trade-offs and costs.
- **Answer honestly; never state facts you're not certain about.** Verify current prices/limits rather than assuming.
- **Cost guardrails:** warehouse stays on the free tier; total recurring infra target is roughly $0–15/month. Flag anything that could exceed it before incurring it.
- **Document the why.** Decisions get recorded (here or in a decision log) so Marc can narrate them to employers.
- **Build in phases**; keep phase 1 local and free. Working software with rigor beats breadth.
- Marc's public portfolio site (marc4data.netlify.app) stays separate; it will link to this project.

## Current status

- Architecture, data scope, and division of labor settled (Aug 2026). Code repo scaffolded at `ncaa_football/claude_code` (own CLAUDE.md, Docker Compose files, src/dbt/dags skeletons); GitHub repo to be created as `ncaa_football` (private).
- Setup provisioning in progress — see `setup_checklist.md` (owner-split checklist) and `decision_log.md` (2026-08-14 decisions: repo name, Databricks now, tracking approach, sign-offs).
- Next up (in Claude Code, per the boundary above): CFBD ingestion spike with a small slice of data to validate the raw → staging → marts flow, once Marc completes the checklist's manual items.
