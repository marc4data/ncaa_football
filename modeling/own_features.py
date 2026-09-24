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
MOV_CAP = 28.0     # a points rating counts no win as more than four scores
# Division offsets are meant to be unpenalised; a negligible penalty keeps the solve defined when a
# division has no rows on one side of the ball in a given week.
OFFSET_PENALTY = 1e-6
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
                       home_conference, away_conference,
                       home_classification, away_classification, home_points, away_points,
                       home_pregame_elo, away_pregame_elo
                from staging.stg_games where season = any(%(s)s) and season_type = 'regular'""",
    "advanced": """select game_id, team, opponent, {cols}
                   from staging.stg_game_team_advanced where season = any(%(s)s) and season_type = 'regular'""",
    "havoc": """select game_id, team, offense_total_plays, defense_total_plays,
                       offense_total_havoc_events, offense_front_seven_havoc_events, offense_db_havoc_events,
                       defense_total_havoc_events, defense_front_seven_havoc_events, defense_db_havoc_events
                from staging.stg_game_team_havoc where season = any(%(s)s) and season_type = 'regular'""",
    "drives": """select d.drive_id, d.game_id, d.offense, d.defense, d.start_yards_to_goal, d.end_yards_to_goal,
                        d.start_offense_score, d.end_offense_score, d.drive_result
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
    return coerce(out)


TEXT_COLUMNS = {"team", "opponent", "offense", "defense", "home_team", "away_team", "home_conference",
                "away_conference", "home_classification", "away_classification", "start_date",
                "is_neutral_site", "drive_result", "drive_id"}


