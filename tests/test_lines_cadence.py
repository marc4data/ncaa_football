"""Tests for the betting-line cadence gate.

The gate decides whether irreversible history gets captured, so the boundaries are tested
explicitly rather than by sampling the middle of the window and assuming the edges follow.
"""
from datetime import date, datetime, timezone

import pytest

from src.lines_cadence import CadenceConfig, Decision, load_config, should_snapshot

# The live 2026 configuration: first game 2026-08-27, 7 days lead -> window opens 08-20.
CONFIG = CadenceConfig(
    season=2026,
    first_game_date=date(2026, 8, 27),
    lead_days=7,
    season_end_date=date(2027, 1, 31),
)


def at(y, m, d, hour=0) -> datetime:
    return datetime(y, m, d, hour, tzinfo=timezone.utc)


def test_window_start_is_lead_days_before_the_first_game():
    assert CONFIG.window_start == date(2026, 8, 20)
    assert CONFIG.window_end == date(2027, 1, 31)


# --- inside the window: every run proceeds ------------------------------------------

def test_inside_window_every_four_hourly_run_proceeds():
    """In season, all six daily runs capture — this is the whole point of the exercise."""
    for hour in (0, 4, 8, 12, 16, 20):
        decision = should_snapshot(at(2026, 9, 15, hour), CONFIG)
        assert decision.proceed, f"{hour:02d}:00 should proceed in season"
        assert decision.branch == "in_season"


def test_inside_window_during_the_postseason():
    """The window runs to the championship, not to the end of the regular season."""
    assert should_snapshot(at(2027, 1, 15, 12), CONFIG).proceed


# --- outside the window: only the 00:00 UTC run proceeds ----------------------------

def test_outside_window_at_midnight_proceeds():
    decision = should_snapshot(at(2026, 6, 1, 0), CONFIG)
    assert decision.proceed
    assert decision.branch == "off_season_daily"


def test_outside_window_at_0400_skips():
    decision = should_snapshot(at(2026, 6, 1, 4), CONFIG)
    assert not decision.proceed
    assert decision.branch == "off_season_skip"


def test_outside_window_all_non_midnight_runs_skip():
    """Exactly one run a day off-season: five of the six are skipped."""
    proceeded = [h for h in (0, 4, 8, 12, 16, 20)
                 if should_snapshot(at(2026, 6, 1, h), CONFIG).proceed]
    assert proceeded == [0]


# --- the boundary days themselves ----------------------------------------------------

def test_boundary_day_window_opens_is_inside():
    """2026-08-20 is the switch date: 04:00 must proceed, which it would not the day before."""
    assert should_snapshot(at(2026, 8, 20, 4), CONFIG).branch == "in_season"
    assert should_snapshot(at(2026, 8, 20, 0), CONFIG).branch == "in_season"


def test_day_before_the_window_is_still_daily():
    """2026-08-19 at 04:00 is the last skipped run before the season cadence begins."""
    assert should_snapshot(at(2026, 8, 19, 4), CONFIG).branch == "off_season_skip"
    assert should_snapshot(at(2026, 8, 19, 0), CONFIG).branch == "off_season_daily"


def test_last_day_of_the_window_is_inside():
    assert should_snapshot(at(2027, 1, 31, 20), CONFIG).branch == "in_season"


def test_day_after_the_window_reverts_to_daily():
    assert should_snapshot(at(2027, 2, 1, 20), CONFIG).branch == "off_season_skip"
    assert should_snapshot(at(2027, 2, 1, 0), CONFIG).branch == "off_season_daily"


# --- the dates this decision was actually made for ----------------------------------

def test_today_2026_08_17_is_pre_switch():
    """Today is three days before the switch: daily cadence still applies."""
    assert should_snapshot(at(2026, 8, 17, 4), CONFIG).branch == "off_season_skip"
    assert should_snapshot(at(2026, 8, 17, 0), CONFIG).branch == "off_season_daily"


# --- shape and robustness ------------------------------------------------------------

def test_a_naive_datetime_is_treated_as_utc():
    """Airflow hands the logical date over in several shapes; none should crash the gate."""
    naive = datetime(2026, 9, 15, 12)
    assert should_snapshot(naive, CONFIG).proceed


def test_a_non_utc_datetime_is_converted_not_assumed():
    """20:00 US/Pacific on 08-19 is 03:00 UTC on 08-20 — inside the window."""
    from zoneinfo import ZoneInfo
    pacific = datetime(2026, 8, 19, 20, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert should_snapshot(pacific, CONFIG).branch == "in_season"


def test_decision_is_truthy_and_carries_a_reason():
    """The reason is what gets logged; a skip must never be silent."""
    decision = should_snapshot(at(2026, 6, 1, 4), CONFIG)
    assert isinstance(decision, Decision)
    assert bool(decision) is False
    assert "outside the active window" in decision.reason


def test_config_loads_from_the_repo_file():
    """The shipped config must parse and describe the season it claims to."""
    config = load_config("config/lines_cadence.json")
    assert config.season == 2026
    assert config.first_game_date == date(2026, 8, 27)
    assert config.lead_days == 7
    assert config.window_start == date(2026, 8, 20), "switch date must be 2026-08-20"
    assert config.season_end_date > config.first_game_date


def test_missing_config_raises_rather_than_defaulting():
    """A silent default would poll at the wrong cadence for months."""
    with pytest.raises(FileNotFoundError):
        load_config("config/does_not_exist.json")
