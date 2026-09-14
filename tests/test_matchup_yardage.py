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
            total = 0.10 + 0.05 * index
            ceiling = 0.10 + 0.05 * (observed - 1)
            rows.append({
                "team_id": leader["team_id"], "panel": leader["panel"],
                "player_id": leader["player_id"],
                "usage_game_id": 900 + index,
                # ⚠️ THE REGULAR SEASON IS ORDINAL 1; the postseason row below is 2, and a sort
                # on `usage_week` alone would put it first because bowl weeks restart at 1.
                "usage_season_type_ordinal": 1, "usage_week": index + 1,
                "usage_total": total,
                "usage_total_max_in_window": ceiling,
                # 🚨 R-740. A120 PUBLISHES THE RATIO; the page reads it. Here it AGREES with the
                # pair by default, and `test_the_SHARE_is_READ…` is the one fixture that makes
                # them disagree — because a fixture where they agree cannot tell reading from
                # dividing, which is the trap B099 fell into on this very line.
                "usage_share_of_max": total / ceiling if ceiling else None,
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
    """Auburn at home, Kentucky away, with the real week-10 figures for game 401752754.

    🚨 THE LOGOS ARE SET HERE SINCE R-736, AND `_side` DEFAULTING THEM TO `None` MEANT EVERY
    TEST IN THIS FILE RENDERED THE MISSING-LOGO PATH. Measured against live serving, only
    14,619 of 375,594 `srv_team_week` rows have no logo — 3.9% — so the fixture was modelling
    the exception for 100% of its assertions, and a defect in the COMMON path could not fail
    here. The two URLs are the real ones for team ids 2 and 96.
    """
    home = _side(HOME_ID, "Auburn", games_counted=8,
                 logo_url="https://cdn.collegefootballdata.com/logos/500/2.png",
                 rushing_yards_for_per_game=170.8, passing_yards_for_per_game=170.0,
                 total_yards_for_per_game=340.8,
                 rushing_yards_allowed_per_game=84.5,
                 passing_yards_allowed_per_game=234.4,
                 total_yards_allowed_per_game=318.9)
    away = _side(AWAY_ID, "Kentucky", games_counted=7,
                 logo_url="https://cdn.collegefootballdata.com/logos/500/96.png",
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


def _metric_of(chart):
    """Which metric a chart is, now that it carries no title.

    🚨 R-752 TOOK `title=` OUT OF THE SPEC, and these tests used it to tell the three charts
    apart. The header is markup emitted before the row now, so the chart identifies itself the
    only way left: by the COLUMNS its axes are bound to, which is a stronger claim anyway — a
    title is a caption and a field is what was plotted.
    """
    spec = str(chart.to_dict())
    for metric in ("rushing", "passing", "total"):
        if f"{metric}_yards_for_per_game" in spec or f"'{metric.title()}" in spec:
            return metric.title()
    return None


def _charts(entries):
    """The altair charts the panel drew, in the order it drew them."""
    return [body for kind, body in entries if kind == "chart"]


# --- the pairing, which is the whole point -------------------------------------------------

def test_the_pairing_runs_across_sides_not_down_one(panel):
    """⚠️ THE ASSERTION THIS FILE EXISTS FOR (1c).

    Kentucky's rushing attack is 154.4 and Auburn allows 84.5 on the ground. Those two must
    appear TOGETHER, in that order, on one line — Kentucky's number beside AUBURN's, not
    beside Kentucky's own 132.6 allowed.

    🚨 R-756 MOVED WHERE THIS IS ASSERTED AND NOT WHAT IT ASSERTS. It used to read the delta
    table's text rows; Marc had those removed, and the same two figures are now the chart's own
    annotation. ✅ **Reading them off the CHART is a stronger claim than reading them off a block
    of markup: the old form asked whether two strings appeared somewhere in the same block, this
    one asks what the rushing chart itself was built from.**

    ⚠️ AND THE PAIRING IS ASSERTED PER CHART, which is what makes the negative half bite: the
    away rushing chart must contain Auburn's 84.5 and must NOT contain Kentucky's own 132.6.
    """
    entries, _ = panel(_game(), _both())
    charts = _charts(entries)
    rushing = [c for c in charts if _metric_of(c) == "Rushing"]
    assert len(rushing) == 2, f"expected one rushing chart per side, got {len(rushing)}"
    away, home = rushing
    away_text = " ".join(_annotation(away)[0])
    assert "154.4" in away_text, f"Kentucky's rushing offense is missing: {away_text}"
    assert "84.5" in away_text, (
        f"Kentucky's attack is not paired with AUBURN's rushing defense: {away_text}")
    assert "132.6" not in away_text, (
        f"the panel paired Kentucky's offense with Kentucky's own defense — one team "
        f"described as though it were a matchup: {away_text}")

    home_text = " ".join(_annotation(home)[0])
    assert "170.8" in home_text and "132.6" in home_text, (
        f"Auburn's attack is not paired with Kentucky's rushing defense: {home_text}")
    assert "84.5" not in home_text, (
        f"the panel paired Auburn's offense with Auburn's own defense: {home_text}")


def test_both_directions_are_drawn(panel):
    """Marc named a comparison with two directions, and one of them is not the answer."""
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    assert "Kentucky offense" in body and "Auburn offense" in body, \
        "only one direction of the comparison was rendered"


def test_rushing_and_passing_are_both_present_and_separate(panel):
    """Marc named both, separately, and asked for them separately rather than as a total.

    ⚠️ R-756 TOOK THE FIGURES OFF THE PAGE'S TEXT AND LEFT THEM ON THE CHARTS, so the eight
    numbers are gathered from the annotations rather than from the rendered body. The claim is
    unchanged: every one of them is on the panel somewhere a reader can see it.
    """
    entries = panel(_game(), _both())[0]
    body = _text(entries)
    assert "Rushing" in body and "Passing" in body
    drawn = " ".join(t for c in _charts(entries) for t in _annotation(c)[0])
    for figure in ("154.4", "207.0", "170.8", "170.0", "84.5", "234.4", "132.6", "253.0"):
        assert figure in drawn, f"{figure} is on no chart in the panel: {drawn}"


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


def test_the_PAGE_contains_exactly_the_DIVISIONS_it_is_allowed_to(panel):
    """🚨 R-743. THIS REPLACES A SOURCE-WINDOW TEXT SCAN THAT WENT BLIND TWICE IN THIS FILE.

    ⚠️ SCOPE, IN THE SAME SENTENCE AS THE CLAIM: this parses `site/views/matchup.py` and asserts
    that the only DIVISION OPERATORS in the module are the ones named below. It says nothing
    about other operators, nothing about other modules, and nothing about a division expressed
    as a method call rather than `/`.

    ── WHY THE OLD SHAPE HAD TO GO ─────────────────────────────────────────────────────────

    `test_the_CHART_CODE_does_not_divide` sliced `SOURCE` between `def _week_distribution(` and
    `def _yardage_column(`, so it could only ever see code written BETWEEN those two names.

      · B092 renamed it once for over-claiming — it was `test_the_page_does_not_divide_anywhere`,
        "a claim the test never made". The NAME became honest; the SCOPE did not.
      · B100 staged a page-side subtraction in `_mark_label` at line 1477. The window opens at
        1632. 🚨 THE GUARD PASSED. A helper gets written wherever it fits, and this file has now
        put one above the window twice.
      · And a text scan cannot tell an operator from a character: quoting Marc's own rule —
        "(Gained - Allowed) / Gained > .2" — inside the window turns the guard RED for a comment.
        B090 spent a round on the same class.

    ── WHY AN AST SCAN RATHER THAN A WIDER WINDOW ──────────────────────────────────────────

    Measured on the merged file: **206 solidus characters on 177 lines, and exactly ONE real
    division operator.** Widening the text scan to the whole file would mean excluding 177 lines
    of markup, URLs and prose — a guard that is mostly exceptions is one nobody can read, and
    every exception is a place it is blind. The AST sees the operator and nothing else.

    ⚠️ WHAT IT STILL CANNOT SEE, NAMED RATHER THAN LEFT TO BE DISCOVERED: a division done for
    this page inside `site/lib/`, one written as `.div()` or `np.divide`, and any OTHER piece of
    metric arithmetic — a subtraction included. 🚨 THAT LAST ONE IS NOT HYPOTHETICAL: B100's
    break was a SUBTRACTION, and what caught it was
    `test_the_label_reads_A106s_COLUMN_and_subtracts_nothing`, which makes the published column
    disagree with its own inputs so no fixture can satisfy both readings. **A behavioural
    assertion per published figure is the other half of this and neither replaces the other.**
    """
    import ast
    tree = ast.parse(SOURCE)
    lines = SOURCE.splitlines()
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv)):
            found[node.lineno] = lines[node.lineno - 1].strip()

    # 🚨 THE LIST IS EMPTY NOW, AND R-740 IS WHY. B102 left one entry here — R-694's dot fill,
    # `float(share) / float(ceiling)` — with the note "⏳ R-740 publishes `usage_share_of_max`
    # and this goes". A120 published it, B101 read it, and the guard's own
    # `assert found` fired on the next run to say the entry had become stale. ✅ REMOVED
    # DELIBERATELY, which is what that assertion existed to force.
    #
    # ⚠️ TO ADD ONE you must be able to finish "this page divides here and the warehouse cannot
    # do it because…" — the bar `PROVIDED_BY_THE_PAGE` in ci/check_page_reads.py sets for its
    # own exceptions. **`site/views/matchup.py` now divides nowhere at all.**
    #
    # 🚨 R-804 ADDED THE FIRST ENTRY SINCE THE LIST WAS EMPTIED, AND IT IS A DIFFERENT KIND OF
    # DIVISION FROM EVERY ONE THIS GUARD WAS BUILT FOR — which is worth saying, because a guard
    # whose exceptions are all one shape stops being read.
    #
    # Finishing the required sentence: **this page divides here, and the warehouse cannot do it,
    # because the quantity is a SCREEN-PIXEL MIDPOINT.** `_ANNOTATION_BLOCK` is how far left of
    # the plot's right edge the annotation may reach, and it must stay in the right half or it
    # sits over the middle-half band. `_CHART_SIDE` is a layout constant in this file; serving
    # has never heard of it, there is no column it could disagree with, and no export reads it.
    #
    # ⚠️ THE DISTINCTION THIS ENTRY DRAWS, AND IT IS THE ONE §4.2.1 ACTUALLY MAKES: the rule is
    # about METRIC arithmetic — a quantity a second consumer could want and therefore a quantity
    # two consumers could compute differently. A pixel derived from a constant declared twelve
    # lines above has exactly one consumer by construction.
    # ✅ B105 derived it rather than writing the literal 80 ON PURPOSE: R-804 moved `_CHART_SIDE`
    # from 240 to 180 and the annotation's FIXED 104px block silently became 58% of the plot —
    # `test_the_annotation_is_anchored_to_the_TOP_RIGHT` caught it. A derived constant cannot be
    # left behind by the next round that moves the square.
    allowed = {"_ANNOTATION_BLOCK = _CHART_SIDE // 2 - 10"}
    unexpected = {line: text for line, text in found.items() if text not in allowed}
    assert not unexpected, (
        f"site/views/matchup.py divides where nothing says it may: "
        f"{unexpected!r}. "
        f"Metric arithmetic belongs upstream (§4.2) — a ratio computed here can disagree with "
        f"the Excel export, which reads the column. If this division is legitimate, add it to "
        f"`allowed` WITH THE REASON; do not delete the assertion.")
    # 🚨 AND THE GUARD MUST NOT GO BLIND. With `allowed` empty, "no divisions found" is the
    # CORRECT answer, so the emptiness of `found` can no longer be the liveness check — a parse
    # that returned nothing at all would look identical to a clean file.
    # ✅ So liveness is asserted on the PARSE instead: the walk must still be able to see this
    # module's own functions.
    walked = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for name in ("_usage_dots", "_scatter", "_yardage_column"):
        assert name in walked, (
            f"the AST walk cannot see {name!r}, so it is not reading matchup.py any more and "
            f"a division anywhere in the file would pass unnoticed")


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

    🚨 SKIPPING IT LOSES NO MEASUREMENT — AND B105 HAD TO MEND THAT, NOT JUST RESTATE IT.
    This used to read "`_yardage_direction` prints both figures as text directly above". R-756
    deleted that block on Marc's word, and the annotation that carries the figures now lives
    INSIDE the chart — so on the one path where the chart is DROPPED, the figures went with it
    and this sentence became false. ✅ The caption carries them itself now
    (`_off_the_frame_figures`), which is what `test_the_dropped_chart_SAYS_it_was_dropped`
    asserts alongside this.
    """
    sides = [_side(HOME_ID, "Stetson", rushing_yards_allowed_per_game=393.0),
             _side(AWAY_ID, "Marist")]
    entries, _ = panel(_game(), sides,
                       distribution=_distribution(
                           axes={"rushing_yards_allowed_per_game": (-50.0, 350.0)}))
    charts = _charts(entries)
    titles = [_metric_of(c) for c in charts]
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
    titles = [_metric_of(c) for c in _charts(entries)]
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
        # ⚠️ THE ANNOTATION'S RULE IS A `rule` WITH A strokeWidth TOO, SINCE R-751 — and it is
        # positioned in SCREEN pixels rather than bound to a percentile column, so the band's
        # edges are the ones whose data carries a value. Without this the subtraction's rule
        # counts as a box edge and this test reports four edges where there are two.
        if "value" in (layer.get("encoding", {}).get("y") or {}):
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
    assert "Sategna" in body, f"the passing panel drew no receiver: {body[:400]}"
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
    assert body.count("Underwood") >= 1
    # One name in that panel, so no 2nd or 3rd place label can follow it there.
    assert "Mateer" in body, "the away QB is missing"


def test_a_TIE_shares_its_rank_and_is_NOT_truncated_to_three(panel):
    """🚨 STATE THREE, AND TRUNCATION WOULD INVENT A WINNER. Ranks are shared, so a three-way
    tie for third returns MORE than three rows.

    🚨 THE FIXTURE CARRIES **FOUR** ROWS AND THE FIRST VERSION CARRIED THREE, WHICH IS WHY THE
    STAGED BREAK PASSED. Truncating to three cannot be detected by a three-row tie — the eighth
    time on this page that a fixture could not distinguish what it claimed to test, and the
    prompt named it in advance.

    ⚠️ THE "T-2nd" HALF OF THIS TEST WENT WITH R-753. Marc: *"Don't include the rank."* The rows
    are still all drawn — which is what matters, because dropping one would invent a winner —
    but nothing on the card now says they SHARE a place. See
    `test_the_RANK_and_the_TIE_MARKER_are_gone_and_NOTHING_carries_the_tie`, which records that
    loss as an assertion rather than leaving it in a report nobody greps.
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
    for name in ("Avant", "McCreary", "Robinson", "Blaylock"):
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
    assert "Sategna" in body, "the player vanished with his jersey"


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

    ⚠️ R-756 MOVED WHERE IT IS READ. The delta chip on the removed table used to carry this;
    the annotation carries it now, and the fixture's disagreement — 38.0 published against a
    69.9 subtraction — is what still makes only one of the two readings possible.
    """
    entries, _ = panel(_game(), _both())
    drawn = " ".join(t for c in _charts(entries) for t in _annotation(c)[0])
    assert "+38.0" in drawn, (
        f"the rushing delta is not A106's column value: {drawn}")
    assert "+69.9" not in drawn, (
        "the page SUBTRACTED 154.4 - 84.5 instead of reading the column (§4.2.1)")


def test_a_NEGATIVE_delta_carries_its_sign_without_relying_on_colour(panel):
    """⚠️ AC-G.22. Marc asked for negatives in red; the leading minus is what a reader in
    greyscale, or with a colour vision deficiency, gets instead. Michigan's rushing delta is
    -6.0 — measured — so the sign is on the page whether or not the colour renders.

    ⚠️ R-756 TOOK THE CHIP; the annotation's bold delta line carries the sign now."""
    entries, _ = panel(_game(), _both())
    drawn = " ".join(t for c in _charts(entries) for t in _annotation(c)[0])
    assert "-6.0" in drawn or "\u22126.0" in drawn, (
        f"the negative delta lost its sign: {drawn}")


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
    first, second = body.index("Sategna"), body.index("Harris")
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
    # ⚠️ `# 9` WITH A SPACE SINCE R-806: the hash is its own element at half the digits' size,
    # and `_plain` puts a space where it strips a tag. The reader sees `#9`.
    for field in ("# 9", "Avant, Lloyd", "RB", "JR"):
        assert field in text, f"the card top row is missing {field!r}"


def _lone_card(entries):
    """The ONE-card block: Michigan's `total` panel.

    ⚠️ A SINGLE-CARD BLOCK IS THE RIGHT INSTRUMENT FOR A PER-CARD CLAIM, and reaching for the
    three-card block is the mistake this helper exists to stop — a block of three contains three
    of everything, so "the card has one KPI" reads as three and "no em dash" is a claim about
    three players at once. The fixture's own docstring already names this panel: one quarterback
    has thrown, `qualified_players` is 1, and padding it to three would invent players.
    """
    # ⚠️ MATCHED ON PLAIN TEXT SINCE R-753. The name is rendered as two elements — small first
    # line, bold last line — so "Bryce Underwood" no longer appears contiguously in the markup.
    return next(str(b) for k, b in entries
                if k == "markdown" and "Underwood" in _plain(str(b)) and "217" in str(b))


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
    card = next(str(b) for k, b in entries
                if k == "markdown" and "Avant" in _plain(str(b)))
    assert "—" in card, "a missing jersey must render an em dash in the same slot"
    assert "#0" not in card and "#nan" not in card.lower()


def test_the_RANK_and_the_TIE_MARKER_are_gone_and_NOTHING_carries_the_tie(panel):
    """🚨 R-753 REMOVED THE RANK, AND THIS RECORDS WHAT WENT WITH IT.

    Marc: *"Don't include the rank."* ✅ The cards are drawn in rank order, so the ORDER carries
    the rank and nothing is lost there.

    ⚠️ BUT THE `T-2nd` MARKER WENT TOO, AND A TIE IS NOW INDISTINGUISHABLE FROM AN ORDER. Two
    players sharing second place render as second and third. **That is a real loss and it is
    asserted here rather than only described**, so a future round that wants to carry the tie
    again has a test to change and a reason written next to it.

    ⚠️ NOT SOLVED IN PASSING: where a tie should live on a three-column header Marc specified is
    a look decision, and inventing a slot for it would be exactly the quiet substitution §2
    forbids.
    """
    rows = [dict(r, tied_players=2) if r["leader_rank"] == 2 else r for r in _leaders()]
    tied_text = _text(panel(_game(), _both(), deltas=_deltas(), leaders=rows)[0])
    plain_text = _text(panel(_game(), _both(), deltas=_deltas(), leaders=_leaders())[0])
    for marker in ("T-1st", "T-2nd", "1st", "2nd", "3rd"):
        assert marker not in tied_text, f"the card still carries a rank marker: {marker!r}"
    # 🚨 THE LOSS, STATED AS AN ASSERTION: the tied render and the untied one are the same card.
    assert tied_text == plain_text, (
        "a tie now renders differently from an order, so something IS carrying it — if that is "
        "deliberate, this test is the one to update, and say what carries it")


# --- 🚨 R-733: the labels are DATA, and the page must not guess at a format it does not know

# ⚠️ REPOINTED FROM THE VIEW TO THE MACRO BY A120 (R-723), AND B102's OWN DOCSTRING PREDICTED IT:
# "a format introduced by a DIFFERENT model, or by A MACRO THIS PARSE DOES NOT FOLLOW, is not
# covered." A120 lifted the twelve slot expressions out of the preview view into a shared macro so
# the new POST-GAME twin could call the identical ones, and the literals left this parse's subject
# the same day the sentence was written.
#
# 🚨 THE PER-SLOT LOGIC BELOW IS B102's AND IS UNCHANGED — only the file it reads moved. That
# logic is strictly stronger than what A120 had written against the old subject, and the merge
# kept it rather than the weaker version.
#
# ✅ AND THE MACRO IS NOW THE BETTER SUBJECT: BOTH leader views call it, so one assertion covers
# the preview card AND the post-game card. A format added there reaches both.
_MODEL = (Path(__file__).resolve().parents[1] / "dbt" / "macros" / "player_card_slots.sql")


def _declared_formats_by_slot():
    """Each slot's format literals, read out of the MODEL'S OWN SOURCE, anchored on `case`.

    🚨 R-739. THE FIRST VERSION READ A FIXED 250-CHARACTER WINDOW BEFORE EACH
    `as stat_N_format`, AND THAT CAN GO PARTLY BLIND WHILE STILL PASSING. A fourth format
    introduced inside a LONGER `case` falls outside the window, `declared` stays a subset of
    `known`, the assertion passes — and the KPI silently vanishes from every card, which is the
    exact outcome the guard exists to prevent.

    ⚠️ AND THE `>= 3` FLOOR DID NOT CATCH IT: three slots each emitting `integer` clear it while
    one slot's new format is missed entirely. **That is why this returns PER SLOT and the caller
    asserts per slot** — a slot that yields nothing is now a failure rather than a silence.
    """
    text = _MODEL.read_text()
    by_slot = {}
    for slot in (1, 2, 3):
        marker = f"as stat_{slot}_format"
        idx = text.index(marker)
        head = text[:idx]
        case_at = head.rfind("case ")
        # ⚠️ THE `case` MUST BE OURS. If another column's `end as stat_…` sits between it and
        # us, that CASE belongs to an earlier slot and this one is a bare literal instead.
        if case_at != -1 and "end as stat_" not in text[case_at:idx]:
            window = text[case_at:idx]
        else:
            window = text[head.rfind("\n") + 1:idx]
        found = set(re.findall(r"(?:then|else)\s+'([a-z_0-9]+)'", window))
        found |= set(re.findall(r"'([a-z_0-9]+)'\s*$", window.rstrip()))
        by_slot[slot] = found
    return by_slot


def test_the_page_knows_every_FORMAT_the_view_can_emit():
    """🚨 THE LOUD HALF OF "AN UNKNOWN FORMAT DRAWS NOTHING".

    `_kpi_value` returns None for a rendering it does not recognise, so a fourth format would
    quietly delete a KPI from every card rather than printing a number nobody designed. That is
    the right behaviour ON THE PAGE and a terrible way to find out, so the formats are read out
    of the MODEL'S OWN SOURCE and checked against the page here — the shape
    `ci/check_health_signals.py` uses for the same reason, and the one A110 named as the model.

    ⚠️ SCOPE, IN THE SAME SENTENCE AS THE CLAIM: this reads the three `stat_N_format`
    expressions in `macros/player_card_slots.sql` and nothing else — the macro BOTH leader views
    call, as of A120. A format introduced by a DIFFERENT model, or by a second macro this parse
    does not follow, is still not covered.
    """
    assert _MODEL.exists(), f"{_MODEL.name} moved — this guard is pinned to it by name"
    known = {_module_constant(n) for n in ("_KPI_INTEGER", "_KPI_DECIMAL_1", "_KPI_PAIR")}
    by_slot = _declared_formats_by_slot()
    for slot, declared in sorted(by_slot.items()):
        # 🚨 PER SLOT. A slot whose formats this parse cannot see yields an EMPTY set, and an
        # empty set is trivially a subset of `known` — so the emptiness is the assertion.
        assert declared, (
            f"slot {slot}: no format literal found in the model's own expression, so this "
            f"guard has gone blind for that slot — a new rendering there would vanish from "
            f"every card with the suite green")
        assert declared <= known, (
            f"slot {slot}: the view emits {sorted(declared - known)} and matchup.py has no "
            f"rendering for it, so that KPI would silently vanish from every card. Adding a "
            f"format is a LAYOUT decision — design the cell, do not widen this assertion.")


def test_the_FORMAT_PARSE_survives_a_longer_case_than_the_old_window(tmp_path):
    """🚨 R-739's OWN BREAK, AND IT IS THE REASON THE ANCHOR CHANGED.

    A fourth format introduced inside a `case` longer than 250 characters was invisible to the
    old parse. This builds exactly that model on disk and asserts the parse SEES the new value —
    if it did not, `declared` would stay a subset of `known` and the guard would pass while the
    page dropped the KPI.
    """
    # ⚠️ THE NEW FORMAT GOES FIRST AND THE PADDING AFTER IT, WHICH IS THE WHOLE POINT. My first
    # version put `furlongs` on the line above the marker, where the OLD 250-character window
    # could still see it — a break that does not break. Measured both ways: from here the old
    # window reads back 250 characters and lands INSIDE the filler, so it never reaches this
    # literal, while the `case` anchor does.
    padding = "\n".join(
        f"                 -- filler line {n} to push this literal out of reach"
        for n in range(8))
    model = tmp_path / "srv_game_team_leader_through_prior_week.sql"
    model.write_text(
        "select\n"
        "    case l.panel when 'total' then 'pair' else 'integer'\n"
        "    end as stat_1_format,\n"
        "    'integer' as stat_2_format,\n"
        "    case l.panel when 'passing' then 'furlongs'\n"
        f"{padding}\n"
        "                 when 'rushing' then 'decimal_1'\n"
        "                 else 'integer'\n"
        "    end as stat_3_format\n")
    import test_matchup_yardage as self_module
    original = self_module._MODEL
    try:
        self_module._MODEL = model
        by_slot = self_module._declared_formats_by_slot()
    finally:
        self_module._MODEL = original
    assert "furlongs" in by_slot[3], (
        f"the parse did not see a format introduced inside a long case — which is exactly how "
        f"R-739 goes blind while passing: {by_slot}")
    assert by_slot[1] == {"pair", "integer"} and by_slot[2] == {"integer"}


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
    """The dot row for one player, as (title, fill-percentage) pairs in drawn order.

    🚨 LOOKED UP BY THE SURNAME, NOT THE WHOLE NAME, AND R-758 IS WHY. The card renders
    `Last, First` since R-806; a helper matching the full `First Last` string raises
    `StopIteration` the moment the order changes — **a crash, which proves the helper is narrow
    rather than that the card is wrong.** B101 and B103 each hit that, and this is the fix
    applied once rather than at nine call sites.
    """
    token = str(name).split()[-1]
    block = next(str(b) for k, b in entries
                 if k == "markdown" and token in _plain(str(b)))
    card = next(piece for piece in block.split("border:1px solid rgba(128,128,128,.22)")
                if token in _plain(piece))
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
    # ⚠️ BY SURNAME (R-758) — the card renders `Last, First`, so a full-name lookup raises.
    token = leaders[1]["player_name"].split()[-1]
    block = next(str(b) for k, b in entries
                 if k == "markdown" and token in _plain(str(b)))
    card = next(piece for piece in block.split("border:1px solid rgba(128,128,128,.22)")
                if token in _plain(piece))
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
                    usage_total_max_in_window=0.30,
                    usage_share_of_max=total / 0.30, usage_games_in_window=4,
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


def test_the_SHARE_is_READ_and_the_page_neither_divides_nor_derives_it(panel):
    """🚨 R-740 / §4.2.1, AND THIS IS B099's BREAK INVERTED.

    B099 shipped `float(share) / float(ceiling)` in the page. A120 published
    `usage_share_of_max` — 159,418 of 159,418 populated — so the ratio has one definition and
    the page reads it.

    ⚠️ THE FIXTURE MAKES THE PUBLISHED SHARE DISAGREE WITH ITS OWN INPUTS, which is the only
    way an assertion can tell READING from DIVIDING. B099 learned that twice on this line: its
    first staged break stayed green because the fixture's ceiling equalled the max of its own
    values, so both readings gave the same answer.

    Here the pair says 0.20 / 0.40 = 50%, and the published column says 90%. A page that
    divides draws half a circle; a page that reads draws nine tenths of one.
    """
    rows = [dict(r, usage_total=0.20, usage_total_max_in_window=0.40,
                 usage_share_of_max=0.90) for r in _usage()]
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=_leaders(), usage=rows)
    _titles, fills = _dots(entries, _leaders()[0]["player_name"])
    assert fills, "no fill was drawn"
    assert set(fills) == {"90"}, (
        f"the fill is not the PUBLISHED share. 0.20 over a 0.40 ceiling is 50%, and the column "
        f"says 90% — a page still dividing draws 50: {fills}")


