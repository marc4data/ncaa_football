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
# 🚨 cfdb-wta-R-900 ADDED THE WHISKER PAIR, AND WITHOUT IT EVERY CHART IN THIS FILE WAS A
# PLACEHOLDER. `distribution.box` frames on `whisker_low`/`whisker_high` and reads them through
# `_whisker_pair`, which looks BOTH keys up in the row and returns `(None, None)` when neither is
# there — at which point `box()` returns its em-dash span **without raising**. ⚠️ So a fixture
# missing these two columns renders a panel of dashes that every presence assertion passes on.
# ✅ The six pairs are READ BACK FROM SERVING for this fixture's own week, like the quartiles
# beside them — `select whisker_low, whisker_high … where season=2025 and season_type='regular'
# and week=12`, 2026-09-15 — so the fixture cannot describe a spread the warehouse never built.
#
# ⚠️ AND ONE DRIFT IS RECORDED RATHER THAN SILENTLY CORRECTED: this fixture carries
# `rushing_yards_for_per_game` axis_max 350.0 where serving publishes 275.0. **It is left alone.**
# The axis columns are the HISTOGRAM's frame, `box()` reads neither, and the tests that used them
# were the scatter's. Changing a number this file does not use would be noise in a round that
# already moves a lot.
_METRICS = {
    #                                  axis_min, axis_max,  p25,      p50,     p75,    w_low,  w_high
    "rushing_yards_for_per_game":     (50.0, 350.0, 126.65, 156.15, 186.00, 69.3, 269.1),
    "passing_yards_for_per_game":     (50.0, 350.0, 194.725, 231.35, 258.575, 107.3, 333.8),
    "total_yards_for_per_game":       (200.0, 550.0, 344.975, 387.90, 428.675, 244.6, 508.0),
    "rushing_yards_allowed_per_game": (60.0, 240.0, 124.625, 146.00, 170.10, 76.6, 232.9),
    "passing_yards_allowed_per_game": (125.0, 300.0, 193.45, 219.80, 241.30, 126.1, 298.6),
    "total_yards_allowed_per_game":   (200.0, 500.0, 325.825, 373.25, 403.475, 211.6, 479.3),
}


_OUTLOOK_MACRO = (Path(__file__).resolve().parents[1] / "dbt" / "macros"
                  / "matchup_outlook.sql")


def _distribution(min_games=9, axes=None, **overrides):
    """The week's six rows. `axes` replaces the limits of named metrics only.

    ⚠️ `axes` IS PER-METRIC AND `overrides` IS NOT — R-601 needs one metric's frame moved
    while the other five stay put, because the defect is a single axis that cannot hold a
    single value. `**overrides` updates every row and would move all six.
    """
    axes = axes or {}
    rows = []
    for metric, (low, high, p25, p50, p75, w_low, w_high) in _METRICS.items():
        low, high = axes.get(metric, (low, high))
        rows.append({
            "season": 2025, "season_type": "regular", "week": 12, "metric": metric,
            "n": 136, "teams_in_week": 136,
            "min_games_counted": min_games, "max_games_counted": 10,
            "mean": p50, "stddev": 59.0,
            "p25": p25, "p50": p50, "p75": p75,
            "whisker_low": w_low, "whisker_high": w_high,
            "axis_min": low, "axis_max": high, "axis_step": 50.0,
            "as_of_ts": pd.Timestamp("2026-09-10 12:00:00+00:00"),
        })
    for row in rows:
        row.update(overrides)
    return rows


def _calendar(team_games=None):
    """Both sides' regular-season calendars, kickoff DESCENDING — what `srv_game_team` returns.

    📊 MEASURED, NOT INVENTED. This is **Boise State's real 2026 regular calendar** read back from
    serving on 2026-09-15, re-keyed onto this file's two teams: **11 games, not 12**, two played
    and nine still scheduled, and **week 7 missing because it is a bye**. ⚠️ Those three
    properties are the ones the strip has to survive, and a hand-built 12-row ladder has none of
    them.

    🚨 AND THE NULLS ARE THE POINT. Measured on 2026 regular serving: `total_yards` is NULL on
    **all 5,848 `scheduled` rows and all 842 `no_box_score` rows**, and non-null on all 668
    `played` ones. **So the two absences are indistinguishable from the figure alone** — the page
    must read `game_figures_state`, and a fixture that filled them with zeros could not tell
    anyone that.
    """
    real = [
        (12, "2026-11-21", True, "SDSU", None, None, "scheduled"),
        (11, "2026-11-14", True, "ORST", None, None, "scheduled"),
        (10, "2026-11-07", False, "CSU", None, None, "scheduled"),
        (9, "2026-10-31", True, "TXST", None, None, "scheduled"),
        (8, "2026-10-24", False, "WSU", None, None, "scheduled"),
        (6, "2026-10-10", False, "FRES", None, None, "scheduled"),
        (5, "2026-10-03", True, "USU", None, None, "scheduled"),
        (4, "2026-09-26", False, "WMU", None, None, "scheduled"),
        # ⚠️ ONE ROW IS RE-STATED AS `no_box_score` SO THE THIRD SENTENCE HAS A SUBJECT. On real
        # serving this is a D-III or D-II opponent: of the 842 such team-games in 2026 regular,
        # **425 are Division III, 368 Division II, 5 FCS and 0 FBS.**
        (3, "2026-09-19", True, "SDAK", None, None, "no_box_score"),
        (2, "2026-09-12", True, "MEM", 578, 519, "played"),
        (1, "2026-09-05", False, "ORE", 274, 497, "played"),
    ]
    rows = []
    for team in (AWAY_ID, HOME_ID):
        for week, date, home, abbr, yards, allowed, state in (team_games or real):
            rows.append({
                "team_id": team, "week": week,
                "game_date": pd.Timestamp(date, tz="UTC"), "is_home": home,
                "opponent_abbreviation": abbr,
                "total_yards": yards, "rushing_yards": yards,
                "passing_yards": yards,
                "total_yards_allowed": allowed, "rushing_yards_allowed": allowed,
                "passing_yards_allowed": allowed,
                "game_figures_state": state})
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
                leaders=None, usage=None, calendar=None,
                allow_error_state=allow_error_state):
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
                # 🚨 R-899's CALENDAR, AND IT DISPATCHES BEFORE THE DELTAS BRANCH FOR EXACTLY THE
                # REASON R-694's COMMENT GIVES ABOVE. This query reads `srv_game_team` too, so a
                # later branch would answer it with the DELTAS frame — two rows at game × team
                # grain, carrying none of `game_date`, `opponent_abbreviation` or
                # `game_figures_state`. ⚠️ **That is not a crash, it is a strip drawn from the
                # wrong relation**, and it is how this stub first reported the panel as raising.
                if "game_figures_state" in sql:
                    seen["calendar_sql"], seen["calendar_params"] = sql, params or {}
                    return pd.DataFrame(calendar if calendar is not None else _calendar())
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


def _away_over(**overrides):
    """Both real sides, with the AWAY row overridden.

    ⚠️ `_both(**kw)` OVERRIDES THE HOME SIDE, and hand-building a two-row list with ids 1 and 2
    does not match `_game()`'s — which degrades the whole panel rather than failing on the row
    under test. **A fixture that cannot be looked up is not a fixture for the case.**
    """
    return [dict(row, **overrides) if row["team_id"] == AWAY_ID else row for row in _both()]


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
    """The altair charts the panel drew, in the order it drew them.

    🚨 cfdb-wta-R-900: THIS MUST NOW RETURN NOTHING, AND THAT IS AN ASSERTION RATHER THAN A
    LEFTOVER. Marc replaced the scatter with a box-and-whisker, which `distribution.box` emits
    as SVG inside markdown — so a chart entry surviving anywhere in this panel means an Altair
    spec is still being shipped. The helper is kept, pointed at the same place, and one test
    below asserts it is empty.
    """
    return [body for kind, body in entries if kind == "chart"]


# --- cfdb-wta-R-900: the panel's markup is the instrument now --------------------------------
#
# ⚠️ EVERY READER BELOW ANCHORS ON A `data-cfdb` ATTRIBUTE, NOT ON A STYLE STRING. R-886 is one
# round old and it is exactly this file's lesson: the card helpers matched nothing the moment a
# border colour moved, because they keyed on the literal grey. **The attribute exists to be
# anchored on; a style string is not an interface.**

def _markup(entries) -> str:
    """Everything the panel wrote as markdown, joined, tags intact."""
    return " ".join(body for kind, body in entries
                    if kind != "chart" and isinstance(body, str))


def _blocks(entries) -> list:
    """`(metric, markup)` for each Gained/Allowed chart, in the order the panel drew them."""
    out = []
    for chunk in _markup(entries).split("<div data-cfdb='gained-allowed'")[1:]:
        metric = re.search(r"data-metric='([^']*)'", chunk)
        out.append((metric.group(1) if metric else None, chunk))
    return out


def _of_metric(entries, metric: str) -> list:
    """Both sides' blocks for one metric, away first — the panel emits away then home."""
    return [markup for name, markup in _blocks(entries) if name == metric.lower()]


def _series(block: str) -> dict:
    """`{"gained": markup, "allowed": markup}` for one chart block."""
    found = {}
    for chunk in block.split("<div data-cfdb='box-series'")[1:]:
        name = re.search(r"data-series='([^']*)'", chunk)
        if name:
            # ⚠️ THE SPLIT LANDS INSIDE THE OPENING TAG, so the attributes that follow are still
            # markup. Dropping to the first `>` is what makes `_plain` return the sentence a
            # reader sees rather than the style string in front of it.
            found[name.group(1)] = chunk.split(">", 1)[1]
    return found


def _legend(block: str) -> str:
    """The top-right worked subtraction, as plain text."""
    piece = block.split("data-cfdb='matchup-legend'")[1].split(">", 1)[1]
    return _plain(piece.split("data-cfdb='box-series'")[0])


def _value_marks(series: str) -> list:
    """The `<text>` labels `box()` drew in the marker's own colour — the team's own figure.

    ⚠️ IT READS THE COLOURED LABELS ONLY. `box()` prints the boundary and percentile labels with
    `fill='currentColor'`; the value carries `fill='<the accent>'`, which is the one thing that
    distinguishes the reader's own number from the frame's. **A test counting every `<text>`
    would pass on a chart that dropped the value and kept its ticks.**
    """
    return re.findall(r"<text[^>]*fill='(?!currentColor)[^']*'[^>]*>([^<]*)</text>", series)


def _svg_of(series: str) -> str:
    """One series' <svg>, or "" when `box()` returned its placeholder instead."""
    found = re.search(r"<svg.*?</svg>", series, re.S)
    return found.group(0) if found else ""


# --- the pairing, which is the whole point -------------------------------------------------

