"""The four staging frames `own_features` reads, rebuilt from raw JSON on disk (cfdb-wtc-R-2482).

History before 2024 lives only in this checkout's `data/raw/` (fetched by `modeling.fetch_history`),
never in the warehouse — landing it there would reach the site through `srv_drive` within two hours.
So the model reads it here, and `tests/test_disk_source.py` plus the round's live parity check hold
this reader to the warehouse's own staging on the seasons both have (2024–2025).

EACH TRANSFORM MIRRORS A STAGING MODEL, read at `origin/main` (session A's files; not edited):

    successful fetches only          `where status_code = 200` — every staging model, `successful_fetches`
    explode `content.data`           `json_array_elements('payload')` — every model, `exploded`
    latest file wins per key         `row_number() over (partition by <key> order by filename desc)`
                                     keys: advanced/havoc (gameId, team) · drives (id) · talent (year, team)
    numbers                          `safe_numeric` = `case when text ~ '^-?[0-9]+(\\.[0-9]+)?$' then numeric`
                                     (`dbt/macros/portability.sql:150–151`) — booleans, blanks, words → NULL
    integers                         `cast(... as int)` / `as bigint` for ids, weeks, yard lines, scores
    names                            `snake_case` = camelCase → camel_case (`dbt/macros/naming.sql:19–21`)
    advanced                         `dbt/models/staging/stg_game_team_advanced.sql` — offense/defense ×
                                     flat metrics and standardDowns/passingDowns/rushingPlays/passingPlays
    havoc                            `dbt/models/staging/stg_game_team_havoc.sql`
    drives                           `dbt/models/staging/stg_drive.sql`
    talent                           `dbt/models/staging/stg_team_talent.sql`

`games` is NOT rebuilt here: `staging.stg_games` already holds full history (R-2412), and every
consumer passes it in, read from the warehouse.
"""
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from modeling.own_features import ADJUSTED, coerce

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
_NUMERIC = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")


def _text(value: Any) -> Optional[str]:
    """What Postgres `->>` renders for a JSON value: numbers as plain decimals, booleans as words."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(Decimal(repr(value)), "f")          # full precision, never exponent notation
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def safe_numeric(value: Any) -> Optional[float]:
    """A JSON number is a number (Postgres renders it as a plain decimal, which always passes the
    regex); a string passes only if it looks like one; booleans, blanks and words are NULL."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    t = _text(value)
    return float(t) if _NUMERIC.match(t) else None


def as_int(value: Any) -> Optional[int]:
    t = _text(value)
    return None if t is None else int(t)


