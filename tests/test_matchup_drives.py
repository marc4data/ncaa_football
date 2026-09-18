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
a kick means the DEFENSE scored — so a panel that reads the result TEXT rather than
`scoring_side` puts every one of them on the wrong side of the game, and does it while looking
entirely healthy.

🚨 **THAT SENTENCE USED TO READ *"908 drives across ten drive_result values"* AND BOTH NUMBERS
WERE STALE.** Re-counted on live published serving: **1,209 drives carry `scoring_side =
'defense'`, 2,845 (3.35%) put points on the defense's board, and `drive_result_key` carries 23
distinct values across 7 categories on 84,838 rows** — the display column `drive_result` has
25 distinct strings. ⚠️ **The "ten" was true of an earlier and smaller population and had been
copied into two docstrings and this header** (R-727's class: a stale count nobody re-measures
gets inherited by whoever reads it next).
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

        def run(frame, season=2026, row=None, encoding=None):
            # R-730. The season decides WHICH absence the Empty state states, so the
            # fixture has to carry one. 2026 is a completed modern game — the case
            # nearly every test here means; the scope tests pass a pre-2024 season.
            #
            # 🚨 **AND v02's THIRD ARGUMENT IS THE `srv_game` ROW, WHICH IS NOT DECORATION.**
            # The scoreboard header reads its SCORE from there because the drives frame's own
            # end scores disagree with the published final on 214 of 3,607 games (5.93%).
            captured.clear()
            # ⚠️ MARC'S TWO YARDLINE ENCODINGS ARE ONE IMPLEMENTATION BEHIND ONE CONSTANT, so
            # a test picks one by name rather than by a second code path (R-574).
            if encoding is not None:
                matchup._DRIVE_YARDLINE_ENCODING = encoding
            # ⚠️ AND THE CHARTS TOO. They used to accumulate across calls while `captured`
            # was cleared, so a test that ran the panel twice and then read the spec got two
            # hconcats and failed with `expected exactly one`. See `Charts.clear`.
            charts.clear()
            original = matchup.query
            matchup.query = lambda *a, **k: frame
            try:
                matchup._drives(9001, season, _game_row() if row is None else row)
            finally:
                matchup.query = original
            # 🚨 R-610. An Error state is not a passing state.
            render_harness.assert_no_error_card(captured, "the drives panel")
            # ⚠️ BOTH HALVES, SINCE B133. v01 draws a CHART, so an assertion about what the
            # panel shows has to reach the chart spec; `_text(entries)` can only see the
            # captions and the subheader now.
            return list(captured.events), charts

        yield run


def _game_row(away="Beta", home="Alpha", away_points=17, home_points=24):
    """The `srv_game` row `_drives` heads its chart with (v02 PART 6).

    ⚠️ **THE SCORES HERE ARE DELIBERATELY NOT THE FIXTURE DRIVES' SCORES.** That is what lets
    `test_THE_SCOREBOARD_READS_THE_GAME_ROW_not_the_drives_frame` tell the two sources apart —
    a header built from the frame would print the drives' numbers and pass a test that only
    checked a scoreboard was present.
    """
    return pd.Series({"away_team": away, "home_team": home,
                      "away_points": away_points, "home_points": home_points,
                      "season": 2026})


def _drive(number, band, offense, result, *, scoring_side=None, scoring=False,
           start=25, end=60, on_field=True, color="#123456", source="primary",
           category="unknown", key=None, period=1, clock="12:00",
           off_score=(0, 7), def_score=(0, 0),
           logo="https://example.test/own.png", opponent_logo="https://example.test/opp.png"):
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
        # 🚨 **THE LOGOS WERE `None` BY DEFAULT AND THAT MADE MARC'S LOGO ENCODING
        # UNTESTABLE — R-744's class exactly.** `_drive_yardline_logo` returned None on every
        # fixture row, so the image layer drew nothing and a test asserting the partition
        # failed with an empty set rather than with the defect it was written for.
        # ⚠️ **Both are parameters, so a test can still take one away**: measured coverage is
        # 99.08% for `offense_logo_url` and 99.10% for `opponent_logo_url`, not 100%.
        "offense_team_display": offense, "offense_logo_url": logo,
        "opponent_logo_url": opponent_logo,
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


def _spec(charts):
    """The one hconcat spec this panel draws, asserted to be one.

    ⚠️ **v02 DRAWS A SECOND CHART — THE RESULT LEGEND — SO THIS PICKS THE PANEL BY SHAPE
    RATHER THAN BY POSITION.** A helper that took `charts[0]` would silently start reading the
    legend the day the order changed, and every assertion below would then be about the wrong
    picture while still passing or failing for reasons nobody could trace.
    """
    hconcats = [s for s in charts if len(s.get("hconcat", [])) == 3]
    assert len(hconcats) == 1, (
        f"expected exactly one three-panel hconcat, got {len(hconcats)} "
        f"among {len(list(charts))} charts")
    return hconcats[0]


def _legend_spec(charts):
    """The result legend, which is a layered chart rather than an hconcat."""
    hits = [s for s in charts if "layer" in s and "hconcat" not in s]
    assert len(hits) == 1, f"expected exactly one legend chart, got {len(hits)}"
    return hits[0]


# 🚨 **EVERY LOOKUP BELOW FINDS A LAYER BY WHAT IT IS, NEVER BY WHERE IT SITS.** v01's helpers
# indexed layers positionally — `_GRID, _BARS, _ICONS = 0, 1, 2` — and v02 inserts a band layer
# under all three panels, a fill under the field and a glyph inside the Result cell. **A
# positional helper does not fail when the layer order moves; it reads a different layer and
# goes on asserting.** That is the same class as cfdb-main-R-1170 one level down: an assertion
# pointed at the wrong element is not a weaker assertion, it is a different one.
def _layers(spec, panel):
    return spec["hconcat"][panel].get("layer", [])


def _rows(spec, node, parent=None):
    """The data rows one layer node plots.

    ⚠️ **ALTAIR HOISTS A DATASET SHARED BY EVERY LAYER UP TO THE PARENT SPEC**, so a layer can
    legitimately carry no `data` of its own. The legend's two layers are built from one frame
    and hit exactly that; a helper that assumed per-layer data raised `KeyError: 'data'`.
    """
    holder = node if "data" in node else (parent if parent is not None else spec)
    return spec["datasets"][holder["data"]["name"]]


def _mark_of(node):
    mark = node.get("mark")
    return mark if isinstance(mark, str) else (mark or {}).get("type")


def _text_field_of(node):
    return ((node.get("encoding", {}) or {}).get("text") or {}).get("field")


def _text_value_of(node):
    return ((node.get("encoding", {}) or {}).get("text") or {}).get("value")


def _only(hits, what):
    assert len(hits) == 1, f"expected exactly one {what}, found {len(hits)}"
    return hits[0]


def _field_rows(spec):
    """The drives the FIELD draws a bar for. A row absent here is a row with no position.

    The bars are the one `rule` layer with a `y` — the gridlines are rules with no y at all.
    """
    return _rows(spec, _only(
        [n for n in _layers(spec, _FIELD)
         if _mark_of(n) == "rule" and "y" in (n.get("encoding") or {})],
        "field bar layer"))


def _field_icons(spec):
    """The result glyphs on the field: the one `point` layer."""
    return _only([n for n in _layers(spec, _FIELD) if _mark_of(n) == "point"],
                 "field icon layer")


def _field_grid(spec):
    """The vertical reference lines: `rule` marks with no y encoding."""
    return _only([n for n in _layers(spec, _FIELD)
                  if _mark_of(n) == "rule" and "y" not in (n.get("encoding") or {})],
                 "field gridline layer")


def _endzone_layer(spec):
    """v02's end-zone fill: a `rect` with an x span and NO y span."""
    return _only([n for n in _layers(spec, _FIELD)
                  if _mark_of(n) == "rect" and "y2" not in (n.get("encoding") or {})],
                 "end-zone fill layer")


def _band_layer(spec, panel):
    """v02's alternating band in one panel: a `rect` that spans y, in every panel."""
    return _only([n for n in _layers(spec, panel)
                  if _mark_of(n) == "rect" and "y2" in (n.get("encoding") or {})],
                 f"band layer in panel {panel}")


def _absence_layers(spec):
    """The field's `position unavailable` branch, if it drew."""
    return [n for n in _layers(spec, _FIELD)
            if _text_value_of(n) == "position unavailable"]


def _table_rows(spec, panel, column="team_drive"):
    """The rows one side's table draws, taken off one NAMED column's text layer.

    ⚠️ **NOT LAYER 0 ANY MORE — THAT IS NOW THE BAND, AND THE BAND CARRIES THE WHOLE FRAME.**
    v01 read `layer[0]` for "this side's rows"; in v02 that layer plots BOTH sides' drives on
    purpose, so the old helper would have reported every drive as belonging to both tables and
    `test_A_TABLE_ROW_SITS_AT_ITS_OWN_DRIVES_INDEX` would have passed while measuring nothing.
    """
    return _rows(spec, _only(
        [n for n in _layers(spec, panel) if _text_field_of(n) == column],
        f"{column} text layer in panel {panel}"))


def _table_heading(spec, panel, heading):
    """One table heading's layer, found by the literal it prints."""
    return _only([n for n in _layers(spec, panel) if _text_value_of(n) == heading],
                 f"{heading!r} heading in panel {panel}")


