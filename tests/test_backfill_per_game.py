"""The per-game fan-out is the most expensive thing this project can do.

Two endpoints at one call per game. Over every completed game in CFBD's universe that is
15,260 calls for 2024-2025; over FBS games it is 3,706. The difference is not a rounding
error against a 75,000/month quota that normally sits near 2,300, so the scope rule is worth
holding in a test rather than in a comment.
"""
from src import backfill
from src.endpoints import BY_PATH


def _games(*rows):
    """A /games payload: (id, completed, homeClassification, awayClassification)."""
    return [{"id": gid, "completed": done,
             "homeClassification": home, "awayClassification": away}
            for gid, done, home, away in rows]


def test_only_completed_fbs_games_fan_out(monkeypatch):
    """An FBS team's game against an FCS opponent IS one of its games — dropping it would
    leave a hole in that team's schedule that reads as missing data rather than as scope.
    Two non-FBS teams playing each other is not in this warehouse at any grain."""
    monkeypatch.setattr(backfill, "SEASON_TYPES", ["regular"])
    monkeypatch.setattr(backfill, "load_latest_raw", lambda *_a, **_k: _games(
        (1, True, "fbs", "fbs"),      # both FBS -> in
        (2, True, "fbs", "fcs"),      # FBS hosting FCS -> in
        (3, True, "fcs", "fbs"),      # FCS hosting FBS -> in, either side counts
        (4, True, "fcs", "fcs"),      # neither -> out
        (5, True, "iii", "ii"),       # neither -> out
        (6, False, "fbs", "fbs"),     # not completed -> out
    ))
    assert backfill.completed_game_ids("2024") == ["1", "2", "3"]


def test_an_unplayed_game_never_fans_out(monkeypatch):
    """Fanning out over a game that has not happened spends a call to be told nothing."""
    monkeypatch.setattr(backfill, "SEASON_TYPES", ["regular"])
    monkeypatch.setattr(backfill, "load_latest_raw", lambda *_a, **_k: _games(
        (10, False, "fbs", "fbs"), (11, False, "fbs", "fcs")))
    assert backfill.completed_game_ids("2026") == []


def test_the_two_endpoints_disagree_about_the_id_parameter():
    """/game/box/advanced takes `id`; /metrics/wp takes `gameId`. Sending the wrong one
    returns a 400 per game — 1,853 wasted calls before anybody reads the log."""
    assert BY_PATH["game/box/advanced"].extra["id_param"] == "id"
    assert BY_PATH["metrics/wp"].extra["id_param"] == "gameId"


def test_per_game_endpoints_are_opt_in(monkeypatch):
    """They must never join the default sweep: the weekly refresh would spend thousands of
    calls without anybody asking for them."""
    for path in ("game/box/advanced", "metrics/wp"):
        assert BY_PATH[path].include is False


def test_the_plan_uses_each_endpoints_own_id_parameter(monkeypatch):
    monkeypatch.setattr(backfill, "SEASON_TYPES", ["regular"])
    monkeypatch.setattr(backfill, "load_latest_raw", lambda *_a, **_k: _games(
        (7, True, "fbs", "fbs")))
    box = backfill.requests_for(BY_PATH["game/box/advanced"], ["2024"], per_game=True)
    wp = backfill.requests_for(BY_PATH["metrics/wp"], ["2024"], per_game=True)
    assert box == [("game/box/advanced", {"id": "7"})]
    assert wp == [("metrics/wp", {"gameId": "7"})]


def test_without_the_flag_nothing_fans_out(monkeypatch):
    """--per-game is the whole guard against an accidental five-figure spend."""
    monkeypatch.setattr(backfill, "SEASON_TYPES", ["regular"])
    monkeypatch.setattr(backfill, "load_latest_raw", lambda *_a, **_k: _games(
        (8, True, "fbs", "fbs")))
    assert backfill.requests_for(BY_PATH["metrics/wp"], ["2024"], per_game=False) == []


# --- min_season is a floor in every path ---------------------------------------------------

