"""Matchup's post-game panel: the box score and the advanced block (R-507).

⚠️ THE DEFECT THIS FILE EXISTS FOR IS AC-G.6, AND IT IS A TRAP RATHER THAN AN OVERSIGHT.

`srv_game_team` holds a row for EVERY game back to 1869, and every box-score column is NULL
in all 202,728 of the pre-2024 ones — measured in serving, not inferred. So a 1999 game
returns two rows of nulls, `df.empty` is FALSE, and the obvious version of this panel — the
one that follows every other panel's shape on this page — renders a two-column table of em
dashes for 101,354 games. That is exactly what AC-G.6 forbids: "a page must not show 0, an em
dash or an empty table where the honest answer is 'nothing matched'."

B075 drafted the opposite claim, checked it, and killed its own sentence. This file is the
guard that keeps the correction.

⚠️ THE EMPTINESS TEST IS ON THE VALUES, AND THE VIEW SHIPS THEM: `has_box_score`,
`has_box_advanced`, `has_team_advanced` and `has_havoc`. They are INDEPENDENT — measured on
2024+ games, 3,543 have a box score, 3,471 of those the advanced block, 2,428 havoc — so a
game can have a complete box score and no advanced figures, which is that section's own state
rather than a reason to hide the panel.

The break was staged: swapping the value test for `if df.empty` and pointing it at 62718
(Toledo at Marshall, 1999 wk 8) renders the grid of dashes, and these tests go red.
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

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()


GLOSSARY = pd.DataFrame([
    {"column_name": f, "is_documented": True,
     "column_description": f"Authored definition of {f}."}
    for f in ("offense_ppa", "offense_success_rate", "offense_explosiveness",
              "offense_standard_downs_success_rate", "offense_passing_downs_success_rate",
              "offense_rushing_plays_ppa", "offense_passing_plays_ppa",
              "offense_power_success", "offense_stuff_rate", "offense_line_yards",
              "defense_havoc_rate", "offense_plays")])


@pytest.fixture
def panel():
    """`_post_game` with streamlit captured and both queries answered from constructed rows.

    ⚠️ IT PUTS THE MODULES BACK — reloading lib.states against a stub binds the stub inside it
    for the rest of the session, which cost test_matchup_drives six unrelated failures.

    ⚠️ ON THE SHARED HARNESS SINCE R-613. `captured.events` carries the same `(kind, body)`
    pairs the bespoke stub produced, so nothing below changed.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
        matchup = importlib.reload(importlib.import_module("views.matchup"))
        seen = []

        def run(sides, glossary=GLOSSARY, season=2026, leaders=None, spread=_SPREAD,
                colors=_COLORS):
            # R-730. The season decides WHICH absence the Empty state states, so the
            # fixture has to carry one. 2026 is a completed modern game — the case
            # nearly every test here means; the scope tests pass a pre-2024 season.
            captured.clear()
            seen.clear()

            def fake_query(sql, params=None):
                seen.append(re.search(r"from\s+(\w+)", sql, re.I).group(1))
                # 🚨 R-738 DISPATCHES FIRST AND THE ORDER IS NOT COSMETIC.
                # "srv_game_team_leader_in_this_game" CONTAINS "srv_game_team", so a later
                # branch would answer the CARDS with the box-score frame — two teams' worth of
                # box score rendered as player cards, which is the same trap B099 hit with the
                # usage query and the reason that one is checked first too.
                if "srv_game_team_leader_in_this_game" in sql:
                    return pd.DataFrame(leaders if leaders is not None
                                        else _post_game_leaders())
                # 🚨 THE PREVIEW VIEW ANSWERS TOO, WITH REAL-LOOKING PEOPLE AND NUMBERS, AND
                # THAT IS THE WHOLE POINT. If this branch did not exist, pointing the cards at
                # `..._through_prior_week` would hand them the BOX SCORE frame and the panel
                # would crash — a break caught by a KeyError rather than by an assertion.
                # ⚠️ The defect this round is exposed to does not crash: it renders three
                # filled cards of the wrong window. So the wrong window is made to look right,
                # and only a test that reads the NAMES and the SLOT VALUES can tell them apart.
                if "srv_game_team_leader_through_prior_week" in sql:
                    return pd.DataFrame(_post_game_leaders(
                        player_name="Preview Player", stat_2_value=999.0))
                # 🚨 R-808. ALSO BEFORE `srv_game_team`, and for the same reason the two leader
                # views are: "srv_game_team_metric_distribution" CONTAINS "srv_game_team", so a
                # later branch would hand the bands the BOX SCORE frame.
                if "srv_game_team_metric_distribution" in sql:
                    return pd.DataFrame(spread if spread is not None else [])
                # 🚨 R-848. `from srv_game ` WITH THE TRAILING SPACE, AND IT IS NOT FUSSINESS:
                # every one of the four relations above STARTS with "srv_game", so a bare
                # substring test here would answer the box score, the cards and the spread with
                # a colour frame. The branch is last AND exact.
                if re.search(r"from\s+srv_game\s", sql):
                    return pd.DataFrame([colors] if colors is not None else [])
                return glossary if "srv_data_dictionary" in sql else pd.DataFrame(sides)

            matchup.query = fake_query
            matchup._post_game(401752754, season)
            # 🚨 R-610. An Error state is not a passing state.
            render_harness.assert_no_error_card(captured, "the post-game panel")
            return list(captured.events), list(seen)

        yield run, matchup


# R-738's post-game cards, measured from `srv_game_team_leader_in_this_game`: one quarterback
# from the `total` panel and three rushers, per side. ⚠️ THE LABELS AND FORMATS ARE THE VIEW'S
# OWN — A120 shipped the same twelve slot columns the preview card already reads.
# ⚠️ THE SLOT LABELS PER PANEL, AS A116 PUBLISHES THEM — the view carries them per row and the
# card reads them (R-733), so a fixture that invented its own would be testing itself.
_POST_GAME_PANELS = {
    "total": (("Comp-Att", "pair"), ("Yards", "integer"), ("TD", "integer")),
    "rushing": (("Carries", "integer"), ("Yards", "integer"), ("Yds/Carry", "decimal_1")),
    # 🚨 R-809. `passing` IS THE RECEIVERS, NOT THE PASSERS — A116 and B099 both settled it, and
    # the quarterback is already on the card under `total`.
    "passing": (("Receptions", "integer"), ("Yards", "integer"), ("TD", "integer")),
}


def _post_game_leaders(**overrides):
    """Both sides' post-game leaders: one QB, three rushers and three receivers each (R-809)."""
    rows = []
    # ⚠️ THE SAME IDS `_side()` USES — 2 at home, 96 away. A card frame keyed on ids the box
    # score does not carry would render no cards at all while every table assertion passed.
    for team_id, who in ((2, "Home"), (96, "Away")):
        for panel, names in (("total", [f"{who} QB"]),
                             ("rushing", [f"{who} RB1", f"{who} RB2", f"{who} RB3"]),
                             ("passing", [f"{who} WR1", f"{who} WR2", f"{who} WR3"])):
            (l1, f1), (l2, f2), (l3, f3) = _POST_GAME_PANELS[panel]
            for rank, name in enumerate(names, start=1):
                rows.append({
                    "team_id": team_id, "panel": panel, "leader_rank": rank,
                    "tied_players": 1, "qualified_players": len(names),
                    "player_id": f"p{team_id}{panel[:2]}{rank}", "player_name": name,
                    "player_slug": name.lower().replace(" ", "-"),
                    "jersey": 10 + rank,
                    "position": {"total": "QB", "rushing": "RB", "passing": "WR"}[panel],
                    "class_year_display": "SR",
                    "stat_1_label": l1, "stat_1_format": f1,
                    "stat_1_value": 18.0 if f1 == "pair" else 12.0,
                    "stat_1_value_secondary": 29.0 if f1 == "pair" else None,
                    "stat_2_label": l2, "stat_2_format": f2,
                    "stat_2_value": 100.0 + rank, "stat_2_value_secondary": None,
                    "stat_3_label": l3, "stat_3_format": f3,
                    "stat_3_value": 4.5 if f3 == "decimal_1" else 2.0,
                    "stat_3_value_secondary": None})
    for row in rows:
        row.update(overrides)
    return rows


# 🚨 R-848. THE TWO TEAMS' COLOURS, as `srv_game` publishes them — the pair `row_for_side`
# renames for `identity.text_on`. ⚠️ The AWAY side deliberately carries NO colour: 10.89% of
# games have one, and a fixture where both sides are populated could not tell the fallback path
# from the sourced one.
_COLORS = {"away_color_on_light": None, "away_color_on_dark": None,
           "home_color_on_light": "#0021A5", "home_color_on_dark": "#4C7BEF"}