def _snake(name: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def _nested(row: dict, *path: str) -> Any:
    for key in path:
        if not isinstance(row, dict):
            return None
        row = row.get(key)
    return row


def rows(endpoint_key: str, key: Iterable[str], raw: Path = RAW) -> List[dict]:
    """Successful fetches, exploded, latest file first-wins per key — the staging `deduped` CTE."""
    seen, out = set(), []
    folder = raw / endpoint_key
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.json"), reverse=True):          # filename desc
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(content, dict) or content.get("status_code") != 200:
            continue
        for row in content.get("data") or []:
            k = tuple(_text(row.get(part)) for part in key)
            if k not in seen:
                seen.add(k)
                out.append(row)
    return out


FLAT = ["plays", "drives", "ppa", "totalPPA", "successRate", "explosiveness", "powerSuccess", "stuffRate",
        "lineYards", "lineYardsTotal", "secondLevelYards", "secondLevelYardsTotal",
        "openFieldYards", "openFieldYardsTotal"]
GROUPED = {"standardDowns": ["ppa", "successRate", "explosiveness"],
           "passingDowns": ["ppa", "successRate", "explosiveness"],
           "rushingPlays": ["ppa", "totalPPA", "successRate", "explosiveness"],
           "passingPlays": ["ppa", "totalPPA", "successRate", "explosiveness"]}
HAVOC = ["totalPlays", "totalHavocEvents", "frontSevenHavocEvents", "dbHavocEvents",
         "havocRate", "frontSevenHavocRate", "dbHavocRate"]


def advanced(raw: Path = RAW) -> pd.DataFrame:
    out = []
    for r in rows("stats_game_advanced", ("gameId", "team"), raw):
        rec = {"game_id": as_int(r.get("gameId")), "season": as_int(r.get("season")),
               "week": as_int(r.get("week")), "season_type": _text(r.get("seasonType")),
               "team": _text(r.get("team")), "opponent": _text(r.get("opponent"))}
        for side in ("offense", "defense"):
            for m in FLAT:
                rec[f"{side}_{_snake(m)}"] = safe_numeric(_nested(r, side, m))
            for group, metrics in GROUPED.items():
                for m in metrics:
                    rec[f"{side}_{_snake(group)}_{_snake(m)}"] = safe_numeric(_nested(r, side, group, m))
        out.append(rec)
    return pd.DataFrame(out)


def havoc(raw: Path = RAW) -> pd.DataFrame:
    out = []
    for r in rows("stats_game_havoc", ("gameId", "team"), raw):
        rec = {"game_id": as_int(r.get("gameId")), "season": as_int(r.get("season")),
               "week": as_int(r.get("week")), "season_type": _text(r.get("seasonType")),
               "team": _text(r.get("team")), "opponent": _text(r.get("opponent"))}
        for side in ("offense", "defense"):
            for m in HAVOC:
                rec[f"{side}_{_snake(m)}"] = safe_numeric(_nested(r, side, m))
        out.append(rec)
    return pd.DataFrame(out)


def drives(raw: Path = RAW) -> pd.DataFrame:
    out = []
    for r in rows("drives", ("id",), raw):
        out.append({"drive_id": _text(r.get("id")), "game_id": as_int(r.get("gameId")),
                    "offense": _text(r.get("offense")), "defense": _text(r.get("defense")),
                    "start_yards_to_goal": as_int(r.get("startYardsToGoal")),
                    "end_yards_to_goal": as_int(r.get("endYardsToGoal")),
                    "start_offense_score": as_int(r.get("startOffenseScore")),
                    "end_offense_score": as_int(r.get("endOffenseScore")),
                    "drive_result": _text(r.get("driveResult"))})
    return pd.DataFrame(out)


def talent(raw: Path = RAW) -> pd.DataFrame:
    out = [{"season": as_int(r.get("year")), "team": _text(r.get("team")), "talent": safe_numeric(r.get("talent"))}
           for r in rows("talent", ("year", "team"), raw)]
    return pd.DataFrame(out)


def load_inputs(games: pd.DataFrame, seasons: Iterable[int], raw: Path = RAW) -> Dict[str, pd.DataFrame]:
    """The same five frames, columns and filters as `own_features.load_inputs`, with `games` supplied
    (read from the warehouse's `stg_games`) and the other four read from disk."""
    seasons = {int(s) for s in seasons}
    adv, hav, drv, tal = advanced(raw), havoc(raw), drives(raw), talent(raw)
    regular = games[(games["season"].isin(seasons))]
    adv = adv[adv["season"].isin(seasons) & (adv["season_type"] == "regular")]
    hav = hav[hav["season"].isin(seasons) & (hav["season_type"] == "regular")]
    drv = drv[drv["game_id"].isin(set(regular["game_id"]))]
    tal = tal[tal["season"].isin(seasons)]
    havoc_cols = ["game_id", "team", "offense_total_plays", "defense_total_plays"] + [
        f"{side}_{h}_havoc_events" for side in ("offense", "defense") for h in ("total", "front_seven", "db")]
    frames = {
        "games": games[games["season"].isin(seasons)].copy(),
        "advanced": adv[["game_id", "team", "opponent", *ADJUSTED.values()]].reset_index(drop=True),
        "havoc": hav[havoc_cols].reset_index(drop=True),
        "drives": drv[["drive_id", "game_id", "offense", "defense", "start_yards_to_goal", "end_yards_to_goal",
                       "start_offense_score", "end_offense_score", "drive_result"]].reset_index(drop=True),
        "talent": tal[["season", "team", "talent"]].reset_index(drop=True),
    }
    return coerce(frames)