def _table_glyph_rows(spec, panel):
    """The rows that get Marc's glyph inside the Result cell."""
    return _rows(spec, _only(
        [n for n in _layers(spec, panel) if _mark_of(n) == "point"],
        f"result glyph layer in panel {panel}"))


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
    assert pick_six["impact_cell"].startswith("-"), (
        f"a pick-six shows Score Impact {pick_six['impact_cell']!r} in the DRIVING team's "
        f"row — a column reading only the offense delta shows 0 or +7 here, which tells a "
        f"reader the drive helped them")
    assert offensive["impact_cell"].startswith("+7"), (
        f"an offensive touchdown shows {offensive['impact_cell']!r}")


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
    said = _absence_layers(spec)
    assert said, "no layer says the position is unavailable — the drive vanished entirely"
    drawn = _rows(spec, said[0])
    assert {r["drive_number"] for r in drawn} == {1}, (
        "the absence layer drew the wrong drives")
    # AND THE ROW SURVIVES IN ITS OWN TABLE, which is the half that makes it a kept row rather
    # than a kept pixel.
    assert 1 in {r["drive_number"] for r in _table_rows(spec, _HOME)}


def test_AN_ADJUSTED_COLOUR_AND_A_NEUTRAL_ONE_DO_NOT_SHARE_A_SENTENCE(panel):
    """🚨 **THE RENDER CAUGHT THIS SAYING THE WRONG THING ON 23.22% OF DRIVES.**

    v01 covered both unsourced rungs with one caption: *"is cfdb's rather than the team's, so
    that side is banded in a neutral tone."* 📊 **The Jacksonville State at Ohio raster printed
    it over bars that were plainly RED** — that game's rung is `adjusted`, and `adjusted` is the
    team's own hue darkened or lightened for contrast (`#cc0000`, which is their red), not a
    replacement. ⚠️ **The sentence was false twice: the colour IS the team's, and it is not
    neutral.**

    📊 **THE RUNGS, MEASURED ON ALL 84,838 ROWS:** `alternate` 66.620% · **`adjusted` 23.220%**
    · `primary` 8.839% · **`fallback` 1.321%**. Only `fallback` is a neutral cfdb tone, and it
    is the rarer of the two by a factor of eighteen — **so the wrong sentence was the one almost
    every degraded game got.**

    ✅ **ASSERTED AS A DIFFERENCE, NOT AS TWO PRESENCE CHECKS.** Two captions that both contain
    the team's name and "Every drive below is present" would pass a presence check while saying
    the same wrong thing; driving both rungs through and requiring the sentences to DIFFER is
    what proves the rung decides it (the R-730 shape, one panel over).
    """
    def caption_for(source):
        frame = pd.DataFrame([
            _drive(1, "home", "Alpha", "PUNT", category="punt",
                   color="#cc0000", source=source),
            _drive(2, "away", "Beta", "PUNT", category="punt")])
        entries, charts = panel(frame)
        assert len(_field_rows(_spec(charts))) == 2, "a degraded colour must not drop the drives"
        return " ".join(b for k, b in entries if k == "caption" and b.startswith("Alpha"))

    adjusted, neutral = caption_for("adjusted"), caption_for("fallback")
    assert adjusted and neutral, (
        f"a degraded rung drew no caption at all: adjusted={adjusted!r} neutral={neutral!r}")
    assert adjusted != neutral, (
        f"`adjusted` and `fallback` were given the SAME sentence: {adjusted!r}. One is the "
        f"team's own colour moved for contrast and the other is cfdb's stand-in")
    # AND EACH SAYS THE TRUE THING RATHER THAN MERELY A DIFFERENT THING.
    assert "their own" in adjusted and "neutral" not in adjusted, (
        f"the `adjusted` caption calls the team's own colour something else: {adjusted!r}")
    assert "no color" in neutral and "neutral" in neutral, (
        f"the `fallback` caption does not say the team publishes no colour: {neutral!r}")
    # ⚠️ AND A SOURCED RUNG DRAWS NO CAPTION AT ALL — an indicator that fires on everything
    # indicates nothing, which is `identity.color_source_hint`'s own recorded lesson.
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt",
                                 source="alternate")])
    entries, _charts = panel(frame)
    assert not [b for k, b in entries
                if k == "caption" and b.startswith("Alpha")], (
        "a team using its own published colour was reported as degraded")


