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
    # 🚨 R-839/B110. A128's DEFENSIVE PANEL, IN THE SHAPE SERVING ACTUALLY PUBLISHES IT —
    # read off `srv_game_team_leader_in_this_game`, not copied from the prompt. `stat_1_format`
    # is `pair`, the same format `Comp-Att` uses, which is why it needed no new page branch.
    "defensive": (("Solo-Ast", "pair"), ("Tackles", "integer"), ("TFL", "integer")),
    # ✅ R-887. A134's TWO PANELS, IN THE SHAPE SERVING ACTUALLY PUBLISHES THEM — read off
    # `srv_game_team_leader_in_this_game`, not copied from the prompt. ⚠️ `kicking`'s slot 1 is
    # a **`pair`**, the same format `Comp-Att` and `Solo-Ast` already use, which is why neither
    # panel needed a new branch in the renderer.
    "punting": (("Yards", "integer"), ("Punts", "integer"), ("Avg", "decimal_1")),
    "kicking": (("FG", "pair"), ("Kicks", "integer"), ("Points", "integer")),
}

# 🚨 A128's NAMED ANCHOR, AND IT IS THE CASE THE SOLO COLUMN EXISTS FOR — read live from
# game 401628319, team 333: **Campbell 6 solo / 3 assisted and Lawson 3 solo / 6 assisted are
# BOTH on 9 tackles and BOTH on 1 TFL.** Two of the three columns cannot separate them; the
# first one can, and the card shows it. ⚠️ Generic 12/101/4.5 filler would have made the two
# cards differ on every slot and proved nothing about which column does the work.
_DEFENSIVE_ANCHOR = (
    # name, solo, assisted, tackles, tfl
    ("Campbell", 6.0, 3.0, 9.0, 1.0),
    ("Lawson", 3.0, 6.0, 9.0, 1.0),
    ("Hubbard", 5.0, 1.0, 6.0, 1.0),
)


def _post_game_leaders(**overrides):
    """Both sides' post-game leaders: one QB, three rushers, three receivers, three
    defenders each (R-809, and the defence in B110)."""
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
        # ✅ R-887. THE TWO SPECIAL-TEAMS PANELS, AT DEPTH 1 — and they are in the fixture
        # because WITHOUT them the group-order test asserts only the four groups the fixture
        # happens to carry. **A tuple added to the page and not to the fixture is a group no
        # test can see**, which is §6's first failure mode wearing a different hat.
        for panel, surname in (("punting", "Pace"), ("kicking", "Boot")):
            (p1, f1), (p2, f2), (p3, f3) = _POST_GAME_PANELS[panel]
            rows.append({
                "team_id": team_id, "panel": panel, "leader_rank": 1,
                "tied_players": 1, "qualified_players": 1,
                "player_id": f"p{team_id}{panel[:2]}1", "player_name": f"{who} {surname}",
                "player_slug": f"{who}-{surname}".lower(),
                "jersey": 90, "position": "K" if panel == "kicking" else "P",
                "class_year_display": "JR",
                "stat_1_label": p1, "stat_1_format": f1,
                "stat_1_value": 2.0 if f1 == "pair" else 180.0,
                "stat_1_value_secondary": 3.0 if f1 == "pair" else None,
                "stat_2_label": p2, "stat_2_format": f2,
                "stat_2_value": 4.0, "stat_2_value_secondary": None,
                "stat_3_label": p3, "stat_3_format": f3,
                "stat_3_value": 45.0 if f3 == "decimal_1" else 8.0,
                "stat_3_value_secondary": None})

        (dl1, df1), (dl2, df2), (dl3, df3) = _POST_GAME_PANELS["defensive"]
        for rank, (surname, solo, ast_, tackles, tfl) in enumerate(_DEFENSIVE_ANCHOR, start=1):
            rows.append({
                "team_id": team_id, "panel": "defensive", "leader_rank": rank,
                "tied_players": 1, "qualified_players": len(_DEFENSIVE_ANCHOR),
                "player_id": f"p{team_id}de{rank}", "player_name": f"{who} {surname}",
                "player_slug": f"{who}-{surname}".lower(),
                "jersey": 40 + rank, "position": "LB", "class_year_display": "SR",
                "stat_1_label": dl1, "stat_1_format": df1,
                "stat_1_value": solo, "stat_1_value_secondary": ast_,
                "stat_2_label": dl2, "stat_2_format": df2,
                "stat_2_value": tackles, "stat_2_value_secondary": None,
                "stat_3_label": dl3, "stat_3_format": df3,
                "stat_3_value": tfl, "stat_3_value_secondary": None})
    for row in rows:
        row.update(overrides)
    return rows


# 🚨 R-848. THE TWO TEAMS' COLOURS, as `srv_game` publishes them — the pair `row_for_side`
# renames for `identity.text_on`. ⚠️ The AWAY side deliberately carries NO colour: 10.89% of
# games have one, and a fixture where both sides are populated could not tell the fallback path
# from the sourced one.
# 🚨 R-856. THE ABBREVIATIONS RIDE ON THIS SAME ROW — `srv_game`'s own columns, and these are
# the two teams' real published values. ⚠️ THE COLOURS STAY ASYMMETRIC (away null) because that
# asymmetry is what makes the accent fallback testable; the abbreviations are BOTH present here
# so the away-then-home ordering assertions still have two distinct tokens to order. **The null
# path gets its own test, which overrides this dict rather than weakening it** — 39 of the 3,674
# games with a box score publish no away abbreviation, so the fallback is real.
_COLORS = {"away_color_on_light": None, "away_color_on_dark": None,
           "home_color_on_light": "#0021A5", "home_color_on_dark": "#4C7BEF",
           "away_abbreviation": "UK", "home_abbreviation": "AUB"}

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
    assert "AUB" in body and "UK" in body, "the two sides are not both identified"
    for figure in ("17", "16", "241", "240", "118", "79", "123", "161"):
        assert figure in body, f"{figure} is missing from the box score"


def test_away_is_on_the_left_and_home_on_the_right(panel):
    """The scoreline's convention, and the reason that layout reads as a matchup at all."""
    run, _ = panel
    blocks = [b for kind, b in run(_both())[0] if kind == "markdown"]
    # ⚠️ R-856: the header identifies the sides by ABBREVIATION now. The convention asserted
    # here — away left, home right — is unchanged and is still positional.
    heading = next(b for b in blocks if "UK" in b and "AUB" in b)
    assert heading.index("UK") < heading.index("AUB"), \
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
    # ⚠️ AMENDED FOR v11. The section HEADING is part of the table's markup and is only built
    # when the section is, so a game with no advanced block no longer prints the words
    # "Advanced Team Stats" at all — it prints the empty state, inside the table column. **The
    # claim that matters is unchanged: the absence is NAMED rather than the section vanishing.**
    assert "would be here" in body and "collected separately" in body


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
    # 🚨 REPOINTED IN B110 FROM `_leaders` TO `_post_game_leaders`, AND THE ASSERTION GOT
    # STRONGER RATHER THAN WEAKER. R-839 deleted the `Game leaders` section, so the ranked
    # read this gripped no longer exists — **but the reason it existed does.** The CARDS now
    # carry the only in-game ranking on the page, so they inherit the ban whole.
    #
    # ⚠️ AND THE NAME IS THE LONG ONE ON PURPOSE. `"srv_game_team_leader" in code` passed as a
    # PREFIX of `srv_game_team_leader_in_this_game`, so it would have gone on passing after the
    # relation it was written for was deleted — an assertion that survives its own subject.
    # A128 and `_game_leaders`'s docstring both warn that these names differ by a suffix.
    assert "srv_game_team_leader_in_this_game" in code, \
        "the cards do not read the ranked object"
    # ⚠️ ANCHORED ON THE QUERY LITERAL, NOT ON ITS FIRST COLUMN. B077 wrote
    # `block.index("select team_id")`, and B078 adding one column to the select — `season`,
    # for the player link — made that anchor vanish and this test raise ValueError instead of
    # asserting anything. The assertion is unchanged; only what it grips has moved to
    # something a column list cannot break.
    block = SOURCE[SOURCE.index("def _post_game_leaders("):SOURCE.index("def _reserved_card(")]
    sql = block.split('query(f"""')[1].split('"""')[0].lower()
    for computed in ("order by", "rank(", "row_number(", "over (", "group by", "join"):
        assert computed not in sql, f"the cards' query contains `{computed}`"


def test_the_panel_computes_nothing(panel):
    """G-3, asserted on the SQL the panel actually issued."""
    # ⚠️ END ANCHOR MOVED IN B110: `def _leader_note(` went with R-839's section. `_travel`
    # is the next panel after `_post_game` and is not going anywhere this round.
    block = SOURCE[SOURCE.index("_POSTGAME_COLUMNS = "):SOURCE.index("def _travel(")]
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

# 🚨 AN ATTRIBUTE, NOT A COLOUR — R-886. This was the literal grey border string until v11 put
# the TEAM COLOUR on the card, at which point every helper below would have matched nothing and
# a dozen assertions would have passed over an empty list. **`_row_markup`'s own comment already
# said it: the attribute exists to be anchored on; a style string is not an interface.**
_CARD_MARK = "<div data-cfdb='leader-card'"
_RESERVED_MARK = "<div data-cfdb='reserved-card'"


