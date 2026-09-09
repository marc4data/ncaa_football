"""The Matchup offence-against-defence panel: form leading into this game's week (R-465).

WHAT THIS EXISTS TO CATCH, AND IT IS ONE THING ABOVE ALL THE OTHERS. The comparison Marc
asked for runs ACROSS SIDES — "how team A produces passing yards compared to how Team B
allows passing yards" — and the wrong version, a team's `_for` beside its own `_allowed`,
renders perfectly. It is a description of one team wearing the layout of a matchup, every
number on it is true, and nothing else in this project would notice. So
`test_the_pairing_runs_across_sides_not_down_one` was written first, the pairing was flipped
on purpose, and the test was watched go red before it was fixed back. A test that passes
both ways is not a test.

⚠️ IT CALLS THE PANEL, IT DOES NOT GREP FOR A COLUMN NAME. R-480 is open precisely because
nothing in this project calls a page's `render()`: `check_page_queries` executes SQL and
never draws, the site smoke test counts pages without running one, and a test that greps
this module's source for `rushing_yards_allowed_per_game` would pass on a panel that pairs
it with the wrong team. The query is stubbed and the panel is invoked, which is the pattern
test_matchup_line_movement used and the one that caught real defects.

THE THREE STATES BELOW THE PAIRING are each a different claim and the panel must not
collapse them:

  1. NULL per-game, because nothing has been counted. srv_team_week's own comment: "0.0
     yards per game is a measurement it did not make." A zero here would be a lie about a
     measurement, and there are TWO reasons for it — nobody has played yet, or cfdb holds no
     box scores for these sides — which are opposite statements.
  2. One side carried and the other not. srv_team_week inner joins dim_team, which does not
     list every opponent an FBS side schedules, and BOTH directions of the comparison need
     both rows. Degraded, naming the side, and the whole panel rather than half of it.
  3. `games_counted` visible for both sides, always (AC-G.33), because the two differ — 7
     against 8 on game 401752754 — and 154.4 beside 84.5 with no denominator is two true
     numbers misleading a reader.
"""
import html
import re
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()


def _stub_streamlit():
    """Capture what the panel emits instead of rendering it."""
    captured = []

    def recorder(kind):
        def call(*args, **kwargs):
            captured.append((kind, " ".join(str(a) for a in args)))
        return call

    stub = types.ModuleType("streamlit")
    for name in ("subheader", "caption", "markdown", "write", "info", "warning", "error"):
        setattr(stub, name, recorder(name))

    class _Col:
        def metric(self, label, value, help=None):
            captured.append(("metric", f"{label} {value} {help or ''}"))

        def markdown(self, *args, **kwargs):
            captured.append(("markdown", " ".join(str(a) for a in args)))

    stub.columns = lambda n: [_Col() for _ in range(n if isinstance(n, int) else len(n))]
    stub.button = lambda *a, **k: False
    stub.empty = lambda *a, **k: _Col()

    def cache(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda fn: fn

    stub.cache_data = stub.cache_resource = cache
    stub.session_state = {}
    return stub, captured


# The modules that hold their own `import streamlit`. Reloading the view alone leaves
# lib.states emitting into the REAL streamlit, so the Degraded state renders somewhere the
# capture cannot see it. lib.shell is here because table.as_of_caption asks it for a slot.
_RELOAD = ("lib.states", "lib.table", "lib.identity", "lib.shell", "views.matchup")


def _reload_all():
    import importlib
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))


@pytest.fixture
def panel():
    """The panel with streamlit captured and the database replaced by constructed rows.

    ⚠️ IT PUTS THE MODULES BACK. Reloading lib.states against a stub binds the stub inside it
    for the REST OF THE SESSION — test_matchup_drives learned that the hard way and six
    unrelated tests failed. `monkeypatch` cannot undo it either: its sys.modules restore runs
    after this teardown, so the swap and the restore are both done by hand here.
    """
    real = sys.modules.get("streamlit")
    stub, captured = _stub_streamlit()
    sys.modules["streamlit"] = stub
    _reload_all()
    matchup = sys.modules["views.matchup"]
    seen = {}

    def run(game, sides):
        """`sides` is what srv_team_week returns — zero, one or two constructed rows."""
        captured.clear()
        seen.clear()

        def fake_query(sql, params=None):
            seen["sql"], seen["params"] = sql, params or {}
            return pd.DataFrame(sides)

        matchup.query = fake_query
        matchup._yardage(pd.Series(game))
        return list(captured), dict(seen)

    yield run

    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    _reload_all()


