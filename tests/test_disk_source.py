"""The disk reader mirrors warehouse staging (cfdb-wtc-R-2482).

The fixture under `tests/fixtures/disk_source/` is SYNTHETIC — invented teams and numbers, shaped
like CFBD's raw payloads — so this runs in CI without the warehouse or any licensed data.

The live parity test compares the reader to the warehouse's own staging on 2024–2025, row for row.
It needs the warehouse tunnel and fetched raw files, so it is opt-in: CFDB_PARITY_LIVE=1.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modeling import disk_source, parity

FIXTURE = Path(__file__).parent / "fixtures" / "disk_source"


def test_advanced_mirrors_staging_latest_file_wins_and_failed_fetches_are_ignored():
    """STAGED BREAK (cfdb-wtc-R-2482): negating `offense_ppa` in `disk_source.advanced` turns THIS
    test RED here and `test_disk_source_matches_warehouse_staging` RED against the warehouse."""
    adv = disk_source.advanced(FIXTURE).set_index("team")
    assert len(adv) == 2                                                   # the 404 file contributes nothing
    assert adv.loc["Home U", "offense_ppa"] == pytest.approx(0.30)         # the Feb file beats the Jan file
    assert np.isnan(adv.loc["Away St", "offense_ppa"])                     # "abc" → NULL, as safe_numeric does
    assert adv.loc["Away St", "offense_success_rate"] == pytest.approx(0.5)  # numeric text → number
    assert adv.loc["Home U", "offense_standard_downs_ppa"] == pytest.approx(0.2)
    assert adv.loc["Home U", "defense_passing_plays_total_ppa"] == pytest.approx(6.5)
    assert adv.loc["Home U", "game_id"] == 1 and adv.loc["Home U", "season_type"] == "regular"


def test_staging_column_names_are_reproduced():
    adv = disk_source.advanced(FIXTURE)
    for col in ("offense_total_ppa", "offense_line_yards_total", "defense_rushing_plays_explosiveness",
                "offense_passing_downs_success_rate", "offense_open_field_yards"):
        assert col in adv.columns


def test_drives_and_talent_and_havoc():
    drives = disk_source.drives(FIXTURE)
    assert len(drives) == 1 and drives.loc[0, "drive_result"] == "FG"      # latest file wins per drive id
    talent = disk_source.talent(FIXTURE).set_index("team")
    assert talent.loc["Home U", "talent"] == pytest.approx(812.5)
    havoc = disk_source.havoc(FIXTURE)
    assert havoc.loc[0, "defense_front_seven_havoc_events"] == 8


def test_load_inputs_has_own_features_columns():
    games = pd.DataFrame({"game_id": [1], "season": [2024], "week": [5], "start_date": ["2024-09-28T19:00:00Z"],
                          "home_team": ["Home U"], "away_team": ["Away St"]})
    frames = disk_source.load_inputs(games, [2024], raw=FIXTURE)
    assert set(frames) == {"games", "advanced", "havoc", "drives", "talent"}
    assert frames["advanced"].columns[:3].tolist() == ["game_id", "team", "opponent"]
    assert frames["drives"]["start_yards_to_goal"].dtype.kind in "if"


def test_parity_reports_every_difference_and_loosens_nothing():
    a = {"advanced": pd.DataFrame({"game_id": [1, 2], "team": ["A", "B"], "x": [0.1, 0.2]}),
         "havoc": pd.DataFrame({"game_id": [1], "team": ["A"], "y": [3]}),
         "drives": pd.DataFrame({"drive_id": ["1"], "z": ["TD"]}),
         "talent": pd.DataFrame({"season": [2024], "team": ["A"], "talent": [1.0]})}
    b = {k: v.copy() for k, v in a.items()}
    assert parity.compare(a, b) == []
    b["advanced"].loc[1, "x"] = 0.2 + 1e-8                                 # beyond 1e-9: a finding
    b["drives"] = pd.DataFrame({"drive_id": ["1", "2"], "z": ["TD", "FG"]})
    found = {(f["frame"], f["column"], f["what"]) for f in parity.compare(a, b)}
    assert ("advanced", "x", "values differ") in found
    assert ("drives", "(row set)", "rows only in the warehouse") in found


@pytest.mark.skipif(os.environ.get("CFDB_PARITY_LIVE") != "1",
                    reason="live parity needs the warehouse tunnel: set CFDB_PARITY_LIVE=1")
def test_disk_source_matches_warehouse_staging(tmp_path):
    """The reader against the staging SQL, on THE SAME BYTES: the warehouse's own stored raw JSON is
    written out, read by `disk_source`, and compared with `staging.*` for 2024–2025, row for row.

    Same bytes on purpose. A fresh API fetch compared with the warehouse also measures CFBD revising
    its numbers between the two fetches (R-2482 found PPA revised on ~79% of 2024–25 team-games), and
    a reader test must not pass or fail on the calendar."""
    import json
    import psycopg2
    from modeling import own_features as of
    conn = psycopg2.connect(host=os.environ["CFDB_WAREHOUSE_HOST"], port=int(os.environ["CFDB_WAREHOUSE_PORT"]),
                            user=os.environ.get("PG_USER", "cfdb"), password=os.environ.get("PG_PASSWORD", "cfdb"),
                            dbname=os.environ.get("PG_DB", "cfdb"), options="-c default_transaction_read_only=on")
    cur = conn.cursor()
    for table, key in (("raw_stats_game_advanced", "stats_game_advanced"), ("raw_stats_game_havoc", "stats_game_havoc"),
                       ("raw_drives", "drives"), ("raw_talent", "talent")):
        cur.execute(f"select filename, status_code, content from raw.{table}")
        folder = tmp_path / key
        folder.mkdir()
        for filename, status, content in cur.fetchall():
            (folder / filename).write_text(json.dumps({"status_code": status, "data": content.get("data")}))
    warehouse = of.load_inputs(conn, seasons=(2024, 2025))
    conn.close()
    disk = disk_source.load_inputs(warehouse["games"], (2024, 2025), raw=tmp_path)
    assert all(n > 0 for n in parity.matched(disk, warehouse).values())
    findings = parity.compare(disk, warehouse)
    assert findings == [], "\n".join(f"{f['frame']}.{f['column']}: {f['rows']} rows — {f['what']}" for f in findings)