def test_a_NULL_published_share_DRAWS_NOTHING_and_never_an_empty_circle(panel):
    """🚨 R-740's SECOND HALF, AND IT REVERSES B102 — COWORK ASKED FOR THE RAISE AND WAS WRONG.

    B102 made a null share raise, reasoning the branch was provably dead and a lie is worse than
    a loud failure. ⚠️ **But `_usage_dots` runs inside `_yardage_column`, so one bad row would
    take down three charts and nine cards for every viewer, on a game day, with no alert.**

    ✅ ASSERT UPSTREAM, DEGRADE DOWNSTREAM. A121's
    `assert_leader_usage_carries_a_drawable_denominator` fails the BUILD on such a row — that is
    the loud half, upstream where it belongs — and the page omits the one dot.

    ⚠️ AC-G.32: "NOTHING" IS NOT AN EMPTY CIRCLE. An empty circle at full border opacity is what
    `did not appear` draws, and a null share means the opposite: he played and we cannot scale
    it. **So the assertion is that the row gets SHORTER, not that it gains a blank.**
    """
    rows = [dict(r, usage_share_of_max=None) for r in _usage()]
    entries, _ = panel(_game(), _both(), deltas=_deltas(), leaders=_leaders(), usage=rows)
    titles, fills = _dots(entries, _leaders()[0]["player_name"])
    assert not fills, f"a null share still drew a filled circle: {fills}"
    assert not any("Did not appear" in t for t in titles), (
        f"a null share drew the DID NOT APPEAR circle, which says he took no part — the "
        f"opposite of what a null share means (AC-G.32): {titles}")
    # And the panel survives: no error card, which is the whole reason the raise came out.
    assert not any(render_harness.ERROR_CARD in str(b) for _k, b in entries)