def test_the_pairing_runs_across_sides_not_down_one(panel):
    """⚠️ THE ASSERTION THIS FILE EXISTS FOR (1c).

    Kentucky's rushing attack is 154.4 and Auburn allows 84.5 on the ground. Those two must
    appear TOGETHER, in that order, on one line — Kentucky's number beside AUBURN's, not
    beside Kentucky's own 132.6 allowed.

    🚨 THE ANCHOR HAS MOVED TWICE AND THE CLAIM HAS NOT. It read the delta table's rows; R-756
    removed the table and it read the chart's Vega annotation; cfdb-wta-R-900 replaces the Vega
    chart and it reads the legend's markup. ✅ **Still PER BLOCK, which is what makes the negative
    half bite**: the away rushing block must contain Auburn's 84.5 and must NOT contain
    Kentucky's own 132.6.
    """
    entries, _ = panel(_game(), _both())
    rushing = _of_metric(entries, "Rushing")
    assert len(rushing) == 2, f"expected one rushing block per side, got {len(rushing)}"
    away, home = rushing
    away_text = _legend(away)
    assert "154.4" in away_text, f"Kentucky's rushing offense is missing: {away_text}"
    assert "84.5" in away_text, (
        f"Kentucky's attack is not paired with AUBURN's rushing defense: {away_text}")
    assert "132.6" not in away_text, (
        f"the panel paired Kentucky's offense with Kentucky's own defense — one team "
        f"described as though it were a matchup: {away_text}")

    home_text = _legend(home)
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
    """Marc named both, separately, and asked for them separately rather than as a total."""
    entries = panel(_game(), _both())[0]
    body = _text(entries)
    assert "Rushing" in body and "Passing" in body
    drawn = " ".join(_legend(markup) for _metric, markup in _blocks(entries))
    for figure in ("154.4", "84.5", "170.8", "132.6"):
        assert figure in drawn, f"{figure} is on no block of the panel: {drawn}"


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


def test_the_FRAME_comes_from_the_WEEKS_ROW_and_not_from_the_two_teams(panel):
    """R-590. The spread a side is drawn against is the WEEK's, not the two teams' own numbers.

    🚨 THE MECHANISM CHANGED AND THE GUARANTEE DID NOT — and the mechanism is the correction
    this round owes the prompt. The scatter framed on `axis_min`/`axis_max`; **`distribution.box`
    reads neither**, and says so in its own docstring (*"IT READS NO BIN COLUMNS"*). It frames on
    `whisker_low`/`whisker_high`, which are published at the same week grain, so the guarantee
    holds through a different pair of columns.

    ⚠️ ASSERTED ON THE DRAWN BOUNDARY LABELS, which is what a reader actually sees: `box()`
    prints the two whisker ends, so the week's published pair must appear under the chart.
    """
    entries, _ = panel(_game(), _both())
    gained = _series(_of_metric(entries, "Rushing")[0])["gained"]
    low, high = _METRICS["rushing_yards_for_per_game"][5:7]
    plain = _plain(gained)
    assert f"{low}" in plain and f"{high}" in plain, (
        f"the rushing GAINED series is not drawn on the week's published whiskers "
        f"{low}–{high}: {plain}")


def test_TWO_DIFFERENT_MATCHUPS_IN_A_WEEK_GET_THE_SAME_FRAME(panel):
    """🚨 R-590's WHOLE POINT, AND A SINGLE GAME CANNOT SHOW IT. Two different matchups in one
    week must be drawn on the SAME geometry, or a reader comparing two pages is comparing two
    rulers. ⚠️ Deriving the frame from the two teams on screen would look identical on any one
    game and be wrong across the week.

    ✅ THE BOX GEOMETRY IS THE ASSERTION: the `<rect>` and the median `<line>` are placed from
    the week's percentiles and whiskers alone, so two games sharing a week share those pixels
    exactly. The VALUE marker differs, which is correct — that is the only thing about the chart
    that belongs to the team.
    """
    first = panel(_game(), _both())[0]
    second = panel(_game(game_id=902), _both(
        total_yards_for_per_game=501.0, rushing_yards_for_per_game=201.0))[0]

    def geometry(entries):
        svg = _svg_of(_series(_of_metric(entries, "Rushing")[0])["gained"])
        return re.findall(r"<rect[^>]*>", svg) + re.findall(
            r"<line[^>]*stroke-width='1.8'[^>]*>", svg)

    assert geometry(first), "the rushing chart drew no box at all"
    assert geometry(first) == geometry(second), (
        "two matchups in one week were drawn on different frames, so the week is not shared")


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
    # 🚨 R-808's ENTRY, AND IT IS THE SAME KIND AS R-804's: a SCREEN-PIXEL SPLIT. There are two
    # bands on a measure row — one per side — so each gets half the cell's inner width less the
    # gap between them. The warehouse cannot do this: `_METRIC_CELL_GAP` and `_REM` are layout
    # constants in this file, serving has never heard of either, there is no column it could
    # disagree with and no export reads it. ⚠️ The quantity has exactly ONE consumer by
    # construction, which is the test §4.2.1 actually sets.
    # 🚨 R-885's TWO ENTRIES, AND THEY ARE THE SAME KIND AS THE TWO ABOVE: SCREEN-PIXEL SPLITS.
    # Marc's v11 asks for *"Measure Cells and graph cells … equal horizontal widths"*, so the
    # row's cell budget is divided three ways; and the cell CSS wants rem where the budget is
    # kept in px, so the px is divided by `_REM`. **The warehouse cannot do either.**
    # `_TABLE_ROW_BUDGET`, `_TABLE_LABEL_WIDTH`, `_TABLE_GAP` and `_REM` are layout constants
    # in this file, serving has never heard of any of them, there is no column these could
    # disagree with and no export reads them. ⚠️ Each quantity has exactly ONE consumer by
    # construction — a CSS width — which is the test §4.2.1 actually sets, rather than "is the
    # result a pixel" (R-741, and the formulation B099 was told not to license).
    # 🚨 R-899's ENTRY, AND IT IS THE SAME KIND AS THE FOUR ABOVE: A SCREEN-PIXEL COORDINATE.
    # Finishing the required sentence: **this page divides here, and the warehouse cannot do it,
    # because the quantity is an x OFFSET INSIDE ONE `<svg>`-sized row.** `_STRIP_PAD` and the
    # row width are layout constants in this file; serving has never heard of either, there is no
    # column this could disagree with and no export reads it. ⚠️ It is the same transform
    # `site/lib/distribution.py`'s own `_box_scale` carries the identical note for — which is the
    # point, because the strip must land on the axis `box()` drew.
    allowed = {"_ANNOTATION_BLOCK = _CHART_SIDE // 2 - 10",
               "return _STRIP_PAD + (float(value) - lo) / span * (width - 2 * _STRIP_PAD)",
               "return (inner - _METRIC_CELL_GAP * _REM) / 2",
               "_TABLE_VALUE_PX = ((_TABLE_CELL_BUDGET // 3) if _TABLE_CELLS_EQUAL",
               "_TABLE_VALUE_WIDTH = _TABLE_VALUE_PX / _REM    # rem, for the cell CSS"}
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
    # ⚠️ THE NAMES ARE THIS ROUND'S, NOT THE OLD ONES. `_scatter` and `_yardage_column` were
    # replaced by `_gained_allowed` and `_yardage_row`; a liveness check pinned to a deleted
    # function fails for the one reason it must not — it says the walk has gone blind when the
    # walk is fine. **Pin it to functions that exist, and move it when they move.**
    for name in ("_usage_dots", "_gained_allowed", "_yardage_row", "_box_row"):
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


def test_each_columns_blocks_belong_to_that_columns_team(panel):
    """The left half is the away team's offence; the right half is the home team's.

    ⚠️ SIX BLOCKS — three metrics, two sides — and the first three are the away side's, because
    `_yardage` emits away then home inside every section.
    """
    entries, _ = panel(_game(), _both())
    blocks = _blocks(entries)
    assert len(blocks) == 6, f"expected six Gained/Allowed blocks, got {len(blocks)}"
    away_total = _series(_of_metric(entries, "Total")[0])
    assert "Kentucky Gained" in _plain(away_total["gained"])
    assert "Auburn Allowed" in _plain(away_total["allowed"])
    home_total = _series(_of_metric(entries, "Total")[1])
    assert "Auburn Gained" in _plain(home_total["gained"])
    assert "Kentucky Allowed" in _plain(home_total["allowed"])


def test_the_SERIES_are_labelled_with_the_TEAM_NAME_and_GAINED_or_ALLOWED(panel):
    """Marc, v14: *"label each series accordingly with team name and gained or allowed"*.

    🚨 BOTH HALVES, AND THE TEAM NAME IS THE HALF A PRESENCE TEST WOULD MISS. "Gained" and
    "Allowed" appear on every block by construction — they are the two series' keys. **The
    claim that can actually fail is WHOSE figure each row carries**: the top row is this side's
    offence and the bottom row is the OPPONENT's defence, so a block that labelled both rows
    with the same team would be the 1c defect wearing correct words.

    ⚠️ AND IT IS READ OFF THE LABEL, NOT OFF `box()`'s `label=` ARGUMENT. That one goes into the
    SVG's `aria-label` and is never drawn; a test reading it would pass on a panel that showed
    the reader nothing.
    """
    entries, _ = panel(_game(), _both())
    away = _of_metric(entries, "Total")[0]
    rows = _series(away)
    assert set(rows) == {"gained", "allowed"}, f"expected two series, got {sorted(rows)}"
    gained, allowed = _plain(rows["gained"]), _plain(rows["allowed"])
    assert gained.startswith("Kentucky Gained"), f"the top series is not Kentucky's: {gained}"
    assert allowed.startswith("Auburn Allowed"), (
        f"the bottom series is not AUBURN's defence — a side compared with itself: {allowed}")


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


def test_the_FRAME_CAPTION_describes_the_CHART_THAT_IS_DRAWN(panel):
    """🚨 THE R-875 CLASS, CAUGHT IN THIS ROUND'S OWN CAPTION.

    The old sentence read *"the shaded box is the middle half … the dashed lines are the medians
    … the box's thin sides are the 25th percentile and its thick sides the 75th"* — **a true,
    careful description of the SCATTER's band, its two dashed median rules and its weighted
    edges, none of which exist on a box-and-whisker.** A caption that survives the chart it
    describes is a justification that stays in the file after it stops being true, one layer out
    from the code.

    ⚠️ AND THE NEW ONE MUST ADMIT THE THING THE CHART CANNOT DO. The two rows are framed
    independently, so the caption says to read each against its own labels rather than by eye.
    """
    text = _text(panel(_game(), _both())[0])
    assert "136 FBS teams" in text, text[:300]
    assert "whiskers" in text, f"the caption does not describe a box-and-whisker: {text[:400]}"
    for gone in ("dashed", "thin sides", "thick sides", "same axes"):
        assert gone not in text, (
            f"the caption still describes the scatter it replaced — {gone!r}: {text[:400]}")


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


