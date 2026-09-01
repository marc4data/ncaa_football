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