# 🚨 R-808. THE WEEK'S SPREAD, PER MEASURE — real 2026 week-1 shapes off
# `srv_game_team_metric_distribution`, so the bands are drawn over numbers the view actually
# publishes rather than over invented ones.
#
# ⚠️ `min_value` AND `whisker_low` DISAGREE ON PURPOSE, AND THAT IS WHAT MAKES THE STAGED BREAK
# DECIDABLE. `first_downs` really does run 4 → 38 with fences at 5 → 38, and `rushing_yards` 2 →
# 569 with fences at 2 → 365. A band drawn from the extremes and labelled as the fences is a
# picture describing a wider spread than its own labels claim — and only a fixture whose two
# pairs differ can tell them apart.
_SPREAD = [
    {"metric": "first_downs", "n": 150, "team_games_in_week": 150,
     "min_value": 4.0, "whisker_low": 5.0, "p25": 18.0, "p50": 21.0, "p75": 27.0,
     "whisker_high": 38.0, "max_value": 38.0},
    {"metric": "total_yards", "n": 150, "team_games_in_week": 150,
     "min_value": 67.0, "whisker_low": 67.0, "p25": 322.0, "p50": 402.0, "p75": 519.0,
     "whisker_high": 762.0, "max_value": 762.0},
    {"metric": "rushing_yards", "n": 150, "team_games_in_week": 150,
     "min_value": 2.0, "whisker_low": 2.0, "p25": 109.5, "p50": 163.5, "p75": 237.0,
     "whisker_high": 365.0, "max_value": 569.0},
    {"metric": "passing_yards", "n": 150, "team_games_in_week": 150,
     "min_value": 19.0, "whisker_low": 19.0, "p25": 164.25, "p50": 233.0, "p75": 308.5,
     "whisker_high": 480.0, "max_value": 480.0},
    {"metric": "rushing_attempts", "n": 150, "team_games_in_week": 150,
     "min_value": 17.0, "whisker_low": 17.0, "p25": 31.0, "p50": 38.0, "p75": 42.0,
     "whisker_high": 58.0, "max_value": 73.0},
    {"metric": "penalty_yards", "n": 150, "team_games_in_week": 150,
     "min_value": 4.0, "whisker_low": 4.0, "p25": 35.0, "p50": 52.0, "p75": 70.0,
     "whisker_high": 119.0, "max_value": 134.0},
    {"metric": "offense_ppa", "n": 150, "team_games_in_week": 150,
     "min_value": -0.336, "whisker_low": -0.336, "p25": 0.075, "p50": 0.234, "p75": 0.402,
     "whisker_high": 0.743, "max_value": 0.743},
    {"metric": "offense_passing_downs_success_rate", "n": 150, "team_games_in_week": 150,
     "min_value": 0.0, "whisker_low": 0.0, "p25": 0.240, "p50": 0.333, "p75": 0.433,
     "whisker_high": 0.714, "max_value": 0.733},
    {"metric": "offense_plays", "n": 150, "team_games_in_week": 150,
     "min_value": 41.0, "whisker_low": 41.0, "p25": 61.0, "p50": 69.0, "p75": 76.0,
     "whisker_high": 95.0, "max_value": 101.0},
]

_ADVANCED_VALUES = {
    "offense_plays": 71, "offense_drives": 12, "offense_ppa": 0.123,
    "offense_success_rate": 0.451, "offense_explosiveness": 1.234,
    "offense_standard_downs_success_rate": 0.512,
    "offense_passing_downs_success_rate": 0.281,
    "offense_rushing_plays_ppa": 0.061, "offense_passing_plays_ppa": 0.188,
    "offense_power_success": 0.750, "offense_stuff_rate": 0.192,
    "offense_line_yards": 2.84, "defense_havoc_rate": 0.172,
}


def _side(team, is_home, **overrides):
    """One srv_game_team row. Real 2025 wk-10 box-score figures for 401752754.

    Every number differs between the two sides on purpose, so an assertion that a value
    reached the panel can only be satisfied by the column and the side it came from.
    """
    row = {"game_id": 401752754, "team_id": 2 if is_home else 96,
           "team_display": team, "team_logo_url": None, "is_home": is_home,
           # 🚨 R-808. THE WEEK IS WHAT KEYS THE DISTRIBUTION, and without it `_metric_band`
           # draws nothing at all — silently, because an absent spread is a legitimate state.
           # **A fixture missing these three would make every band assertion vacuous.**
           "season": 2025, "season_type": "regular", "week": 10,
           "has_box_score": True, "has_box_advanced": True,
           "has_team_advanced": True, "has_havoc": True,
           "first_downs": 17 if is_home else 16,
           "total_yards": 241 if is_home else 240,
           "rushing_yards": 118 if is_home else 79,
           "passing_yards": 123 if is_home else 161,
           "rushing_attempts": 40 if is_home else 32,
           "turnovers": 2, "interceptions": 1 if is_home else 2,
           "fumbles_lost": 1 if is_home else 0,
           "third_down_conversions": 6,
           "third_down_attempts": 16 if is_home else 13,
           "fourth_down_conversions": 1 if is_home else 0,
           "fourth_down_attempts": 2 if is_home else 1,
           "penalties": 4 if is_home else 3,
           "penalty_yards": 26 if is_home else 20,
           # ⚠️ THE SERVING-SHIPPED DISPLAY STRINGS (A080). Without these the narrowed
           # percentage assertion below passes for the wrong reason — no `%` can appear if
           # the fixture never supplies one.
           "possession_display": "31:46" if is_home else "28:14",
           "offense_success_rate_display": "45.1%" if is_home else "22.6%",
           "offense_standard_downs_success_rate_display": "51.2%" if is_home else "25.6%",
           "offense_passing_downs_success_rate_display": "28.1%" if is_home else "14.1%",
           "offense_power_success_display": "75.0%" if is_home else "37.5%",
           "offense_stuff_rate_display": "19.2%" if is_home else "9.6%",
           "defense_havoc_rate_display": "17.2%" if is_home else "8.6%",
           "as_of_ts": pd.Timestamp("2026-09-09T12:00:00Z")}
    row.update({k: (v if is_home else round(v / 2, 3))
                for k, v in _ADVANCED_VALUES.items()})
    # The denominator is set explicitly rather than halved: 71/2 lands on 35.5, and an
    # assertion that depends on which way a .5 rounds is testing the formatter.
    row["offense_plays"] = 71 if is_home else 64
    row.update(overrides)
    return row


def _both(**over):
    return [_side("Auburn", True, **over), _side("Kentucky", False, **over)]


def _dead(**over):
    """⚠️ A PRE-2024 GAME: rows present, every value NULL, every flag False. 62718."""
    row = {"game_id": 62718, "team_id": 276, "team_display": "Marshall",
           "team_logo_url": None, "is_home": True,
           "has_box_score": False, "has_box_advanced": False,
           "has_team_advanced": False, "has_havoc": False,
           "as_of_ts": pd.Timestamp("2026-09-09T12:00:00Z")}
    row.update({f: None for f in
                ("first_downs", "total_yards", "rushing_yards", "passing_yards",
                 "rushing_attempts", "turnovers", "interceptions", "fumbles_lost",
                 "third_down_conversions", "third_down_attempts",
                 "fourth_down_conversions", "fourth_down_attempts",
                 "penalties", "penalty_yards")})
    row.update({f: None for f in _ADVANCED_VALUES})
    row.update({f: None for f in
                ("possession_display", "offense_success_rate_display",
                 "offense_standard_downs_success_rate_display",
                 "offense_passing_downs_success_rate_display",
                 "offense_power_success_display", "offense_stuff_rate_display",
                 "defense_havoc_rate_display")})
    row.update(over)
    other = dict(row, team_id=2649, team_display="Toledo", is_home=False)
    return [row, other]


def _text(entries):
    return " ".join(
        re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()
        for _, body in entries)


# --- ⚠️ AC-G.6: the trap ---------------------------------------------------------------------

def test_a_pre_2024_game_renders_empty_not_a_table_of_em_dashes(panel):
    """THE ASSERTION THIS FILE EXISTS FOR, on `62718` — the real game B074 and B075 both used.

    Staged red first: replacing the `has_box_score` test with `if df.empty` makes the panel
    draw a full grid of `—` for both sides and fails this test on the dash count.
    """
    run, _ = panel
    entries, _ = run(_dead(), season=2023)
    body = _text(entries)
    # ⚠️ THE DASH COUNT IS ASSERTED FIRST, ON PURPOSE. When the break was staged, the
    # ADVANCED section's own guard still fired, so "would be here" was present while the box
    # score above it drew a full grid of dashes — the "did it render Empty" assertion passed
    # for the wrong reason. The count and the absent row label are what actually catch it.
    assert body.count("—") == 0, \
        f"the panel drew {body.count('—')} em dashes where the honest answer is Empty"
    assert "First downs" not in body, "the box score grid rendered over a game with no data"
    assert "would be here" in body, "the Empty state did not render"
    assert "2024 onward" in body, "the Empty state did not say why"


def test_the_emptiness_test_is_on_the_values_not_the_frame(panel):
    """The frame is NOT empty for a pre-2024 game — two rows come back. If the panel ever
    tests `df.empty` again, this is the sentence that failed."""
    run, _ = panel
    sides = _dead()
    assert len(sides) == 2 and not pd.DataFrame(sides).empty, \
        "the fixture no longer reproduces the trap"
    assert "would be here" in _text(run(sides)[0])


def test_one_side_missing_its_box_score_is_empty_too(panel):
    """Half a box score is not a box score. Both columns or neither."""
    run, _ = panel
    sides = _both()
    sides[1]["has_box_score"] = False
    assert "would be here" in _text(run(sides)[0])


# --- ⚠️ one read, two renderings -------------------------------------------------------------

def test_the_box_score_and_the_advanced_block_are_one_read(panel):
    """G-2. srv_game_team carries both, so two queries against it would be two passes over
    one relation — and it is also what stops the two sections disagreeing about a game."""
    run, _ = panel
    _, seen = run(_both())
    assert seen.count("srv_game_team") == 1, \
        f"srv_game_team was read {seen.count('srv_game_team')} times, not once"