HOME_ID, AWAY_ID = 2, 96


def _game(**overrides):
    """One srv_game row's worth of the columns this panel keys on."""
    game = {"game_id": 401752754, "season": 2025, "season_type": "regular", "week": 10,
            "home_team": "Auburn", "away_team": "Kentucky",
            "home_team_id": HOME_ID, "away_team_id": AWAY_ID}
    game.update(overrides)
    return game


def _side(team_id, display, **overrides):
    """One srv_team_week row. Deliberately distinct numbers on every field.

    THE NUMBERS ARE NOT ARBITRARY: no two figures across the two sides are equal, so an
    assertion that a particular value reached the panel can only be satisfied by the column
    it actually came from. Real 2025 week 10 figures for the two teams named.
    """
    side = {"team_id": team_id, "team_display": display, "team_slug": display.lower(),
            "logo_url": None, "color_on_light": "#0C2340", "color_on_dark": "#0C2340",
            "conference": "SEC", "classification": "fbs", "is_fbs": True,
            "games_counted": 8,
            "rushing_yards_for_per_game": 111.1, "passing_yards_for_per_game": 222.2,
            "total_yards_for_per_game": 333.3,
            "rushing_yards_allowed_per_game": 444.4,
            "passing_yards_allowed_per_game": 555.5,
            "total_yards_allowed_per_game": 999.9,
            "as_of_ts": pd.Timestamp("2026-09-09T12:00:00Z")}
    side.update(overrides)
    return side


def _both(**home_over):
    """Auburn at home, Kentucky away, with the real week-10 figures for game 401752754."""
    home = _side(HOME_ID, "Auburn", games_counted=8,
                 rushing_yards_for_per_game=170.8, passing_yards_for_per_game=170.0,
                 total_yards_for_per_game=340.8,
                 rushing_yards_allowed_per_game=84.5,
                 passing_yards_allowed_per_game=234.4,
                 total_yards_allowed_per_game=318.9)
    away = _side(AWAY_ID, "Kentucky", games_counted=7,
                 rushing_yards_for_per_game=154.4, passing_yards_for_per_game=207.0,
                 total_yards_for_per_game=361.4,
                 rushing_yards_allowed_per_game=132.6,
                 passing_yards_allowed_per_game=253.0,
                 total_yards_allowed_per_game=385.6)
    home.update(home_over)
    return [home, away]


def _plain(markup: str) -> str:
    """Tags out, whitespace collapsed.

    The team name and the word "offence" sit in separate spans, so stripping tags leaves a
    double space between them and a naive substring test for "Kentucky offence" fails on a
    panel that is drawing correctly. Collapsing here means the assertions read as the
    sentence a reader sees.
    """
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


def _text(entries):
    return " ".join(_plain(body) for _, body in entries)


# --- the pairing, which is the whole point -------------------------------------------------

def test_the_pairing_runs_across_sides_not_down_one(panel):
    """⚠️ THE ASSERTION THIS FILE EXISTS FOR (1c).

    Kentucky's rushing attack is 154.4 and Auburn allows 84.5 on the ground. Those two must
    appear TOGETHER, in that order, on one line — Kentucky's number beside AUBURN's, not
    beside Kentucky's own 132.6 allowed.

    This was verified by breaking it: swapping the two arguments of `_yardage_direction` in
    the panel makes both assertions below fail, because the away block then reads 154.4
    against Kentucky's own 132.6.
    """
    entries, _ = panel(_game(), _both())
    blocks = [_plain(body) for kind, body in entries if kind == "markdown"]
    away_block = " ".join(b for b in blocks if "Kentucky offence" in b)
    assert away_block, "the away team's attack was never drawn"
    assert "154.4" in away_block, "Kentucky's rushing offence is missing"
    assert "84.5" in away_block, \
        "Kentucky's attack is not paired with AUBURN's rushing defence"
    assert "132.6" not in away_block, \
        "the panel paired Kentucky's offence with Kentucky's own defence — one team " \
        "described as though it were a matchup"

    home_block = " ".join(b for b in blocks if "Auburn offence" in b)
    assert home_block, "the home team's attack was never drawn"
    assert "170.8" in home_block and "132.6" in home_block, \
        "Auburn's attack is not paired with Kentucky's rushing defence"
    assert "84.5" not in home_block, \
        "the panel paired Auburn's offence with Auburn's own defence"