def test_the_VALUE_MARK_is_the_TEAMS_OWN_FIGURE_not_zero(panel):
    """Marc: *"Color and label the Metric value."* The marker is the side's own per-game number.

    🚨 READ OFF THE COLOURED LABEL, WHICH IS THE ONE THING ONLY THE VALUE CARRIES. `box()` prints
    the boundary and percentile labels with `fill='currentColor'` and the value's with the
    accent, so a test counting every `<text>` would pass on a chart that dropped the value and
    kept its ticks.
    """
    entries, _ = panel(_game(), _both())
    gained = _series(_of_metric(entries, "Rushing")[0])["gained"]
    assert _value_marks(gained) == ["154.4"], (
        f"the rushing gained marker is not Kentucky's own 154.4: {_value_marks(gained)}")
    allowed = _series(_of_metric(entries, "Rushing")[0])["allowed"]
    assert _value_marks(allowed) == ["84.5"], (
        f"the rushing allowed marker is not Auburn's own 84.5: {_value_marks(allowed)}")


def test_every_one_of_the_SIX_BLOCKS_draws_BOTH_of_its_values(panel):
    """Twelve markers — six blocks, two series each — and none of them missing."""
    entries, _ = panel(_game(), _both())
    blocks = _blocks(entries)
    assert len(blocks) == 6, f"expected six blocks, got {len(blocks)}"
    for metric, markup in blocks:
        rows = _series(markup)
        for side in ("gained", "allowed"):
            marks = _value_marks(rows[side])
            assert len(marks) == 1, (
                f"the {metric} {side} series drew {len(marks)} value markers: {marks}")
            assert _svg_of(rows[side]), (
                f"the {metric} {side} series is `box()`'s PLACEHOLDER rather than a chart — "
                f"the week row is missing the whisker pair")


def test_a_GENUINE_zero_still_draws_because_it_is_a_datum(panel):
    """AC-G.32. A team held to zero is a measurement, not an absence, and it gets a marker."""
    entries, _ = panel(_game(), _away_over(rushing_yards_for_per_game=0.0))
    gained = _series(_of_metric(entries, "Rushing")[0])["gained"]
    assert _value_marks(gained) == ["0.0"], (
        f"a genuine zero was dropped rather than drawn: {_value_marks(gained)}")


def test_a_NULL_per_game_figure_draws_NO_MARKER_and_still_draws_the_SPREAD(panel):
    """🚨 THE CLAIM CHANGED SHAPE WITH THE CHART AND IS STRONGER FOR IT.

    The scatter needed BOTH figures to plot one point, so a null dropped the whole chart. **A box
    plot is the week's spread with the team's mark on it** — the spread is still true when the
    team has no figure — so a null now drops the MARKER and keeps the distribution.

    ✅ THAT IS BETTER, NOT MERELY DIFFERENT: R-141. A chart that disappears takes its height with
    it and shifts everything below; a chart that keeps its frame and loses one mark holds the
    row. ⚠️ AND A NULL MUST STILL NEVER BE DRAWN AS A ZERO, which is what this asserts.
    """
    entries, _ = panel(_game(), _away_over(rushing_yards_for_per_game=None))
    gained = _series(_of_metric(entries, "Rushing")[0])["gained"]
    assert _value_marks(gained) == [], (
        f"a null figure drew a marker: {_value_marks(gained)}")
    assert "0.0" not in _plain(gained).split("Gained")[-1][:20], \
        "a null per-game figure was drawn as a zero"
    assert _svg_of(gained), "the week's spread was dropped along with the missing marker"


def _frame_of(chart, channel):
    """The (min, max) the chart's own spec says that channel is drawn on."""
    spec = chart.to_dict()
    for layer in spec.get("layer", [spec]):
        domain = layer.get("encoding", {}).get(channel, {}).get("scale", {}).get("domain")
        if domain:
            return float(domain[0]), float(domain[1])
    raise AssertionError(f"the chart declares no {channel} domain")


def test_a_FIGURE_BEYOND_THE_WHISKERS_IS_STILL_DRAWN_where_it_is(panel):
    """🚨 THIS REPLACES THREE TESTS AND ONE WHOLE GUARD, AND THE DEFECT THEY GUARDED CANNOT RECUR.

    The scatter could not plot a point outside `axis_min`/`axis_max`, so R-601 built
    `_off_the_frame` to DROP such a chart, `_off_the_frame_metrics` to name what was dropped and
    `_off_the_frame_figures` to print the figures the picture lost. Three tests asserted that
    machinery and a fourth asserted it did not over-fire.

    ✅ `box()` FRAMES ON THE WHISKERS **WIDENED BY THE VALUE** — its own comment: *"a figure
    outside the whiskers is drawn where it is rather than clamped to the edge. An outlier pinned
    to the boundary reads as 'at the extreme' when the truth is 'beyond it', and the outlier is
    the interesting case."* **So there is no longer any figure this panel cannot draw**, the
    dropped-chart state is unreachable, and the copy explaining it is gone with it.

    ⚠️ ASSERTED, NOT ASSUMED: 900.0 is far beyond the week's 269.1 upper whisker, and it must
    still get a marker and a label.
    """
    entries, _ = panel(_game(), _away_over(rushing_yards_for_per_game=900.0))
    gained = _series(_of_metric(entries, "Rushing")[0])["gained"]
    assert _value_marks(gained) == ["900.0"], (
        f"a figure beyond the whiskers was dropped rather than drawn: {_value_marks(gained)}")
    text = _text(entries)
    assert "not plotted" not in text, (
        "the panel still claims it dropped a chart — that state cannot occur on a box plot")


def test_a_WEEK_WITH_NO_DISTRIBUTION_says_so_and_prints_the_figures(panel):
    """AC-G.11, and it is the ONE absence that survives the chart change.

    ⚠️ `box(None, …)` RETURNS A TITLED EM DASH, which holds the row's height (R-141) and says
    nothing a sighted reader can read. So the panel names the metrics in words and carries their
    two figures, exactly as the dropped-chart caption used to.
    """
    thin = [r for r in _distribution() if not r["metric"].startswith("rushing")]
    entries, _ = panel(_game(), _both(), distribution=thin)
    text = _text(entries)
    assert "Rushing" in text and "not drawn against the week" in text, text[:400]
    assert "154.4" in text and "84.5" in text, (
        f"the figures the chart could not draw are not printed: {text[:400]}")


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


def test_TWO_DIFFERENT_VALUES_RENDER_AT_DIFFERENT_POSITIONS(panel):
    """🚨 R-603's CLASS, CARRIED ACROSS. Four rounds of assertions passed while the scatter's y
    scale was collapsed by Streamlit's `autosize`, because every one of them read the numbers
    going IN rather than the geometry coming OUT. **The only assertion that could have caught it
    is that two different values land in two different places.**

    ⚠️ IT IS CHEAP AND IT IS THE WHOLE LESSON: the coordinate, not the datum.
    """
    def x_of(value):
        entries = panel(_game(), _away_over(rushing_yards_for_per_game=value))[0]
        svg = _svg_of(_series(_of_metric(entries, "Rushing")[0])["gained"])
        found = re.search(r"<polygon points='([\d.]+),", svg) or \
            re.search(r"<line x1='([\d.]+)'[^>]*stroke-width='2.2'", svg)
        assert found, f"no value marker in the svg: {svg[:300]}"
        return float(found.group(1))

    low, high = x_of(100.0), x_of(250.0)
    assert high > low + 5, (
        f"100 and 250 yards render {high - low:.1f}px apart — the scale is collapsed, which is "
        f"the defect four rounds of spec assertions could not see")


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


def test_the_caption_SAYS_which_side_is_which(panel):
    """The two halves are one team's offence each, and the heading says whose."""
    entries, _ = panel(_game(), _both())
    body = _text(entries)
    assert "Kentucky offense against Auburn's defense" in body, body[:400]
    assert "Auburn offense against Kentucky's defense" in body, body[:400]


