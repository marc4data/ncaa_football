# Databricks notebook source
# MAGIC %md
# MAGIC # Land CFBD raw JSON in a Unity Catalog Volume — one-shot and weekly
# MAGIC
# MAGIC **What this does.** Calls the CollegeFootballData.com API for one season's completed regular-season
# MAGIC weeks and writes the responses, **untouched**, as JSON files into two Volumes:
# MAGIC
# MAGIC | batch | Volume (default) | files | for practising |
# MAGIC |---|---|---|---|
# MAGIC | **one-shot** | `/Volumes/cfdb/raw/raw_api_json` | one per endpoint, all weeks | a **single bulk load** |
# MAGIC | **weekly** | `/Volumes/cfdb/raw/raw_api_json_weekly` | one per endpoint per week | **incremental** loads |
# MAGIC
# MAGIC **Endpoints:** `/calendar` (to find the completed weeks), then for each completed week `/games`,
# MAGIC `/games/teams` and `/games/players`.
# MAGIC
# MAGIC **One fetch feeds both batches.** Each (endpoint, week) is requested once per run. The weekly file is the
# MAGIC response body byte-for-byte; the one-shot file is the weekly arrays joined in week order, elements unchanged.
# MAGIC So the two batches always hold exactly the same records — only the file layout differs.
# MAGIC
# MAGIC **Ingestion only.** No tables, no flattening. Reading these files is the next exercise.
# MAGIC
# MAGIC ⚠️ CFBD's terms allow storing this data for your own use, not redistributing it raw — keep these files in
# MAGIC your workspace.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Settings that never change
# MAGIC
# MAGIC The API's address, and the three game endpoints with the folder name each one lands in.

# COMMAND ----------

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://api.collegefootballdata.com"
GAME_ENDPOINTS = {               # folder / file name  →  API path
    "games": "/games",
    "games_teams": "/games/teams",
    "games_players": "/games/players",
}
WEEK_END_FIELD = "endDate"       # the calendar field that says when a week is over (read from the live payload)
PACE_SECONDS = 1.0               # pause between calls, to be polite to the API
MAX_RETRIES = 4                  # retries on HTTP 429 (rate limited), waiting longer each time

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · The functions
# MAGIC
# MAGIC Plain Python, no Databricks calls inside them — so the same code can be tested on a laptop with a
# MAGIC stand-in for the API. Each one does one job:
# MAGIC
# MAGIC - `fetch` — one GET; returns the raw bytes and the parsed JSON array; **raises** on anything but a 200
# MAGIC   with a JSON array (and backs off on 429).
# MAGIC - `completed_weeks` — which regular-season weeks have ended, from `/calendar`.
# MAGIC - `write_bytes` — write a file under a root folder, creating folders as needed (overwrites on re-run).
# MAGIC - `land` — the whole run: calendar, every (endpoint, week), then the files for the batches asked for.

# COMMAND ----------


class LandingError(RuntimeError):
    """A response the run must not quietly skip: a non-200, a body that is not a JSON array, or an
    empty array for a week that is supposed to be over."""


def fetch(path, params, api_key, http_get=requests.get, pace=PACE_SECONDS, sleep=time.sleep):
    """GET one endpoint. Returns (raw response bytes, parsed JSON array)."""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    for attempt in range(MAX_RETRIES + 1):
        response = http_get(BASE_URL + path, params=params, headers=headers, timeout=60)
        if response.status_code == 429 and attempt < MAX_RETRIES:
            sleep(pace * 2 ** (attempt + 1))          # back off: 2, 4, 8, 16 × pace
            continue
        break
    if response.status_code != 200:
        raise LandingError(f"{path} {params} returned HTTP {response.status_code}")
    try:
        body = json.loads(response.content)
    except ValueError as exc:
        raise LandingError(f"{path} {params} did not return JSON") from exc
    if not isinstance(body, list):
        raise LandingError(f"{path} {params} returned a {type(body).__name__}, not a JSON array")
    sleep(pace)
    return response.content, body


def completed_weeks(calendar, now=None, field=WEEK_END_FIELD):
    """Regular-season weeks whose end date has passed (UTC), in week order."""
    now = now or datetime.now(timezone.utc)
    done = []
    for entry in calendar:
        if entry.get("seasonType") != "regular":
            continue
        ended = datetime.fromisoformat(str(entry[field]).replace("Z", "+00:00"))
        if ended <= now:
            done.append(int(entry["week"]))
    return sorted(done)