def test_the_panel_issues_exactly_THREE_reads_and_each_serves_both_sides(panel):
    """Not one read per metric, and not one per card column.

    ⚠️ THE SEQUENCE IS ASSERTED RATHER THAN THE COUNT, so a read that moves or doubles is
    visible. `query` caches on the parameter set, so the dictionary is one read per TTL window
    across every game anyone opens.

    🚨 R-738 ADDED THE THIRD AND IT IS ONE READ FOR FOUR CARD COLUMNS — both panels are flanked
    by the same cast, so reading per panel, or per side, would have been two or four reads for
    one answer. That is the whole reason `_post_game_leaders` is called once in `_post_game`
    rather than inside `_post_game_flank`.
    """
    run, _ = panel
    _, seen = run(_both())
    assert seen.count("srv_data_dictionary") == 1
    assert seen.count("srv_game_team_leader_in_this_game") == 1, (
        f"the cards were read {seen.count('srv_game_team_leader_in_this_game')} times — both "
        f"panels are flanked by the same leaders and one read serves all four columns: {seen}")
    # 🚨 R-808 ADDED THE FOURTH, AND IT IS ONE READ FOR EIGHTEEN BANDS. The distribution is
    # keyed by the WEEK, not by the measure, so one row set serves every band in both panels —
    # eighteen reads for one answer is the shape this assertion exists to prevent.
    assert seen.count("srv_game_team_metric_distribution") == 1, (
        f"the spread was read {seen.count('srv_game_team_metric_distribution')} times — one "
        f"week-keyed read serves all eighteen bands across both panels: {seen}")
    # 🚨 R-848 ADDED THE FIFTH. `srv_game_team` carries no colour column, so the header's team
    # accent comes from `srv_game` — one bounded read for both sides, not one per side.
    assert seen.count("srv_game") == 1, (
        f"the colours were read {seen.count('srv_game')} times — one read serves both sides "
        f"and both sections: {seen}")
    assert seen == ["srv_game_team", "srv_game_team_leader_in_this_game",
                    "srv_game_team_metric_distribution", "srv_game",
                    "srv_data_dictionary"], f"the panel issued {seen}"


def test_a_game_with_no_advanced_block_does_not_read_the_dictionary(panel):
    """Nothing to define, so nothing to look up — the laziness B075 built, one level down."""
    run, _ = panel
    _, seen = run(_both(has_team_advanced=False))
    assert "srv_data_dictionary" not in seen


# --- the box score draws, and on the right sides ---------------------------------------------

def test_a_2024_game_draws_real_figures_for_both_sides(panel):
    run, _ = panel
    body = _text(run(_both())[0])
    assert "Auburn" in body and "Kentucky" in body
    for figure in ("17", "16", "241", "240", "118", "79", "123", "161"):
        assert figure in body, f"{figure} is missing from the box score"


def test_away_is_on_the_left_and_home_on_the_right(panel):
    """The scoreline's convention, and the reason that layout reads as a matchup at all."""
    run, _ = panel
    blocks = [b for kind, b in run(_both())[0] if kind == "markdown"]
    heading = next(b for b in blocks if "Kentucky" in b and "Auburn" in b)
    assert heading.index("Kentucky") < heading.index("Auburn"), \
        "the home team was drawn on the left"


def _row_markup(entries, label):
    """The VISIBLE TEXT of the single rendered row carrying this label.

    ⚠️ IT SPLITS ON `data-cfdb='metric-cell'`, NOT ON A STYLE PREFIX. B106 moved the row into a
    fixed-width cell (R-807) and the old anchor — the literal `<div style='display:flex;` — no
    longer started the row, so every chunk collapsed into one and the whole panel came back as
    "the row". The attribute exists to be anchored on; a style string is not an interface.

    🚨 AND IT RETURNS TEXT RATHER THAN MARKUP, WHICH IS THE HALF THAT WAS ALWAYS WRONG. The two
    callers assert `"%" not in row`, and the cell's own style carries `max-width:100%` — so on
    markup the assertion fires on a CSS declaration and says the page divided. A `%` inside an
    attribute was never what G-3 was about; a `%` the reader can see is.
    """
    # ⚠️ NON-GREEDY TO THE FIRST `</div>`, WHICH IS SOUND HERE AND SAYS WHY: a metric cell's
    # children are all `<span>`, so the first close tag is the cell's own. The heading shares
    # the cell's GEOMETRY but carries no `data-cfdb`, so it is not a row and never matches.
    for cell in _cells(entries):
        if f">{label}<" in cell:
            return re.sub(r"\s+", " ",
                          html.unescape(re.sub(r"<[^>]+>", " ", cell))).strip()
    return ""


def test_the_ratio_rows_are_fractions_not_percentages(panel):
    """G-3. The app does not divide — `8/14`, never `46.2%`.

    ⚠️ THIS ASSERTION WAS NARROWED IN B077, NOT REMOVED, AND THE DIFFERENCE IS THE POINT.

        before:  assert "%" not in body            — no percentage ANYWHERE in the panel
        after:   assert "%" not in <the third-down row>
                 assert "%" not in <the fourth-down row>
                 plus test_the_five_decimal_rows_did_not_gain_a_percent, and
                 test_the_six_share_rows_render_the_serving_display_string

    What it protected is unchanged and is still protected: a conversion rate is the app doing
    arithmetic on two columns it was handed separately, and it must never appear. What changed
    is that A080 published six display strings, so six rows now carry a `%` that the SERVING
    LAYER computed — a `%` in the panel is no longer evidence that the page divided, but a `%`
    on these two rows still is. Loosening this to "no % except sometimes" would have been the
    failure mode; scoping it to the rows it was always about is not.
    """
    run, _ = panel
    entries = run(_both())[0]
    body = _text(entries)
    assert "6/13" in body and "6/16" in body, "third down did not render as a fraction"
    for label in ("Third down", "Fourth down"):
        row = _row_markup(entries, label)
        assert row, f"the {label} row did not render at all"
        assert "%" not in row, f"the panel computed a conversion rate on {label}"


def test_the_five_decimal_rows_did_not_gain_a_percent(panel):
    """⚠️ MEASURED, NOT CONVENTIONAL. offense_ppa runs NEGATIVE (−0.644) and
    offense_explosiveness reaches 2.737 — a share can do neither, so these five have no
    display column and must keep their decimals."""
    run, matchup = panel
    entries = run(_both())[0]
    for label in ("Predicted points added / play", "PPA, rushing plays",
                  "PPA, passing plays", "Explosiveness", "Line yards"):
        row = _row_markup(entries, label)
        assert row, f"the {label} row did not render"
        assert "%" not in row, f"{label} was rendered as a percentage"
    decimal_fields = [f for _l, f, _d in matchup._ADVANCED_ROWS
                      if f not in matchup._DISPLAY_COLUMN and f != "offense_plays"]
    assert len(decimal_fields) == 5, f"expected five decimal rows, found {decimal_fields}"


def test_the_six_share_rows_render_the_serving_display_string(panel):
    """⚠️ THE APP CANNOT MULTIPLY. B076 drew 0.451 and said so; A080 published the string.
    Nothing here computes it — the value on screen is the column."""
    run, matchup = panel
    body = _text(run(_both())[0])
    assert len(matchup._DISPLAY_COLUMN) == 6
    for shown in ("45.1%", "22.6%", "51.2%", "28.1%", "75.0%", "19.2%", "17.2%"):
        assert shown in body, f"{shown} did not reach the panel"


def test_the_glossary_still_looks_the_metric_up_by_its_real_name(panel):
    """⚠️ THE TRAP IN PART 0. dim_field_metadata documents `offense_success_rate`, NOT
    `offense_success_rate_display`. Swapping the field name inside _ADVANCED_ROWS would make
    six of the twelve tooltips "(undefined)" — which is why the display column is a MAP beside
    the rows rather than a replacement inside them."""
    _, matchup = panel
    for field in matchup._GLOSSARY_FIELDS:
        assert not field.endswith("_display"), \
            f"{field} is a display column and the dictionary has never heard of it"
    for metric, display in matchup._DISPLAY_COLUMN.items():
        assert metric in matchup._GLOSSARY_FIELDS, f"{metric} fell out of the glossary lookup"
        assert display == f"{metric}_display"


def test_possession_renders_from_the_serving_column(panel):
    """A080 published possession_display, so the row B076 left off exists and nothing here
    divides 1,906 into 31:46. Sanity check on 401752665: 29:38 + 30:22 = 60:00."""
    run, _ = panel
    body = _text(run(_both())[0])
    assert "Possession" in body and "31:46" in body and "28:14" in body
    assert "1906" not in body and "1,906" not in body, "raw seconds reached the reader"


def test_turnovers_carry_their_split(panel):
    run, _ = panel
    body = _text(run(_both())[0])
    assert "INT" in body and "FUM" in body


# --- the advanced block, and the dozen --------------------------------------------------------

def test_exactly_twelve_advanced_rows_are_offered(panel):
    """⚠️ srv_game_team HAS 223 COLUMNS. A hundred numbers is not a page, it is a data
    dictionary with a scoreline on top. The cut is editorial and it is stated so a reviewer
    can disagree with it."""
    _, matchup = panel
    assert len(matchup._ADVANCED_ROWS) == 12, \
        f"the advanced cut is {len(matchup._ADVANCED_ROWS)} rows, not a dozen"