# --- 🚨 R-735: the card and the chart share the row at 1:4 ---------------------------------

def test_the_CHART_SLOT_is_wide_enough_for_the_square_it_holds():
    """🚨 R-750. THE RATIO IS NOT A PREFERENCE ANY MORE, IT IS A CONSTRAINT, AND THE RENDER SET
    IT.

    Marc asked for 1:4 (B100) and then *"too much white space between the left side and right
    side"* (v04.1). ⚠️ **Those pull in opposite directions and the second one wins**, because a
    PROPORTIONAL column cannot size a FIXED-WIDTH element: at 1:4 the chart slot took four
    fifths of the half to draw a 240px square, and the remainder was dead space on the side away
    from the cards — both gaps in his screenshot.

    ⚠️ AND A SLACK THIRD COLUMN WAS BUILT AND REMOVED. Cowork's lean was to absorb the remainder
    at each half's outer edge. **Rendered at 1300px it made things worse**: with the sidebar
    open each half is ~520px, the chart needs ~310px including its axis labels, and there is no
    slack to give — the charts clipped and the card's name column collapsed to three lines.

    ✅ SO THE CHART SLOT IS SIZED TO THE CHART AND THE REMAINDER GOES TO THE CARD, which answers
    both complaints with one number: the gap closes because the slot no longer exceeds its
    contents, and the card gets the width R-745 has wanted for four rounds.

    🚨 R-804 RE-DERIVED EVERY NUMBER IN THIS DOCSTRING, BECAUSE FOUR ROUNDS REASONED FROM
    ESTIMATES AND THE ESTIMATES WERE WRONG. Measured in the browser at 1300px, sidebar open:

        the page's content              840px
        one half, `st.columns(2)`       412px    ← the old text here said "~520px"
        the gap `st.columns` inserts     16px
        so the pair splits              396px
        the shipped chart               227px    ← the old text here said "about 300px"

    ⚠️ THE FLOOR IS WHAT THIS ASSERTS, and it is now arithmetic rather than a guess: the chart
    slot is `396 × share`, and it must hold 227px. `227 / 396` is **0.573**, so anything at or
    below that CLIPS — which is what B098, B100, B104 and B106 each measured as a symptom
    without ever measuring the column. 0.58 is the floor with a little headroom.

    ⚠️ AND THE CEILING IS THE CARD, WHICH IS NOT SLACK. At 0.68 the card gets 127px, and B106
    measured its name row at 134px inside a 150px card with names ALREADY ellipsising. Above
    that the header Marc spent B103, B104 and B106 shaping stops fitting at all.

    **Nothing here can read a pixel, so the raster in B105's report is the evidence and this is
    the guard that stops a future round tightening it blind.**
    """
    widths = _module_constant("_SLOT_WIDTHS")
    assert set(widths) == {"cards", "chart"}, (
        f"a third slot is back — R-750 removed the slack column because at 1300px there is no "
        f"slack to give: {widths}")
    share = widths["chart"] / sum(widths.values())
    assert 0.58 <= share <= 0.68, (
        f"the chart slot takes {share:.0%} of the pair, which is 396px at 1300px with the "
        f"sidebar open. Below 58% the {_module_constant('_CHART_SIDE')}px square plus its 47px "
        f"of axis chrome does not fit and DRAWS OVER the column beside it (R-755); above 68% "
        f"the card drops under 127px and cannot hold the header R-753 specified.")


