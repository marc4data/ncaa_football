"""A181 — box scores on the day the game is played (cfdb-main-R-1900, cfdb-main-R-1901).

> **MARC, 2026-09-20:** *"The data has to load and it has to be presented on the site. … all
> day, everyday. Saturday into Sunday is an unacceptable time to fail to load a full slate of
> game results. Unacceptable."*
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.box_refresh import (PER_GAME, PRESENCE, WEEK_SCOPED, box_requests,   # noqa: E402
                             relations_to_publish)

# ⚠️ THESE TESTS MEAN THE ADVANCED BOX SPECIFICALLY, NOT "whatever is per-game".
# Until A185 those were the same thing and `PER_GAME` was a single string; it is a tuple
# of three endpoints now, so using it as a dict key here would silently test nothing.
ADVANCED = "game/box/advanced"


class _Cursor:
    """A cursor that answers `missing_box_games`'s three queries from a script."""

    def __init__(self, answers):
        self._answers, self._rows = answers, []

    def execute(self, sql, params=None):
        # The relation name is what distinguishes the three queries.
        #
        # ⚠️ DRIVEN FROM `PRESENCE` RATHER THAN FROM HARDCODED NAMES — A184
        # (cfdb-main-R-1907). This used to name `stg_game_box_team`, `stg_game_box_player` and
        # `stg_game_team_advanced` directly, so when the map was corrected every test in this
        # file went silently to zero rows and four of them failed for a reason that had
        # nothing to do with what they were testing. A fixture that restates the thing under
        # test is a second copy that drifts.
        self._rows = []
        for endpoint, relation in PRESENCE.items():
            if relation.split(".")[-1] in sql:
                self._rows = self._answers.get(endpoint, [])
                break

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self, answers):
        self._answers = answers

    def cursor(self):
        return _Cursor(self._answers)

    def close(self):
        pass


WEEKS = [{"season": "2026", "seasonType": "regular", "week": 3}]


def test_a_week_scoped_endpoint_is_asked_for_the_week_not_for_each_game():
    """🚨 THE COST STORY, AND IT IS NOT OBVIOUS FROM THE ENDPOINT NAMES.

    📊 `games/teams` and `games/players` are SEASON_WEEK in the registry — **one request each
    for a whole Saturday** — while `game/box/advanced` is PER_GAME. Sixty games missing a team
    box in week 3 is ONE request, not sixty, and building the list the other way would have
    spent sixty to receive the same payload sixty times.
    """
    # Rows come back as tuples, the way psycopg2 yields them.
    missing = [(100 + n, 3, "regular") for n in range(60)]
    conn = _Conn({"games/teams": missing, "games/players": missing, ADVANCED: missing})

    requests, summary = box_requests("2026", WEEKS, conn=conn)

    week_scoped = [r for r in requests if r[0] in WEEK_SCOPED]
    per_game = [r for r in requests if r[0] == ADVANCED]
    assert len(week_scoped) == 2, (
        f"one request per week-scoped endpoint, not per game: {week_scoped}")
    assert len(per_game) == 60, "the advanced box really is one call per game"
    assert summary["games/teams"] == 60, "the SUMMARY still counts games, not requests"

    # Every week-scoped request names the week, and every per-game one names a game.
    for endpoint, params in week_scoped:
        assert params == {"year": "2026", "week": 3, "seasonType": "regular"}, endpoint
    assert {p["id"] for _e, p in per_game} == {str(100 + n) for n in range(60)}


def test_two_weeks_with_gaps_cost_one_request_each_not_one_per_game():
    """⚠️ The results window covers the prior week too, so a Sunday run spans two."""
    missing = [(1, 2, "regular"), (2, 3, "regular"), (3, 3, "regular")]
    conn = _Conn({"games/teams": missing, "games/players": [], ADVANCED: []})
    requests, _ = box_requests("2026", WEEKS, conn=conn)
    teams = [p["week"] for e, p in requests if e == "games/teams"]
    assert sorted(teams) == [2, 3], f"one per distinct week: {teams}"


def test_a_week_with_nothing_missing_costs_nothing():
    """✅ THE PROPERTY THAT LETS THIS SIT ON A TWO-HOURLY CADENCE. On a Tuesday every finished
    game is already boxed, so the request list is empty and the task is a no-op. A design that
    re-fetched regardless is the one `scores_cadence.py` rightly rejected."""
    conn = _Conn({"games/teams": [], "games/players": [], ADVANCED: []})
    requests, summary = box_requests("2026", WEEKS, conn=conn)
    assert requests == []
    assert set(summary.values()) == {0}


def test_no_weeks_in_play_asks_for_nothing():
    requests, summary = box_requests("2026", [], conn=_Conn({}))
    assert requests == []
    # The summary still names every endpoint at zero — an explicit "nothing missing" reads
    # better in a task log than an empty dict, which looks like the check did not run.
    assert set(summary.values()) == {0}


# --- the publish half, which A182 proved is not optional -----------------------------------