def _plain(markup: str) -> str:
    """Tags out, whitespace collapsed — the sentence a reader sees."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


_GROUP_RE = re.compile(r"<div style='font-size:\.66rem;font-weight:700;[^']*'>([^<]+)</div>")


def _groups(block):
    """One card column split into its NAMED groups, keyed by the header the reader sees.

    🚨 B110 NEEDED THIS BECAUSE THE TWO SECTIONS NO LONGER SHARE A PREFIX. Until this round
    Advanced was the Box score column plus receiving, so `adv.startswith(box)` was the whole
    claim. **Box score now ends in Defense and Advanced ends in Receiving**, so they agree on
    the first two groups and diverge on the third — a prefix test would fail for the right
    reason and the wrong claim. Comparing the named groups says what R-738 actually meant:
    *a reader scrolling between the panels must not find the shared cast changed.*
    """
    marks = [(m.start(), m.group(1)) for m in _GROUP_RE.finditer(block)]
    return {title: block[start:(marks[i + 1][0] if i + 1 < len(marks) else len(block))]
            for i, (start, title) in enumerate(marks)}


def _card_region(entries):
    """THE card region — one markdown block, drawn once (R-886).

    🚨 IT WAS FOUR BLOCKS AND IS NOW ONE, WHICH IS v11's WHOLE STRUCTURAL CHANGE. The cards
    were rendered beside Box score and again beside Advanced, two Streamlit columns each. Marc:
    *"the vertical breaks are independent"* — so they are drawn once, top to bottom, and a
    helper returning four is a helper describing a page that no longer exists.
    """
    blocks = [str(b) for k, b in entries
              if k == "markdown" and (_CARD_MARK in str(b) or _RESERVED_MARK in str(b))]
    assert len(blocks) <= 1, (
        f"the cards were drawn {len(blocks)} times — v11 draws them ONCE, with no vertical "
        f"association to the table beside them")
    return blocks[0] if blocks else ""


def _card_halves(region: str) -> list:
    """Every card half in DRAWN ORDER, as (side, markup) — away, home, away, home… (R-886).

    ⚠️ AWAY FIRST, AND THE SIDE IS READ FROM THE MARKUP RATHER THAN FROM ITS POSITION. B082 and
    B083 both proved a presence assertion cannot see a left/right swap; a helper that assumed
    the first half is away could not either. `data-side` is what the page states.
    """
    pieces = region.split("<div data-cfdb='card-half' data-side='")[1:]
    return [(p.split("'", 1)[0], p) for p in pieces]


def _side_cards(region: str, side: str) -> str:
    """One side's whole card column — every group's half for that side, concatenated."""
    return "".join(markup for which, markup in _card_halves(region) if which == side)


def _cards_in(block):
    """The real (non-reserved) cards inside a block, split apart."""
    return [piece for piece in block.split(_CARD_MARK)[1:]]


def _groups_in(region: str) -> list:
    """The position headings drawn over the card region, in order (R-886)."""
    return re.findall(r"text-transform:uppercase;opacity:\.8;[^>]*>([^<]+)</div>", region)


def test_the_cards_are_ONE_CONTINUOUS_COLUMN_with_every_group_drawn_ONCE(panel):
    """🚨 R-886. Marc, v11: *"Continuous, top-down, Quarterbacks (2), Rushing (3), Receiving (3),
    Defense (3) … The Player cards should flow top to bottom, with no vertical association to
    the Box/Advanced."*

    ⚠️ THIS REPLACES `test_the_cards_sit_beside_BOTH_panels_and_RECEIVING_is_added_only_in_
    ADVANCED`, AND THE CLAIM IS INVERTED RATHER THAN RELAXED. That test asserted the cards were
    drawn TWICE with a different cast each time, which was right while they flanked two panels.
    **Drawing them twice is now the defect**, and the old test would have passed a page that
    kept doing it.

    ✅ AND IT IS WHY B113 IS TWO TUPLES: the renderer loops `_CARD_GROUPS` and draws whatever is
    in it, so Punter and Placekicker need no new branch.
    """
    run, _ = panel
    region = _card_region(run(_both())[0])
    assert region, "no card region was drawn at all"
    groups = _groups_in(region)
    # ⚠️ ALL SIX SINCE R-887, AND IN MARC'S ORDER RATHER THAN ALPHABETICAL. The two
    # special-teams groups go at the END — *"Quarterbacks (2), Rushing (3), Receiving (3),
    # Defense (3), Punter (1), Placekicker (1)"* — and asserting the LIST rather than a set is
    # what makes the order part of the claim.
    assert groups == ["Quarterback", "Rushing", "Receiving", "Defense",
                      "Punter", "Placekicker"], (
        f"the card groups are {groups} — v11 asks for one continuous top-down run, in the "
        f"order Marc listed, with each group drawn exactly once")
    # 🚨 EVERY GROUP EXACTLY ONCE. A page that still drew the cards per section would repeat
    # Quarterback and Rushing, and a set comparison would not see it.
    assert len(groups) == len(set(groups)), (
        f"a group is drawn more than once — the cards are still keyed to the table's sections: "
        f"{groups}")


def test_the_AWAY_cards_are_drawn_BEFORE_the_HOME_cards(panel):
    """🚨 POSITIONAL, NOT PRESENCE. B082 proved a presence assertion passes a left/right swap on
    the game header and B083 proved it again on the win-probability bar.

    ⚠️ AND THIS PANEL IS NOT B098's MIRROR. That flanked two charts, one per side; this flanks
    ONE TABLE carrying both sides, so away goes outside-left and home outside-right — the
    away-over-home law (R-522) rather than a mirror.
    """
    run, _ = panel
    region = _card_region(run(_both())[0])
    # ⚠️ PLAIN TEXT SINCE R-753: the name is two elements — small first line, bold last line —
    # so "Away QB" no longer appears contiguously in the markup.
    # ⚠️ AND THE SIDE IS READ FROM `data-side` SINCE R-886, not from a block's position.
    halves = _card_halves(region)
    assert halves and halves[0][0] == "away", (
        f"the first card half drawn is {halves[0][0] if halves else None!r}, not away (R-522)")
    away, home = _plain(_side_cards(region, "away")), _plain(_side_cards(region, "home"))
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
    region = _card_region(run(_both())[0])
    box_away = adv_away = _plain(_side_cards(region, "away"))
    # ⚠️ WHICH SECTION EACH DISCIPLINE IS LOOKED FOR IN IS THE v08 CHANGE (R-848). Receiving
    # moved to Advanced on Marc's word; the other two stay in both. **Looking for all three in
    # the Box score column would now fail for the right reason and the wrong claim.**
    for discipline, marker, where, text in (
            ("the quarterback", "Comp-Att", "Box score", box_away),
            ("the rushers", "Carries", "Box score", box_away),
            ("the quarterback", "Comp-Att", "Advanced", adv_away),
            ("the rushers", "Carries", "Advanced", adv_away),
            ("the receivers", "Receptions", "Advanced", adv_away),
            # 🚨 R-839/B110. `Tackles` CAN ONLY COME FROM THE `defensive` PANEL, which is what
            # makes this the right assertion for the staged break rather than a card COUNT: a
            # count moves for every legitimate depth change too, and every other discipline
            # publishes a different slot-2 label. **It is also the whole reason the section
            # could be deleted — the tackle was one of two figures it alone carried.**
            ("the defence", "Tackles", "Box score", box_away)):
        assert marker in text, (
            f"{discipline} are not on the {where} cards — no {marker!r} in the away column. "
            f"Marc asked for full coverage: {text[:200]}")


def test_ONE_quarterback_slot_pair_and_THREE_of_each_other_group(panel):
    """🚨 A120 MEASURED WHY THE QB IS ALONE: of 6,736 `total` groups, 6,300 — 93.5% — have fewer
    than three leaders and 3,990 have exactly one. A team plays one quarterback.

    ⚠️ AMENDED FOR v11: the cards are ONE column now, so the counts are per GROUP across the
    whole region rather than per section. The fixture has one QB, three rushers, three
    receivers and three defenders, so the away column draws **ten real cards plus one reserved
    quarterback slot**.

    ⚠️ THE COUNT IS ASSERTED AGAINST THE MEASURED SHAPE AND NOT READ FROM `_CARD_GROUPS`, for
    the same reason the coverage test writes its set out: a test that took the page's own tuple
    as its expectation would agree with any tuple.
    """
    run, _ = panel
    region = _card_region(run(_both())[0])
    away = _side_cards(region, "away")
    # ⚠️ `_cards_in` COUNTS DRAWN CARDS ONLY — a reserved slot carries its own marker, so it is
    # deliberately not one of these. The reserved slot is asserted by its text below.
    # ⚠️ TWELVE SINCE R-887: one quarterback, three rushers, three receivers, three defenders,
    # one punter, one placekicker. **The count moved because the page gained two groups, which
    # is the change being asserted** — and the reserved quarterback slot is still not one of
    # these, because a reserved slot carries its own marker.
    assert len(_cards_in(away)) == 12, (
        f"the away column should draw one quarterback, three rushers, three receivers, three "
        f"defenders, a punter and a placekicker — got {len(_cards_in(away))} cards")
    assert _plain(away).count("No second quarterback recorded") == 1, (
        f"the missing second quarterback is not reserved: {_plain(away)[:200]}")
    text = _plain(away)
    # ⚠️ ORDERED BY A TOKEN THAT SURVIVES A RENAME, NOT BY THE RENDERED NAME — R-758, and
    # B106's own name break is what exposed it: a lookup by full name CRASHED instead of
    # failing and proved only that the lookup was narrow.
    assert text.index("Comp-Att") < text.index("RB1"), (
        f"the quarterback is not drawn above the rushers: {text[:200]}")


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
    away_cards = _cards_in(_side_cards(_card_region(run(_both(), leaders=rows)[0]), "away"))
    adv_away = away_cards
    assert len(adv_away) == 10, (
        f"a one-rusher side should draw ten cards — QB, one rusher, three receivers, three "
        f"receivers — got {len(adv_away)}")
    text = _plain("".join(adv_away))
    assert "RB2" not in text
    # ⚠️ AND THE RECEIVERS ARE UNAFFECTED, which is the half a count alone cannot see: a short
    # RUSHING row must not shorten the RECEIVING one.
    assert "WR1" in text and "WR2" in text, "a missing rusher took a receiver with it"
    # 🚨 AND THE SHORT GROUP IS **NOT** RESERVED — R-849 is scoped to the quarterbacks. Rushing
    # and receiving are the last groups in their column, so a short one misaligns nothing
    # beneath it and a reserved slot there would be a hole bought for no alignment.
    assert "rusher played" not in _plain(away_cards and "".join(away_cards)), (
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
    away = _plain("".join(_cards_in(_side_cards(_card_region(entries), "away"))))
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
    away = _plain("".join(_cards_in(
        _side_cards(_card_region(run(_both(), leaders=rows)[0]), "away"))))
    assert "—" in away, "a missing jersey must render an em dash in the same slot"
    assert "#0" not in away and "#nan" not in away.lower()


def test_NO_leaders_at_all_says_so_rather_than_drawing_an_empty_column(panel):
    """AC-G.11 again: an absent cast is a sentence, not a blank gutter."""
    run, _ = panel
    entries, _ = run(_both(), leaders=[])
    text = _text(entries)
    assert "No player leaders held for this side." in text
    assert not _cards_in(_card_region(entries)), "an empty cast still drew a real card"


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


def _expected_value_width() -> float:
    """The value cell's width in rem, recomputed from the literals (R-885)."""
    rem = _module_constant("_REM")
    budget = _module_constant("_TABLE_ROW_BUDGET")
    cells = budget - int(_module_constant("_TABLE_LABEL_WIDTH") * rem) - 3 * int(
        _module_constant("_TABLE_GAP") * rem)
    value = (cells // 3 if _module_constant("_TABLE_CELLS_EQUAL")
             else _module_constant("_TABLE_VALUE_CONTENT_PX"))
    return value / rem


