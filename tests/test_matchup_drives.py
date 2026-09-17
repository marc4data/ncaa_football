"""The Matchup drive chart: the alternating possession sequence (R-372/R-374).

WHAT THIS EXISTS TO CATCH. `states.section` turns any exception inside the panel into the
Error state — plain language, no traceback, exactly as designed. That is also why a broken
panel looks like a handled failure rather than a defect: ci/check_page_queries.py was written
after Scores asked srv_game for eight columns it did not have and had been raising on every
load since it was written, with nobody noticing.

That check executes this panel's query too, so renamed and dropped columns are already
covered. What it cannot see is whether the panel still DRAWS the drives, and that is what
these assertions are for — the frame is stubbed so they test rendering, not the database.

THE ASSERTION THAT MATTERS MOST is the defense-touchdown one. A `TD` suffix on a turnover or
a kick means the DEFENSE scored — 908 drives across ten drive_result values, measured on the
built model — so a panel that reads the result TEXT rather than `scoring_side` puts every one
of them on the wrong side of the game, and does it while looking entirely healthy.
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
from lib import fmt  # noqa: E402


def _module_constant(name):
    """A page constant, read off the imported module rather than parsed out of the source.

    ⚠️ NOT `ast.literal_eval` — B126 found that cannot evaluate an attribute reference, and a
    helper that works for a dict of strings and fails for a module attribute is one a later
    round trips over.
    """
    import importlib
    return getattr(importlib.import_module("views.matchup"), name)


@pytest.fixture
def panel():
    """The panel with streamlit captured and the query stubbed, ready to be handed a frame.

    ⚠️ IT PUTS THE MODULES BACK, and the first version of this file did not. Reloading
    lib.states against a stub binds the stub inside it for the REST OF THE SESSION, and six
    unrelated tests in test_site_foundation and test_scores_page failed as a result — a test
    file that breaks other test files is worse than the regression it was written to catch.
    monkeypatch cannot undo it either: its sys.modules restore runs after this teardown, so
    the swap and the restore are both done by hand here.

    ⚠️ ON THE SHARED HARNESS SINCE R-613, which is what this docstring was always arguing for:
    the restore it describes by hand is `streamlit_stubbed`'s whole job, and it does both
    halves — sys.modules AND the parent package attribute, which A101 found the hard way.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, captured, charts):
        matchup = importlib.reload(importlib.import_module("views.matchup"))

        def run(frame, season=2026):
            # R-730. The season decides WHICH absence the Empty state states, so the
            # fixture has to carry one. 2026 is a completed modern game — the case
            # nearly every test here means; the scope tests pass a pre-2024 season.
            captured.clear()
            original = matchup.query
            matchup.query = lambda *a, **k: frame
            try:
                matchup._drives(9001, season)
            finally:
                matchup.query = original
            # 🚨 R-610. An Error state is not a passing state.
            render_harness.assert_no_error_card(captured, "the drives panel")
            # ⚠️ BOTH HALVES, SINCE B133. v01 draws a CHART, so an assertion about what the
            # panel shows has to reach the chart spec; `_text(entries)` can only see the
            # captions and the subheader now.
            return list(captured.events), charts

        yield run


def _drive(number, band, offense, result, *, scoring_side=None, scoring=False,
           start=25, end=60, on_field=True, color="#123456", source="primary",
           category="unknown", key=None, period=1, clock="12:00",
           off_score=(0, 7), def_score=(0, 0)):
    """One srv_drive row, carrying the columns v01 actually reads.

    🚨 **THE COLOURS SIT ON `offense_color_*` NOW, AND THIS FIXTURE USED TO SAY THE OPPOSITE** —
    *"srv_drive has no offense_color_*; a band's colour comes off the OTHER band's
    opponent_color_*"*. ✅ **Re-checked against `information_schema` at B133's base: all three of
    `offense_color_on_light`, `offense_color_on_dark` and `offense_color_source` exist, at
    100.00% coverage over 84,838 rows.** The upstream fix the old docstring asked for shipped;
    nothing told the fixture.

    ⚠️ **`start_yardline` IS DERIVED THE WAY THE WAREHOUSE DERIVES IT, NOT INVENTED** — measured
    at 100% on both bands: home `yardline == yards_from_own_goal`, away `yardline == 100 −
    yards_from_own_goal`. A fixture that got this backwards would make the direction assertions
    pass on a mirrored field, which is the failure `_drive_field_chart` exists to prevent.
    """
    absolute = (lambda own: own) if band == "home" else (lambda own: 100 - own)
    return {
        "drive_number": number, "band": band, "band_order": 2 if band == "home" else 1,
        "is_home_offense": band == "home",
        "offense_team_display": offense, "offense_logo_url": None,
        "offense_color_on_light": color, "offense_color_on_dark": color,
        "offense_color_source": source,
        "opponent_team_display": "Other",
        "drive_result": result, "drive_result_key": key or result.lower().replace(" ", "_"),
        "drive_result_category": category,
        "scoring_side": scoring_side, "is_scoring_drive": scoring,
        "plays": 5, "yards": end - start, "elapsed_display": "2:00",
        "start_period": period, "start_clock_display": clock,
        "start_yardline": absolute(start), "end_yardline": absolute(end),
        "start_yards_from_own_goal": start, "end_yards_from_own_goal": end,
        "start_offense_score": off_score[0], "end_offense_score": off_score[1],
        "start_defense_score": def_score[0], "end_defense_score": def_score[1],
        "is_end_on_field": on_field, "is_negative_drive": end < start,
        "as_of_ts": pd.Timestamp("2026-09-08T00:00:00Z"),
    }