def test_the_leaders_come_from_the_THROUGH_PRIOR_WEEK_view(panel):
    """🚨 TWO VIEWS, TWO WINDOWS, AND NOTHING BUT THIS STANDS BETWEEN THEM.

    `srv_game_team_leader` answered who led IN this game, from its own box score.
    `srv_game_team_leader_through_prior_week` answers who leads GOING IN. On a preview the
    first did not exist yet, and on a completed game the two were different facts about
    different windows — so reading the short name here would put post-game numbers on a
    pre-game card and look entirely reasonable doing it.

    ⚠️ A102 SPENT A WHOLE ROUND on two near-identically-named COLUMNS that disagreed on 83% of
    games. These were two VIEWS whose names differ by a suffix.

    🚨 PAST TENSE SINCE A132 (R-841): `srv_game_team_leader` NO LONGER EXISTS. B110 removed the
    page section that read it and A132 contracted the serving object; only the mart remains.

    ✅ THE GUARD IS KEPT ANYWAY, AND THIS IS THE ARGUMENT (R-873, A133's call). What it defends
    has changed rather than gone: it used to stop this panel reading the WRONG LIVE VIEW and
    quietly showing post-game numbers on a pre-game card. Today reading that name would raise
    `UndefinedTable` instead — a loud failure rather than a plausible-looking wrong one — so
    the guard is less critical than it was and still correct.

    ⚠️ IT IS KEPT BECAUSE THE NAME CAN COME BACK. `fct_player_game_stat` still carries every
    row, so republishing that view is one model file and one list entry, and `srv_game_team_leader`
    is the obvious name for it. The day it returns this assertion resumes its original job with
    nobody having to remember to write it again. A regex costs microseconds; re-deriving
    B077's finding costs a round.
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

    ⚠️ THE "T-2nd" HALF OF THIS TEST WENT WITH R-753 AND THE TIE CAME BACK IN B110 — as
    `tied 2`, which says the place is SHARED without reintroducing the ordinal Marc removed.
    The rows are still all drawn, which is what matters here because dropping one would invent
    a winner. See `test_the_RANK_IS_STILL_GONE_but_a_TIE_IS_NOW_CARRIED`.
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
    """The same claim as the legend test above, made for all three metrics at once."""
    entries, _ = panel(_game(), _both(), deltas=_deltas(
        rushing_yards_for_minus_opponent_allowed_per_game=1.0,
        passing_yards_for_minus_opponent_allowed_per_game=2.0,
        total_yards_for_minus_opponent_allowed_per_game=3.0))
    seen = {metric: _legend(markup) for metric, markup in _blocks(entries)}
    for metric, stored in (("total", "3.0"), ("rushing", "1.0"), ("passing", "2.0")):
        assert stored in seen[metric], f"{metric} does not print the stored delta: {seen[metric]}"


def test_a_NEGATIVE_delta_carries_its_sign_without_relying_on_colour(panel):
    """AC-G.22: the sign is the signal, and it survives greyscale."""
    entries, _ = panel(_game(), _both(),
                       deltas=_deltas(rushing_yards_for_minus_opponent_allowed_per_game=-24.5))
    assert "-24.5" in _legend(_of_metric(entries, "Rushing")[0]).replace("\u2212", "-")


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
    """Per side, the order of its slots down the panel — `["cards", "chart"] * 3` or the mirror.

    🚨 cfdb-wta-R-900 TURNED THE PANEL INSIDE OUT AND THIS HELPER WITH IT. The old emission was
    two direction blocks, each containing its own three metrics, so the two "offense against"
    headings were the SECTION BOUNDARIES. **Now the metric loop is outermost**: both headings are
    emitted first, then one spanning section heading per metric with a fresh column pair beneath
    it. So the boundaries are the SECTION HEADINGS and each section holds four slots — away's
    two, then home's two, because `st.columns` is consumed left to right.

    ⚠️ AND THE CHART IS MARKDOWN NOW, so the two slots are told apart by their `data-cfdb`
    attribute rather than by the entry KIND. That is the stronger anchor anyway (R-886).
    """
    names = {label for label, *_rest in _module_constant("_YARDAGE_DIMENSIONS")}
    starts = [i for i, (kind, body) in enumerate(entries)
              if kind == "markdown" and _plain(str(body)) in names
              and "gained-allowed" not in str(body)]
    assert len(starts) == len(names), (
        f"expected one spanning section heading per metric, got {len(starts)}")
    away, home = [], []
    for lo, hi in zip(starts, starts[1:] + [len(entries)]):
        section = []
        for kind, body in entries[lo + 1:hi]:
            if kind != "markdown":
                continue
            text = str(body)
            if "data-cfdb='gained-allowed'" in text:
                section.append("chart")
            elif _CARD_GRID in text or "No yards recorded" in text:
                section.append("cards")
        assert len(section) == 4, (
            f"expected four slots in a section — two per side — got {section}")
        away.extend(section[:2])
        home.extend(section[2:])
    return [away, home]


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
    # ⚠️ THE NAME IS TWO LINES AGAIN SINCE R-835, so the two parts are asserted separately —
    # `_plain` puts a space between elements, so `Lloyd Avant` is what the stripped text holds.
    for field in ("# 9", "Lloyd", "Avant", "RB", "JR"):
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
    # 🚨 THE JERSEY SLOT, NOT THE WHOLE CARD — cfdb-wta-R-901 MADE THE OLD FORM A FALSE POSITIVE.
    # `"#0" not in card` was true while the card held no hex colours. The team-colour border
    # ships `light-dark(#0C2340, #0C2340)`, **and `#0C2340` contains `#0`** — so the assertion
    # fired on a card that was rendering the em dash correctly. ⚠️ A substring test over a whole
    # block is a test whose meaning depends on what else is in the block.
    jersey = re.search(r"font-size:1\.15rem[^>]*>([^<]*)<", card)
    assert jersey, f"the jersey slot is not where this test expects it: {card[:200]}"
    assert jersey.group(1).strip() == "\u2014", (
        f"a missing jersey rendered {jersey.group(1)!r} rather than an em dash")
    assert "#nan" not in card.lower()


def test_the_RANK_IS_STILL_GONE_but_a_TIE_IS_NOW_CARRIED(panel):
    """🚨 R-753 REMOVED THE RANK; R-856 PUT THE TIE BACK WITHOUT PUTTING THE RANK BACK.

    ⚠️ THIS TEST USED TO ASSERT THE OPPOSITE, AND IT ASKED TO BE CHANGED IN THESE WORDS: *"if
    that is deliberate, this test is the one to update, and say what carries it."* B110 is that
    round. **The two rulings are compatible and neither was overturned:**

      Marc, R-753:  *"Don't include the rank."*  → NO ORDINAL. Still asserted below.
      Cowork, B110: a card that draws a shared place as an order is claiming a competition
                    that did not resolve.                   → the tie is SAID, without a place.

    ✅ SO THE MARKER IS `tied 2` AND DELIBERATELY NOT `T-2nd`. The cards are drawn in rank order
    and the ORDER carries the rank; what was missing was the statement that a place is not sole.

    📊 IT IS NOT DEFENCE-ONLY. Measured on `srv_game_team_leader_in_this_game`, rows with
    `tied_players > 1`: passing rank 3 **9.8%**, rushing rank 3 **7.7%**, defensive rank 3
    **11.9%**, `total` **0.1%**. This panel is the PREVIEW card, and it shares `_leader_card`
    with the post-game one — so the marker had to be right for both or wrong for both.

    ⚠️ AND IT MUST NOT CHANGE THE CARD'S HEIGHT. `_RESERVED_CARD_HEIGHT` is pinned to a real
    card's 84px (B109 measured what a 33px register error costs), so a marker on its own line
    would grow only the TIED cards and put two cards in one column out of step. Inline in the
    position line, at `.6rem` inside a `.78rem` line, it cannot raise the line box.
    """
    rows = [dict(r, tied_players=2) if r["leader_rank"] == 2 else r for r in _leaders()]
    tied_text = _text(panel(_game(), _both(), deltas=_deltas(), leaders=rows)[0])
    plain_text = _text(panel(_game(), _both(), deltas=_deltas(), leaders=_leaders())[0])
    # 🚨 R-753 IS UNTOUCHED AND THIS HALF IS UNCHANGED FROM THE ORIGINAL TEST.
    for marker in ("T-1st", "T-2nd", "1st", "2nd", "3rd"):
        assert marker not in tied_text, f"the card still carries a rank marker: {marker!r}"
    # 🚨 THE POSITIVE HALF. A bare `tied_text != plain_text` would pass on ANY difference, so
    # the marker's own text is what is asserted, and the COUNT with it — `tied_players=2` was
    # set on the rank-2 row of every panel in the fixture, so one card per panel must carry it.
    assert "tied 2" in tied_text, (
        f"a tied card does not say so — a shared place is being drawn as an order: "
        f"{tied_text[:300]}")
    assert "tied" not in plain_text, (
        "an UNTIED card carries the marker, so it says nothing about being tied")
    # ⚠️ AND THE MARKER IS DRIVEN BY THE COLUMN, NOT BY THE RANK: `tied_players=1` is the
    # untied value and must draw nothing even on a card that is not first.
    ones = [dict(r, tied_players=1) for r in _leaders()]
    assert "tied" not in _text(panel(_game(), _both(), deltas=_deltas(), leaders=ones)[0]), \
        "`tied_players = 1` drew a tie marker — 1 is the value for a place held alone"


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
    # 🚨 SPLIT ON THE MARKER, NOT ON THE BORDER — cfdb-wta-R-901, AND R-886 CALLED THIS SHOT.
    # Three helpers read `block.split("border:1px solid rgba(128,128,128,.22)")` until the
    # before-the-game cards got their team colour. `_leader_card`'s own comment already said why
    # that fails: *"`data-cfdb='leader-card'` IS AN INTERFACE AND THE BORDER IS NOT. The tests
    # anchored on the literal grey border string until R-886 put the TEAM COLOUR there, at which
    # point every card-finding helper silently matched nothing."*
    # ⚠️ AND IT DID NOT FAIL LOUDLY. The split returned ONE piece — the whole three-card block —
    # so the helper handed back **nine dots for a three-game season**, and the assertion that
    # caught it reads *"the two rows are different lengths"*, which is not what was wrong.
    # 🚨 R-886 FIXED THE POST-GAME HELPERS AND THESE THREE WERE NOT ON THAT PANEL, so they kept
    # a dead anchor for two rounds and nothing could see it until a colour arrived here too.
    card = next(piece for piece in block.split("data-cfdb='leader-card'")
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
    # 🚨 SPLIT ON THE MARKER, NOT ON THE BORDER — cfdb-wta-R-901, AND R-886 CALLED THIS SHOT.
    # Three helpers read `block.split("border:1px solid rgba(128,128,128,.22)")` until the
    # before-the-game cards got their team colour. `_leader_card`'s own comment already said why
    # that fails: *"`data-cfdb='leader-card'` IS AN INTERFACE AND THE BORDER IS NOT. The tests
    # anchored on the literal grey border string until R-886 put the TEAM COLOUR there, at which
    # point every card-finding helper silently matched nothing."*
    # ⚠️ AND IT DID NOT FAIL LOUDLY. The split returned ONE piece — the whole three-card block —
    # so the helper handed back **nine dots for a three-game season**, and the assertion that
    # caught it reads *"the two rows are different lengths"*, which is not what was wrong.
    # 🚨 R-886 FIXED THE POST-GAME HELPERS AND THESE THREE WERE NOT ON THAT PANEL, so they kept
    # a dead anchor for two rounds and nothing could see it until a colour arrived here too.
    card = next(piece for piece in block.split("data-cfdb='leader-card'")
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


def test_the_DISTRIBUTION_QUERY_SELECTS_EVERY_COLUMN_the_chart_reads(panel):
    """🚨 R-744, FOUND BY STAGING THE BREAK AND LOOKING. THIS TEST EXISTS BECAUSE ONE CAME BACK
    GREEN.

    The break: delete `whisker_low, whisker_high` from `_DISTRIBUTION_COLUMNS`. Live, that turns
    **every chart on the panel into `box()`'s em-dash placeholder** — `_whisker_pair` finds
    neither key, returns `(None, None)`, and `box()` returns its placeholder span *without
    raising*. ⚠️ **All 95 tests stayed green.**

    🚨 WHY, AND IT IS THE FIXTURE RATHER THAN THE ASSERTIONS: the panel stub answers the
    distribution query with `pd.DataFrame(_distribution())` **whatever the SQL says**. So no
    behavioural test in this file can see the SELECT list at all — the rows arrive complete no
    matter what was asked for. Every assertion about what the chart draws is true of a page whose
    query is broken.

    ✅ SO THE SQL IS THE SUBJECT HERE, and the required columns are taken from `box()`'s OWN
    vocabulary rather than retyped — `distribution._WHISKER_NAMES` is where the two spellings
    live, so a module that renames one cannot leave this guard agreeing with a stale literal.
    """
    from lib import distribution as dist
    _entries, seen = panel(_game(), _both())
    sql = seen["axis_sql"].lower()
    spellings = [pair for pair in dist._WHISKER_NAMES]
    assert any(lo in sql and hi in sql for lo, hi in spellings), (
        f"the distribution query selects no whisker pair, so `box()` frames on nothing and "
        f"every chart draws an em dash: {sql}")
    for needed in ("p25", "p50", "p75"):
        assert needed in sql, f"the query does not select {needed}, which `box()` requires"


def test_GAINED_IS_ON_TOP_and_ALLOWED_BENEATH_IT(panel):
    """🚨 R-744 AGAIN, AND THE SECOND GREEN BREAK. Marc, v14: *"Gained on top, Allowed on
    Bottom."*

    The break: swap the two `_box_row` calls. **95 tests stayed green**, because every helper in
    this file finds a series by its `data-series` ATTRIBUTE — which is the right anchor for
    *which* series it is (R-886) and says nothing at all about WHERE it is. ⚠️ **An attribute
    lookup is order-blind by design, so a suite built entirely on attribute lookups cannot see a
    layout instruction.**

    ✅ POSITIONAL, LIKE R-522's away-before-home: the gained series must be EMITTED FIRST, which
    in a block of markup is what "on top" means. B082 and B083 both proved a presence assertion
    passes a swap; this is the same lesson on a third panel.
    """
    entries, _ = panel(_game(), _both())
    for metric, markup in _blocks(entries):
        assert markup.index("data-series='gained'") < markup.index("data-series='allowed'"), (
            f"the {metric} block draws Allowed above Gained — Marc's v14 puts gained on top")


# --- R-899: the calendar strip ---------------------------------------------------------------

def _strips(entries) -> list:
    """`(metric, markup)` for each calendar strip, in the order the panel drew them."""
    out = []
    for metric, block in _blocks(entries):
        chunks = block.split("<div data-cfdb='calendar-strip'")
        if len(chunks) > 1:
            out.append((metric, chunks[1]))
    return out


def _strip_rows(strip: str) -> list:
    """`(state, plain text)` per row, in drawn order."""
    rows = []
    for chunk in strip.split("<div data-cfdb='strip-row'")[1:]:
        state = re.search(r"data-state='([^']*)'", chunk)
        body = chunk.split("</div></div>")[0]
        rows.append((state.group(1) if state else None, _plain(body.split(">", 1)[1])))
    return rows


def test_the_STRIP_draws_ONE_ROW_PER_GAME_on_a_calendar_that_is_NOT_TWELVE(panel):
    """🚨 R-899. Marc: *"reserve/print rows for each regular season game on the calendar."*

    📊 PROVED ON A CALENDAR THAT IS NOT 12, WHICH IS THE CASE A 12-ROW ASSUMPTION SURVIVES. The
    fixture is **Boise State's real 2026 regular season — 11 games**, read back from serving. Of
    716 teams on that calendar, **231 have 12 games and 485 (67.7%) do not**; inside FBS it is
    129 at 12, 8 at 11 and San José State at 13.

    ⚠️ AND *"RESERVED"* IS THE HALF A ROW COUNT ALONE WOULD MISS: nine of those eleven have not
    been played, so a strip that drew only games with figures would show TWO rows and look
    entirely reasonable doing it.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    strips = _strips(entries)
    assert len(strips) == 6, f"expected one strip per metric per side, got {len(strips)}"
    for metric, strip in strips:
        rows = _strip_rows(strip)
        assert len(rows) == 11, (
            f"the {metric} strip drew {len(rows)} rows for an 11-game calendar — a reserved row "
            f"per scheduled game is the instruction, not a row per game with a figure")
        assert "data-games='11'" in strip, "the strip does not declare its own row count"