# The two numbers B105 measured in the browser, pinned where the assertion can use them.
# ⚠️ THEY ARE MEASUREMENTS, NOT TARGETS: 246 is what `st.columns([1, 1.6])` gave the chart slot
# inside a 412px half at 1300px with the sidebar open, and 47 is `shipped width − _CHART_SIDE`
# for the same chart in the same browser. Both were read off the live page, not derived.
_CHART_SLOT_AT_1300 = 246
_CHART_CHROME = 47
# Average glyph width as a fraction of font size, for this page's sans stack. ⚠️ MEASURED in the
# browser by B106 — 1.5rem held 12.2 characters in 134px, 1.25rem held 14.5, 1.0rem held 17.0 —
# which is 0.52em per character at all three sizes.
_AXIS_LABEL_EM = 0.52


def test_the_AXIS_LABELS_have_room_to_be_read_at_the_smaller_square():
    """🚨 THIS TEST EXISTS BECAUSE THE ROUND'S OWN STAGED BREAK CAME BACK GREEN (R-744).

    B105 was asked to restore the eight-tick axis and assert the PAD. It did, and the pad
    assertion passed — **because the tick count moves the shipped width by exactly zero.** The
    x axis runs UNDER the plot, so its labels cost HEIGHT; the 47px of horizontal chrome is all
    y axis. A break that cannot fail proves nothing, and the honest response is not to drop it
    but to assert the thing the tick count is actually FOR.

    ⚠️ WHICH IS LEGIBILITY, AND ONLY SINCE R-804. At 240px, 8 ticks sat 34px apart and nobody
    had to think about it. At 180px they sit 22px apart against a label about 16px wide — a
    three-digit number at `_AXIS_LABEL_SIZE`, at roughly 0.52em per character. **That is 6px of
    clearance, which is a solid band of digits rather than an axis.**

    ⚠️ ASSERTED WITHOUT A DIVISION ON PURPOSE — `2 * ticks * label <= side` is the same claim as
    "the labels take under half the axis" and does not need an entry in
    `test_the_PAGE_contains_exactly_the_DIVISIONS_it_is_allowed_to`.
    """
    ticks = _module_constant("_AXIS_TICKS")
    side = _module_constant("_CHART_SIDE")
    # A three-digit tick label — "350", "700" — at the axis label size. Every axis this panel
    # draws is per-game yardage, so three digits is the real worst case and not a guess.
    label = 3 * _AXIS_LABEL_EM * _module_constant("_AXIS_LABEL_SIZE")
    assert 2 * ticks * label <= side, (
        f"{ticks} ticks of about {label:.0f}px each on a {side}px axis leaves "
        f"{(side - ticks * label) / ticks:.0f}px between labels — they read as one band rather "
        f"than as a scale a reader can interpolate from")
    assert ticks >= 3, (
        f"{ticks} ticks cannot carry a scale — a reader needs a low, a high and something "
        f"between them to interpolate")


