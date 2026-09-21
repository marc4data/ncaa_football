"""Box scores for games that have finished and do not have one yet.

🚨 A181 (cfdb-main-R-1900). WHY THIS EXISTS, IN THE DESIGN'S OWN WORDS.

`src/scores_cadence.py` argued: *"A full results_refresh is 31 requests and re-fetches plays,
drives, box scores and PPA, none of which change between Saturday night and Sunday morning.
Being cheap is what makes it frequent; the heavy refresh stays weekly."*

⚠️ **That reasoning is about whether the DATA changes, not about when a reader expects to see
it** — and it compared two options while missing a third:

    re-fetch EVERYTHING every two hours        expensive, and it was right to reject
    fetch EVERYTHING once a week               cheap, and a full slate is a day late
    fetch ONLY the games that have finished    <- this module
      and do not yet have a box score

📊 MEASURED BEFORE IT WAS BUILT, not argued:

    CFBD quota (Tier 3)              7,555 of 75,000 used — 10.1%, 67,445 remaining
    a Saturday's FBS finals          71 (2026-09-19), 80 (2026-09-12)
    `games/teams`, `games/players`   SEASON_WEEK — ONE request each per week, not per game
    `game/box/advanced`              PER_GAME — one per game

🚨 **THE TWO ENDPOINTS THAT FEED THE LEADERBOARDS ARE WEEK-SCOPED.** `has_box_score` on
`fct_game_team` comes from `games/teams`, and the player boards from `games/players`; both cost
ONE request for a whole Saturday. Only the advanced box is per game. So a full Saturday through
this module is on the order of **75 + a handful** requests — about **0.2% of a month's quota** —
against a weekly refresh that spent 522 to get the same data a day later.

⚠️ **"ALREADY BOXED" IS DEFINED FROM THE WAREHOUSE, NEVER FROM A LOCAL MARKER.** A marker can
disagree with the data, and this project has been corrected by the data twice in three rounds —
A179 inferred the warehouse held 521 of 522 responses and `raw.*` said zero. The question this
module asks is the same one the site asks: *does this game have a box score in the warehouse?*
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.load_raw_to_postgres import get_conn

# The endpoints that make a completed game COMPLETE ON THE SITE, and how each is addressed.
#
# 🚨 A185 (cfdb-main-R-1909) ADDED THE LAST FOUR, AND THE REASON IS THAT "BOXED" WAS NEVER THE
# STANDARD. A181 and A184 scoped this module to box scores; Marc's standard is that the PAGES
# show data. `drives`, `plays`, `plays/stats` and `metrics/wp` all sat in `BUCKET_IMMUTABLE_WK`
# — fetched only by the weekly Sunday refresh — so after A184 a Saturday night still showed
# every box score and NO Matchup drive panel, NO win-probability chart, and no Most Exciting
# sparklines, until Sunday at the earliest and through the one fetch that had just lost a
# weekend.
#
# ⚠️ THE SPLIT IS THE WHOLE COST STORY AND IT IS NOT OBVIOUS FROM THE NAMES. Four of these are
# week-scoped — ONE request covers a whole Saturday — and three fan out per game. Treating the
# week-scoped ones as per-game would multiply the request count for an identical payload;
# treating the per-game ones as week-scoped silently truncates, which is a defect this registry
# has already been bitten by: `plays/stats` caps at 2,000 rows per response and returned exactly
# 2,000 with a 200 status, covering 11% of games while looking healthy.
WEEK_SCOPED = ("games/teams", "games/players", "drives", "plays")

# ⚠️ A TUPLE SINCE A185. It was a single string while `game/box/advanced` was the only per-game
# endpoint, and every consumer indexed it as one.
PER_GAME = ("game/box/advanced", "plays/stats", "metrics/wp")

# Which staging relation proves each layer arrived.
#
# 🚨 A184 (cfdb-main-R-1907). ALL THREE OF THESE WERE WRONG, AND THE COMMENT THAT USED TO SIT
# HERE SAID "Read rather than assumed: these are the models `fct_game_team` actually joins to
# decide `has_box_score` and `has_box_advanced`." **It had not been read.** The map was shifted
# by one relation the whole way across:
#
#     endpoint              A181 pointed at            actually fed by that endpoint
#     games/teams           stg_game_box_team          stg_game_team_stat
#     games/players         stg_game_box_player        stg_game_player_stat
#     game/box/advanced     stg_game_team_advanced     stg_game_box_team
#
# ⚠️ `stg_game_box_team` and `stg_game_box_player` BOTH read `raw_game_box_advanced`, so two
# endpoints were being proved by a THIRD endpoint's payload; and `stg_game_team_advanced` reads
# `raw_stats_game_advanced` — `stats/game/advanced`, a different endpoint again, which this DAG
# does not fetch at all.
#
# 🚨 AND THE FAILURE IS SILENT AND EXACTLY BACKWARDS FROM WHAT THE MODULE IS FOR. `PRESENCE`
# decides *already boxed*, so a wrong relation makes a game look FETCHED when it is not, and
# the incremental refresh then never asks for it again. A184 found a live instance: **Florida
# State at Alabama, week 3 (401856685) — `stg_game_box_player` has 19 rows and
# `stg_game_player_stat` has ZERO**, so the game has usage data, no player box score, is absent
# from all three of Today's player boards, and A181's map would have called it done forever.
#
# ✅ VERIFIED BY FOLLOWING THE LINEAGE RATHER THAN THE NAMES, and pinned by
# `test_presence_names_the_relation_that_endpoint_actually_feeds`, which reads the dbt manifest
# so a plausible-looking name cannot drift back in:
#
#     has_box_score     fct_game_team          <- stg_game_team_stat   <- raw_games_teams
#     has_box_advanced  fct_game_team_advanced <- stg_game_box_team    <- raw_game_box_advanced
#     player boards     fct_player_game_stat   <- stg_game_player_stat <- raw_games_players
PRESENCE = {
    "games/teams": "staging.stg_game_team_stat",
    "games/players": "staging.stg_game_player_stat",
    "game/box/advanced": "staging.stg_game_box_team",
    # A185. Resolved from the dbt manifest — for each endpoint, the staging model that reads
    # `raw_<endpoint>` — rather than by choosing a plausible name, which is the mistake A184
    # had to undo three times.
    "drives": "staging.stg_drive",
    "plays": "staging.stg_play",
    "plays/stats": "staging.stg_play_stat",
    "metrics/wp": "staging.stg_game_win_probability",
}


# 🚨 WHICH SERVING RELATIONS A FRESH BOX SCORE CHANGES, AND WHICH ARE ALREADY PUBLISHED
# (A181, cfdb-main-R-1901). A182 found this the hard way: it loaded week 3, the team box
# reached the site on the next two-hourly publish, and the THREE PLAYER BOARDS STAYED EMPTY.
#
# 📊 The cause is the publish split, not the fetch:
#
#     games/teams        -> fct_game_team      -> srv_game_team       HOT   published every 2h
#     game/box/advanced  -> fct_game_team_adv  -> srv_game_team       HOT   published every 2h
#     games/players      -> fct_player_game_stat -> srv_player_game_log  HEAVY_SERVING, WEEKLY
#
# ⚠️ **SO FETCHING PLAYER BOX SCORES EVERY TWO HOURS WITHOUT THIS WOULD PUT THEM IN THE
# WAREHOUSE AND LEAVE THEM OFF THE SITE** — the same failure one layer over, and exactly what
# A182 measured: `srv_game_team` week 3 read 150/150 while Today's player boards still said
# "Nothing to show".
#
# 📊 AND THE COST IS REAL, WHICH IS WHY IT IS CONDITIONAL RATHER THAN ADDED TO HOT_SERVING:
# `srv_player_game_log` is **475 MB** on serving (against `srv_game_team`'s 121 MB). Published
# on every two-hourly run all week it would be the most expensive thing the pipeline does over
# the link its own comments call the fragile step. Published only on runs that actually loaded
# new player box scores, it costs nothing on a Tuesday and one extra transfer on a Saturday.
# ⚠️ ONLY THE **HEAVY** RELATIONS NEED A LINE HERE. A185 (cfdb-main-R-1910). Everything the
# scores DAG builds and that lives in `SCORES_HOT` is published on every gate-open run by
# A184's gate rule; this map is for the ones deliberately kept OFF that list because of size,
# so they ship only on the runs whose own fetch changed them.
#
# 📊 MEASURED BEFORE CHOOSING (A184's method): `srv_player_game_log` 517 MB / 60 s;
# `srv_drive` + `srv_game_win_probability_play` + `srv_player_play` together 291.8 MB
# compressed to 62.8 MB, **40 s**. `srv_drive` is small (47 MB) and goes in `SCORES_HOT`; the
# other two are HEAVY and ride this map.
PUBLISH_FOR = {
    "games/players": ["srv_player_game_log"],
    "metrics/wp": ["srv_game_win_probability_play"],
    "plays/stats": ["srv_player_play"],
}


def _id_param(endpoint: str) -> str:
    """The query parameter CFBD wants for this per-game endpoint, from the registry.

    🚨 IT IS NOT THE SAME FOR ALL THREE, AND GUESSING IT FAILS SILENTLY. `game/box/advanced`
    takes `id`; `plays/stats` and `metrics/wp` take `gameId`. A wrong parameter name is not
    rejected — CFBD ignores it and answers 200 with the UNFILTERED payload, so the run looks
    successful and the warehouse gets rows for the wrong games.

    ⚠️ Read from `src/endpoints.py`, which is where fetch behaviour is declared (§4.3), so a
    registry change cannot leave a second copy behind here.
    """
    from src.endpoints import REGISTRY

    for entry in REGISTRY:
        if entry.path == endpoint:
            return entry.extra.get("id_param", "id")
    raise KeyError(f"{endpoint} is not in the endpoint registry")


def relations_to_publish(loaded_endpoints) -> List[str]:
    """The serving relations a run must republish, given what it loaded.

    ⚠️ ENDPOINT KEYS ARRIVE UNDERSCORED, because that is how `load_endpoint` names a directory
    (`games/players` -> `games_players`). Matching on the slashed form would return nothing and
    the player boards would stay empty with every task green — the failure this map exists to
    prevent, reintroduced by a string mismatch.
    """
    loaded = {str(e).replace("/", "_") for e in (loaded_endpoints or [])}
    out: List[str] = []
    for endpoint, relations in PUBLISH_FOR.items():
        if endpoint.replace("/", "_") in loaded:
            out.extend(relations)
    return sorted(set(out))


def missing_box_games(season: str, weeks: List[dict],
                      conn=None) -> Dict[str, List[dict]]:
    """Completed FBS games in `weeks` that are missing each box layer.

    Returns {endpoint: [ {game_id, week, season_type}, ... ]}.

    ⚠️ COMPLETED ONLY, WHICH IS WHAT MAKES THIS SAFE TO RUN MID-SLATE. CFBD reports
    `completed: false` for a game in progress, so a live game is simply not in the set yet —
    the same property `scores_refresh` relies on to run every two hours without recording a
    half-finished score as final.

    ⚠️ AND FBS ONLY, matching the standard the round was written against: *every completed FBS
    game is on the site with its box score*. A Division III game with no box score upstream is
    not a gap this should chase every two hours (A180 measured one: Wayland Baptist against
    Howard Payne, which CFBD never scored).
    """
    if not weeks:
        return {}

    keys = [(str(w["seasonType"]), int(w["week"])) for w in weeks]
    out: Dict[str, List[dict]] = {}
    close = conn is None
    conn = conn or get_conn()
    try:
        with conn.cursor() as cur:
            for endpoint, relation in PRESENCE.items():
                cur.execute(f"""
                    select g.game_id, g.week, g.season_type
                    from marts.fct_game g
                    where g.season = %s
                      and g.is_completed
                      and (g.home_classification = 'fbs'
                           or g.away_classification = 'fbs')
                      and (g.season_type, g.week) in %s
                      and not exists (select 1 from {relation} b
                                      where b.game_id = g.game_id)
                    order by g.game_id
                """, (season, tuple(keys)))
                out[endpoint] = [{"game_id": r[0], "week": r[1], "season_type": r[2]}
                                 for r in cur.fetchall()]
    finally:
        if close:
            conn.close()
    return out


def box_requests(season: str, weeks: List[dict],
                 conn=None) -> Tuple[List[tuple], Dict[str, int]]:
    """The fetch list, and a summary of what it is for.

    🚨 A WEEK-SCOPED ENDPOINT IS ASKED FOR A **WEEK**, NOT FOR EACH MISSING GAME. Sixty games
    missing a team box in week 3 is ONE request, not sixty — and building the list any other
    way would have cost sixty and returned the same payload sixty times.

    ✅ AND A WEEK WITH NOTHING MISSING COSTS NOTHING. On a Tuesday, when every finished game is
    already boxed, this returns an empty list and the task is a no-op — which is what lets it
    sit on a two-hourly cadence without spending quota all week.
    """
    missing = missing_box_games(season, weeks, conn=conn)
    requests: List[tuple] = []
    summary: Dict[str, int] = {}

    for endpoint in WEEK_SCOPED:
        games = missing.get(endpoint, [])
        summary[endpoint] = len(games)
        # One request per DISTINCT week that still has a gap.
        for season_type, week in sorted({(g["season_type"], g["week"]) for g in games}):
            requests.append((endpoint, {"year": season, "week": week,
                                        "seasonType": season_type}))

    # ⚠️ THE ID PARAMETER IS PER ENDPOINT AND IS READ FROM THE REGISTRY, NOT ASSUMED.
    # `game/box/advanced` takes `id`; `plays/stats` and `metrics/wp` take `gameId`, declared in
    # `src/endpoints.py` as `extra["id_param"]`. Hardcoding `id` would send a parameter CFBD
    # ignores and return the whole unfiltered payload — a 200, with the wrong rows.
    for endpoint in PER_GAME:
        games = missing.get(endpoint, [])
        summary[endpoint] = len(games)
        id_param = _id_param(endpoint)
        for game in games:
            requests.append((endpoint, {id_param: str(game["game_id"])}))

    return requests, summary


def box_refresh(season: Optional[str] = None, now=None, conn=None) -> Dict[str, object]:
    """Fetch and load the box scores that are missing, and fail loudly if any request did.

    🚨 FETCH **AND LOAD** IN ONE UNIT, WHICH IS THE POINT — "retry less; never fail quieter".

    The weekly refresh raises on the first partial failure and loads nothing, so one bad
    request in 522 discarded a whole weekend and the retry re-issued all 522 to recover one
    (`cfdb-main-R-1860`). Here, what succeeded is LOADED before the failure is raised. The run
    still fails and still alerts — nothing downstream publishes — but the next run two hours
    later recomputes the missing set from the warehouse and asks only for what is still absent.
    **Progress survives a failure; the alarm does not get quieter.**

    ⚠️ THE RAISE IS AT THE END AND IT IS NOT OPTIONAL. `a partial refresh must not read as a
    success` is the rule this keeps, not the rule it relaxes.
    """
    from datetime import datetime, timezone

    from src import ingest
    from src.load_raw_to_postgres import load_endpoint
    from src.weekly import week_window

    now = now or datetime.now(timezone.utc)
    season = season or str(now.year)
    weeks = week_window(season, now, include_prior=True)
    if not weeks:
        return {"status": "skipped", "reason": f"no active week in {season}", "requests": 0}

    requests, summary = box_requests(season, weeks, conn=conn)
    if not requests:
        return {"status": "ok", "weeks": weeks, "requests": 0, "fetched": 0,
                "missing": summary, "endpoints": []}

    fetched, failures, touched = 0, [], set()
    for endpoint, params in requests:
        resp = ingest.fetch(endpoint, params)
        touched.add(endpoint.replace("/", "_"))
        if resp.status_code == 200:
            fetched += 1
        else:
            failures.append(f"{endpoint} {params} -> {resp.status_code}")

    # LOAD WHAT ARRIVED, BEFORE RAISING. See the docstring.
    for endpoint_key in sorted(touched):
        load_endpoint(endpoint_key)

    result = {"status": "ok", "weeks": weeks, "requests": len(requests),
              "fetched": fetched, "failed": len(failures), "missing": summary,
              "endpoints": sorted(touched)}
    if failures:
        result["failures"] = failures
        raise RuntimeError(
            f"{len(failures)} of {len(requests)} box requests failed "
            f"(the {fetched} that succeeded are loaded): {failures[:5]}")
    return result