def test_the_STRIP_is_ordered_by_KICKOFF_DESCENDING_and_does_not_re_sort(panel):
    """Marc: *"order by kick-off date, desc."*

    🚨 THE ORDER IS THE QUERY's AND THE TEST READS WHAT WAS DRAWN. R-768's class is a test that
    sorts its own frame and then asserts pandas sorts; this hands the panel rows in the order
    serving returns them and reads the abbreviations back off the page.

    ⚠️ AND IT IS ASSERTED AS A LIST, NOT AS *first* AND *last*. Two rows out of order in the
    middle is exactly what a first/last check cannot see.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    _metric, strip = _strips(entries)[0]
    drawn = [_plain(text).replace("vs ", "").replace("@ ", "").split()[0]
             for _state, text in _strip_rows(strip)]
    # Boise State's real 2026 calendar, kickoff descending — week 7 is a bye and is simply absent,
    # which is the shape of a calendar the page must not "fill in".
    assert drawn == ["SDSU", "ORST", "CSU", "TXST", "WSU", "FRES", "USU", "WMU",
                     "SDAK", "MEM", "ORE"], \
        f"the strip is not in kickoff-descending order: {drawn}"


def test_the_THREE_ABSENCE_STATES_read_DIFFERENTLY(panel):
    """🚨 AC-G.11 and cfdb-main-R-911. Three states, three sentences, and none of them a zero.

    📊 MEASURED ON 2026 REGULAR SERVING THIS ROUND: `scheduled` 5,848 · `no_box_score` 842 ·
    `played` 668 — **and `total_yards` is NULL on every one of the first two and present on every
    one of the third.** So the two absences are indistinguishable from the figure alone and the
    page must read `game_figures_state`.

    ⚠️ THE ASSERTION IS THAT THEY DIFFER, NOT MERELY THAT EACH EXISTS. A page that printed the
    same words for both absences would pass a presence check per state and still tell a reader
    that a game in November and a D-III fixture in September are the same kind of nothing.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    _metric, strip = _strips(entries)[0]
    words = {}
    for state, text in _strip_rows(strip):
        words.setdefault(state, set()).add(text)
    assert set(words) == {"scheduled", "no_box_score", "played"}, (
        f"the strip does not carry all three states: {sorted(words)}")
    scheduled = " ".join(words["scheduled"])
    no_box = " ".join(words["no_box_score"])
    assert "not yet" in scheduled, f"a future game does not read as not yet: {scheduled}"
    assert no_box != scheduled, "the two absences are told in the same words"
    assert "no box score" in no_box, f"the no_box_score row does not say so: {no_box}"


