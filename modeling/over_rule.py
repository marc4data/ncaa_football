"""Marc's "both teams over" rule, tested walk-forward (cfdb edges work, pre-registered 2026-09-30).

    python -m modeling.over_rule            # the six folds, 2018–2024 without 2020
    python -m modeling.over_rule --exam     # 2025, once, after the folds are reported

THE RULE. The market's spread S (away − home) and total T imply each team's points: home (T − S)/2,
away (T + S)/2. A model that predicts BOTH teams above their implied points says the game goes over.
The CUSHION is the smaller of the two gaps — the weaker side is what decides whether the over lands —
so "fires at cushion > c" is the rule with a margin of safety c. The mirror (both below) says under.

GRADING. Combined points against T: over is a hit, under a miss, exactly T a push, which counts in
neither. Break-even at −110 is 52.38%. The pre-registration, written before any of this ran, is
`claude_work/renders/over-rule-preregistration-2026-09-30.md`; the reading of the result is fixed there.

TWO MODELS, both walk-forward: ours (`modeling.weekly.backtest`, the tuned R-2490 procedure, fitted
once per season on the seasons before it) and the pack's C2 (boosted trees on team points, R-2420,
trained on pack rows from earlier seasons). The market is CFBD's historical lines on disk
(`disk_source.lines`) for every season, so every fold is graded against one source.
"""
import argparse
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from modeling.evaluate import ATS_BREAK_EVEN, rate_interval
from modeling.tune import check_fold

FOLDS = (2018, 2019, 2021, 2022, 2023, 2024)
EXAM = 2025
THRESHOLDS = (0.0, 1.0, 2.0, 3.0)
FIRST_WEEK = 5


def implied_points(spread: pd.Series, total: pd.Series):
    """(home, away) points the market implies. `spread` is away − home: −7 means home by 7."""
    return (total - spread) / 2, (total + spread) / 2


def apply_rule(frame: pd.DataFrame) -> pd.DataFrame:
    """Adds implied points, each side's gap, both cushions and the over/under result.

    Needs pred_home, pred_away, spread, market_total, home_points, away_points."""
    out = frame.copy()
    out["implied_home"], out["implied_away"] = implied_points(out["spread"], out["market_total"])
    out["gap_home"] = out["pred_home"] - out["implied_home"]
    out["gap_away"] = out["pred_away"] - out["implied_away"]
    out["over_cushion"] = out[["gap_home", "gap_away"]].min(axis=1, skipna=False)
    out["under_cushion"] = -out[["gap_home", "gap_away"]].max(axis=1, skipna=False)
    combined = out["home_points"] + out["away_points"]
    out["ou_result"] = np.where(out["market_total"].isna() | combined.isna(), None,
                                np.where(combined > out["market_total"], "over",
                                         np.where(combined < out["market_total"], "under", "push")))
    return out


def _record(results: pd.Series, hit: str) -> dict:
    hits, pushes = int((results == hit).sum()), int((results == "push").sum())
    misses = int(results.isin(["over", "under"]).sum()) - hits
    decided = hits + misses
    rate = hits / decided if decided else float("nan")
    low, high = rate_interval(rate, decided)
    return {"fires": len(results), "hits": hits, "misses": misses, "pushes": pushes,
            "hit_rate": rate, "range_low": low, "range_high": high}


def verdict(row: dict) -> str:
    """The reading fixed in the pre-registration."""
    if not row["hits"] + row["misses"] or row["hit_rate"] <= ATS_BREAK_EVEN:
        return "no edge"
    return "edge" if row["range_low"] > ATS_BREAK_EVEN else "promising, not proven"


def summarize(graded: pd.DataFrame, thresholds: Iterable[float] = THRESHOLDS) -> pd.DataFrame:
    """One row per (direction, threshold), plus the all-games over rate as context."""
    g = graded[graded["ou_result"].notna() & graded["over_cushion"].notna()]
    rows = [{"direction": "context: every graded game, over", "threshold": None, **_record(g["ou_result"], "over")}]
    for direction, cushion, hit in (("both over → over", "over_cushion", "over"),
                                    ("both under → under", "under_cushion", "under")):
        for t in thresholds:
            rows.append({"direction": direction, "threshold": t, **_record(g.loc[g[cushion] > t, "ou_result"], hit)})
    out = pd.DataFrame(rows)
    out["verdict"] = [verdict(r) if r["threshold"] is not None else "" for r in out.to_dict("records")]
    return out


# ---------------------------------------------------------------- the two models, walk-forward