def test_new_player_box_scores_republish_the_relation_that_carries_them():
    """🚨 A182 LOADED WEEK 3 AND THE PLAYER BOARDS STAYED EMPTY. `srv_game_team` is HOT and
    publishes every two hours; `srv_player_game_log` is HEAVY_SERVING and publishes WEEKLY.
    Fetching player box scores on the fast cadence without this moves the day-late problem
    from the fetch to the publish and changes nothing a reader sees."""
    assert relations_to_publish(["games_players"]) == ["srv_player_game_log"]
    assert relations_to_publish(["games_players", "game_box_advanced"]) \
        == ["srv_player_game_log"]


def test_a_run_that_changed_no_player_box_publishes_no_heavy_relation():
    """⚠️ 475 MB against srv_game_team's 121 MB. Publishing it on every two-hourly run all
    week would make the quietest Tuesday the most expensive thing the pipeline does."""
    assert relations_to_publish([]) == []
    assert relations_to_publish(["games_teams", "game_box_advanced"]) == []


def test_the_endpoint_key_is_matched_in_the_form_the_loader_uses():
    """🚨 `load_endpoint` names a directory `games_players`, not `games/players`. Matching the
    slashed form would return nothing, publish nothing, and leave the player boards empty with
    every task green — the failure this map exists to prevent, reintroduced by a string."""
    assert relations_to_publish(["games_players"]) == relations_to_publish(["games/players"])


# --- the DAG wiring ------------------------------------------------------------------------

def _dag_source():
    return (ROOT / "dags" / "scores_refresh_dag.py").read_text()


def test_the_box_task_runs_after_the_spine_has_loaded():
    """🚨 THE PLACEMENT IS THE WHOLE DESIGN, NOT A DETAIL.

    The missing set is computed from the warehouse, so it must be read AFTER this run's spine
    has landed. Before the load, a game that went final in the last two hours is not yet known
    to be complete and its box score waits for the NEXT run — which doubles the worst-case
    delay from one cadence to two.
    """
    source = _dag_source()
    chain = next(ln for ln in source.splitlines() if "gate >> fetch" in ln)
    order = [chain.index(name) for name in
             ("load", "boxes", "dbt_run", "publish")]
    assert order == sorted(order), f"the box task is in the wrong place: {chain.strip()}"


def test_the_box_task_derives_its_own_work_rather_than_reading_an_xcom():
    """⚠️ cfdb-main-R-1863. `_load` pulls its endpoint list from the fetch task, which is how a
    failed fetch produced a green load that loaded nothing. This task asks the warehouse every
    time it runs, so there is no upstream value for it to lose."""
    source = _dag_source()
    tree = ast.parse(source)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_refresh_boxes")
    body = ast.get_source_segment(source, fn)
    assert "xcom_pull" not in body, (
        "the box task must not depend on an upstream XCom for its work")
    assert "box_refresh()" in body


def test_the_publish_refuses_when_it_cannot_tell_what_changed():
    """🚨 cfdb-main-R-1865's rule, applied one task over. Publishing the hot views and
    reporting success while new player box scores sit unpublished in the warehouse is the same
    false green in a different place."""
    source = _dag_source()
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_publish")
    body = ast.get_source_segment(source, fn)
    assert "if loaded is None:" in body and "raise RuntimeError" in body, body[:400]
    assert "or []" not in body, "an absent value must not collapse into 'nothing to do'"


# --- PART 3: break it on purpose ------------------------------------------------------------

class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code


def _run_box_refresh(monkeypatch, conn, failing=(), loaded=None):
    """Drive `box_refresh` with a stubbed API and loader. `failing` are params that 429."""
    import src.box_refresh as box
    import src.ingest as ingest
    import src.load_raw_to_postgres as loader
    import src.weekly as weekly

    asked = []

    def fetch(endpoint, params):
        asked.append((endpoint, params))
        bad = any(params.get("id") == str(g) for g in failing)
        return _Resp(429 if bad else 200)

    monkeypatch.setattr(ingest, "fetch", fetch)
    # ⚠️ `loaded or []` WOULD BUILD A FRESH LIST when the caller passes an empty one, and the
    # appends would vanish — the same `or []` trap this round removed from two DAGs, committed
    # here in the test helper that proves the fix. An empty list is not an absent one.
    sink = loaded if loaded is not None else []
    monkeypatch.setattr(loader, "load_endpoint", lambda e: sink.append(e))
    monkeypatch.setattr(weekly, "week_window", lambda *a, **k: WEEKS)
    return box.box_refresh(season="2026", conn=conn), asked


