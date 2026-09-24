"""Hold the disk reader to the warehouse's staging, row for row and column for column (cfdb-wtc-R-2482).

    compare(disk_frames, warehouse_frames) → one finding per (frame, column) that differs

Exact on keys, integers and text; within 1e-9 on floats; two NULLs are equal. Every difference is
reported with its row count and examples — the tolerance is never loosened to make a column pass.
"""
from typing import Dict, List

import pandas as pd

KEYS = {"advanced": ["game_id", "team"], "havoc": ["game_id", "team"],
        "drives": ["drive_id"], "talent": ["season", "team"]}
FLOAT_TOLERANCE = 1e-9


def _differs(a: pd.Series, b: pd.Series) -> pd.Series:
    both_null = a.isna() & b.isna()
    if pd.api.types.is_float_dtype(a) or pd.api.types.is_float_dtype(b):
        a_, b_ = pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")
        close = (a_ - b_).abs() <= FLOAT_TOLERANCE
        return ~(both_null | close.fillna(False))
    return ~(both_null | (a == b).fillna(False))


def compare(disk: Dict[str, pd.DataFrame], warehouse: Dict[str, pd.DataFrame]) -> List[dict]:
    findings = []
    for name, key in KEYS.items():
        d, w = disk[name], warehouse[name]
        merged = d.merge(w, on=key, how="outer", suffixes=("_disk", "_wh"), indicator=True)
        for side, label in (("left_only", "rows only on disk"), ("right_only", "rows only in the warehouse")):
            n = int((merged["_merge"] == side).sum())
            if n:
                findings.append({"frame": name, "column": "(row set)", "rows": n, "what": label,
                                 "examples": merged.loc[merged["_merge"] == side, key].head(3).to_dict("records")})
        both = merged[merged["_merge"] == "both"]
        for col in [c for c in d.columns if c not in key]:
            if col not in w.columns:
                findings.append({"frame": name, "column": col, "rows": len(both), "what": "not in the warehouse frame"})
                continue
            bad = _differs(both[f"{col}_disk"], both[f"{col}_wh"])
            if bad.any():
                ex = both.loc[bad, key + [f"{col}_disk", f"{col}_wh"]].head(3)
                findings.append({"frame": name, "column": col, "rows": int(bad.sum()), "what": "values differ",
                                 "examples": ex.to_dict("records")})
        dtype_diff = {c: (str(d[c].dtype), str(w[c].dtype)) for c in d.columns
                      if c in w.columns and str(d[c].dtype) != str(w[c].dtype)}
        if dtype_diff:
            findings.append({"frame": name, "column": "(dtypes)", "rows": 0, "what": f"dtype differs: {dtype_diff}"})
    return findings


def matched(disk: Dict[str, pd.DataFrame], warehouse: Dict[str, pd.DataFrame]) -> Dict[str, int]:
    """Rows matched by key per frame — the denominator every finding is read against."""
    return {name: int(len(disk[name].merge(warehouse[name], on=key))) for name, key in KEYS.items()}