def test_the_advanced_rows_come_from_the_broader_family(panel):
    """⚠️ DECIDED ON COVERAGE, NOT TASTE. has_team_advanced reaches 3,471 games and
    has_box_advanced 1,849, so the narrower family would blank this section on 48% of the
    games that HAVE a box score while an equivalent column sat beside it."""
    _, matchup = panel
    fields = [f for _l, f, _d in matchup._ADVANCED_ROWS]
    for narrow in ("ppa_overall_total", "success_rate_overall_total", "explosiveness_total",
                   "havoc_total", "stuff_rate", "power_success", "line_yards_average"):
        assert narrow not in fields, \
            f"{narrow} is behind has_box_advanced, which covers half as many games"


def test_the_defensive_mirror_is_not_drawn_twice(panel):
    """⚠️ defense_ppa for one side EQUALS offense_ppa for the other, to the last decimal —
    verified on 401752754. Rendering both per side draws the same numbers twice; the
    defensive reading is the other column, read across."""
    _, matchup = panel
    fields = [f for _l, f, _d in matchup._ADVANCED_ROWS]
    mirrored = [f for f in fields if f.startswith("defense_") and f != "defense_havoc_rate"]
    assert not mirrored, f"these are the other column restated: {mirrored}"


def test_havoc_is_read_from_the_defensive_side(panel):
    """⚠️ offense_havoc_rate is havoc SUFFERED by that offense, not generated by it —
    offense_havoc_rate(Auburn) equals defense_havoc_rate(Kentucky), measured. Labelling it as
    a defensive figure would be exactly wrong."""
    _, matchup = panel
    fields = [f for _l, f, _d in matchup._ADVANCED_ROWS]
    assert "defense_havoc_rate" in fields and "offense_havoc_rate" not in fields


def test_the_denominator_is_on_the_panel(panel):
    """AC-G.33. Every rate above is over that side's own plays and the two sides do not run
    the same number of them."""
    run, matchup = panel
    fields = [f for _l, f, _d in matchup._ADVANCED_ROWS]
    assert "offense_plays" in fields
    body = _text(run(_both())[0])
    assert "71" in body and "64" in body, \
        "the two sides' play counts are not both on the panel"


def test_a_game_with_no_havoc_drops_that_row_and_keeps_the_rest(panel):
    run, _ = panel
    body = _text(run(_both(has_havoc=False))[0])
    assert "Havoc" not in body, "a havoc row rendered for a game with no havoc data"
    assert "Success rate" in body, "the rest of the advanced block went with it"


def test_a_box_score_without_advanced_says_so_rather_than_vanishing(panel):
    """⚠️ THE FLAGS ARE INDEPENDENT. 72 of the 3,543 games with a box score have no advanced
    block, and a section that silently disappeared would be indistinguishable from one that
    had never been written."""
    run, _ = panel
    body = _text(run(_both(has_team_advanced=False))[0])
    assert "First downs" in body, "the box score went with the advanced block"
    assert "Advanced" in body and "would be here" in body


# --- ⚠️ the definitions come from the dictionary, not from the page ---------------------------

def test_every_advanced_metric_carries_its_definition(panel):
    """PPA, havoc, explosiveness and stuff rate are not common knowledge, and a number a
    reader cannot interpret is worse than no number — it reads as padding."""
    run, matchup = panel
    body = " ".join(b for _k, b in run(_both())[0])
    for _label, field, _dp in matchup._ADVANCED_ROWS:
        assert f"Authored definition of {field}" in body, f"{field} rendered undefined"


def test_a_metric_with_no_dictionary_entry_is_named_not_quietly_rendered(panel):
    """A finding a reader can act on, rather than a bare number."""
    run, _ = panel
    thin = GLOSSARY[GLOSSARY.column_name != "offense_stuff_rate"]
    body = _text(run(_both(), glossary=thin)[0])
    assert "Not yet defined in the data dictionary" in body
    assert "Stuff rate" in body


def test_no_definition_is_written_in_the_page(panel):
    """⚠️ Prose written here is prose that drifts from the dictionary the export ships."""
    block = SOURCE[SOURCE.index("_ADVANCED_ROWS = ("):SOURCE.index("_GLOSSARY_FIELDS")]
    for word in ("expected points", "tackle for loss", "line of scrimmage", "share of plays"):
        assert word not in block.lower(), \
            f"a definition was written into the page: {word!r}"


# --- what this round did NOT build ------------------------------------------------------------

def _code_only(source: str) -> str:
    """The module with comments and docstrings removed.

    ⚠️ A BAN ON A NAME MUST BE A BAN ON READING IT, NOT ON EXPLAINING IT. B075 hit the same
    shape with `st.tabs`: the module documents at length why it is not used, so a bare
    substring test asserts that the reasoning is absent rather than that the call is. Here the
    leaders panel's docstring names both banned views to record why neither could answer the
    question — which is exactly the prose that should survive.
    """
    import ast
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body[0].value.value = ""
    return ast.unparse(tree)


def test_the_ranking_is_read_and_never_computed_in_the_page():
    """⚠️ THE BAN STAYS, AND THE POSITIVE ASSERTION JOINS IT — IT DOES NOT REPLACE IT.

    B076 ended with R-506 blocked: nothing in serving ranked players within a game, so "who
    led" was a window function, which CLAUDE.md puts upstream. A080 built
    `srv_game_team_leader` at (game_id, team_id, stat_category, stat_type), so B077 could read
    it. `srv_game_team_leader` is neither banned view, so the ban did not have to move.

    It must not move. `srv_player_stats` still ranks at SEASON grain with no game_id and
    `srv_player_game_log` still carries no rank, so either name being READ here would still
    mean the page derived a ranking — the exact thing A080 was built to prevent.
    """
    code = _code_only(SOURCE)
    for banned in ("srv_player_game_log", "srv_player_stats"):
        assert banned not in code, f"{banned} was read to rank players in the page"
    assert "srv_game_team_leader" in code, "the leaders panel does not read the ranked object"
    # ⚠️ ANCHORED ON THE QUERY LITERAL, NOT ON ITS FIRST COLUMN. B077 wrote
    # `block.index("select team_id")`, and B078 adding one column to the select — `season`,
    # for the player link — made that anchor vanish and this test raise ValueError instead of
    # asserting anything. The assertion is unchanged; only what it grips has moved to
    # something a column list cannot break.
    block = SOURCE[SOURCE.index("def _leaders("):SOURCE.index("def _leader_heading(")]
    sql = block.split('query("""')[1].split('"""')[0].lower()
    for computed in ("order by", "rank(", "row_number(", "over (", "group by", "join"):
        assert computed not in sql, f"the leaders query contains `{computed}`"


def test_the_panel_computes_nothing(panel):
    """G-3, asserted on the SQL the panel actually issued."""
    block = SOURCE[SOURCE.index("_POSTGAME_COLUMNS = "):SOURCE.index("def _leader_note(")]
    sql = block[block.index("select {_POSTGAME_COLUMNS}"):block.index('limit 2')].lower()
    for banned in ("group by", "sum(", "avg(", "row_number(", "rank(", "over (", "join"):
        assert banned not in sql, f"the panel's query contains `{banned}`"


# --- 🚨 R-730: WHICH absence is this? ------------------------------------------------------
#
# "cfdb holds box scores from 2024 onward, and this game's is not among them." True, and the
# wrong reason for a 2026 game — the box score lands after the game rather than never.
#
# ⚠️ THE FIXTURE IS `_dead()` IN BOTH CASES ON PURPOSE. srv_game_team holds an all-NULL row
# for every game back to 1869 AND for a modern game whose box score has not landed, so the
# FRAME cannot tell the two apart. That is precisely why the season had to be passed in, and
# a test that used a different frame per branch would be proving something easier.

def test_the_two_absences_do_not_share_a_sentence(panel):
    run, _ = panel
    out_of_scope = _text(run(_dead(), season=2023)[0])
    not_yet = _text(run(_dead(), season=2026)[0])
    assert out_of_scope != not_yet, (
        "a 2023 game and a 2026 game were told the same thing about why there is no box score")


def test_a_completed_modern_game_is_told_the_data_has_not_LANDED(panel):
    run, _ = panel
    body = _text(run(_dead(), season=2026)[0])
    assert "2024 onward" not in body, (
        "scope is the wrong reason for a 2026 game whose box score simply has not landed")
    assert "kicked off" not in body
    assert "not arrived yet" in body and "after the game" in body, (
        f"the reader was not told when to come back: {body!r}")
    assert body.count("—") == 0, "still Empty, not a grid of dashes"


def test_a_pre_2024_game_is_still_told_it_is_out_of_SCOPE(panel):
    run, _ = panel
    body = _text(run(_dead(), season=1999)[0])
    assert "2024 onward" in body
    assert "not arrived yet" not in body, (
        "a 1999 game was promised a box score that will never exist")


# --- 🚨 R-738: the post-game cards ---------------------------------------------------------

_CARD_MARK = "border:1px solid rgba(128,128,128,.22)"


def _plain(markup: str) -> str:
    """Tags out, whitespace collapsed — the sentence a reader sees."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


def _card_blocks(entries):
    """The card columns, in drawn order: away, home, away, home — two panels, two sides."""
    return [str(b) for k, b in entries if k == "markdown" and _CARD_MARK in str(b)]


def _cards_in(block):
    """One column's cards, split apart."""
    return [piece for piece in block.split(_CARD_MARK)[1:]]