def test_a_failed_request_still_loads_what_arrived_and_still_fails_the_run(monkeypatch):
    """🚨 "RETRY LESS; NEVER FAIL QUIETER" — BOTH HALVES, IN ONE TASK.

    The weekly refresh raises on the first partial failure and loads NOTHING, so one bad
    request in 522 discarded a whole weekend and the retry re-issued all 522 to recover one
    (`cfdb-main-R-1860`). Here the successes are LOADED before the failure is raised.

    ✅ **The run still fails and still alerts** — nothing downstream publishes — but the next
    run recomputes the missing set from the warehouse and asks only for what is still absent.
    **Progress survives a failure; the alarm does not get quieter.**
    """
    missing = [(101, 3, "regular"), (102, 3, "regular"), (103, 3, "regular")]
    conn = _Conn({"games/teams": [], "games/players": [], ADVANCED: missing})
    loaded = []

    with pytest.raises(RuntimeError) as exc:
        _run_box_refresh(monkeypatch, conn, failing=(102,), loaded=loaded)

    message = str(exc.value)
    assert "1 of 3 box requests failed" in message, message
    assert "the 2 that succeeded are loaded" in message, (
        "the refusal must say that progress was kept, or the next reader assumes it was not")
    assert "429" in message, "the status code is the finding, not a paraphrase"

    # 🚨 AND THE LOAD REALLY RAN. Without this the message above would be a claim.
    assert loaded == ["game_box_advanced"], loaded


def test_the_next_run_asks_only_for_what_is_still_missing(monkeypatch):
    """⚠️ THE OTHER HALF OF THE SAME PROMISE, AND THE ONE THE WEEKLY REFRESH CANNOT KEEP.

    After the failure above, two of the three games are in the warehouse. The next run derives
    its work from the warehouse again, so it asks for ONE game — not three, and not 522.
    """
    still_missing = [(102, 3, "regular")]
    conn = _Conn({"games/teams": [], "games/players": [], ADVANCED: still_missing})

    result, asked = _run_box_refresh(monkeypatch, conn, failing=())

    assert [p["id"] for _e, p in asked] == ["102"], asked
    assert result["fetched"] == 1 and result["requests"] == 1
    assert result.get("failed", 0) == 0


def test_a_run_with_nothing_missing_asks_for_nothing_at_all(monkeypatch):
    """✅ The Tuesday case, end to end: no requests, no load, no failure."""
    conn = _Conn({"games/teams": [], "games/players": [], ADVANCED: []})
    loaded = []
    result, asked = _run_box_refresh(monkeypatch, conn, loaded=loaded)
    assert asked == [] and loaded == []
    assert result["requests"] == 0 and result["endpoints"] == []


# ── THE PRESENCE MAP IS LINEAGE, NOT NAMING (A184, cfdb-main-R-1907) ────────────────────────

def test_presence_names_the_relation_that_endpoint_actually_feeds():
    """🚨 ALL THREE ENTRIES WERE WRONG AND EVERY ONE OF THEM LOOKED RIGHT.

    `stg_game_box_team`, `stg_game_box_player`, `stg_game_team_advanced` and
    `stg_game_player_stat` are four plausible names for "the box score", and A181's map picked
    the wrong one three times out of three — two endpoints proved by a THIRD endpoint's payload
    and one by a fourth the pipeline does not even fetch here.

    ⚠️ SO THIS ASSERTS LINEAGE FROM THE MANIFEST RATHER THAN COMPARING STRINGS. A name test
    would have passed on the broken map — that is precisely how it shipped.

    🚨 AND THE DEFECT IS SILENT AND INVERTED: `PRESENCE` decides *already boxed*, so a wrong
    relation makes a missing game look fetched and the incremental refresh never asks again.
    Live instance: Florida State at Alabama (401856685) had 19 `stg_game_box_player` rows and
    ZERO `stg_game_player_stat` rows — no player box score, absent from all three player
    boards, and marked done.
    """
    import json

    manifest = (Path(__file__).resolve().parents[1]
                / "dbt" / "target" / "manifest.json")
    if not manifest.exists():
        pytest.skip("no compiled manifest — run `dbt parse` (R-575)")
    man = json.loads(manifest.read_text())

    # model name -> the raw source tables it reads
    sources = {}
    for uid, node in man["nodes"].items():
        if node["resource_type"] != "model":
            continue
        raw = {man["sources"][s]["name"]
               for s in node.get("depends_on", {}).get("nodes", [])
               if s in man.get("sources", {})}
        if raw:
            sources[node["name"]] = raw

    for endpoint, relation in PRESENCE.items():
        model = relation.split(".")[-1]
        expected_raw = "raw_" + endpoint.replace("/", "_")
        assert model in sources, (
            f"{model} reads no raw source at all, so it cannot prove {endpoint} arrived")
        assert expected_raw in sources[model], (
            f"PRESENCE maps {endpoint!r} to {relation}, but that model reads "
            f"{sorted(sources[model])} — not {expected_raw}. A relation fed by a DIFFERENT "
            f"endpoint cannot prove this one arrived, and getting it wrong marks a missing "
            f"game as already boxed.")


def test_presence_covers_every_endpoint_the_refresh_fetches():
    """A layer with no presence relation is a layer nothing can prove arrived."""
    for endpoint in WEEK_SCOPED + PER_GAME:
        assert endpoint in PRESENCE, f"{endpoint} is fetched but has no presence relation"
