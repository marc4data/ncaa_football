"""The staging-sample workbook's narrowing rule.

The export is a documentation artifact: someone reads a tab to learn what a staging model
holds. That makes the NOTE on each sheet as load-bearing as the rows — "20,000 of 199,083"
and "every Big 12 game of 2025" are different claims, and the tab cannot tell you which it
is holding.

These exercise build_query against fake column sets rather than a database. The shape of a
staging model follows its endpoint, so the branch a table takes is decided entirely by which
columns exist — which is exactly what can be tested without Postgres.
"""
from pathlib import Path

import pytest

from src import export_sample as ex


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


# --- the field inventory ---------------------------------------------------------------

class ProfileCursor:
    """Answers the two questions profile_fields asks, and records the SQL it was asked."""

    def __init__(self, columns_by_table, aggregates_by_table):
        self._columns = columns_by_table
        self._aggregates = aggregates_by_table
        self._rows = []
        self._row = None
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append(sql)
        if "information_schema" in sql:
            self._rows = list(self._columns[params[1]])
        else:
            table = next(t for t in self._aggregates if f'"{t}"' in sql)
            self._row = self._aggregates[table]

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._row


def test_the_profile_reports_null_share_and_cardinality_per_field():
    """Null % is a share of the whole table; cardinality is distinct non-null values."""
    cursor = ProfileCursor(
        {"stg_x": [("team_id", "integer"), ("note", "text")]},
        # count(*), then count / count(distinct) per column, in ordinal order.
        {"stg_x": (200, 200, 40, 150, 7)})
    profile = ex.profile_fields(cursor, ["stg_x"], "staging")
    assert profile == [
        ("stg_x", "team_id", "integer", 0.0, 40),
        # 50 of 200 null -> 25.0%, and 7 distinct among the 150 that are populated.
        ("stg_x", "note", "text", 25.0, 7),
    ]


def test_one_query_per_table_not_one_per_column():
    """1,447 columns asked individually is 2,894 round trips against views that re-parse JSON
    on every scan. Folded into one statement per table it is one."""
    cursor = ProfileCursor(
        {"stg_x": [("a", "text"), ("b", "text"), ("c", "text")]},
        {"stg_x": (10, 10, 3, 10, 4, 10, 5)})
    ex.profile_fields(cursor, ["stg_x"], "staging")
    aggregate_statements = [s for s in cursor.statements if "information_schema" not in s]
    assert len(aggregate_statements) == 1


def test_identifiers_are_quoted():
    """They come from information_schema so they are trustworthy, but a quoted identifier is
    correct for any name and a bare one only for the names we happen to have today."""
    cursor = ProfileCursor(
        {"stg_x": [("select", "text")]},
        {"stg_x": (5, 5, 2)})
    ex.profile_fields(cursor, ["stg_x"], "staging")
    aggregate = next(s for s in cursor.statements if "information_schema" not in s)
    assert 'count("select")' in aggregate
    assert 'count(distinct "select")' in aggregate


def test_an_empty_table_has_no_null_share_rather_than_zero_percent():
    """Zero would claim the column is fully populated, which is the opposite of what an empty
    table means. The sheet leaves the cell blank."""
    cursor = ProfileCursor(
        {"stg_empty": [("a", "text")]},
        {"stg_empty": (0, 0, 0)})
    profile = ex.profile_fields(cursor, ["stg_empty"], "staging")
    assert profile == [("stg_empty", "a", "text", None, 0)]


def test_a_table_with_no_columns_is_skipped_rather_than_queried():
    cursor = ProfileCursor({"stg_none": []}, {})
    assert ex.profile_fields(cursor, ["stg_none"], "staging") == []
    assert all("information_schema" in s for s in cursor.statements)


# --- the schema parameter ---------------------------------------------------------------

