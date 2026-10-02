# Databricks: land CFBD raw JSON (cfdb-wtc-R-2570)

`cfbd_landing_ingest.py` is a Databricks **source-format** notebook. It calls the CollegeFootballData.com API for one
season's completed regular-season weeks and writes the responses, untouched, into two Unity Catalog Volumes:

| batch | default Volume | layout |
|---|---|---|
| one-shot | `/Volumes/cfdb/raw/raw_api_json` | `<endpoint>/<endpoint>_<season>.json`: every completed week in one file |
| weekly | `/Volumes/cfdb/raw/raw_api_json_weekly` | `<endpoint>/<endpoint>_<season>_wk<NN>.json`: one file per week |

- **Endpoints:** `calendar` (in both Volumes), `games`, `games_teams` and `games_players`.
- **The two batches always hold exactly the same records.** Each response is fetched once and written both ways.

⚠️ **Keep the files in your workspace.** CFBD's terms allow storing the data for your own use, not redistributing it
raw.

## Steps

Each step says whether it was **verified** (run by session `wtc` on its own machine) or **not verified** (it depends
on your workspace, which no session can see).

| # | step | status |
|---|---|---|
| 1 | **The Volumes exist:** `cfdb.raw.raw_api_json` and `cfdb.raw.raw_api_json_weekly`. You created them, per your word on 2026-10-02 | not verified |
| 2 | **Store the API key as a secret.** Use the Databricks CLI on your laptop: `databricks secrets create-scope cfbd`, then `databricks secrets put-secret cfbd api_key`, and paste the key when prompted. A different scope or key name is fine; set the widgets to match | not verified |
| 3 | **Check that the cluster or serverless compute can reach `https://api.collegefootballdata.com`.** Outbound internet is a workspace setting | not verified |
| 4 | **Import the notebook:** Workspace → Import → File → `notebooks/databricks/cfbd_landing_ingest.py`. Databricks reads the `# Databricks notebook source` header and splits it into cells | not verified |
| 5 | **Run all.** The widgets appear on the first run, with these defaults: `mode = both`, `season = 2026`, the two Volume paths, `secret_scope = cfbd`, `secret_key = api_key`, `weeks` blank (= every completed week) | not verified |
| 6 | **What a good run prints:** a table with one row per file. Each `weekly` row has a week number and a non-zero `elements`. Each endpoint has one `one_shot` row whose `elements` equals the sum of its weekly rows | **verified locally**: see below |

**Re-running is safe.** Every file is overwritten.
- **To add a week later,** run again with `weeks` blank. Every completed week is rewritten, so the one-shot files stay
  complete.
- **To re-run single weeks,** use `mode = weekly` with `weeks = 6`, which rewrites only Week 6's weekly files. A week
  list with the one-shot batch is refused, because it would overwrite the season file with one week.

**What it refuses, rather than half-finishing:**
- an HTTP error;
- a response that isn't a JSON array;
- an empty week that should be over;
- a requested week that hasn't finished.

## The local proof (session `wtc`, 2026-10-02)

The same functions were run on a laptop with a scratch folder standing in for the Volumes.
- **Weeks:** 13 API calls. Weeks 1–4 were complete by the calendar's `endDate`; Week 5 ends 2026-10-05.

| endpoint | one-shot elements | weekly elements (wk 1 + 2 + 3 + 4) |
|---|---|---|
| games | 1,352 | 455 + 303 + 311 + 283 |
| games_teams | 586 | 204 + 131 + 128 + 123 |
| games_players | 586 | 204 + 131 + 128 + 123 |

- **Identical:** in every case the one-shot array equals the weekly arrays joined in week order, element for element.
- **Why `games` has more elements:** `games` lists every game CFBD has, including lower divisions. `games_teams` and
  `games_players` list only games with box scores.

The tests are in `tests/test_databricks_landing.py`, with the API stubbed.
