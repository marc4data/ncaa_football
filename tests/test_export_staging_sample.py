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


# `team_ids` / `names` are PARTICIPANTS — the members plus every opponent they played.
# `member_ids` / `member_names` are the conference itself. The two are deliberately
# different here so a filter that reaches for the wrong one is visible in the params.
MEMBERS = {"conference": "Big 12", "seasons": [2025, 2026],
           "per_season": {2025: 2, 2026: 2},
           "member_ids": [197, 2306], "member_names": ["Kansas", "Oklahoma State"],
           "team_ids": [8, 197, 2306, 2641],
           "names": ["Arkansas", "Kansas", "Oklahoma State", "Tulsa"],
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
    express a game gets the game reading.

    MEMBERS HERE, NOT PARTICIPANTS. A game qualifies because a CONFERENCE team is in it.
    Filtering on participants would also return games between two of the opponents — Tulsa
    vs Arkansas because both happened to play a Big 12 team — which is a different and much
    larger question than the one asked.
    """
    sql, params, note = _query(["season", "home_team_id", "away_team_id"], 999_999)
    assert "home_team_id = any(%(member_ids)s)" in sql
    assert params["member_ids"] == MEMBERS["member_ids"]
    assert "ids" not in params, "the participant set must not reach the game filter"
    assert "either side a Big 12 team" in note
    assert "both teams' rows are included" in note


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


def test_a_team_table_includes_the_opponents_and_says_so():
    """A team-grain table has no games to be tied to, so it is filtered to teams — and the
    teams that matter are everyone who played in the game set, not just the members.

    This was the gap. A game-grain sheet returned both sides for free, but a team-grain
    sheet returned only the conference's own rows, so the opponent whose game was in the
    workbook had no season stats, no rating and no ranking anywhere in it. Half of every
    matchup was missing from exactly the tables that describe a matchup.
    """
    sql, params, note = _query(["season", "team_id", "elo"], 999_999)
    assert "team_id = any(%(ids)s)" in sql
    assert params["ids"] == MEMBERS["team_ids"]
    assert params["ids"] != MEMBERS["member_ids"], "opponents must be in the team filter"
    assert "TEAM grain, not game grain" in note
    assert "opponents" in note


def test_a_table_with_only_a_name_is_matched_by_name_and_flagged():
    """Name-matched team grain follows the same participants rule as id-matched."""
    sql, params, note = _query(["season", "school", "yards"], 999_999)
    assert "school = any(%(names)s)" in sql
    assert params["names"] == MEMBERS["names"]
    assert "matched by" in note and "NAME" in note
    assert "opponents" in note


def test_season_is_always_applied_where_the_column_exists():
    """Conference membership is season-scoped — the Big 12 had 14 members in 2023 and 16
    from 2024 — so a filter without the season would blend eras."""
    sql, params, note = _query(["season", "home_team_id", "away_team_id"], 999_999)
    assert "season = any(%(seasons)s)" in sql
    assert params["seasons"] == [2025, 2026]
    assert "season 2025, 2026" in note


def test_every_season_asked_for_reaches_the_filter():
    """A multi-season export that quietly dropped a year would look like a correct workbook
    with a thin tab, which is the hardest kind of wrong to notice."""
    _sql, params, _note = _query(["season", "team_id"], 999_999)
    assert params["seasons"] == MEMBERS["seasons"]


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


# --- membership is resolved per season, then unioned --------------------------------------

class SeasonAwareCursor:
    """Answers the three queries resolve_conference asks, per season.

    `members` maps season -> [(team_id, school)]; `games` maps season -> [(game_id, home, away)].
    """

    def __init__(self, members, games):
        self._members, self._games = members, games
        self._result = []

    def execute(self, sql, params=None):
        params = params or {}
        if "dim_team" in sql and "conference" in sql:
            self._result = self._members.get(params["season"], [])
        elif "stg_games" in sql:
            self._result = self._games.get(params["season"], [])
        elif "dim_team" in sql:                       # participant names
            wanted = set(params["ids"])
            names = {school for rows in self._members.values() for tid, school in rows
                     if tid in wanted}
            self._result = [(n,) for n in sorted(names)]
        else:
            self._result = []

    def fetchall(self):
        return self._result


def test_membership_is_resolved_per_season_not_across_the_union():
    """THE REASON THIS IS NOT A ONE-LINE CHANGE.

    A team that joins in 2026 must contribute its 2026 games and not its 2025 ones. Asking
    "who was in the Big 12 across 2025 and 2026" as a single question, then filtering games
    by that merged list, hands the joiner both years — silently, and in the direction of
    more data, which is the direction nobody double-checks.

    Newcomer (id 9) is a member in 2026 only. Its 2025 game must not be in the set.
    """
    members = {2025: [(197, "Oklahoma State")],
               2026: [(197, "Oklahoma State"), (9, "Newcomer")]}
    games = {2025: [(1, 197, 50)],                    # Oklahoma State v an opponent
             2026: [(2, 197, 60), (3, 9, 70)]}        # and Newcomer's own 2026 game
    cursor = SeasonAwareCursor(members, games)

    scope = ex.resolve_conference(cursor, "Big 12", [2025, 2026])

    assert scope["seasons"] == [2025, 2026]
    assert scope["per_season"] == {2025: 1, 2026: 2}
    assert sorted(scope["member_ids"]) == [9, 197]
    assert scope["game_ids"] == [1, 2, 3]
    # If membership had been resolved against the merged set, Newcomer would have been a
    # 2025 member too and any 2025 game of its own would have joined the set.
    assert 9 not in [home for _g, home, _a in games[2025]]


def test_opponents_are_in_the_participant_set_but_not_the_member_set():
    """The two sets answer different questions and the filters pick between them."""
    members = {2025: [(197, "Oklahoma State")]}
    games = {2025: [(1, 197, 50), (2, 60, 197)]}      # home and away opponents
    scope = ex.resolve_conference(SeasonAwareCursor(members, games), "Big 12", [2025])

    assert scope["member_ids"] == [197]
    assert scope["team_ids"] == [50, 60, 197], "both opponents, and the member, in order"


def test_seasons_are_deduplicated_and_sorted():
    """`--season 2026 2025 2026` is a typo, not a request for 2026 twice."""
    members = {2025: [(197, "Oklahoma State")], 2026: [(197, "Oklahoma State")]}
    scope = ex.resolve_conference(SeasonAwareCursor(members, {}), "Big 12", [2026, 2025, 2026])
    assert scope["seasons"] == [2025, 2026]


def test_a_season_with_no_members_is_reported_rather_than_hidden():
    """A zero year is a misspelled conference or a season with no data. Folded into a
    combined count it is invisible; per season it is obvious."""
    members = {2025: [(197, "Oklahoma State")], 2026: []}
    scope = ex.resolve_conference(SeasonAwareCursor(members, {}), "Big 12", [2025, 2026])
    assert scope["per_season"] == {2025: 1, 2026: 0}
