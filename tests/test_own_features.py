"""Track 2's own features (cfdb-wtc-R-2430): point-in-time is enforced here, not by care.

A synthetic six-team league plays six weeks. The Week 6 games carry ABSURD stats (EPA 50, every
drive a touchdown from the 1), so any Week 6 information that reaches a Week 6 game's inputs is
impossible to miss. No warehouse, no scikit-learn: this runs in CI.
"""
import numpy as np
import pandas as pd
import pytest

from modeling import features, leakage, own_features as of

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
                      "home_points": 99.0 if week == 6 else 24.0 + 30 * STRENGTH[home],
                      "away_points": 0.0 if week == 6 else 21.0 + 30 * STRENGTH[away],
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


# ---------------------------------------------------------------- cfdb-wtc-R-2440: SOS and the division prior

def _ratings_as_of(inputs, season, week):
    """Ratings from scratch: games of this season in an earlier week, before that week's first kickoff."""
    g = inputs["games"]
    first = g.loc[(g["season"] == season) & (g["week"] == week), "start_date"].min()
    keep = g.loc[(g["season"] == season) & (g["week"] < week) & (g["start_date"] < first), "game_id"]
    return of.ratings_at({n: (f[f["game_id"].isin(keep)] if "game_id" in f.columns else f) for n, f in inputs.items()})


def test_strength_of_schedule_rates_each_opponent_as_it_stood_at_kickoff(league):
    """STAGED BREAK (cfdb-wtc-R-2440): rating each past opponent by its CURRENT rating (as of the
    target week) instead of its rating at that game's kickoff turns THIS test RED."""
    built = of.build(league, seasons=[2025], sos=True).set_index("id")
    g = league["games"]
    for game_id in (1015, 1016, 1012):
        game = g[g["game_id"] == game_id].iloc[0]
        for side in ("home", "away"):
            team = game[f"{side}_team"]
            past = g[(g["week"] < game["week"]) & ((g["home_team"] == team) | (g["away_team"] == team))]
            eff, pts = [], []
            for p in past.itertuples():
                opponent = p.away_team if p.home_team == team else p.home_team
                r = _ratings_as_of(league, 2025, p.week)
                eff.append(r["efficiency"].get(opponent, 0.0) if len(r) else 0.0)
                pts.append(r["points"].get(opponent, 0.0) if len(r) else 0.0)
            row = built.loc[game_id]
            assert row[f"{side}_sos_efficiency"] == pytest.approx(np.mean(eff)), (game_id, side)
            assert row[f"{side}_sos_results"] == pytest.approx(np.mean(pts)), (game_id, side)
            now = _ratings_as_of(league, 2025, game["week"])
            assert row[f"{side}_points_rating"] == pytest.approx(now["points"].get(team, 0.0))
            assert abs(row[f"{side}_points_rating"]) < 40, "a Week 6 99-0 reached a Week 6 rating"


def test_sos_columns_are_ours_and_pass_the_leakage_guard(league):
    built = of.build(league, seasons=[2025], sos=True)
    ours = [c for c in built.columns if "sos_" in c or "points_rating" in c]
    assert len(ours) == 6 and leakage.assert_no_leakage(ours) == ours


def test_points_rating_caps_a_blowout_at_four_scores():
    games = pd.DataFrame({"game_id": [1, 2], "home_team": ["X", "Y"], "away_team": ["Z", "Z"],
                          "home_points": [70.0, 56.0], "away_points": [0.0, 0.0], "is_neutral_site": [True, True]})
    r = of.points_ratings(games, alpha=0.0001)
    assert r["X"] == pytest.approx(r["Y"], abs=1e-3)          # 70-0 and 56-0 both count as +28