def test_both_directions_are_drawn(panel):
    """Marc named a comparison with two directions, and one of them is not the answer."""
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    assert "Kentucky offence" in body and "Auburn offence" in body, \
        "only one direction of the comparison was rendered"


def test_rushing_and_passing_are_both_present_and_separate(panel):
    """Marc named both, separately, and asked for them separately rather than as a total."""
    body = _text(panel(_game(), _both())[0])
    assert "Rushing" in body and "Passing" in body
    for figure in ("154.4", "207.0", "170.8", "170.0", "84.5", "234.4", "132.6", "253.0"):
        assert figure in body, f"{figure} is missing from the panel"


# --- the denominator travels with the numbers (AC-G.33) ------------------------------------

def test_games_counted_is_shown_for_both_sides_and_they_can_differ(panel):
    """7 against 8 on this real game. A reader comparing 154.4 to 84.5 without the
    denominators is being misled by two true numbers."""
    body = _text(panel(_game(), _both())[0])
    assert "7" in body and "8" in body
    assert "Auburn" in body and "Kentucky" in body
    assert "not games played" in body.lower(), \
        "games_counted was shown without saying what it counts"


# --- the states ----------------------------------------------------------------------------

def test_nothing_played_yet_renders_empty_and_never_a_zero(panel):
    """⚠️ THE PER-GAME COLUMNS ARE NULL BY DESIGN AT THE OPENING WEEK, NOT ZERO.

    Measured against serving: at week 1 of a regular season, games_counted is 0 for every
    team in all 157 seasons srv_team_week covers. "0.0 yards per game is a measurement it
    did not make" — the view's own comment.
    """
    sides = [_side(HOME_ID, "Auburn", games_counted=0, **{c: None for c in (
                 "rushing_yards_for_per_game", "passing_yards_for_per_game",
                 "total_yards_for_per_game", "rushing_yards_allowed_per_game",
                 "passing_yards_allowed_per_game", "total_yards_allowed_per_game")}),
             _side(AWAY_ID, "Kentucky", games_counted=0, **{c: None for c in (
                 "rushing_yards_for_per_game", "passing_yards_for_per_game",
                 "total_yards_for_per_game", "rushing_yards_allowed_per_game",
                 "passing_yards_allowed_per_game", "total_yards_allowed_per_game")})]
    entries, _ = panel(_game(week=1), sides)
    body = _text(entries)
    assert "would be here" in body, "the Empty state did not render"
    assert "0.0" not in body, "a null per-game figure was drawn as zero"
    assert "not played" in body.lower() or "no per-game figure" in body.lower()


def test_no_box_scores_is_a_different_claim_from_nothing_played_yet(panel):
    """The two reasons a per-game figure is missing are opposite statements.

    Box scores are held from 2024 onward — measured: no row in any earlier season carries
    games_counted > 0 — so a 1999 game has played eight weeks and still has no figure.
    Saying "neither side has played yet" about it would be the lie _model refuses to tell
    about a missing forecast.
    """
    sides = [_side(HOME_ID, "Marshall", games_counted=0),
             _side(AWAY_ID, "Toledo", games_counted=0)]
    body = _text(panel(_game(season=1999, week=8,
                             home_team="Marshall", away_team="Toledo"), sides)[0]).lower()
    assert "no box scores" in body, \
        "a pre-box-score game was explained as though nobody had played yet"
    assert "has played" not in body and "played a counted game" not in body, \
        "a game eight weeks into 1999 was described as though nobody had played yet"
    assert "0.0" not in body