def test_the_cards_sit_beside_BOTH_panels_and_RECEIVING_is_added_only_in_ADVANCED(panel):
    """Marc named ONE card list against TWO panels — and v08 changed what that list is.

    ⚠️ THIS TEST USED TO ASSERT THE TWO SECTIONS WERE IDENTICAL (R-738), and the reason was
    good: *a reader scrolling from one panel to the other should not find the cast has changed
    under him.* 🚨 **Marc's v08 overrules it — *"Receiving (3, in the Advanced section)"* — and
    his reason beats the old one: Cowork argued about MEANING, he is arguing about FIT.**

    ✅ SO THE CLAIM NARROWS RATHER THAN DISAPPEARING. The quarterbacks and rushers must STILL be
    identical between the sections — that half of R-738 is untouched, and it is what stops a
    reader finding a different cast — and Advanced adds receiving on top.
    """
    run, _ = panel
    blocks = _card_blocks(run(_both())[0])
    assert len(blocks) == 4, (
        f"expected two card columns per section across two sections, got {len(blocks)}")
    box_away, box_home, adv_away, adv_home = blocks
    for section, box, adv in (("away", box_away, adv_away), ("home", box_home, adv_home)):
        assert "Receiving" not in _plain(box), (
            f"the {section} Box score column carries a Receiving group — v08 puts it in "
            f"Advanced only")
        assert "Receiving" in _plain(adv), (
            f"the {section} Advanced column has no Receiving group")
        # 🚨 THE SHARED HALF, ASSERTED AS A PREFIX RATHER THAN AS EQUALITY: Advanced is the Box
        # score column plus receiving, so the quarterbacks and rushers must be byte-identical
        # up to where receiving begins. Equality would have to be dropped entirely; a prefix
        # keeps R-738's actual claim.
        assert adv.startswith(box), (
            f"the {section} column's quarterbacks and rushers differ between the sections — "
            f"v08 adds receiving to Advanced, it does not rebuild the cast")


def test_the_AWAY_cards_are_drawn_BEFORE_the_HOME_cards(panel):
    """🚨 POSITIONAL, NOT PRESENCE. B082 proved a presence assertion passes a left/right swap on
    the game header and B083 proved it again on the win-probability bar.

    ⚠️ AND THIS PANEL IS NOT B098's MIRROR. That flanked two charts, one per side; this flanks
    ONE TABLE carrying both sides, so away goes outside-left and home outside-right — the
    away-over-home law (R-522) rather than a mirror.
    """
    run, _ = panel
    blocks = _card_blocks(run(_both())[0])
    # ⚠️ PLAIN TEXT SINCE R-753: the name is two elements — small first line, bold last line —
    # so "Away QB" no longer appears contiguously in the markup.
    away, home = _plain(blocks[0]), _plain(blocks[1])
    # ⚠️ R-835 PUT THE NAME BACK ON TWO LINES, so `_plain` yields `Away QB` rather than
    # `QB, Away`. The claim is unchanged — which SIDE is drawn first — and it is still
    # positional rather than a presence check.
    assert "Away QB" in away and "Home QB" not in away, \
        f"the first card column is not the AWAY side: {away[:120]}"
    assert "Home QB" in home and "Away QB" not in home, \
        f"the second card column is not the HOME side: {home[:120]}"


def test_EVERY_DISCIPLINE_IS_REPRESENTED_on_the_post_game_cards(panel):
    """🚨 R-809. Marc: *"I don't see any WR in the player cards… We need full coverage."*

    ⚠️ THE EXPECTED SET IS WRITTEN OUT HERE AND IS **NOT** READ FROM `_POST_GAME_CARDS`, AND
    THAT IS THE WHOLE POINT. A test that iterated the page's own tuple would drop `passing` from
    its expectations the moment the page dropped it — it would pass the staged break and assert
    nothing but that the page agrees with itself (R-744).

    ✅ ASSERTED BY WHAT THE READER SEES, per discipline: the slot-1 LABEL the view publishes for
    that panel. `Comp-Att` can only come from `total`, `Carries` from `rushing`, `Receptions`
    from `passing` — so this cannot be satisfied by drawing the same man three times.

    ⚠️ AND IT INVOKES THE PAGE RATHER THAN REPRODUCING IT (R-768, A123's break went green
    because the test built its own frame). `run()` calls the real `_post_game`.
    """
    run, _ = panel
    blocks = _card_blocks(run(_both())[0])
    box_away = _plain("".join(_cards_in(blocks[0])))
    adv_away = _plain("".join(_cards_in(blocks[2])))
    # ⚠️ WHICH SECTION EACH DISCIPLINE IS LOOKED FOR IN IS THE v08 CHANGE (R-848). Receiving
    # moved to Advanced on Marc's word; the other two stay in both. **Looking for all three in
    # the Box score column would now fail for the right reason and the wrong claim.**
    for discipline, marker, where, text in (
            ("the quarterback", "Comp-Att", "Box score", box_away),
            ("the rushers", "Carries", "Box score", box_away),
            ("the quarterback", "Comp-Att", "Advanced", adv_away),
            ("the rushers", "Carries", "Advanced", adv_away),
            ("the receivers", "Receptions", "Advanced", adv_away)):
        assert marker in text, (
            f"{discipline} are not on the {where} cards — no {marker!r} in the away column. "
            f"Marc asked for full coverage: {text[:200]}")


def test_TWO_quarterback_slots_THREE_rushers_and_THREE_receivers(panel):
    """🚨 A120 MEASURED WHY THE QB IS ALONE: of 6,736 `total` groups, 6,300 — 93.5% — have fewer
    than three leaders and 3,990 have exactly one. A team plays one quarterback.

    🚨 AND THE OTHER TWO ARE AT **2**, WHICH IS A TRADE RATHER THAN A PREFERENCE. Measured on Sam
    Houston at Troy at 1300px: at three per discipline the card column runs 515px against a
    353px Box score and a 384px Advanced — 162px and 131px past the panel it flanks. At two it
    is 426px, so +73 and +42.

    ⚠️ THE COUNT IS ASSERTED AGAINST THE MEASURED SHAPE AND NOT READ FROM `_POST_GAME_CARDS`,
    for the same reason `test_EVERY_DISCIPLINE_IS_REPRESENTED` writes its set out: a test that
    took the page's own tuple as its expectation would agree with any tuple.
    """
    run, _ = panel
    blocks = _card_blocks(run(_both())[0])
    # ⚠️ `_cards_in` COUNTS DRAWN CARDS ONLY — a reserved slot carries a DASHED border, so it is
    # deliberately not one of these. The reserved slots are asserted by their own text below.
    box_away = _cards_in(blocks[0])
    adv_away = _cards_in(blocks[2])
    assert len(box_away) == 4, (
        f"Box score should draw one quarterback and three rushers — the fixture has one QB, so "
        f"the second slot is reserved rather than drawn — got {len(box_away)} cards")
    assert len(adv_away) == 7, (
        f"Advanced should draw the same four plus three receivers, got {len(adv_away)}")
    assert _plain(blocks[0]).count("No second quarterback played") == 1, (
        f"the missing second quarterback is not reserved: {_plain(blocks[0])[:200]}")
    text = _plain("".join(adv_away))
    # ⚠️ ORDERED BY A TOKEN THAT SURVIVES A RENAME, NOT BY THE RENDERED NAME — R-758, and
    # B106's own name break is what exposed it: `text.index("QB, Away")` raised
    # `ValueError: substring not found` when the card went back to `First Last`, so this test
    # CRASHED instead of failing and proved only that the lookup was narrow. `Comp-Att` is the
    # quarterback's own KPI label and `RB1` is a whole token of the rusher's name either way.
    # ⚠️ ORDERED BY A TOKEN THAT SURVIVES A RENAME, NOT BY THE RENDERED NAME — R-758, and
    # B106's own name break is what exposed it: `text.index("QB, Away")` raised
    # `ValueError: substring not found` when the card's name shape changed, so the test CRASHED
    # instead of failing and proved only that the lookup was narrow.
    # ✅ AND THE ORDER IS THE ROUND'S OWN CLAIM (R-809): the quarterback, then who ran it, then
    # who caught it — the way a reader reads a game.
    assert text.index("Comp-Att") < text.index("RB1") < text.index("WR1"), \
        f"the cast is not QB, then rushers, then receivers: {text[:200]}"
    for who in ("RB1", "RB2", "RB3", "WR1", "WR2", "WR3"):
        assert who in text, f"{who} did not render"
    # ⚠️ v08 TOOK THE DEPTH BACK TO THREE (R-848), superseding R-840's *keep 2 and 2* on Marc's
    # own word. The fixture holds exactly three of each, so a depth ABOVE three would need a
    # deeper fixture to catch — what this pins is that none of the three is being dropped.


