"""Track 2's own features (cfdb-wtc-R-2430): point-in-time is enforced here, not by care.

A synthetic six-team league plays six weeks. The Week 6 games carry ABSURD stats (EPA 50, every
drive a touchdown from the 1), so any Week 6 information that reaches a Week 6 game's inputs is
impossible to miss. No warehouse, no scikit-learn: this runs in CI.
"""
import numpy as np
import pandas as pd
import pytest

from modeling import features, own_features as of

TEAMS = ["A", "B", "C", "D", "E", "F"]
SCHEDULE = [  # (week, home, away)
    (1, "A", "B"), (1, "C", "D"), (1, "E", "F"),
    (2, "A", "C"), (2, "B", "E"), (2, "D", "F"),
    (3, "A", "D"), (3, "B", "F"), (3, "C", "E"),
    (4, "A", "E"), (4, "B", "C"), (4, "D", "F"),
    (5, "A", "F"), (5, "B", "D"), (5, "C", "E"),
    (6, "A", "B"), (6, "C", "D"), (6, "E", "F"),
]
STRENGTH = dict(zip(TEAMS, [0.30, 0.20, 0.10, 0.00, -0.10, -0.20]))


@pytest.fixture
def league():
    rng = np.random.default_rng(2430)
    games, adv, havoc, drives = [], [], [], []
    for i, (week, home, away) in enumerate(SCHEDULE):
        gid = 1000 + i
        kickoff = pd.Timestamp("2025-08-30", tz="UTC") + pd.Timedelta(weeks=week - 1, hours=i % 3)
        games.append({"game_id": gid, "season": 2025, "week": week, "start_date": kickoff,
                      "is_neutral_site": False, "home_team": home, "away_team": away,
                      "home_classification": "fbs", "away_classification": "fbs",
                      "home_points": 24.0, "away_points": 21.0,
                      "home_pregame_elo": 1500.0, "away_pregame_elo": 1480.0})
        absurd = week == 6
        for team, opp in ((home, away), (away, home)):
            base = 50.0 if absurd else 0.15 + STRENGTH[team] - STRENGTH[opp] / 2 + rng.normal(0, 0.02)
            adv.append({"game_id": gid, "team": team, "opponent": opp,
                        **{col: base for col in of.ADJUSTED.values()}})
            havoc.append({"game_id": gid, "team": team, "offense_total_plays": 70.0, "defense_total_plays": 70.0,
                          **{f"{side}_{h}_havoc_events": (70.0 if absurd else 10.0)
                             for side in ("offense", "defense") for h in ("total", "front_seven", "db")}})
            for k in range(10):
                start = 1.0 if absurd else 75.0 - k
                drives.append({"game_id": gid, "offense": team, "defense": opp, "start_yards_to_goal": start,
                               "end_yards_to_goal": 0.0 if absurd else 35.0 + k,
                               "start_offense_score": 0.0, "end_offense_score": 7.0 if absurd else 3.0})
    talent = pd.DataFrame({"season": 2025, "team": TEAMS, "talent": [900.0, 800, 700, 600, 500, 400]})
    return {"games": pd.DataFrame(games), "advanced": pd.DataFrame(adv), "havoc": pd.DataFrame(havoc),
            "drives": pd.DataFrame(drives), "talent": talent}


def _independent_recompute(inputs, game_id):
    """The rule, restated from scratch: this season, an earlier week, before that week's first kickoff."""
    g = inputs["games"]
    game = g[g["game_id"] == game_id].iloc[0]
    first_kickoff = g.loc[(g["season"] == game["season"]) & (g["week"] == game["week"]), "start_date"].min()
    keep = g.loc[(g["season"] == game["season"]) & (g["week"] < game["week"])
                 & (g["start_date"] < first_kickoff), "game_id"]
    assert (g.set_index("game_id").loc[keep, "start_date"] < game["start_date"]).all()
    prior = {n: (f[f["game_id"].isin(keep)] if "game_id" in f.columns else f) for n, f in inputs.items()}
    return of.team_features(prior), game


def test_features_are_point_in_time(league):
    """STAGED BREAK (cfdb-wtc-R-2430): `inputs_before` changed to `week <= week` lets the target
    week into its own inputs, and THIS test goes RED."""
    built = of.build(league, seasons=[2025]).set_index("id")
    for game_id in (1015, 1016, 1017, 1012):                     # every Week 6 game, and one Week 5
        per_team, game = _independent_recompute(league, game_id)
        row = built.loc[game_id]
        for side, team in (("home", game["home_team"]), ("away", game["away_team"])):
            for name in per_team.columns:
                assert row[f"{side}_{name}"] == pytest.approx(per_team.loc[team, name]), (game_id, side, name)
        assert row["home_adjusted_epa"] < 1.0, "a Week 6 stat of 50 reached a Week 6 game's inputs"


def test_week_one_to_four_games_are_never_targets(league):
    built = of.build(league, seasons=[2025])
    assert set(built["id"]) == {1012, 1013, 1014, 1015, 1016, 1017}


def test_opponent_adjustment_credits_who_you_played():
    """Team X scores the same raw EPA as Y, but only against the league's best defence: adjusted, X ranks higher."""
    games = pd.DataFrame({"game_id": [1, 2, 3, 4], "home_team": ["X", "Y", "S", "W"],
                          "is_neutral_site": [True] * 4})
    rows = pd.DataFrame({"game_id": [1, 2, 3, 4], "team": ["X", "Y", "S", "W"],
                         "opponent": ["S", "W", "W", "S"], "v": [0.2, 0.2, 0.5, -0.1]})
    adj = of.adjust(rows, "v", games, alpha=1.0).set_index("team")
    assert adj.loc["X", "offense"] > adj.loc["Y", "offense"]


def test_column_names_line_up_with_the_packs_so_c1_can_read_either(league):
    built = of.build(league, seasons=[2025])
    columns = list(built.columns) + ["id", "week", "neutral_site", "home_points", "away_points", "margin", "spread"]
    stems = features.pairs_in(columns)
    assert len(stems) == 36
    for name in ("adjusted_epa_allowed", "total_havoc_defense", "points_per_opportunity_offense",
                 "avg_start_defense", "elo", "talent", "adjusted_pass_explosiveness"):
        assert name in stems


def test_talent_missing_is_zero_as_the_pack_does(league):
    league["talent"] = league["talent"][league["talent"]["team"] != "F"]
    built = of.build(league, seasons=[2025]).set_index("id")
    assert built.loc[1017, "away_talent"] == 0.0