def _text(entries):
    """The panel's TEXT — captions, headings, states.

    ⚠️ IT SKIPS THE CHART OBJECT. `captured.events` carries `("chart", HConcatChart)` since
    B133, and a regex over that raises rather than returning nothing — a test helper that
    crashes on the thing the panel now mostly IS would send a later round looking in the
    wrong place. **The chart is read through `_spec`, deliberately and by layer.**
    """
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body))
                    for _kind, body in entries if isinstance(body, str))


# --- 🚨 READING THE CHART, AND EVERY HELPER IS SCOPED TO ONE ELEMENT (cfdb-main-R-1170) -----
#
# **B131 asserted that a caption NAMED a measure by searching the WHOLE panel, and every
# measure's label was already on the panel as a table row — so the assertion was true whether
# or not the caption named anything. B132's break 5 proved it green.**
#
# 🚨 **THIS PANEL IS BUILT FOR THAT TRAP: the team name, the quarter, the result and the score
# each appear in a TABLE, in a TOOLTIP, and in the LEGEND CAPTION.** A test that greps the spec
# for `"defense"` passes on a panel that credits a pick-six to the offense, because the word is
# in the legend. ✅ **So nothing below searches the spec as text. Every assertion reads the rows
# of ONE named layer, or ONE panel's encoding.**

_AWAY, _FIELD, _HOME = 0, 1, 2          # hconcat panel order
_GRID, _BARS, _ICONS = 0, 1, 2          # field layer order


def _spec(charts):
    """The one hconcat spec this panel draws, asserted to be one."""
    specs = list(charts)
    assert len(specs) == 1, f"expected exactly one chart, got {len(specs)}"
    spec = specs[0]
    assert len(spec.get("hconcat", [])) == 3, (
        f"expected three panels (away table, field, home table), "
        f"got {len(spec.get('hconcat', []))}")
    return spec


def _layer_rows(spec, panel, layer):
    """The DATA ROWS one named layer plots — not the whole spec, and not text."""
    node = spec["hconcat"][panel]["layer"][layer]
    name = node["data"]["name"]
    return spec["datasets"][name]


def _field_rows(spec):
    """The drives the FIELD draws a bar for. A row absent here is a row with no position."""
    return _layer_rows(spec, _FIELD, _BARS)


def _absence_layers(spec):
    """The field's extra text layers — the `position unavailable` branch, if it drew."""
    return spec["hconcat"][_FIELD]["layer"][_ICONS + 1:]


def _table_rows(spec, panel):
    """The rows one side's table draws. Its first layer is the `#` column."""
    return _layer_rows(spec, panel, 0)


def _row_for(rows, drive_number):
    """One drive's row out of a layer's data, by drive number."""
    hits = [r for r in rows if r.get("drive_number") == drive_number]
    assert len(hits) == 1, (
        f"expected drive {drive_number} exactly once in this layer, found {len(hits)}")
    return hits[0]


# --- it draws the drives -------------------------------------------------------------------