def test_THE_SOURCED_RUNGS_ARE_READ_FROM_IDENTITY_not_copied():
    """🚨 `matchup.py` CARRIED `_SOURCED_COLOR_RUNGS = ("primary", "alternate")` WITH A COMMENT
    SAYING *"mirrored from lib.identity"* — **a second inventory of a tuple A's module already
    publishes**, which is the same defect v02 fixed in the result legend.

    ✅ `site/lib/identity.py` is session A's file and `SOURCED_RUNGS` is a public name on it, so
    reading it costs nothing and cannot drift.
    """
    import importlib
    module = importlib.import_module("views.matchup")
    from lib import identity

    # 🚨 ASKED OF THE MODULE, NOT OF ITS TEXT — AND THE FIRST DRAFT OF THIS TEST GOT IT WRONG
    # IN THE EXACT WAY THE CHARTER NAMES. It asserted `"_SOURCED_COLOR_RUNGS" not in source`
    # and went red, because **the name appears in the comment that explains why it was
    # removed.** §2.2.1c.1: a grep locates, it does not tell you what a line IS. `hasattr`
    # asks the only question that matters.
    assert not hasattr(module, "_SOURCED_COLOR_RUNGS"), (
        "the local copy of identity.SOURCED_RUNGS is back as a module attribute; read the "
        "module's own name instead")
    assert identity.SOURCED_RUNGS == ("primary", "alternate"), (
        f"identity's rung list moved to {identity.SOURCED_RUNGS} — this panel's caption splits "
        f"on what is NOT in it, so the split follows A's module by reading it")


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
    flat_td = _row_for(rows, 1)["impact_cell"]
    moving_punt = _row_for(rows, 2)["impact_cell"]
    honest_fg = _row_for(rows, 3)["impact_cell"]

    assert flat_td == fmt.EM_DASH, (
        f"a scoring drive whose snapshots did not move printed {flat_td!r} — a touchdown worth "
        f"nothing is a false statement, and `0` is the one value that looks deliberate")
    assert moving_punt == fmt.EM_DASH, (
        f"a punt printed {moving_punt!r} — the snapshot window covered somebody else's score "
        f"and the column credited it to this drive")
    assert honest_fg.startswith("+3"), (
        f"a field goal whose snapshots agree printed {honest_fg!r} — the guard must suppress "
        f"the contradictions, not the column")
    illegal = _row_for(rows, 4)["impact_cell"]
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

    🚨 **AND THE QUARTER COMES OFF THE PUBLISHED CLOCK STRING, NOT OFF A FORMATTER.** v01 wrote
    a `_drive_period_label` that turned period 5 into `OT`, before measuring what
    `start_clock_display` contains, and its first render printed *"Q1 Q1 5:07"*. The helper is
    deleted and this test pins the column's own strings, so a second formatter cannot come back.

    📊 **THE EXACT PREFIX INVENTORY, RE-MEASURED IN v02 BECAUSE v01's COMMENT DID NOT ADD UP:**
    `Q1` 21,413 · `Q2` 22,472 · `Q3` 21,117 · `Q4` 19,459 = **84,461**; the overtime family
    `OT` 252 · `2OT` 61 · `3OT` 16 · `4OT` 10 · `5OT` 6 · `6OT` 4 · `7OT` 2 · `8OT` 2 = **353**;
    null **24**. ⚠️ **v01 reported the overtime family as 252, which is the bare `OT` prefix
    alone — so its three numbers summed to 84,737, 101 rows short of the population they
    claimed to partition.** ✅ **A sum that misses its own total is the cheapest possible tell.**

    ⚠️ **AND v02 SPLITS MARC'S `When` INTO TWO COLUMNS** — *"Split When into 2 columns: Clock,
    Dur"* — so the absence now has to hold in `Clock` while `Dur` still stands on its own.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt",
                                 period=0, clock=None),
                          _drive(2, "home", "Alpha", "PUNT", category="punt",
                                 period=5, clock="OT"),
                          _drive(3, "home", "Alpha", "PUNT", category="punt",
                                 period=1, clock="Q1 5:07")])
    spec = _spec(panel(frame)[1])
    rows = _table_rows(spec, _HOME, column="clock")
    broken, overtime, regulation = (_row_for(rows, n) for n in (1, 2, 3))

    assert broken["clock"] == fmt.EM_DASH, (
        f"period 0 rendered as {broken['clock']!r} — a quarter zero is a defect, not a period")
    # 🚨 THE DURATION IS PUBLISHED ON ALL 84,838 ROWS AND SURVIVES THE CLOCK'S ABSENCE. In v01
    # the two shared one cell, so losing the clock could have taken the duration with it.
    assert broken["duration"] == "2:00", (
        f"the absent clock took the duration with it: {broken['duration']!r}, and "
        f"`elapsed_display` is present on every published row")
    # AND THE PERIOD IS NOT PRINTED TWICE — the defect v01's first render shipped.
    assert regulation["clock"] == "Q1 5:07", (
        f"the clock cell reads {regulation['clock']!r}. `start_clock_display` already carries "
        f"the quarter, so prefixing a formatted period duplicates the column")
    assert overtime["clock"] == "OT", (
        f"an overtime drive rendered as {overtime['clock']!r} — the published clock says OT")

    # 🚨 AND THE TWO COLUMNS ARE ACTUALLY TWO, WHICH IS THE HALF A FIELD READ CANNOT SEE.
    # A frame carrying `clock` and `duration` proves nothing if the table still draws one
    # cell; these are the headings Marc named, found by the literal each one prints.
    for heading in ("Clock", "Dur"):
        assert _table_heading(spec, _HOME, heading), f"no {heading!r} column heading"


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
    srv_drive is 84,838 rows today; an unscoped read of it is the defect."""
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


# ── 🚨 v02 PART 1: THE STARTING YARDLINE, WHICH MARC FLAGGED THE TRAP ON HIMSELF ────────────

def test_THE_YARDLINE_IS_THE_BROADCAST_YARDLINE_not_yards_to_goal(panel):
    """> **MARC:** *"NOTE: This is the actually yardline on the field, not yards to goal, or
    > any of the other tricky data points you worked through to make the graph display
    > properly."*

    🚨 **THREE PUBLISHED COLUMNS DESCRIBE THIS ONE FACT AND TWO ARE THE WRONG ANSWER.**
    `start_yards_to_goal` is offense-relative and equals `100 - start_yards_from_own_goal` on
    **84,838 of 84,838 rows** — measured — so reading it would put every drive on the wrong
    yardline and the picture would look entirely healthy.

    ✅ **THE NUMBER IS FRAME-INDEPENDENT AND THAT IS WHY THIS IS SAFE: `min(v, 100-v)` computed
    from the relative frame and from the absolute frame agree on 84,838 / 84,838 rows.** The
    SIDE is what needs the relative frame, because "own" is a fact about who has the ball.

    📊 own side 74,027 (87.257%) · opponent side 10,177 (11.996%) · midfield 634 (0.747%).
    """
    frame = pd.DataFrame([
        _drive(1, "home", "Alpha", "PUNT", category="punt", start=25, end=40),
        _drive(2, "home", "Alpha", "PUNT", category="punt", start=70, end=80),
        _drive(3, "home", "Alpha", "PUNT", category="punt", start=50, end=60)])
    rows = _table_rows(_spec(panel(frame)[1]), _HOME, column="yardline_mark")
    own, opponent, midfield = (_row_for(rows, n) for n in (1, 2, 3))

    # 🚨 PINNED TO LITERALS, AND THE 70 IS THE ONE THAT MATTERS. `start_yards_from_own_goal =
    # 70` is the OPPONENT's 30. A panel reading `start_yards_to_goal` would print 30 with the
    # wrong SIDE; one printing the raw column would say 70, which is not a yardline at all.
    assert own["yardline_mark"] == "-25", (
        f"a drive starting 25 yards from its own goal reads {own['yardline_mark']!r} — Marc's "
        f"`-` means the offense's own half and the number is the yardline")
    assert opponent["yardline_mark"] == "+30", (
        f"a drive starting 70 yards from its own goal reads {opponent['yardline_mark']!r}. "
        f"The broadcast yardline there is the OPPONENT's 30: `+30`. "
        f"`+70` would be the raw column and `-30` would be the wrong half")
    assert midfield["yardline_mark"] == "50", (
        f"midfield reads {midfield['yardline_mark']!r} — it belongs to NEITHER side, so giving "
        f"it a sign claims a half it does not have (634 drives start there)")


def test_THE_GOAL_LINE_IS_NAMED_rather_than_printed_as_a_zero(panel):
    """📊 **413 drives (0.487%) start ON a goal line** — 193 at own-goal `0` and 220 at `100`.

    ⚠️ **A FOOTBALL FIELD CARRIES NO `0` MARKER**, so `-0` and `+0` would read as a formatting
    fault rather than as a position. This is the one place in the vocabulary a letter appears.
    """
    frame = pd.DataFrame([
        _drive(1, "home", "Alpha", "PUNT", category="punt", start=0, end=20),
        _drive(2, "home", "Alpha", "TD", category="offensive score", start=100, end=100)])
    rows = _table_rows(_spec(panel(frame)[1]), _HOME, column="yardline_mark")
    own_goal, opponent_goal = _row_for(rows, 1), _row_for(rows, 2)
    mark = _module_constant("_DRIVE_GOAL_MARK")
    assert own_goal["yardline_mark"] == "-" + mark, (
        f"a drive starting on its own goal line reads {own_goal['yardline_mark']!r}")
    assert opponent_goal["yardline_mark"] == "+" + mark, (
        f"a drive starting on the opponent's goal line reads "
        f"{opponent_goal['yardline_mark']!r}")
    for row in (own_goal, opponent_goal):
        assert "0" not in row["yardline_mark"], (
            f"{row['yardline_mark']!r} prints a zero yardline, which no field carries")


def test_THE_TOOLTIP_NAMES_THE_SIDE_IN_WORDS_because_it_cannot_carry_a_logo(panel):
    """🚨 **MARC ASKED FOR A LOGO IN THE TOOLTIP AND A VEGA TOOLTIP CANNOT RENDER ONE.**

    > *"I like the tooltip on hover. Needs to include the yard the drive started on. Need to
    > probably use a logo to indicate which side of the 50."*

    📊 **MEASURED RATHER THAN ASSERTED (§2.4): a tooltip field whose value was
    `<img src=…>` was hovered in Chromium and read back out of the DOM. `vega-tooltip`
    escapes it — the text came through as `&lt;img src=…&gt;` with **0 `<img>` elements**
    inside `#vg-tooltip-element`.** ✅ **So the team's NAME does the logo's job there**, which
    is also what a broadcast caption says out loud.

    ⚠️ **AND THE ASSERTION IS SCOPED TO THE TOOLTIP, NOT TO THE PANEL (cfdb-main-R-1170).**
    Every team name is already on the panel in the scoreboard, the direction caption and the
    degraded caption, so a text search for `"Alpha"` passes on a tooltip that names nothing.
    """
    frame = pd.DataFrame([
        _drive(1, "home", "Alpha", "PUNT", category="punt", start=25, end=40),
        _drive(2, "home", "Alpha", "PUNT", category="punt", start=70, end=80),
        _drive(3, "home", "Alpha", "PUNT", category="punt", start=50, end=60)])
    spec = _spec(panel(frame)[1])

    # the tooltip is an ENCODING on the bar layer, so this reads the encoding rather than text
    bars = _only([n for n in _layers(spec, _FIELD)
                  if _mark_of(n) == "rule" and "y" in (n.get("encoding") or {})], "bar layer")
    fields = [t.get("field") for t in bars["encoding"]["tooltip"]]
    assert "yardline_words" in fields, (
        f"the bar tooltip does not carry the starting yardline Marc asked for: {fields}")

    rows = _field_rows(spec)
    own, opponent, midfield = (_row_for(rows, n) for n in (1, 2, 3))
    assert own["yardline_words"] == "Alpha the 25", (
        f"the tooltip says {own['yardline_words']!r} — it must name the team whose half it is")
    assert opponent["yardline_words"] == "Other the 30", (
        f"the tooltip says {opponent['yardline_words']!r} — 70 yards from your own goal is the "
        f"OPPONENT's 30, and the tooltip has room to say whose")
    assert midfield["yardline_words"] == "Midfield 50", (
        f"the tooltip says {midfield['yardline_words']!r} for a drive starting at the 50")


# ── 🚨 v02 PART 3: THE BANDS, WHICH ARE WHAT MAKE THE SHARED AXIS VISIBLE ───────────────────

def test_THE_BANDS_LINE_UP_ACROSS_ALL_THREE_PANELS(panel):
    """> **MARC:** *"an alternating band (light gray/white) … a slightly darker border"*

    🚨 **UNDER `hconcat` THE THREE PANELS ARE SEPARATE VIEWS, SO EACH DRAWS ITS OWN BAND —
    AND THEY MUST COME FROM ONE COMPUTATION** (cfdb-wta-R-941). Three independently derived
    parities drift the moment a drive is filtered, and the defect would read as a rendering
    bug rather than a data one.

    ✅ **THIS IS ALSO THE FIRST THING ON THE PAGE THAT SHOWS v01's SHARED AXIS.** The axis has
    been exact since it shipped — worst disagreement 1.00px — and nothing displayed it.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt"),
                          _drive(2, "away", "Beta", "PUNT", category="punt"),
                          _drive(3, "away", "Beta", "TD", category="offensive score"),
                          _drive(4, "home", "Alpha", "FG", category="offensive score")])
    spec = _spec(panel(frame)[1])

    seen = {}
    for name, index in (("away", _AWAY), ("field", _FIELD), ("home", _HOME)):
        layer = _band_layer(spec, index)
        rows = _rows(spec, layer)
        # 🚨 THE BAND LAYER CARRIES THE **WHOLE** FRAME IN EVERY PANEL, INCLUDING THE TABLES.
        # A table draws only its own side's text; if its bands were filtered the same way the
        # stripes would break wherever the other team had the ball, which is most rows.
        assert {r["drive_number"] for r in rows} <= {1, 2, 3, 4}
        seen[name] = {r["drive_number"]: (r["y_lo"], r["y_hi"]) for r in rows}
        assert layer["encoding"]["y"]["field"] == "y_lo"
        assert layer["encoding"]["y2"]["field"] == "y_hi"
        # ⚠️ AND NO PANEL'S BAND MAY PIN A y DOMAIN — that is what ties it to the field's.
        assert "scale" not in layer["encoding"]["y"], (
            f"the {name} band declares its own y scale, so the stripes are placed by "
            f"arithmetic rather than by the shared axis")

    assert seen["away"] == seen["field"] == seen["home"], (
        f"the three panels band DIFFERENT rows, so a stripe in one does not line up with the "
        f"same drive in another: away={seen['away']} field={seen['field']} home={seen['home']}")
    assert seen["field"], "no band was drawn at all"
    # AND EACH STRIPE BRACKETS ITS OWN DRIVE — one row tall, centred on the drive it marks.
    for drive_number, (lo, hi) in seen["field"].items():
        assert lo < drive_number < hi and (hi - lo) == 1.0, (
            f"drive {drive_number}'s stripe spans {lo}…{hi}, which is not the one row it owns")
    # AND IT ALTERNATES rather than striping everything.
    assert set(seen["field"]) == {2, 4}, (
        f"the stripes are on drives {sorted(seen['field'])} — an alternating band puts them "
        f"on every other row of the sequence")


