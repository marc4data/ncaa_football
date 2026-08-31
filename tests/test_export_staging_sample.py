"""The staging-sample workbook's narrowing rule.

The export is a documentation artifact: someone reads a tab to learn what a staging model
holds. That makes the NOTE on each sheet as load-bearing as the rows — "20,000 of 199,083"
and "every Big 12 game of 2025" are different claims, and the tab cannot tell you which it
is holding.

These exercise build_query against fake column sets rather than a database. The shape of a
staging model follows its endpoint, so the branch a table takes is decided entirely by which
columns exist — which is exactly what can be tested without Postgres.
"""
import pytest

from src import export_staging_sample as ex


class FakeCursor:
    """Answers only the information_schema question build_query asks."""

    def __init__(self, columns):
        self._columns = columns
        self._result = []

    def execute(self, sql, params=None):
        self._result = [(c,) for c in self._columns]

    def fetchall(self):
        return self._result


MEMBERS = {"conference": "Big 12", "season": 2025,
           "team_ids": [197, 2306], "names": ["Oklahoma State", "Kansas"],
           "game_ids": [1, 2, 3]}


def _query(columns, row_count):
    return ex.build_query(FakeCursor(columns), "stg_x", row_count, MEMBERS)


def test_the_cap_is_twenty_thousand():
    assert ex.ROW_CAP == 20_000


def test_a_table_under_the_cap_is_exported_whole():
    sql, params, note = _query(["season", "game_id"], 500)
    assert "where" not in sql.lower()
    assert params == {}
    assert "Whole table" in note


def test_a_game_table_is_filtered_on_either_side_being_a_member():
    """The request is activity tied to games involving a Big 12 team, so a table that can
    express a game gets the game reading."""
    sql, params, note = _query(["season", "home_team_id", "away_team_id"], 999_999)
    assert "home_team_id = any(%(ids)s) or away_team_id = any(%(ids)s)" in sql
    assert params["ids"] == MEMBERS["team_ids"]
    assert "either side a Big 12 team" in note


def test_a_table_with_only_game_id_is_scoped_through_the_resolved_game_set():
    """stg_lines and stg_game_team_stat carry no team and no season. Answering the request
    through a join is legitimate; implying the table carried the filter itself is not, so
    the note has to say the narrowing was indirect."""
    sql, params, note = _query(["game_id", "provider"], 999_999)
    assert "game_id = any(%(game_ids)s)" in sql
    assert params["game_ids"] == MEMBERS["game_ids"]
    assert "resolved via stg_games" in note


def test_game_grain_wins_over_team_grain_when_a_table_has_both():
    """stg_game_team_stat has game_id AND team_id. Filtering on team_id would return that
    team's rows from games against anyone; the request is the games."""
    sql, _params, note = _query(["game_id", "team_id"], 999_999)
    assert "game_id = any" in sql
    assert "team_id = any" not in sql
    assert "resolved via stg_games" in note


def test_a_team_table_is_filtered_to_the_member_teams_and_says_so():
    """A team-grain table has no games to be tied to. Filtering it to the members is the
    same request at the grain the table has — but it is a different claim, so the note
    marks it rather than letting the tab look like a game filter."""
    sql, params, note = _query(["season", "team_id", "elo"], 999_999)
    assert "team_id = any(%(ids)s)" in sql
    assert params["ids"] == MEMBERS["team_ids"]
    assert "TEAM grain, not game grain" in note


def test_a_table_with_only_a_name_is_matched_by_name_and_flagged():
    sql, params, note = _query(["season", "school", "yards"], 999_999)
    assert "school = any(%(names)s)" in sql
    assert params["names"] == MEMBERS["names"]
    assert "matched by" in note and "NAME" in note


def test_season_is_always_applied_where_the_column_exists():
    """Conference membership is season-scoped — the Big 12 had 14 members in 2023 and 16
    from 2024 — so a filter without the season would blend eras."""
    sql, params, _note = _query(["season", "home_team_id", "away_team_id"], 999_999)
    assert "season = %(season)s" in sql
    assert params["season"] == 2025


def test_an_unnarrowable_table_says_so_rather_than_pretending():
    sql, params, note = _query(["some_column", "another"], 999_999)
    assert "where" not in sql.lower()
    assert params == {}
    assert "NOT NARROWABLE" in note


@pytest.mark.parametrize("columns", [
    ["season", "home_team_id", "away_team_id"], ["game_id"], ["season", "team_id"],
    ["season", "school"], ["nothing_useful"],
])
def test_every_branch_produces_a_note(columns):
    """The Index sheet is the only place the workbook explains itself."""
    _sql, _params, note = _query(columns, 999_999)
    assert note and len(note) > 20