def test_every_drive_is_drawn(panel):
    """The regression this file is named for: the panel silently stopping.

    ⚠️ RE-EXPRESSED AGAINST THE CHART IN B133 — the intent is unchanged. It used to count
    markdown rows carrying `border-left`; v01 draws one bar per drive instead, so the count is
    taken off the bar layer's own data.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt"),
                          _drive(2, "away", "Beta", "PUNT", category="punt"),
                          _drive(3, "home", "Alpha", "FG", category="offensive score",
                                 scoring_side="offense", scoring=True)])
    entries, charts = panel(frame)
    rows = _field_rows(_spec(charts))
    assert len(rows) == 3, f"expected one bar per drive, drew {len(rows)}"
    assert {r["drive_number"] for r in rows} == {1, 2, 3}
    body = _text(entries)
    assert "3 drives" in body and "1 scoring" in body


def test_scoring_drives_are_distinguishable_at_a_glance(panel):
    """The whole point of the artefact — a scoring drive must not render identically to a punt.

    ⚠️ IN v01 THE DISTINCTION IS THE ICON'S SHAPE, NOT A BACKGROUND TINT, and that is a
    deliberate move rather than a loss: AC-G.22 asks for shape before colour, and the drive's
    colour is already spent on the team (Marc's *"Color the drive by the team color"*).
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt"),
                          _drive(2, "home", "Alpha", "TD", category="offensive score",
                                 scoring_side="offense", scoring=True)])
    rows = _field_rows(_spec(panel(frame)[1]))
    punt = _row_for(rows, 1)["result_shape"]
    score = _row_for(rows, 2)["result_shape"]
    assert punt != score, (
        f"a punt and a touchdown drew the SAME shape ({punt!r}) — the result icon carries no "
        f"information and the colour cannot carry it, because the colour is the team's")


def test_a_defense_touchdown_is_not_credited_to_the_offense(panel):
    """🚨 THE ONE THAT MATTERS. `INT TD` means the DEFENSE scored.

    A panel keying off the substring "TD" marks this as an offensive score and puts every one
    of them on the wrong side of the game — while looking entirely healthy. 📊 Re-counted at
    B133's base: **1,209 drives carry `scoring_side = 'defense'` and 2,845 (3.35%) put points
    on the defense's board.**

    🚨 **AND THIS TEST MAY NOT SEARCH THE SPEC FOR THE WORD "defense" — cfdb-main-R-1170.**
    The result legend caption contains *"◀ defensive score"* on every render, so a text search
    passes on a panel that gets this exactly backwards. **Both assertions below read ONE
    drive's own fields.**
    """
    frame = pd.DataFrame([
        _drive(1, "home", "Alpha", "INT TD", key="interception_return_td",
               category="defensive score", scoring_side="defense", scoring=True,
               off_score=(0, 0), def_score=(0, 7)),
        _drive(2, "home", "Alpha", "TD", key="touchdown", category="offensive score",
               scoring_side="offense", scoring=True, off_score=(0, 7), def_score=(0, 0))])
    rows = _field_rows(_spec(panel(frame)[1]))
    pick_six, offensive = _row_for(rows, 1), _row_for(rows, 2)

    # 🚨 LITERALS, NOT A DIFFERENCE TEST, AND NOT A LOOKUP IN THE MODULE. B133 staged the
    # break that swaps the two score shapes — both stay distinct and all seven categories keep
    # a shape, so the vocabulary test cannot see it — and **the first version of this
    # assertion, `pick_six != offensive`, CAME BACK GREEN.** A swap keeps them different.
    # ⚠️ Reading `_DRIVE_RESULT_SHAPES` instead would move the expectation with the defect
    # (R-768). **So the two marks are pinned by name here: changing which shape means
    # *defense* is a DECISION, and it should cost a deliberate edit to this line.**
    assert offensive["result_shape"] == "triangle-right", (
        f"an offensive touchdown drew {offensive['result_shape']!r}")
    assert pick_six["result_shape"] == "triangle-left", (
        f"a pick-six drew {pick_six['result_shape']!r} — the shape that means *the offense "
        f"scored* is pointing the other way, so the picture credits the score to whoever "
        f"had the ball")
    # 🚨 AND THE SIGN IS THE HALF A SHAPE CANNOT CARRY. Score Impact reads BOTH sides, so a
    # drive that put seven on the OPPONENT's board must cost this offense seven.
    assert pick_six["impact_label"].startswith("-"), (
        f"a pick-six shows Score Impact {pick_six['impact_label']!r} in the DRIVING team's "
        f"row — a column reading only the offense delta shows 0 or +7 here, which tells a "
        f"reader the drive helped them")
    assert offensive["impact_label"] == "+7", (
        f"an offensive touchdown shows {offensive['impact_label']!r}")