def test_min_season_floors_a_normal_backfill():
    """AN OUT-OF-RANGE YEAR IS A 200 WITH AN EMPTY ARRAY, NOT A 404.

    The passing/* endpoints begin in 2025 — probed, not assumed: 2022, 2023 and 2024 all
    answer 200 with zero rows. Without a floor, `--seasons 2024` would write a file, record a
    success in the manifest, and leave an endpoint that looks landed and holds nothing. That
    is the exact confusion the coverage matrix's "raw only" vs "no raw data" split exists to
    prevent, arriving one layer earlier — and unlike a 400 it leaves no trace.

    min_season used to apply only under --full-history, which is why this could happen.
    """
    passing = BY_PATH["passing/plays"]
    assert passing.min_season == 2025
    assert backfill.seasons_for(passing, ["2024", "2025", "2026"],
                                full_history=False, current_season=2026) == ["2025", "2026"]
    assert backfill.seasons_for(passing, ["2024"],
                                full_history=False, current_season=2026) == []


def test_the_floor_does_not_disturb_endpoints_that_predate_it():
    """Every other floor in the registry sits below the project's 2024 default, so this
    change must be a no-op for them — the guard is against a silent narrowing."""
    games = BY_PATH["games"]
    assert games.min_season == 1869
    assert backfill.seasons_for(games, ["2024", "2025"],
                                full_history=False, current_season=2026) == ["2024", "2025"]


def test_an_endpoint_with_no_floor_takes_the_seasons_as_given():
    lines = BY_PATH["lines"]
    assert lines.min_season is None
    assert backfill.seasons_for(lines, ["2024", "2025"],
                                full_history=False, current_season=2026) == ["2024", "2025"]


def test_the_passing_endpoints_stay_out_of_the_default_sweep():
    """passing/plays is 7,396 rows and 5.9 MB for one week. In the sweep it would change what
    the weekly refresh costs without anybody deciding to."""
    for path in ("passing/players/season", "passing/teams/season", "passing/players/games",
                 "passing/teams/games", "passing/plays"):
        assert BY_PATH[path].include is False, path
        assert BY_PATH[path].min_season == 2025, path


# --- a network error is one failed request, not a failed backfill --------------------------

def test_a_timeout_is_recorded_and_the_plan_continues(monkeypatch, capsys):
    """THE PASSING BACKFILL DIED ON ITS FIRST REQUEST BECAUSE THIS CALL WAS UNGUARDED.

    A read timeout propagated out of run() and killed the whole plan with a traceback, so the
    operator saw a stack trace instead of a summary saying what to re-run. On a long plan that
    is the difference between losing one request and losing hours: the per-game fan-out is
    3,706 requests, and a blip at request 3,000 would have ended it.
    """
    import requests

    calls = []

    class Response:
        status_code = 200

    def flaky(endpoint, params):
        calls.append(params)
        if len(calls) == 1:
            raise requests.exceptions.ReadTimeout("read timed out")
        return Response()

    monkeypatch.setattr(backfill.ingest, "fetch", flaky)
    monkeypatch.setattr(backfill, "already_fetched", lambda *_a: False)
    monkeypatch.setattr(backfill, "SLEEP_SECONDS", 0)
    monkeypatch.setattr(backfill, "build_plan",
                        lambda *a, **k: [("teams", {"year": "2024"}),
                                         ("teams", {"year": "2025"})])

    exit_code = backfill.run(["2024", "2025"], only=None, bucket=None, per_game=False,
                             force=False, dry_run=False)

    assert len(calls) == 2, "the second request must still be attempted"
    out = capsys.readouterr().out
    assert "ReadTimeout" in out, "the failure must name what went wrong"
    assert "fetched=1" in out and "failed=1" in out
    # A partial backfill must not look like a success — the existing contract, kept.
    assert exit_code == 1


def test_the_request_timeout_separates_connect_from_read():
    """A flat 30s was too tight: /game/box/advanced measured 20.2s on one call and
    /passing/plays returns 5.9 MB for a week. The connect half stays short because a
    connection that will not establish in ten seconds is not going to."""
    from src import ingest
    connect, read = ingest.REQUEST_TIMEOUT
    assert connect <= 15
    assert read >= 120
