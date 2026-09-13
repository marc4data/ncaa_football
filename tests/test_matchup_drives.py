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
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
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
            return list(captured.events)

        yield run


def _drive(number, band, offense, result, *, scoring_side=None, scoring=False,
           start=25, end=60, on_field=True, color="#123456", source="primary"):
    """One srv_drive row. Colours sit on opponent_*, which is where srv_drive actually has
    them — the identity pair is asymmetric and there is no offense_color_*."""
    return {
        "drive_number": number, "band": band, "band_order": 1 if band == "home" else 2,
        "is_home_offense": band == "home",
        "offense_team_display": offense, "offense_logo_url": None,
        "opponent_team_display": "Other", "opponent_color_on_light": color,
        "opponent_color_on_dark": color, "opponent_color_source": source,
        "drive_result": result, "drive_result_category": "unknown",
        "scoring_side": scoring_side, "is_scoring_drive": scoring,
        "plays": 5, "yards": end - start, "elapsed_display": "2:00",
        "start_yards_from_own_goal": start, "end_yards_from_own_goal": end,
        "is_end_on_field": on_field, "is_negative_drive": end < start,
        "end_offense_score": 7, "end_defense_score": 0,
        "as_of_ts": pd.Timestamp("2026-09-08T00:00:00Z"),
    }


def _text(entries):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)) for _, body in entries)


# --- it draws the drives -------------------------------------------------------------------

def test_every_drive_is_drawn(panel):
    """The regression this file is named for: the panel silently stopping."""
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT"),
                          _drive(2, "away", "Beta", "PUNT"),
                          _drive(3, "home", "Alpha", "FG", scoring_side="offense", scoring=True)])
    entries = panel(frame)
    drawn = [b for kind, b in entries if kind == "markdown" and "border-left" in b]
    assert len(drawn) == 3, f"expected one row per drive, drew {len(drawn)}"
    body = _text(entries)
    for team in ("Alpha", "Beta"):
        assert team in body
    assert "3 drives" in body and "1 scoring" in body


def test_scoring_drives_are_distinguishable_at_a_glance(panel):
    """The whole point of the artefact. A scoring drive must not render identically to a punt."""
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT"),
                          _drive(2, "home", "Alpha", "TD", scoring_side="offense", scoring=True)])
    drawn = [b for kind, b in panel(frame) if kind == "markdown" and "border-left" in b]
    assert len(drawn) == 2
    highlighted = [b for b in drawn if "rgba(120,160,120" in b]
    assert len(highlighted) == 1, "exactly the scoring drive should carry the highlight"
    assert "TD" in highlighted[0]


def test_a_defense_touchdown_is_not_credited_to_the_offense(panel):
    """⚠️ THE ONE THAT MATTERS. `INT TD` means the DEFENSE scored.

    A panel keying off the substring "TD" marks this as an offensive score and puts ~908
    drives on the wrong side of the game — while looking entirely healthy. `scoring_side` is
    the column; the text is not.
    """
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "INT TD",
                                 scoring_side="defense", scoring=True)])
    body = _text([e for e in panel(frame) if "border-left" in e[1]])
    assert "defense" in body, "a defensive score must say so"
    assert "offense" not in body, "INT TD credited to the offense — read scoring_side, not the text"


def test_each_band_takes_its_own_colour(panel):
    """srv_drive has no offense_color_*; a band's colour comes off the OTHER band's
    opponent_color_*. If that recovery breaks, both bands collapse to one accent."""
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", color="#aa0000"),
                          _drive(2, "away", "Beta", "PUNT", color="#0000bb")])
    drawn = [b for kind, b in panel(frame) if kind == "markdown" and "border-left" in b]
    accents = {re.search(r"border-left:4px solid (#\w+)", b).group(1) for b in drawn}
    assert len(accents) == 2, f"both bands rendered the same accent: {accents}"


def test_an_off_field_end_coordinate_keeps_the_row_and_drops_the_bar(panel):
    """0.15% of drives carry a broken end coordinate. A missing possession is a worse lie
    than a bar that admits it does not know where it ended."""
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "TD", end=193, on_field=False)])
    drawn = [b for kind, b in panel(frame) if kind == "markdown" and "border-left" in b]
    assert len(drawn) == 1, "the drive must still be listed"
    assert "position unavailable" in drawn[0]
    assert not re.search(r"left:[\d.]+%;width:[\d.]+%", drawn[0]), \
        "no field-position bar should be drawn from a broken coordinate"


# --- and it says so when it cannot ---------------------------------------------------------

def test_no_drives_is_empty_not_a_blank_panel(panel):
    """Empty is a state with a sentence, never a zero-row render.

    ⚠️ DRIVEN AT 2023 EXPLICITLY SINCE R-730. This test's claim is the SCOPE one — "we
    collect from 2024 onward" — and it used to pass on copy that never looked at the season,
    so it could not have failed if the sentence was wrong for a modern game. It was. The
    2026 branch is asserted separately below.
    """
    entries = panel(pd.DataFrame(), season=2023)
    body = _text(entries)
    assert "2024" in body, "the Empty state must say why there are none"
    assert not [b for k, b in entries if k == "markdown" and "border-left" in b]


def test_a_fallback_colour_is_named_rather_than_silently_neutral(panel):
    """Degraded is not Empty. The drives are all here; a side's colour is cfdb's."""
    frame = pd.DataFrame([_drive(1, "home", "Alpha", "PUNT", color="#6b6b68", source="fallback"),
                          _drive(2, "away", "Beta", "PUNT")])
    captions = " ".join(b for k, b in panel(frame) if k == "caption")
    assert "cfdb's rather than the team's" in captions
    drawn = [b for k, b in panel(frame) if k == "markdown" and "border-left" in b]
    assert len(drawn) == 2, "a degraded colour must not drop the drives"


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
    out_of_scope = _text(panel(pd.DataFrame(), season=2023))
    not_yet = _text(panel(pd.DataFrame(), season=2026))
    assert out_of_scope != not_yet, (
        "a 2023 game and a 2026 game were told the same thing about why there are no drives, "
        "which is the R-730 defect: one is permanent scope and the other is latency")


def test_a_completed_modern_game_is_told_the_data_has_not_LANDED(panel):
    """The state nothing said until now: 2024+, the game is over, the drives have not arrived.

    ⚠️ THE WINDOW IS THE POINT — it opens when the game ends and closes when the next
    collection lands, which is exactly when a reader opens the page to see what happened.
    """
    body = _text(panel(pd.DataFrame(), season=2026))
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
    body = _text(panel(pd.DataFrame(), season=1999))
    assert "2024 onward" in body, "a pre-2024 game must still be told this is scope"
    assert "not arrived yet" not in body, (
        "a 1999 game was told its drives have not arrived YET, which promises data that will "
        "never exist")