def test_a_SHORT_ROW_is_drawn_SHORT_and_reserves_no_hole(panel):
    """⚠️ AC-G.11. A120 measured a third rusher missing 6.6% of the time — 31 team-games in
    2026 have exactly two. A missing card is not an empty card, and an empty card is not an em
    dash: the column simply ends."""
    run, _ = panel
    # ⚠️ THE FIXTURE MUST DROP A RUSHER THE PAGE WOULD OTHERWISE DRAW. At a depth of 2 the third
    # rusher is not drawn anyway, so removing rank 3 would change nothing and this test would
    # assert against a row the page never asked for — the R-760 shape, an assertion nothing can
    # fail. Rank 2 is the one in the drawn set.
    # 🚨 AND IT MUST DROP RANKS 2 AND 3, NOT JUST ONE. `[:wanted]` takes the first TWO of
    # whatever survives, so removing rank 2 alone leaves ranks 1 and 3 and the page still draws
    # two rushers — the test would assert a short row against a full one and pass for the wrong
    # reason.
    rows = [r for r in _post_game_leaders()
            if not (r["panel"] == "rushing" and r["leader_rank"] in (2, 3))]
    blocks = _card_blocks(run(_both(), leaders=rows)[0])
    adv_away = _cards_in(blocks[2])
    assert len(adv_away) == 5, (
        f"a one-rusher side should draw five cards in Advanced — QB, one rusher, three "
        f"receivers — got {len(adv_away)}")
    text = _plain("".join(adv_away))
    assert "RB2" not in text
    # ⚠️ AND THE RECEIVERS ARE UNAFFECTED, which is the half a count alone cannot see: a short
    # RUSHING row must not shorten the RECEIVING one.
    assert "WR1" in text and "WR2" in text, "a missing rusher took a receiver with it"
    # 🚨 AND THE SHORT GROUP IS **NOT** RESERVED — R-849 is scoped to the quarterbacks. Rushing
    # and receiving are the last groups in their column, so a short one misaligns nothing
    # beneath it and a reserved slot there would be a hole bought for no alignment.
    assert "rusher played" not in _plain(blocks[2]), (
        "a short rushing group reserved a slot — R-849 is quarterback-only")


def test_the_cards_read_the_IN_THIS_GAME_view_and_never_the_preview_one(panel):
    """🚨 THE DEFECT THE WHOLE ROUND IS EXPOSED TO, AND A PRESENCE ASSERTION CANNOT SEE IT.

    `..._through_prior_week` is what a player brought INTO the game; `..._in_this_game` is what
    he did IN it. ⚠️ Point the cards at the wrong one and you get real players, plausible
    numbers and three filled slots — A102 spent a whole round on a pair this similar, and A120
    staged the model-side twin (53,872 of 53,873 rows red).

    ✅ So the SQL is asserted by name, and the slot values are asserted against the frame this
    fixture answers that view with — a card showing the other window's numbers fails here.
    """
    run, matchup = panel
    entries, seen = run(_both())
    assert "srv_game_team_leader_in_this_game" in seen, (
        f"the cards did not read the post-game view at all: {seen}")
    assert "srv_game_team_leader_through_prior_week" not in seen, (
        f"the post-game cards read the PREVIEW window — real players, plausible numbers, wrong "
        f"game: {seen}")
    # The fixture's QB carries Comp-Att 18-29 and 101 yards; the preview view would not.
    away = _plain("".join(_cards_in(_card_blocks(entries)[0])))
    assert "18-29" in away and "101" in away, (
        f"the QB card's slots are not this game's figures: {away[:160]}")
    source = matchup.__dict__["_POST_GAME_LEADER_COLUMNS"]
    assert "stat_1_label" in source and "jersey" in source


def test_a_player_with_NO_JERSEY_keeps_his_slot(panel):
    """AC-G.32, and A120 found a real one. 2,335 rows on the view carry no jersey; the card
    renders an em dash in the same place rather than shifting the row."""
    run, _ = panel
    rows = [dict(r, jersey=None) if r["leader_rank"] == 1 else r
            for r in _post_game_leaders()]
    away = _plain("".join(_cards_in(_card_blocks(run(_both(), leaders=rows)[0])[0])))
    assert "—" in away, "a missing jersey must render an em dash in the same slot"
    assert "#0" not in away and "#nan" not in away.lower()


def test_NO_leaders_at_all_says_so_rather_than_drawing_an_empty_column(panel):
    """AC-G.11 again: an absent cast is a sentence, not a blank gutter."""
    run, _ = panel
    entries, _ = run(_both(), leaders=[])
    text = _text(entries)
    assert "No player leaders held for this side." in text
    assert not _card_blocks(entries), "an empty cast still drew card markup"


# --- R-807: the measure is a cell, centred, with right-aligned values -------------------------

def _module_constant(name):
    """One of matchup.py's module-level constants, by AST, without importing the page.

    ⚠️ `ast.literal_eval` ONLY — so a constant computed from others is deliberately NOT
    readable here, and the test below recomputes the total from its parts instead. That is the
    point rather than a limitation: a test that read the page's own arithmetic back would
    agree with any arithmetic the page happened to contain.
    """
    import ast
    for node in ast.parse(SOURCE).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"matchup.py has no module-level {name}")


def _cells(entries):
    """Every metric cell rendered, as markup, by its own attribute.

    🚨 SPLIT ON THE MARKER, NOT ON `</div>`, SINCE R-808. The cell used to be a flat row and a
    non-greedy match to the first close tag captured all of it. It now NESTS — a row div, and
    under it a band div holding two svgs — so that match stops at the row's close and silently
    drops the band. **A helper that returns most of the thing it names is how an assertion
    passes over the half that changed.**
    """
    out = []
    for _kind, body in entries:
        pieces = str(body).split("<div data-cfdb='metric-cell'")
        out.extend("<div data-cfdb='metric-cell'" + piece for piece in pieces[1:])
    return out


def _resolved(style: str) -> dict:
    """An inline style as the browser resolves it — LAST DECLARATION WINS.

    🚨 THIS EXISTS BECAUSE A STAGED BREAK CAME BACK GREEN (R-744). B106 appended
    `;text-align:left` to the home figure's style and the assertion `"text-align:right" in
    style` still passed — the right-align was there, and overridden, and the test could not
    tell the difference. **A test that reads a declaration's PRESENCE cannot see an override;
    only its resolved VALUE can.**
    """
    out = {}
    for part in style.split(";"):
        if ":" in part:
            key, _, value = part.partition(":")
            out[key.strip()] = value.strip()
    return out


def _spans(cell: str) -> list:
    """The three spans of a measure ROW — name, away figure, home figure — resolved.

    ⚠️ SCOPED TO THE ROW SINCE R-847. The band beneath it carries its own spans (a spacer the
    width of the name column, then one per side), so a cell-wide sweep returns six and the
    unpack fails — or worse, succeeds against the wrong three.
    """
    row = cell.split("</div>", 1)[0]
    return [_resolved(m) for m in re.findall(r"<span style='([^']*)'>", row)]


# --- R-808: the band under each measure ----------------------------------------------------

def _bands(cell):
    """The distribution svgs inside one metric cell — one per side."""
    return re.findall(r"<svg[^>]*viewBox='0 0 (\d+) (\d+)'", cell)


def _band_labels(cell):
    """Every label drawn inside this cell's bands, in document order."""
    return re.findall(r"<text[^>]*>([^<]*)</text>", cell)


def test_EVERY_MEASURE_WITH_A_DISTRIBUTION_gets_a_band_and_the_others_do_not(panel):
    """🚨 R-808. Marc, v07: *"use it to show the spread/dispersion of EACH metric in the Box
    Score and Advanced"* — and R-816, in two words, *"R-816, both"*, with the height cost in
    front of him.

    ⚠️ SO THE ASSERTION IS COVERAGE, NOT PRESENCE: every row the view publishes a distribution
    for carries a band, and the five that are NOT scalars — third down `6/14`, turnovers
    `1 (1 INT · 0 FUM)`, possession `30:51` — carry none.

    🚨 AND THAT SECOND HALF IS AC-G.11 RATHER THAN AN OVERSIGHT. `box()`'s placeholder says
    *"cfdb holds no distribution for this week yet"*, which is true of a measure that could have
    one and FALSE of a fraction. **A band promising a percentile for `6/14` names the wrong
    absence.**
    """
    run, _ = panel
    entries = run(_both())[0]
    banded, bare = [], []
    for cell in _cells(entries):
        # ⚠️ THE MEASURE NAME IS THE ROW'S FIRST SPAN SINCE R-847 — it used to sit between the
        # two figures in the centred cell, so a pattern keyed on the label's own font size is
        # what survives the move rather than a positional one.
        label = re.search(r"_TABLE_LABEL|opacity:.75;font-size:.85rem[^']*'>"
                          r"(?:<span[^>]*>)?([^<]+)", cell)
        name = label.group(1).strip() if label else "?"
        (banded if _bands(cell) else bare).append(name)
    for measure in ("First downs", "Total yards", "Rushing yards", "Passing yards",
                    "Rushing attempts", "Penalty yards"):
        assert measure in banded, f"{measure!r} has a distribution and drew no band: {banded}"
    for composite in ("Third down", "Fourth down", "Turnovers", "Possession", "Penalties"):
        assert composite not in banded, (
            f"{composite!r} is not a scalar — there is nothing to take a percentile of — and it "
            f"drew a band anyway")


def test_the_BOX_SCORE_band_labels_carry_no_false_decimals(panel):
    """R-829. Every Box Score measure is an integer count — first downs, yards, attempts — and
    `box()`'s default `dp=1` labels them `22.0`, `5.0`, `38.0`: precision the measure does not
    have. ⚠️ Measured: `dp` changes no label COUNT at these widths, so this costs nothing."""
    run, _ = panel
    for cell in _cells(run(_both())[0]):
        if ">First downs<" not in cell:
            continue
        labels = _band_labels(cell)
        assert labels, "the first-downs band drew no labels"
        assert not any("." in text for text in labels), (
            f"a count's band is labelled with decimals it does not have: {labels}")
        return
    raise AssertionError("the first-downs row never rendered")


