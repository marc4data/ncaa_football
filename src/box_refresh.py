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

# The three endpoints that make a game "boxed", and how each is addressed.
#
# ⚠️ THE SPLIT IS THE WHOLE COST STORY AND IT IS NOT OBVIOUS FROM THE NAMES. Two of these are
# week-scoped and one is per game; treating all three as per-game would triple the request count
# for no benefit, and treating all three as week-scoped would silently never fetch the advanced
# box at all.
WEEK_SCOPED = ("games/teams", "games/players")
PER_GAME = "game/box/advanced"

# Which staging relation proves each layer arrived. Read rather than assumed: these are the
# models `fct_game_team` actually joins to decide `has_box_score` and `has_box_advanced`.
PRESENCE = {
    "games/teams": "staging.stg_game_box_team",
    "games/players": "staging.stg_game_box_player",
    PER_GAME: "staging.stg_game_team_advanced",
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
PUBLISH_FOR = {"games/players": ["srv_player_game_log"]}


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

    per_game = missing.get(PER_GAME, [])
    summary[PER_GAME] = len(per_game)
    for game in per_game:
        requests.append((PER_GAME, {"id": str(game["game_id"])}))

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