def test_each_band_takes_its_own_colour(panel):
    """Both bands must not collapse to one accent.

    ⚠️ THE SOURCE OF THE COLOUR CHANGED IN B133 and the intent did not. It used to be recovered
    from the OTHER band's `opponent_color_*` because `srv_drive` had no `offense_color_*`; those
    columns exist now, so each band reads its own.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt", color="#aa0000"),
                          _drive(2, "away", "Beta", "PUNT", category="punt", color="#0000bb")])
    rows = _field_rows(_spec(panel(frame)[1]))
    accents = {_row_for(rows, 1)["accent"], _row_for(rows, 2)["accent"]}
    assert len(accents) == 2, f"both bands rendered the same accent: {accents}"


def test_a_ONE_SIDED_GAME_STILL_COLOURS_THE_SIDE_THAT_PLAYED(panel):
    """🚨 THE FAILURE MODE THE OLD RECOVERY HAD AND THE NEW PATH DOES NOT.

    The old `_drive_colors` read a band's colour off the COMPLEMENTARY band and skipped the
    band entirely when that one was empty — `if other.empty: continue`. **Possession
    alternating is an assumption about football, not a property of the frame**, and a frame
    holding only one side's drives got no colour at all.

    ⚠️ This is a NEW assertion rather than a re-expressed one, because the old rendering could
    not have passed it.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt", color="#aa0000"),
                          _drive(2, "home", "Alpha", "PUNT", category="punt", color="#aa0000")])
    rows = _field_rows(_spec(panel(frame)[1]))
    accent = _row_for(rows, 1)["accent"]
    assert accent and accent != "#6b6b68", (
        f"a game with only one side's drives drew accent {accent!r} — the colour recovery "
        f"needs the other band to exist, which is the defect this replaced")


def test_an_off_field_end_coordinate_keeps_the_row_and_drops_the_bar(panel):
    """0.139% of drives carry a broken end coordinate — measured at this base, 118 of 84,838.

    A missing possession is a worse lie than a bar that admits it does not know where it ended.
    ⚠️ **A REWRITE IS EXACTLY HOW THIS BRANCH GETS LOST SILENTLY (R-141's family), so it is
    asserted in both directions: absent from the bars, present in its own text layer.**
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "TD", category="offensive score",
                                 end=93, on_field=False),
                          _drive(2, "away", "Beta", "PUNT", category="punt")])
    spec = _spec(panel(frame)[1])
    bars = _field_rows(spec)
    assert {r["drive_number"] for r in bars} == {2}, (
        "a drive with a broken end coordinate was given a bar, which draws a position cfdb "
        "does not know")
    extra = _absence_layers(spec)
    assert extra, "the drive with no position vanished from the field entirely"
    said = [layer for layer in extra
            if layer.get("encoding", {}).get("text", {}).get("value") == "position unavailable"]
    assert said, f"no layer says the position is unavailable: {extra}"
    drawn = _layer_rows(spec, _FIELD, _ICONS + 1)
    assert {r["drive_number"] for r in drawn} == {1}, (
        "the absence layer drew the wrong drives")
    # AND THE ROW SURVIVES IN ITS OWN TABLE, which is the half that makes it a kept row rather
    # than a kept pixel.
    assert 1 in {r["drive_number"] for r in _table_rows(spec, _HOME)}


def test_a_fallback_colour_is_named_rather_than_silently_neutral(panel):
    """Degraded is not Empty. The drives are all here; a side's colour is cfdb's.

    ⚠️ IT NAMES THE TEAM WHOSE COLOUR FELL BACK NOW, not that team's opponent — the sentence
    reads `offense_color_source` off the side's own row.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt",
                                 color="#6b6b68", source="fallback"),
                          _drive(2, "away", "Beta", "PUNT", category="punt")])
    entries, charts = panel(frame)
    captions = " ".join(b for k, b in entries if k == "caption")
    assert "cfdb's rather than the team's" in captions
    assert "Alpha" in captions, (
        f"the caption must name the side whose colour fell back, not its opponent: {captions!r}")
    assert len(_field_rows(_spec(charts))) == 2, "a degraded colour must not drop the drives"