def test_the_band_draws_the_WHISKERS_and_not_the_MIN_MAX_it_could_have(panel):
    """🚨 BOTH PAIRS ARE PUBLISHED AND THEY ARE DIFFERENT NUMBERS, WHICH IS THE WHOLE EXPOSURE.
    `srv_game_team_metric_distribution` carries `whisker_low`/`whisker_high` AND
    `min_value`/`max_value`. Marc's v07 said *"measure the min/max"*; his v06 said *"label
    upper/lower boundaries"*. A band drawn from the extremes and labelled as the fences is a
    picture describing a wider spread than its own labels claim — **every number real, the box
    still drawn, and nothing crashing.**

    ✅ SO THE ASSERTION IS THE DRAWN EXTENT AGAINST THE COLUMN THE LABEL NAMES. On 2026 week 1
    rushing yards the fences run 2 → **365** and the extremes 2 → **569**; on first downs the
    fences are **5** → 38 and the extremes **4** → 38. Either swap changes a printed label.

    ⚠️ AND IT INVOKES THE PAGE RATHER THAN REPRODUCING IT (R-768): `run()` calls the real
    `_post_game`, and these are the labels `box()` actually emitted.

    ⚠️ WHY THE FENCES ARE THE RIGHT ANSWER, measured rather than asserted: on that rushing-yards
    row the box spans 35% of the fence range and 22% of the min-max range. Drawing the extremes
    compresses the box toward a line, which is what `outlier_count` is published separately to
    avoid.
    """
    run, _ = panel
    for cell in _cells(run(_both())[0]):
        if ">Rushing yards<" not in cell:
            continue
        labels = _band_labels(cell)
        assert "365" in labels, (
            f"the band's upper end is not `whisker_high` (365) — if it reads 569 it is drawing "
            f"`max_value` while the plot claims to be a box-and-whisker: {labels}")
        assert "569" not in labels, (
            f"the band is drawn to `max_value` (569), which is 56% wider than the fence it is "
            f"labelled as, and it squeezes the box from 35% of the frame to 22%: {labels}")
        break
    else:
        raise AssertionError("the rushing-yards row never rendered")
    for cell in _cells(run(_both())[0]):
        if ">First downs<" not in cell:
            continue
        labels = _band_labels(cell)
        assert "5" in labels and "4" not in labels, (
            f"the band's lower end is not `whisker_low` (5) — `min_value` is 4: {labels}")
        return
    raise AssertionError("the first-downs row never rendered")


# --- R-847: the table's own geometry, amended from B106/B108 rather than deleted ------------

def test_the_MEASURE_NAME_comes_FIRST_and_both_figures_are_RIGHT_aligned(panel):
    """🚨 AMENDED FROM B108's `test_BOTH_figures_are_RIGHT_aligned_and_not_only_the_away_one`.
    The requirement did not change; the geometry it asserts against did.

    Marc, v08: *"move the measure name to the left, then 2 columns for the metric values."*

    ⚠️ RIGHT-ALIGNMENT SURVIVES THE MOVE AND IT WAS NEVER ABOUT CENTRING. The home column used
    to be left-aligned, so a column of figures lined up on its FIRST digit — `9` and `415`
    starting in the same place. Right-aligned they line up on the units, which is the only
    alignment that lets a reader compare a column of numbers by eye, wherever the column sits.

    ⚠️ AND THE ORDER IS ASSERTED, NOT JUST THE ALIGNMENT — B082 and B083 both proved a presence
    assertion cannot see a left/right swap.
    """
    run, _ = panel
    cells = _cells(run(_both())[0])
    assert cells, "no measure row rendered at all"
    for cell in cells:
        label, away, home = _spans(cell)
        assert label.get("text-align") is None, (
            f"the measure name is right- or centre-aligned — v08 puts it LEFT: {label}")
        assert away.get("text-align") == "right", (
            f"the away figure resolves to text-align:{away.get('text-align')}")
        assert home.get("text-align") == "right", (
            f"the HOME figure resolves to text-align:{home.get('text-align')} — its column "
            f"lines up on the first digit instead of the units")
        # 🚨 THE NAME IS FIRST IN DOCUMENT ORDER, which is what "to the left" means and what a
        # swap would change. `_spans` returns them in source order.
        assert label.get("width") == f"{_module_constant('_TABLE_LABEL_WIDTH')}rem", (
            f"the first span is not the measure-name column: {label}")


def test_the_TABLE_ROW_CLIPS_rather_than_drawing_over_the_cards_beside_it(panel):
    """🚨 AMENDED FROM B108. R-755's mechanism is unchanged and only its NEIGHBOUR moved: the
    table used to sit between the two card columns, and now it is hard left with both card
    columns to its right. **A Streamlit column still does not clip its children, so a row wider
    than its share draws over the AWAY CARDS.**"""
    run, _ = panel
    label_w = _module_constant("_TABLE_LABEL_WIDTH")
    value_w = _module_constant("_TABLE_VALUE_WIDTH")
    for cell in _cells(run(_both())[0]):
        style = _resolved(cell.split("style='")[1].split("'")[0])
        assert style.get("overflow") == "hidden", f"a measure row does not clip: {style}"
        assert style.get("box-sizing") == "border-box", (
            "without border-box the padding is ADDED to the width and the row grows past its "
            "column")
        # ⚠️ NO PART OF THE ROW IS PROPORTIONAL — scoped to the row itself, because the band
        # beneath it legitimately sizes its own spacer to the label column.
        row_only = cell.split("</div>", 1)[0]
        assert "flex:1" not in row_only, (
            f"something in the measure row is proportional again: {row_only[:200]}")
        label, away, home = _spans(cell)
        for part, wanted, what in ((label, label_w, "measure name"),
                                   (away, value_w, "away figure"),
                                   (home, value_w, "home figure")):
            assert part.get("flex") == "none", f"the {what} can grow or shrink"
            assert part.get("width") == f"{wanted}rem", (
                f"the {what} is {part.get('width')} rather than the {wanted}rem the table "
                f"budgets for it")


def test_the_TABLE_HEADER_carries_the_section_name_and_BOTH_logos_in_order(panel):
    """🚨 AMENDED FROM B108's `test_the_SIDE_HEADING_takes_the_cells_width_and_not_the_columns`.
    The heading is a TABLE HEADER ROW now — Marc, v08: *"One big table, with a header row for
    Box Score / Logo Away / Logo Home"*.

    ⚠️ AND IT TAKES THE TABLE'S OWN COLUMN WIDTHS OR IT STOPS BEING A HEADER: a header whose
    cells do not line up with the rows beneath it is a caption.
    """
    run, _ = panel
    entries = run(_both())[0]
    # ⚠️ THE SUBHEADER ALSO SAYS "Box score", so the header ROW is found by its own markup
    # rather than by its text — the first markdown that carries a rule under it.
    header = next(str(b) for _k, b in entries
                  if "Box score" in _plain(str(b)) and "border-top" in str(b))
    assert f"width:{_module_constant('_TABLE_LABEL_WIDTH')}rem" in header, (
        "the header's first cell is not the measure-name column's width")
    assert f"width:{_module_constant('_TABLE_VALUE_WIDTH')}rem" in header, (
        "the header's figure cells are not the value columns' width")
    # 🚨 AWAY BEFORE HOME, BY THE TEAMS' OWN NAMES (R-522). `_both()` is Auburn at HOME and
    # Kentucky AWAY, so a swap changes which name comes first — which is the thing B082 and
    # B083 both proved a presence assertion cannot see.
    plain = _plain(header)
    assert plain.index("Kentucky") < plain.index("Auburn"), (
        f"the header's two teams are not in away-then-home order — Kentucky is the away side: "
        f"{plain[:160]}")
    # Marc: *"a horizontal line between the header row and the metrics row"*.
    assert "border-top" in header, "there is no rule under the header row"


def test_the_band_is_given_the_VALUE_COLUMNS_width_and_never_box_s_240px_default(panel):
    """🚨 AMENDED FROM B108. `box()`'s default is still not this panel's width; what changed is
    which width that is. The band sits directly under its own figure now, so it IS the value
    column — B108's two half-cells are gone with the centred cell.

    ⚠️ AND THE NUMBER GOT SMALLER, WHICH THE REPORT CARRIES RATHER THAN THIS TEST HIDING: B108
    measured the minimum useful plot width at 200px and shipped 216px (Box Score) and 148px
    (Advanced). v08's value column is narrower than either. **That is a consequence of the shape
    Marc asked for, not a choice — the floor assertion below is deliberately the wide one that
    says when the picture stops carrying its numbers at all.**
    """
    run, _ = panel
    widths = {int(w) for cell in _cells(run(_both())[0]) for w, _h in _bands(cell)}
    assert widths, "no band was drawn at all"
    assert 240 not in widths, (
        f"a band is 240px — that is `box()`'s own default, so the width was not passed: "
        f"{sorted(widths)}")
    wanted = int(_module_constant("_TABLE_VALUE_WIDTH") * 16)
    assert widths == {wanted}, (
        f"the bands are {sorted(widths)}px; the value column they sit under is {wanted}px")
    assert min(widths) >= 110, (
        f"a band is {min(widths)}px wide. Below ~110px `box()`'s placement pass has dropped "
        f"most of its labels and the picture stops carrying the numbers it exists to carry")