# ── 🚨 v02 PART 5: THE LEGEND IS THE VOCABULARY RENDERED, NOT A LIST BESIDE IT ──────────────

def test_THE_LEGEND_IS_BUILT_FROM_THE_SHAPE_MAP_in_both_directions(panel):
    """> **MARC:** *"the icons/glyphs … need to be bigger, and there should be a legenc"*

    🚨 **v01's LEGEND WAS A SECOND INVENTORY AND THIS IS THE DEFECT v02 FIXES.** It carried its
    own dict — `{"offensive score": "▶", …}` — seven hand-typed unicode characters beside the
    seven Vega shape names they were meant to depict, with **nothing tying them together**. A
    shape could be changed in `_DRIVE_RESULT_SHAPES` and the legend would go on showing the old
    glyph, correctly spelled and wrong. **That is exactly what B117 exists to prevent.**

    ✅ **BOTH DIRECTIONS, WHICH IS THE WHOLE POINT: every category appears, and nothing that is
    not a category appears.** A legend asserted one way only can quietly grow an eighth entry.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt")])
    _entries, charts = panel(frame)
    legend = _legend_spec(charts)

    glyph_layer = _only([n for n in legend["layer"] if _mark_of(n) == "point"],
                        "legend glyph layer")
    rows = _rows(legend, glyph_layer, parent=legend)
    shapes = _module_constant("_DRIVE_RESULT_SHAPES")

    drawn = {r["category"]: r["result_shape"] for r in rows}
    assert drawn == shapes, (
        f"the legend and the shape map disagree — missing "
        f"{set(shapes) - set(drawn)}, extra {set(drawn) - set(shapes)}, "
        f"mismatched "
        f"{dict((k, (drawn.get(k), v)) for k, v in shapes.items() if drawn.get(k) != v)}")
    # AND THE SHAPE IS PASSED THROUGH RATHER THAN SCALED, so the legend draws the same mark the
    # chart does instead of a look-alike Vega chose for it.
    assert glyph_layer["encoding"]["shape"]["scale"] is None, (
        "the legend's shape encoding has a scale, so Vega picks the marks and they can differ "
        "from the ones on the field")
    # AC-G.22: THE LEGEND NAMES THE SHAPES WITHOUT COLOUR, because colour is the team's.
    assert "color" not in glyph_layer.get("encoding", {}), (
        "the legend encodes colour, which belongs to the team and says nothing about a result")
    labels = _only([n for n in legend["layer"] if _mark_of(n) == "text"], "legend label layer")
    assert _text_field_of(labels) == "category"


def test_THE_TABLE_GLYPH_IS_MARCS_THREE_CATEGORIES_and_a_subset_of_the_shape_map(panel):
    """> **MARC:** *"In the table, If the Result is a FG, TD, or some kind of Turnover, include
    > the icon/glyph"*

    ✅ **FG and TD are `offensive score`; a pick-six is `defensive score`; "some kind of
    turnover" is `turnover`.** ⚠️ **AND THE SET IS ASSERTED TO BE A SUBSET OF THE SHAPE MAP'S
    KEYS** — a second hand-written list of category names is the same defect as a second
    legend, one column over. **Punts, kicks, clock expiries and unclassified drives carry no
    table glyph**, which is what makes his three legible at a glance.
    """
    wanted = _module_constant("_DRIVE_TABLE_GLYPH_CATEGORIES")
    shapes = _module_constant("_DRIVE_RESULT_SHAPES")
    assert set(wanted) <= set(shapes), (
        f"the table glyph set names categories the shape vocabulary does not have: "
        f"{set(wanted) - set(shapes)}")
    assert set(wanted) == {"offensive score", "defensive score", "turnover"}, (
        f"Marc named FG/TD, a defensive score and turnovers; this set is {sorted(wanted)}")

    frame = pd.DataFrame([
        _drive(1, "home", "Alpha", "PUNT", category="punt"),
        _drive(2, "home", "Alpha", "TD", category="offensive score", scoring=True,
               scoring_side="offense"),
        _drive(3, "home", "Alpha", "INT", category="turnover"),
        _drive(4, "home", "Alpha", "END OF HALF", category="clock")])
    spec = _spec(panel(frame)[1])
    marked = {r["drive_number"] for r in _table_glyph_rows(spec, _HOME)}
    assert marked == {2, 3}, (
        f"the table drew a glyph on drives {sorted(marked)} — Marc asked for FG/TD, defensive "
        f"scores and turnovers, so a punt and a clock expiry must carry none")


# ── 🚨 v02 PART 4: THE IMPACT COLUMN'S TWO ABSENCES, AND THE RUNNING SCORE ──────────────────

def test_A_ZERO_IMPACT_IS_BLANK_AND_AN_UNTRUSTWORTHY_ONE_IS_A_DASH(panel):
    """> **MARC:** *"Don't present a 0 in the Impact column"*

    🚨 **DROPPING THE `0` PUTS TWO DIFFERENT ABSENCES IN ONE COLUMN AND AC-G.11 SAYS THEY MUST
    NOT LOOK THE SAME.** `0` means *this drive scored nothing* — 52,336 of 84,838 rows (61.69%)
    — and `—` means *no figure here can be trusted*, which is v01's two guards firing on 3,005
    rows (3.54%). **Blank and an em dash are different marks AND the caption says which is
    which**, because a reader cannot be expected to infer it.
    """
    frame = pd.DataFrame([
        # scored nothing, and the snapshots agree it scored nothing → BLANK
        _drive(1, "home", "Alpha", "PUNT", category="punt", scoring=False,
               off_score=(0, 0), def_score=(0, 0)),
        # a touchdown whose snapshots did not move → the guard fires → EM DASH
        _drive(2, "home", "Alpha", "TD", category="offensive score", scoring=True,
               scoring_side="offense", off_score=(17, 17), def_score=(14, 14)),
        # and a real swing → a figure
        _drive(3, "home", "Alpha", "FG", category="offensive score", scoring=True,
               scoring_side="offense", off_score=(0, 3), def_score=(0, 0))])
    entries, charts = panel(frame)
    rows = _table_rows(_spec(charts), _HOME, column="impact_cell")

    assert _row_for(rows, 1)["impact_cell"] == "", (
        f"a drive that scored nothing printed {_row_for(rows, 1)['impact_cell']!r} — Marc asked "
        f"for no zero in this column")
    assert _row_for(rows, 2)["impact_cell"] == fmt.EM_DASH, (
        f"an untrustworthy figure printed {_row_for(rows, 2)['impact_cell']!r} — it must not "
        f"collapse into the same blank a real zero now uses")
    assert _row_for(rows, 3)["impact_cell"].startswith("+3")

    # 🚨 AND THE CAPTION IS WHAT MAKES THE TWO READABLE — SCOPED TO ITSELF, NOT TO THE PANEL
    # (cfdb-main-R-1170). The words `blank` and `em dash` appear nowhere else on the panel, so
    # this selects the one caption that opens with them rather than grepping everything.
    note = [b for k, b in entries if k == "caption" and b.startswith("In Impact,")]
    assert len(note) == 1, f"expected exactly one Impact caption, found {len(note)}"
    assert "blank" in note[0] and "em dash" in note[0], (
        f"the caption does not distinguish the two absences: {note[0]!r}")


def test_THE_RUNNING_SCORE_IS_READ_NOT_ACCUMULATED(panel):
    """> **MARC:** *"If there is a score Impact (table), then include the impact (running sum
    > of teams points)"*

    🚨 **A RUNNING SUM WOULD COMPOUND EVERY DEFECT IN THE SCORE SNAPSHOTS, AND THE COST IS
    MEASURED:** 3,005 drives carry a wrong or suppressed impact (3.54%), and **a running sum
    would carry a wrong total on 22,216 of 84,838 rows (26.19%)** — because one bad delta
    shifts every row below it. ✅ **Reading the published scoreboard is wrong on ONE row.**

    ⚠️ **THE FIXTURE IS BUILT SO THE TWO CANNOT AGREE, WHICH IS THE ONLY WAY THIS TEST CAN
    FAIL.** Drive 2's published end score is 28 while its impact is +7 on top of drive 1's 7 —
    **an accumulator prints 14 and a reader prints 28.** A fixture whose snapshots happened to
    be self-consistent would pass either way, which is R-744's class.
    """
    frame = pd.DataFrame([
        _drive(1, "home", "Alpha", "TD", category="offensive score", scoring=True,
               scoring_side="offense", off_score=(0, 7), def_score=(0, 0)),
        _drive(2, "home", "Alpha", "TD", category="offensive score", scoring=True,
               scoring_side="offense", off_score=(21, 28), def_score=(0, 0))])
    rows = _table_rows(_spec(panel(frame)[1]), _HOME, column="impact_cell")
    second = _row_for(rows, 2)["impact_cell"]
    assert second == "+7 0-28", (
        f"the second drive's Impact cell reads {second!r}. The published scoreboard after it "
        f"is 0-28; an accumulated one would say 0-14, which is what this fixture exists to "
        f"tell apart")
    assert _row_for(rows, 1)["impact_cell"] == "+7 0-7"


def test_THE_RUNNING_SCORE_IS_SUPPRESSED_WHERE_IT_WOULD_GO_BACKWARDS(panel):
    """🚨 **A SCOREBOARD CANNOT GO DOWN. Points are never removed, so a running score lower
    than the previous drive's is impossible rather than merely suspicious.**

    📊 **1,549 of 81,231 within-game comparisons fall foul of it (1.91%), across 793 of 3,607
    games (21.99%)** — and the same snapshots disagree with `srv_game`'s published final on
    214 games (5.93%). ✅ **So the impossible rows print no score at all, and the impact beside
    them still stands**: the swing came from `is_scoring_drive` and the legal-value check,
    which are not the scoreboard.
    """
    frame = pd.DataFrame([
        _drive(1, "home", "Alpha", "TD", category="offensive score", scoring=True,
               scoring_side="offense", off_score=(0, 7), def_score=(0, 0)),
        _drive(2, "home", "Alpha", "TD", category="offensive score", scoring=True,
               scoring_side="offense", off_score=(21, 28), def_score=(0, 0)),
        # the home total drops 28 → 10, which no game can do
        _drive(3, "home", "Alpha", "FG", category="offensive score", scoring=True,
               scoring_side="offense", off_score=(7, 10), def_score=(0, 0))])
    rows = _table_rows(_spec(panel(frame)[1]), _HOME, column="impact_cell")
    backwards = _row_for(rows, 3)["impact_cell"]
    assert backwards == "+3", (
        f"a drive whose running score went BACKWARDS printed {backwards!r} — the scoreboard "
        f"is impossible there and must be withheld, while the swing itself still stands")
    assert "10" not in backwards, (
        f"{backwards!r} still carries the impossible total")


# ── 🚨 v02 PART 6: THE SCOREBOARD HEADER ────────────────────────────────────────────────────

def test_THE_SCOREBOARD_READS_THE_GAME_ROW_not_the_drives_frame(panel):
    """> **MARC:** *"Include the Scoreboard at the top/middle as a header to the chart."*

    🚨 **THE DRIVES FRAME CANNOT SUPPLY IT, AND THAT IS MEASURED AGAINST AN INDEPENDENT
    AUTHORITY.** The last drive's `end_offense_score` / `end_defense_score` agree with
    `srv_game`'s published final on **3,393 of 3,607 games (94.07%)** and **disagree on 214
    (5.93%)**, by up to 22 points. ⚠️ **A header built from the frame would be wrong on one
    game in seventeen, in the one place a reader would never think to doubt.**

    ✅ **THE FIXTURE'S TWO SOURCES DISAGREE ON PURPOSE** — the row says 17-24 and the drives
    add up to something else — so a header taken from the wrong place fails here rather than
    passing by coincidence.
    """
    frame = pd.DataFrame([
        _drive(1, "home", "Alpha", "TD", category="offensive score", scoring=True,
               scoring_side="offense", off_score=(0, 7), def_score=(0, 0))])
    entries, _charts = panel(frame, row=_game_row(away_points=17, home_points=24))
    header = [b for k, b in entries
              if k == "markdown" and isinstance(b, str) and "Drives</div>" in b]
    assert len(header) == 1, f"expected exactly one scoreboard header, found {len(header)}"
    head = header[0]
    assert ">17<" in head and ">24<" in head, (
        f"the header does not carry the published final score 17-24: {head!r}")
    assert ">7<" not in head, (
        "the header printed the drives frame's own score — those columns disagree with the "
        "published final on 5.93% of games")


def test_THE_SCOREBOARD_SEGMENTS_ARE_THE_PANELS_OWN_CONSTANTS(panel):
    """🚨 **DO NOT USE `st.columns` — a proportional element cannot track an absolute one**, the
    argument B115 lost at 1700px with a green suite and a pixel-perfect 1300px raster
    (cfdb-wta-R-941).

    ✅ **A156 MEASURED THAT `use_container_width` IS INERT UNDER `hconcat` AND THE PANEL IS A
    FIXED WIDTH (cfdb-main-R-1106), WHICH MAKES THIS EASIER RATHER THAN HARDER** — an HTML
    header whose segments ARE the chart's constants lines up by construction.

    🚨 **AND THE PANEL IS 1200px WIDE, NOT 1180 — `spacing` IS REAL WIDTH.** The three panels
    sum to 1180 and `hconcat` puts ten pixels between each neighbouring pair. **A header built
    to 1180 would be twenty pixels narrow and the middle segment would sit off-centre**, which
    is the arithmetic this assertion exists to keep honest.
    """
    table_w = _module_constant("_DRIVE_TABLE_WIDTH")
    field_w = _module_constant("_DRIVE_FIELD_WIDTH")
    spacing = _module_constant("_DRIVE_PANEL_SPACING")
    panel_w = _module_constant("_DRIVE_PANEL_WIDTH")
    assert panel_w == 2 * table_w + field_w + 2 * spacing, (
        f"the declared panel width {panel_w} is not what hconcat draws: "
        f"{table_w} + {spacing} + {field_w} + {spacing} + {table_w}")

    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt")])
    entries, charts = panel(frame)
    head = _only([b for k, b in entries
                  if k == "markdown" and isinstance(b, str) and "Drives</div>" in b],
                 "scoreboard header")
    widths = [int(m) for m in re.findall(r"width:(\d+)px", head)]
    assert widths == [panel_w, table_w, field_w, table_w], (
        f"the header's segments are {widths}, which do not match the chart's "
        f"{[panel_w, table_w, field_w, table_w]}")
    assert f"gap:{spacing}px" in head, (
        f"the header's gutters do not match hconcat's spacing of {spacing}px: {head!r}")

    # AND THE CHART IT HEADS REALLY IS THOSE WIDTHS — the half a header-only test cannot see.
    spec = _spec(charts)
    drawn = [spec["hconcat"][i].get("width") for i in (_AWAY, _FIELD, _HOME)]
    assert drawn == [table_w, field_w, table_w], (
        f"the three panels are {drawn} wide, so the header is aligned to numbers the chart "
        f"does not use")
    assert spec.get("spacing") == spacing, (
        f"the hconcat spacing is {spec.get('spacing')} and the header assumes {spacing}")


def test_THE_COLUMN_PLAN_SUMS_TO_THE_TABLE_WIDTH():
    """🚨 **v01 CARRIED FIVE LITERAL x POSITIONS AND v02 DERIVES THEM, WHICH NEEDS THIS GUARD.**

    A literal x agrees with the widths beside it only until somebody edits one, and the failure
    is silent: columns overprint, which is what v01's first render did. **This asserts the last
    column's right edge is exactly `_DRIVE_TABLE_WIDTH`** — the one assertion that can catch a
    plan whose parts no longer sum.

    📊 **AND THE FIT IS MEASURED, NOT ASSUMED.** Each distinct string in each column was put
    through a real Vega-Lite text mark at `fontSize` 10 in Chromium and read back with
    `getComputedTextLength()`. Seven columns need **307px** and have **236**, so `Result`
    absorbs the shortfall at 45px and clips on **9,107 of 84,838 drives (10.735%)**.
    """
    plan = _module_constant("_DRIVE_COLUMN_PLAN")
    gap = _module_constant("_DRIVE_TABLE_GAP")
    width = _module_constant("_DRIVE_TABLE_WIDTH")
    glyph = _module_constant("_DRIVE_GLYPH_CELL")

    total = sum(c[2] for c in plan) + gap * (len(plan) - 1)
    assert total == width, (
        f"the seven columns and their {len(plan) - 1} gutters come to {total}px inside a "
        f"{width}px table — a plan that does not sum overprints, silently")
    assert [c[6] for c in plan] == ["#", "Clock", "Dur", "Yard", "Yrds", "Result", "Impact"], (
        f"the column order is {[c[6] for c in plan]}; Marc asked for the yardline between the "
        f"clock group and Yrds")

    layout = _module_constant("_drive_column_layout")()
    last = layout[-1]
    assert last[2] == float(width), (
        f"the last column is anchored at {last[2]} rather than the table's right edge {width}")
    # AND THE RESULT CELL RESERVES EXACTLY THE GLYPH'S WIDTH FOR THE GLYPH, which is why its
    # column width and its text limit differ.
    result = _only([c for c in plan if c[0] == "result"], "the Result column")
    assert result[2] - result[4] == glyph, (
        f"the Result column is {result[2]}px wide with a {result[4]}px text limit, a difference "
        f"of {result[2] - result[4]} — the glyph cell is {glyph}px, so the text would overlap it")


# ── 🚨 v02 PART 2: THE FIELD'S FURNITURE ────────────────────────────────────────────────────

def test_THE_REFERENCE_LINES_ARE_SOLID_and_the_goal_lines_and_midfield_are_BOLDER(panel):
    """> **MARC:** *"vertical reference lines should be solid instead of dashed. Would be ideal
    > to make the 0,50,0 a bolder line."*

    ⚠️ **HIS `0,50,0` IS THREE LINES AND THE OUTER TWO ARE THE GOAL LINES** — where the DATA's
    0 and 100 sit, at field x 10 and 110 — **not the picture's edges**, which are the back of
    each end zone. Emphasising the edges would put the weight on the one pair of lines that
    means nothing to a reader.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt")])
    spec = _spec(panel(frame)[1])
    grid = _field_grid(spec)

    mark = grid["mark"]
    assert "strokeDash" not in (mark if isinstance(mark, dict) else {}), (
        f"the reference lines are still dashed: {mark}")

    rows = _rows(spec, grid)
    kinds = {r["x"]: r["kind"] for r in rows}
    endzone = _module_constant("_DRIVE_ENDZONE")
    yards = _module_constant("_DRIVE_FIELD_YARDS")
    assert kinds[endzone] == "goal" and kinds[yards - endzone] == "goal", (
        f"the goal lines are not marked as goal lines: {kinds}")
    assert kinds[yards / 2] == "mid", f"midfield is not marked: {kinds}"
    assert kinds[0] == "edge" and kinds[yards] == "edge", (
        f"the back of the end zones is being treated as a goal line: {kinds}")

    widths = dict(zip(grid["encoding"]["strokeWidth"]["scale"]["domain"],
                      grid["encoding"]["strokeWidth"]["scale"]["range"]))
    assert widths["goal"] > widths["ten"] and widths["mid"] > widths["ten"], (
        f"the 0/50/0 lines are not bolder than the ten-yard lines: {widths}")
    assert widths["goal"] > widths["edge"], (
        f"the goal line is no bolder than the back of the end zone: {widths}")


