"""Tests for the raw loader's pure logic.

The database work needs Postgres, but row counting is what makes empty-response detection
possible, so it is worth pinning down on its own.
"""
from pathlib import Path

from src.load_raw_to_postgres import payload_row_count


def test_counts_a_list_payload():
    assert payload_row_count({"status_code": 200, "data": [1, 2, 3]}) == 3


def test_an_empty_list_is_zero_not_missing():
    """The failure that reports green: HTTP 200 carrying nothing."""
    assert payload_row_count({"status_code": 200, "data": []}) == 0


def test_a_dict_payload_counts_as_one():
    assert payload_row_count({"status_code": 200, "data": {"a": 1}}) == 1
    assert payload_row_count({"status_code": 200, "data": {}}) == 0


def test_error_payloads_count_as_zero():
    assert payload_row_count({"status_code": 401, "data": None}) == 0
    assert payload_row_count({"status_code": 400, "data": {"message": "Validation Failed"}}) == 1


def test_malformed_payloads_do_not_raise():
    assert payload_row_count(None) == 0
    assert payload_row_count("not a dict") == 0
    assert payload_row_count({"no_data_key": True}) == 0


# --- bootstrapping a genuinely empty warehouse --------------------------------------------

def test_the_schema_is_created_before_any_table_in_it():
    """Rebuilding from raw files into a NEW database is what this loader is for, and that
    path was broken.

    `CREATE TABLE raw.raw_<endpoint>` ran before the call that creates the `raw` schema. On
    any machine where the schema already existed — which was every machine, for months —
    that worked. On the first genuinely fresh warehouse, during the move to the droplet, all
    66 endpoints failed with `schema "raw" does not exist`.

    Asserted on order rather than behaviour because reproducing it needs a database with no
    schema, and the ordering IS the property.
    """
    import inspect
    from src import load_raw_to_postgres as loader
    body = inspect.getsource(loader.load_endpoint)
    ensure_at = body.index("_ensure_manifest_table(cur)")
    create_at = body.index("CREATE TABLE IF NOT EXISTS {table}")
    assert ensure_at < create_at, (
        "the raw schema must be created before the first table inside it, or a fresh "
        "warehouse cannot be loaded at all")


def test_an_explicitly_named_file_does_not_widen_the_packs_allow_list():
    """A269 (cfdb-main-R-4350). `--file` loads a named path; the directory scan stays as
    restrictive as it was.

    🚨 THE POINT OF `EXPECTED_FILES` IS THAT A STRAY CSV IS NEVER SILENTLY INGESTED. A second
    allow-list keyed by family would need editing every week, because the modeling session
    writes `..._week05.csv`, `..._week06.csv` and so on. Naming the file keeps the guarantee
    without a list that is always one week stale.
    """
    from src import load_predictions as lp
    assert hasattr(lp, "load_files")
    # the pack's list is untouched, and neither modeling file is in it
    assert len(lp.EXPECTED_FILES) == 7
    for name in lp.EXPECTED_FILES:
        assert "wtc" not in name
    assert lp.CANDIDATE_DIRS == (Path("model_outputs"),
                                 Path("cfdb_model_pack") / "model_outputs")


def test_naming_a_missing_file_loads_nothing_and_says_so(capsys):
    """A path that is not there must report that, not raise and not silently load zero."""
    from src import load_predictions as lp
    summary = lp.load_files([Path("/nonexistent/not_a_file.csv")])
    assert summary == {"files": 0, "rows": 0}
    assert "NOT FOUND" in capsys.readouterr().out