def test_the_NO_BOX_SCORE_sentence_is_TRUE_of_a_DIVISION_III_fixture(panel):
    """🚨 cfdb-main-R-911, AND THE SENTENCE R-730 ALREADY PUT ON THE LIVE PAGE ONCE.

    ❌ *"Collected from 2024 onward"* IS FLATLY FALSE ON A 2025 DIVISION III GAME. A135 measured
    the seasons; **this round measured whose games they are**, which is the half that makes a
    true sentence writable:

        of the 842 `no_box_score` team-games in 2026 regular
          Division III 425 · Division II 368 · FCS 5 · **FBS 0**

    ✅ SO THE SENTENCE MUST NAME THE LEVEL OF OPPONENT, NEVER A YEAR. Checked against the real
    D-III fixtures this round queried: team 354 vs MILK and team 2781 vs BSU, week 1, 2026-09-03.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    _metric, strip = _strips(entries)[0]
    rows = [text for state, text in _strip_rows(strip) if state == "no_box_score"]
    assert rows, "the fixture carries no no_box_score row, so this test has no subject"
    assert "no box score" in " ".join(rows), (
        f"the row does not say which absence it is (AC-G.11): {rows}")

    # 🚨 THE SENTENCE LIVES IN THE STRIP's ABSENCE NOTE, NOT ON EVERY ROW, and that is where this
    # asserts it. Printing the full explanation on each reserved row meant "not yet played" ten
    # times down a twelve-row strip — the render is what said so — so the row carries a short tag
    # and the strip carries the sentence ONCE, for the states actually present.
    note = _plain(strip.split("data-cfdb='strip-absences'")[1])
    assert "no box score" in note, f"the no_box_score absence is never explained: {note}"
    for forbidden in ("2024", "2025", "onward", "since"):
        assert forbidden not in note.lower(), (
            f"the sentence makes a claim about DATES — {forbidden!r} — and the measurement says "
            f"it is about the opponent's DIVISION: {note}")
    assert "Division" in note, (
        f"the sentence does not name the level of opponent, which is the only thing that makes "
        f"it true of a D-III fixture: {note}")

    # ✅ AND IT IS NOT PRINTED WHERE IT DOES NOT APPLY (R-762). An FBS-vs-FBS calendar has no
    # `no_box_score` row — 0 of 842 in 2026 regular — so the sentence must not appear on one.
    fbs_only = [g for g in _calendar() if g["game_figures_state"] != "no_box_score"]
    entries, _ = panel(_game(), _both(), deltas=_deltas(), calendar=fbs_only)
    _metric, strip = _strips(entries)[0]
    clean = _plain(strip.split("data-cfdb='strip-absences'")[1])
    assert "no box score" not in clean, (
        f"a calendar with no such game still explains the absence: {clean}")


def test_a_FUTURE_GAME_DRAWS_NO_MARK_and_never_a_ZERO(panel):
    """🚨 AC-G.32 ON A YARDS AXIS. A zero is a claim about a game that has not happened.

    ⚠️ AND THE MARK IS WHAT MATTERS, NOT THE TEXT. A scheduled row that printed no number but
    still drew its tick at the axis origin would read as *held to nothing* — the same lie in a
    different element, and invisible to a test that only greps for "0".
    """
    # 🚨 KEYED ON THE FIXTURE, NEVER ON `data-state` — AND STAGING THE BREAK IS WHAT SAID SO.
    #
    # The first version read each row's `data-state` off the markup and asserted accordingly. The
    # break that removes the null guard makes every row take the mark-drawing branch, **which
    # hardcodes `data-state='played'`** — so the break rewrote the very attribute the test used to
    # decide what to expect, and **the test passed while every scheduled game drew a mark.**
    #
    # ⚠️ R-768's CLASS: a test must not key on a value the defect controls. ✅ The truth about
    # which games have figures lives in the CALENDAR FIXTURE, so the rows are paired to it by
    # opponent — the one field the page copies and never computes.
    expected = {g["opponent_abbreviation"]: g["game_figures_state"]
                for g in _calendar() if g["team_id"] == AWAY_ID}
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    _metric, strip = _strips(entries)[0]
    chunks = strip.split("<div data-cfdb='strip-row'")[1:]
    assert len(chunks) == len(expected), (
        f"expected {len(expected)} rows, got {len(chunks)} — this test cannot pair them up")
    for chunk in chunks:
        # ⚠️ THE SPLIT LANDS INSIDE THE OPENING TAG, so the attributes that follow are still
        # markup — dropping to the first `>` is what makes `_plain` return the row a reader sees.
        body = chunk.split(">", 1)[1].split("</div></div>")[0]
        abbr = _plain(body).replace("vs ", "").replace("@ ", "").split()[0]
        state = expected[abbr]
        if state == "played":
            assert "background:" in body, f"a played game drew no mark: {_plain(body)}"
        else:
            assert "background:" not in body, (
                f"a {state} game ({abbr}) drew a MARK on the yards axis — a game with no figure "
                f"placed at a position is a measurement nobody made: {_plain(body)}")
            assert not re.search(r">\s*0\s*<", body), (
                f"a {state} game ({abbr}) rendered a zero: {_plain(body)}")


def test_the_STRIP_and_the_BOX_agree_about_WHERE_A_VALUE_GOES(panel):
    """🚨 THE GUARD THAT MAKES A BORROWED PRIVATE CONSTANT LOUD — R-899, and it is the reason
    this round was allowed to do what B114 refused.

    B114 declined to align two `box()` rows by width-and-offset because it *"needs `box()`'s
    internal `pad`, which is a local variable. Coupling this file to another module's private
    constant is worse than the parameter it is avoiding."* ⚠️ **That judgement stands for that
    problem.** It cannot stand for this one: there is no way to put a NEW element on an existing
    chart's axis without knowing that chart's geometry, and the alternative is a strip whose marks
    do not line up with the distribution they are drawn against — which is the whole element.

    ✅ SO THE COPY IS DECLARED (`_STRIP_PAD`) AND THEN CHECKED AGAINST THE REAL THING. This renders
    an actual `box()` and reads back the x it drew its MEDIAN line at, then asks `_strip_x` where
    it would put the same number. **They must agree to within half a pixel.**

    🚨 THE DAY `site/lib/distribution.py` CHANGES ITS PADDING, THIS FAILS AND NAMES WHY — which is
    exactly what a silent copy of a constant can never do. A139 is in that file right now.

    ⚠️ AND THE MEDIAN IS THE RIGHT PROBE BECAUSE IT IS DRAWN FROM THE ROW RATHER THAN FROM THE
    VALUE: `box()` widens its frame around a value marker, so probing with the value would
    measure a frame this test had to predict. p50 sits inside the whiskers by construction.
    """
    from lib import distribution as dist
    width = _module_constant("_BOX_ROW_WIDTH")
    row = _distribution()[0]
    frame = (float(row["whisker_low"]), float(row["whisker_high"]))
    svg = dist.box(row, value=None, width=width, show_value=False)
    drawn = re.search(r"<line x1='([\d.]+)'[^>]*stroke-width='1.8'", svg)
    assert drawn, f"no median line in box()'s output — this probe has gone blind: {svg[:300]}"

    import importlib
    matchup = importlib.import_module("views.matchup")
    ours = matchup._strip_x(float(row["p50"]), frame, width)
    assert abs(float(drawn.group(1)) - ours) < 0.5, (
        f"the strip would place {row['p50']} at {ours:.1f}px and `box()` drew it at "
        f"{drawn.group(1)}px. The two are on DIFFERENT axes, which is the one thing the calendar "
        f"strip exists not to be. `_STRIP_PAD` no longer matches `distribution.box`'s own `pad`.")


def test_the_STRIPS_PLOT_IS_A_FIXED_WIDTH_and_never_stretches(panel):
    """🚨 THE DEFECT THE 1700px RENDER FOUND AND EVERY OTHER INSTRUMENT MISSED.

    The strip's plot was `flex:1`. At 1300px the chart slot is 246px, so a 40px gutter left
    exactly 206 and it lined up with the box perfectly — **the suite was green and the 1300px
    raster was pixel-exact.** 📊 **At 1700px the slot is 369px: the strip's plot took 329 and the
    box's SVG stayed at its declared 206**, so the strip was drawn on an axis 60% longer than the
    distribution beneath which it sits, with every mark in the wrong place.

    ✅ `box()` SHIPS A FIXED WIDTH, SO ANYTHING SHARING ITS AXIS MUST BE FIXED TOO. A proportional
    element cannot track an absolute one — R-750's finding on a different pair.

    ⚠️ THIS TEST READS THE DECLARED WIDTH, WHICH IS WHAT A UNIT TEST CAN SEE. It cannot measure
    the browser, and it is not a substitute for the two renders — it is the cheap guard that stops
    the same edit coming back. **The expensive instrument found it; this one remembers it.**
    """
    width = _module_constant("_BOX_ROW_WIDTH")
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    _metric, strip = _strips(entries)[0]
    for chunk in strip.split("<div data-cfdb='strip-row'")[1:]:
        opening = chunk.split(">", 1)[1]
        plot = opening.split("</span>")[0]
        assert "flex:1" not in chunk, (
            "a strip row still stretches to fill its slot, so its axis grows with the viewport "
            "while `box()`'s stays fixed")
        assert f"width:{width}px" in chunk, (
            f"a strip row does not pin its plot to `_BOX_ROW_WIDTH` ({width}px), so it cannot "
            f"be on the same axis as the chart above it: {plot[:160]}")


def test_the_STRIP_takes_the_GAINED_rows_frame_and_the_PAGE_SAYS_SO(panel):
    """🚨 cfdb-wta-R-927 REACHES THE STRIP, AND THE PAGE HAS TO STAY HONEST ABOUT IT.

    The two box rows are framed on their own whiskers — measured 13.8% apart on `total` — so a
    strip can share ONE of them. It shares **Gained's**, because this half of the panel is
    *"<Team> offense against <Opponent>'s defense"* and the strip carries that team's own per-game
    yardage. ⚠️ **Which means it is aligned with the top row and NOT with the bottom one.**

    ✅ B114's caption already admitted the two rows are framed independently; this asserts it
    still covers the page now that a third element sits on one of those frames. **The page has
    been honest about this for a round and a new element must not quietly break it.**

    ⚠️ THE PAIRING IS THE CLAIM: the strip reads the gained frame AND the caption says the frames
    are not shared. A round that flips `_BOX_SHARED_AXIS` (B116) should change both together.
    """
    assert _module_constant("_BOX_SHARED_AXIS") is False, (
        "the shared axis is on — the strip now sits on a frame BOTH box rows use, and this test "
        "and the page's caption should both be revisited")

    entries, _ = panel(_game(), _both(), deltas=_deltas())
    assert "framed on their OWN spreads" in _text(entries), (
        "the caption no longer tells the reader the rows are not on one axis")
    # 🚨 BEHAVIOURAL, NOT A SOURCE READ: move the GAINED whisker pair only, and the strip's mark
    # must move with it. A strip computing its own frame would not budge.

    def mark_x(gained_high):
        rows = [dict(r, whisker_high=gained_high)
                if r["metric"] == "total_yards_for_per_game" else r
                for r in _distribution()]
        entries, _ = panel(_game(), _both(), deltas=_deltas(), distribution=rows)
        strip = dict(_strips(entries))["total"]
        played = [c for c in strip.split("<div data-cfdb='strip-row'")[1:]
                  if "background:" in c][0]
        return float(re.search(r"left:([\d.]+)px;top:4px", played).group(1))

    wide, narrow = mark_x(900.0), mark_x(600.0)
    assert wide < narrow - 5, (
        f"widening the GAINED row's frame did not move the strip's mark ({wide:.1f} vs "
        f"{narrow:.1f}) — the strip is on an axis of its own, not on the box row's")


def test_the_CARD_BORDERS_carry_the_TEAM_COLOUR_on_THIS_tab_too(panel):
    """🚨 cfdb-wta-R-901. Marc, v11: *"Player Card borders should be color of team."*

    R-886 did this on the POST-GAME cards; `_leader_block` never passed `accent` through, so the
    before-the-game cards kept the neutral grey. **This is the pass-through, asserted.**

    ⚠️ AND IT IS THE SIDE'S OWN COLOUR, NOT JUST *A* COLOUR. Each half's cards must carry that
    half's team — the away column Kentucky, the home column Auburn — or the border is decoration
    that happens to be coloured. The fixture gives both sides the same hex, so this drives them
    apart first.
    """
    sides = [dict(row, **({"color_on_light": "#AA0000", "color_on_dark": "#AA0000"}
                          if row["team_id"] == AWAY_ID else
                          {"color_on_light": "#0000BB", "color_on_dark": "#0000BB"}))
             for row in _both()]
    entries, _ = panel(_game(), sides, deltas=_deltas())
    away, home = [], []
    names = {label for label, *_rest in _module_constant("_YARDAGE_DIMENSIONS")}
    starts = [i for i, (kind, body) in enumerate(entries)
              if kind == "markdown" and _plain(str(body)) in names
              and "gained-allowed" not in str(body)]
    for lo, hi in zip(starts, starts[1:] + [len(entries)]):
        cards = [str(b) for k, b in entries[lo + 1:hi]
                 if k == "markdown" and "data-cfdb='leader-card'" in str(b)]
        assert len(cards) == 2, f"expected one card block per side in a section, got {len(cards)}"
        away.append(cards[0])
        home.append(cards[1])
    assert all("#AA0000" in block for block in away), \
        "the away cards do not carry the away team's colour"
    assert all("#0000BB" in block for block in home), \
        "the home cards do not carry the home team's colour"
    assert not any("#0000BB" in block for block in away), \
        "an away card is wearing the HOME team's colour"
    # ⚠️ AND IT IS THE COMPOSED PAIR, NOT THE RAW HEX (R-855). `light-dark(...)` is what keeps
    # B109's invisible-black case from coming back; a bare on-light hex would pass a substring
    # test and render `rgb(0,0,0)` on a dark page for the 18.6% of teams that publish it.
    assert "light-dark(" in away[0], "the border is a raw hex rather than `_accent`'s pair"


def test_THE_TWO_SERIES_ARE_FRAMED_INDEPENDENTLY_and_the_page_SAYS_SO(panel):
    """🚨 cfdb-wta-R-900. Marc asked for *"the same x-axis"* and this panel does NOT have one.

    📊 MEASURED ON LIVE SERVING, 2026 regular week 15 — the whisker spans `box()` frames on:

        pair       gained          allowed         union           narrower row uses
        total      204.0–620.5     142.5–508.5     142.5–620.5     87.9% of the width
        rushing     40.5–336.0      10.0–241.0      10.0–336.0     70.8%
        passing     46.0–396.5      47.5–352.0      46.0–396.5     93.7%

    ❌ IT CANNOT BE FIXED FROM THIS FILE. `box()` has no frame parameter, faking the whisker pair
    would print two published figures wrongly, and matching the scales by width-and-offset needs
    `box()`'s internal `pad`. **`site/lib/distribution.py` is session A's (§3 rule 3)** — B074
    did exactly this with `states.degraded()` and was right to.

    ✅ SO THIS TEST HOLDS THE HONEST STATE IN PLACE UNTIL THAT PARAMETER EXISTS: the two rows are
    framed independently AND the caption admits it. ⚠️ **The pairing of those two is the claim.**
    A round that adds the shared axis should flip this test, not delete it.
    """
    assert _module_constant("_BOX_SHARED_AXIS") is False, (
        "the shared axis is declared on — flip this test to assert the two frames now MATCH")
    entries, _ = panel(_game(), _both())
    rows = _series(_of_metric(entries, "Total")[0])
    gained, allowed = _plain(rows["gained"]), _plain(rows["allowed"])
    low_g, high_g = _METRICS["total_yards_for_per_game"][5:7]
    low_a, high_a = _METRICS["total_yards_allowed_per_game"][5:7]
    assert f"{low_g}" in gained and f"{low_a}" in allowed, (gained, allowed)
    assert low_g != low_a, "the fixture cannot show the difference this test is about"
    # 🚨 THE PAGE MUST SAY IT. A chart whose two rows are not comparable, laid out as though
    # they were, is worse than one that admits it — AC-G.11 applied to a scale.
    assert "framed on their OWN spreads" in _text(entries), (
        "the caption does not tell the reader the two rows are not on one axis")


def test_the_CHART_WIDTH_FITS_the_slot_it_is_drawn_in(panel):
    """R-609/R-750's concern, restated for an SVG.

    ⚠️ `box()` EMITS `max-width:100%`, so a chart handed more width than its cell is SCALED
    rather than clipped — which is safer than the Vega square ever was, and is also why the
    width must still be chosen rather than left large: a scaled SVG shrinks its labels with it.

    🚨 THE BOUND IS MEASURED, NOT COMPUTED, AND THE FIRST DRAFT OF THIS TEST GOT IT WRONG. It
    derived the slot from an assumed ~1100px content width and passed on a `_BOX_ROW_WIDTH` of
    296 — **which the live render then measured being scaled to 246.** The content is 1000px at
    1300 with the sidebar open, and the chart slot is **246px**, measured with
    `getBoundingClientRect()` on the real page (`claude_work/renders/B114_v14_1300.png`).

    ⚠️ SO THE NUMBER BELOW IS AN OBSERVATION WITH A DATE ON IT, and it is a CEILING rather than
    an equality: a round that widens the slot may raise it, and a round that widens the BOX past
    it is re-introducing the silent scale. **A derived bound would have gone on agreeing with
    itself, which is what it did.**
    """
    slot = 246  # measured at 1300px, sidebar open, 2026-09-15
    drawn = _module_constant("_BOX_ROW_WIDTH")
    assert drawn <= slot, (
        f"the box is {drawn}px in a ~{slot:.0f}px slot, so `max-width:100%` will scale it down "
        f"and shrink its labels with it")
    entries, _ = panel(_game(), _both())
    svg = _svg_of(_series(_of_metric(entries, "Total")[0])["gained"])
    assert f"width='{drawn}'" in svg, f"the drawn width is not the declared constant: {svg[:200]}"


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


def test_the_LEGEND_is_a_worked_SUBTRACTION_in_three_rows(panel):
    """R-751, kept through the chart change. Marc, v02.2: *"add a line below the Opponent metric
    (like a math problem)"* — gained, allowed, a rule, the difference.

    🚨 AND MARC'S v14 CALLS THIS *"the legend"*. There has never been a legend on this chart in
    the Vega sense — `matchup.py` contains the word nowhere and `_scatter` said why in its own
    comment — so *"Keep the current legend on the graph on top right"* is this block, and this
    test is what holds it there.
    """
    entries, _ = panel(_game(), _both())
    text = _legend(_of_metric(entries, "Rushing")[0])
    assert "Gained" in text and "Allowed" in text, text
    assert "154.4" in text and "84.5" in text, text
    # 🚨 `+38.0`, NOT `69.9`, AND THE DIFFERENCE IS THE WHOLE POINT. 154.4 gained minus 84.5
    # allowed IS 69.9 — and `_deltas()` carries the STORED column, which reads 38.0. **The first
    # draft of this test asserted 69.9 and the fixture caught it**: an assertion that recomputes
    # the figure is an assertion that the page may subtract, which is the one thing §4.2.1
    # forbids here. The stored number is the claim.
    assert "+38.0" in text, f"the stored difference is not on the block: {text}"


def test_the_LEGEND_is_anchored_to_the_TOP_RIGHT(panel):
    """Marc: *"Keep the current legend on the graph on top right."*

    ⚠️ IT IS A `float:right` NOW RATHER THAN A SCREEN COORDINATE INSIDE A VEGA SPEC, so the
    assertion is on the CSS that puts it there. R-804's failure — a fixed 104px block silently
    becoming 58% of a resized plot — cannot recur, because nothing about this block is measured
    in pixels of a plot any more.
    """
    entries, _ = panel(_game(), _both())
    block = _of_metric(entries, "Total")[0]
    piece = block.split("data-cfdb='matchup-legend'")[1].split(">")[0]
    assert "float:right" in piece, f"the legend is not floated right: {piece}"
    assert "text-align:right" in piece, f"the legend's figures are not right-aligned: {piece}"
    # ⚠️ POSITIONAL, NOT PRESENCE: it must be emitted BEFORE the two series, or "top" is a lie.
    assert block.index("matchup-legend") < block.index("box-series"), \
        "the legend is drawn after the series, so it is not at the top"


def test_the_LEGEND_carries_BOTH_LOGOS(panel):
    """One logo per side, so the subtraction says WHO without repeating two long names."""
    entries, _ = panel(_game(), _both())
    block = _of_metric(entries, "Total")[0]
    piece = block.split("data-cfdb='matchup-legend'")[1].split("data-cfdb='box-series'")[0]
    assert piece.count("<img") == 2, f"expected two logos in the legend, got {piece.count('<img')}"


def test_a_NULL_LOGO_PUTS_THE_TEAM_NAME_in_the_legend(panel):
    """🚨 AC-G.11 AT LOGO SIZE, AND THE FALLBACK IMPROVED WITH THE CHART.

    Inside an Altair spec a monogram was impossible, so `_annotation_layers` substituted the
    team's NAME as text — B100's rule, and the best available. ✅ **In HTML the app's own
    `identity.logo_or_monogram` applies**, so a missing logo gets the same monogram every other
    surface draws. **Leaving Vega turned a workaround back into the shared helper.**
    """
    entries, _ = panel(_game(), _both(logo_url=None))
    block = _of_metric(entries, "Total")[0]
    piece = block.split("data-cfdb='matchup-legend'")[1].split("data-cfdb='box-series'")[0]
    assert piece.count("<img") == 1, "the home side's null logo still drew an <img>"
    assert "Auburn" in _plain(piece), (
        f"a missing logo left an EMPTY box rather than the team's name — AC-G.28 keeps the "
        f"footprint and B100's rule wants the name: {_plain(piece)}")


def test_a_PRESENT_logo_does_NOT_repeat_the_team_name_in_the_legend(panel):
    """The fallback is a fallback. With a logo, the block is logo + word + figure and no name —
    the names are already on the two series labels directly beneath."""
    entries, _ = panel(_game(), _both())
    block = _of_metric(entries, "Total")[0]
    piece = _plain(block.split("data-cfdb='matchup-legend'")[1]
                   .split("data-cfdb='box-series'")[0])
    assert "Kentucky" not in piece and "Auburn" not in piece, (
        f"the legend repeats a team name it already shows a logo for: {piece}")


def test_the_LEGEND_reads_A106s_COLUMN_and_subtracts_nothing(panel):
    """🚨 THE BEHAVIOURAL HALF OF §4.2.1, AND THE AST GUARD DOES NOT REPLACE IT.

    A106 published the difference as a column. This makes the published column DISAGREE with its
    own inputs — 154.4 gained, 84.5 allowed, and a stored delta of 1.0 — so a page that
    subtracted would print 69.9 and a page that reads prints 1.0. **No fixture can satisfy both
    readings, which is what makes this fire where a source scan cannot.**
    """
    entries, _ = panel(_game(), _both(),
                       deltas=_deltas(rushing_yards_for_minus_opponent_allowed_per_game=1.0))
    text = _legend(_of_metric(entries, "Rushing")[0])
    assert "1.0" in text, f"the stored delta is not on the block: {text}"
    assert "69.9" not in text, (
        f"the page subtracted its own inputs instead of reading A106's column: {text}")


def test_a_NULL_delta_renders_an_em_dash_and_a_ZERO_renders_a_number(panel):
    """AC-G.32. A null is an absence and a zero is a measurement, and they must not look alike."""
    entries, _ = panel(_game(), _both(),
                       deltas=_deltas(rushing_yards_for_minus_opponent_allowed_per_game=None))
    assert "\u2014" in _legend(_of_metric(entries, "Rushing")[0])
    entries, _ = panel(_game(), _both(),
                       deltas=_deltas(rushing_yards_for_minus_opponent_allowed_per_game=0.0))
    text = _legend(_of_metric(entries, "Rushing")[0])
    assert "0.0" in text and "\u2014" not in text, text


def test_the_delta_no_longer_carries_a_COLOUR_of_its_own(panel):
    """R-736. The number is bold and uncoloured; the verdict beside it is what carries the look.

    ⚠️ TWO COLOUR SIGNALS FOR ONE FACT IS WHAT THIS PREVENTS — a green `+38.0` beside a green
    circle says the same thing twice and disagrees the moment one of them is wrong.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    block = _of_metric(entries, "Rushing")[0]
    piece = block.split("data-cfdb='matchup-legend'")[1].split("data-cfdb='box-series'")[0]
    delta_span = re.search(r"<span style='font-weight:700'>([^<]*)</span>", piece)
    assert delta_span, f"the difference is not a plain bold span: {piece}"
    assert "color" not in delta_span.group(0), "the delta carries its own colour again"


