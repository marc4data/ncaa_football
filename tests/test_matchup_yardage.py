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
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_harness  # noqa: E402

# ⚠️ IMPORTED HERE, BEFORE ANY STUB IS INSTALLED, AND `_shipped` SAYS WHY. Inside
# `streamlit_stubbed` the name `streamlit` is a plain module and this import cannot resolve.
from streamlit.elements.vega_charts import _prepare_vega_lite_spec  # noqa: E402

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()


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


def _deltas(**overrides):
    """R-686's three deltas for both sides, at game x team grain.

    ⚠️ MEASURED, NOT INVENTED — srv_game_team for 401856679 on 2026-09-12. Oklahoma's offense
    runs ahead of Michigan's defense on all three; Michigan's rushing is NEGATIVE, which is the
    case the sign and the colour both have to carry.
    """
    # 🚨 `is_home` IS IN THIS FIXTURE SINCE R-731 AND WITHOUT IT THE MIRROR IS NOT TESTED AT
    # ALL. `_GAME_TEAM_COLUMNS` has always selected it, so the real frame carries it; the
    # fixture did not, and `_is_home_side` therefore read False for BOTH sides — which made
    # both columns take the away order while all 52 tests here still passed.
    # ⚠️ THAT IS THE FIXTURE FAILURE THIS PROJECT KEEPS FINDING, caught this time by asking
    # what the fixture could NOT distinguish rather than by a red test.
    rows = [
        {"team_id": AWAY_ID, "is_home": False,
         "rushing_yards_for_minus_opponent_allowed_per_game": 38.0,
         "passing_yards_for_minus_opponent_allowed_per_game": 142.0,
         "total_yards_for_minus_opponent_allowed_per_game": 180.0},
        {"team_id": HOME_ID, "is_home": True,
         "rushing_yards_for_minus_opponent_allowed_per_game": -6.0,
         "passing_yards_for_minus_opponent_allowed_per_game": 84.0,
         "total_yards_for_minus_opponent_allowed_per_game": 78.0},
    ]
    for row in rows:
        row.update(overrides)
    return rows


# The label/format trio each panel carries, measured live from
# `srv_game_team_leader_through_prior_week` on 2026-09-13. ⚠️ THE FORMATS ARE THE VIEW'S OWN
# WORDS — `integer`, `decimal_1`, `pair` — and a test below reads them out of the model source
# rather than trusting this copy.
_PANEL_STATS = {
    "rushing": (("Carries", "integer"), ("Yards", "integer"), ("Yds/Carry", "decimal_1")),
    "passing": (("Receptions", "integer"), ("Yards", "integer"), ("TD", "integer")),
    "total": (("Comp-Att", "pair"), ("Yards", "integer"), ("TD", "integer")),
}


def _usage(players=None, games=3, window=None, skip=()):
    """R-694's game dots: one row per (team, panel, player, EARLIER game).

    ⚠️ BUILT FROM THE LEADERS SO THE TWO FRAMES AGREE ON `player_id`, which is the key the card
    joins them on. `skip` drops a player from the usage frame entirely — the "we hold nothing
    for him" absence that Ben McCreary is on the live game.
    """
    rows = []
    for leader in (players if players is not None else _leaders()):
        if leader["player_id"] in skip:
            continue
        observed = window if window is not None else games
        for index in range(games):
            if index >= observed:
                continue
            rows.append({
                "team_id": leader["team_id"], "panel": leader["panel"],
                "player_id": leader["player_id"],
                "usage_game_id": 900 + index,
                # ⚠️ THE REGULAR SEASON IS ORDINAL 1; the postseason row below is 2, and a sort
                # on `usage_week` alone would put it first because bowl weeks restart at 1.
                "usage_season_type_ordinal": 1, "usage_week": index + 1,
                "usage_total": 0.10 + 0.05 * index,
                "usage_total_max_in_window": 0.10 + 0.05 * (observed - 1),
                "usage_games_in_window": observed})
    return rows


def _leaders(**overrides):
    """R-687's leaders through the prior week, measured from 401856679 on 2026-09-12.

    ⚠️ MICHIGAN'S `total` PANEL IS ONE NAME AND THAT IS CORRECT — one quarterback has thrown,
    `qualified_players` is 1, and a card that padded it to three would invent players.
    """
    rows = []
    for team_id, panel, metric, names in (
        (AWAY_ID, "rushing", "rushing_yards",
         [("Lloyd Avant", 79, 9, "RB", "JR"), ("Ben McCreary", 40, 23, "RB", "SR"),
          ("Xavier Robinson", 30, 21, "RB", "JR")]),
        (AWAY_ID, "passing", "receiving_yards",
         [("Isaiah Sategna", 76, 1, "WR", "SR"), ("Trell Harris", 61, 11, "WR", "SR"),
          ("Rocky Beers", 43, 81, "TE", "SR")]),
        (AWAY_ID, "total", "quarterback_total_yards",
         [("John Mateer", 232, 10, "QB", "SR")]),
        (HOME_ID, "rushing", "rushing_yards",
         [("Bryce Underwood", 47, 19, "QB", "SO")]),
        (HOME_ID, "passing", "receiving_yards",
         [("JJ Buchanan", 126, 6, "WR", "SO")]),
        (HOME_ID, "total", "quarterback_total_yards",
         [("Bryce Underwood", 217, 19, "QB", "SO")]),
    ):
        for rank, (name, yards, jersey, position, year) in enumerate(names, start=1):
            # 🚨 R-733: THE THREE KPIs COME OFF THE ROW NOW, and their LABELS vary by panel —
            # A116's shape, measured live. `yards` stays in slot 2 because that is where the
            # view puts it, so every assertion written against the old single KPI still means
            # the same thing.
            (l1, f1), (l2, f2), (l3, f3) = _PANEL_STATS[panel]
            rows.append({
                "team_id": team_id, "panel": panel, "leader_metric": metric,
                "leader_rank": rank, "tied_players": 1, "qualified_players": len(names),
                "player_id": f"p{team_id}{rank}{panel[:2]}",
                "player_name": name, "player_slug": name.lower().replace(" ", "-"),
                "jersey": jersey, "position": position, "class_year_display": year,
                "stat_1_label": l1, "stat_1_format": f1,
                "stat_1_value": 51.0 if f1 == "pair" else 9.0,
                "stat_1_value_secondary": 75.0 if f1 == "pair" else None,
                "stat_2_label": l2, "stat_2_format": f2,
                "stat_2_value": float(yards), "stat_2_value_secondary": None,
                "stat_3_label": l3, "stat_3_format": f3,
                "stat_3_value": 5.2 if f3 == "decimal_1" else 2.0,
                "stat_3_value_secondary": None})
    for row in rows:
        row.update(overrides)
    return rows