def _expected_chart_width() -> int:
    """The chart's width RECOMPUTED FROM ITS PARTS, never read back off the page (R-885).

    🚨 `_TABLE_CHART_WIDTH` IS DERIVED NOW, and `_module_constant` refuses a computed constant
    on purpose: *"a test that read the page's own arithmetic back would agree with any
    arithmetic the page happened to contain."* **So the test does the arithmetic itself**, from
    the literals — the row budget, the label column, the gap, and which of Marc's two readings
    of *"equal horizontal widths"* is switched on.
    """
    rem = _module_constant("_REM")
    budget = _module_constant("_TABLE_ROW_BUDGET")
    label = int(_module_constant("_TABLE_LABEL_WIDTH") * rem)
    gap = int(_module_constant("_TABLE_GAP") * rem)
    cells = budget - label - 3 * gap
    value = (cells // 3 if _module_constant("_TABLE_CELLS_EQUAL")
             else _module_constant("_TABLE_VALUE_CONTENT_PX"))
    return cells - 2 * value


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
    """The FOUR spans of a measure ROW — name, away figure, home figure, chart — resolved.

    ⚠️ SCOPED TO THE ROW SINCE R-847, AND IT IS FOUR SINCE R-864. The band that used to sit
    BENEATH the row carried its own spans, so a cell-wide sweep returned six and the unpack
    failed — or worse, succeeded against the wrong three. v10 replaced that second row with a
    fourth cell on this one, so the sweep is honest again and the count changed.

    🚨 THE CHART CELL IS RETURNED EVEN WHEN EMPTY, which is what lets a test assert R-141's
    reservation on the five composite rows: `_custom_row` draws no chart and must still hold
    the column, or every figure on those rows shifts right relative to the metric rows.
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


def _recovered_frame(cell, p25, p75):
    """The frame `box()` actually scaled on, in DATA units, read back out of the drawn SVG.

    🚨 cfdb-main-R-1020 TOOK THE PRINTED BOUNDARY NUMBERS OFF THE CHARTS, and several assertions
    here were reading them as a proxy for *which column the frame came from*. **The frame is
    still recoverable — it is just geometry now.**

    ✅ TWO KNOWN DATA POINTS AND TWO KNOWN PIXELS ARE ENOUGH, AND IT NEEDS NO PRIVATE CONSTANT:
    the box rect spans p25→p75, the whisker serifs sit at the frame's two ends, so the scale is
    `(p75 - p25) / rect_width` and everything else follows. ⚠️ **Nothing here assumes `box()`'s
    `pad`** — B114 refused to couple to that private value and this respects it.
    """
    rect = re.search(r"<rect x='([\d.]+)' y='[\d.]+' width='([\d.]+)'", cell)
    serifs = sorted(float(x) for x in re.findall(
        r"<line x1='([\d.]+)' y1='[\d.]+' x2='[\d.]+' y2='[\d.]+' "
        r"stroke='currentColor' stroke-width='1' opacity='.55'", cell))
    if rect is None or len(serifs) < 2:
        return None
    left, span = float(rect.group(1)), float(rect.group(2))
    scale = (p75 - p25) / span
    lo = p25 - (left - serifs[0]) * scale
    return lo, lo + (serifs[-1] - serifs[0]) * scale


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
    have. ⚠️ Measured: `dp` changes no label COUNT at these widths, so this costs nothing.

    🚨 ITS SUBJECT NARROWED IN cfdb-main-R-1020 AND THE TEST STAYED GREEN THROUGH IT, WHICH IS
    WHY THIS PARAGRAPH IS HERE. Marc took the tick labels off, so the only `<text>` left in the
    cell is **the two teams' own value labels** — `dp` still governs them, so the property holds
    and the assertion still bites, **but it now covers two labels where it used to cover five.**
    ⚠️ A test whose coverage shrinks silently is the thing this file keeps finding; the
    `assert labels` below is what stops it shrinking to zero unnoticed."""
    run, _ = panel
    for cell in _cells(run(_both())[0]):
        if ">First downs<" not in cell:
            continue
        labels = _band_labels(cell)
        assert labels, (
            "the first-downs cell drew no labels at all — with the ticks gone (cfdb-main-R-1020) "
            "the value labels are all that is left, and this test has gone blind if they go too")
        assert not any("." in text for text in labels), (
            f"a count's band is labelled with decimals it does not have: {labels}")
        return
    raise AssertionError("the first-downs row never rendered")


def test_THE_METRIC_CELLS_LABEL_MIN_AND_MAX_and_not_the_whisker_ends(panel):
    """🚨 cfdb-main-R-1028, THE SECOND CALL SITE. **Marc, v17:** *"label MIN, Max, 25pctl, 75pctl
    where there is room"* and *"the whisker endpoints don't need to be labeled"*.

    ⚠️ FLIPPED FROM `test_THE_METRIC_CELLS_PRINT_NO_TICK_NUMBERS_but_keep_both_teams_own`, WHICH
    B125 WROTE ONE ROUND AGO FOR v16. **v17 reverses the *no numbers* half and keeps the *not the
    whisker ends* half**, so the test tracks the requirement rather than being deleted with it.

    🚨 ITS ORIGINAL REASON IS UNCHANGED: B125 staged the removal of `ticks=` and **the whole suite
    stayed green.** Marc's instruction had nothing holding it at either call site.

    ⚠️ `value_label=None` DOES NOT MEAN *no label* HERE — `box()` falls back to
    `fmt.number(value, dp=dp)`, so **both teams' own figures print** and both must survive.

    ⚠️ ONLY THE HIGH END IS DECIDABLE ON THIS ROW: rushing yards publishes `min_value` 2 and
    `whisker_low` 2, **the same number**, so a labelled low whisker end is indistinguishable from
    a labelled MIN. The high pair — fences to 365, extreme to 569 — is distinct, and the
    assertion says so rather than pretending to test both.
    """
    run, _ = panel
    spread = {row["metric"]: row for row in _SPREAD}["rushing_yards"]
    assert spread["whisker_high"] != spread["max_value"], (
        "the fixture's high fence and high extreme now agree, so this test cannot tell a "
        "labelled whisker end from a labelled MAX")
    for cell in _cells(run(_both())[0]):
        if ">Rushing yards<" not in cell:
            continue
        labels = _band_labels(cell)
        assert f"{spread['max_value']:g}" in labels, (
            f"the cell does not print MAX {spread['max_value']:g} — v17 extends the frame to the "
            f"extremes precisely so they can be labelled: {labels}")
        assert f"{spread['whisker_high']:g}" not in labels, (
            f"the cell prints the high whisker end {spread['whisker_high']:g} — v17: *the whisker "
            f"endpoints don't need to be labeled*: {labels}")
        assert f"{spread['p50']:g}" not in labels, (
            f"the cell prints the median {spread['p50']:g}, which is in no version of Marc's "
            f"list: {labels}")
        return
    raise AssertionError("the rushing-yards row never rendered")