def test_the_TABLE_is_the_LEFTMOST_block_and_the_cards_follow_it(panel):
    """🚨 R-847. Marc, v08: *"Move the Box Score and Advanced tables all the way to the left.
    Move the Away Player Cards to be next (left) of the Home Player cards."*

    ⚠️ THE ORDER, NOT THE PRESENCE — B082 and B083 both proved a presence assertion cannot see a
    left/right swap, and all three blocks are present in every arrangement. **The old layout put
    the table BETWEEN the two card columns and every block was on the page then too.**

    ✅ AND IT IS READABLE BECAUSE ONE LIST DECIDES BOTH THE ORDER AND THE WIDTH (B098's pattern):
    `st.columns` hands its columns back left to right, so zipping them against `_POST_GAME_LAYOUT`
    makes the visual position and the width the same fact. A round that moved the table back to
    the middle would have to move its width with it.
    """
    layout = _module_constant("_POST_GAME_LAYOUT")
    slots = [slot for slot, _w in layout]
    assert slots == ["table", "away", "home"], (
        f"the blocks are laid out {slots} — v08 is the table hard left, then away, then home")
    widths = dict(layout)
    # 🚨 THE TABLE IS THE WIDE ONE, AND IT IS PINNED TO THE SLOT RATHER THAN TO THE INDEX. If
    # the weights were keyed by position, moving the table would hand it a card's width while
    # every positional assertion still passed — which is exactly what B098 found on this page.
    assert widths["table"] > widths["away"] * 2, (
        f"the table is not the wide block: {widths}")
    assert widths["away"] == widths["home"], (
        f"the two card columns are different widths, so the cards cannot line up row for row: "
        f"{widths}")


def test_a_ONE_QUARTERBACK_side_RESERVES_the_second_slot_and_SAYS_SO(panel):
    """🚨 R-849, AND IT REVERSES AC-G.11's USUAL ANSWER ON THIS PAGE. B107 ships
    `test_a_SHORT_ROW_is_drawn_SHORT_and_reserves_no_hole` and it is still right for rushing and
    receiving; this is the narrow case where the opposite is true, and the reason is R-847.

    **While the cards FLANKED the table a short away column had nothing to line up against.
    Side by side, an unmatched quarterback slot puts every row below it out of register between
    the two teams.** ✅ Marc asked for the reserved slot and Cowork's ruling keeps both rules: a
    reserved slot is not a hole IF IT SAYS IT IS RESERVED.

    📊 AND IT EARNS ITS KEEP — measured before it was built: **3,990 of 6,736 team-games (59.2%)
    have exactly one quarterback, and 1,812 of 3,520 games (51.5%) have the two sides carrying
    DIFFERENT counts.** More than half of all games are this case.

    🚨 A COUNT CANNOT SEE THIS BREAK. Removing the reserved slot leaves the same number of DRAWN
    cards — what changes is whether the two columns' rows line up. **So the assertion is the
    reserved card's own text, which is a value that moves.**
    """
    run, _ = panel
    # The fixture's away side has ONE quarterback; give the home side a second.
    rows = list(_post_game_leaders())
    second = dict(next(r for r in rows if r["panel"] == "total" and r["team_id"] == 2),
                  leader_rank=2, player_name="Home QB2", player_id="p2to2")
    blocks = _card_blocks(run(_both(), leaders=rows + [second])[0])
    box_away, box_home = _plain(blocks[0]), _plain(blocks[1])
    assert "No second quarterback played" in box_away, (
        f"the away side has one quarterback and reserved nothing — every row below it is now "
        f"out of register with the home column: {box_away[:200]}")
    assert "Home QB2" in box_home, "the fixture's second home quarterback did not render"
    assert "No second quarterback played" not in box_home, (
        "the home side has two quarterbacks and still reserved a slot")
    # 🚨 AND THE RESERVED SLOT IS A DRAWN BOX, NOT A GAP. An empty box a reader cannot
    # distinguish from missing data is the hole AC-G.11 forbids; this one names itself.
    assert "border:1px dashed" in blocks[0], (
        "the reserved slot draws no box at all, so the column just ends short")
    # 🚨 AND IT IS A REAL CARD'S HEIGHT, WHICH THE FIRST VERSION WAS NOT. A `min-height:3.2rem`
    # slot measured 51px against a real card's 84px, so reserving kept the two columns' card
    # COUNTS in step and left their group headers **33px out of register** — the exact
    # misalignment this feature exists to remove, one level down. **Only the raster showed it:
    # every card was present and every count was right.**
    # ⚠️ Nothing here can read a pixel, so the constant is pinned against the measurement and
    # B109's raster is the evidence — this is the guard that stops a later round shrinking it.
    reserved_h = _module_constant("_RESERVED_CARD_HEIGHT")
    assert reserved_h * 16 == 84, (
        f"the reserved slot is {reserved_h * 16:.0f}px and a real card measured 84px at 1300px "
        f"with the sidebar open. Any difference puts every group below it out of register "
        f"between the two columns, which is the whole point of the slot")
    assert f"height:{reserved_h}rem" in blocks[0], (
        "the reserved slot does not declare a fixed height, so it collapses to its text")


def test_the_RESERVED_SLOT_does_not_replace_the_HONEST_ABSENCE_for_a_side_we_hold_nothing_for(panel):
    """🚨 THE REGRESSION R-849 ALMOST CAUSED, CAUGHT BY ITS OWN RENDER. Reserving the second
    quarterback unconditionally meant a side with NO leaders at all drew two blank cards instead
    of saying we hold nothing for it.

    ⚠️ THOSE ARE DIFFERENT ABSENCES (AC-G.11) AND THE RESERVED CARD ANSWERS THE WRONG ONE: *no
    second quarterback played* is a statement about one player; *we hold no leaders for this
    side* is a statement about the side. **The sentence wins whenever every group is empty.**
    """
    run, _ = panel
    # ⚠️ TEAM 2 IS THE HOME SIDE in `_side()`, so keeping only its rows leaves the AWAY column
    # with nothing at all — which is the case under test.
    rows = [r for r in _post_game_leaders() if r["team_id"] == 2]
    entries = run(_both(), leaders=rows)[0]
    # ⚠️ NOT `_card_blocks` — that helper keeps only blocks containing CARD markup, and the
    # whole point here is that the away column contains none. The sentence would be filtered
    # out by the very helper used to look for it.
    text = _text(entries)
    assert "No player leaders held for this side." in text, (
        f"a side we hold nothing for drew reserved slots instead of saying so: {text[:300]}")
    # And the home side, which does have leaders, still reserves its missing second quarterback.
    home = _plain(_card_blocks(entries)[0])
    assert "No second quarterback played" in home, (
        "the side that DOES have one quarterback stopped reserving the second")


def test_the_HEADER_ACCENT_names_BOTH_theme_variants_and_not_just_the_light_one(panel):
    """🚨 AC-G.22, AND THE RASTER CAUGHT THE OBVIOUS VERSION FAILING.

    The app's precedent is `identity.text_on(row)`, which defaults to the ON-LIGHT colour —
    `_drives` says so in its own comment, *"which is what team.py does and the only precedent in
    the app"*. **Rendered in dark mode, North Alabama's accent came out `rgb(0,0,0)` against a
    `rgb(14,17,23)` page. Invisible.**

    📊 NOT A CORNER CASE: **6,338 of 34,061 team rows — 18.6% — publish `#000000` as their
    on-light colour, and every one of them has an on-dark variant.** So the fix is available for
    100% of the teams the defect hits.

    ✅ `light-dark()` IS THIS CODEBASE'S OWN TOOL FOR IT (theme.py, R-547/R-552): it follows the
    `color-scheme` property Streamlit sets, where `prefers-color-scheme` answers the OPERATING
    SYSTEM and hands a reader on a dark Mac with the app in Light the wrong palette.

    ⚠️ ASSERTED ON BOTH VARIANTS BEING NAMED, because a single hex is exactly what shipped first
    and it renders perfectly in one of the two modes — which is how it passed the eye.
    """
    run, _ = panel
    entries = run(_both())[0]
    header = next(str(b) for _k, b in entries
                  if "Box score" in _plain(str(b)) and "border-top" in str(b))
    accents = re.findall(r"border-bottom:3px solid ([^;']+)", header)
    assert len(accents) == 2, f"expected one accent per side, got {accents}"
    for accent in accents:
        assert accent.startswith("light-dark("), (
            f"the header accent is a single colour — {accent!r} — so it is right in one theme "
            f"and wrong in the other. 18.6% of teams publish #000000 on light")
        light, dark = accent[len("light-dark("):-1].split(", ")
        assert light and dark, f"the accent names only one variant: {accent}"
    # 🚨 AND THE FALLBACK PATH IS EXERCISED BY THE FIXTURE ON PURPOSE: `_COLORS` gives the AWAY
    # side no colour at all, because 10.89% of games have one and a fixture with both sides
    # populated could not tell the sourced path from the neutral one.
    assert identity_fallback() in accents[0], (
        f"a side with no published colour did not fall back to the neutral: {accents[0]}")


def identity_fallback():
    from lib import identity
    return identity.FALLBACK