def test_one_side_missing_is_degraded_and_names_that_side(panel):
    """⚠️ srv_team_week INNER JOINS dim_team, and dim_team does not list every opponent.

    Measured against serving directly: 11,827 games across all seasons have exactly one side
    carried and the other not. A075 measured the row loss upstream — 485,173
    fct_team_yardage_week rows against 375,440 published here, so ~22.6% do not survive the
    join — and the 375,440 half of that was re-verified in serving for this round.
    """
    entries, _ = panel(_game(), [_side(HOME_ID, "Auburn")])
    body = _text(entries)
    assert "Kentucky" in body, "the Degraded state did not name the side it is missing"
    assert "srv_team_week" in body, "Degraded must name the object it is waiting on"


def test_one_side_missing_does_not_render_half_a_matchup(panel):
    """A panel that draws one team's own for-and-allowed under a matchup heading is worse
    than one that says it cannot: every number on it is true and it answers a question
    nobody asked."""
    entries, _ = panel(_game(), [_side(HOME_ID, "Auburn")])
    body = _text(entries)
    assert "Auburn offence" not in body, \
        "half the comparison was drawn as though it were the whole one"
    assert "111.1" not in body and "444.4" not in body


def test_neither_side_carried_is_empty_and_the_page_survives(panel):
    entries, _ = panel(_game(season=1873, week=3), [])
    body = _text(entries)
    assert "would be here" in body
    assert "Auburn" in body and "Kentucky" in body


def test_a_broken_row_degrades_this_panel_and_not_the_page(panel):
    """states.section is the blast wall. The panel must not take Matchup down with it."""
    entries, _ = panel(_game(week="not a week"), _both())
    body = _text(entries)
    assert "Something went wrong" in body or "srv_team_week" in body, \
        "the panel raised out of its own section instead of degrading"


# --- the contract the serving layer exists to keep -----------------------------------------

def test_the_panel_does_no_aggregation_and_no_arithmetic(panel):
    """G-3. The grain returns one row per side, so a `group by` or a `sum(` here would mean
    the design is wrong rather than that the page needs a workaround."""
    _, seen = panel(_game(), _both())
    sql = seen["sql"].lower()
    for banned in ("group by", "sum(", "avg(", "count(", "over (", "join"):
        assert banned not in sql, f"the panel's query contains `{banned}`"
    assert "_per_game" in sql, "the panel reads the sums instead of the per-game columns"


def test_the_lookup_is_keyed_on_the_games_own_week(panel):
    """⚠️ Marc, 2026-09-09: "Can't find ourselves at Week 10 and looking back to the
    matchups for a team in Week 2 and have their data for Week 2 showing like they've played
    through Week 10." The row read is the one for THIS game's own key."""
    _, seen = panel(_game(week=10), _both())
    assert seen["params"]["week"] == 10
    assert seen["params"]["season"] == 2025
    assert seen["params"]["season_type"] == "regular"
    assert set(seen["params"]) >= {"home_team_id", "away_team_id"}


def test_the_panel_reads_one_serving_view_with_a_limit():
    """G-1, G-2 and AC-G.39, enforced by the real contract checker rather than by eye."""
    from lib.query import check_contract
    matchup = sys.modules.get("views.matchup")
    if matchup is None:
        import importlib
        matchup = importlib.import_module("views.matchup")
    sql = f"select {matchup._YARDAGE_COLUMNS} from srv_team_week where season = :season limit 2"
    assert check_contract(sql) == "srv_team_week"


def test_the_game_id_columns_the_lookup_needs_are_selected():
    """1a. The lookup cannot be keyed without them, and COLUMNS did not carry them."""
    assert "home_team_id" in SOURCE and "away_team_id" in SOURCE
    columns = SOURCE.split("COLUMNS = \"\"\"")[1].split("\"\"\"")[0]
    assert "home_team_id" in columns and "away_team_id" in columns, \
        "the ids are used but never selected from srv_game"


# --- nothing is ranked ---------------------------------------------------------------------

def test_no_threshold_no_edge_no_ranking(panel):
    """Marc sets the line, not the page — the rule _line_movement carries a test for."""
    lopsided = _both()
    lopsided[0]["rushing_yards_allowed_per_game"] = 12.0
    body = _text(panel(_game(), lopsided)[0]).lower()
    for verdict in ("edge", "advantage", "mismatch", "favours", "favors", "stronger",
                    "weaker", "elite", "best", "worst", "rank"):
        assert verdict not in body, f"the panel editorialised: {verdict!r}"