def test_THE_ENDZONES_ARE_FILLED_on_geometry_that_already_existed(panel):
    """> **MARC:** *"Can we fill the endzone with a light/mid gray?"*

    ✅ **v01 ALREADY DREW 120 YARDS WITH THE DATA INSET AT 10…110, so this is a fill on real
    space rather than new decoration.**

    🚨 **AND THE GRAY IS `currentColor` AT LOW OPACITY, NOT A LITERAL — AC-G.22 AND R-855.**
    Streamlit sets the page's text colour per theme and the SVG inherits it, so the fill is the
    theme's own ink. **A hex gray is the R-855 trap in a different property:** that round found
    `identity.text_on(row)` defaulting to the on-light colour and rendering `rgb(0,0,0)` on a
    `rgb(14,17,23)` page, invisible, and the raster is what caught it.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt")])
    spec = _spec(panel(frame)[1])
    fill = _endzone_layer(spec)
    mark = fill["mark"]
    assert mark["fill"] == "currentColor", (
        f"the end-zone fill is {mark.get('fill')!r} — a literal colour is right in one theme "
        f"and wrong in the other")
    assert 0 < mark["fillOpacity"] < 0.5, (
        f"the end-zone fill opacity is {mark.get('fillOpacity')} — it must not compete with a "
        f"team colour (AC-G.22)")

    endzone = _module_constant("_DRIVE_ENDZONE")
    yards = _module_constant("_DRIVE_FIELD_YARDS")
    spans = sorted((r["x"], r["x2"]) for r in _rows(spec, fill))
    assert spans == [(0.0, float(endzone)), (float(yards - endzone), float(yards))], (
        f"the fill covers {spans} rather than the two end zones")
    # AND IT SPANS THE WHOLE HEIGHT rather than one row — no y encoding at all.
    assert "y" not in fill["encoding"], (
        "the end-zone fill is bound to a drive, so it draws a band instead of a zone")


# 📊 **MEASURED BOLD HEADING WIDTHS, AT `fontSize` 10 IN CHROMIUM'S `sans-serif`** — read back
# with `getComputedTextLength()` off the node a real Vega-Lite text mark produced, with
# `fontWeight: bold` set, which is how the panel draws them.
#
# 🚨 **THIS TABLE EXISTS BECAUSE THE FIRST v02 RENDER BROKE THREE HEADINGS AT ONCE AND NOTHING
# IN THE SUITE COULD SEE IT.** `Result` clipped to `Res…` inside a 30px limit because bold
# `Result` is 30.56px; `Impact` clipped to `Imp…` at 32 because bold is 32.23; and `Yard` and
# `Yrds`, both right-aligned in adjacent ~17px cells, overlapped by 2.2px and rendered as the
# single word `YardYr…`. ⚠️ **Every heading had been sized from its REGULAR width.**
#
# ✅ **A HEADING NOT IN THIS TABLE FAILS THE TEST BELOW**, which is deliberate: renaming a
# column should cost a measurement, because a guessed width is what broke it.
_BOLD_HEADING_PX = {
    "#": 5.56, "Clock": 27.23, "Dur": 17.23, "Yard": 21.69,
    "Yrds": 22.23, "Result": 30.56, "Impact": 32.23,
}


def test_NO_TWO_TABLE_HEADINGS_COLLIDE_and_none_is_clipped_by_its_own_limit():
    """🚨 THE THREE DEFECTS THE FIRST v02 RASTER SHOWED, TURNED INTO AN ASSERTION.

    ⚠️ **AND IT IS ABOUT THE BOLD WIDTH, WHICH IS THE WHOLE LESSON.** The limits were set from
    regular widths and bold costs up to +2.22px — exactly the headroom they had. **§2.4: the
    measurement answered *how wide is this string* when the question was *how wide is this
    string AS DRAWN*.**

    ✅ **THE COLLISION IS FIXED BY ALIGNMENT, NOT BY SHORTENING MARC'S WORDS.** A heading need
    not share its cell's alignment: `Yrds` is left-aligned at its cell's left edge so it grows
    away from `Yard` rather than back into it.
    """
    layout = _module_constant("_drive_column_layout")()
    width = _module_constant("_DRIVE_TABLE_WIDTH")

    spans = []
    for entry in layout:
        (_key, _field, _x, _left, _w, _align, _limit,
         head_limit, heading, head_align, head_x) = entry
        assert heading in _BOLD_HEADING_PX, (
            f"heading {heading!r} has no measured bold width — measure it in a real Vega text "
            f"mark at fontSize 10 with fontWeight bold and add it to _BOLD_HEADING_PX. "
            f"A guessed width is what shipped `Res…` and `YardYr…`")
        bold = _BOLD_HEADING_PX[heading]
        # 1. NOTHING IS CLIPPED BY ITS OWN LIMIT — the `Res…` / `Imp…` defect.
        assert bold <= head_limit, (
            f"{heading!r} needs {bold}px bold and its limit is {head_limit} — Vega will clip "
            f"the heading to fit, which is a word narrower than itself")
        lo = head_x - bold if head_align == "right" else head_x
        spans.append((heading, lo, lo + bold))

    # 2. NO TWO HEADINGS OVERLAP — the `YardYr…` defect.
    for (left_name, _l0, l1), (right_name, r0, _r1) in zip(spans, spans[1:]):
        assert r0 >= l1, (
            f"{left_name!r} ends at {l1:.2f} and {right_name!r} starts at {r0:.2f} — they "
            f"overlap by {l1 - r0:.2f}px and render as one word, which is what the first v02 "
            f"raster showed as `YardYr…`")

    # 3. AND THE ROW STAYS INSIDE THE TABLE at both ends.
    assert spans[0][1] >= 0, f"{spans[0][0]!r} starts off the left edge at {spans[0][1]}"
    assert spans[-1][2] <= width, (
        f"{spans[-1][0]!r} runs to {spans[-1][2]} past the table's {width}px right edge")


def test_THE_LOGO_ENCODING_PARTITIONS_THE_ROWS_and_never_double_labels_a_cell(panel):
    """🚨 **THE RASTER CAUGHT THIS AS `50 50` IN ONE CELL AND NO ASSERTION EXISTED FOR IT.**

    Marc offered two encodings for the side of the 50 — a logo, or his `+`/`-` — and they are
    one implementation behind `_DRIVE_YARDLINE_ENCODING`. In the logo reading a row with no
    logo has to fall back to the mark, **and the first version filtered only the fallback
    layer**: the number layer still drew every row, so a midfield drive printed the mark and
    the number side by side.

    📊 **THE ROWS WITH NO LOGO ARE NOT RARE: midfield is 634 drives (0.747%) and it has no side
    at all, so it can never have one** — plus `offense_logo_url` covers 84,058 of 84,838 rows
    (99.08%) and `opponent_logo_url` 84,076 (99.10%).

    ⚠️ **A `notna()` FILTER ON ONE LAYER IS HALF A PARTITION.** The other half has to be told,
    which is the shape of R-141's family: a branch that is right about what it draws and wrong
    about what the other branch draws.
    """
    frame = pd.DataFrame([
        # own side, with a logo
        _drive(1, "home", "Alpha", "PUNT", category="punt", start=25, end=40),
        # MIDFIELD — no side, so no logo, ever
        _drive(2, "home", "Alpha", "PUNT", category="punt", start=50, end=60),
        # opponent side, with a logo
        _drive(3, "home", "Alpha", "PUNT", category="punt", start=70, end=80)])
    spec = _spec(panel(frame, encoding="logo")[1])

    images = _only([n for n in _layers(spec, _HOME) if _mark_of(n) == "image"],
                   "yardline logo layer")
    numbers = _only([n for n in _layers(spec, _HOME)
                     if _text_field_of(n) == "yardline_number"], "yardline number layer")
    marks = _only([n for n in _layers(spec, _HOME)
                   if _text_field_of(n) == "yardline_mark"], "yardline fallback layer")

    with_logo = {r["drive_number"] for r in _rows(spec, images)}
    numbered = {r["drive_number"] for r in _rows(spec, numbers)}
    fallen_back = {r["drive_number"] for r in _rows(spec, marks)}

    assert with_logo == {1, 3}, f"the logo drew for drives {sorted(with_logo)}"
    assert 2 in fallen_back, (
        "a midfield drive has no side and so no logo — it must keep the +/- encoding")
    # 🚨 THE PARTITION, WHICH IS THE WHOLE TEST. No drive may be labelled twice.
    both = numbered & fallen_back
    assert not both, (
        f"drive(s) {sorted(both)} were labelled by BOTH the number layer and the fallback "
        f"layer — that is the `50 50` the raster showed in one cell")
    # AND THE OTHER NO-LOGO CASE — a team that publishes no logo url at all (~0.9% of rows).
    # ⚠️ It is a SEPARATE cause from midfield and must land in the same fallback, not a hole.
    bare = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt", start=25,
                                logo=None, opponent_logo=None)])
    bare_spec = _spec(panel(bare, encoding="logo")[1])
    assert not [n for n in _layers(bare_spec, _HOME) if _mark_of(n) == "image"
                and _rows(bare_spec, n)], "a row with no logo url drew an image anyway"
    bare_marks = _only([n for n in _layers(bare_spec, _HOME)
                        if _text_field_of(n) == "yardline_mark"], "fallback layer")
    assert {r["drive_number"] for r in _rows(bare_spec, bare_marks)} == {1}, (
        "a team with no published logo lost its yardline entirely rather than falling back")

    assert numbered | fallen_back == {1, 2, 3}, (
        f"the two layers together cover {sorted(numbered | fallen_back)} of three drives — a "
        f"row labelled by neither is a blank cell where a yardline should be")


def test_THE_MARK_ENCODING_DRAWS_NO_IMAGE_AT_ALL(panel):
    """The other reading, asserted so the two cannot quietly become one.

    ⚠️ **AND THIS IS WHAT SHIPS**, for two measured reasons rather than a preference: a Vega
    tooltip cannot carry an image (hovered and read out of the DOM — 0 `<img>` elements), and
    the mark covers 100% of rows against the logo's 99.08%.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt", start=25)])
    spec = _spec(panel(frame, encoding="mark")[1])
    assert not [n for n in _layers(spec, _HOME) if _mark_of(n) == "image"], (
        "the default encoding drew a logo — the two readings have collapsed into one")
    assert _module_constant("_DRIVE_YARDLINE_ENCODING") == "mark", (
        "the shipped default is no longer the encoding that works in the tooltip and covers "
        "every row; if that is deliberate it is Marc's call and this line should say so")