def coerce(frames: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """One set of dtypes, whichever source the frames came from (warehouse or `disk_source`).

    psycopg2 hands numeric columns back as Decimal; everything that is not text becomes a number.
    """
    for frame in frames.values():
        for col in frame.columns.difference(list(TEXT_COLUMNS)):
            frame[col] = pd.to_numeric(frame[col])
    if "games" in frames:
        frames["games"]["start_date"] = pd.to_datetime(frames["games"]["start_date"], utc=True)
    return frames


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


def divisions(games: pd.DataFrame) -> Dict[str, str]:
    """team → 'fbs' / 'fcs' / 'ii' / 'iii', from the games spine. Blank reads as 'fcs'.

    ⚠️ Pass ONE season's games. Teams change division — Delaware and Missouri State moved FCS→FBS in
    2025, North Dakota State and Sacramento State in 2026 — so a map built across seasons would
    apply a later season's division to an earlier one (found and fixed in cfdb-wtc-R-2450).
    """
    out = {}
    for side in ("home", "away"):
        for team, cls in zip(games[f"{side}_team"], games[f"{side}_classification"]):
            out[team] = cls if isinstance(cls, str) and cls else out.get(team, "fcs")
    return out


def _ridge(X: np.ndarray, y: np.ndarray, penalty: np.ndarray) -> np.ndarray:
    """Closed-form ridge with a per-column penalty (0 = unpenalised)."""
    return np.linalg.solve(X.T @ X + np.diag(penalty), X.T @ y)


def _division_columns(teams_a, teams_b, division, classes, sign_b=1.0) -> np.ndarray:
    """One column per non-FBS division: +1 if side A is in it, `sign_b` if side B is."""
    cols = np.zeros((len(teams_a), len(classes)))
    for j, cls in enumerate(classes):
        cols[:, j] += np.array([division.get(t) == cls for t in teams_a], dtype=float)
        if sign_b:
            cols[:, j] += sign_b * np.array([division.get(t) == cls for t in teams_b], dtype=float)
    return cols


def adjust(rows: pd.DataFrame, value: str, games: pd.DataFrame, alpha: float = ALPHA,
           division: Optional[Dict[str, str]] = None, weights: Optional[pd.Series] = None) -> pd.DataFrame:
    """Opponent-adjusted offence and defence-allowed per team, by closed-form ridge.

    With `division`, each non-FBS division gets its own UNPENALISED offset for offence and for
    defence, so a thinly observed FCS team shrinks toward the FCS average, not the league's.
    The offsets are estimated from the same prior games as everything else (point-in-time holds).
    """
    rows = rows.dropna(subset=[value])
    if not len(rows):
        return pd.DataFrame(columns=["team", "offense", "allowed"])
    teams = sorted(set(rows["team"]) | set(rows["opponent"]))
    index = {t: i for i, t in enumerate(teams)}
    n, k = len(rows), len(teams)
    classes = sorted({division.get(t) for t in teams} - {"fbs", None}) if division else []
    c = len(classes)
    # y is centred on its mean (R-2430's formulation, kept so the no-prior build is unchanged).
    # columns: division offsets (offence c, defence c) · hfa · attack k · defence k
    X = np.zeros((n, 2 * c + 1 + 2 * k))
    if c:
        X[:, :c] = _division_columns(rows["team"], rows["opponent"], division, classes, sign_b=0.0)
        X[:, c:2 * c] = _division_columns(rows["opponent"], rows["team"], division, classes, sign_b=0.0)
    X[:, 2 * c] = _home_sign(rows, games)
    base = 1 + 2 * c
    X[np.arange(n), [base + index[t] for t in rows["team"]]] = 1.0
    X[np.arange(n), [base + k + index[t] for t in rows["opponent"]]] = 1.0
    y = rows[value].to_numpy(dtype=float)
    penalty = np.r_[np.full(2 * c, OFFSET_PENALTY), alpha * np.ones(1 + 2 * k)]
    if weights is None:
        mean = y.mean()
        beta = _ridge(X, y - mean, penalty)
    else:   # recency weighting (cfdb-wtc-R-2492): a weighted mean and a weighted ridge, nothing else changes
        w = weights.loc[rows.index].to_numpy(dtype=float)
        mean = float(np.average(y, weights=w))
        beta = np.linalg.solve(X.T @ (X * w[:, None]) + np.diag(penalty), X.T @ (w * (y - mean)))
    off_div = {cls: beta[j] for j, cls in enumerate(classes)}
    def_div = {cls: beta[c + j] for j, cls in enumerate(classes)}
    division = division or {}
    return pd.DataFrame({
        "team": teams,
        "offense": [mean + off_div.get(division.get(t), 0.0) + beta[base + i] for i, t in enumerate(teams)],
        "allowed": [mean + def_div.get(division.get(t), 0.0) + beta[base + k + i] for i, t in enumerate(teams)],
    })


def points_ratings(games: pd.DataFrame, alpha: float = ALPHA, division: Optional[Dict[str, str]] = None,
                   cap: float = MOV_CAP) -> pd.Series:
    """A results rating per team: capped margin of victory = rating[home] − rating[away] + hfa.

    The cap (±28) keeps a 70–0 over an FCS side from counting for more than a four-score win.
    Only completed games with at least one FBS or FCS team are used.
    """
    g = games.dropna(subset=["home_points", "away_points"])
    if division:
        keep = [division.get(h) in ("fbs", "fcs") or division.get(a) in ("fbs", "fcs")
                for h, a in zip(g["home_team"], g["away_team"])]
        g = g[keep]
    if not len(g):
        return pd.Series(dtype=float)
    teams = sorted(set(g["home_team"]) | set(g["away_team"]))
    index = {t: i for i, t in enumerate(teams)}
    n, k = len(g), len(teams)
    classes = sorted({division.get(t) for t in teams} - {"fbs", None}) if division else []
    c = len(classes)
    X = np.zeros((n, c + 1 + k))
    if c:
        X[:, :c] = _division_columns(g["home_team"], g["away_team"], division, classes, sign_b=-1.0)
    X[:, c] = np.where(g["is_neutral_site"].fillna(False).astype(bool), 0.0, 1.0)
    X[np.arange(n), [c + 1 + index[t] for t in g["home_team"]]] += 1.0
    X[np.arange(n), [c + 1 + index[t] for t in g["away_team"]]] -= 1.0
    y = np.clip(g["home_points"].to_numpy(float) - g["away_points"].to_numpy(float), -cap, cap)
    beta = _ridge(X, y, np.r_[np.full(c, OFFSET_PENALTY), alpha * np.ones(1 + k)])
    offset = {cls: beta[j] for j, cls in enumerate(classes)}
    division = division or {}
    return pd.Series({t: offset.get(division.get(t), 0.0) + beta[c + 1 + i] for i, t in enumerate(teams)})


def _havoc(havoc: pd.DataFrame) -> pd.DataFrame:
    t = havoc.groupby("team").sum(numeric_only=True)
    out = pd.DataFrame(index=t.index)
    for stem, col in HAVOC.items():
        out[f"{stem}_havoc_offense"] = t[f"offense_{col}_havoc_events"] / t["offense_total_plays"]
        out[f"{stem}_havoc_defense"] = t[f"defense_{col}_havoc_events"] / t["defense_total_plays"]
    return out


END_OF_PERIOD = ("END OF HALF", "END OF GAME", "END OF 4TH QUARTER", "END OF HALF TD", "END OF GAME TD")


def _drives(drives: pd.DataFrame, ppo_without_try: bool = False, fp_without_period_end: bool = False) -> pd.DataFrame:
    d = drives.copy()
    points = (d["end_offense_score"] - d["start_offense_score"]).clip(lower=0)
    if ppo_without_try:
        # 6 for a touchdown, 3 for a field goal: the try after a TD is not the drive's doing
        points = np.where(points >= 6, 6, np.where(points >= 3, 3, points))
    d["points"] = points
    d["opportunity"] = d[["start_yards_to_goal", "end_yards_to_goal"]].min(axis=1) <= 40
    opp = d[d["opportunity"]]
    fp = d[~d["drive_result"].isin(END_OF_PERIOD)] if fp_without_period_end and "drive_result" in d else d
    return pd.DataFrame({
        "points_per_opportunity_offense": opp.groupby("offense")["points"].mean(),
        "points_per_opportunity_defense": opp.groupby("defense")["points"].mean(),
        "avg_start_offense": fp.groupby("offense")["start_yards_to_goal"].mean(),
        "avg_start_defense": fp.groupby("defense")["start_yards_to_goal"].mean(),
    })


def team_features(prior: Dict[str, pd.DataFrame], alpha: float = ALPHA, division: Optional[Dict[str, str]] = None,
                  ppo_without_try: bool = False, fp_without_period_end: bool = False,
                  recency_halflife: Optional[float] = None, as_of_week: Optional[int] = None) -> pd.DataFrame:
    """Per team, every non-Elo, non-talent feature from the given prior games only.

    `recency_halflife` (weeks) weights each prior game in the opponent adjustment by
    0.5 ** ((as_of_week − game week) / halflife): a game that many weeks old counts half.
    Havoc, points per opportunity and field position stay plain season-to-date averages.
    """
    weights = None
    if recency_halflife and as_of_week is not None and len(prior["advanced"]):
        week_of = prior["advanced"]["game_id"].map(prior["games"].set_index("game_id")["week"])
        weights = 0.5 ** ((as_of_week - week_of) / recency_halflife)
    parts = []
    for stem, col in ADJUSTED.items():
        a = adjust(prior["advanced"], col, prior["games"], alpha, division, weights).set_index("team")
        parts.append(a.rename(columns={"offense": stem, "allowed": f"{stem}_allowed"}))
    parts += [_havoc(prior["havoc"]), _drives(prior["drives"], ppo_without_try, fp_without_period_end)]
    return pd.concat(parts, axis=1)


def ratings_at(prior: Dict[str, pd.DataFrame], alpha: float = ALPHA,
               division: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """Each team's two single-number ratings from these prior games: efficiency and points.

    efficiency = adjusted EPA for − adjusted EPA allowed (attack minus defence, per play).
    """
    a = adjust(prior["advanced"], ADJUSTED["adjusted_epa"], prior["games"], alpha, division).set_index("team")
    return pd.DataFrame({"efficiency": a["offense"] - a["allowed"],
                         "points": points_ratings(prior["games"], alpha, division)})


def carry_forward(current: pd.DataFrame, previous: pd.DataFrame, prior_advanced: pd.DataFrame,
                  weight: float) -> pd.DataFrame:
    """(n × current + weight × previous) / (n + weight), per team and column; n = games so far."""
    teams = current.index.union(previous.index)
    cur, prev = current.reindex(teams), previous.reindex(index=teams, columns=current.columns)
    n = prior_advanced.groupby("team").size().reindex(teams).fillna(0).to_numpy(float)[:, None]
    has_prev = prev.notna().to_numpy()
    has_cur = cur.notna().to_numpy()
    blended = np.where(has_cur & has_prev, (n * cur.to_numpy() + weight * prev.to_numpy()) / (n + weight),
                       np.where(has_cur, cur.to_numpy(), prev.to_numpy()))
    return pd.DataFrame(blended, index=teams, columns=current.columns)


# ---------------------------------------------------------------- the builder

def target_games(games: pd.DataFrame, completed: bool = True) -> pd.DataFrame:
    """The pack's population: FBS vs FBS, regular season, Week 5 on — completed, or (to score an
    upcoming week) not yet played."""
    played = games["home_points"].notna()
    return games[(games["week"] >= FIRST_WEEK) & (games["home_classification"] == "fbs")
                 & (games["away_classification"] == "fbs") & (played if completed else ~played)]


def schedule_strength(inputs: Dict[str, pd.DataFrame], season: int, week: int, team: str,
                      ratings_by_week: Dict[int, pd.DataFrame]) -> Dict[str, float]:
    """Mean pre-game rating of the opponents `team` has faced before `week`.

    Each opponent is rated AS IT STOOD AT THAT GAME'S KICKOFF — the ratings from games before the
    week that game was played — never as it stands today. An opponent with no rating yet counts 0
    (league average): early in the season, strength of schedule is honestly thin.
    """
    played = inputs_before(inputs, season, week)["games"]
    mine = played[(played["home_team"] == team) | (played["away_team"] == team)]
    eff, pts = [], []
    for g in mine.itertuples():
        opponent = g.away_team if g.home_team == team else g.home_team
        at_kickoff = ratings_by_week[g.week]
        eff.append(at_kickoff["efficiency"].get(opponent, 0.0) if len(at_kickoff) else 0.0)
        pts.append(at_kickoff["points"].get(opponent, 0.0) if len(at_kickoff) else 0.0)
    return {"sos_efficiency": float(np.nanmean(eff)) if eff else np.nan,
            "sos_results": float(np.nanmean(pts)) if pts else np.nan}


def build(inputs: Dict[str, pd.DataFrame], seasons: Iterable[int] = SEASONS, alpha: float = ALPHA,
          only_game_ids: Optional[set] = None, division_prior: bool = False, sos: bool = False,
          ppo_without_try: bool = False, fp_without_period_end: bool = False,
          completed: bool = True, carry_weight: float = 0.0,
          recency_halflife: Optional[float] = None) -> pd.DataFrame:
    """One row per target game: `id` plus home_/away_ features named as the pack names them.

    The switches are this round's changes, each off by default so R-2430's build is unchanged:
      division_prior        FBS / FCS / II / III priors in the adjustment (R-2441)
      sos                   points rating and the two cumulative SOS columns (R-2442) — ours, no pack twin
      ppo_without_try       points per opportunity without the try after a TD (R-2443)
      fp_without_period_end field position without end-of-half / end-of-game drives (R-2443)
      carry_weight          last season carried forward (R-2492): each per-team feature becomes
                            (n × this season + k × last season's end value) / (n + k), n = games
                            played so far this season, k = carry_weight — so it fades as games accrue
      recency_halflife      recent games weigh more in the opponent adjustment (R-2492)
    """
    games = inputs["games"]
    talent = inputs["talent"].set_index(["season", "team"])["talent"]
    rows = []
    for season in seasons:
        division = divisions(games[games["season"] == season]) if division_prior else None
        season_games = target_games(games[games["season"] == season], completed)
        if only_game_ids is not None:
            season_games = season_games[season_games["game_id"].isin(only_game_ids)]
        previous = None
        if carry_weight:
            last_ids = set(games.loc[(games["season"] == season - 1) & games["home_points"].notna(), "game_id"])
            if last_ids:
                last = {n: (f[f["game_id"].isin(last_ids)] if "game_id" in f.columns else f) for n, f in inputs.items()}
                last_division = divisions(games[games["season"] == season - 1]) if division_prior else None
                previous = team_features(last, alpha, last_division, ppo_without_try, fp_without_period_end)
        ratings_by_week = {}
        if sos:
            weeks = sorted(games.loc[games["season"] == season, "week"].unique())
            ratings_by_week = {w: ratings_at(inputs_before(inputs, season, w), alpha, division) for w in weeks}
        for week, week_games in season_games.groupby("week"):
            prior = inputs_before(inputs, season, week)
            per_team = team_features(prior, alpha, division, ppo_without_try, fp_without_period_end,
                                     recency_halflife, week)
            if previous is not None:
                per_team = carry_forward(per_team, previous, prior["advanced"], carry_weight)
            for g in week_games.itertuples():
                row = {"id": g.game_id}
                for side, team, elo in (("home", g.home_team, g.home_pregame_elo),
                                        ("away", g.away_team, g.away_pregame_elo)):
                    feats = per_team.loc[team] if team in per_team.index else pd.Series(dtype=float)
                    for name in per_team.columns:
                        row[f"{side}_{name}"] = feats.get(name, np.nan)
                    row[f"{side}_elo"] = elo
                    row[f"{side}_talent"] = float(talent.get((season, team), 0.0))
                    if sos:
                        row[f"{side}_points_rating"] = ratings_by_week[week]["points"].get(team, 0.0)
                        row.update({f"{side}_{k}": v for k, v in
                                    schedule_strength(inputs, season, week, team, ratings_by_week).items()})
                rows.append(row)
    return pd.DataFrame(rows)