def test_the_band_draws_the_WHISKERS_and_not_the_MIN_MAX_it_could_have(panel):
    """🚨 BOTH PAIRS ARE PUBLISHED AND THEY ARE DIFFERENT NUMBERS, WHICH IS THE WHOLE EXPOSURE.
    `srv_game_team_metric_distribution` carries `whisker_low`/`whisker_high` AND
    `min_value`/`max_value`. Marc's v07 said *"measure the min/max"*; his v06 said *"label
    upper/lower boundaries"*. A band drawn from the extremes and labelled as the fences is a
    picture describing a wider spread than its own labels claim — **every number real, the box
    still drawn, and nothing crashing.**

    ✅ SO THE ASSERTION IS THE DRAWN EXTENT AGAINST THE COLUMN THE LABEL NAMES. On 2026 week 1
    rushing yards the fences run 2 → **365** and the extremes 2 → **569**; on first downs the
    fences are **5** → 38 and the extremes **4** → 38.

    ⚠️ AND IT INVOKES THE PAGE RATHER THAN REPRODUCING IT (R-768): `run()` calls the real
    `_post_game`, and this is the geometry `box()` actually emitted.

    🚨 IT ASSERTED THE PRINTED BOUNDARY LABEL UNTIL cfdb-main-R-1020, WHEN MARC TOOK THE PRINTED
    NUMBERS OFF THE CHARTS: *"Draw the whiskers but don't add tick marks/labels for the values."*
    **`"365" in labels` had nothing left to read.** ⚠️ The exposure is unchanged and the fixture
    still carries both pairs — so the instrument moved from the LABEL to the DRAWN BOX, which is
    what this test's own docstring always said it was about.

    ✅ AND THE DISCRIMINATOR IS THE ONE ALREADY MEASURED HERE: **the box spans 35% of the fence
    range and 22% of the min-max range.** Drawing the extremes compresses the box toward a line,
    which is what `outlier_count` is published separately to avoid. A swap moves the rect by ~13
    points of plot width — far outside any rounding.
    """
    run, _ = panel
    spread = {row["metric"]: row for row in _SPREAD}
    cells = _cells(run(_both())[0])
    # (metric, cell heading, which end this row's two pairs disagree on)
    for metric, heading, end in (("rushing_yards", ">Rushing yards<", "high"),
                                 ("first_downs", ">First downs<", "low")):
        row = spread[metric]
        fence = (row["whisker_low"], row["whisker_high"])
        extreme = (row["min_value"], row["max_value"])
        index = 0 if end == "low" else 1
        assert fence[index] != extreme[index], (
            f"{metric}'s fence and extreme agree at the {end} end, so this row cannot tell the "
            f"two columns apart — see the comment on `_SPREAD`")
        for cell in cells:
            if heading not in cell:
                continue
            got = _recovered_frame(cell, row["p25"], row["p75"])
            assert got is not None, f"the {metric} cell drew no box to measure: {cell[:300]}"
            # ⚠️ `box()` WIDENS ITS FRAME AROUND A VALUE MARKER, so the recovered end is the
            # fence OR a team's own figure beyond it — never the OTHER published column. The
            # assertion is therefore *nearer the fence than the extreme*, which is exactly the
            # swap this test exists for and is immune to the widening.
            to_fence = abs(got[index] - fence[index])
            to_extreme = abs(got[index] - extreme[index])
            assert to_fence < to_extreme, (
                f"{metric}'s band is framed at {got[index]:.1f} on its {end} end — that is "
                f"{to_fence:.1f} from `whisker_{'low' if end == 'low' else 'high'}` "
                f"{fence[index]} and {to_extreme:.1f} from the extreme {extreme[index]}. A band "
                f"drawn to the extremes describes a wider spread than a box-and-whisker claims, "
                f"with every number real and nothing crashing")
            break
        else:
            raise AssertionError(f"the {metric} row never rendered")


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
        label, away, home, _chart = _spans(cell)
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
    value_w = _expected_value_width()
    for cell in _cells(run(_both())[0]):
        style = _resolved(cell.split("style='")[1].split("'")[0])
        assert style.get("overflow") == "hidden", f"a measure row does not clip: {style}"
        assert style.get("box-sizing") == "border-box", (
            "without border-box the padding is ADDED to the width and the row grows past its "
            "column")
        # 🚨 NO PART OF THE ROW IS PROPORTIONAL, AND SINCE R-864 THAT INCLUDES THE CHART CELL.
        # A `flex:1` chart cell would be the obvious way to fill the leftover room and it is the
        # wrong one: `box()` emits `max-width:100%`, so an SVG whose declared width its cell
        # cannot honour is SCALED rather than clipped — B108 squeezed a 432px viewBox into 216px
        # and rendered its `18` four pixels tall. **The DOM was correct and the text was
        # unreadable**, which no assertion on the markup could have caught.
        row_only = cell.split("</div>", 1)[0]
        assert "flex:1" not in row_only, (
            f"something in the measure row is proportional again: {row_only[:200]}")
        label, away, home, chart = _spans(cell)
        for part, wanted, what in ((label, label_w, "measure name"),
                                   (away, value_w, "away figure"),
                                   (home, value_w, "home figure")):
            assert part.get("flex") == "none", f"the {what} can grow or shrink"
            assert part.get("width") == f"{wanted}rem", (
                f"the {what} is {part.get('width')} rather than the {wanted}rem the table "
                f"budgets for it")
        chart_w = _expected_chart_width()
        assert chart.get("flex") == "none", "the chart column can grow or shrink"
        assert chart.get("width") == f"{chart_w}px", (
            f"the chart column is {chart.get('width')} rather than the {chart_w}px it declares "
            f"— and `box()` is handed that same number, so the two cannot be allowed to drift")