def _mark_of(block):
    """R-722's verdict as it is drawn: `(glyph, colour)` off the legend's own span.

    🚨 THE VERDICT SURVIVED THE CHART AND CHANGED CARRIER. The scatter set shape and colour on
    its single `mark_point`; a box-and-whisker has no single point, so the classification moved
    into the legend beside the subtraction it describes. ⚠️ **Shape is still first and colour
    second (AC-G.22)** — the glyph is a filled circle, a filled diamond or a hollow square, and
    a greyscale reader separates all three by outline.
    """
    found = re.search(r"<span title='([^']*)' style='color:([^;]*);[^']*'>(.)</span>", block)
    assert found, f"no outlook glyph in the block: {block[:200]}"
    return found.group(3), found.group(2), found.group(1)


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
    """R-722. Marc's three verdicts get three DIFFERENT looks, and the shape carries two of them.

    ⚠️ `_OUTLOOK_MARKS` still holds shape, colour and fill; only the CARRIER changed. The
    mapping is asserted through what is drawn, so a glyph table that disagreed with the mark
    table would fail here rather than in a source read.
    """
    seen = {}
    for value in ("favorable", "contested", "challenging"):
        entries, _ = panel(_game(), _both(), deltas=_with_outlook(value))
        seen[value] = _mark_of(_of_metric(entries, "Rushing")[0])
    glyphs = {v: m[0] for v, m in seen.items()}
    colours = {v: m[1] for v, m in seen.items()}
    assert glyphs["favorable"] == glyphs["contested"] == "\u25cf", \
        f"Marc's rule gives favorable and contested a CIRCLE: {glyphs}"
    assert glyphs["challenging"] == "\u25c6", (
        f"`challenging` must be the DIAMOND — it is the one state a greyscale reader can find "
        f"by outline alone: {glyphs}")
    assert len(set(colours.values())) == 3, f"two outlooks share a colour: {colours}"
    assert colours["favorable"] == "#1b6b3a", f"green is not on favorable: {colours}"


def _luminance(hex_colour: str) -> float:
    """Rec. 601 luma, which is what a greyscale render collapses a colour to."""
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


def test_GREEN_and_YELLOW_are_separated_in_GREYSCALE_too(panel):
    """🚨 AC-G.22's HARD CASE, UNCHANGED BY THE CHART. Favorable and contested share a shape, so
    colour is all that separates them — and the two tones are chosen for LUMINANCE distance, not
    hue, so a greyscale reader still sees two different marks.
    """
    tones = {}
    for value in ("favorable", "contested"):
        entries, _ = panel(_game(), _both(), deltas=_with_outlook(value))
        tones[value] = _mark_of(_of_metric(entries, "Rushing")[0])[1]

    def luma(hex_colour):
        r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    gap = abs(luma(tones["favorable"]) - luma(tones["contested"]))
    assert gap > 40, (
        f"green and yellow are {gap:.0f} apart in luminance; in greyscale they are the same "
        f"mark and Marc's rule loses a state: {tones}")


