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

        def run(sides, glossary=GLOSSARY, season=2026, leaders=None):
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
_POST_GAME_PANELS = {
    "total": (("Comp-Att", "pair"), ("Yards", "integer"), ("TD", "integer")),
    "rushing": (("Carries", "integer"), ("Yards", "integer"), ("Yds/Carry", "decimal_1")),
}


def _post_game_leaders(**overrides):
    """Both sides' post-game leaders: one QB each, three rushers each."""
    rows = []
    # ⚠️ THE SAME IDS `_side()` USES — 2 at home, 96 away. A card frame keyed on ids the box
    # score does not carry would render no cards at all while every table assertion passed.
    for team_id, who in ((2, "Home"), (96, "Away")):
        for panel, names in (("total", [f"{who} QB"]),
                             ("rushing", [f"{who} RB1", f"{who} RB2", f"{who} RB3"])):
            (l1, f1), (l2, f2), (l3, f3) = _POST_GAME_PANELS[panel]
            for rank, name in enumerate(names, start=1):
                rows.append({
                    "team_id": team_id, "panel": panel, "leader_rank": rank,
                    "tied_players": 1, "qualified_players": len(names),
                    "player_id": f"p{team_id}{panel[:2]}{rank}", "player_name": name,
                    "player_slug": name.lower().replace(" ", "-"),
                    "jersey": 10 + rank, "position": "QB" if panel == "total" else "RB",
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
    assert seen == ["srv_game_team", "srv_game_team_leader_in_this_game",
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
    for _kind, body in entries:
        for cell in re.findall(r"<div data-cfdb='metric-cell'.*?</div>", str(body)):
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


def test_the_cards_flank_BOTH_panels_and_the_cast_does_not_change(panel):
    """Marc named ONE card list against TWO panels — Box score and Advanced.

    ✅ COWORK'S LEAN, BUILT AND KEPT: the same QB and rushers beside both, because they are the
    same game's leaders and a reader scrolling from one panel to the other should not find the
    cast has changed under him.
    """
    run, _ = panel
    blocks = _card_blocks(run(_both())[0])
    assert len(blocks) == 4, (
        f"expected two card columns per panel across two panels, got {len(blocks)}")
    assert blocks[0] == blocks[2] and blocks[1] == blocks[3], \
        "the cast changed between the box score and the advanced block"


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
    assert "QB, Away" in away and "QB, Home" not in away, \
        f"the first card column is not the AWAY side: {away[:120]}"
    assert "QB, Home" in home and "QB, Away" not in home, \
        f"the second card column is not the HOME side: {home[:120]}"


def test_ONE_quarterback_and_THREE_rushers(panel):
    """🚨 A120 MEASURED WHY IT IS NOT THREE OF EACH: of 6,736 `total` groups, 6,300 — 93.5% —
    have fewer than three leaders and 3,990 have exactly one. A team plays one quarterback, and
    Marc's own wording says so — *"Include QA, Top 3 Rusher"*: QB singular, three rushers."""
    run, _ = panel
    away = _cards_in(_card_blocks(run(_both())[0])[0])
    assert len(away) == 4, f"expected one QB and three rushers, got {len(away)} cards"
    text = _plain("".join(away))
    # ⚠️ ORDERED BY A TOKEN THAT SURVIVES A RENAME, NOT BY THE RENDERED NAME — R-758, and
    # B106's own name break is what exposed it: `text.index("QB, Away")` raised
    # `ValueError: substring not found` when the card went back to `First Last`, so this test
    # CRASHED instead of failing and proved only that the lookup was narrow. `Comp-Att` is the
    # quarterback's own KPI label and `RB1` is a whole token of the rusher's name either way.
    assert text.index("Comp-Att") < text.index("RB1"), \
        "the quarterback must lead the column"
    for rb in ("RB1", "RB2", "RB3"):
        assert rb in text, f"{rb} did not render"


def test_a_SHORT_ROW_is_drawn_SHORT_and_reserves_no_hole(panel):
    """⚠️ AC-G.11. A120 measured a third rusher missing 6.6% of the time — 31 team-games in
    2026 have exactly two. A missing card is not an empty card, and an empty card is not an em
    dash: the column simply ends."""
    run, _ = panel
    rows = [r for r in _post_game_leaders()
            if not (r["panel"] == "rushing" and r["leader_rank"] == 3)]
    away = _cards_in(_card_blocks(run(_both(), leaders=rows)[0])[0])
    assert len(away) == 3, f"a two-rusher side should draw three cards, got {len(away)}"
    text = _plain("".join(away))
    assert "RB3" not in text
    assert "—" not in text, "an absent third rusher reserved a hole"


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
    """Every metric cell rendered, as markup, by its own attribute."""
    return [c for _k, b in entries
            for c in re.findall(r"<div data-cfdb='metric-cell'.*?</div>", str(b))]


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
    """The three spans of a metric cell, each as a resolved style dict."""
    return [_resolved(m) for m in re.findall(r"<span style='([^']*)'>", cell)]


def test_the_metric_cell_FITS_the_middle_column_at_1300px_with_the_sidebar_open():
    """🚨 R-807's FLOOR AND CEILING, PINNED THE WAY B103 PINNED `_SLOT_WIDTHS` — because nothing
    in this suite can read a pixel, so the raster is the evidence and this test exists to stop a
    later round widening the cell blind.

    ⚠️ THE NUMBERS ARE MEASURED, IN THE BROWSER, NOT DERIVED:

        `_POST_GAME_SPLIT`'s middle column      493px at 1300px with the sidebar open
                                                733px at 1700px
        "Havoc rate forced by this defense"     188px at .85rem, the page's own font
        "12 (4 INT · 8 FUM)"                    118px at 1rem/600 — the widest figure either
                                                panel can produce

    🚨 AND THE CEILING IS THE ONE THAT MATTERS, BECAUSE B104 PAID FOR IT: a Streamlit column
    does NOT clip its children, so a cell wider than 493px does not compress — it DRAWS OVER
    the card column beside it, which is how `+214.0` landed on top of the home side's
    `Rushing`.
    """
    value = _module_constant("_METRIC_VALUE_WIDTH")
    label = _module_constant("_METRIC_LABEL_WIDTH")
    gap = _module_constant("_METRIC_CELL_GAP")
    pad = _module_constant("_METRIC_CELL_PAD")
    total_px = (2 * value + label + 2 * gap + 2 * pad) * 16
    assert total_px <= 493, (
        f"the cell is {total_px:.0f}px against a 493px middle column at 1300px with the "
        f"sidebar open — it will draw OVER the card column beside it, not compress")
    assert total_px >= 420, (
        f"the cell is {total_px:.0f}px, and the content it must hold is 188px of label plus "
        f"two 118px figures plus gaps — tightening it below that clips a real label")
    assert label * 16 >= 188, (
        f"the label column is {label * 16:.0f}px and the longest label in _ADVANCED_ROWS "
        f"measures 188px — 'Havoc rate forced by this defense' would be truncated")
    assert value * 16 >= 118, (
        f"the value column is {value * 16:.0f}px and a two-digit turnover line, "
        f"'12 (4 INT · 8 FUM)', measures 118px")


def test_BOTH_figures_are_RIGHT_aligned_and_not_only_the_away_one(panel):
    """Marc, v06: *"Right align the metric value."*

    🚨 A TEST THAT COUNTED `text-align:right` ONCE WOULD HAVE PASSED BEFORE THIS ROUND — the
    away figure has been right-aligned since B076 and the HOME one was left-aligned, so a
    column of figures lined up on its FIRST digit: `9` and `415` started in the same place.
    ✅ So the assertion is on BOTH, per cell, by position.
    """
    run, _ = panel
    cells = _cells(run(_both())[0])
    assert cells, "no metric cell rendered at all"
    for cell in cells:
        away, label, home = _spans(cell)
        assert away.get("text-align") == "right", (
            f"the away figure resolves to text-align:{away.get('text-align')}")
        assert home.get("text-align") == "right", (
            f"the HOME figure resolves to text-align:{home.get('text-align')} — its column "
            f"lines up on the first digit instead of the units, which is the comparison the "
            f"panel exists to make")
        assert label.get("text-align") == "center", (
            f"the label resolves to text-align:{label.get('text-align')}")


def test_the_cell_CLIPS_rather_than_drawing_over_the_column_beside_it(panel):
    """🚨 R-755's LESSON, AND IT IS THE ONE THING THAT MAKES A FIXED WIDTH SAFE HERE. Without
    `overflow:hidden` a cell that cannot have its width corrupts the card column beside it; with
    it, it loses its rightmost characters inside its own column. A page that clips reads as
    tight, a page that overlaps reads as broken."""
    run, _ = panel
    value = _module_constant("_METRIC_VALUE_WIDTH")
    label_w = _module_constant("_METRIC_LABEL_WIDTH")
    for cell in _cells(run(_both())[0]):
        style = _resolved(cell.split("style='")[1].split("'")[0])
        assert style.get("overflow") == "hidden", f"a metric cell does not clip: {style}"
        assert style.get("margin") == "0 auto", "a metric cell is not centred in its column"
        assert style.get("box-sizing") == "border-box", (
            "without border-box the .4rem padding is ADDED to the width and the 32px of "
            "headroom against the 493px column becomes 19px")
        # 🚨 EVERY PART OF THE CELL IS FIXED, AND THIS IS ASSERTED ON THE CHILDREN TOO — the
        # staged break put `flex:1` back on the LABEL, not on the cell, and an assertion that
        # only read the cell's own style came back green (R-744). R-807 exists because a
        # proportional row put the two figures 301px apart at 1300px and 541px apart at 1700px.
        assert "flex:1" not in cell, (
            f"something inside the cell is proportional again: {cell[:200]}")
        away, label, home = _spans(cell)
        for part, wanted, what in ((away, value, "away figure"),
                                   (label, label_w, "label"),
                                   (home, value, "home figure")):
            assert part.get("flex") == "none", f"the {what} can grow or shrink"
            assert part.get("width") == f"{wanted}rem", (
                f"the {what} is {part.get('width')} rather than the {wanted}rem the cell's "
                f"arithmetic budgets for it")


def test_the_SIDE_HEADING_takes_the_cells_width_and_not_the_columns(panel):
    """⚠️ A HEADING LEFT SPANNING THE FULL COLUMN STOPS BEING A HEADING. At 1700px the column is
    733px and the cell is 461px, so a full-width heading would sit 136px outboard of its own
    figures and read as a caption for something else."""
    run, _ = panel
    entries = run(_both())[0]
    heading = next(str(b) for _k, b in entries if "Kentucky" in _plain(str(b)))
    value = _module_constant("_METRIC_VALUE_WIDTH")
    label = _module_constant("_METRIC_LABEL_WIDTH")
    gap = _module_constant("_METRIC_CELL_GAP")
    pad = _module_constant("_METRIC_CELL_PAD")
    width = 2 * value + label + 2 * gap + 2 * pad
    assert f"width:{width}rem" in heading, (
        f"the side heading does not carry the cell's own {width}rem width")
    assert "margin:0 auto" in heading, "the side heading is not centred with its cell"