def test_SCORE_IMPACT_REFUSES_A_FIGURE_THAT_CONTRADICTS_THE_DRIVES_OWN_RESULT(panel):
    """🚨 THE RENDER CAUGHT THIS COLUMN LYING, AND NO ASSERTION HERE WOULD HAVE.

    The first version printed the bare snapshot delta. The Jacksonville State at Ohio overtime
    render showed **a PUNT worth `+7`, a MISSED FG worth `+13` and a TOUCHDOWN worth `0`** —
    every one of them straight from the published score columns.

    📊 **The snapshots are incoherent across 3 of that game's possession flips**: possession
    alternates, so `end_offense_score(N)` must equal `start_defense_score(N+1)`, and on drive 5
    an Ohio punt runs `0 → 31`. **The window some snapshots cover is not the drive.**

    ✅ So the delta is cross-checked TWICE: against `is_scoring_drive` — published separately
    and derived from the RESULT rather than from the scoreboard — and against the set of values
    one scoring play can actually produce. 📊 **The first fires on 2,306 drives (2.72%); the
    second on a further 699 (0.82%); a figure is printed on 96.46%.**

    ⚠️ **THE SECOND GUARD EXISTS BECAUSE THE FIRST ONE SHIPPED AND THE RENDER STILL SHOWED A
    FIELD GOAL WORTH `-4`** — the two facts agreed that the drive scored, so the cross-check
    passed it, and `-4` is not a number any scoring play can produce.

    ⚠️ **AC-G.11: a wrong number and a missing number are different, and only one misleads.**
    """
    frame = pd.DataFrame([
        # a TOUCHDOWN whose snapshots did not move — the real defect, drive 9 of that game
        _drive(1, "home", "Alpha", "TD", key="touchdown", category="offensive score",
               scoring_side="offense", scoring=True, off_score=(17, 17), def_score=(14, 14)),
        # a PUNT whose snapshots moved by a touchdown — drive 5 of that game
        _drive(2, "home", "Alpha", "PUNT", key="punt", category="punt",
               scoring=False, off_score=(0, 31), def_score=(7, 31)),
        # and a drive where the two facts AGREE, which must still print
        _drive(3, "home", "Alpha", "FG", key="field_goal", category="offensive score",
               scoring_side="offense", scoring=True, off_score=(0, 3), def_score=(0, 0)),
        # a FIELD GOAL worth -4: both facts agree it scored, and no play produces -4. This is
        # the row the FIRST guard let through and the render caught.
        _drive(4, "home", "Alpha", "FG", key="field_goal", category="offensive score",
               scoring_side="offense", scoring=True, off_score=(0, 0), def_score=(0, 4))])
    rows = _table_rows(_spec(panel(frame)[1]), _HOME)
    flat_td = _row_for(rows, 1)["impact_label"]
    moving_punt = _row_for(rows, 2)["impact_label"]
    honest_fg = _row_for(rows, 3)["impact_label"]

    assert flat_td == fmt.EM_DASH, (
        f"a scoring drive whose snapshots did not move printed {flat_td!r} — a touchdown worth "
        f"nothing is a false statement, and `0` is the one value that looks deliberate")
    assert moving_punt == fmt.EM_DASH, (
        f"a punt printed {moving_punt!r} — the snapshot window covered somebody else's score "
        f"and the column credited it to this drive")
    assert honest_fg == "+3", (
        f"a field goal whose snapshots agree printed {honest_fg!r} — the guard must suppress "
        f"the contradictions, not the column")
    illegal = _row_for(rows, 4)["impact_label"]
    assert illegal == fmt.EM_DASH, (
        f"a field goal printed {illegal!r} — both facts agreed the drive scored, so the "
        f"result cross-check passes it, and no scoring play produces that number")


# --- 🚨 PART 1: ONE AXIS SYSTEM, AND ONLY ONE PANEL PINS IT --------------------------------