def test_the_shipped_CHART_FITS_the_column_it_is_drawn_in():
    """🚨 R-804/R-817. THE ONE ASSERTION FOUR ROUNDS OF SYMPTOM-CHASING DID NOT HAVE.

    B098, B100, B104 and B106 each reported a DIFFERENT symptom — a clipped axis label, a
    clipped annotation, cards drawn over a chart — and every one of them was the same fact:
    **the chart is wider than its column, and a Streamlit column does not clip its children
    (R-755), so the overflow lands on whatever sits to the right.** At 240px the shipped box was
    305px in a 246px column: 59px over.

    ⚠️ ASSERTED ON THE PAD, NOT ON THE TICK COUNT, AND THE DIFFERENCE IS THE ROUND'S FINDING.
    B105 swept every axis lever with vl_convert and measured that **the tick count moves the
    width by ZERO** — the x axis runs UNDER the plot, so its labels cost height. The whole 47px
    is the y axis: its rotated title and its tick labels. A test that counted ticks would pass
    any styling that kept four of them and would say nothing about whether the chart fits.

    ⚠️ WHY IT PINS A NUMBER RATHER THAN COMPILING THE SPEC: the measurement was taken with
    `vl_convert`, which is NOT in `requirements*.txt` — it is in the local venv incidentally.
    A test that imported it would ERROR in CI, and guarding it with `importorskip` would make
    it skip there, which is the silently-thinner green run §3.4 exists to stop. **So the
    measurement is pinned and the raster is the evidence, which is this file's own idiom.**
    """
    side = _module_constant("_CHART_SIDE")
    shipped = side + _CHART_CHROME
    assert shipped <= _CHART_SLOT_AT_1300, (
        f"the chart ships at {shipped}px ({side}px square + {_CHART_CHROME}px of y-axis chrome) "
        f"into a {_CHART_SLOT_AT_1300}px column at 1300px with the sidebar open. It is "
        f"{shipped - _CHART_SLOT_AT_1300}px too wide, and a Streamlit column does not clip its "
        f"children — it draws over the one beside it (R-755).")
    # ⚠️ HEADROOM, NOT A HAIR — B104's rule, after a row that was two per cent over.
    assert shipped <= _CHART_SLOT_AT_1300 - 10, (
        f"the chart fits by only {_CHART_SLOT_AT_1300 - shipped}px. Font metrics differ between "
        f"browsers and this margin is the whole defence against the class.")
    # ⚠️ AND A FLOOR, so nobody answers a future overflow by shrinking the square to nothing.
    assert side >= 150, (
        f"a {side}px plot carries a band, two median rules, a point and a three-line "
        f"annotation; below ~150 the annotation alone is half of it")


def test_the_WIDTHS_are_pinned_to_the_SLOT_and_not_to_the_column_index(panel):
    """🚨 B082 AND B083 BOTH PROVED A PRESENCE ASSERTION CANNOT SEE A LEFT/RIGHT SWAP, and a
    width is the same shape of claim.

    B098 made one ordered tuple drive the order, the column AND the width, so the away side
    reads [cards, chart] and the home side [chart, cards] — which means the WIDTH LIST IS
    REVERSED BETWEEN THE SIDES TOO. If the weights were keyed by position rather than by slot,
    the home chart would get the card's width while every positional assertion still passed.
    """
    widths = _module_constant("_SLOT_WIDTHS")
    away, home = _slots(panel(_game(), _both(), deltas=_deltas())[0])
    assert away[0] == "cards" and home[0] == "chart"
    # The card is the NARROW one on both sides, whichever end of the row it sits at.
    assert widths["cards"] < widths["chart"], (
        "the card is not the narrow slot, so the 1:4 split is applied the wrong way round")


# --- 🚨 R-736: the mark's label, as a worked subtraction ------------------------------------

def _annotation(chart):
    """One chart's annotation, as (texts, logo urls) read out of the SHIPPED SPEC.

    🚨 R-751 MOVED IT INSIDE THE VEGA SPEC, so these assertions moved with it. B100 put the
    block BESIDE the chart because marks inside the spec can move the box `autosize: pad`
    ships; this round put it in and PROVES the box did not move —
    `test_the_spec_STREAMLIT_SHIPS_does_not_make_height_the_outer_box` is the proof, and it
    runs against this same chart.
    """
    spec = chart.to_dict()
    # ⚠️ A LAYER'S `data` IS A NAMED REFERENCE, NOT INLINE VALUES. Altair hoists every frame into
    # a top-level `datasets` map and leaves `{"name": "data-…"}` behind, so reading
    # `layer["data"]["values"]` finds nothing and this helper returns empty — which would make
    # every assertion below vacuously true. Resolved rather than assumed.
    datasets = spec.get("datasets", {})

    def rows(layer):
        data = layer.get("data") or {}
        if "values" in data:
            return data["values"]
        return datasets.get(data.get("name"), [])

    texts, urls = [], []
    for layer in spec.get("layer", []):
        mark = layer.get("mark")
        kind = mark.get("type") if isinstance(mark, dict) else mark
        if kind == "text":
            texts.extend(str(v["t"]) for v in rows(layer) if "t" in v)
        elif kind == "image":
            urls.extend(str(v["u"]) for v in rows(layer) if "u" in v)
    assert texts or urls, "the annotation could not be read out of the spec at all"
    return texts, urls


def test_the_annotation_is_a_worked_SUBTRACTION_in_three_rows(panel):
    """Marc, v04: *"The logo math that ties to the mark is supposed to be a label/annotation on
    the chart. Needs to be smaller."*

    ⚠️ ASSERTED IN ORDER, not on presence. All three numbers appear elsewhere on the panel
    already; what makes this an annotation rather than three numbers is that they are stacked
    as a subtraction, gained over allowed over the delta.
    """
    charts = _charts(panel(_game(), _both(), deltas=_deltas())[0])
    texts, _urls = _annotation(charts[0])
    joined = " | ".join(texts)
    assert joined.index("Rushing") < joined.index("Allowed") < joined.index("+38.0"), (
        f"the annotation is not gained, then allowed, then the delta: {texts}")


