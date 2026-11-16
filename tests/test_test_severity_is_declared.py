"""A294 (cfdb-main-R-5132): a singular assertion's severity is a decision, not a default.

The check is `ci/check_test_severity_declared.py`. These tests prove it can fail (R-760/R-843):
a staged undeclared test turns it red, and so does one whose only `severity=` is prose.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_test_severity_declared", ROOT / "ci" / "check_test_severity_declared.py")
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)


def _stage(tmp_path, name, body):
    (tmp_path / f"{name}.sql").write_text(body)
    return tmp_path


def test_every_singular_test_in_the_repository_declares_its_severity():
    missing = chk.undeclared(ROOT / "dbt" / "tests")
    assert missing == [], [p.name for p in missing]


def test_a_staged_test_with_no_config_turns_the_check_red(tmp_path):
    _stage(tmp_path, "assert_declared", "{{ config(severity='warn') }}\nselect 1 where false\n")
    _stage(tmp_path, "assert_undeclared", "-- a header\nselect 1 where false\n")
    assert [p.name for p in chk.undeclared(tmp_path)] == ["assert_undeclared.sql"]
    assert chk.main([str(tmp_path)]) == 1


def test_a_severity_written_only_in_a_comment_declares_nothing(tmp_path):
    # The prose trap: this project's headers discuss config() at length.
    _stage(tmp_path, "assert_prose", "-- {{ config(severity='error') }} is what this used to say\n"
                                     "{# config(severity='warn') #}\n"
                                     "{{ config(tags=['full_refresh_only']) }}\nselect 1\n")
    assert [p.name for p in chk.undeclared(tmp_path)] == ["assert_prose.sql"]


def test_choosing_error_deliberately_passes(tmp_path):
    # It declares; it does not silence.
    _stage(tmp_path, "assert_gates", "{{ config(severity='error', tags=[]) }}\nselect 1\n")
    assert chk.undeclared(tmp_path) == []
    assert chk.main([str(tmp_path)]) == 0


def test_generic_test_definitions_are_not_assertions(tmp_path):
    (tmp_path / "generic").mkdir()
    (tmp_path / "generic" / "populated_rate.sql").write_text("{% test populated_rate() %}{% endtest %}")
    assert chk.undeclared(tmp_path) == []


def test_exactly_the_tests_marc_s_rule_names_still_gate():
    # A294's classification, pinned: changing the gating set is a decision to make in the
    # open, with the report's table updated, not a side effect of an edit.
    gating = sorted(p.stem for p in (ROOT / "dbt" / "tests").glob("*.sql")
                    if chk.declared_severity(p.read_text()) == "error")
    assert gating == sorted([
        "assert_a_games_two_ats_margins_cancel",
        "assert_a_poll_row_is_not_multiplied_by_its_explaining_game",
        "assert_devig_probabilities_sum_to_one",
        "assert_facts_are_unique_on_their_natural_key",
        "assert_game_winner_matches_margin_sign",
        "assert_no_moneyline_sentinel_reaches_the_devig",
        "assert_no_prediction_travels_without_its_attribution",
        "assert_only_pack_models_claim_the_pack",
        "assert_prediction_margin_is_away_minus_home",
        "assert_prediction_sign_convention",
        "assert_predictions_are_never_mutated",
        "assert_site_facing_staging_models_are_unique_on_their_grain",
        "assert_srv_game_is_still_one_row_per_game",
        "assert_srv_player_game_log_is_one_row_per_player_stat",
        "assert_the_line_basis_names_the_side_that_was_favoured",
        "assert_the_per_side_spread_names_the_spread_favorite",
    ])
