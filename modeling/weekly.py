"""Score a week from our own data — no pack file needed (cfdb-wtc-R-2450, tuned in R-2490).

    frame_for        own features + outcomes + the market line, one row per target game
    backtest         the exact live procedure run on a past season, week by week
    score_week       fit on completed seasons, predict one upcoming week, refuse any null
    main             python -m modeling.weekly --season 2026 --week 5

WHERE THE DATA COMES FROM (R-2490). Every feature is read from THIS checkout's `data/raw/`
(`modeling.disk_source`), so history and the week being predicted share one version of CFBD's PPA:
CFBD revised PPA after the warehouse fetched 2024–25 (R-2482), and the live pipeline never refetched
2026 Week 1, so the warehouse holds its pre-revision PPA too (R-2495). `main` therefore refreshes the
season it predicts to disk first (13 calls). `stg_games` (the schedule, Elo, results) and the betting
lines — neither of them PPA — are read from the warehouse, read-only.

THE TUNED CONFIGURATION (R-2490, walk-forward folds 2018–2024; each step kept only if its gain beat
its fold standard error). Margin and total are fitted separately, because they wanted different things:

    margin   ALPHA 0.5 · drop field position and points per opportunity · ridge α 300 · all seasons
    total    ALPHA 0.5 + last season carried forward (k = 1) · drop explosiveness · ridge α 10 ·
             the last 3 seasons

THE MARKET LINE. Per game: each provider's LATEST snapshot in `marts.fct_betting_line`, then the
median across providers — CFBD's closing line for a completed game (r 0.9996 against the pack's
spread), every snapshot pre-kickoff for an upcoming one. Spread = the market's expected (away − home)
margin, the pack's sign.
"""
from typing import Dict, Iterable, List

import pandas as pd

from modeling import own_features as of
from modeling.evaluate import evaluate
from modeling.tune import check_fold, drop_family_columns

BASE_BUILD = {"division_prior": True, "ppo_without_try": True}
MARGIN = {"build": {"alpha": 0.5}, "drop": ("field_position", "points_per_opportunity"),
          "ridge_alpha": 300.0, "window": None}
TOTAL = {"build": {"alpha": 0.5, "carry_weight": 1.0}, "drop": ("explosiveness",),
         "ridge_alpha": 10.0, "window": 3}
FIRST_SEASON = 2016

LINES_SQL = """
with latest as (
  select distinct on (game_id, provider_key) game_id, spread, over_under
  from marts.fct_betting_line
  where season = any(%(s)s) and season_type = 'regular'
  order by game_id, provider_key, snapshot_ts desc)
select game_id, percentile_cont(0.5) within group (order by spread) as spread,
       percentile_cont(0.5) within group (order by over_under) as market_total,
       count(*) as providers
from latest group by game_id
"""


class NullFeatureError(ValueError):
    """A feature the model reads is empty. Ridge would raise; a tree would not. We refuse either way."""


def market_lines(conn, seasons: Iterable[int]) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(LINES_SQL, {"s": [int(s) for s in seasons]})
    out = pd.DataFrame(cur.fetchall(), columns=["id", "spread", "market_total", "providers"])
    return out.astype({"id": int, "spread": float, "market_total": float, "providers": int})


def _meta(games: pd.DataFrame) -> pd.DataFrame:
    g = games.rename(columns={"game_id": "id", "is_neutral_site": "neutral_site"})
    g = g.assign(season_type="regular", neutral_site=g["neutral_site"].fillna(False).astype(bool),
                 margin=g["away_points"] - g["home_points"])
    return g[["id", "season", "season_type", "week", "start_date", "neutral_site", "home_team", "away_team",
              "home_conference", "away_conference", "home_points", "away_points", "margin"]]