def test_the_query_targets_the_schema_it_was_asked_for():
    """The narrowing logic is schema-agnostic — it reads columns, not table names — so the
    same rules apply to serving. Only the qualified name changes."""
    sql, _, _ = ex.build_query(FakeCursor(["game_id"]), "srv_game", 999_999, MEMBERS,
                               schema="serving")
    assert "from serving.srv_game" in sql
    assert "staging." not in sql


def test_the_schema_defaults_to_staging():
    """The existing invocation must keep working unchanged."""
    sql, _, _ = _query(["game_id"], 999_999)
    assert "from staging.stg_x" in sql
    assert ex.DEFAULT_SCHEMA == "staging"


def test_the_game_spine_is_pinned_to_staging_whatever_is_being_exported():
    """Resolving which games belong to a conference is a question about the SCHEDULE, not
    about the layer somebody asked for — and `serving.stg_games` does not exist, so a naive
    substitution would fail on the first serving export."""
    assert ex.SPINE_TABLE == "staging.stg_games"
    source = Path(ex.__file__).read_text()
    assert "{SPINE_TABLE}" in source
    assert "{schema}.stg_games" not in source


def test_only_the_allowlisted_schemas_are_reachable():
    """The schema name is interpolated into SQL because a bound parameter cannot be an
    identifier. An allowlist is the correct cheap answer: `raw` holds JSON payloads nobody
    wants in a workbook, and there is nothing to escape."""
    assert set(ex.EXPORTABLE_SCHEMAS) == {"staging", "serving"}
    assert "raw" not in ex.EXPORTABLE_SCHEMAS


def test_every_exportable_schema_describes_itself():
    """The Index sheet's layer note is read from this map rather than written twice, so a
    serving workbook cannot describe itself as staging."""
    for name, description in ex.EXPORTABLE_SCHEMAS.items():
        assert description and len(description) > 30, name


# --- the default output path -------------------------------------------------------------

def test_the_default_filename_carries_the_schema_and_a_timestamp():
    """Two runs must not silently overwrite each other.

    The old default was a fixed `staging_sample.xlsx`, so exporting twice left one file and
    no way to tell which run made it. The name now carries both the layer and the minute.
    """
    import re
    source = Path(ex.__file__).read_text()
    match = re.search(r'f"data/exports/\{args\.schema\}_sample_\{([^}]+)\}\.xlsx"', source)
    assert match, "the default output name must interpolate both the schema and a timestamp"
    assert "%Y%m%d_%H%M" in match.group(1), "sortable to the minute, so files list in order"


def test_the_default_is_local_time_and_the_workbook_reconciles_it():
    """The filename stamp is for a person finding the file they made this afternoon, so it is
    local. The Index line is provenance and has always been UTC. Showing one without the
    other makes the pair look inconsistent, so the Index carries both."""
    source = Path(ex.__file__).read_text()
    assert 'datetime.now():%Y%m%d_%H%M' in source, "filename uses local time"
    assert "local" in source and "UTC)" in source, "the Index shows both zones"


def test_nothing_still_refers_to_the_old_module_name():
    """Renamed with NO shim, for the reason alias views are forbidden in this project: a
    second name is how two things drift. So there must be no second name."""
    import re
    root = Path(ex.__file__).resolve().parents[1]
    # Match the IMPORT and INVOCATION forms, not the bare word. The module's own docstring
    # explains what it was renamed from, and this file names it in a search string — the
    # first version of this test flagged both. That is the fifth time a source-reading test
    # in this project has matched its own prose; test_dag_structure._is_tagged carries the
    # earlier ones, and the lesson keeps being the same: assert on the code, not the words.
    usage = re.compile(r"(?:src\.|import\s+)export_staging_sample")
    stale = []
    for pattern in ("src/*.py", "tests/*.py", "site/**/*.py", "dags/*.py", "ci/*.py"):
        for path in root.glob(pattern):
            if path.name == Path(__file__).name:
                continue
            if usage.search(path.read_text()):
                stale.append(str(path.relative_to(root)))
    assert not stale, f"still importing or invoking the old module name: {stale}"