def test_the_annotation_size_is_BETWEEN_v04s_floor_and_a_ceiling_the_plot_can_hold(panel):
    """🚨 THE SIZE INSTRUCTION REVERSED BETWEEN v04 AND v05, AND THIS RECORDS BOTH ENDS.

      v04  *"Needs to be smaller. Font size similar to the axis labels, maybe a little
           smaller."*  -> B103 shipped 8.5
      v05  *"in-chart legend, nice. Move it to the top right. Increase font substantially."*

    ⚠️ **8.5 IS THE FLOOR NOW, NOT THE TARGET.** It went past readable, and citing v04 to keep it
    small would be answering the instruction he replaced. ✅ The axis labels are the reference he
    reached for twice, so the size sits at theirs rather than below them.

    ⚠️ AND THE CEILING IS THE PLOT. `_CHART_SIDE` is 240px; three lines at 14px plus a rule is a
    quarter of the square's height, and the annotation would start competing with the data it
    describes. **The round rendered two sizes and the report says what each costs.**
    """
    charts = _charts(panel(_game(), _both(), deltas=_deltas())[0])
    sizes = {layer["mark"]["fontSize"] for layer in charts[0].to_dict().get("layer", [])
             if isinstance(layer.get("mark"), dict) and "fontSize" in layer["mark"]}
    assert sizes, "the annotation carries no explicit font size"
    assert min(sizes) > 8.5, (
        f"the annotation is back at or below v04's size, which Marc replaced: {sizes}")
    assert max(sizes) <= 12, (
        f"three lines of {max(sizes)}px plus a rule take too much of a 240px plot — the "
        f"annotation starts competing with the mark it describes: {sizes}")


def test_the_annotation_is_anchored_to_the_TOP_RIGHT(panel):
    """Marc, v05: *"Move it to the top right."*

    ⚠️ `alt.value()` POSITIONS FROM THE LEFT, so "right" is the plot width minus a margin and a
    test that only checked for a large x would pass on a block that ran off the plot. The right
    edge is asserted against `_CHART_SIDE` itself.
    """
    charts = _charts(panel(_game(), _both(), deltas=_deltas())[0])
    side = _module_constant("_CHART_SIDE")
    xs = []
    for layer in charts[0].to_dict().get("layer", []):
        mark = layer.get("mark")
        kind = mark.get("type") if isinstance(mark, dict) else mark
        if kind in {"text", "image"} and "value" in (layer.get("encoding", {}).get("x") or {}):
            xs.append(layer["encoding"]["x"]["value"])
    assert xs, "no screen-positioned annotation layer found"
    assert max(xs) <= side, f"the annotation runs off the right edge of a {side}px plot: {xs}"
    assert min(xs) > side / 2, (
        f"part of the annotation is in the LEFT half of the plot, so it is not anchored to the "
        f"top right: {xs}")


def test_the_annotation_carries_BOTH_logos(panel):
    """The logos are what make it a subtraction rather than three numbers."""
    charts = _charts(panel(_game(), _both(), deltas=_deltas())[0])
    _texts, urls = _annotation(charts[0])
    assert len(urls) == 2, f"expected this team's logo and the opponent's: {urls}"
    assert urls[0] != urls[1]


def test_a_NULL_logo_puts_the_TEAM_NAME_in_the_annotation(panel):
    """🚨 AC-G.11 AT 8.5px, AND THE FALLBACK HAD TO CHANGE WITH THE MOVE.

    B100 rendered a missing logo as `identity.logo_or_monogram`'s empty box plus the team name,
    because the helper's own comment says the box is only safe when *"the name is right there"*.
    ⚠️ **Inside a Vega spec there is no `identity` and no monogram** — so the row falls back to
    the team's NAME as a text mark in the logo's place, which is the same promise kept by the
    only means available.
    """
    sides = _both()
    sides[0]["logo_url"] = None
    sides[1]["logo_url"] = None
    charts = _charts(panel(_game(), sides, deltas=_deltas())[0])
    texts, urls = _annotation(charts[0])
    assert not urls, f"a null logo still emitted an image mark: {urls}"
    joined = " ".join(texts)
    assert "Kentucky" in joined and "Auburn" in joined, (
        f"a row with no logo must NAME its team — nothing else in the annotation does: {texts}")


def test_a_PRESENT_logo_does_NOT_repeat_the_team_name(panel):
    """⚠️ MARC'S OWN COMPLAINT, one level down: he flagged the name appearing twice. The name is
    a FALLBACK for an absent logo, not a second label beside a present one."""
    charts = _charts(panel(_game(), _both(), deltas=_deltas())[0])
    texts, _urls = _annotation(charts[0])
    joined = " ".join(texts)
    assert "Kentucky" not in joined and "Auburn" not in joined, (
        f"the team name is drawn beside a logo that is present: {texts}")


def test_the_annotation_reads_A106s_COLUMN_and_subtracts_nothing(panel):
    """🚨 §4.2. The delta is a published column at game x team grain precisely so this page does
    not compute it; a subtraction here would let the annotation disagree with the Excel export,
    which reads the same column — R-645, one panel along.

    ⚠️ PROVED BY MAKING THE COLUMN DISAGREE WITH ITS OWN INPUTS. A page that subtracts would
    print 69.9; a page that reads prints the column. A fixture whose delta happens to equal
    `gained - allowed` cannot tell the two apart.
    """
    deltas = [dict(r, rushing_yards_for_minus_opponent_allowed_per_game=-12.5)
              for r in _deltas()]
    texts, _urls = _annotation(_charts(panel(_game(), _both(), deltas=deltas)[0])[0])
    joined = " ".join(texts)
    assert "-12.5" in joined or "−12.5" in joined, \
        f"the annotation did not print the column's value: {texts}"
    assert "69.9" not in joined, "the page subtracted instead of reading A106's column"


def test_a_NULL_delta_renders_an_em_dash_and_a_ZERO_renders_a_number(panel):
    """AC-G.32, on the result row. A null is the absence of a measurement; a zero is one."""
    nulls = [dict(r, rushing_yards_for_minus_opponent_allowed_per_game=None)
             for r in _deltas()]
    texts, _u = _annotation(_charts(panel(_game(), _both(), deltas=nulls)[0])[0])
    assert "—" in " ".join(texts)
    zeros = [dict(r, rushing_yards_for_minus_opponent_allowed_per_game=0.0)
             for r in _deltas()]
    drawn = " ".join(_annotation(_charts(panel(_game(), _both(), deltas=zeros)[0])[0])[0])
    assert "—" not in drawn, "a measured zero rendered as an absence"
    assert "+0.0" in drawn, (
        "exactly level is a real answer and rendering it bare reads as 'no figure' — the chip "
        "has said so since R-686, and the annotation shares that renderer")


def test_the_delta_CHIP_no_longer_carries_a_COLOUR(panel):
    """✅ COWORK'S RULING, and Marc can reverse it in one line.

    The chip is `gained − allowed`, red when negative. The mark v02.3 introduces paints that
    SAME comparison GREEN, because a defence conceding more than this offence gains is a
    FAVOURABLE matchup. Red would then point two ways within an inch of itself.

    ⚠️ AND IT COSTS NOTHING A GREYSCALE READER HAD: B091 established on this very delta that
    the SIGN carries it and the colour only agrees (AC-G.22).
    🚨 R-756 DELETED THE CHIP ITSELF, AND THE RULING OUTLIVES IT. The same comparison is now
    the annotation's bold bottom line, an inch from a mark whose COLOUR says the opposite thing
    — so "red points two ways in one panel" is live, on the same chart rather than across it.
    ✅ Asserted on the annotation's own layers: the delta line carries no colour, and the sign
    still carries the fact.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    charts = _charts(entries)
    assert charts, "no charts drew, so the annotation could not be checked"
    for chart in charts:
        for layer in chart.to_dict().get("layer", []):
            mark = layer.get("mark")
            if not isinstance(mark, dict) or mark.get("type") != "text":
                continue
            if mark.get("fontWeight") != "bold":
                continue
            assert "color" not in mark and "fill" not in mark, (
                f"the delta line is tinted, so red points two ways within one chart: {mark}")
    drawn = " ".join(t for c in charts for t in _annotation(c)[0])
    assert "-6.0" in drawn or "\u22126.0" in drawn, (
        f"the sign is what carries it and it is gone: {drawn}")


# --- 🚨 R-722: the mark, and the pairing a presence assertion cannot see -------------------

_OUTLOOK_MACRO = (Path(__file__).resolve().parents[1] / "dbt" / "macros"
                  / "matchup_outlook.sql")


def _mark_of(chart):
    """One chart's point mark, as (shape, colour, filled)."""
    spec = chart.to_dict()
    layers = spec.get("layer", [])
    point = next(layer for layer in layers
                 if isinstance(layer.get("mark"), dict)
                 and layer["mark"].get("type") == "point")
    mark = point["mark"]
    return mark.get("shape"), mark.get("color"), mark.get("filled")