def test_a_thin_fcs_opponent_shrinks_toward_fcs_average_not_the_leagues():
    """Marc's case: a big day against an FCS defence is credited less once the prior knows what FCS is."""
    games = pd.DataFrame({"game_id": range(1, 9), "home_team": ["X", "Y", "S", "W", "S", "W", "V", "X"],
                          "is_neutral_site": [True] * 8})
    # both sides of the FCS games, as in the warehouse
    rows = pd.DataFrame({"game_id": [1, 1, 2, 2, 3, 4, 5, 6, 7, 8],
                         "team":     ["X", "Z", "Y", "Q", "S", "W", "S", "W", "V", "X"],
                         "opponent": ["Z", "X", "Q", "Y", "W", "S", "V", "V", "S", "S"],
                         "v":        [0.90, -0.20, 0.85, -0.25, 0.20, 0.10, 0.25, 0.15, 0.12, 0.30]})
    division = {t: "fbs" for t in "XYSWV"} | {"Z": "fcs", "Q": "fcs"}
    flat = of.adjust(rows, "v", games, alpha=4.0).set_index("team")
    prior = of.adjust(rows, "v", games, alpha=4.0, division=division).set_index("team")
    assert prior.loc["Z", "allowed"] > flat.loc["Z", "allowed"] + 0.1
    assert prior.loc["X", "offense"] < flat.loc["X", "offense"]


def test_no_switches_is_r2430s_build(league):
    """Every R-2440 change is behind a switch; with all of them off, the build is R-2430's."""
    default = of.build(league, seasons=[2025])
    assert not any("sos_" in c or "points_rating" in c for c in default.columns)


def test_a_team_that_changes_division_is_judged_by_that_seasons_division():
    """cfdb-wtc-R-2450: Delaware was FCS in 2024 and FBS in 2025. A map built across seasons would call
    it FBS in 2024; per season it must not."""
    games = pd.DataFrame({"season": [2024, 2025], "home_team": ["Delaware", "Delaware"],
                          "away_team": ["Rival", "Rival"], "home_classification": ["fcs", "fbs"],
                          "away_classification": ["fbs", "fbs"]})
    assert of.divisions(games[games["season"] == 2024])["Delaware"] == "fcs"
    assert of.divisions(games[games["season"] == 2025])["Delaware"] == "fbs"


# ---------------------------------------------------------------- cfdb-wtc-R-2450: scoring an upcoming week

def _as_upcoming_2026(league):
    """The synthetic league relabelled as 2026 with Week 6 NOT YET PLAYED — but its absurd stat rows
    left in the inputs, as if something upstream had written them early."""
    out = {n: f.copy() for n, f in league.items()}
    out["games"]["season"] = 2026
    out["talent"]["season"] = 2026
    wk6 = out["games"]["week"] == 6
    out["games"].loc[wk6, ["home_points", "away_points"]] = np.nan
    return out


def test_an_upcoming_2026_week_is_built_from_earlier_weeks_only(league):
    """STAGED BREAK (cfdb-wtc-R-2450): `inputs_before` changed to `week <= week` lets the target week's
    rows feed its own features, and THIS test goes RED — the live path, not only the backtest."""
    upcoming = _as_upcoming_2026(league)
    built = of.build(upcoming, seasons=[2026], completed=False).set_index("id")
    assert set(built.index) == {1015, 1016, 1017}                     # only the unplayed Week 6
    for game_id in built.index:
        per_team, game = _independent_recompute(upcoming, game_id)
        for side, team in (("home", game["home_team"]), ("away", game["away_team"])):
            for name in per_team.columns:
                assert built.loc[game_id, f"{side}_{name}"] == pytest.approx(per_team.loc[team, name])
        assert built.loc[game_id, "home_adjusted_epa"] < 1.0, "Week 6's own rows reached Week 6's features"


def test_scoring_refuses_a_null_feature_and_a_played_game(league):
    from modeling import weekly
    frame = of.build(league, seasons=[2025])
    frame = frame.assign(neutral_site=False, week=6, home_points=np.nan)
    bad = frame.copy()
    bad.loc[bad.index[0], "home_adjusted_epa"] = np.nan
    with pytest.raises(weekly.NullFeatureError, match="home_adjusted_epa"):
        weekly.refuse_nulls(bad)
    weekly.refuse_nulls(frame)
    with pytest.raises(ValueError, match="unplayed"):
        weekly.score_week(frame, frame.assign(home_points=24.0))


def test_the_live_command_refuses_a_week_below_the_floor():
    from modeling import weekly
    with pytest.raises(SystemExit, match="below the Week 5 floor"):
        weekly.main(["--season", "2026", "--week", "4"])


def test_the_live_output_name_is_never_a_file_the_loader_ingests():
    from modeling import weekly
    from src.load_predictions import EXPECTED_FILES
    assert weekly.output_name(2026, 5) == "cfdb_wtc_c1_own_2026_week05.csv"
    assert weekly.output_name(2026, 5) not in EXPECTED_FILES