_DISTRIBUTION = _distribution()


@pytest.fixture
def panel(request):
    """The panel with streamlit captured and the database replaced by constructed rows.

    ⚠️ IT PUTS THE MODULES BACK. Reloading lib.states against a stub binds the stub inside it
    for the REST OF THE SESSION — test_matchup_drives learned that the hard way and six
    unrelated tests failed. `monkeypatch` cannot undo it either: its sys.modules restore runs
    after this teardown, so the swap and the restore are both done by hand here.

    🚨 ON THE SHARED HARNESS SINCE R-613, AND THIS FILE IS THE REASON THE ROUND EXISTS. It
    rolled its own stub, which is why B092's guard had to read DRAWN MARKUP rather than hook
    the harness: a harness-level check would have covered two files of nine and missed this
    one — the file where B091's `deltas or {}` actually hid.

    ⚠️ THE RESTORE THIS DOCSTRING DESCRIBES BY HAND IS `streamlit_stubbed`'s JOB, and it does
    both halves — sys.modules and the parent-package attribute (A101).
    """
    import importlib
    # 🚨 R-705(2). `streamlit_stubbed` ENFORCES ON EXIT NOW, and the exemption is declared
    # here rather than granted to the file. A112 added that enforcement temporarily, ran the
    # full suite, and exactly one test failed — the one below that renders a card ON PURPOSE.
    # A reverted the harness byte-identically rather than landing it, because turning another
    # session's suite red for something that is not a defect is what §3 rule 3.1 prevents.
    #
    # ⚠️ IT IS PER-TEST, NOT PER-FILE. Exempting the fixture outright would take the guard off
    # all fifty-two tests in here to serve one, which is a blind spot wearing an exemption's
    # clothes. `indirect=True` hands the flag to the ONE test that needs it, and that test
    # says why in its own decorator.
    allow_error_state = getattr(request, "param", False)
    with render_harness.streamlit_stubbed(
            allow_error_state=allow_error_state) as (_st, captured, _charts):
        matchup = importlib.reload(importlib.import_module("views.matchup"))
        seen = {}

        def run(game, sides, distribution=_DISTRIBUTION, deltas=None,
                leaders=None, usage=None, allow_error_state=allow_error_state):
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
                # ⚠️ R-686 MADE THIS PANEL READ A THIRD RELATION, and the stub dispatches on the
                # SQL rather than answering everything with the same frame. `srv_game_team` is
                # game × team grain; the figures beside it are week grain on `srv_team_week`.
                # 🚨 R-694 DISPATCHES FIRST AND THE ORDER IS NOT COSMETIC.
                # "srv_game_team_leader_usage" CONTAINS "srv_game_team", so a later branch
                # would answer the dots query with the DELTAS frame — which is how this stub
                # first reported the panel as raising rather than as mis-stubbed.
                if "srv_game_team_leader_usage" in sql:
                    seen["usage_sql"], seen["usage_params"] = sql, params or {}
                    return pd.DataFrame(usage if usage is not None else _usage())
                if "srv_game_team_leader_through_prior_week" in sql:
                    seen["leader_sql"] = sql
                    return pd.DataFrame(leaders if leaders is not None else _leaders())
                if "srv_game_team" in sql:
                    seen["delta_sql"], seen["delta_params"] = sql, params or {}
                    return pd.DataFrame(deltas if deltas is not None else _deltas())
                seen["sql"], seen["params"] = sql, params or {}
                return pd.DataFrame(sides)

            matchup.query = fake_query
            matchup._yardage(pd.Series(game))
            # 🚨 R-610, AND THIS IS THE FILE THAT MAKES THE CASE. B091 shipped `deltas or {}` into
            # `_delta_for`; `Series.__bool__` RAISES; `states.section` caught it and drew an Error
            # card — and every assertion in this file passed, because they all read the entries a
            # panel EMITS and a dead panel emits exactly one card. The LIVE RENDER found it.
            #
            # ⚠️ THE GUARD READS WHAT WAS DRAWN rather than how the stub was built, because seven
            # of the nine matchup files roll their own and a harness-only check would have covered
            # two of them — missing the one bug it is named for.
            render_harness.assert_no_error_card(captured, "the yardage panel",
                                                allow_error_state)
            return list(captured.events), dict(seen)

        yield run


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


@pytest.mark.parametrize("panel", [True], indirect=True)
def test_a_broken_row_degrades_this_panel_and_not_the_page(panel):
    """states.section is the blast wall. The panel must not take Matchup down with it.

    ✅ THE EXEMPTION IS DECLARED BECAUSE PROVING THE ERROR CARD FIRES IS THIS TEST'S ENTIRE
    JOB. R-610 makes an Error state fatal by default precisely so a panel cannot die
    unnoticed; the one test that renders one on purpose says so, which is the difference
    between an exemption and a blind spot.

    ⚠️ THE `indirect=True` PARAMETER IS THE DECLARATION SINCE R-705(2), and it reaches BOTH
    guards — `assert_no_error_card` inside the run and `streamlit_stubbed`'s new check on
    exit. One statement, so the two cannot disagree about whether this test is exempt.
    """
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