def test_the_COMMENTS_ABOUT_THE_CHART_WIDTH_AGREE_WITH_THE_CODE():
    """🚨 cfdb-wta-R-961. A COMMENT THAT MISSTATES THE CODE BESIDE IT — THE FOURTH THIS WEEK, AND
    THE FIRST ONE CHEAP ENOUGH TO GIVE A TEST.

    `matchup.py` said *"the alternative this file actually carries is **230px** at
    `_TABLE_CELLS_EQUAL = True `"*. **The code does the opposite:** `True` makes the three value
    cells take a third of the budget each and leaves the chart the NARROW 118px; `False` gives the
    value cells their content width and the chart the wider 230px. ⚠️ **Twelve lines further down
    the same file had it right**, so the file contradicted itself, and the paragraph was already
    carrying a correction notice from R-893 when it shipped the inversion.

    ✅ THE CLASS IS NOT CARELESSNESS — after A138's `play_number` docstring, B115's four dead
    `_scatter` pointers and the note whose premises had died, the pattern is plain: **comments have
    no test.** This is what one looks like when the comment states a NUMBER the code computes.

    ⚠️ SCOPE, IN THE SAME SENTENCE AS THE CLAIM: this checks pixel figures that appear in the same
    sentence as a `_TABLE_CELLS_EQUAL` value. **It cannot see a prose claim with no number in it**,
    and it says nothing about the other three instances, which were not numeric. A guard that
    caught one shape of one class is still a guard nothing else provides.
    """
    source = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()

    # Recompute BOTH widths from the module's own literals — never read `_TABLE_CHART_WIDTH`
    # back, which would only prove the file agrees with whichever branch is shipped today.
    budget = (_module_constant("_TABLE_ROW_BUDGET")
              - int(_module_constant("_TABLE_LABEL_WIDTH") * _module_constant("_REM"))
              - 3 * int(_module_constant("_TABLE_GAP") * _module_constant("_REM")))
    width = {True: budget - 2 * (budget // 3),
             False: budget - 2 * _module_constant("_TABLE_VALUE_CONTENT_PX")}
    assert width[True] != width[False], (
        "the two options compute the same width, so this test cannot tell them apart")

    # Two shapes occur in the file: "**230px** at `_TABLE_CELLS_EQUAL = False`" and
    # "`True` is 118px". Both pair a figure with a flag value in one sentence.
    pairs = []
    for line in source.splitlines():
        if not line.lstrip().startswith("#"):
            continue
        for px, flag in re.findall(r"(\d{2,4})px\D{0,80}?`?_TABLE_CELLS_EQUAL = (True|False)",
                                   line):
            pairs.append((int(px), flag == "True", line.strip()))
        for flag, px in re.findall(r"`(True|False)` is \*?\*?(\d{2,4})px", line):
            pairs.append((int(px), flag == "True", line.strip()))

    assert pairs, (
        "no comment in matchup.py pairs a pixel figure with a `_TABLE_CELLS_EQUAL` value — this "
        "guard has gone blind, which is exactly how the inverted claim survived R-893's fix")

    wrong = [(px, flag, line) for px, flag, line in pairs if px != width[flag]]
    assert not wrong, (
        "a comment states a chart width the code does not produce — "
        + " || ".join(f"says {px}px at _TABLE_CELLS_EQUAL={flag} but the code computes "
                      f"{width[flag]}px :: {line[:90]}" for px, flag, line in wrong))


def test_the_TABLE_HEADER_takes_the_TABLES_OWN_COLUMN_WIDTHS_and_BOTH_logos_in_order(panel):
    """🚨 AMENDED FROM B108's `test_the_SIDE_HEADING_takes_the_cells_width_and_not_the_columns`.
    The heading is a TABLE HEADER ROW now — Marc, v08: *"One big table, with a header row for
    Box Score / Logo Away / Logo Home"*.

    ⚠️ AND IT TAKES THE TABLE'S OWN COLUMN WIDTHS OR IT STOPS BEING A HEADER: a header whose
    cells do not line up with the rows beneath it is a caption.

    ⚠️ RENAMED IN R-885: it no longer carries the section NAME. `_section_heading` does, with
    Marc's bold rule under it, and this row is the logos. **The old name described an assertion
    this test never made** — see `test_each_SECTION_NAME_is_drawn_ONCE_with_a_BOLD_RULE`.
    """
    run, _ = panel
    entries = run(_both())[0]
    # ⚠️ THE SUBHEADER ALSO SAYS "Box score", so the header ROW is found by its own markup
    # rather than by its text — the first markdown that carries a rule under it.
    header = next(str(b) for _k, b in entries
                  if "Box score" in _plain(str(b)) and "border-top" in str(b))
    assert f"width:{_module_constant('_TABLE_LABEL_WIDTH')}rem" in header, (
        "the header's first cell is not the measure-name column's width")
    assert f"width:{_expected_value_width()}rem" in header, (
        "the header's figure cells are not the value columns' width")
    # 🚨 AWAY BEFORE HOME, BY THE TEAMS' OWN NAMES (R-522). `_both()` is Auburn at HOME and
    # Kentucky AWAY, so a swap changes which name comes first — which is the thing B082 and
    # B083 both proved a presence assertion cannot see.
    plain = _plain(header)
    # ⚠️ THE TOKENS ARE THE ABBREVIATIONS SINCE R-856 — the header draws `UK` and `AUB`, not
    # the full names. The CLAIM is untouched: away before home, by the teams' own identities.
    assert plain.index("UK") < plain.index("AUB"), (
        f"the header's two teams are not in away-then-home order — Kentucky (UK) is the away "
        f"side: {plain[:160]}")
    # Marc: *"a horizontal line between the header row and the metrics row"*.
    assert "border-top" in header, "there is no rule under the header row"


def test_ONE_chart_per_row_at_the_CHART_COLUMNS_width_and_never_box_s_240px_default(panel):
    """🚨 R-864. Marc, v10: *"make a single box-whisker chart, create a new column for it."*

    ⚠️ AMENDED FROM B108's band test, TWICE OVER: the count changed as well as the width. There
    were TWO bands per row, one under each figure, because a band could carry only one team's
    mark; A131's two-sided `box()` carries both, so there is now ONE chart and it has its own
    column. **A test that only checked the width would pass on two charts of the right size.**

    📊 AND THE WIDTH IS BELOW THE FLOOR, WHICH THIS TEST STATES RATHER THAN HIDES. B108 measured
    the minimum useful plot width at 200px and A131's own sweep puts 200px at the point where
    the below band stops dropping to three labels. **The chart ships at 110px** because that is
    what is left at 1300px once the label column has given up everything it can and the cards
    have given up nothing — measured, not chosen. **The report carries the trade to Marc.**
    """
    run, _ = panel
    cells = _cells(run(_both())[0])
    assert cells, "no measure row rendered at all"
    metric_cells = [c for c in cells if _bands(c)]
    assert metric_cells, "no chart was drawn at all"
    # 🚨 ONE PER ROW. Two would mean the two-sided call was not used and each side got its own.
    for cell in metric_cells:
        assert len(_bands(cell)) == 1, (
            f"a measure row carries {len(_bands(cell))} charts — v10 asks for a SINGLE chart "
            f"holding both teams, not one per side")
    widths = {int(w) for cell in metric_cells for w, _h in _bands(cell)}
    assert 240 not in widths, (
        f"a chart is 240px — that is `box()`'s own default, so the width was not passed: "
        f"{sorted(widths)}")
    wanted = _expected_chart_width()
    assert widths == {wanted}, (
        f"the charts are {sorted(widths)}px; the column budgets {wanted}px. `box()` emits "
        f"max-width:100%, so a chart wider than its cell is SCALED DOWN and its labels shrink "
        f"with it — B108's 4px-tall `18`")


def test_the_chart_is_TWO_SIDED_and_says_so_to_a_SCREEN_READER(panel):
    """🚨 AC-G.11 THROUGH THE ONE CHANNEL A SIGHTED READER DOES NOT USE. `box()` narrates two
    markers, one marker and none as three different sentences; a reader who cannot see the empty
    half has only this string. **A chart drawn one-sided would still LOOK plausible.**

    ⚠️ AND IT IS THE ARGUMENT'S PRESENCE THAT SELECTS THE MODE, NOT ITS VALUE —
    `two_sided = show_value and value_below is not _UNSET`. Passing `value_below=None` for a side
    with no figure keeps away in its own half; OMITTING it redraws away as a centre marker
    belonging to neither team. That distinction is invisible in a width or a count, so it is
    asserted on the narration.
    """
    run, _ = panel
    cells = [c for c in _cells(run(_both())[0]) if _bands(c)]
    labels = [m for c in cells for m in re.findall(r"aria-label='([^']*)'", c)]
    assert labels, "no chart carried an aria-label at all"
    for reading in labels:
        assert ", two values" in reading, (
            f"the chart does not narrate two values — a one-sided chart on a two-team panel "
            f"reads as belonging to neither side: {reading!r}")


BOX_HEIGHT = 26      # `distribution.BOX_HEIGHT` — the box's own height in the SVG


def _markers(cell):
    """Every sided value marker in one cell's chart: (side, x, colour).

    🚨 READ OFF `_sided_marker`'s OWN GEOMETRY, which is what makes the two Part 4 tests
    independent. The above marker's rule runs `y1='0'` to the midline; the below marker's runs
    from the midline to the full height. **Side is read from y, colour from stroke** — so a test
    can assert one while staying blind to the other, and a single mistake cannot redden both.
    """
    out = []
    for x, y1, y2, colour in re.findall(
            r"<line x1='([\d.]+)' y1='([\d.]+)' x2='[\d.]+' y2='([\d.]+)' "
            r"stroke='([^']*)' stroke-width='2\.2'", cell):
        top, bottom = float(y1), float(y2)
        # 🚨 CLASSIFIED ON THE SPAN, NOT ON `y1` ALONE — AND THE FIRST VERSION WAS WRONG.
        # `_sided_marker` draws 0→13 above and 13→26 below; `_value_marker` — the ONE-VALUE
        # centre mark — draws 0→26, which shares its `y1` with the above marker. Keying on the
        # start alone reported a centre marker as "above", so the staged break that omits
        # `value_below` slipped past the geometry assertion entirely and was caught only by the
        # aria-label. **A helper that answers the wrong question is R-758's family**, and it is
        # exactly what the break existed to find.
        side = ("centre" if bottom - top > BOX_HEIGHT * 0.75
                else "above" if top == 0.0 else "below")
        out.append((side, float(x), colour))
    return out


def _table_header_markup(entries) -> str:
    """The table's own header ROW — the one with the two logos and a rule under it.

    ⚠️ SCOPED SINCE R-886. The card region gained a team header that ALSO carries a 3px accent
    underline, so a sweep over the whole page returns four accents where a test expects two —
    and the two extra ones are correct markup, which is what makes it a silent miscount rather
    than an obvious break (R-859: name the question the command actually answered).
    """
    return next(str(b) for _k, b in entries
                if "Box score" in _plain(str(b)) and "border-top" in str(b))


def _header_accents(entries):
    """The away and home underline colours from the TABLE header, in that order."""
    header = _table_header_markup(entries)
    # 🚨 THE FIRST TWO, AND THE REASON IS v11's ONE TABLE. `_table_header` runs TWICE inside a
    # single markdown now — once for Box score and once for Advanced Team Stats — so a sweep
    # returns FOUR correct accents where this test means the first section's two. **A count
    # that was right while there were two markdown blocks silently doubled when there was one.**
    found = re.findall(r"border-bottom:3px solid ([^;']+)", header)
    assert len(found) % 2 == 0 and found[:2] == found[2:4] or len(found) == 2, (
        f"the two sections' header accents disagree, so one of them is naming the wrong team: "
        f"{found}")
    return found[:2]


def test_AWAY_is_the_ABOVE_marker_and_HOME_is_the_BELOW_one(panel):
    """🚨 R-864, PART 4. Marc, v10: *"label Away above the line, Home below, if possible."*

    ⚠️ HE PREFIXED IT *"would be ideal… if possible"* AND IT IS NOT A NICETY — it is the
    accessibility answer. `_sided_marker`'s own docstring makes the case: nothing prevents two
    teams being the same red, B102 measured green and red 1.8 luma apart on this very panel, and
    **10.1% of the games that render this panel have at least one row where the two sides have
    the SAME figure** — two markers at the same x, which in one lane is one mark and a lost team.
    Above and below survive greyscale, colour-blindness and two teams from one palette.

    🚨 THIS TEST IS DELIBERATELY BLIND TO COLOUR. A131 measured why: its colour break left every
    orientation test GREEN and its side break left the colour test GREEN. **They are two
    independent mistakes.** A test that reddened on both would tell you something broke without
    telling you which — see `test_AWAY_S_COLOUR_goes_with_AWAY_S_MARKER`.

    ⚠️ ASSERTED ON x-ORDER, NOT ON PRESENCE. The fixture's rushing yards are away 79 and home
    118, so away's marker must sit LEFT of home's. Both markers are present in either
    arrangement, which is exactly what B082 and B083 proved a presence assertion cannot see.
    """
    run, _ = panel
    cell = next(c for c in _cells(run(_both())[0])
                if "Rushing yards" in _plain(c) and _bands(c))
    marks = _markers(cell)
    assert len(marks) == 2, f"expected one marker per side, got {len(marks)}: {marks}"
    sides = {side: x for side, x, _c in marks}
    assert set(sides) == {"above", "below"}, (
        f"the two markers are not one above and one below — a side lost its half: {marks}")
    # away 79 < home 118, so away's x is the smaller. The ABOVE marker must be away's.
    assert sides["above"] < sides["below"], (
        f"the ABOVE marker sits at x={sides['above']} and the BELOW one at x={sides['below']}. "
        f"Away's rushing yards are 79 and home's are 118, so away is the smaller x — the two "
        f"sides are swapped and home is being drawn above the line")


def test_AWAY_S_COLOUR_goes_with_AWAY_S_MARKER(panel):
    """🚨 R-864, PART 4, AND THE OTHER HALF. The marker in away's half must carry away's colour.

    🚨 DELIBERATELY BLIND TO WHICH VALUE IS WHERE. It reads the side off the geometry and then
    asserts ONLY the colour, so swapping the two figures leaves it green and swapping the two
    colour strings reddens it alone. **Two mistakes, two tests, and each says which.**

    ✅ AND IT TIES THE CHART TO THE HEADER, WHICH IS R-855's CLAIM MADE MECHANICAL. `_accent` is
    the one producer of the `light-dark(...)` string; the header underline and the chart marker
    are the same call. Asserting they are EQUAL rather than merely both-present is what catches a
    second copy of the expression drifting from the first — the failure R-855 exists for, and
    which this file has now paid for three rounds running.
    """
    run, _ = panel
    entries = run(_both())[0]
    away_accent, home_accent = _header_accents(entries)
    assert away_accent != home_accent, (
        "the fixture's two sides resolve to the same accent, so this test cannot tell them "
        "apart — it would pass on any swap")
    cell = next(c for c in _cells(entries) if "Rushing yards" in _plain(c) and _bands(c))
    by_side = {side: colour for side, _x, colour in _markers(cell)}
    assert by_side.get("above") == away_accent, (
        f"the ABOVE marker is {by_side.get('above')!r} and away's header underline is "
        f"{away_accent!r} — the chart and the header are naming the same team in different "
        f"colours, or the two colour strings are swapped")
    assert by_side.get("below") == home_accent, (
        f"the BELOW marker is {by_side.get('below')!r} and home's header underline is "
        f"{home_accent!r}")


def test_value_below_is_PASSED_even_when_it_is_NONE_so_away_keeps_its_own_half(panel):
    """🚨 R-864. `box()` SELECTS TWO-SIDED MODE ON THE ARGUMENT'S PRESENCE, NOT ITS VALUE —
    `two_sided = show_value and value_below is not _UNSET`. Omitting it for a side with no
    figure does not draw "away plus a gap": it redraws away as a ONE-VALUE CENTRE MARKER, a
    mark belonging to neither team on a panel whose whole job is comparing two.

    ⚠️ AND THE STATE IS NOT REACHABLE IN PRODUCTION TODAY, WHICH THIS TEST SAYS OUT LOUD RATHER
    THAN IMPLYING COVERAGE IT DOES NOT HAVE (§6, R-762). Measured on live serving: **0 of 7,348
    box-score rows carry a null on any charted measure**, and the only advanced column that goes
    null per side is `defense_havoc_rate` — whose row `_post_game` already drops unless BOTH
    sides carry `has_havoc`. `has_havoc` and the null agree on all 7,204 rows, so the filter is
    exact and **0 games reach this branch**.

    ✅ SO WHY TEST IT AT ALL: the thing being guarded is REACHED ON EVERY ROW. Passing
    `value_below` is what selects two-sided mode for the 18 rows that DO draw two values, and a
    fixture null is simply the cheapest way to prove the argument is passed rather than omitted.
    **The assertion is on the call, not on a state nobody can reach.**
    """
    run, _ = panel
    home = dict(_side("Auburn", True), rushing_yards=None)
    entries = run([home, _side("Kentucky", False)])[0]
    cell = next(c for c in _cells(entries) if "Rushing yards" in _plain(c) and _bands(c))
    marks = _markers(cell)
    assert len(marks) == 1, (
        f"a side with no figure should leave ONE marker drawn, got {len(marks)}: {marks}")
    assert marks[0][0] == "above", (
        f"away's marker slid out of its own half to {marks[0][0]} — `value_below` was omitted "
        f"rather than passed as None, so box() drew a one-value CENTRE marker that belongs to "
        f"neither team")
    reading = re.search(r"aria-label='([^']*)'", cell).group(1)
    assert "one value — the other side has none" in reading, (
        f"the chart does not narrate WHICH absence this is (AC-G.11): {reading!r}")


def test_a_side_with_NO_SOURCED_COLOUR_still_draws_its_marker(panel):
    """⚠️ COLOUR IS THE SECOND SIGNAL AND POSITION IS THE FIRST (AC-G.22), SO A TEAM WITH NO
    PUBLISHED COLOUR MUST STILL APPEAR. `identity.text_on(None)` yields `identity.FALLBACK` —
    neutral grey in both themes — and the marker draws in its own half exactly as any other.

    📊 THE POPULATION, CORRECTED. B109 measured **10.89% of games** with a side carrying no
    sourced colour and that is right across all **112,675** games. **This panel only ever renders
    the 3,674 that have a box score, and there it is 37 games — 1.01%.** Both numbers are true
    of different questions; the one that governs this branch is the smaller (§2.4, R-859).

    ⚠️ THE FIXTURE'S AWAY SIDE ALREADY HAS NO COLOUR, which is why `_COLORS` is asymmetric — a
    symmetric fixture could not tell a fallback from a real colour.
    """
    run, _ = panel
    entries = run(_both())[0]
    away_accent, home_accent = _header_accents(entries)
    cell = next(c for c in _cells(entries) if "Rushing yards" in _plain(c) and _bands(c))
    by_side = {side: colour for side, _x, colour in _markers(cell)}
    assert set(by_side) == {"above", "below"}, (
        f"a side with no sourced colour lost its marker entirely: {by_side}")
    assert by_side["above"] == away_accent, (
        f"the uncoloured side's marker is {by_side['above']!r} rather than the fallback its "
        f"own header underline uses, {away_accent!r}")
    assert "light-dark(" in by_side["above"], (
        f"the fallback is a single colour, so it is right in one theme and wrong in the other: "
        f"{by_side['above']!r}")


def test_the_COMPOSITE_rows_RESERVE_the_chart_column_and_draw_NO_PLACEHOLDER(panel):
    """🚨 R-864, PART 5. Third down, turnovers and possession are not scalars — `6/14`,
    `1 (1 INT · 0 FUM)`, `30:51` — so there is nothing to take a percentile of, ever.

    ✅ THE COLUMN IS STILL RESERVED (R-141: *an element that appears only when populated shifts
    everything beside it*). Without it the two figures would sit in a different place on a
    turnovers row than on a yards row, and the table would stop being a table.

    ❌ AND IT DRAWS NO PLACEHOLDER. `box()`'s own empty state says *"cfdb holds no distribution
    for this week yet"*, which is TRUE of a measure that could have one and FALSE of these five.
    **A placeholder promising one later is the wrong absence** — AC-G.11, and it is the same
    distinction B110 drew between *no second quarterback* and *no leaders at all*.
    """
    run, _ = panel
    cells = _cells(run(_both())[0])
    composite = [c for c in cells if "Third down" in _plain(c) or "Turnovers" in _plain(c)]
    assert composite, "neither composite row rendered"
    chart_w = _expected_chart_width()
    for cell in composite:
        assert not _bands(cell), (
            f"a composite row drew a chart — there is no percentile of {_plain(cell)[:60]!r}")
        assert "no distribution" not in _plain(cell).lower(), (
            f"a composite row drew box()'s placeholder, which promises a distribution that can "
            f"never arrive: {_plain(cell)[:120]}")
        spans = _spans(cell)
        assert len(spans) == 4, (
            f"a composite row has {len(spans)} cells against the metric rows' 4 — the chart "
            f"column was dropped rather than reserved, so every figure on this row shifts")
        assert spans[3].get("width") == f"{chart_w}px", (
            f"the composite row's chart column is {spans[3].get('width')} rather than "
            f"{chart_w}px, so it does not line up with the metric rows above it")


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
    assert slots == ["table", "cards"], (
        f"the blocks are laid out {slots} — v08 is the table hard left, then away, then home")
    widths = dict(layout)
    # 🚨 THE TABLE IS THE WIDE ONE, AND IT IS PINNED TO THE SLOT RATHER THAN TO THE INDEX. If
    # the weights were keyed by position, moving the table would hand it a card's width while
    # every positional assertion still passed — which is exactly what B098 found on this page.
    assert widths["table"] > widths["cards"], (
        f"the table is not the wide block: {widths}")
    # ⚠️ THE AWAY/HOME EQUALITY MOVED INSIDE THE REGION (R-886). It used to be two Streamlit
    # weights; the two halves are now `flex:1` siblings, which is the same claim enforced by
    # the browser rather than by a tuple — and `test_the_two_card_HALVES_are_EQUAL_WIDTH`
    # asserts it on the markup.


def test_each_SECTION_NAME_is_drawn_ONCE_with_a_BOLD_RULE(panel):
    """🚨 R-885. Marc, v11: *"Box Score and Advanced (renamed to Advanced Team Stats) … should
    have a bold underline to help define the section."*

    🚨 AND `ONCE` IS THE HALF THE RASTER CAUGHT. The section heading was added above a table
    header row that ALREADY printed the same words in its first cell, so the page drew **"Box
    score" twice, one line apart.** Both elements were correct, both were exactly what their
    own tests asked for, and every assertion passed. **Only the picture showed it** — the
    fourth time on this panel (B103's invisible rule, B108's squash, B111's floating chart).

    ⚠️ THE RULE IS HEAVIER THAN THE HEADER ROW'S ON PURPOSE. `_table_header` draws 1px under
    the LOGOS, which separates a header from its figures; this draws 2px for the section's
    NAME, which separates one section from the other. Same weight twice would read as the same
    boundary drawn twice — which is what the duplicated name looked like.

    🚨 cfdb-wta-R-995 MOVED THAT 2px ABOVE THE NAME, AND THIS TAB WAS NOT WHAT MARC NAMED.
    His v16 line is about *"Header rows (Total, Rushing, Passing"* — the BEFORE-GAME metric
    headers. **`_section_heading` draws those AND this tab's "Box score" and "Advanced", so the
    change reaches here too.** ✅ Taken deliberately: one element, one look — two arrangements of
    the same heading would be the drift §4.3 exists to stop. ⚠️ **Reported so it can be reversed
    if he meant only the three rows he named.**
    ❌ `_CARD_RULE`, the position headings' own 2px, is untouched — a different element, and he
    did not name it.
    """
    run, _ = panel
    body = _text(run(_both())[0])
    for name in ("Box score", _module_constant("_ADVANCED_SECTION")):
        assert body.count(name) == 1, (
            f"{name!r} is drawn {body.count(name)} times — the section heading and the table "
            f"header row are both printing it")
    table = next(str(b) for _k, b in run(_both())[0]
                 if "Box score" in _plain(str(b)) and "border-top" in str(b))
    rule = _module_constant("_SECTION_RULE")
    assert table.count(rule) == 2, (
        f"expected one bold section rule per section, found {table.count(rule)}")


def test_a_DEPTH_ONE_group_handed_FOUR_ROWS_draws_ONE_and_does_not_break(panel):
    """🚨 R-891. MARC'S `(1)` DESCRIBES THE USUAL CASE; IT IS NOT A GUARANTEE THE DATA MAKES.

    📊 Measured on serving: **810 punting team-games (11.3%) and 629 kicking (8.8%) carry more
    than one man**, with a maximum of **3** for punting and **4** for kicking. 🚨 **And
    `leader_rank <= 3` is not a cap of three** — `rank()` with a tie yields `1,2,3,3`, so four
    rows pass the filter. **The real case is game 401655657, team 2086: ranks 1, 2, 3, 3.**

    ✅ THE DECISION IS *DRAW RANK 1 ONLY*, which is what Marc asked for — but the thing this
    test exists for is that the page must not BREAK on four, and a fixture carrying one could
    never tell. **`[:wanted]` is the slice; this proves the slice is what limits it rather than
    an assumption about the relation.**

    ⚠️ AND IT ASSERTS WHICH ONE SURVIVES, NOT MERELY HOW MANY. Taking the LAST of four would
    also draw one card — and would show the reader the fourth-best kicker.
    """
    run, _ = panel
    rows = [r for r in _post_game_leaders() if r["panel"] != "kicking"]
    for rank, (name, tied) in enumerate(
            (("Boot One", 1), ("Boot Two", 1), ("Boot Three", 2), ("Boot Four", 2)), start=1):
        rows.append(dict(
            next(r for r in _post_game_leaders() if r["panel"] == "kicking"),
            team_id=96, leader_rank=min(rank, 3), tied_players=tied,
            player_id=f"p96ki{rank}", player_name=name, qualified_players=4))
    region = _card_region(run(_both(), leaders=rows)[0])
    away = _side_cards(region, "away")
    kicking = [c for c in _cards_in(away) if "Points" in c]
    assert len(kicking) == 1, (
        f"a depth-1 group handed four rows drew {len(kicking)} cards — the slice is what must "
        f"limit it, not an assumption that the relation returns one row")
    assert "Boot One" in _plain(kicking[0]), (
        f"the card drawn is not rank 1 — the reader is being shown the wrong kicker: "
        f"{_plain(kicking[0])[:120]}")
    # ✅ AND THE GROUP AFTER IT STILL DRAWS, which is what would break if four rows overflowed
    # into the next group's row rather than being sliced off.
    assert _groups_in(region) == ["Quarterback", "Rushing", "Receiving", "Defense",
                                  "Punter", "Placekicker"], (
        f"the group run was disturbed by the extra rows: {_groups_in(region)}")


def test_an_EMPTY_HALF_under_a_DRAWN_HEADER_names_its_own_absence(panel):
    """🚨 R-887, AND v11's SPANNING HEADER IS WHAT CREATED IT.

    A group is skipped only when NEITHER side has rows. When ONE side has a punter and the
    other does not, the header draws **across both halves** and the empty one was blank — no
    card, no text, nothing a reader could distinguish from missing data. **Measured before the
    fix: `leader-cards=0 reserved=0 text=''`.** That is the hole AC-G.11 forbids.

    📊 **153 of 7,309 sides (2.1%) carry no punting row**, and at depth 1 *short* and *empty*
    are the same thing — which is why Rushing and Receiving never needed this and Punter does.

    ⚠️ IT IS A SENTENCE RATHER THAN A HELD SLOT, and deliberately not `_RESERVED_GROUPS`: that
    reserves a fixed 84px to keep the two columns' card COUNTS in register (R-849), a different
    job. These are the last two groups, so nothing below them needs the register.
    """
    run, _ = panel
    rows = [r for r in _post_game_leaders()
            if not (r["panel"] == "punting" and r["team_id"] == 96)]
    region = _card_region(run(_both(), leaders=rows)[0])
    assert "Punter" in _groups_in(region), (
        "the Punter header vanished — one side still has a punter, so it must draw")
    away = _side_cards(region, "away")
    assert "No punter recorded." in away, (
        f"the empty half under the Punter header says nothing: {_plain(away)[-200:]!r}")
    # 🚨 AND THE OTHER SIDE STILL DRAWS ITS CARD — a fix that silenced both halves would pass a
    # "the absence is named" check while losing the punter who actually played.
    home = _side_cards(region, "home")
    assert "Punts" in home, "the side that HAS a punter lost its card"
    assert "No punter recorded." not in home, "the side with a punter also claims it has none"


def test_ONE_MAN_can_be_BOTH_punter_and_placekicker_and_that_is_not_a_defect(panel):
    """⚠️ R-887. THE SAME NAME APPEARS IN TWO GROUPS, AND IT IS CORRECT — he has two jobs.

    📊 Measured on serving: **380 of 7,156 punting team-games — 5.3%** have the same `player_id`
    at rank 1 in both panels. The real case is **Aeron Burrell, North Carolina at TCU (game
    401856766)**, which this round rendered rather than assumed.

    🚨 IT IS TESTED BECAUSE THE OBVIOUS DEFENCE IS THE BUG. A renderer that de-duplicated cards
    by player — or a test that asserted every card names a different man — would drop his second
    card and leave a group with a header and no card under it.
    """
    run, _ = panel
    rows = list(_post_game_leaders())
    kick = next(r for r in rows if r["panel"] == "kicking" and r["team_id"] == 96)
    pun = next(r for r in rows if r["panel"] == "punting" and r["team_id"] == 96)
    kick.update(player_id=pun["player_id"], player_name=pun["player_name"])
    away = _side_cards(_card_region(run(_both(), leaders=rows)[0]), "away")
    cards = _cards_in(away)
    assert len([c for c in cards if "Punts" in c]) == 1, "the punter card vanished"
    assert len([c for c in cards if "Points" in c]) == 1, (
        "the placekicker card vanished — the same man in two groups was de-duplicated, which "
        "leaves a position header with nothing under it")


def test_the_two_card_HALVES_are_EQUAL_WIDTH_and_AWAY_comes_FIRST(panel):
    """🚨 R-886/R-522. The away and home halves are `flex:1` siblings of one row, so equality is
    enforced by the browser rather than by two Streamlit weights that could drift apart.

    ⚠️ AND THE ORDER IS ASSERTED, NOT THE PRESENCE. B082 and B083 both proved a presence
    assertion cannot see a left/right swap, and both halves are present in either arrangement.
    """
    run, _ = panel
    halves = _card_halves(_card_region(run(_both())[0]))
    assert halves, "no card halves were drawn"
    sides = [which for which, _m in halves]
    assert sides[::2] == ["away"] * (len(sides) // 2 + len(sides) % 2), (
        f"the halves are not away-then-home down the column: {sides}")
    assert sides.count("away") == sides.count("home"), (
        f"a group drew one side and not the other, so the position header above it spans a "
        f"row that is missing a half: {sides}")
    for _which, markup in halves:
        assert "flex:1" in markup, "a card half is not proportional, so the two can differ"


def test_each_POSITION_HEADER_spans_BOTH_halves_and_carries_a_BOLD_RULE(panel):
    """🚨 R-886. Marc, v11: *"the Position … should cover the entire row of player cards and
    have a bold underline breaking the vertical space."*

    🚨 THIS IS WHY THE CARDS STOPPED BEING TWO STREAMLIT COLUMNS. A header that spans both
    halves cannot live inside either of them, and Streamlit offers no way to place one element
    across two of its columns — so the region is one markdown block that splits itself.

    ⚠️ ASSERTED AS *OUTSIDE ANY HALF*, which is the thing that would break if someone put the
    header back inside a column: it would still render, still read correctly, and silently stop
    spanning. A presence check could not see that.
    """
    run, _ = panel
    region = _card_region(run(_both())[0])
    groups = _groups_in(region)
    assert groups, "no position header was drawn"
    for title in groups:
        before = region.split(f">{title}</div>")[0]
        # the header must not sit inside a half — every half opened before it must be closed
        opened = before.count("<div data-cfdb='card-half'")
        assert opened == before.count("</div></div>") or "card-half" not in \
            before.rsplit("<div style='display:flex", 1)[-1], (
            f"the {title!r} header is drawn inside a card half, so it spans one side rather "
            f"than the row")
    rule = _module_constant("_CARD_RULE")
    assert region.count(rule) >= len(groups), (
        f"{len(groups)} position headers but only {region.count(rule)} bold rules — v11 asks "
        f"for one under each")


def test_the_CARD_BORDER_is_the_TEAM_COLOUR_and_each_side_gets_ITS_OWN(panel):
    """🚨 R-886. Marc, v11: *"Player Card borders should be color of team."*

    ✅ `_accent` IS B111's ONE PRODUCER (R-855) and the table header's underline already uses
    it, so this asserts the card border EQUALS that underline rather than merely being a
    colour. **A second copy of the expression would pass a presence check and drift.**

    ⚠️ AND EACH SIDE GETS ITS OWN, which a swap would not change the COUNT of — so the away
    half's border is checked against away's underline specifically.
    """
    run, _ = panel
    entries = run(_both())[0]
    away_accent, home_accent = _header_accents(entries)
    assert away_accent != home_accent, "the fixture's two sides share an accent"
    region = _card_region(entries)
    for side, accent in (("away", away_accent), ("home", home_accent)):
        cards = _cards_in(_side_cards(region, side))
        assert cards, f"the {side} side drew no cards"
        for card in cards:
            assert f"border:1px solid {accent}" in card, (
                f"a {side} card's border is not that side's team colour — the border and the "
                f"header underline must be the same `_accent` call: {card[:140]}")


def test_a_side_with_NO_SOURCED_COLOUR_still_gets_a_CARD_BORDER(panel):
    """⚠️ POSITION IS THE FIRST SIGNAL AND COLOUR THE SECOND (AC-G.22), so a team with no
    published colour must still have an edge. `_accent(None)` yields `identity.FALLBACK`.

    📊 **1.01% of the games THIS panel renders — 37 of 3,674** — not the 10.89% all-games
    figure B109 measured and the prompt repeated (R-876). Both are true of different questions.
    """
    run, _ = panel
    region = _card_region(run(_both())[0])
    away_cards = _cards_in(_side_cards(region, "away"))
    assert away_cards, "the uncoloured side drew no cards at all"
    for card in away_cards:
        assert "border:1px solid light-dark(" in card, (
            f"the uncoloured side's card has no border, or a single-theme one: {card[:140]}")


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
    region = _card_region(run(_both(), leaders=rows + [second])[0])
    box_away_markup = _side_cards(region, "away")
    box_away, box_home = _plain(box_away_markup), _plain(_side_cards(region, "home"))
    assert "No second quarterback recorded" in box_away, (
        f"the away side has one quarterback and reserved nothing — every row below it is now "
        f"out of register with the home column: {box_away[:200]}")
    assert "Home QB2" in box_home, "the fixture's second home quarterback did not render"
    assert "No second quarterback recorded" not in box_home, (
        "the home side has two quarterbacks and still reserved a slot")
    # 🚨 AND THE RESERVED SLOT IS A DRAWN BOX, NOT A GAP. An empty box a reader cannot
    # distinguish from missing data is the hole AC-G.11 forbids; this one names itself.
    assert "border:1px dashed" in box_away_markup, (
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
    assert f"height:{reserved_h}rem" in box_away_markup, (
        "the reserved slot does not declare a fixed height, so it collapses to its text")


def test_a_side_with_NO_QUARTERBACK_gets_ONE_block_and_NOT_a_FIRST_and_a_SECOND(panel):
    """🚨 R-856, AND IT IS LANGUAGE RATHER THAN GEOMETRY — WHICH IS WHY B109's MEASUREMENTS
    COULD NOT CATCH IT. That round measured ALIGNMENT and got it exactly right: group headers
    at identical y in both columns. **A side with no quarterback still drew:**

        No first quarterback played
        No second quarterback played

    ⚠️ THE SECOND IS FINE. THE FIRST IS NOT. A reader does not think of quarterbacks as
    numbered slots — the ordinal is an artefact of the card grid, not a fact about the game —
    so *no FIRST quarterback* reads as a rendering error. **One block saying the thing that is
    true of the SIDE answers the question actually being asked.**

    🚨 AND `recorded` RATHER THAN `played`, WHICH IS A MEASUREMENT. Of the **573** sides with no
    `total` row on `srv_game_team_leader_in_this_game`, **571 — 99.7% — have receivers in the
    same game.** The ball was thrown and caught, so a quarterback was on the field; only the
    box score is silent. *Played* would be false on essentially every side this sentence draws
    for. **The live render game is one of them — North Alabama at Arkansas, game 401856635.**

    ✅ AND THE FOOTPRINT SURVIVES, WHICH IS THE WHOLE REASON R-849 EXISTS. One block standing
    in for `n` cards must occupy `n` heights plus the `n - 1` margins between them, or every
    group below it goes out of register between the two columns — the 33px error B109 shipped
    and caught only in a raster.
    """
    run, _ = panel
    # ⚠️ THE AWAY SIDE KEEPS ITS RUSHERS AND DEFENDERS AND LOSES ONLY ITS QUARTERBACK. A side
    # stripped of everything is the OTHER absence and is covered by the test below — if this
    # fixture removed all its rows, the honest-absence sentence would answer instead and this
    # test would pass while asserting nothing about the quarterback group (§6, R-760).
    rows = [r for r in _post_game_leaders()
            if not (r["panel"] == "total" and r["team_id"] == 96)]
    region = _card_region(run(_both(), leaders=rows)[0])
    away = _plain(_side_cards(region, "away"))
    assert "No quarterback recorded for this side." in away, (
        f"a side with no quarterback did not get the side-level sentence: {away[:200]}")
    # 🚨 THE ORDINAL MUST BE GONE FOR THIS SIDE — and `first` is the one that read as a bug.
    assert "No first quarterback" not in away, (
        f"the invented FIRST slot is still drawn — the ordinal is an artefact of the grid, "
        f"not a fact about the game: {away[:200]}")
    assert "No second quarterback" not in away, (
        f"the side-level block did not replace the per-slot cards, it joined them: {away[:200]}")
    # ✅ AND THE VERB, ASSERTED SEPARATELY FROM THE SHAPE so a reworded sentence cannot pass
    # by accident while re-asserting about the GAME rather than about the RECORD.
    assert "played" not in away, (
        "the block says a quarterback did not PLAY — 571 of 573 such sides have receivers in "
        "the same game, so the ball was thrown and only the box score is silent")
    # 🚨 THE FOOTPRINT, IN THE MARKUP, BECAUSE THE ALIGNMENT IS THE FEATURE. Two cards at
    # `_RESERVED_CARD_HEIGHT` plus the one `.3rem` margin BETWEEN them.
    card_h = _module_constant("_RESERVED_CARD_HEIGHT")
    spanned = 2 * card_h + 0.3
    assert f"height:{spanned:g}rem" in _side_cards(region, "away"), (
        f"the spanning block is not {spanned:g}rem, so it does not occupy the two slots it "
        f"replaced and every group below it is out of register with the home column")
    # ✅ AND THE HOME SIDE, WHICH HAS ONE QUARTERBACK, STILL GETS THE ORDINAL — the two
    # sentences must not collapse into one another.
    assert "No second quarterback recorded" in _plain(_side_cards(region, "home")), (
        "the side WITH a quarterback stopped naming which slot is missing")


def test_the_RESERVED_SLOT_does_not_replace_the_HONEST_ABSENCE_for_a_side_we_hold_nothing_for(panel):
    """🚨 THE REGRESSION R-849 ALMOST CAUSED, CAUGHT BY ITS OWN RENDER. Reserving the second
    quarterback unconditionally meant a side with NO leaders at all drew two blank cards instead
    of saying we hold nothing for it.

    ⚠️ THOSE ARE DIFFERENT ABSENCES (AC-G.11) AND THE RESERVED CARD ANSWERS THE WRONG ONE: *no
    second quarterback recorded* is a statement about one player; *we hold no leaders for this
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
    home = _plain(_side_cards(_card_region(entries), "home"))
    assert "No second quarterback recorded" in home, (
        "the side that DOES have one quarterback stopped reserving the second")


def test_the_HEADER_uses_the_ABBREVIATION_and_FALLS_BACK_to_the_full_name(panel):
    """🚨 R-856. B109's new header truncated *North Alabama* to **North Ala…**.

    ⚠️ AND B109 WAS NOT WRONG TO MISS IT: it counted 0 of 40 truncations in the CARD names and
    that count was correct. **The table header is an element the same round had just built and
    did not count** — a new element is outside the population of the measurement taken before
    it existed.

    ✅ `srv_game.away_abbreviation` / `home_abbreviation` ALREADY EXIST, so this is two columns
    on the `limit 1` read the header was ALREADY doing for its colours — no second query, and
    G-2 untouched. **Max published length is 9 characters, so the abbreviation cannot itself
    truncate.** 📊 And the same column answers A130's browser-tab question, which is why it is
    worth saying flat: the two rounds should read one object rather than coin two.

    ⚠️ THE FALLBACK IS NOT DEFENSIVE TYPING. Across all 112,675 games 12,018 away and 5,560 home
    abbreviations are null; on the 3,674 that HAVE a box score — the only ones this header ever
    draws — it is 39 away and 2 home. **~1% of this panel's population takes the fallback**, and
    the fixture's away side is one of them.
    """
    run, _ = panel
    entries = run(_both())[0]
    header = next(str(b) for _k, b in entries
                  if "Box score" in _plain(str(b)) and "border-top" in str(b))
    text = _plain(header)
    # 🚨 THE HOME SIDE HAS AN ABBREVIATION AND MUST USE IT — asserted as the FULL NAME BEING
    # ABSENT as well as the short one being present, because a header carrying both would
    # satisfy a presence check while still overflowing, which is the defect.
    assert "AUB" in text and "UK" in text, (
        f"the header does not use the published abbreviations: {text[:160]}")
    # 🚨 ASSERTED AS THE FULL NAME BEING ABSENT TOO, because a header carrying BOTH would
    # satisfy a presence check while still overflowing — which is the defect, not the fix.
    assert "Auburn" not in text, (
        f"the header still prints the full team name beside the abbreviation: {text[:160]}")
    # ✅ AND THE FALLBACK, ON ITS OWN RUN. A side with no published abbreviation keeps its full
    # name rather than drawing blank — AC-G.11: an absent abbreviation is not an absent team.
    fallback = next(
        str(b) for _k, b in run(_both(), colors=dict(_COLORS, home_abbreviation=None))[0]
        if "Box score" in _plain(str(b)) and "border-top" in str(b))
    assert "Auburn" in _plain(fallback), (
        f"a side with no published abbreviation lost its name entirely: "
        f"{_plain(fallback)[:160]}")


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
    accents = _header_accents(entries)
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