def test_an_UNCLASSIFIED_mark_does_not_BORROW_one_of_the_three_looks(panel):
    """A null outlook is not a fourth verdict and must not wear one of the three."""
    entries, _ = panel(_game(), _both(), deltas=_with_outlook(None))
    glyph, colour, title = _mark_of(_of_metric(entries, "Rushing")[0])
    assert glyph == "\u25a1", f"unclassified borrowed a verdict's shape: {glyph}"
    assert colour not in ("#1b6b3a", "#c8a415"), f"unclassified borrowed a verdict's colour: {colour}"
    assert "not classified" in title, f"the hover does not say it is unclassified: {title}"


def test_an_UNKNOWN_outlook_string_falls_to_the_UNCLASSIFIED_look_not_a_verdict(panel):
    """🚨 THE BRITISH-SPELLING CLASS. A119 shipped `favourable`, CI rejected it and the stored
    value changed; a mapping keyed on a string serving does not store must fall to the
    unclassified look rather than silently picking one.
    """
    entries, _ = panel(_game(), _both(), deltas=_with_outlook("favourable"))
    glyph, _colour, _title = _mark_of(_of_metric(entries, "Rushing")[0])
    assert glyph == "\u25a1", f"an unknown string was given a verdict's shape: {glyph}"


def _header_row(entries, name):
    """One card's header row markup, by the player it names."""
    block = next(str(b) for k, b in entries
                 if k == "markdown" and name in _plain(str(b)))
    # 🚨 SPLIT ON THE MARKER, NOT ON THE BORDER — cfdb-wta-R-901, AND R-886 CALLED THIS SHOT.
    # Three helpers read `block.split("border:1px solid rgba(128,128,128,.22)")` until the
    # before-the-game cards got their team colour. `_leader_card`'s own comment already said why
    # that fails: *"`data-cfdb='leader-card'` IS AN INTERFACE AND THE BORDER IS NOT. The tests
    # anchored on the literal grey border string until R-886 put the TEAM COLOUR there, at which
    # point every card-finding helper silently matched nothing."*
    # ⚠️ AND IT DID NOT FAIL LOUDLY. The split returned ONE piece — the whole three-card block —
    # so the helper handed back **nine dots for a three-game season**, and the assertion that
    # caught it reads *"the two rows are different lengths"*, which is not what was wrong.
    # 🚨 R-886 FIXED THE POST-GAME HELPERS AND THESE THREE WERE NOT ON THAT PANEL, so they kept
    # a dead anchor for two rounds and nothing could see it until a colour arrived here too.
    card = next(piece for piece in block.split("data-cfdb='leader-card'")
                if name in _plain(piece))
    return card.split("repeat(3,1fr)")[0]


def test_the_name_renders_FIRST_over_BOLD_LAST_and_not_merely_that_it_appears(panel):
    """🚨 A PRESENCE ASSERTION CANNOT SEE THIS SWAP. B082 proved it on the game header and B083
    on the win-probability bar; *Avant Lloyd* contains exactly the same characters as
    *Lloyd Avant*.

    Marc, R-835: *"First name should be above the last name in a small font."* — which is a
    RETURN to his own v04 shape after B106's one-line `Last, First`. ⚠️ Nothing was broken: that
    round was right for its premise, and Marc removed the premise.

    ✅ So the ORDER and the WEIGHT are both asserted against the part, not the presence of
    either: the small line must come FIRST and carry the given name, the bold line SECOND and
    carry the surname.
    """
    # ⚠️ LOOKED UP BY A SINGLE TOKEN, NOT THE WHOLE NAME. Searching for "Lloyd Avant" makes the
    # swap a StopIteration in this helper — a crash, which proves the helper is narrow rather
    # than that the card is wrong. "Avant" is present whichever line it lands on, so the
    # assertion below is what fails.
    header = _header_row(panel(_game(), _both(), deltas=_deltas())[0], "Avant")
    # ⚠️ SCOPED TO THE NAME COLUMN. The POSITION carries a bold weight too (R-801's mirror), so
    # a bare `font-weight:700` sweep would return two strings and this would be about whichever
    # came first. Both name lines carry `text-overflow:ellipsis`; so does the block that wraps
    # them, which has no font size of its own — hence the `font-size` in the pattern.
    lines = re.findall(r"font-size:[^']*text-overflow:ellipsis[^>]*>([^<]+)<", header)
    assert lines == ["Lloyd", "Avant"], (
        f"the name is not `first` over `last` — and the two parts contain exactly the same "
        f"characters whichever order they are in, so nothing that merely looks for the name "
        f"can see the difference: {lines}")
    # 🚨 AND THE WEIGHT, PER PART. Marc asked for the surname bold and the given name small and
    # not bold; a test that only checked the ORDER would pass a header with both lines bold.
    first_markup = header.split(">Lloyd<")[0].rsplit("<div", 1)[-1]
    last_markup = header.split(">Avant<")[0].rsplit("<div", 1)[-1]
    assert "font-weight:700" in last_markup, f"the surname is not bold: {last_markup}"
    assert "font-weight:700" not in first_markup, (
        f"the given name is bold, so the two lines carry equal weight and the surname stops "
        f"being the one a reader finds first: {first_markup}")


def test_the_THREE_HEADER_SIZES_keep_MARCS_ORDERING():
    """🚨 R-835, AND IT IS A RULE HE STATED RATHER THAN A LOOK COWORK CHOSE.

    Marc: *"Jersey # Font can be bigger than Last Name b/c it has the vertical space of First
    Name `<br>` Last Name."* — so the ordering is **jersey > last > first**, and his REASON is
    the geometry: the jersey spans the two-line block, the name lines do not.

    ⚠️ ASSERTED AS A RELATIONSHIP, NOT AS THREE LITERALS. B106 pinned a single literal and Marc
    then changed the shape rather than the number; what survives a reshape is the ordering. A
    round that wants different sizes may have them — it may not invert the rule silently.
    """
    jersey = _module_constant("_CARD_JERSEY_SIZE")
    last = _module_constant("_CARD_LAST_SIZE")
    first = _module_constant("_CARD_FIRST_SIZE")
    assert jersey > last > first, (
        f"the header sizes are jersey={jersey} last={last} first={first}, which breaks Marc's "
        f"ordering jersey > last > first")
    # ⚠️ AND BOTH CAME DOWN FROM B106, because *"too big"* was said about the jersey's 1.5 AND
    # the last name's 1.25. A round may not quietly put them back.
    assert jersey <= 1.5 and last <= 1.25, (
        f"jersey={jersey} last={last} — Marc called 1.5 and 1.25 too big (R-835)")
    # The given name is a supporting line, not a second headline.
    assert first < last * 0.9, (
        f"the given name at {first} is within 10% of the surname at {last}, so the two lines "
        f"read as equals and the surname stops being the one a reader finds first")


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


def test_the_METRIC_HEADER_SPANS_THE_PAGE_and_is_emitted_ONCE_per_metric(panel):
    """🚨 cfdb-wta-R-900. Marc, v14: *"Total, Rushing, and Passing should each have a single
    header row that spans the whole page and has a bold line underneath it."*

    ⚠️ ONCE, NOT TWICE, AND THAT IS THE WHOLE CHANGE. R-752 emitted one header PER HALF PER
    METRIC — six — and said in its own comment that a spanning header *"is deliberately not
    built, because the two halves are separate Streamlit columns."* **The header is now emitted
    at the top level, before the columns open**, so there are three.

    🚨 AND "SPANS" IS ASSERTED POSITIONALLY RATHER THAN BY READING A WIDTH. A markdown block at
    the top level IS the content width; what a test can actually check is that the heading is
    emitted OUTSIDE the column pair — i.e. exactly once per metric rather than once per half.
    A presence assertion would pass on six.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    names = [label for label, *_rest in _module_constant("_YARDAGE_DIMENSIONS")]
    headers = [_plain(str(b)) for k, b in entries
               if k == "markdown" and _plain(str(b)) in set(names)
               and "gained-allowed" not in str(b)]
    assert headers == names, (
        f"expected ONE spanning header per metric in Marc's order {names}, got {headers}")
    assert _charts(entries) == [], (
        "an Altair chart is still being shipped — the scatter was replaced by a box-and-whisker")


def test_each_SECTION_HEADER_carries_a_BOLD_RULE_beneath_it(panel):
    """🚨 cfdb-wta-R-900. Marc, v14: *"has a bold line underneath it."*

    ⚠️ THIS REPLACES A HAIRLINE THAT MEANT SOMETHING ELSE. The old rule was `opacity:.12`
    BETWEEN the blocks and not before the first — a separator. Marc has asked for a rule UNDER
    each heading, including the first, which is a different element doing a different job: it
    binds the name to the rows beneath it rather than parting two neighbours.
    ✅ **It is `_SECTION_RULE`, B112's own 2px constant, reused rather than re-declared** — the
    post-game tab draws exactly this under exactly this heading.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    rule = _module_constant("_SECTION_RULE")
    headers = [str(b) for k, b in entries
               if k == "markdown" and _plain(str(b)) in {"Rushing", "Passing", "Total"}
               and "gained-allowed" not in str(b)]
    assert len(headers) == 3, f"expected three section headings, got {len(headers)}"
    for header in headers:
        assert rule in header, (
            f"a section heading has no bold rule under it: {header}")


def test_the_SUBTRACTION_RULE_is_drawn_and_not_merely_specified(panel):
    """🚨 R-803, AND THE DEFECT IT WORKED AROUND IS GONE WITH THE VEGA SPEC.

    Marc's v02.2 line under the opponent's figure *"like a math problem"* could not be a
    `mark_rule` inside a layered chart: positioned entirely in screen values it serialised
    correctly, validated, appeared in `to_dict()` — **and drew nothing.** The workaround was a
    one-pixel `mark_rect` with a comment begging the next reader not to simplify it.

    ✅ IN HTML IT IS A `border-top` AND THE CLASS OF DEFECT CANNOT RECUR. The old test had to
    assert the mark TYPE to prove the workaround was still in place; this asserts the rule is
    there at all, which is now the same thing.
    """
    entries, _ = panel(_game(), _both(), deltas=_deltas())
    block = _of_metric(entries, "Rushing")[0]
    piece = block.split("data-cfdb='matchup-legend'")[1].split("data-cfdb='box-series'")[0]
    assert "border-top" in piece, (
        f"the subtraction has no rule under its two figures: {piece}")
    # ⚠️ POSITIONAL: the rule sits BETWEEN the two figures and the difference, or it is not a
    # worked subtraction — it is three numbers and a line somewhere.
    assert piece.index("Allowed") < piece.index("border-top") < piece.index("font-weight:700"), \
        "the rule is not between the two figures and the difference"