# ── 🚨 v03: THE DISPLAY MAP, THE DERIVED SPLIT AND THE BAND WEIGHT ──────────────────────────
#
# 📊 **THE 25 PUBLISHED `drive_result` VALUES, ENUMERATED ON LIVE PUBLISHED SERVING WITH THEIR
# MEASURED WIDTHS AT `fontSize` 10.** Pinned here for the same reason the seven categories are
# pinned in `test_EVERY_DRIVE_RESULT_CATEGORY_HAS_ITS_OWN_SHAPE`: CI has no warehouse, so the
# population is a measurement carried into the suite rather than a query the suite can run.
#
#     PUNT 27.23 (30,345) · TD 13.34 (22,870) · FG 13.89 (7,499) · DOWNS 38.34 (6,094)
#     INT 16.11 (5,028) · FUMBLE 40.56 (3,069) · MISSED FG 55.02 (2,669)
#     END OF HALF 66.12 (2,600) · END OF GAME 70.02 (2,399) · Uncategorized 64.48 (904)
#     INT TD 31.88 (486) · FUMBLE RETURN TD 100.94 (207) · SF 12.78 (201)
#     END OF 4TH QUARTER 110.95 (138) · PUNT TD 42.98 (129) · PUNT RETURN TD 87.42 (86)
#     FUMBLE TD 56.50 (70) · MISSED FG TD 70.94 (15) · KICKOFF 43.34 (8) · DOWNS TD 54.27 (7)
#     END OF HALF TD 82.06 (5) · BLOCKED FG 64.47 (3) · BLOCKED PUNT 77.80 (3)
#     FG TD 29.83 (2) · END OF GAME TD 85.94 (1)
_PUBLISHED_RESULTS = {
    "PUNT", "TD", "FG", "DOWNS", "INT", "FUMBLE", "MISSED FG", "END OF HALF",
    "END OF GAME", "Uncategorized", "INT TD", "FUMBLE RETURN TD", "SF",
    "END OF 4TH QUARTER", "PUNT TD", "PUNT RETURN TD", "FUMBLE TD", "MISSED FG TD",
    "KICKOFF", "DOWNS TD", "END OF HALF TD", "BLOCKED FG", "BLOCKED PUNT", "FG TD",
    "END OF GAME TD",
}