def frame_for(inputs: Dict[str, pd.DataFrame], seasons: Iterable[int], lines: pd.DataFrame, spec: dict,
              completed: bool = True) -> pd.DataFrame:
    """Own features built with `spec`, joined to the games spine and the market line."""
    feats = of.build(inputs, seasons=seasons, completed=completed, **BASE_BUILD, **spec["build"])
    market = lines[["id", "spread", "market_total"]]
    frame = _meta(inputs["games"]).merge(feats, on="id").merge(market, on="id", how="left")
    frame = drop_family_columns(frame, spec["drop"])
    return frame.sort_values(["season", "week", "id"]).reset_index(drop=True)


def feature_columns(frame: pd.DataFrame) -> List[str]:
    return [c for c in frame.columns if c.startswith(("home_", "away_"))
            and c not in ("home_team", "away_team", "home_points", "away_points", "home_conference",
                          "away_conference")]


def refuse_nulls(frame: pd.DataFrame) -> None:
    cols = feature_columns(frame) + ["neutral_site", "week"]
    empty = frame[cols].isna().sum()
    empty = empty[empty > 0]
    if len(empty):
        raise NullFeatureError(f"refusing to score: {len(empty)} feature column(s) have nulls: {empty.to_dict()}")


def training_seasons(season: int, spec: dict) -> List[int]:
    seasons = list(range(FIRST_SEASON, season))
    return seasons[-spec["window"]:] if spec["window"] else seasons


def _fit(train: pd.DataFrame, score: pd.DataFrame, spec: dict):
    from modeling.models import predict   # lazily: scikit-learn is a modeling extra, not in CI
    return predict(train, score, "paired", "wide", "ridge", "direct", ridge_alpha=spec["ridge_alpha"])


def _usable(train: pd.DataFrame) -> pd.DataFrame:
    """Training games whose teams had no earlier game that season carry no features (34 games of
    2020); they are left out of training, as in the walk-forward. A scored week never drops a game."""
    return train[train[feature_columns(train)].notna().all(axis=1)]


def backtest(margin_frame: pd.DataFrame, total_frame: pd.DataFrame, season: int, weeks: Iterable[int],
             exam_open: bool = False) -> pd.DataFrame:
    """Fit once on the seasons before `season`, score `weeks` one at a time — the live procedure."""
    fits = {}
    for name, frame, spec in (("margin", margin_frame, MARGIN), ("total", total_frame, TOTAL)):
        seasons = training_seasons(season, spec)
        check_fold(seasons, season, exam_open=exam_open)
        fits[name] = (_usable(frame[frame["season"].isin(seasons)]), frame[frame["season"] == season], spec)
    rows = []
    for week in weeks:
        parts = {}
        for name, (train, target, spec) in fits.items():
            games = target[target["week"] == week]
            refuse_nulls(games)
            margin, total = _fit(train, games, spec)
            parts[name] = games.assign(pred_margin=margin, pred_total=total).set_index("id")
        if len(parts["margin"]):
            out = parts["margin"].copy()
            out["pred_total"] = parts["total"].loc[out.index, "pred_total"]
            rows.append(out.reset_index())
    return pd.concat(rows, ignore_index=True)


def score_week(margin_train: pd.DataFrame, total_train: pd.DataFrame, margin_week: pd.DataFrame,
               total_week: pd.DataFrame) -> pd.DataFrame:
    """Predictions for one upcoming week; refuses if any game is played or any feature is empty."""
    if margin_week["home_points"].notna().any():
        raise ValueError("score_week is for unplayed games; this frame has results in it")
    for frame in (margin_week, total_week):
        refuse_nulls(frame)
    margin, _ = _fit(_usable(margin_train), margin_week, MARGIN)
    _, total = _fit(_usable(total_train), total_week, TOTAL)
    out = margin_week.assign(pred_margin=margin).set_index("id")
    out["pred_total"] = pd.Series(total, index=total_week["id"].to_numpy()).loc[out.index]
    return out.reset_index()


