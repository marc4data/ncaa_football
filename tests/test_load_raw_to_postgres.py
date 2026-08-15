"""Tests for the raw loader's pure logic.

The database work needs Postgres, but row counting is what makes empty-response detection
possible, so it is worth pinning down on its own.
"""
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