# 📊 **AND THE DISPLAY FORMS, MEASURED THE SAME WAY.** The widest is what sizes the cell.
_DISPLAY_LABEL_PX = {
    "PUNT RET TD": 65.59, "FUM RET TD": 60.20, "DOWNS TD": 54.27, "PUNT TD": 42.98,
    "X-FG TD": 39.83, "DOWNS": 38.34, "EOG TD": 38.17, "EOH TD": 37.61,
    "FUM TD": 37.59, "B-PUNT": 37.23, "INT TD": 31.88, "FG TD": 29.83,
    "EOQ4": 27.80, "PUNT": 27.23, "X-FG": 23.89, "B-FG": 23.89, "EOG": 22.23,
    "FUM": 21.67, "EOH": 21.67, "N/A": 16.67, "INT": 16.11, "KO": 14.45,
    "FG": 13.89, "TD": 13.34, "SF": 12.78,
}


def test_EVERY_PUBLISHED_RESULT_HAS_A_DISPLAY_FORM_and_nothing_else_does():
    """🚨 B117's RULE, AS THE LEGEND NEEDED IT (cfdb-wta-R-1189) — BOTH DIRECTIONS.

    > **MARC:** *"I recommend a label change for "MISSED FG", present as "X-FG", "END OF HALF"
    > as "EOH" or "Half". "Uncategorized" as N/A."*

    🚨 **HE NAMED THREE AND THERE ARE 25.** A partial map leaves the column sized by whichever
    long string he did not mention — and `END OF 4TH QUARTER`, the widest published string at
    **110.95px**, is one he did not mention. **On a partial map it would still set the width and
    the round would have bought nothing.**

    ⚠️ **ASSERTED IN BOTH DIRECTIONS because one direction is not enough:** a map missing a
    value lets a new feed string reach a reader unmapped, and a map with an EXTRA key is a
    label for something that does not exist — dead code that reads as coverage.
    """
    labels = _module_constant("_DRIVE_RESULT_LABELS")
    assert set(labels) == _PUBLISHED_RESULTS, (
        f"the display map and the published results disagree: "
        f"missing {sorted(_PUBLISHED_RESULTS - set(labels))}, "
        f"extra {sorted(set(labels) - _PUBLISHED_RESULTS)}")

    # 🚨 AND IT MUST BE INJECTIVE. `PUNT TD` and `PUNT RETURN TD` are different published
    # results, as are `FUMBLE TD` and `FUMBLE RETURN TD` — **two collapsing onto one label
    # would make a returned score indistinguishable from a scored one**, which is worse than
    # the clipping this map exists to remove.
    collisions = {v: [k for k in labels if labels[k] == v]
                  for v in set(labels.values()) if list(labels.values()).count(v) > 1}
    assert not collisions, (
        f"the display map is not injective — these published results share a label: "
        f"{collisions}")

    # AND MARC'S OWN THREE ARE WHAT HE ASKED FOR, pinned so a later tidy-up cannot drift them.
    assert labels["MISSED FG"] == "X-FG"
    assert labels["END OF HALF"] == "EOH"
    assert labels["Uncategorized"] == "N/A"


def test_THE_DISPLAY_MAP_CANNOT_SILENTLY_SWALLOW_A_NEW_FEED_VALUE(panel):
    """🚨 **A VALUE WITH NO DISPLAY FORM MUST NOT RENDER AS `N/A`, AND THAT IS THE OPPOSITE OF
    WHAT IT LOOKS LIKE.**

    `N/A` is already the display form of `Uncategorized` — a real, published, classified-as-
    unknown result. **Routing an UNMAPPED value there would tell a reader cfdb knows the drive
    was unclassified, when the truth is that cfdb has a result and this file has no word for
    it.** ⚠️ **Two different absences, AC-G.11.**

    ✅ **So it falls through to the published string: true, and LOUD — it is wider than the 66px
    cell, so it clips with an ellipsis and announces itself.** The control against it reaching
    production at all is the both-directions test above.
    """
    frame = pd.DataFrame([
        _drive(1, "home", "Alpha", "SOME NEW CFBD RESULT", category="punt"),
        _drive(2, "home", "Alpha", "Uncategorized", category="unknown")])
    rows = _table_rows(_spec(panel(frame)[1]), _HOME, column="result_label")
    unmapped, genuinely_unknown = _row_for(rows, 1), _row_for(rows, 2)

    assert unmapped["result_label"] == "SOME NEW CFBD RESULT", (
        f"an unmapped feed value rendered as {unmapped['result_label']!r} — it must keep the "
        f"published string rather than borrow another result's label")
    assert genuinely_unknown["result_label"] == "N/A", (
        f"`Uncategorized` rendered as {genuinely_unknown['result_label']!r}")
    assert unmapped["result_label"] != genuinely_unknown["result_label"], (
        "an unmapped result and a published-as-unclassified one read identically, which tells "
        "a reader cfdb knows something it does not (AC-G.11)")


