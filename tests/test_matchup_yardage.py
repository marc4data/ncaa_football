"""The Matchup offense-against-defense panel: form leading into this game's week (R-465).

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
        # R-522 put the two directions in columns, so the panel now uses `with left:` and the
        # stub has to be enterable. Content written inside goes to the MODULE recorders, which
        # is what real streamlit does too, so the captured order is unchanged.
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def metric(self, label, value, help=None):
            captured.append(("metric", f"{label} {value} {help or ''}"))

        def markdown(self, *args, **kwargs):
            captured.append(("markdown", " ".join(str(a) for a in args)))

    stub.columns = lambda n, **k: [_Col() for _ in range(n if isinstance(n, int) else len(n))]

    def altair_chart(chart, **kwargs):
        # ⚠️ THE OBJECT, NOT ITS REPR. A chart's axis limits are the thing R-590 is about, and
        # `str(chart)` says nothing about them — the assertions read `chart.to_dict()`.
        captured.append(("chart", chart))

    stub.altair_chart = altair_chart
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


# The week's shared frame, read back from srv_team_week_metric_distribution for 2025 regular
# week 12 — the axis limits, the medians and the quartiles a real page would draw on.
_METRICS = {
    "rushing_yards_for_per_game":     (50.0, 350.0, 126.65, 156.15, 186.00),
    "passing_yards_for_per_game":     (50.0, 350.0, 194.725, 231.35, 258.575),
    "total_yards_for_per_game":       (200.0, 550.0, 344.975, 387.90, 428.675),
    "rushing_yards_allowed_per_game": (60.0, 240.0, 124.625, 146.00, 170.10),
    "passing_yards_allowed_per_game": (125.0, 300.0, 193.45, 219.80, 241.30),
    "total_yards_allowed_per_game":   (200.0, 500.0, 325.825, 373.25, 403.475),
}


def _distribution(min_games=9, axes=None, **overrides):
    """The week's six rows. `axes` replaces the limits of named metrics only.

    ⚠️ `axes` IS PER-METRIC AND `overrides` IS NOT — R-601 needs one metric's frame moved
    while the other five stay put, because the defect is a single axis that cannot hold a
    single value. `**overrides` updates every row and would move all six.
    """
    axes = axes or {}
    rows = []
    for metric, (low, high, p25, p50, p75) in _METRICS.items():
        low, high = axes.get(metric, (low, high))
        rows.append({
            "season": 2025, "season_type": "regular", "week": 12, "metric": metric,
            "n": 136, "teams_in_week": 136,
            "min_games_counted": min_games, "max_games_counted": 10,
            "mean": p50, "stddev": 59.0,
            "p25": p25, "p50": p50, "p75": p75,
            "axis_min": low, "axis_max": high, "axis_step": 50.0,
            "as_of_ts": pd.Timestamp("2026-09-10 12:00:00+00:00"),
        })
    for row in rows:
        row.update(overrides)
    return rows


_DISTRIBUTION = _distribution()


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

    def run(game, sides, distribution=_DISTRIBUTION):
        """`sides` is what srv_team_week returns — zero, one or two constructed rows.

        ⚠️ THE PANEL READS TWO RELATIONS SINCE R-590, so the stub dispatches on the SQL rather
        than answering both with the same frame. `seen["sql"]` stays bound to the srv_team_week
        query, because that is the one every assertion below was written about; the
        distribution query is recorded separately.
        """
        captured.clear()
        seen.clear()
        seen["queries"] = []

        def fake_query(sql, params=None):
            seen["queries"].append(sql)
            if "srv_team_week_metric_distribution" in sql:
                seen["axis_sql"], seen["axis_params"] = sql, params or {}
                return pd.DataFrame(distribution or [])
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
    it actually came from. ⚠️ THEY ARE SYNTHETIC AND THIS DOCSTRING USED TO CALL THEM "real
    2025 week 10 figures" — they are not, and the real ones are in `_both()`. B082's `_row()`
    made exactly that claim about invented numbers and its tests passed either way.

    🚨 AND THEY NOW SIT INSIDE `_METRICS`'s LIMITS, WHICH THEY DID NOT (R-601). The allowed
    columns read 444.4, 555.5 and 999.9 against week-12 axes of [60, 240], [125, 300] and
    [200, 500] — every one of them off the frame the same fixture said the chart was drawn
    on. Nothing noticed, because until this round no test asked where in the frame a point
    landed. A fixture that cannot be plotted on its own axis cannot test a chart.
    """
    side = {"team_id": team_id, "team_display": display, "team_slug": display.lower(),
            "logo_url": None, "color_on_light": "#0C2340", "color_on_dark": "#0C2340",
            "conference": "SEC", "classification": "fbs", "is_fbs": True,
            "games_counted": 8,
            "rushing_yards_for_per_game": 111.1, "passing_yards_for_per_game": 222.2,
            "total_yards_for_per_game": 333.3,
            "rushing_yards_allowed_per_game": 144.4,
            "passing_yards_allowed_per_game": 255.5,
            "total_yards_allowed_per_game": 399.9,
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

    The team name and the word "offense" sit in separate spans, so stripping tags leaves a
    double space between them and a naive substring test for "Kentucky offense" fails on a
    panel that is drawing correctly. Collapsing here means the assertions read as the
    sentence a reader sees.
    """
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


def _text(entries):
    """The panel's TEXT. Chart entries carry an altair object, not markup, and are skipped —
    what a chart asserts is its axis, and that is read from the object in `_charts`."""
    return " ".join(_plain(body) for kind, body in entries if kind != "chart")


def _charts(entries):
    """The altair charts the panel drew, in the order it drew them."""
    return [body for kind, body in entries if kind == "chart"]


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
    away_block = " ".join(b for b in blocks if "Kentucky offense" in b)
    assert away_block, "the away team's attack was never drawn"
    assert "154.4" in away_block, "Kentucky's rushing offense is missing"
    assert "84.5" in away_block, \
        "Kentucky's attack is not paired with AUBURN's rushing defense"
    assert "132.6" not in away_block, \
        "the panel paired Kentucky's offense with Kentucky's own defense — one team " \
        "described as though it were a matchup"

    home_block = " ".join(b for b in blocks if "Auburn offense" in b)
    assert home_block, "the home team's attack was never drawn"
    assert "170.8" in home_block and "132.6" in home_block, \
        "Auburn's attack is not paired with Kentucky's rushing defense"
    assert "84.5" not in home_block, \
        "the panel paired Auburn's offense with Auburn's own defense"


def test_both_directions_are_drawn(panel):
    """Marc named a comparison with two directions, and one of them is not the answer."""
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    assert "Kentucky offense" in body and "Auburn offense" in body, \
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
    assert "Auburn offense" not in body, \
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


# --- 🚨 R-590: the axis belongs to the WEEK, not to the two teams on screen ----------------------

def _domains(chart):
    """The (x, y) scale domains of one chart, read out of the compiled spec."""
    spec = chart.to_dict()
    found = {}
    for layer in spec.get("layer", [spec]):
        for channel in ("x", "y"):
            encoding = layer.get("encoding", {}).get(channel, {})
            domain = encoding.get("scale", {}).get("domain")
            if domain:
                found[channel] = [float(v) for v in domain]
    return found.get("x"), found.get("y")


def test_the_axis_comes_from_the_WEEKS_ROW_and_not_from_the_two_teams(panel):
    """🚨 THE ASSERTION THIS ROUND EXISTS FOR.

    Marc: "I'd like to standardize axis across all the FBS matchups for the week." The limits
    come from srv_team_week_metric_distribution, which every matchup in the week reads the same
    row of.

    ⚠️ THE FIXTURE MAKES THE TWO SOURCES DISAGREE ON PURPOSE. The teams' own values are 154.4
    and 84.5; the week's rushing axis is 50–350 for `_for` and 60–240 for `_allowed`. A panel
    that derived its limits from the two teams present could not produce those numbers, and a
    panel that ignored the row entirely would produce something near the teams' own range —
    which would look perfectly reasonable on this one game and be wrong across the week.
    """
    entries, _ = panel(_game(), _both())
    charts = _charts(entries)
    assert charts, "the panel drew no charts"
    x_domain, y_domain = _domains(charts[0])
    assert y_domain == [50.0, 350.0], \
        f"the y axis is not the week's rushing_yards_for frame: {y_domain}"
    assert x_domain == [60.0, 240.0], \
        f"the x axis is not the week's rushing_yards_allowed frame: {x_domain}"


def test_TWO_DIFFERENT_MATCHUPS_IN_A_WEEK_GET_THE_SAME_FRAME(panel):
    """⚠️ THE CLAIM IS ABOUT TWO GAMES AND SO IS THE TEST.

    One game cannot demonstrate a shared axis: any limits at all look fine on a single chart.
    Two different fixtures, the same week, and the frames must be identical — which they are
    only because both read the week's row rather than their own values.

    ⚠️ THE SECOND PAIR USED TO READ 402/31/12/498, EVERY ONE OF WHICH IS OUTSIDE WEEK 12's OWN
    LIMITS ([50, 350] for `_for`, [60, 240] for `_allowed`). R-601 drops a chart whose point
    the frame cannot hold, so those values stopped producing a rushing chart to compare and
    this test began reading the PASSING chart's domain against the rushing one. The contrast
    they existed for is intact: 330 against 60 is still nowhere near `_both()`'s 170.8 and
    154.4, so a panel deriving its limits from the two teams on screen would still produce a
    visibly different frame from the week's [50, 350].
    """
    first, _ = panel(_game(), _both())
    other = [_side(HOME_ID, "Auburn", rushing_yards_for_per_game=330.0,
                   rushing_yards_allowed_per_game=65.0),
             _side(AWAY_ID, "Kentucky", rushing_yards_for_per_game=60.0,
                   rushing_yards_allowed_per_game=235.0)]
    second, _ = panel(_game(), other)
    assert _domains(_charts(first)[0]) == _domains(_charts(second)[0]), \
        "two matchups in the same week were drawn on different axes"


def test_the_distribution_is_keyed_on_season_type_as_well_as_week(panel):
    """🚨 `week` ALONE IS NOT A KEY. A092's crude check returned 12 rows for `week = 1` and
    every one was POSTSEASON — bowl games with eleven or twelve played, a real distribution
    that would draw bowl numbers on a September page and look plausible doing it."""
    _, seen = panel(_game(week=10), _both())
    assert seen["axis_params"]["week"] == 10
    assert seen["axis_params"]["season"] == 2025
    assert seen["axis_params"]["season_type"] == "regular"


def test_the_axis_query_reads_one_relation_and_computes_nothing(panel):
    """G-1/G-2/G-3 on the second relation this panel now reads."""
    _, seen = panel(_game(), _both())
    sql = seen["axis_sql"].lower()
    assert sql.count(" from ") == 1
    for banned in ("join", "group by", "sum(", "avg(", "stddev(", "over ("):
        assert banned not in sql, f"the axis query contains `{banned}`"


def test_the_page_does_not_divide_anywhere(panel):
    """🚨 A092 MOVED THE PER-GAME DIVISION INTO THE MART SO THERE IS EXACTLY ONE OF IT.

    Two copies of `yards / games_counted` would let the axis disagree with the point drawn on
    it, and that reads to a viewer as a rendering fault rather than a metric one. Asserted on
    the source of the chart code, because the defect is an operator rather than an output.
    """
    block = SOURCE[SOURCE.index("def _week_distribution("):SOURCE.index("def _yardage_column(")]
    assert "games_counted" not in block, \
        "the chart code touches games_counted, which is the mart's arithmetic"
    assert "/" not in block.replace("__", "").replace("# ", ""), \
        "the chart code contains a division"


# --- R-522: away on the left, home on the right -------------------------------------------------

def test_the_AWAY_column_is_drawn_before_the_HOME_column(panel):
    """⚠️ POSITIONAL, NOT PRESENCE — spec §0 is a page law and both blocks are on the page
    either way round. B082 proved a presence assertion passes this swap on the game header and
    B083 proved it again on the win-probability bar.

    The away block is written first, so it is the first markdown the panel emits.
    """
    entries, _ = panel(_game(), _both())
    blocks = [_plain(b) for kind, b in entries
              if kind == "markdown" and "offense against" in _plain(b)]
    assert len(blocks) == 2, f"expected two direction blocks, got {len(blocks)}"
    assert "Kentucky offense" in blocks[0], "the away side is not in the left column"
    assert "Auburn offense" in blocks[1], "the home side is not in the right column"


def test_each_columns_charts_belong_to_that_columns_team(panel):
    """The three away charts come before the three home charts, and each names its own team.

    ⚠️ A chart titled for the wrong side renders perfectly, which is why the title is read
    rather than merely counted.
    """
    entries, _ = panel(_game(), _both())
    charts = _charts(entries)
    assert len(charts) == 6, f"expected three charts per column, got {len(charts)}"
    away_y = charts[0].to_dict()
    titles = str(away_y)
    assert "Kentucky gained" in titles, "the left column's y axis is not the away team's"
    assert "Auburn allowed" in titles, "the left column's x axis is not the home team's"
    home = str(charts[3].to_dict())
    assert "Auburn gained" in home and "Kentucky allowed" in home, \
        "the right column's axes are not the home team's attack"


def test_the_axis_labels_say_GAINED_and_ALLOWED(panel):
    """⚠️ A chart whose axes both read "yards" explains nothing. Marc's comparison is offense
    against defense, so one axis is what a side gains and the other is what the other side
    concedes — and the labels have to carry that or the picture is unreadable."""
    entries, _ = panel(_game(), _both())
    spec = str(_charts(entries)[0].to_dict())
    assert "gained" in spec and "allowed" in spec


# --- R-590 §3.4: a thin sample is a property and the page says so ------------------------------

def test_a_THIN_WEEK_says_a_per_game_figure_is_nearly_one_afternoon(panel):
    """🚨 A092 MEASURED IT AND TOLD COWORK TO TELL ME. At 2026 week 2 the least-played team
    has ONE counted game, so its "per game" IS that game — stddev 139.2 against 59.0 at 2025
    week 12. Presenting that as season form is the overclaim B077 removed from the leaders
    panel by deleting the word "led"."""
    entries, _ = panel(_game(), _both(), distribution=_distribution(min_games=1))
    text = _text(entries)
    assert "1 counted game" in text
    assert "single afternoon" in text


def test_a_SETTLED_WEEK_does_not_carry_the_caveat(panel):
    """The caveat is a measurement, not decoration: at nine games it is false and absent."""
    assert "single afternoon" not in _text(panel(_game(), _both())[0])


def test_the_shared_frame_is_explained_once_for_both_columns(panel):
    """The band and the medians are properties of the WEEK, so they are described once rather
    than implied per chart."""
    text = _text(panel(_game(), _both())[0])
    assert "136 FBS teams" in text
    assert "same axes" in text


def test_NO_DISTRIBUTION_draws_no_charts_and_says_WHICH_absence(panel):
    """⚠️ ABSENT, NOT AN EMPTY FRAME (AC-G.11, B075's rule).

    A092: 136 FBS teams carry a regular-season week-1 row and ZERO carry a value, so the model
    emits nothing for it. An axis with no points is a chart that looks broken; saying the
    week has no distribution is a statement.
    """
    entries, _ = panel(_game(), _both(), distribution=[])
    assert _charts(entries) == [], "charts were drawn with no week distribution to draw them on"
    text = _text(entries)
    assert "No week-wide distribution" in text
    assert "154.4" in text, "the panel stopped drawing its figures along with its charts"


# --- 🚨 R-594: the POINT, which B084 never asserted ---------------------------------------------

def _point(chart):
    """The plotted coordinate, out of the compiled spec's own datasets."""
    spec = chart.to_dict()
    for values in spec.get("datasets", {}).values():
        if values and "who" in values[0]:
            return values[0]["x"], values[0]["y"]
    raise AssertionError("the chart drew no point")


def test_the_point_is_the_TEAMS_OWN_VALUE_not_zero(panel):
    """🚨 THE ASSERTION B084 DID NOT HAVE, AND MARC FOUND ITS ABSENCE BEFORE A TEST DID.

    B084 verified its AXES — identical across two matchups, which was its claim — and never
    once quoted a plotted value. ⚠️ A round can prove exactly what it set out to prove and
    ship a defect in the same panel, and the only defense is asserting the thing a reader
    actually looks at.

    Kentucky gain 154.4 on the ground and Auburn allow 84.5, so the away column's rushing
    point is (84.5, 154.4) — the opponent's allowed on x, this team's gained on y.
    """
    entries, _ = panel(_game(), _both())
    x, y = _point(_charts(entries)[0])
    assert y == 154.4, f"the y value is not the away team's rushing figure: {y}"
    assert x == 84.5, f"the x value is not the home team's rushing allowed: {x}"
    assert y != 0 and x != 0


def test_every_one_of_the_six_charts_plots_a_real_value(panel):
    """Not one chart — all six. A single correct point would have passed B084's gap too."""
    entries, _ = panel(_game(), _both())
    charts = _charts(entries)
    assert len(charts) == 6
    for index, chart in enumerate(charts):
        x, y = _point(chart)
        assert x not in (0, None) and y not in (0, None), \
            f"chart {index} plotted at ({x}, {y})"


def test_a_GENUINE_zero_still_draws_because_it_is_a_datum(panel):
    """⚠️ THE OTHER HALF, AND THE PROMPT WAS EXPLICIT: "DO NOT fix it by filtering zeros."

    Measured across every season: 13,728 srv_team_week rows carry a counted game, and exactly
    TWO have a zero per-game figure — both rushing, both plausible. A team that genuinely
    gained nothing is a measurement, and suppressing it would trade a visible defect for an
    invisible one.

    ⚠️ THE FRAME HAS TO CONTAIN ZERO FOR THIS TO MEAN ANYTHING, AND R-601 IS WHY THIS TEST
    NOW SAYS SO. It used to run on week 12's axis of [50, 350], where 0.0 is BELOW the floor
    — so what it actually asserted was that the panel draws a point outside its own chart,
    which is the defect this round found. 2026 regular week 2 carries `axis_min` = 0.0 for
    `rushing_yards_for_per_game`, measured, so a genuine zero is both a datum AND plottable
    there. On a week whose floor is above zero the chart is dropped and captioned instead,
    which `test_a_figure_OFF_the_weeks_scale_...` covers.
    """
    sides = [_side(HOME_ID, "Auburn"), _side(AWAY_ID, "Kentucky",
                                             rushing_yards_for_per_game=0.0)]
    entries, _ = panel(_game(), sides,
                       distribution=_distribution(
                           axes={"rushing_yards_for_per_game": (0.0, 600.0)}))
    x, y = _point(_charts(entries)[0])
    assert y == 0.0, "a genuine zero was suppressed rather than drawn"


def test_a_NULL_per_game_figure_draws_NO_chart_rather_than_a_zero(panel):
    """Null and zero are different facts. The chart is absent for a null, not plotted at 0."""
    sides = [_side(HOME_ID, "Auburn"), _side(AWAY_ID, "Kentucky",
                                             rushing_yards_for_per_game=None)]
    entries, _ = panel(_game(), sides)
    assert len(_charts(entries)) == 5, "a null figure was drawn as a point"


# --- 🚨 R-601: a frame that cannot hold its own point ------------------------------------------
#
# WHAT B084 AND B085 EACH PROVED, AND WHAT NEITHER DID. B084 asserted the AXES and never a
# plotted value; Marc found that gap before a test did. B085 added the coordinate — "is it
# zero?" — and answered no on sixty charts. ⚠️ BOTH QUESTIONS CAN PASS WHILE THE POINT IS NOT
# ON THE CHART, because the third question is WHERE IN THE FRAME the coordinate lands, and
# nothing asked it.
#
# 🚨 MEASURED 2026-09-11, AND IT IS SHIPPED. srv_team_week_metric_distribution reports
# n = teams_in_week = 138 for every 2026 week; srv_team_week carries 658 teams in each of
# those weeks. The axis is built from the FBS spread and the panel plots any team an FBS side
# schedules, so 26 distribution rows in 2026 already hold at least one team beyond their own
# limits. Game 401868264 — Marist at Stetson, week 5 — renders it: Stetson allow 393.0 rushing
# yards per game on an axis of [-50, 350], and the point draws in the chart's right margin,
# outside the plotting rectangle, past the last tick.


def _frame_of(chart, channel):
    """The (min, max) the chart's own spec says that channel is drawn on."""
    spec = chart.to_dict()
    for layer in spec.get("layer", [spec]):
        domain = layer.get("encoding", {}).get(channel, {}).get("scale", {}).get("domain")
        if domain:
            return float(domain[0]), float(domain[1])
    raise AssertionError(f"the chart declares no {channel} domain")


def test_every_plotted_point_lands_INSIDE_the_frame_it_is_drawn_on(panel):
    """🚨 THE QUESTION B084 AND B085 BOTH LEFT: not "is it zero" but "is it ON the chart".

    ⚠️ `alt.Scale(domain=…, nice=False)` BOUNDS THE AXIS, NOT THE MARK. Vega-Lite keeps
    drawing a point whose coordinate falls outside the domain; it simply lands outside the
    plotting rectangle. So the failure is not an error, an empty frame or a zero — it is a
    complete-looking chart with its point somewhere else, which reads as "nothing remarkable
    here".
    """
    entries, _ = panel(_game(), _both())
    charts = _charts(entries)
    assert len(charts) == 6
    for index, chart in enumerate(charts):
        x, y = _point(chart)
        x_low, x_high = _frame_of(chart, "x")
        y_low, y_high = _frame_of(chart, "y")
        assert x_low <= x <= x_high, \
            f"chart {index}: x={x} is outside its own frame [{x_low}, {x_high}]"
        assert y_low <= y <= y_high, \
            f"chart {index}: y={y} is outside its own frame [{y_low}, {y_high}]"


def test_a_figure_OFF_the_weeks_scale_draws_no_chart_rather_than_a_point_beside_one(panel):
    """⚠️ THE FIXTURE IS THE MEASURED GAME, NOT AN INVENTED ONE (R-594's lesson from B082).

    Stetson's real week-5 figure is 393.0 rushing yards allowed per game and the week's real
    `rushing_yards_allowed_per_game` axis is [-50, 350] — both read out of live serving on
    2026-09-11. The away column's rushing chart pairs Marist's `_for` against that `_allowed`,
    so it is the x value that leaves the frame.

    🚨 SKIPPING IT LOSES NO MEASUREMENT. `_yardage_direction` prints both figures as text
    directly above, so what is dropped is a picture that could not be honest — not a number.
    """
    sides = [_side(HOME_ID, "Stetson", rushing_yards_allowed_per_game=393.0),
             _side(AWAY_ID, "Marist")]
    entries, _ = panel(_game(), sides,
                       distribution=_distribution(
                           axes={"rushing_yards_allowed_per_game": (-50.0, 350.0)}))
    charts = _charts(entries)
    titles = [c.to_dict().get("title") for c in charts]
    assert titles.count("Rushing") == 1, (
        f"the away column's rushing chart was drawn with a point off its own frame: {titles}")


def test_the_dropped_chart_SAYS_it_was_dropped_rather_than_going_quiet(panel):
    """AC-G.11. A chart missing from a row of three, with nothing said, reads as "we hold
    nothing" — and we hold the figure and printed it one line above."""
    sides = [_side(HOME_ID, "Stetson", rushing_yards_allowed_per_game=393.0),
             _side(AWAY_ID, "Marist")]
    entries, _ = panel(_game(), sides,
                       distribution=_distribution(
                           axes={"rushing_yards_allowed_per_game": (-50.0, 350.0)}))
    body = _text(entries)
    assert "not plotted" in body, "a chart vanished without the page saying so"
    assert "Rushing" in body


def test_the_guard_does_NOT_suppress_a_point_that_merely_sits_low(panel):
    """🚨 THE OTHER HALF, AND MARC'S TWO GAMES ARE EXACTLY THIS STATE.

    401856679 and 401856782 are both 2026 regular week 2, and Michigan's 106.0 rushing yards
    per game sits on an axis of [0, 600] — 17.7% up a frame 150px tall, or 26 pixels off the
    floor. ⚠️ THAT IS LOW, AND IT IS NOT OFF THE FRAME. A guard that removed it would delete
    the very charts Marc is asking about and call the page fixed.
    """
    sides = [_side(HOME_ID, "Michigan", rushing_yards_allowed_per_game=112.0),
             _side(AWAY_ID, "Oklahoma", rushing_yards_for_per_game=106.0)]
    entries, _ = panel(_game(), sides,
                       distribution=_distribution(
                           axes={"rushing_yards_for_per_game": (0.0, 600.0)}))
    charts = _charts(entries)
    assert len(charts) == 6, "a low-but-valid point was suppressed"
    x, y = _point(charts[0])
    assert y == 106.0
    y_low, y_high = _frame_of(charts[0], "y")
    fraction = (y - y_low) / (y_high - y_low)
    assert fraction < 0.20, (
        "this fixture is meant to reproduce the bottom-fifth position Marc reported; "
        f"it landed at {fraction:.1%}")


# --- 🚨 R-603: the scale that is DRAWN, not the numbers that went into it -----------------------
#
# 🚨 FOUR ROUNDS ASSERTED SOMETHING TRUE ABOUT THIS PANEL AND SHIPPED IT BROKEN.
#
#   B084  the axes are shared across a week      never quoted a plotted value
#   B085  the coordinate is not zero, 60 charts  never asked where the coordinate lands
#   B086  the position in the frame, 17.7%       computed from the DECLARED domain
#   A097  the position moved to 26.5%            same measurement, same blindness
#
# ⚠️ EVERY ONE OF THOSE PASSES ON THE CHART IN MARC'S SCREENSHOT, because all four read
# `chart.to_dict()` — and the property that broke the scale is added AFTER altair is finished,
# by Streamlit, on the way to the browser:
#
#     _prepare_vega_lite_spec:  if "autosize" not in spec:  spec["autosize"] = {"type": "fit"}
#
# `fit` makes `height` the OUTER box. Vega-Lite subtracts the title, the x-axis labels, the
# x-axis title and the padding from 150px and gives the y scale the remainder — which on a
# reader whose text renders larger is nearly nothing. Rasterised at a larger base font, that
# spec reproduces the screenshot exactly: y title clipped to "lahoma gain", one stray y tick,
# the band flattened to a sliver, the point sitting on the median rule whatever its value, the
# chart title gone off the top, and a perfect x axis.
#
# ⚠️ SO THESE TESTS GO THROUGH STREAMLIT'S OWN FUNCTION rather than reading the altair spec.
# It is a private function and that is a real coupling; it is also the only thing that answers
# "what does the browser receive". If Streamlit moves it these tests fail loudly rather than
# skipping, which is correct — the fix's premise would have changed.

def _shipped(chart):
    """The spec Streamlit actually sends for `st.altair_chart(chart, use_container_width=True)`."""
    from streamlit.elements.vega_charts import _prepare_vega_lite_spec
    return _prepare_vega_lite_spec(chart.to_dict(), True)


def _plot_height(spec):
    """The height the Y SCALE actually gets, under this spec's own autosize semantics.

    🚨 THIS IS THE WHOLE DISTINCTION THE ROUND IS ABOUT. With `fit`, `height` is the outer box
    and the plot gets whatever the chrome leaves — unknowable here and demonstrably near zero
    in the wild. With `fit-x`, `pad` or `none`, `height` is the plot and the chrome is added
    outside it.
    """
    kind = (spec.get("autosize") or {}).get("type")
    if kind == "fit":
        return None
    return float(spec["height"])


def test_the_spec_STREAMLIT_SHIPS_does_not_make_height_the_outer_box(panel):
    """🚨 THE ONE ASSERTION THAT WOULD HAVE CAUGHT MARC'S SCREENSHOT.

    Streamlit fills `autosize` in only when the spec does not declare one, so the panel
    declaring `fit-x` is what keeps `height=150` meaning the plot. Streamlit's own comment
    beside that branch says `fit` "does not work for many chart types" and that "fit-x fits the
    width and height can be adjusted".
    """
    entries, _ = panel(_game(), _both())
    charts = _charts(entries)
    assert charts
    for index, chart in enumerate(charts):
        shipped = _shipped(chart)
        kind = (shipped.get("autosize") or {}).get("type")
        assert kind != "fit", (
            f"chart {index} ships autosize 'fit', so height={shipped.get('height')} is the "
            f"OUTER box and the y scale gets only what the title and x axis leave over")
        assert kind == "fit-x", f"chart {index} ships autosize {kind!r}, expected 'fit-x'"


def test_TWO_DIFFERENT_Y_VALUES_RENDER_AT_DIFFERENT_HEIGHTS(panel):
    """🚨 THE HEART OF IT — Oklahoma's 170.0 and Michigan's 106.0 were on the same line.

    ⚠️ THIS ASKS THE SCALE, NOT THE ROW. The two values are read back out of the shipped spec's
    own point datasets and converted through the shipped domain and the shipped plot height, so
    the test can only pass if the chart has a height to draw them in. On the defect
    `_plot_height` is unknowable and this fails rather than quietly comparing inputs.
    """
    entries, _ = panel(_game(), _both())
    charts = _charts(entries)
    # chart 0 is the away column's rushing, chart 3 the home column's — same metric, same frame.
    away, home = charts[0], charts[3]
    heights = []
    for chart in (away, home):
        shipped = _shipped(chart)
        plot = _plot_height(shipped)
        assert plot is not None, (
            "the shipped spec makes height the outer box, so no y position can be computed — "
            "which is exactly how two different values came to sit on one line")
        assert plot > 0
        _x, y = _point(chart)
        low, high = _frame_of(chart, "y")
        heights.append((y - low) / (high - low) * plot)
    assert heights[0] != heights[1], (
        f"Kentucky and Auburn rendered at the same height: {heights}")
    assert abs(heights[0] - heights[1]) > 1.0, (
        f"two values a whole metric apart rendered within a pixel: {heights}")


def test_the_middle_half_BAND_has_a_drawn_height(panel):
    """The shaded rectangle was missing from Marc's screenshot, and a rect with no height is
    not an absent band — it is a band drawn as a line, which reads as another rule."""
    entries, _ = panel(_game(), _both())
    for index, chart in enumerate(_charts(entries)):
        shipped = _shipped(chart)
        plot = _plot_height(shipped)
        assert plot, f"chart {index} has no computable plot height"
        band = None
        for values in chart.to_dict().get("datasets", {}).values():
            if values and "y2" in values[0]:
                band = values[0]
        assert band, f"chart {index} drew no band"
        low, high = _frame_of(chart, "y")
        drawn = (float(band["y2"]) - float(band["y"])) / (high - low) * plot
        assert drawn > 1.0, (
            f"chart {index}: the middle-half band is {drawn:.2f}px tall and is not a rectangle")


def test_a_DEGENERATE_y_domain_draws_nothing_rather_than_a_confident_flat_chart(panel):
    """⚠️ `alt.Scale(domain=[v, v])` IS A SCALE WITH NO EXTENT AND VEGA-LITE DOES NOT COMPLAIN.

    It draws every mark at the same height — the picture this round was reported as. A week
    whose counted teams all return one figure produces exactly that row, so the panel refuses
    it the way it refuses an off-frame point.

    🚨 THE VALUE IS 200.0 ON PURPOSE AND THE FIRST VERSION OF THIS TEST WAS NOT A TEST. It left
    Kentucky on 154.4 against a domain of [200, 200], so `_off_the_frame` refused the chart
    before `_degenerate` was ever consulted — and the staged break that deletes the degenerate
    guard PASSED GREEN. Putting the team exactly on the single point of the domain makes
    `_off_the_frame` false (200 <= 200 <= 200) and leaves `_degenerate` as the only thing that
    can refuse it, which is what this test is for.
    """
    sides = [_side(HOME_ID, "Auburn", rushing_yards_allowed_per_game=84.5),
             _side(AWAY_ID, "Kentucky", rushing_yards_for_per_game=200.0)]
    entries, _ = panel(_game(), sides,
                       distribution=_distribution(
                           axes={"rushing_yards_for_per_game": (200.0, 200.0)}))
    titles = [c.to_dict().get("title") for c in _charts(entries)]
    assert titles.count("Rushing") == 0, (
        f"a scale with no extent was drawn as a chart: {titles}")


# --- 🚨 R-608: the box's sides carry which percentile they are ---------------------------------

def _edge_weights(chart):
    """Each box-edge rule's (percentile value, strokeWidth), from the compiled spec.

    The edges are the `rule` layers that carry a strokeWidth — the two medians are dashed and
    set none, and the shaded box is a `rect`.
    """
    spec = chart.to_dict()
    datasets = spec.get("datasets", {})
    out = []
    for layer in spec.get("layer", []):
        mark = layer.get("mark", {})
        if mark.get("type") != "rule" or mark.get("strokeWidth") is None:
            continue
        name = layer.get("data", {}).get("name")
        values = (datasets.get(name) or [{}])[0]
        # A vertical edge is pinned by x and spans y2; a horizontal one is the reverse.
        value = values.get("x") if "y2" in values else values.get("y")
        out.append((value, float(mark["strokeWidth"])))
    return out


def test_the_bands_p25_and_p75_sides_have_DIFFERENT_line_weights(panel):
    """🚨 THIS TEST EXISTS BECAUSE ITS STAGED BREAK WENT GREEN WITHOUT IT.

    Marc: "Use a thinner line for the sides that represent 25th percentile, thicker (maybe
    double line) for the 75th percentile." Giving both sides one weight renders a perfectly
    tidy box that says nothing — and nothing in the suite noticed until the break was run.

    ⚠️ WEIGHT IS THE CARRIER, NOT COLOUR, and that is AC-G.22: a line weight survives
    greyscale and colour-blindness. So the assertion is on `strokeWidth`, which is the
    property doing the work.
    """
    entries, _ = panel(_game(), _both())
    weights = _edge_weights(_charts(entries)[0])
    assert len(weights) == 4, f"the box does not have four drawn sides: {weights}"

    low, high = _METRICS["rushing_yards_for_per_game"][2], \
        _METRICS["rushing_yards_for_per_game"][4]
    x_low, x_high = _METRICS["rushing_yards_allowed_per_game"][2], \
        _METRICS["rushing_yards_allowed_per_game"][4]
    thin = {w for value, w in weights if value in (low, x_low)}
    thick = {w for value, w in weights if value in (high, x_high)}
    assert thin and thick, f"could not match sides to percentiles: {weights}"
    assert thin != thick, (
        f"the 25th and 75th percentile sides are drawn at the same weight, so the box says "
        f"nothing about which side is which: {weights}")
    assert max(thick) > max(thin), (
        f"the 75th percentile side is not the THICKER one: thin={thin} thick={thick}")


def test_the_caption_SAYS_which_side_is_which(panel):
    """⚠️ A THIN LINE AND A THICK LINE ARE ONLY SELF-DESCRIBING IF SOMETHING SAYS SO.

    The weights are meaningless to a reader who has not been told the convention, so the
    sentence that already explains the shaded box explains its sides too.
    """
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    assert "thin" in body and "thick" in body, \
        f"the caption does not explain the two line weights: {body}"
    assert "25th percentile" in body and "75th" in body, \
        f"the caption does not name the percentiles: {body}"