def summary(scored: pd.DataFrame, by_week: bool = True) -> pd.DataFrame:
    """Margin MAE, straight-up and ATS beside the market; total MAE beside the market's total."""
    def one(f):
        e = evaluate(f, pred_margin=f["pred_margin"], pred_total=f["pred_total"])
        has_total = f["market_total"].notna()
        actual_total = f["home_points"] + f["away_points"]
        return pd.Series({
            "games": len(f),
            "margin_mae": e.loc["margin MAE (points)", "model"],
            "market_margin_mae": e.loc["margin MAE (points)", "market"],
            "total_mae": e.loc["total MAE (points)", "model"],
            "market_total_mae": float((actual_total[has_total] - f.loc[has_total, "market_total"]).abs().mean()),
            "straight_up": e.loc["straight-up %", "model"],
            "market_straight_up": e.loc["straight-up %", "market"],
            "ats": e.loc["ATS %", "model"], "ats_games": e.loc["ATS %", "games"],
        })
    parts = [one(f).rename(w) for w, f in scored.groupby("week")] if by_week else []
    return pd.DataFrame(parts + [one(scored).rename("all")])


def output_name(season: int, week: int) -> str:
    return f"cfdb_wtc_c1_own_{season}_week{week:02d}.csv"


def write_week(scored: pd.DataFrame, season: int, week: int):
    """The 42-column export for an upcoming week; outcome columns blank. Never loaded anywhere."""
    from modeling.export import export_frame, write_export
    frame = export_frame(scored, scored["pred_margin"], scored["pred_total"], split="live",
                         model_name="cfdb_wtc_c1_own_features_tuned", model_family="linear_regression",
                         target="margin_and_total")
    return write_export(frame, output_name(season, week))


def main(argv=None) -> int:
    """python -m modeling.weekly --season 2026 --week 5   (warehouse read-only; history from disk)."""
    import argparse
    import os

    import psycopg2

    from modeling import disk_source

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--no-refresh", action="store_true",
                        help="skip refreshing the season being predicted to disk (tests and rehearsals only)")
    args = parser.parse_args(argv)
    if args.week < of.FIRST_WEEK:
        raise SystemExit(f"refusing: Week {args.week} is below the Week {of.FIRST_WEEK} floor "
                         "(in-season features are too thin before it — spec §4)")

    if not args.no_refresh:
        from modeling import fetch_history
        counts = fetch_history.run(fetch_history.current_season_plan(args.season), force=True)
        if counts["failed"]:
            raise SystemExit(f"refusing: the refresh of {args.season} to disk had failures: {counts}")

    conn = psycopg2.connect(host=os.environ["CFDB_WAREHOUSE_HOST"], port=int(os.environ["CFDB_WAREHOUSE_PORT"]),
                            user=os.environ.get("PG_USER", "cfdb"), password=os.environ.get("PG_PASSWORD", "cfdb"),
                            dbname=os.environ.get("PG_DB", "cfdb"), options="-c default_transaction_read_only=on")
    history_seasons = list(range(FIRST_SEASON, args.season))
    cur = conn.cursor()
    cur.execute(of.QUERIES["games"], {"s": history_seasons + [args.season]})
    games = of.coerce({"games": pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])})["games"]
    lines = market_lines(conn, [args.season])
    conn.close()

    inputs = disk_source.load_inputs(games, history_seasons + [args.season])
    m_frame = frame_for(inputs, history_seasons, lines, MARGIN)
    t_frame = frame_for(inputs, training_seasons(args.season, TOTAL), lines, TOTAL)
    m_week = frame_for(inputs, [args.season], lines, MARGIN, completed=False)
    t_week = frame_for(inputs, [args.season], lines, TOTAL, completed=False)
    m_week, t_week = m_week[m_week["week"] == args.week], t_week[t_week["week"] == args.week]
    if m_week.empty:
        raise SystemExit(f"refusing: no unplayed FBS-vs-FBS games found for {args.season} Week {args.week}")
    scored = score_week(m_frame, t_frame, m_week, t_week)
    path = write_week(scored, args.season, args.week)
    spreads, totals = int(m_week["spread"].notna().sum()), int(m_week["market_total"].notna().sum())
    print(f"wrote {path.name}: {len(m_week)} games · margin fitted on {history_seasons[0]}–{history_seasons[-1]} · "
          f"total on {training_seasons(args.season, TOTAL)} · market spread on {spreads} · total on {totals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