def test_the_CHART_CODE_does_not_divide(panel):
    """🚨 A092 MOVED THE PER-GAME DIVISION INTO THE MART SO THERE IS EXACTLY ONE OF IT.

    ⚠️ RENAMED IN B092 (R-611), AND THE OLD NAME WAS A CLAIM THE TEST NEVER MADE. It was
    `test_the_page_does_not_divide_anywhere`, and it is scoped to the source between
    `def _week_distribution(` and `def _yardage_column(` — the chart code, nothing else. The
    docstring was always honest; the NAME was not, and B091's own report cited it three times
    as though it guarded the page.

    🚨 THE PAGE DOES DIVIDE: `site/views/players.py:202` renders
    `f"{int(made)}/{int(attempted)} ({made / attempted * 100:.0f}%)"` — a ratio of TWO COLUMNS
    computed in the page. That is session A's file and B092 reported it rather than touching it.


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
    """The spec Streamlit actually sends for `st.altair_chart(chart, use_container_width=True)`.

    🚨 THE IMPORT IS AT THE TOP OF THIS FILE AND THAT IS THE FIX, NOT A TIDY-UP. It used to sit
    HERE, inside the function, and the function only ever runs inside `streamlit_stubbed` —
    where `sys.modules["streamlit"]` is a plain module rather than a package, so
    `streamlit.elements.vega_charts` cannot be imported through it.

    ⚠️ IT PASSED ANYWAY, because some earlier test in this file had already cached the real
    submodule. Measured on `origin/main`: run this test ALONE and it fails with
    `ModuleNotFoundError: 'streamlit' is not a package`. **The 1:1 guarantee B091 fought four
    rounds for was one test-selection away from not being asserted at all** — R-639's class, and
    it was pre-existing rather than introduced by this round.
    """
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
        # ⚠️ THE ASSERTION IS THE DANGER, NOT ONE PARTICULAR SAFE ANSWER. B087 wrote this as
        # `== "fit-x"` when that was the only safe value in play; R-609 needs `pad`, because a
        # 1:1 chart has to pin BOTH dimensions and `fit-x` gives the width to the container by
        # construction. Both leave `height` meaning the plot, which is the whole claim — so
        # the safe set is named rather than the one member that happened to be in use.
        assert kind in ("fit-x", "pad"), (
            f"chart {index} ships autosize {kind!r}; the safe values are 'fit-x' (width "
            f"follows the column) and 'pad' (both dimensions pinned, which 1:1 requires)")


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


# --- 🚨 R-687: the player cards, and the four states A106 measured ------------------------------

def test_the_leaders_come_from_the_THROUGH_PRIOR_WEEK_view(panel):
    """🚨 TWO VIEWS, TWO WINDOWS, AND NOTHING BUT THIS STANDS BETWEEN THEM.

    `srv_game_team_leader` answers who led IN this game, from its own box score.
    `srv_game_team_leader_through_prior_week` answers who leads GOING IN. On a preview the
    first does not exist yet, and on a completed game the two are different facts about
    different windows — so reading the short name here would put post-game numbers on a
    pre-game card and look entirely reasonable doing it.

    ⚠️ A102 SPENT A WHOLE ROUND on two near-identically-named COLUMNS that disagreed on 83% of
    games. These are two VIEWS whose names differ by a suffix.
    """
    _entries, seen = panel(_game(), _both())
    sql = seen.get("leader_sql", "")
    assert "srv_game_team_leader_through_prior_week" in sql, \
        f"the leaders panel does not read the prior-week view: {sql}"
    assert not re.search(r"from\s+srv_game_team_leader\s", sql), \
        "the panel read the SHORT view, which answers the other window"


def test_the_PASSING_panel_shows_RECEIVERS_because_that_is_the_data(panel):
    """🚨 MARC'S PAIRING, CARRIED AS DATA RATHER THAN PROSE. The view's `leader_metric` says
    `receiving_yards` for the passing panel, and the page reads it rather than choosing. A
    round that "corrected" this to passers would be overruling him with a plausible tidy-up."""
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    # Isaiah Sategna is a WR and leads Oklahoma's receiving through the prior week.
    assert "Isaiah Sategna" in body, f"the passing panel drew no receiver: {body[:400]}"
    assert "WR" in body


def test_a_WEEK_ONE_game_says_nobody_has_yards_yet_rather_than_going_blank(panel):
    """⚠️ STATE ONE, AND IT IS NOT A FAILURE. A106: a week-1 game returns ZERO rows, because
    nobody has yards through week zero. AC-G.11 — the absence says which absence it is."""
    entries, _ = panel(_game(), _both(), leaders=[])
    body = _text(entries)
    assert "No yards recorded before this week." in body, \
        f"a week-1 game rendered nothing at all: {body[:300]}"


def test_FEWER_THAN_THREE_is_drawn_as_what_exists_and_never_padded(panel):
    """⚠️ STATE TWO. Michigan's `total` panel is ONE name on 401856679 — one quarterback has
    thrown — and `qualified_players` says so. Padding to three would invent players."""
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    assert body.count("Bryce Underwood") >= 1
    # One name in that panel, so no 2nd or 3rd place label can follow it there.
    assert "John Mateer" in body, "the away QB is missing"


def test_a_TIE_shares_its_rank_and_is_NOT_truncated_to_three(panel):
    """🚨 STATE THREE, AND TRUNCATION WOULD INVENT A WINNER. Ranks are shared, so a three-way
    tie for third returns MORE than three rows. `tied_players` is what makes "T-3rd" honest.

    🚨 THE FIXTURE CARRIES **FOUR** ROWS AND THE FIRST VERSION CARRIED THREE, WHICH IS WHY THE
    STAGED BREAK PASSED. Truncating to three cannot be detected by a three-row tie — the eighth
    time on this page that a fixture could not distinguish what it claimed to test, and the
    prompt named it in advance.
    """
    tied = [r for r in _leaders() if r["panel"] == "rushing" and r["team_id"] == AWAY_ID]
    tied.append(dict(tied[0], player_name="Tory Blaylock", jersey=4,
                     yards_through_prior_week=30.0))
    for r in tied:
        r["leader_rank"] = 2
        r["tied_players"] = 4
        r["qualified_players"] = 4
    entries, _ = panel(_game(), _both(), leaders=tied)
    body = _text(entries)
    assert "T-2nd" in body, f"a shared rank was not marked as tied: {body[:400]}"
    for name in ("Lloyd Avant", "Ben McCreary", "Xavier Robinson", "Tory Blaylock"):
        assert name in body, f"{name} was truncated out of a four-way tie"


def test_a_MISSING_JERSEY_is_an_absence_and_never_a_zero(panel):
    """🚨 STATE FOUR. 0 of 8,447 non-FBS leader rows carry a jersey — the roster load covers
    138 of 305 teams (R-693) — and they still appear on the card.

    ⚠️ AC-G.32: `#0` would be a false fact about a real player and a blank reads as one too.
    The slot holds an em dash, which says "we do not hold this" and keeps the cards aligned.
    """
    no_jersey = [dict(r, jersey=None) for r in _leaders()]
    entries, _ = panel(_game(), _both(), leaders=no_jersey)
    body = _text(entries)
    assert "#0" not in body, "a missing jersey rendered as number zero"
    assert "—" in body, "a missing jersey rendered as a blank rather than an absence"
    assert "Isaiah Sategna" in body, "the player vanished with his jersey"


# --- 🚨 R-686: the delta is READ, and the fixture proves which ---------------------------------

def test_the_delta_is_READ_from_the_column_and_never_subtracted_in_the_page(panel):
    """🚨 THIS TEST EXISTS BECAUSE ITS STAGED BREAK WENT GREEN. Computing
    `offense[for] - defense[allowed]` right there in the markup passed the entire suite.

    ⚠️ THE FIXTURE IS WHAT MAKES THIS DECIDABLE, AND IT DISAGREES ON PURPOSE. Kentucky gain
    154.4 on the ground and Auburn concede 84.5, so a page that subtracted would print +69.9.
    A106's column says **38.0** — a real srv_game_team figure, computed over a different and
    correct set of games — so the two numbers cannot both appear and only the read produces
    the column's.

    🚨 WHY IT MATTERS BEYOND THE RULE: the Excel export reads the same column. A subtraction
    here would make the page and the workbook disagree about one fact, which is R-645 exactly —
    the defect Marc found himself on a betting page.
    """
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    assert "+38.0" in body, (
        f"the rushing delta is not A106's column value: {body[:400]}")
    assert "+69.9" not in body, (
        "the page SUBTRACTED 154.4 - 84.5 instead of reading the column (§4.2)")


def test_a_NEGATIVE_delta_carries_its_sign_without_relying_on_colour(panel):
    """⚠️ AC-G.22. Marc asked for negatives in red; the leading minus is what a reader in
    greyscale, or with a colour vision deficiency, gets instead. Michigan's rushing delta is
    -6.0 — measured — so the sign is on the page whether or not the colour renders."""
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    assert "-6.0" in body, f"the negative delta lost its sign: {body[:400]}"


# --- 🚨 R-609: the charts are square, asserted on what Streamlit ships --------------------------

def test_the_charts_are_SQUARE_in_the_spec_the_browser_receives(panel):
    """🚨 THIS TEST EXISTS BECAUSE ITS STAGED BREAK WENT GREEN. Making the height 0.6 of the
    width passed the whole suite — nothing in the project asserted the ratio Marc asked for.

    ⚠️ IT READS `_prepare_vega_lite_spec`, NOT `chart.to_dict()`, AND THAT IS THE LESSON OF
    B087. Streamlit fills `autosize` in after altair has finished, and `fit`/`fit-x` both hand
    a dimension to the container — so a spec that looks square can still be drawn oblong. The
    only honest question is what the browser receives.

    🚨 AND THE RATIO NEEDS BOTH PINNED. `fit-x` gives the width to the column by construction,
    so a 1:1 chart cannot use it; `pad` leaves both dimensions the plot's, which is why R-609
    changed the constant B087 introduced.
    """
    entries, _ = panel(_game(), _both())
    charts = _charts(entries)
    assert charts, "no charts drawn"
    for index, chart in enumerate(charts):
        shipped = _shipped(chart)
        width, height = shipped.get("width"), shipped.get("height")
        assert isinstance(width, (int, float)), (
            f"chart {index} ships width={width!r} — a container-sized width cannot be square")
        assert isinstance(height, (int, float)), f"chart {index} ships height={height!r}"
        assert width == height, (
            f"chart {index} is {width}x{height}, not 1:1 — Marc asked for square charts "
            f"(R-609) and the aspect is what he will see")
        kind = (shipped.get("autosize") or {}).get("type")
        assert kind != "fit-x", (
            "autosize 'fit-x' hands the WIDTH to the column, so the ratio depends on the "
            "browser width and 1:1 cannot hold")


def test_one_constant_drives_BOTH_sides_of_the_square():
    """⚠️ TWO CONSTANTS COULD DRIFT APART and the chart would stop being square with nothing
    failing. `_CHART_HEIGHT` is `_CHART_SIDE`, and this says so where a reader looks."""
    from views import matchup
    assert matchup._CHART_HEIGHT == matchup._CHART_SIDE


def test_the_leaders_are_drawn_in_RANK_ORDER(panel):
    """🚨 THE LIVE RENDER CAUGHT THIS AND NO UNIT TEST WOULD HAVE. Oklahoma's receivers came
    back from serving as 2nd, 1st, 3rd — the query carries no `order by` and a DataFrame keeps
    whatever order the driver gave it, so the card listed the second-best receiver first.

    ⚠️ SORTING ON `leader_rank` IS READING, NOT RANKING. A106 computed the rank upstream so the
    page would not; putting rows in the order a column already states is presentation.
    """
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    first, second = body.index("Isaiah Sategna"), body.index("Trell Harris")
    assert first < second, (
        "the leaders are not in rank order — Sategna is 1st and Harris 2nd, and the card "
        "listed them the other way round")


# --- 🚨 R-731: the cards are on the OUTSIDE, and the layout is a MIRROR --------------------
#
# Marc: "There should be a round for B to get the layout correct with the Player Cards on the
# OUTSIDE of the charts in the Offense vs Defense section." So the two charts sit together in
# the middle and the cards are pushed to the outer edges:
#
#     away (left column)     cards | chart
#     home (right column)    chart | cards
#
# 🚨 A PRESENCE ASSERTION PASSES A LEFT/RIGHT SWAP, AND THIS PROJECT HAS PROVED THAT TWICE —
# B082 on the game header, B083 on the win-probability bar. A mirror is worse: a test that
# cannot tell the sides apart also passes when BOTH sides are wrong in the same direction,
# which is exactly the state this file was in before `is_home` reached `_deltas()`.
#
# ✅ SO THE ASSERTIONS ARE POSITIONAL, PER SIDE, AND OPPOSITE — neither is satisfied by the
# other, and the staged break turns exactly ONE of them red.

# ⚠️ THE CARD'S OWN KPI GRID, USED AS THE MARKER SINCE R-733. It used to be the literal
# "Yards so far", and that stopped working the moment the labels became DATA — which is the
# point of the round. The grid is structural: every card has one and nothing else does.
_CARD_GRID = "repeat(3,1fr)"


def _slots(entries):
    """The order of card blocks and charts inside each side's column, in emission order.

    ⚠️ WHY EMISSION ORDER IS THE LAYOUT HERE, rather than a proxy for it: `_yardage_column`
    zips ONE ordered tuple against `st.columns(2)`, which returns left-to-right. So the nth
    thing emitted goes into the nth column from the left, and reversing the tuple moves the
    block and its emission together. There is no way to change the picture without changing
    this sequence, which is what makes reading it honest.
    """
    starts = [i for i, (kind, body) in enumerate(entries)
              if kind == "markdown" and "offense against" in _plain(str(body))]
    assert len(starts) == 2, f"expected two direction blocks, got {len(starts)}"
    out = []
    for lo, hi in zip(starts, starts[1:] + [len(entries)]):
        sequence = []
        for kind, body in entries[lo + 1:hi]:
            if kind == "chart":
                sequence.append("chart")
            elif kind == "markdown" and (_CARD_GRID in str(body)
                                         or "No yards recorded" in str(body)):
                sequence.append("cards")
        out.append(sequence)
    return out


def test_the_AWAY_side_draws_its_CARDS_BEFORE_its_chart(panel):
    """The left column's outer edge is the page's left, so the cards come first."""
    away, _home = _slots(panel(_game(), _both(), deltas=_deltas())[0])
    assert away == ["cards", "chart"] * 3, (
        f"the away column is not cards-then-chart for all three metrics: {away}")


def test_the_HOME_side_draws_its_CARDS_AFTER_its_chart(panel):
    """🚨 THE OPPOSITE ASSERTION, AND THE ONE THE BREAK IS AIMED AT.

    The right column's outer edge is the page's right, so the chart comes first and the cards
    sit beyond it. ⚠️ This is the assertion a non-positional test cannot make, and the one that
    fails when both sides are built the same way round.
    """
    _away, home = _slots(panel(_game(), _both(), deltas=_deltas())[0])
    assert home == ["chart", "cards"] * 3, (
        f"the home column is not chart-then-cards for all three metrics: {home}")


def test_the_TWO_SIDES_ARE_OPPOSITE_which_is_the_requirement(panel):
    """⚠️ STATED AS ITS OWN CLAIM so that "both sides identical" fails even if some future
    change makes both of the two assertions above agree on one order."""
    away, home = _slots(panel(_game(), _both(), deltas=_deltas())[0])
    assert away != home, (
        "both columns drew the same inner order, so the cards are not on the OUTSIDE of the "
        "charts — they are on the same side of both, which is what the layout replaced")
    assert away[0] == "cards" and home[0] == "chart"


def test_the_side_is_READ_from_is_home_rather_than_assumed(panel):
    """⚠️ AND IT IS READ FROM THE FRAME THE PANEL ALREADY HOLDS.

    `srv_game_team.is_home` — measured live at 225,350 rows, set on every one, exactly two per
    game and exactly one home. Flipping the fixture's flags must flip the layout, which is what
    proves the column is being read rather than the call order being relied on.
    """
    flipped = [dict(r, is_home=not r["is_home"]) for r in _deltas()]
    away, home = _slots(panel(_game(), _both(), deltas=flipped)[0])
    assert away == ["chart", "cards"] * 3, \
        "flipping is_home did not flip the away column, so the flag is not being read"
    assert home == ["cards", "chart"] * 3


def test_an_ABSENT_game_team_row_falls_back_rather_than_guessing(panel):
    """A game with no `srv_game_team` row draws no delta chips either, so it is already a
    degraded render. The mirror is then unmirrored — visible — rather than silently reversed."""
    away, home = _slots(panel(_game(), _both(), deltas=[])[0])
    assert away == home == ["cards", "chart"] * 3


# --- R-731: the card is two rows ----------------------------------------------------------

def test_the_card_top_row_carries_all_four_of_MARCS_FIELDS(panel):
    """Marc: "Top Row: Jersey #, Name, Position, Year in school." All four are on the view."""
    text = _text(panel(_game(), _both(), deltas=_deltas())[0])
    for field in ("#9", "Lloyd Avant", "RB", "JR"):
        assert field in text, f"the card top row is missing {field!r}"


def _lone_card(entries):
    """The ONE-card block: Michigan's `total` panel.

    ⚠️ A SINGLE-CARD BLOCK IS THE RIGHT INSTRUMENT FOR A PER-CARD CLAIM, and reaching for the
    three-card block is the mistake this helper exists to stop — a block of three contains three
    of everything, so "the card has one KPI" reads as three and "no em dash" is a claim about
    three players at once. The fixture's own docstring already names this panel: one quarterback
    has thrown, `qualified_players` is 1, and padding it to three would invent players.
    """
    return next(str(b) for k, b in entries
                if k == "markdown" and "Bryce Underwood" in str(b) and "217" in str(b))


def _module_constant(name):
    """One of matchup.py's module-level constants, by AST, without importing the page.

    Importing the view outside `streamlit_stubbed` would bind the real streamlit into it for
    the rest of the session, which is R-665's shape. Reading the source cannot.
    """
    import ast
    for node in ast.parse(SOURCE).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"matchup.py has no module-level {name}")


def test_the_KPI_row_puts_the_MEASURE_NAME_ABOVE_the_number(panel):
    """Marc: "Bottom Row: 3 stats KPI w/name of the measure above the metric."

    ⚠️ ASSERTED ON ORDER WITHIN THE MARKUP, not on both being present. A card with the label
    below the number contains exactly the same two strings.
    """
    card = _lone_card(panel(_game(), _both(), deltas=_deltas())[0])
    assert card.index("Yards") < card.index("217"), \
        "the measure name must sit ABOVE its number, not below it"


def test_the_KPI_ROW_IS_BUILT_FOR_THREE_even_though_one_is_filled(panel):
    """✅ A116 widens `fct_player_leader_week`; the next two measures must not need another
    layout round. The grid is sized by `_CARD_KPI_SLOTS`, so it already has room."""
    slots = _module_constant("_CARD_KPI_SLOTS")
    card = _lone_card(panel(_game(), _both(), deltas=_deltas())[0])
    assert slots == 3, "Marc asked for three KPI slots"
    assert f"repeat({slots},1fr)" in card, "the KPI row is not a grid built for three slots"
    # ✅ R-733: THE GRID B098 BUILT FOR THREE IS NOW FILLED WITH THREE, and they came off the
    # row rather than out of a constant. The `total` panel's trio, measured live.
    for label in ("Comp-Att", "Yards", "TD"):
        assert label in card, f"the card is missing the {label!r} slot"
    assert "51-75" in card, "the `pair` format did not compose its two columns"


def test_an_UNFILLED_slot_is_NOT_an_em_dash(panel):
    """🚨 THE DECISION, AND IT IS AN AC-G.11 ONE RATHER THAN AC-G.32.

    An em dash means "we hold no VALUE for this". Here the MEASURE does not exist yet, which is
    a different statement — two dashes would tell a reader we have nothing for this player when
    the truth is nobody has defined the stat. So only the filled slots are drawn, and the grid
    keeps the shape visible without saying anything untrue.
    """
    # A view that names only two measures for this panel must draw two cells, not three with
    # a dash in the third.
    rows = [dict(r, stat_3_label=None, stat_3_value=None) for r in _leaders()]
    card = _lone_card(panel(_game(), _both(), deltas=_deltas(), leaders=rows)[0])
    assert "TD" not in card, "an unnamed slot drew a label anyway"
    # This player HAS a jersey, so a dash anywhere on his card would be an invented absence.
    assert "—" not in card, f"an unfilled KPI slot rendered an em dash: {card}"
    assert "Yards" in card, "the slots that ARE named must still draw"


def test_the_JERSEY_em_dash_SURVIVES_the_card_rewrite(panel):
    """⚠️ AC-G.32, ALREADY LIVE AND EASY TO LOSE IN A REWRITE. 0 of 8,447 non-FBS leader rows
    carry a jersey (R-693), so a missing one is an absence we can explain — an em dash in the
    same slot, not "#0" and not a blank that reads as one."""
    rows = [dict(r, jersey=None) if r["player_name"] == "Lloyd Avant" else r
            for r in _leaders()]
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=rows)
    card = next(str(b) for k, b in entries if k == "markdown" and "Lloyd Avant" in str(b))
    assert "—" in card, "a missing jersey must render an em dash in the same slot"
    assert "#0" not in card and "#nan" not in card.lower()


def test_the_TIE_BADGE_SURVIVES_the_card_rewrite(panel):
    """⚠️ A TIE SHARES A RANK, so "T-2nd" is the honest label and the row count can exceed
    three. Dropping the badge would turn shared places into an invented order."""
    rows = [dict(r, tied_players=2) if r["leader_rank"] == 2 else r for r in _leaders()]
    text = _text(panel(_game(), _both(), deltas=_deltas(), leaders=rows)[0])
    assert "T-2nd" in text, "the tie badge did not survive"
    assert "T-1st" not in text, "an untied leader was labelled as tied"


# --- 🚨 R-733: the labels are DATA, and the page must not guess at a format it does not know

_MODEL = (Path(__file__).resolve().parents[1] / "dbt" / "models" / "serving"
          / "srv_game_team_leader_through_prior_week.sql")


def test_the_page_knows_every_FORMAT_the_view_can_emit():
    """🚨 THE LOUD HALF OF "AN UNKNOWN FORMAT DRAWS NOTHING".

    `_kpi_value` returns None for a rendering it does not recognise, so a fourth format would
    quietly delete a KPI from every card rather than printing a number nobody designed. That is
    the right behaviour ON THE PAGE and a terrible way to find out, so the formats are read out
    of the MODEL'S OWN SOURCE and checked against the page here — the shape
    `ci/check_health_signals.py` uses for the same reason, and the one A110 named as the model.

    ⚠️ A fourth format then fails in CI on the commit that adds it, which is the only moment it
    is cheap to design a rendering for.
    """
    assert _MODEL.exists(), f"{_MODEL.name} moved — this guard is pinned to it by name"
    # ⚠️ SCOPED TO THE EXPRESSION THAT PRODUCES EACH COLUMN, not to the whole file. A global
    # `then '...'` sweep would read a future CASE for an unrelated column as a format and fail
    # this test for a reason that has nothing to do with the card.
    text = _MODEL.read_text()
    declared = set()
    for match in re.finditer(r"as stat_\d_format", text):
        window = text[max(0, match.start() - 250):match.start()]
        declared |= set(re.findall(r"(?:then|else)\s+'([a-z_0-9]+)'", window))
        declared |= set(re.findall(r"'([a-z_0-9]+)'\s*$", window.rstrip()))
    assert declared, "no format literals found in the model — the parse has gone blind"
    assert len(declared) >= 3, f"the parse found only {sorted(declared)} — it has gone partly blind"
    known = {_module_constant(n) for n in ("_KPI_INTEGER", "_KPI_DECIMAL_1", "_KPI_PAIR")}
    assert declared <= known, (
        f"the view emits {sorted(declared - known)} and matchup.py has no rendering for it, so "
        f"that KPI would silently vanish from every card. Adding a format is a LAYOUT decision "
        f"— design the cell, do not widen this assertion.")


def test_an_UNKNOWN_format_draws_NOTHING_rather_than_something_plausible(panel):
    """⚠️ NOT a raw float, and not a fallback to `integer`. A number nobody designed is
    indistinguishable on the card from one somebody did."""
    rows = [dict(r, stat_3_label="Mystery", stat_3_format="furlongs", stat_3_value=7.0)
            for r in _leaders()]
    card = _lone_card(panel(_game(), _both(), deltas=_deltas(), leaders=rows)[0])
    assert "Mystery" not in card, "an unknown format drew its label"
    # ⚠️ COUNTED, NOT SEARCHED FOR THE DIGIT. "7" appears inside `51-75`, `217` and `9px`, so a
    # substring test here passes or fails for reasons that have nothing to do with the slot.
    assert card.count("text-transform:uppercase") == 2, (
        "the unknown format left a third cell on the card rather than drawing nothing")


def test_the_PAIR_format_composes_two_columns_and_invents_no_number(panel):
    """⚠️ FORMATTING, NOT ARITHMETIC (§4.2). A116 shipped `51` and `75` rather than the string
    so the page joins them; joining creates no quantity, which is the line `players.py:202`
    crossed and R-611 removed."""
    card = _lone_card(panel(_game(), _both(), deltas=_deltas())[0])
    assert "51-75" in card
    # 51/75 would be 0.68 — the composed pair must not have become a ratio anywhere.
    assert "0.68" not in card and "68%" not in card


# --- 🚨 R-694: Marc's game dots ------------------------------------------------------------

def _dots(entries, name):
    """The dot row for one player, as (title, fill-percentage) pairs in drawn order."""
    block = next(str(b) for k, b in entries if k == "markdown" and name in str(b))
    card = next(piece for piece in block.split("border:1px solid rgba(128,128,128,.22)")
                if name in piece)
    out = []
    for span in re.findall(r"<span title='([^']*)'[^>]*>", card):
        out.append(span)
    fills = re.findall(r"currentColor (\d+)%", card)
    return out, fills


def test_one_circle_per_game_the_TEAM_played_not_per_game_the_PLAYER_played(panel):
    """🚨 MARC'S WORDS: "One circle for each game the team played and fill it if the player
    played the game". A player missing a game gets an EMPTY circle, not a shorter row — a row
    that shrinks says nothing about what he missed.
    """
    leaders = _leaders()
    thin = [r for r in _usage() if not (r["player_id"] == leaders[1]["player_id"]
                                        and r["usage_game_id"] == 901)]
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=leaders, usage=thin)
    full, _fills = _dots(entries, leaders[0]["player_name"])
    partial, _f = _dots(entries, leaders[1]["player_name"])
    assert len(full) == len(partial) == 3, (
        f"the two rows are different lengths — {len(full)} vs {len(partial)} — so the timeline "
        f"is the PLAYER's rather than the TEAM's")
    assert any("Did not appear" in t for t in partial), \
        "the missed game did not draw the empty-circle absence"
    assert not any("Did not appear" in t for t in full)


def test_the_FILL_is_relative_to_the_players_OWN_MAXIMUM(panel):
    """🚨 THE DESIGN, AND IT IS MEASURED. Usage is positional — medians QB 0.551, RB 0.134,
    WR 0.058, TE 0.041 — so a circle filled against a flat 0–1 scale leaves every receiver
    about 6% full, which is visually EMPTY and indistinguishable from "did not play".

    A107 proved it on Sedrick Alexander: 0.229 absolute, 93% of his own maximum.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=_leaders(), usage=_usage())
    _titles, fills = _dots(entries, _leaders()[0]["player_name"])
    assert fills, "no fill was drawn at all"
    assert fills[-1] == "100", (
        f"the player's best game is not full, so the fill is not relative to his own maximum: "
        f"{fills}")
    assert fills[0] != "100" and int(fills[0]) > 0, (
        f"an earlier, smaller game should be partly filled: {fills}")


