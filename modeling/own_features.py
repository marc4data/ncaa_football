"""Track 2: our own point-in-time features, built from the warehouse (cfdb-wtc-R-2430).

For every FBS-vs-FBS regular-season game from Week 5 on, each team's features are computed from
that season's EARLIER weeks only — games in a week before the target week AND starting before
that week's first kickoff. Nothing from the target week, or later, can reach an input.
`inputs_before()` is that rule, written once; the point-in-time test recomputes it independently.

Column names match the pack's one-for-one (`home_adjusted_epa`, `away_total_havoc_defense`, …),
so model C1 can read either source.

THE FAMILIES, and where each comes from:

    adjusted efficiency  `staging.stg_game_team_advanced`, per team-game, OPPONENT-ADJUSTED (below)
                         12 stats × offence and defence-allowed: EPA (all, rush, pass), success
                         (all, standard downs, passing downs), line / second-level / open-field
                         yards, explosiveness (all, rush, pass)
    havoc                `staging.stg_game_team_havoc` — season-to-date events / plays, unadjusted
    points per opp.      `staging.stg_drive` — points on drives that got inside the opponent's 40,
                         per such drive. ⚠️ An APPROXIMATION: CFBD counts an opportunity from a first
                         down inside the 40, which needs play-by-play; a drive's start and end yard
                         lines are what the drive table carries
    field position       `staging.stg_drive.start_yards_to_goal`, averaged (the pack's units: ~70)
    talent               `staging.stg_team_talent` — one number per team per season; 0 where
                         absent, which is the pack's own convention (its minimum is 0)
    Elo                  `staging.stg_games.home_pregame_elo` / `away_pregame_elo` — pre-game by name

OPPONENT ADJUSTMENT. For each target week, one ridge fit per stat over every prior team-game in the
season (FCS included — more games connect more of the league):

    stat(offence O vs defence D) = mean + attack[O] + defence[D] + hfa × (+1 home, −1 away, 0 neutral)

adjusted offence of T = mean + attack[T]; adjusted allowed of T = mean + defence[T]. The penalty
ALPHA = 4 shrinks each team toward average by roughly four games' worth, fixed before looking at the
pack: per-game efficiency noise is about twice the spread of true team strength, so the
noise-to-signal variance ratio is ~4. Solved in closed form with numpy (no scikit-learn, so CI runs it).

REJECTED: plain season-to-date averages (a 4-0 start against four weak teams reads as elite);
iterative SRS averaging (unstable at Week 5 with 3–4 games a team and FCS opponents with one
game each); CFBD's season-level advanced stats (leak the game being predicted, R-2412).
"""
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

ALPHA = 4.0
FIRST_WEEK = 5
SEASONS = (2024, 2025)

# pack stem → our per-game offence column in stg_game_team_advanced
ADJUSTED = {
    "adjusted_epa": "offense_ppa",
    "adjusted_rushing_epa": "offense_rushing_plays_ppa",
    "adjusted_passing_epa": "offense_passing_plays_ppa",
    "adjusted_success": "offense_success_rate",
    "adjusted_standard_down_success": "offense_standard_downs_success_rate",
    "adjusted_passing_down_success": "offense_passing_downs_success_rate",
    "adjusted_line_yards": "offense_line_yards",
    "adjusted_second_level_yards": "offense_second_level_yards",
    "adjusted_open_field_yards": "offense_open_field_yards",
    "adjusted_explosiveness": "offense_explosiveness",
    "adjusted_rush_explosiveness": "offense_rushing_plays_explosiveness",
    "adjusted_pass_explosiveness": "offense_passing_plays_explosiveness",
}
HAVOC = {"total": "total", "front_seven": "front_seven", "db": "db"}


# ---------------------------------------------------------------- loading (read-only)