def ours(conn, seasons: Iterable[int], market: pd.DataFrame, exam_open: bool = False) -> pd.DataFrame:
    """Our weekly procedure on each season, trained only on the seasons before it."""
    from modeling import disk_source, own_features as of, weekly

    seasons = sorted(seasons)
    history = list(range(weekly.FIRST_SEASON, max(seasons) + 1))
    cur = conn.cursor()
    cur.execute(of.QUERIES["games"], {"s": history})
    games = of.coerce({"games": pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])})["games"]
    inputs = disk_source.load_inputs(games, history)
    lines = market.rename(columns={"game_id": "id"})
    m_frame = weekly.frame_for(inputs, history, lines, weekly.MARGIN)
    t_frame = weekly.frame_for(inputs, history, lines, weekly.TOTAL)
    parts = []
    for season in seasons:
        weeks = sorted(w for w in m_frame.loc[m_frame["season"] == season, "week"].unique() if w >= FIRST_WEEK)
        scored = weekly.backtest(m_frame, t_frame, season, weeks, exam_open=exam_open)
        parts.append(scored)
    out = pd.concat(parts, ignore_index=True).rename(columns={"id": "game_id"})
    out["pred_home"] = (out["pred_total"] - out["pred_margin"]) / 2
    out["pred_away"] = (out["pred_total"] + out["pred_margin"]) / 2
    return out[["game_id", "season", "week", "home_team", "away_team", "home_points", "away_points",
                "pred_home", "pred_away"]].assign(model="ours")


def pack_c2(seasons: Iterable[int], exam_open: bool = False) -> pd.DataFrame:
    """The pack's C2 on each season, trained only on pack rows from earlier seasons."""
    from modeling.data import load_pack
    from modeling.models import predict

    pack = load_pack()
    pack = pack[(pack["season_type"] == "regular") & (pack["week"] >= FIRST_WEEK)]
    parts = []
    for season in sorted(seasons):
        train = pack[pack["season"] < season]
        check_fold(sorted(train["season"].unique()), season, exam_open=exam_open)
        score = pack[pack["season"] == season]
        margin, total = predict(train, score, "paired", "wide", "hgb", "team_points")
        parts.append(score.assign(pred_home=(total - margin) / 2, pred_away=(total + margin) / 2))
    out = pd.concat(parts, ignore_index=True).rename(columns={"id": "game_id"})
    return out[["game_id", "season", "week", "home_team", "away_team", "home_points", "away_points",
                "pred_home", "pred_away"]].assign(model="pack_c2")


def graded(predictions: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    """Predictions joined to the market's spread and total, then the rule applied."""
    m = market[["game_id", "spread", "market_total"]]
    return apply_rule(predictions.merge(m, on="game_id", how="left"))


def report(tables: Dict[str, pd.DataFrame]) -> str:
    lines: List[str] = []
    for name, table in tables.items():
        t = table.copy()
        for c in ("hit_rate", "range_low", "range_high"):
            t[c] = t[c].map(lambda v: "" if v != v else f"{v:.1%}")
        lines += [f"\n## {name}\n", t.to_markdown(index=False)]
    return "\n".join(lines)


def main(argv=None) -> int:
    import os

    import psycopg2

    from modeling import disk_source

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exam", action="store_true", help="score 2025 once (after the folds are reported)")
    args = parser.parse_args(argv)
    seasons = [EXAM] if args.exam else list(FOLDS)

    market = disk_source.lines()
    market = market[market["season_type"] == "regular"]
    conn = psycopg2.connect(host=os.environ["CFDB_WAREHOUSE_HOST"], port=int(os.environ["CFDB_WAREHOUSE_PORT"]),
                            user=os.environ.get("PG_USER", "cfdb"), password=os.environ.get("PG_PASSWORD", "cfdb"),
                            dbname=os.environ.get("PG_DB", "cfdb"), options="-c default_transaction_read_only=on")
    frames = {"ours": graded(ours(conn, seasons, market, exam_open=args.exam), market),
              "pack C2": graded(pack_c2(seasons, exam_open=args.exam), market)}
    conn.close()

    from modeling.export import OUTPUT_DIR
    tag = "exam_2025" if args.exam else "folds_2018_2024"
    tables = {}
    for name, frame in frames.items():
        frame.to_csv(OUTPUT_DIR / f"cfdb_over_rule_{name.replace(' ', '_').lower()}_{tag}.csv", index=False)
        ungraded = int(frame["ou_result"].isna().sum())
        tables[f"{name} — {tag} · {len(frame)} games scored, {ungraded} without a total"] = summarize(frame)
    print(report(tables))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