def _with_outlook(value, metric="rushing"):
    """The deltas frame with one metric's outlook forced to `value` on both sides."""
    return [dict(r, **{f"{metric}_matchup_outlook": value}) for r in _deltas()]


def test_the_MAPPING_KEYS_are_the_values_the_warehouse_actually_stores():
    """🚨 THE FAILURE THIS PREVENTS ALREADY HAPPENED ONCE, ONE LAYER UP.

    A119 shipped `favourable`, `test_no_dbt_description_uses_british_spelling` failed the build,
    and the value changed to `favorable`. ⚠️ **Cowork's prompt for THIS round still specified the
    British spelling.** A mapping keyed on `favourable` matches nothing, every mark falls to the
    unclassified look, and NOTHING ELSE SAYS SO — the page renders, the suite passes, and three
    verdicts quietly become one.

    ✅ So the keys are read out of the macro that WRITES them — `ci/check_health_signals.py`'s
    shape, which A110 named as the model for exactly this.

    ⚠️ SCOPE, IN THE SAME SENTENCE AS THE CLAIM: this compares the string literals emitted by
    `dbt/macros/matchup_outlook.sql` against the keys of `_OUTLOOK_MARKS`. It cannot see a value
    written by any other model, and it says nothing about which LOOK each value gets.
    """
    assert _OUTLOOK_MACRO.exists(), f"{_OUTLOOK_MACRO.name} moved — this guard is pinned by name"
    stored = set(re.findall(r"then '([a-z_]+)'", _OUTLOOK_MACRO.read_text()))
    stored |= set(re.findall(r"else '([a-z_]+)'", _OUTLOOK_MACRO.read_text()))
    assert stored, "no outlook literals found in the macro — the parse has gone blind"
    mapped = set(_module_constant("_OUTLOOK_MARKS"))
    assert stored == mapped, (
        f"the warehouse stores {sorted(stored)} and matchup.py maps {sorted(mapped)}. A key the "
        f"page does not have falls to the UNCLASSIFIED mark on every game and nothing else "
        f"reports it — which is precisely how `favourable` would have shipped.")


def test_each_STORED_VALUE_gets_ITS_OWN_LOOK_not_merely_A_look(panel):
    """🚨 A PRESENCE ASSERTION IS BLIND TO A SWAP, AND THIS PROJECT HAS PROVED IT THREE TIMES —
    B082 on the game header, B083 on the win-probability bar, and A119 one layer down, where
    reversing its two positive-delta branches passed the exhaustiveness test completely.

    So the VALUE-to-LOOK pairing is asserted, one row at a time. Marc's rule:

        favorable   -> green circle       challenging -> red diamond
        contested   -> yellow circle
    """
    seen = {}
    for value in ("favorable", "contested", "challenging"):
        entries, _ = panel(_game(), _both(), deltas=_with_outlook(value))
        seen[value] = _mark_of(_charts(entries)[0])
    shapes = {v: m[0] for v, m in seen.items()}
    colours = {v: m[1] for v, m in seen.items()}
    assert shapes["favorable"] == shapes["contested"] == "circle", \
        f"Marc's rule gives favorable and contested a CIRCLE: {shapes}"
    assert shapes["challenging"] == "diamond", (
        f"`challenging` must be the DIAMOND — it is the one state a greyscale reader can find "
        f"by outline alone: {shapes}")
    assert len({colours["favorable"], colours["contested"], colours["challenging"]}) == 3, \
        f"two outlooks share a colour: {colours}"
    # 🚨 THE SWAP THE BREAK STAGES: green must be the FAVOURABLE one, not merely present.
    assert _luminance(colours["challenging"]) < _luminance(colours["contested"]), (
        f"the challenging mark is not the darkest — swapping favorable and challenging in the "
        f"mapping would paint a hard matchup green: {colours}")
    assert colours["favorable"] != colours["challenging"]


def _luminance(hex_colour: str) -> float:
    """Rec. 601 luma, which is what a greyscale render collapses a colour to."""
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


def test_GREEN_and_YELLOW_are_separated_in_GREYSCALE_too(panel):
    """⚠️ AC-G.22, AND THIS IS THE ONE PLACE MARC'S RULE SPENDS COLOUR ALONE.

    Two of the three states are CIRCLES, so `favorable` and `contested` differ by colour and
    nothing else. In greyscale, or to a red-green colour-blind reader, that is one distinction
    rather than two — unless the two tones are far enough apart in LUMINANCE to read as light
    and dark.

    🚨 SO THE TONES ARE CHOSEN FOR LUMA DISTANCE RATHER THAN HUE, and this asserts it rather
    than trusting the eye. The round's report carries the greyscale picture.
    """
    tones = {v: _mark_of(_charts(panel(_game(), _both(), deltas=_with_outlook(v))[0])[0])[1]
             for v in ("favorable", "contested", "challenging")}
    lumas = {v: _luminance(c) for v, c in tones.items()}
    gap = abs(lumas["favorable"] - lumas["contested"])
    assert gap >= 40, (
        f"favorable and contested are both circles, so greyscale leaves only their tone to "
        f"tell them apart, and these two collapse to {lumas['favorable']:.0f} and "
        f"{lumas['contested']:.0f} — a gap of {gap:.0f}. Under 40 they read as the same grey "
        f"disc and the panel has two marks a colour-blind reader cannot distinguish.")


def test_an_UNCLASSIFIED_mark_does_not_BORROW_one_of_the_three_looks(panel):
    """🚨 REACHABLE, AND MEASURED RATHER THAN ASSUMED (AC-G.11).

    The prompt expected a null outlook to be unreachable, because `_scatter` returns None when
    either figure is missing and A119 proved the outlook is null on exactly the rows the delta
    is null on — 0 rows disagree across all 225,350.

    ⚠️ BUT THOSE ARE DIFFERENT RELATIONS — `srv_game_team` at game x team grain against
    `srv_team_week` at week grain — so nothing STRUCTURAL ties the two absences together.

    🚨 CHASED, AND THE HONEST ANSWER IS "NOT DEMONSTRATED". 243 rows in 2026 carry a null rushing
    outlook while that team has both team-week figures at that game's week — ⚠️ but that is the
    NECESSARY condition only, and `_scatter` also needs the week's distribution, a non-degenerate
    axis and a point inside the frame. A sample of those 243 rendered ZERO charts.

    ✅ SO THE BRANCH IS NEITHER PROVEN REACHABLE NOR PROVEN DEAD, and this test is what keeps it
    honest if it ever draws: a shape neither other state uses, unfilled, in grey.
    """
    shape, colour, filled = _mark_of(
        _charts(panel(_game(), _both(), deltas=_with_outlook(None))[0])[0])
    marks = _module_constant("_OUTLOOK_MARKS")
    assert shape not in {m[0] for m in marks.values()} or filled is False, (
        f"an unclassified mark borrowed a classified look: {(shape, colour, filled)}")
    assert filled is False, "the unclassified mark must be hollow — it is not a fourth verdict"
    assert colour not in {m[1] for m in marks.values()}, \
        f"the unclassified mark uses a verdict's colour: {colour}"


def test_an_UNKNOWN_outlook_string_falls_to_the_UNCLASSIFIED_look_not_a_verdict(panel):
    """A value the warehouse starts emitting that this page has never heard of must not be
    painted as one of Marc's three. `test_the_MAPPING_KEYS…` is what makes it LOUD; this is what
    makes it SAFE in the meantime."""
    shape, colour, filled = _mark_of(
        _charts(panel(_game(), _both(), deltas=_with_outlook("favourable"))[0])[0])
    assert filled is False and shape == "square", (
        f"the British spelling — the one Cowork's prompt specified — was painted as a verdict: "
        f"{(shape, colour, filled)}")


# --- 🚨 R-753 / R-752: the card header, and the metric header that left the spec -----------