QUERIES = {
    "games": """select game_id, season, week, start_date, is_neutral_site, home_team, away_team,
                       home_classification, away_classification, home_points, away_points,
                       home_pregame_elo, away_pregame_elo
                from staging.stg_games where season = any(%(s)s) and season_type = 'regular'""",
    "advanced": """select game_id, team, opponent, {cols}
                   from staging.stg_game_team_advanced where season = any(%(s)s) and season_type = 'regular'""",
    "havoc": """select game_id, team, offense_total_plays, defense_total_plays,
                       offense_total_havoc_events, offense_front_seven_havoc_events, offense_db_havoc_events,
                       defense_total_havoc_events, defense_front_seven_havoc_events, defense_db_havoc_events
                from staging.stg_game_team_havoc where season = any(%(s)s) and season_type = 'regular'""",
    "drives": """select d.game_id, d.offense, d.defense, d.start_yards_to_goal, d.end_yards_to_goal,
                        d.start_offense_score, d.end_offense_score
                 from staging.stg_drive d join staging.stg_games g on g.game_id = d.game_id
                 where g.season = any(%(s)s) and g.season_type = 'regular'""",
    "talent": "select season, team, talent from staging.stg_team_talent where season = any(%(s)s)",
}


def load_inputs(conn, seasons: Iterable[int] = SEASONS) -> Dict[str, pd.DataFrame]:
    """Every input frame, from a connection the caller opened read-only."""
    seasons = [int(s) for s in seasons]
    out = {}
    for name, sql in QUERIES.items():
        sql = sql.format(cols=", ".join(ADJUSTED.values()))
        cur = conn.cursor()
        cur.execute(sql, {"s": seasons})
        out[name] = pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
    # psycopg2 hands numeric columns back as Decimal; everything that is not text becomes a float.
    text = {"team", "opponent", "offense", "defense", "home_team", "away_team",
            "home_classification", "away_classification", "start_date", "is_neutral_site"}
    for frame in out.values():
        for col in frame.columns.difference(list(text)):
            frame[col] = pd.to_numeric(frame[col])
    out["games"]["start_date"] = pd.to_datetime(out["games"]["start_date"], utc=True)
    return out


# ---------------------------------------------------------------- the point-in-time rule

def inputs_before(inputs: Dict[str, pd.DataFrame], season: int, week: int) -> Dict[str, pd.DataFrame]:
    """Only games of `season` in an earlier week AND starting before `week`'s first kickoff."""
    games = inputs["games"]
    this_week = games[(games["season"] == season) & (games["week"] == week)]
    cutoff = this_week["start_date"].min()
    prior_ids = set(games.loc[(games["season"] == season) & (games["week"] < week)
                              & (games["start_date"] < cutoff), "game_id"])
    return {name: (frame[frame["game_id"].isin(prior_ids)] if "game_id" in frame.columns else frame)
            for name, frame in inputs.items()}


# ---------------------------------------------------------------- the families

def _home_sign(rows: pd.DataFrame, games: pd.DataFrame) -> np.ndarray:
    g = games.set_index("game_id")
    home = rows["game_id"].map(g["home_team"]).to_numpy()
    neutral = rows["game_id"].map(g["is_neutral_site"]).fillna(False).astype(bool).to_numpy()
    sign = np.where(rows["team"].to_numpy() == home, 1.0, -1.0)
    return np.where(neutral, 0.0, sign)


def adjust(rows: pd.DataFrame, value: str, games: pd.DataFrame, alpha: float = ALPHA) -> pd.DataFrame:
    """Opponent-adjusted offence and defence-allowed per team, by closed-form ridge."""
    rows = rows.dropna(subset=[value])
    teams = sorted(set(rows["team"]) | set(rows["opponent"]))
    if not len(rows):
        return pd.DataFrame(columns=["team", "offense", "allowed"])
    index = {t: i for i, t in enumerate(teams)}
    n, k = len(rows), len(teams)
    X = np.zeros((n, 2 * k + 1))
    X[np.arange(n), [index[t] for t in rows["team"]]] = 1.0
    X[np.arange(n), [k + index[t] for t in rows["opponent"]]] = 1.0
    X[:, -1] = _home_sign(rows, games)
    y = rows[value].to_numpy(dtype=float)
    mean = y.mean()
    beta = np.linalg.solve(X.T @ X + alpha * np.eye(X.shape[1]), X.T @ (y - mean))
    return pd.DataFrame({"team": teams, "offense": mean + beta[:k], "allowed": mean + beta[k:2 * k]})


