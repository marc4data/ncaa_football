"""The both-teams-over rule and the disk lines reader (cfdb edges work, 2026-09-30).

Every fixture is hand-worked, and each case is chosen so a wrong sign moves it: a game where the
home team is favoured by 7 with a total of 50 implies home 28.5, away 21.5. A model saying home 30,
away 22 beats both (cushion +0.5); home 30, away 21 beats only one.
"""
import json

import pandas as pd
import pytest

from modeling import disk_source, over_rule


def _game(pred_home, pred_away, home_points, away_points, spread=-7.0, total=50.0):
    return {"game_id": 1, "pred_home": pred_home, "pred_away": pred_away, "spread": spread,
            "market_total": total, "home_points": home_points, "away_points": away_points}


def test_implied_points_follow_the_away_minus_home_sign():
    home, away = over_rule.implied_points(pd.Series([-7.0]), pd.Series([50.0]))
    assert (home.iloc[0], away.iloc[0]) == (28.5, 21.5)


def test_both_sides_over_fires_one_side_over_does_not():
    frame = over_rule.apply_rule(pd.DataFrame([_game(30, 22, 31, 24), _game(30, 21, 31, 24)]))
    assert frame["over_cushion"].tolist() == [0.5, -0.5]
    assert (frame["over_cushion"] > 0).tolist() == [True, False]


def test_the_cushion_is_the_weaker_side():
    frame = over_rule.apply_rule(pd.DataFrame([_game(40, 22, 31, 24)]))
    assert frame.loc[0, "gap_home"] == 11.5 and frame.loc[0, "over_cushion"] == 0.5


def test_results_and_pushes_are_graded_against_the_total():
    frame = over_rule.apply_rule(pd.DataFrame([_game(30, 22, 31, 24), _game(30, 22, 20, 20),
                                               _game(30, 22, 25, 25)]))
    assert frame["ou_result"].tolist() == ["over", "under", "push"]


def test_a_push_counts_in_neither_hits_nor_misses():
    frame = over_rule.apply_rule(pd.DataFrame([_game(30, 22, 31, 24), _game(30, 22, 20, 20),
                                               _game(30, 22, 25, 25)]))
    row = over_rule.summarize(frame, thresholds=(0.0,)).set_index("direction").loc["both over → over"]
    assert (row["fires"], row["hits"], row["misses"], row["pushes"]) == (3, 1, 1, 1)
    assert row["hit_rate"] == 0.5


def test_the_under_mirror_fires_when_both_sides_are_below():
    frame = over_rule.apply_rule(pd.DataFrame([_game(27, 20, 20, 20)]))
    assert frame.loc[0, "under_cushion"] == 1.5
    row = over_rule.summarize(frame, thresholds=(0.0,)).set_index("direction").loc["both under → under"]
    assert (row["hits"], row["misses"]) == (1, 0)


@pytest.mark.parametrize("rate,low,expected", [(0.52, 0.49, "no edge"), (0.55, 0.51, "promising, not proven"),
                                               (0.58, 0.53, "edge")])
def test_the_verdict_is_the_pre_registered_reading(rate, low, expected):
    assert over_rule.verdict({"hits": 1, "misses": 1, "hit_rate": rate, "range_low": low}) == expected


def test_disk_lines_take_the_median_across_books(tmp_path):
    folder = tmp_path / "lines"
    folder.mkdir()
    game = {"id": 7, "season": 2019, "week": 6, "seasonType": "regular", "homeTeam": "A", "awayTeam": "B",
            "homeScore": 30, "awayScore": 20,
            "lines": [{"provider": "x", "spread": -3, "overUnder": 50},
                      {"provider": "y", "spread": -4, "overUnder": None},
                      {"provider": "z", "spread": -6, "overUnder": 52}]}
    (folder / "2026-09-30T00-00-00-000Z.json").write_text(json.dumps({"status_code": 200, "data": [game]}))
    row = disk_source.lines(tmp_path).iloc[0]
    assert (row["spread"], row["market_total"], row["books"]) == (-4.0, 51.0, 3)


def test_team_history_reads_each_game_from_both_sides():
    """Home favoured by 7 (spread −7, total 50) wins 30–20: home covers by 3, away misses by 3, over by 0."""
    from modeling import edges_workbook
    games = pd.DataFrame([{"game_id": 1, "season": 2025, "week": 6, "start_date": "2025-10-04T19:00:00Z",
                           "home_team": "H", "away_team": "A", "home_conference": "X", "away_conference": "Y",
                           "home_points": 30, "away_points": 20, "spread": -7.0, "market_total": 50.0}])
    h = edges_workbook.team_history(games, pd.DataFrame(columns=["game_id"])).set_index("team")
    assert (h.at["H", "team spread"], h.at["H", "ATS margin"], h.at["H", "covered"]) == (-7.0, 3.0, "yes")
    assert (h.at["A", "team spread"], h.at["A", "ATS margin"], h.at["A", "covered"]) == (7.0, -3.0, "no")
    assert (h.at["H", "implied for"], h.at["H", "vs implied for"]) == (28.5, 1.5)
    assert (h.at["A", "implied for"], h.at["A", "vs implied for"]) == (21.5, -1.5)
    assert h.at["H", "O/U"] == "push" and h.at["A", "opponent"] == "H"
