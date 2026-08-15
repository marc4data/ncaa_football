"""Tests for the endpoint registry.

The registry is the project's claim about what CFBD offers and how to reach it, so the
invariants worth protecting are structural: no duplicates, every strategy understood,
and expensive or un-sweepable endpoints excluded from the default sweep.
"""
import pytest

from src import endpoints as ep


def test_no_duplicate_paths():
    paths = [e.path for e in ep.REGISTRY]
    assert len(paths) == len(set(paths))


def test_every_endpoint_has_a_known_strategy_and_bucket():
    strategies = {ep.STATIC, ep.SEASON, ep.SEASON_TYPE, ep.SEASON_WEEK,
                  ep.PER_GAME, ep.MANUAL, ep.LIVE}
    buckets = {ep.BUCKET_STRUCTURAL, ep.BUCKET_HISTORICAL, ep.BUCKET_REVISIONIST,
               ep.BUCKET_IMMUTABLE_WK, ep.BUCKET_PREGAME, ep.BUCKET_REFERENCE}
    for e in ep.REGISTRY:
        assert e.strategy in strategies, e.path
        assert e.bucket in buckets, e.path


def test_expensive_and_unsweepable_endpoints_are_opt_in():
    """PER_GAME fans out per game; MANUAL/LIVE can't be swept at all."""
    for e in ep.REGISTRY:
        if e.strategy in (ep.PER_GAME, ep.MANUAL, ep.LIVE):
            assert e.include is False, f"{e.path} should not be in the default sweep"


def test_per_game_endpoints_declare_their_id_parameter():
    """CFBD is inconsistent here: /game/box/advanced takes `id`, /metrics/wp takes `gameId`."""
    for e in ep.by_strategy(ep.PER_GAME):
        assert e.extra.get("id_param"), f"{e.path} must declare id_param"


def test_key_matches_the_ingest_directory_convention():
    assert ep.BY_PATH["games/teams"].key == "games_teams"
    assert ep.BY_PATH["teams"].key == "teams"


def test_resolve_rejects_unknown_endpoints():
    assert ep.resolve(["plays", "drives"]) == [ep.BY_PATH["plays"], ep.BY_PATH["drives"]]
    with pytest.raises(KeyError, match="nonsense"):
        ep.resolve(["plays", "nonsense"])


def test_sweepable_is_a_meaningful_subset():
    assert 0 < len(ep.SWEEPABLE) < len(ep.REGISTRY)
    assert all(e.include for e in ep.SWEEPABLE)


def test_full_history_endpoints_declare_a_min_season():
    """`full` without a bound would be unrunnable — the expansion needs a floor."""
    for e in ep.REGISTRY:
        if e.history == ep.HISTORY_FULL:
            assert e.min_season, f"{e.path} is full-history but has no min_season"
            assert 1869 <= e.min_season <= 2026, f"{e.path} min_season {e.min_season} implausible"


def test_history_defaults_to_recent():
    """Depth is opt-in: an endpoint added without thought stays at the project's default."""
    assert ep.BY_PATH["plays"].history == ep.HISTORY_RECENT
    assert ep.BY_PATH["lines"].history == ep.HISTORY_RECENT
    assert ep.BY_PATH["games"].history == ep.HISTORY_FULL


def test_the_ratified_full_history_set_is_exactly_what_was_decided():
    """Guards the decision log: membership changes should be deliberate, not incidental."""
    ratified = {
        "games", "records", "rankings", "teams", "coaches", "stats/season",
        "stats/season/advanced", "stats/player/season", "wepa/team/season",
        "ppa/players/season", "draft/picks",
        "calendar",  # added at Marc's direction 2026-08-15
    }
    assert {e.path for e in ep.REGISTRY if e.history == ep.HISTORY_FULL} == ratified