def test_THE_CELL_IS_ABBREVIATED_AND_THE_TOOLTIP_KEEPS_THE_WHOLE_WORD(panel):
    """✅ **THE ABBREVIATION IS FOR A 66px CELL, NOT A REPLACEMENT FOR THE PUBLISHED WORD.**

    🚨 **AND BOTH HALVES ARE ASSERTED, SCOPED TO THEIR OWN ELEMENT (cfdb-main-R-1170).** The
    full string is on the panel in the tooltip and the abbreviation is in the cell, so a test
    that searched the spec as text would pass with either one missing.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "END OF 4TH QUARTER", category="clock")])
    spec = _spec(panel(frame)[1])

    cell = _row_for(_table_rows(spec, _HOME, column="result_label"), 1)
    assert cell["result_label"] == "EOQ4", (
        f"the cell reads {cell['result_label']!r}; the published string is 110.95px and the "
        f"cell is 66px, so the whole point is that it does not go there")

    # THE TOOLTIP, READ OFF THE BAR LAYER'S ENCODING rather than out of the spec's text
    bars = _only([n for n in _layers(spec, _FIELD)
                  if _mark_of(n) == "rule" and "y" in (n.get("encoding") or {})], "bar layer")
    fields = [t.get("field") for t in bars["encoding"]["tooltip"]]
    assert "drive_result" in fields, (
        f"the tooltip lost the published result: {fields}. A reader who wants the word must be "
        f"able to get it")
    assert "result_label" not in fields, (
        "the tooltip carries the ABBREVIATION, which is the one place there is room for the "
        "whole word")
    drawn = _row_for(_field_rows(spec), 1)
    assert drawn["drive_result"] == "END OF 4TH QUARTER", (
        f"the tooltip's own row carries {drawn['drive_result']!r} rather than the published "
        f"string, so the abbreviation has replaced the data rather than displayed it")


def test_THE_RESULT_CELL_FITS_EVERY_DISPLAY_LABEL_with_no_truncation():
    """🚨 **THE WHOLE POINT OF v03's WIDTH WORK: ZERO TRUNCATION, DERIVED RATHER THAN CHOSEN.**

    📊 The widest display label is `PUNT RET TD` at **65.59px**, down from `END OF 4TH QUARTER`
    at **110.95px** — a 40.9% fall in the number that sizes the column. **The cell is 66px
    because the measurement says 65.59, not the other way round.**

    ⚠️ **AND THE MAP'S VALUES MUST ALL BE MEASURED**, or a later rename could add a label wider
    than the cell and this test would not know.
    """
    labels = _module_constant("_DRIVE_RESULT_LABELS")
    plan = _module_constant("_DRIVE_COLUMN_PLAN")
    result = _only([c for c in plan if c[0] == "result"], "the Result column")
    limit = result[4]

    unmeasured = set(labels.values()) - set(_DISPLAY_LABEL_PX)
    assert not unmeasured, (
        f"these display labels have no measured width: {sorted(unmeasured)} — measure them in "
        f"a real Vega text mark at fontSize 10 and add them to _DISPLAY_LABEL_PX")

    over = {v: _DISPLAY_LABEL_PX[v] for v in set(labels.values())
            if _DISPLAY_LABEL_PX[v] > limit}
    assert not over, (
        f"these labels are wider than the {limit}px Result cell and will clip: {over}")
    # AND THE CELL IS NOT WASTEFULLY WIDE EITHER — he is spending field pixels on it.
    widest = max(_DISPLAY_LABEL_PX[v] for v in set(labels.values()))
    assert limit - widest < 1.0, (
        f"the Result cell is {limit}px for a widest label of {widest}px — {limit - widest}px "
        f"of it comes straight out of the field, which Marc is paying for")


def test_THE_SPLIT_IS_DERIVED_AND_THE_FIELD_TAKES_THE_REMAINDER():
    """> **MARC:** *"Reduce the size of the field to gain the extra information I requested to be
    > in the tables."*

    ✅ **cfdb-main-R-895, OPEN SINCE B113, IS ANSWERED — as a priority rather than a number.**
    So the assertion is not *"the split is 256/668/256"*; it is that **the table is the sum of
    what its columns measure and the field is whatever is left**, which is the property that
    makes the number a consequence rather than a preference.

    📊 v02 was 236/708/236. v03 is 256/668/256 — **the field pays 40px (5.6%), and the label
    abbreviations paid the other 45px**, which is why it is not the 301px the old labels needed.
    """
    table = _module_constant("_DRIVE_TABLE_WIDTH")
    field = _module_constant("_DRIVE_FIELD_WIDTH")
    panel_w = _module_constant("_DRIVE_PANEL_WIDTH")
    spacing = _module_constant("_DRIVE_PANEL_SPACING")
    plan = _module_constant("_DRIVE_COLUMN_PLAN")
    gap = _module_constant("_DRIVE_TABLE_GAP")

    # 1. THE TABLE IS EXACTLY ITS COLUMNS — nothing spare, nothing missing.
    assert sum(c[2] for c in plan) + gap * (len(plan) - 1) == table

    # 2. AND THE THREE PANELS STILL SUM TO THE SAME TOTAL, so growing the tables came OUT OF
    #    THE FIELD rather than out of the page.
    assert 2 * table + field == 1180, (
        f"2x{table} + {field} = {2 * table + field}, not 1180 — the tables grew at the page's "
        f"expense rather than the field's, which is not what Marc asked for")
    assert panel_w == 2 * table + field + 2 * spacing == 1200

    # 3. THE FIELD MUST STILL CARRY ITS FURNITURE. 120 yards, a gridline every ten, and a
    #    2-digit axis label measured at 11.12px.
    per_yard = field / _module_constant("_DRIVE_FIELD_YARDS")
    assert per_yard * 10 > 3 * 11.12, (
        f"at {per_yard:.3f} px/yard a ten-yard gap is {per_yard * 10:.1f}px, which is not "
        f"comfortably more than the 11.12px axis label it has to hold")


def test_THE_BAND_IS_A_LIGHT_GRAY_AND_ITS_BORDER_IS_ONLY_SLIGHTLY_DARKER():
    """> **MARC:** *"I would use an alternating band (light gray/white). I would also include a
    > slightly darker border"* · *"I don't see the row banding included"*

    🚨 **v02 HAD THESE BACKWARDS: the band was 0.055 and the BORDER was 0.16 — three times the
    band, so the thing he asked to be "slightly darker" was the dominant mark, and 5.5% of the
    theme's ink is not a light gray.**

    ⚠️ **THE UPPER BOUND IS AC-G.22 AND IT IS NOT DECORATION: the bars are full-strength team
    colour, and a band that competes with them takes colour away from identity.** The weight
    itself was settled by looking at four renders; this pins the RELATIONSHIPS that looking
    cannot regress silently.
    """
    band = _module_constant("_DRIVE_BAND_OPACITY")
    border = _module_constant("_DRIVE_BAND_BORDER_OPACITY")
    endzone = _module_constant("_DRIVE_ENDZONE_OPACITY")

    assert band > 0.055, (
        f"the band is still {band} — that is v02's weight, the one Marc could not see")
    assert border > band, (
        f"the border ({border}) must be darker than the band ({band}) — he asked for a border, "
        f"not an outline round nothing")
    assert border < 2 * band, (
        f"the border is {border} against a {band} band, more than twice it — he asked for "
        f"*slightly* darker, and v02's 3x is what made the edge the dominant mark")
    assert band < 0.2, (
        f"a band at {band} competes with the team colour on the bars (AC-G.22)")
    # 🚨 AND THE CEILING IS NOT AC-G.22 — IT IS THE FIELD'S OWN STRUCTURE, WHICH THE RENDER
    # REVEALED AND THE ARITHMETIC DID NOT. At band 0.16 the row stripe is heavier than a 0.10
    # end-zone fill, and **the field's boundary then reads as weaker than its rows** — the end
    # zones stop reading as zones. A boundary must outweigh a guide.
    assert endzone > band, (
        f"the end-zone fill ({endzone}) is no heavier than the row band ({band}), so the "
        f"field's boundary reads as weaker than its rows and the zones stop reading as zones")
    assert endzone < 2 * band, (
        f"the end-zone fill ({endzone}) is more than twice the band ({band}) — it has become "
        f"the loudest thing on a field whose point is the drives")


def test_NO_FIELD_LAYER_SUPPRESSES_THE_SHARED_X_AXIS(panel):
    """🚨🚨 **v02 SILENTLY LOST THE FIELD'S YARD NUMBERS AND ITS OWN RASTER DID NOT CATCH IT.**

    v02 added the end-zone fill with `axis=None` on a private copy of the x encoding.
    **In a LAYERED chart Vega-Lite resolves axes across the layers, so one explicit `null`
    suppressed the axis for ALL of them.** 📊 Measured in Chromium: the rendered SVG carried
    **0 `g.role-axis` groups and 0 label texts**, while the axis definition sat correctly on two
    other layers. v01 drew `0 10 20 30 40 50 40 30 20 10 0`; v02 drew nothing.

    🚨 **AND THE SPEC WAS RIGHT, WHICH IS WHY THIS TEST IS SHAPED THE WAY IT IS.** Asserting
    *"the field declares an axis"* passes on the broken version — v02 declared one, twice. **The
    defect is a CONFLICT between layers, so the assertion has to be about the set of them.**

    ⚠️ **AND IT IS THE FAILURE A PICTURE IS WORST AT: a reader notices a wrong mark and does not
    notice an absent one.** Five defects in v01 and three headings in v02 were caught by looking;
    this one survived two rounds of looking.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", category="punt")])
    spec = _spec(panel(frame)[1])

    declared, suppressed = [], []
    for node in _layers(spec, _FIELD):
        enc = (node.get("encoding") or {}).get("x")
        if not isinstance(enc, dict) or "axis" not in enc:
            continue
        (suppressed if enc["axis"] is None else declared).append(_mark_of(node))

    assert declared, "no field layer declares an x axis at all, so the yard numbers cannot draw"
    assert not suppressed, (
        f"these field layers set `x.axis = null` while {declared} declare an axis: "
        f"{suppressed}. Vega-Lite resolves axes across a layer, so the explicit null wins and "
        f"the field's yard numbers are not drawn — which is exactly what v02 shipped")