def _header_row(entries, name):
    """One card's header row markup, by the player it names."""
    block = next(str(b) for k, b in entries
                 if k == "markdown" and name in _plain(str(b)))
    card = next(piece for piece in block.split("border:1px solid rgba(128,128,128,.22)")
                if name in _plain(piece))
    return card.split("repeat(3,1fr)")[0]


def test_the_name_renders_LAST_COMMA_FIRST_and_not_merely_that_it_appears(panel):
    """🚨 A PRESENCE ASSERTION CANNOT SEE THIS SWAP. B082 proved it on the game header and B083
    on the win-probability bar; *Avant Lloyd* contains exactly the same characters as
    *Lloyd Avant*.

    Marc: *"Present player name on 2 lines. First name on top, not bold and small. Bold last
    name."* ✅ So the WEIGHT is asserted against the part, not the presence of either.
    """
    # ⚠️ LOOKED UP BY A SINGLE TOKEN, NOT THE WHOLE NAME. Searching for "Lloyd Avant" makes the
    # swap a StopIteration in this helper — a crash, which proves the helper is narrow rather
    # than that the card is wrong. "Avant" is present whichever line it lands on, so the
    # assertion below is what fails.
    header = _header_row(panel(_game(), _both(), deltas=_deltas())[0], "Avant")
    # ⚠️ SCOPED TO THE NAME COLUMN SINCE R-801. The POSITION now carries the same weight and
    # size — that is the point of the mirror — so a bare `font-weight:700` sweep returns two
    # strings and this assertion would be about whichever came first.
    name = re.findall(r"text-overflow:ellipsis[^>]*>([^<]+)<", header)
    assert name == ["Avant, Lloyd"], (
        f"the name is not `Last, First` — and `First Last` contains exactly the same "
        f"characters, so nothing that merely looks for the name can see the difference: {name}")
    assert name[0].index("Avant") < name[0].index("Lloyd"), "the surname must come first"


def test_a_SINGLE_TOKEN_name_has_NO_COMMA_and_no_empty_second_part(panel):
    """⚠️ AC-G.11 ON A NAME. An empty first line would still take its line-height and push that
    one card's header down relative to its neighbours — a hole reserved for something that does
    not exist.

    🚨 MEASURED AGAINST LIVE SERVING RATHER THAN ASSUMED: `srv_game_team_leader_through_prior_
    week` carries **no single-token `player_name`** today — every one of the 75,283 rows has at
    least two tokens. **So this is a defensive branch, and saying so is the measurement.** It is
    still asserted, because "none today" is not "none ever" and a one-word name is a rendering
    decision rather than a data error.
    """
    rows = [dict(r, player_name="Ochocinco") if r["leader_rank"] == 1 else r
            for r in _leaders()]
    header = _header_row(panel(_game(), _both(), deltas=_deltas(), leaders=rows)[0],
                         "Ochocinco")
    name = re.findall(r"text-overflow:ellipsis[^>]*>([^<]+)<", header)
    assert name == ["Ochocinco"], f"a one-token name did not render alone: {name}"
    assert "," not in name[0], (
        "a one-token name rendered a comma with nothing after it, which reads as a truncated "
        "surname rather than as a whole name")


def test_a_leader_with_NO_POSITION_renders_an_EM_DASH_and_never_the_string_nan(panel):
    """🚨 THE LIVE RENDER FOUND THIS, AND `or ""` IS WHY IT SURVIVED THREE ROUNDS. A null
    arrives out of the frame as `float('nan')`, **and NaN is TRUTHY in Python** — so
    `str(row.get("position") or "")` returns the NaN and the card printed the three characters
    `nan` where a position belongs. B106's render of Arkansas vs North Alabama shows it on
    three of the four away cards.

    ⚠️ NOT RARE, MEASURED IN SERVING RATHER THAN ASSUMED: 13,431 of 75,283 rows on
    `srv_game_team_leader_through_prior_week` (17.8%) and 3,734 of 53,873 on
    `..._in_this_game` (6.9%) carry no position and no class year.

    ✅ AC-G.32, AND THE TWO SLOTS ANSWER DIFFERENTLY ON PURPOSE. The position is a VALUE, so an
    absent one is an em dash — the same statement the jersey already makes. The year is the
    small faded line, the surname block's mirror, so an absent year is an absent LINE: B103
    settled that a missing first name renders the bold line alone rather than an empty row that
    shifts the card's height.
    """
    rows = [dict(r, position=float("nan"), class_year_display=float("nan"))
            if r["leader_rank"] == 1 else r for r in _leaders()]
    header = _header_row(panel(_game(), _both(), deltas=_deltas(), leaders=rows)[0], "Avant")
    assert "nan" not in header.lower(), (
        f"a null position or class year reached the page as the literal string `nan`: "
        f"{_plain(header)!r}")
    # ⚠️ ASSERTED ON THE POSITION'S OWN SLOT, not on the card. The jersey already renders an em
    # dash elsewhere, so a card-wide dash count cannot tell the two absences apart.
    slot = header.split("text-align:right;min-width:0")[1]
    assert "—" in slot, "an absent position must render an em dash in its own slot"
    assert slot.count("—") == 1, (
        f"an absent YEAR drew a dash of its own — it is the faded mirror of the first-name "
        f"line and an absent one is an absent line, not a hole: {_plain(slot)!r}")


def test_the_RANK_is_not_on_the_card_at_all(panel):
    """Marc: *"Don't include the rank."* Asserted on the header row rather than the whole panel,
    because "1st" appears in prose elsewhere on the page."""
    header = _header_row(panel(_game(), _both(), deltas=_deltas())[0], "Avant")
    for marker in ("1st", "2nd", "3rd", "T-"):
        assert marker not in header, f"the card header still carries {marker!r}"


def test_the_METRIC_HEADER_is_emitted_OUTSIDE_the_chart_spec(panel):
    """🚨 R-752, AND A TEST THAT THE TEXT IS ON THE PAGE WOULD PASS EITHER WAY.

    Marc: *"The header over the Chart should be the header for the whole row."* `Rushing` was the
    Altair spec's own `title=`, which can only ever sit over the chart — so the assertion is that
    it is NOT in the spec and IS in the markup, not that it exists.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    for chart in _charts(entries):
        spec = chart.to_dict()
        assert "title" not in spec, (
            f"the metric is still the chart's own title, so it can never be a ROW header: "
            f"{spec.get('title')!r}")
    headers = [_plain(str(b)) for k, b in entries
               if k == "markdown" and _plain(str(b)) in {"Rushing", "Passing", "Total"}]
    assert headers == ["Rushing", "Passing", "Total"] * 2, (
        f"expected one header per metric per half, emitted before each row: {headers}")


def test_a_small_RULE_separates_the_three_blocks_and_not_the_first(panel):
    """Marc: *"There should a small line or element to break the space between Rushing, Passing,
    and Total."* ⚠️ Subtle — the three blocks are one panel, so a rule BEFORE the first would
    section the panel off from the delta table above it."""
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    rules = [str(b) for k, b in entries
             if k == "markdown" and "opacity:.12" in str(b)]
    assert len(rules) == 4, (
        f"expected a rule between the blocks on each half — two per half, none before the "
        f"first — got {len(rules)}")


def test_the_SUBTRACTION_RULE_is_drawn_and_not_merely_specified(panel):
    """🚨 IT WAS IN THE SPEC AND DID NOT APPEAR, WHICH A SPEC ASSERTION CANNOT SEE.

    The rule was a `mark_rule` positioned entirely in SCREEN values inside a layer chart that
    has scales. ⚠️ **It serialised at the right coordinates and drew nothing** — so a test
    asserting "a rule layer exists" passed while the reader saw three numbers in a list, which
    is exactly what the rule exists to prevent (v02.2: *"like a math problem"*).

    ✅ A one-pixel `mark_rect` with all four edges as values does draw. **This asserts the MARK
    TYPE, because that is the part that was wrong** — and the render in B104's report is the
    evidence that it appears.
    """
    charts = _charts(panel(_game(), _both(), deltas=_deltas())[0])
    rects = [layer for layer in charts[0].to_dict().get("layer", [])
             if isinstance(layer.get("mark"), dict)
             and layer["mark"].get("type") == "rect"
             and "value" in (layer.get("encoding", {}).get("y") or {})]
    assert len(rects) == 1, (
        f"expected exactly one screen-positioned rect — the subtraction's rule: {len(rects)}")
    edges = rects[0]["encoding"]
    assert edges["y2"]["value"] - edges["y"]["value"] == 1, "the rule is not one pixel tall"
    assert edges["x2"]["value"] > edges["x"]["value"], "the rule has no width"