def test_THE_THREE_PANELS_SHARE_ONE_AXIS_and_only_the_field_pins_it(panel):
    """> **MARC:** *"I would think about the tables as features of a graph on the same axis
    > system, using coordinates to align everything - instead of 3 different elements trying
    > to be aligned."*

    🚨 **A156's RULE, AND ITS FIRST INSTRUMENT WAS WORTHLESS (cfdb-main-R-1105): it pinned the
    same domain on both halves, and the `independent` negative control AGREED — two independent
    scales over one domain at one height produce identical pixels.** ✅ **What makes the
    measurement discriminating is what makes the design correct: ONE panel pins, the others
    inherit.** So this asserts the asymmetry, not the equality.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt"),
                          _drive(2, "away", "Beta", "PUNT", category="punt"),
                          _drive(3, "home", "Alpha", "TD", category="offensive score")])
    spec = _spec(panel(frame)[1])
    assert spec.get("resolve", {}).get("scale", {}).get("y") == "shared", (
        f"the three panels do not share a y scale, so the tables are aligned by arithmetic — "
        f"the thing Marc's last sentence rejects: {spec.get('resolve')}")

    def pinned(index):
        return [layer["encoding"]["y"]["scale"]
                for layer in spec["hconcat"][index].get("layer", [])
                if "scale" in layer.get("encoding", {}).get("y", {})]

    assert pinned(_FIELD), "the field pins no y domain, so nothing anchors the shared scale"
    for side, name in ((_AWAY, "away"), (_HOME, "home")):
        assert not pinned(side), (
            f"the {name} table declares its own y scale {pinned(side)} — a domain with three "
            f"homes drifts, and it also makes this test unable to fail")


def test_A_TABLE_ROW_SITS_AT_ITS_OWN_DRIVES_INDEX_leaving_gaps_for_the_other_side(panel):
    """The alignment Marc actually asked for: a table row level with ITS drive in the graph.

    ⚠️ **THE GAPS ARE THE FEATURE.** A side's table holds only that side's drives, plotted at
    the y of their drive in the FULL sequence — so a blank row is the other team having the
    ball. A table that packed its rows 1..N would look tidier and would no longer line up.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt"),
                          _drive(2, "away", "Beta", "PUNT", category="punt"),
                          _drive(3, "away", "Beta", "TD", category="offensive score"),
                          _drive(4, "home", "Alpha", "FG", category="offensive score")])
    spec = _spec(panel(frame)[1])
    assert {r["drive_number"] for r in _table_rows(spec, _AWAY)} == {2, 3}
    assert {r["drive_number"] for r in _table_rows(spec, _HOME)} == {1, 4}
    # AND THE TEAM'S OWN NUMBER RESTARTS PER SIDE — Marc's *"Drive # for the team"*, which
    # `drive_number` is not: it runs 1..N across BOTH teams (measured, per game).
    away = {r["drive_number"]: r["team_drive"] for r in _table_rows(spec, _AWAY)}
    assert away == {2: 1, 3: 2}, (
        f"the away table's drive numbers are {away} — Marc asked for the TEAM's drive number "
        f"and `drive_number` is per GAME")


# --- 🚨 PART 0: ONE FIELD, TWO DIRECTIONS, NOTHING MIRRORED --------------------------------

def test_THE_FIELD_IS_120_YARDS_AND_THE_DATA_IS_INSET_BY_TEN(panel):
    """Marc: *"from end of goal to the other end of the goal (120 yrds)"*.

    📊 The coordinates run 0–100 and never leave it, so the end zones are ten yards of real
    space the data arrives at rather than occupies — home touchdowns end at `yardline` 100 on
    9,236 drives, away at 0 on 6,193.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "TD", category="offensive score",
                                 start=0, end=100)])
    spec = _spec(panel(frame)[1])
    x_scales = [layer["encoding"]["x"]["scale"]
                for layer in spec["hconcat"][_FIELD]["layer"]
                if "scale" in layer.get("encoding", {}).get("x", {})]
    assert x_scales, "the field declares no x domain"
    assert all(s["domain"] == [0, 120] for s in x_scales), (
        f"the field is not 120 yards wide: {x_scales}")
    row = _row_for(_field_rows(spec), 1)
    assert (row["x"], row["x_end"]) == (10, 110), (
        f"a goal-line-to-goal-line drive spans {row['x']}…{row['x_end']} — the data must be "
        f"inset by the end zone, so 0 sits at 10 and 100 at 110")


def test_THE_TWO_SIDES_ATTACK_OPPOSITE_ENDS_so_the_away_band_is_not_mirrored(panel):
    """🚨 PART 0's PROOF, IN THE RENDER RATHER THAN IN THE WAREHOUSE.

    📊 **Measured on all 84,838 published rows: `start_yardline == start_yards_from_own_goal`
    on 42,233 of 42,233 home drives, and `== 100 − start_yards_from_own_goal` on 42,605 of
    42,605 away drives.** So `yardline` is ONE absolute frame, and on it the two sides drive in
    opposite directions — which is what a shared field means.

    ⚠️ **THE OLD PANEL'S DOCSTRING WARNED THAT A BAR KEYED OFF `yardline` *"mirrors the away
    band and reads as a rendering fault"*. THAT WARNING IS ABOUT MIXING THE TWO FRAMES and it is
    correct; it is not an argument against the absolute frame.** This test is what tells the two
    apart: both drives below gain 40 yards, and their bars must run in OPPOSITE directions.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt", start=20, end=60),
                          _drive(2, "away", "Beta", "PUNT", category="punt", start=20, end=60)])
    rows = _field_rows(_spec(panel(frame)[1]))
    home, away = _row_for(rows, 1), _row_for(rows, 2)
    assert home["x_end"] > home["x"], (
        f"the home team gained 40 yards and its bar ran backwards: {home['x']}→{home['x_end']}")
    assert away["x_end"] < away["x"], (
        f"the away team gained 40 yards and its bar ran the SAME WAY as the home team's "
        f"({away['x']}→{away['x_end']}) — the away band is mirrored, which is the rendering "
        f"fault the absolute frame exists to avoid")


