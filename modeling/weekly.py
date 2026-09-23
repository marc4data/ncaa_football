"""Score a week from our own data — no pack file needed (cfdb-wtc-R-2450).

Everything here reads the warehouse through `own_features`, so a 2026 week can be predicted the
moment its earlier weeks are in `stg_games`, without CFBD's weekly Patreon file.

    training_frame   own features + outcomes for completed seasons, meta taken from the games spine
    market_lines     the market's spread and total per game, from `marts.fct_betting_line`
    backtest         the exact live procedure run one season back, week by week
    score_week       fit on completed seasons, predict one upcoming week, refuse any null

THE MARKET LINE. Per game: each provider's LATEST snapshot, then the median across providers.
For completed seasons the warehouse holds one snapshot per provider, taken after the game — CFBD's
closing line, and it matches the pack's `spread` at r 0.9996 (same sign, 98.8% within a point) on
the 1,125 games of 2024–25. For an upcoming game every snapshot is pre-kickoff by construction.
Sign convention is the pack's: spread = the market's expected (away − home) margin.

THE CONFIGURATION is R-2440's best: the division prior and points per opportunity without the try.
The SOS columns stay out — they added nothing on the model.
"""
from typing import Dict, Iterable, List

import pandas as pd

from modeling import own_features as of
from modeling.evaluate import evaluate

CONFIG = {"division_prior": True, "ppo_without_try": True}
MODEL = ("paired", "wide", "ridge", "direct")      # C1

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


def frame_for(inputs: Dict[str, pd.DataFrame], seasons: Iterable[int], lines: pd.DataFrame,
              completed: bool = True) -> pd.DataFrame:
    """Own features joined to the games spine and the market line, one row per target game."""
    feats = of.build(inputs, seasons=seasons, completed=completed, **CONFIG)
    market = lines[["id", "spread", "market_total"]]
    frame = _meta(inputs["games"]).merge(feats, on="id").merge(market, on="id", how="left")
    return frame.sort_values(["season", "week", "id"]).reset_index(drop=True)


def feature_columns(frame: pd.DataFrame) -> List[str]:
    return [c for c in frame.columns if c.startswith(("home_", "away_"))
            and c not in ("home_team", "away_team", "home_points", "away_points")]


def refuse_nulls(frame: pd.DataFrame) -> None:
    cols = feature_columns(frame) + ["neutral_site", "week"]
    empty = frame[cols].isna().sum()
    empty = empty[empty > 0]
    if len(empty):
        raise NullFeatureError(f"refusing to score: {len(empty)} feature column(s) have nulls: {empty.to_dict()}")


def backtest(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Fit once on `train`, score `test` one week at a time — exactly what the live procedure does."""
    from modeling.models import predict   # lazily: scikit-learn is a modeling extra, not in CI
    rows = []
    for week, games in test.groupby("week"):
        refuse_nulls(games)
        margin, total = predict(train, games, *MODEL)
        rows.append(games.assign(pred_margin=margin, pred_total=total))
    return pd.concat(rows)


def score_week(train: pd.DataFrame, week_games: pd.DataFrame) -> pd.DataFrame:
    """Predictions for one upcoming week; refuses if any feature is empty."""
    if week_games["home_points"].notna().any():
        raise ValueError("score_week is for unplayed games; this frame has results in it")
    refuse_nulls(train)
    refuse_nulls(week_games)
    from modeling.models import predict
    margin, total = predict(train, week_games, *MODEL)
    return week_games.assign(pred_margin=margin, pred_total=total)


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
                         model_name="cfdb_wtc_c1_own_features", model_family="linear_regression",
                         target="margin_and_total")
    return write_export(frame, output_name(season, week))


def main(argv=None) -> int:
    """python -m modeling.weekly --season 2026 --week 5   (reads the warehouse, read-only)."""
    import argparse
    import os

    import psycopg2

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args(argv)
    if args.week < of.FIRST_WEEK:
        raise SystemExit(f"refusing: Week {args.week} is below the Week {of.FIRST_WEEK} floor "
                         "(in-season features are too thin before it — spec §4)")

    conn = psycopg2.connect(host=os.environ["CFDB_WAREHOUSE_HOST"], port=int(os.environ["CFDB_WAREHOUSE_PORT"]),
                            user=os.environ.get("PG_USER", "cfdb"), password=os.environ.get("PG_PASSWORD", "cfdb"),
                            dbname=os.environ.get("PG_DB", "cfdb"), options="-c default_transaction_read_only=on")
    fit_seasons = list(range(2024, args.season))
    inputs = of.load_inputs(conn, seasons=fit_seasons + [args.season])
    lines = market_lines(conn, fit_seasons + [args.season])
    conn.close()

    train = frame_for(inputs, fit_seasons, lines)
    upcoming = frame_for(inputs, [args.season], lines, completed=False)
    week = upcoming[upcoming["week"] == args.week]
    if week.empty:
        raise SystemExit(f"refusing: no unplayed FBS-vs-FBS games found for {args.season} Week {args.week}")
    path = write_week(score_week(train, week), args.season, args.week)
    spreads, totals = int(week["spread"].notna().sum()), int(week["market_total"].notna().sum())
    print(f"wrote {path.name}: {len(week)} games · fitted on {fit_seasons} ({len(train)} games) · "
          f"market spread on {spreads} · market total on {totals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