def write_bytes(root, relative, data):
    """Write `data` to root/relative, creating folders. Overwrites, so a re-run is idempotent."""
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def land(season, api_key, one_shot_root=None, weekly_root=None, weeks=None, now=None,
         http_get=requests.get, pace=PACE_SECONDS, sleep=time.sleep):
    """Fetch once, write whichever batches have a root. Returns one summary row per file written.

    `weeks` — an explicit list to re-run (e.g. [5]); None means every completed week.
    """
    if not one_shot_root and not weekly_root:
        raise ValueError("give one_shot_root, weekly_root, or both")
    if weeks and one_shot_root:
        # The one-shot file IS "every completed week". Writing it from a week list would overwrite it with
        # just those weeks and silently drop the rest — so a week list is for the weekly batch only.
        raise ValueError("the one-shot batch always holds every completed week: leave `weeks` blank, "
                         "or use mode=weekly to re-run single weeks")
    summary = []

    # 1. The calendar, written as returned into each Volume.
    raw, calendar = fetch("/calendar", {"year": season}, api_key, http_get, pace, sleep)
    for root, batch in ((one_shot_root, "one_shot"), (weekly_root, "weekly")):
        if root:
            path = write_bytes(root, f"calendar/calendar_{season}.json", raw)
            summary.append({"batch": batch, "endpoint": "calendar", "week": "", "elements": len(calendar),
                            "bytes": len(raw), "path": path})

    # 2. Which weeks.
    finished = completed_weeks(calendar, now)
    if weeks:
        not_done = sorted(set(weeks) - set(finished))
        if not_done:
            raise LandingError(f"week(s) {not_done} are not completed yet; completed: {finished}")
        finished = sorted(weeks)
    if not finished:
        raise LandingError(f"no completed regular-season weeks in {season} yet")

    # 3. Every (endpoint, week) once; the weekly file is the body as returned.
    for name, path in GAME_ENDPOINTS.items():
        combined = []
        for week in finished:
            raw, elements = fetch(path, {"year": season, "seasonType": "regular", "week": week},
                                  api_key, http_get, pace, sleep)
            if not elements:
                raise LandingError(f"{path} week {week} of {season} came back empty, but the week is over")
            combined.extend(elements)
            if weekly_root:
                written = write_bytes(weekly_root, f"{name}/{name}_{season}_wk{week:02d}.json", raw)
                summary.append({"batch": "weekly", "endpoint": name, "week": str(week), "elements": len(elements),
                                "bytes": len(raw), "path": written})
        # 4. The one-shot file: the same elements, in week order, in one array.
        if one_shot_root:
            data = json.dumps(combined).encode("utf-8")
            written = write_bytes(one_shot_root, f"{name}/{name}_{season}.json", data)
            summary.append({"batch": "one_shot", "endpoint": name, "week": "all", "elements": len(combined),
                            "bytes": len(data), "path": written})
    return summary


# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Widgets — the run's settings
# MAGIC
# MAGIC `mode` picks the batches: `one_shot`, `weekly` or `both`. `weeks` is blank for every completed week, or a
# MAGIC comma list (`5` or `5,6`) to re-run just those — **weekly mode only**, because the one-shot file is
# MAGIC always every completed week. The API key is read from a **secret scope** — it is never
# MAGIC typed into the notebook and never printed.
# MAGIC
# MAGIC (`if __name__ == "__main__"` keeps these cells from running when the test suite imports the functions above.)

# COMMAND ----------

if __name__ == "__main__":
    dbutils.widgets.dropdown("mode", "both", ["both", "one_shot", "weekly"])  # noqa: F821 — Databricks global
    dbutils.widgets.text("season", "2026")  # noqa: F821
    dbutils.widgets.text("one_shot_root", "/Volumes/cfdb/raw/raw_api_json")  # noqa: F821
    dbutils.widgets.text("weekly_root", "/Volumes/cfdb/raw/raw_api_json_weekly")  # noqa: F821
    dbutils.widgets.text("secret_scope", "cfbd")  # noqa: F821
    dbutils.widgets.text("secret_key", "api_key")  # noqa: F821
    dbutils.widgets.text("weeks", "")  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Run

# COMMAND ----------

if __name__ == "__main__":
    w = dbutils.widgets.get  # noqa: F821
    mode = w("mode")
    rows = land(
        season=int(w("season")),
        api_key=dbutils.secrets.get(w("secret_scope"), w("secret_key")),  # noqa: F821
        one_shot_root=w("one_shot_root") if mode in ("both", "one_shot") else None,
        weekly_root=w("weekly_root") if mode in ("both", "weekly") else None,
        weeks=[int(x) for x in w("weeks").split(",") if x.strip()] or None,
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · What landed
# MAGIC
# MAGIC One row per file. For each endpoint, the one-shot `elements` equals the sum of its weekly rows.

# COMMAND ----------

if __name__ == "__main__":
    display(spark.createDataFrame(rows))  # noqa: F821 — Databricks globals