def test_the_absolute_share_is_in_the_HOVER_because_the_fill_is_relative(panel):
    """⚠️ THE RELATIVE FILL IS THE ONLY READABLE ONE AND IT IS ALSO A CLAIM THE READER CANNOT
    CHECK. `usage_total` — the share of the actual team — is carried in the title so the
    absolute number is never lost, only moved."""
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=_leaders(), usage=_usage())
    titles, _f = _dots(entries, _leaders()[0]["player_name"])
    assert any("%" in t and "of the team" in t for t in titles), \
        f"the absolute share is not in the hover: {titles}"


def test_a_SINGLE_OBSERVATION_says_so_rather_than_reading_as_fully_involved(panel):
    """🚨 THE SECOND ABSENCE, AND IT IS A CAVEAT RATHER THAN A GAP (AC-G.11).

    With one observation the maximum IS that game, so the circle is full BY CONSTRUCTION. Full
    means "we have seen him once", not "he was fully involved" — B085's single-snapshot shape.

    ⚠️ IT IS NOT RARE RIGHT NOW: measured on 401856679, EVERY leader on the game has
    `usage_games_in_window = 1`, because it is week 2 and one earlier game exists. Drawing no
    fill at all on a single observation — the other option — would have shown that whole game
    as empty circles, which reads as "nobody played".
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=_leaders(),
                       usage=_usage(games=1, window=1))
    titles, fills = _dots(entries, _leaders()[0]["player_name"])
    assert fills == ["100"], f"a single observation should still show he played: {fills}"
    assert any("only 1 game observed" in t for t in titles), (
        f"a full circle drawn from ONE observation must say so, or it reads as fully "
        f"involved: {titles}")


def test_NO_usage_rows_at_all_is_a_SENTENCE_not_a_row_of_empty_circles(panel):
    """🚨 THE TWO ABSENCES ARE DIFFERENT AND THE DATA PROVES IT (AC-G.11).

    On 401856679 Ben McCreary is Oklahoma's SECOND-ranked rusher through the prior week — he
    has yards, so he played — and `srv_game_team_leader_usage` holds NOT ONE ROW for him.
    Drawing his team's games as empty circles would say he appeared in none of them, which is
    false: we simply hold no usage for him.

    ⚠️ 2026 coverage is partial (R-718), so this is common rather than exotic.
    """
    leaders = _leaders()
    missing = leaders[1]["player_id"]
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=leaders,
                       usage=_usage(skip=(missing,)))
    block = next(str(b) for k, b in entries
                 if k == "markdown" and leaders[1]["player_name"] in str(b))
    card = next(piece for piece in block.split("border:1px solid rgba(128,128,128,.22)")
                if leaders[1]["player_name"] in piece)
    assert "No game-by-game usage held" in card, (
        "a player we hold nothing for drew circles instead of saying so")
    assert "Did not appear" not in card, (
        "we told the reader he missed games we cannot actually say he missed")


def test_the_dots_are_ordered_by_SEASON_TYPE_then_week_never_week_alone(panel):
    """🚨 POSTSEASON WEEKS RESTART AT 1, so a bowl game sorts into October on `usage_week`
    alone. The ordinal is the first key and this is the assertion that says so.

    ⚠️ The rows are handed to the panel in the WRONG order on purpose — a test that supplies
    them already sorted cannot tell a sort from a passthrough.
    """
    leaders = _leaders()
    first = leaders[0]

    def game(game_id, ordinal, week, total):
        return dict(usage_game_id=game_id, usage_season_type_ordinal=ordinal,
                    usage_week=week, usage_total=total,
                    # ⚠️ ONE CEILING FOR ALL FOUR, because the window maximum is a property of
                    # the PLAYER rather than of a game — and it makes every fill distinct, which
                    # is what lets the order be read off the render at all.
                    usage_total_max_in_window=0.30, usage_games_in_window=4,
                    team_id=first["team_id"], panel=first["panel"],
                    player_id=first["player_id"])

    # 🚨 THE FILLS ARE DELIBERATELY ALL DIFFERENT — 33 · 50 · 67 · 100. My first version gave
    # the bowl and the last regular game the same fill and the staged break stayed GREEN: the
    # assertion could not tell the two orders apart. A fixture that cannot fail for the reason
    # it claims is the thing this project keeps finding, and it found it here.
    rows = [game(950, 2, 1, 0.30),        # the POSTSEASON game, first in the frame
            game(901, 1, 1, 0.10), game(902, 1, 2, 0.15), game(903, 1, 3, 0.20)]
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=leaders, usage=rows)
    _titles, fills = _dots(entries, first["player_name"])
    assert fills == ["33", "50", "67", "100"], (
        f"the dots are not in (season_type, week) order. A sort on usage_week ALONE puts the "
        f"bowl first, because postseason weeks restart at 1 — which draws a January game in "
        f"among September's: {fills}")


def test_the_DENOMINATOR_is_READ_not_derived_from_the_rows_on_the_page(panel):
    """🚨 THE ASSERTION MY FIRST STAGED BREAK COULD NOT MAKE, AND THAT IS WHY IT IS HERE.

    `usage_total_max_in_window` is a published column so the page never takes a maximum over
    rows — that window function is what CLAUDE.md puts upstream, and A107 shipped the column
    precisely to keep it there.

    ⚠️ A FIXTURE WHOSE PUBLISHED MAX EQUALS THE MAX OF ITS OWN VALUES CANNOT TELL THE TWO
    APART. I staged the break — the page deriving `max(...)` over the rows it holds — and every
    dots test stayed green, because the two numbers agreed by construction. So this fixture sets
    them APART: the published ceiling is higher than anything in the frame, which is what a real
    window max does whenever the page holds a subset of it.

    A page that derives would show the best row as 100%. A page that reads shows it below.
    """
    rows = [dict(r, usage_total_max_in_window=0.40) for r in _usage()]
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=_leaders(), usage=rows)
    _titles, fills = _dots(entries, _leaders()[0]["player_name"])
    assert fills, "no fill was drawn"
    assert fills[-1] != "100", (
        f"the best row filled the circle completely, so the denominator came from the page's "
        f"own rows rather than from `usage_total_max_in_window`: {fills}")
    assert fills[-1] == "50", f"0.20 of a published 0.40 ceiling is half a circle: {fills}"