def _havoc(havoc: pd.DataFrame) -> pd.DataFrame:
    t = havoc.groupby("team").sum(numeric_only=True)
    out = pd.DataFrame(index=t.index)
    for stem, col in HAVOC.items():
        out[f"{stem}_havoc_offense"] = t[f"offense_{col}_havoc_events"] / t["offense_total_plays"]
        out[f"{stem}_havoc_defense"] = t[f"defense_{col}_havoc_events"] / t["defense_total_plays"]
    return out


def _drives(drives: pd.DataFrame) -> pd.DataFrame:
    d = drives.copy()
    d["points"] = (d["end_offense_score"] - d["start_offense_score"]).clip(lower=0)
    d["opportunity"] = d[["start_yards_to_goal", "end_yards_to_goal"]].min(axis=1) <= 40
    opp = d[d["opportunity"]]
    out = pd.DataFrame({
        "points_per_opportunity_offense": opp.groupby("offense")["points"].mean(),
        "points_per_opportunity_defense": opp.groupby("defense")["points"].mean(),
        "avg_start_offense": d.groupby("offense")["start_yards_to_goal"].mean(),
        "avg_start_defense": d.groupby("defense")["start_yards_to_goal"].mean(),
    })
    return out


def team_features(prior: Dict[str, pd.DataFrame], alpha: float = ALPHA) -> pd.DataFrame:
    """Per team, every non-Elo, non-talent feature from the given prior games only."""
    parts = []
    for stem, col in ADJUSTED.items():
        a = adjust(prior["advanced"], col, prior["games"], alpha).set_index("team")
        parts.append(a.rename(columns={"offense": stem, "allowed": f"{stem}_allowed"}))
    parts += [_havoc(prior["havoc"]), _drives(prior["drives"])]
    return pd.concat(parts, axis=1)


# ---------------------------------------------------------------- the builder

def target_games(games: pd.DataFrame) -> pd.DataFrame:
    """The pack's population: FBS vs FBS, regular season, Week 5 on, completed."""
    return games[(games["week"] >= FIRST_WEEK) & (games["home_classification"] == "fbs")
                 & (games["away_classification"] == "fbs") & games["home_points"].notna()]


def build(inputs: Dict[str, pd.DataFrame], seasons: Iterable[int] = SEASONS, alpha: float = ALPHA,
          only_game_ids: Optional[set] = None) -> pd.DataFrame:
    """One row per target game: `id` plus home_/away_ features named as the pack names them."""
    games = inputs["games"]
    talent = inputs["talent"].set_index(["season", "team"])["talent"]
    rows = []
    for season in seasons:
        season_games = target_games(games[games["season"] == season])
        if only_game_ids is not None:
            season_games = season_games[season_games["game_id"].isin(only_game_ids)]
        for week, week_games in season_games.groupby("week"):
            per_team = team_features(inputs_before(inputs, season, week), alpha)
            for g in week_games.itertuples():
                row = {"id": g.game_id}
                for side, team, elo in (("home", g.home_team, g.home_pregame_elo),
                                        ("away", g.away_team, g.away_pregame_elo)):
                    feats = per_team.loc[team] if team in per_team.index else pd.Series(dtype=float)
                    for name in per_team.columns:
                        row[f"{side}_{name}"] = feats.get(name, np.nan)
                    row[f"{side}_elo"] = elo
                    row[f"{side}_talent"] = float(talent.get((season, team), 0.0))
                rows.append(row)
    return pd.DataFrame(rows)