# --- 🚨 PART 4: THE RESULT ICON COVERS EVERY PUBLISHED CATEGORY ----------------------------

def test_EVERY_DRIVE_RESULT_CATEGORY_HAS_ITS_OWN_SHAPE(panel):
    """Marc: *"Use an icon on the end to indicate the result (outcome)"*.

    📊 **Counted at this base rather than trusted: `drive_result_key` carries 23 distinct values
    across 7 `drive_result_category` values on 84,838 rows.** ⚠️ **The panel this replaced said
    *"ten drive_result values"* in two docstrings and this file's own header — wrong by more
    than a factor of two.**

    🚨 **AC-G.22: the shapes must differ from EACH OTHER, because the colour is the team's and
    carries nothing about the result.** A vocabulary with two categories sharing a shape is a
    reader unable to tell a turnover from a punt in greyscale.
    """
    shapes = _module_constant("_DRIVE_RESULT_SHAPES")
    published = {"punt", "offensive score", "turnover", "clock",
                 "kick", "defensive score", "unknown"}
    assert set(shapes) == published, (
        f"the icon vocabulary and the published categories disagree: "
        f"missing {published - set(shapes)}, extra {set(shapes) - published}")
    assert len(set(shapes.values())) == len(shapes), (
        f"two categories share a shape, so they are indistinguishable without colour: {shapes}")
    # and an unrecognised category falls to the unclassified mark rather than borrowing a look
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "???", category="something new")])
    row = _row_for(_field_rows(_spec(panel(frame)[1])), 1)
    assert row["result_shape"] == _module_constant("_DRIVE_RESULT_UNKNOWN"), (
        f"an unknown category drew {row['result_shape']!r}, borrowing one of the seven looks "
        f"instead of reading as unclassified (AC-G.11)")


def test_A_PERIOD_ZERO_IS_AN_ABSENCE_not_a_quarter(panel):
    """📊 `start_period` carries `0` on 24 of 84,838 rows and `_models.yml` calls it *"a defect
    rather than a period"*. **All 24 also carry a null `start_clock_display`** — one absence,
    measured, not two.

    🚨 **AND THE QUARTER COMES OFF THE PUBLISHED CLOCK STRING, NOT OFF A FORMATTER.** This
    round wrote a `_drive_period_label` that turned period 5 into `OT`, before measuring what
    `start_clock_display` contains — **84,461 rows already start `Qn …` and 252 already say
    `OT`/`2OT`** — and the first render printed *"Q1 Q1 5:07"*. The helper is deleted and this
    test pins the column's own strings, so a second formatter cannot come back.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt",
                                 period=0, clock=None),
                          _drive(2, "home", "Alpha", "PUNT", category="punt",
                                 period=5, clock="OT"),
                          _drive(3, "home", "Alpha", "PUNT", category="punt",
                                 period=1, clock="Q1 5:07")])
    rows = _table_rows(_spec(panel(frame)[1]), _HOME)
    broken = _row_for(rows, 1)["when"]
    overtime = _row_for(rows, 2)["when"]
    regulation = _row_for(rows, 3)["when"]

    assert "Q0" not in broken and "0:" not in broken.split("(")[0], (
        f"period 0 rendered as {broken!r} — a quarter zero is a defect, not a period")
    assert broken.startswith(fmt.EM_DASH), (
        f"period 0 must read as an absence, not as a number: {broken!r}")
    assert "(" in broken, (
        f"the absence dropped the duration too, which IS published here: {broken!r}")
    # AND THE PERIOD IS NOT PRINTED TWICE — the defect the first render shipped.
    assert regulation.count("Q1") == 1, (
        f"the quarter is printed twice: {regulation!r}. `start_clock_display` already carries "
        f"it, so prefixing a formatted period duplicates the column")
    assert overtime.startswith("OT"), (
        f"an overtime drive rendered as {overtime!r} — the published clock says OT")


# --- and it says so when it cannot ---------------------------------------------------------

def test_no_drives_is_empty_not_a_blank_panel(panel):
    """Empty is a state with a sentence, never a zero-row render.

    ⚠️ DRIVEN AT 2023 EXPLICITLY SINCE R-730. This test's claim is the SCOPE one — "we
    collect from 2024 onward" — and it used to pass on copy that never looked at the season,
    so it could not have failed if the sentence was wrong for a modern game. It was. The
    2026 branch is asserted separately below.
    """
    entries, _charts = panel(pd.DataFrame(), season=2023)
    body = _text(entries)
    assert "2024" in body, "the Empty state must say why there are none"
    assert not [b for k, b in entries if k == "chart"], \
        "an empty frame must draw no chart at all, only the Empty state"


# --- the query stays inside the app's rules ------------------------------------------------

def test_the_query_is_one_table_scoped_to_a_game_and_bounded():
    """AC-G.3 and AC-G.39, asserted on the source so a rewrite cannot quietly widen it.
    srv_drive is 81,433 rows; an unscoped read of it is the defect."""
    source = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()
    block = source[source.index("def _drives("):source.index("def render()")]
    sql = block[block.index("select drive_number"):block.index('""", {"game_id"')]
    assert sql.lower().count(" from ") == 1 and "join" not in sql.lower()
    assert "where game_id = :game_id" in sql
    assert re.search(r"\blimit\s+\d+", sql, re.I), "an unbounded select is a defect (AC-G.39)"


# --- 🚨 R-730: WHICH absence is this? ------------------------------------------------------
#
# A112 rendered `401856679` — Michigan vs Oklahoma, `is_completed = True`, kicked off 9:00 AM
# PDT — six hours after kickoff and this panel said:
#
#     "Drives are collected from 2024 onward, and a game that has not kicked off yet has none."
#
# ⚠️ FLATLY FALSE, AND UNREACHABLE COPY BESIDES. `_available_tabs` gives an unplayed game no
# after tab, so this panel cannot be reached before kickoff at all — proved in
# test_matchup_tabs by `test_a_scheduled_game_renders_no_after_tab_at_all` and
# `test_after_tab_requested_on_a_scheduled_game_falls_back_and_does_not_raise`. TWO states
# reach here, not three, and until now they shared one sentence.

def test_the_two_absences_do_not_share_a_sentence(panel):
    """🚨 THE ASSERTION THE OBVIOUS VERSION CANNOT MAKE.

    Checking that the copy contains "not arrived yet" passes on a panel that picked the
    branch by accident. Driving BOTH seasons through the same empty frame and asserting the
    two differ is what actually proves the season decides it.
    """
    out_of_scope = _text(panel(pd.DataFrame(), season=2023)[0])
    not_yet = _text(panel(pd.DataFrame(), season=2026)[0])
    assert out_of_scope != not_yet, (
        "a 2023 game and a 2026 game were told the same thing about why there are no drives, "
        "which is the R-730 defect: one is permanent scope and the other is latency")


def test_a_completed_modern_game_is_told_the_data_has_not_LANDED(panel):
    """The state nothing said until now: 2024+, the game is over, the drives have not arrived.

    ⚠️ THE WINDOW IS THE POINT — it opens when the game ends and closes when the next
    collection lands, which is exactly when a reader opens the page to see what happened.
    """
    body = _text(panel(pd.DataFrame(), season=2026)[0])
    assert "kicked off" not in body, (
        "the panel told a reader of a FINISHED game that it had not kicked off yet — this is "
        "the exact sentence A112 rendered on a game that ended six hours earlier")
    assert "2024 onward" not in body, (
        "scope is the wrong reason for a 2026 game and offering it sends the reader away "
        "believing cfdb will never hold this")
    assert "not arrived yet" in body and "after the game" in body, (
        f"the reader was not told when to come back: {body!r}")


def test_a_pre_2024_game_is_still_told_it_is_out_of_SCOPE(panel):
    """The other branch, unchanged in substance: for 1999 the drives are never coming."""
    body = _text(panel(pd.DataFrame(), season=1999)[0])
    assert "2024 onward" in body, "a pre-2024 game must still be told this is scope"
    assert "not arrived yet" not in body, (
        "a 1999 game was told its drives have not arrived YET, which promises data that will "
        "never exist")
