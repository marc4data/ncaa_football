"""The Matchup model panel: every model number on the site, in one sign convention.

WHY THIS FILE DID NOT EXIST UNTIL R-517. B080's panel-invocation census found that nothing
in `tests/` calls `_model` — the panel carrying the model line, the predicted total, the win
probability, the cover edge and the result was executed by nothing.

🚨 ONE CONVENTION FOR EVERY LINE (cfdb-wtc-R-2550, Marc's decision 2026-10-01). The panel used
to show the model's margin HOME-POSITIVE beside a header that prints the market's line
HOME-NEGATIVE — *"Flipping the sign on 2 values that are compared makes things difficult to
comprehend."* The model line is now the stored `predicted_margin` (away − home, the market's
sign), shown beside the home team's name exactly as the header shows `spread`:

    header      LOU -1.5          model line      LOU -7.4

So the assertions here are POSITIONAL and carry the sign: the "Model line" tile must hold the
stored value, and a panel that reached for a flipped copy would render "+7.4" and fail.

The RESULT is a score, said once ("Final score 20 – 19 (away – home)"). It used to print the
actual margin two ways; R-544's inversion lived in exactly that kind of sentence.

THE FIXTURE IS A REAL ROW, read back from `srv_game` for game 401754591 (Clemson at
Louisville, week 12 2025, Clemson won 20–19). Its model columns are the random-forest row the
file was written against. If a rendered figure disagrees with this fixture, the fixture is
wrong.

⚠️ `home_win_probability` DEFAULTS TO None HERE BECAUSE THAT IS THE ONLY VALUE IT HAS EVER
HAD: R-572 measured it null in all 111,049 rows of srv_game. One test below deliberately
supplies a value anyway, so that this file keeps testing the metric rather than the outage.
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
    """The panel on the SHARED harness (R-613).

    🚨 THIS FILE USED TO ROLL ITS OWN STREAMLIT STUB, AND SEVEN OF THE NINE MATCHUP FILES DID.
    R-631 built `tests/render_harness.py` "after five rounds rebuilt one"; this page then did
    it five more times. B092 had to detect a dead panel through DRAWN MARKUP rather than
    through the harness precisely because a harness-level guard would have reached two files
    of nine.

    ⚠️ THE ASSERTIONS BELOW ARE UNCHANGED because `captured.events` carries the same
    `(kind, body)` pairs the bespoke stub produced. `Capture` is a `list` subclass, so the
    harness's own callers still see a list of strings — the addition is inert for session A.

    ⚠️ `views.matchup` IS IMPORTED INSIDE THE STUB. It is not in the harness's RELOAD list, so
    a copy imported before the swap would bind the real streamlit and the capture would be
    empty. The harness reloads every `views.*` bound to the stub on the way out.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
        matchup = importlib.reload(importlib.import_module("views.matchup"))

        def run(row):
            captured.clear()
            matchup._model(pd.Series(row))
            # 🚨 R-610. AN ERROR STATE IS NOT A PASSING STATE. B091's `deltas or {}` raised,
            # `states.section` drew a card, and this file stayed green on a dead panel.
            render_harness.assert_no_error_card(captured, "the model panel")
            return list(captured.events)

        yield run


ATTRIBUTION = ("cfdb model, built on a licensed CFB Model Training Pack (2026 Edition). "
               "Not an official CollegeFootballData.com prediction.")


def _row(**overrides):
    """One srv_game row's worth of model columns, read back from game 401754591."""
    row = {
        "season": 2025,
        "week": 12,
        "training_week_floor": 5,
        "model_name": "random_forest_score",
        "model_family": "random_forest",
        "model_version_key": "98d34949266b",
        "home_team": "Louisville",
        "home_abbreviation": "LOU",
        "away_team": "Clemson",
        "predicted_margin": -7.386955,
        "predicted_total_points": 48.474485,
        "predicted_home_points": 27.93072,
        "predicted_away_points": 20.543765,
        # R-572: null in all 111,049 rows of srv_game. This is the real value.
        "home_win_probability": None,
        "home_cover_edge": 5.886955,
        "is_out_of_sample_week": False,
        # Louisville were at home and lost by one: Clemson 20, Louisville 19.
        "actual_margin": 1,
        "home_points": 19,
        "away_points": 20,
        "attribution": ATTRIBUTION,
    }
    row.update(overrides)
    return row


def _plain(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def _text(entries):
    return " ".join(_plain(body) for _, body in entries)


def _metric(entries, label):
    """THE VALUE OF ONE NAMED METRIC.

    Reading a figure out of the block that carries its label is what makes these assertions
    survive a transposition — `"+7.4" in body` passes when two metrics are swapped.
    """
    # ⚠️ R-613: THE SHARED HARNESS SEPARATES A METRIC'S LABEL FROM ITS VALUE WITH ` :: `,
    # where this file's own stub used a space. The separator is the harness's and it is the
    # better one — unambiguous when a value itself contains spaces — so the parser moved
    # rather than the format.
    hits = [b for k, b in entries if k == "metric" and b.startswith(label + " :: ")]
    if not hits:
        raise AssertionError(f"no metric labelled {label!r} was drawn; "
                             f"drew {[b for k, b in entries if k == 'metric']}")
    # ⚠️ AMBIGUITY IS AN ERROR, NOT A COIN TOSS. On the whole page "Home win probability" is
    # a PREFIX of line movement's "Home win probability move", and a helper that returned the
    # first match would read the wrong panel's figure and say nothing. These tests call one
    # panel at a time so it cannot arise here — this makes sure it can never arise quietly.
    if len(hits) > 1:
        raise AssertionError(f"{label!r} matched {len(hits)} metrics, so the figure read back "
                             f"is ambiguous: {hits}")
    return hits[0][len(label) + len(" :: "):].strip().split(" ")[0]


def _captions(entries):
    return [_plain(body) for kind, body in entries if kind == "caption"]


def _line(entries, label):
    """A LINE TILE'S VALUE: the team named, then its signed number — "LOU -7.4"."""
    hits = [b for k, b in entries if k == "metric" and b.startswith(label + " :: ")]
    assert len(hits) == 1, f"expected one metric labelled {label!r}, drew {hits}"
    return " ".join(hits[0][len(label) + len(" :: "):].strip().split(" ")[:2])


# --- the four figures ------------------------------------------------------------------------

def test_each_model_figure_lands_in_its_own_metric(panel):
    """Four figures, four labels, none interchangeable.

    The line and the cover edge are the dangerous pair: 7.4 and 5.9 are both plausible as
    either, and a swap would render perfectly.
    """
    entries = panel(_row())
    assert _line(entries, "Model line") == "LOU -7.4"
    assert _metric(entries, "Predicted total") == "48.5"
    assert _metric(entries, "Cover edge") == "+5.9"


def test_the_model_line_reads_in_the_MARKETS_sign_not_a_flipped_one(panel):
    """🚨 cfdb-wtc-R-2550: ONE CONVENTION. The header prints the home team's line as the market
    does — a home favourite is NEGATIVE ("LOU -1.5" on this game). The model's line sits beside
    it in the same sign: the model has Louisville by 7.4, so "LOU -7.4".

    ⚠️ POSITIONAL AND SIGNED. A panel that read the old home-positive copy
    (`predicted_margin_home_perspective`, +7.39 on this game) would render "LOU +7.4" — the
    opposite of the header's convention, which is the thing Marc asked to stop.
    """
    assert _line(panel(_row()), "Model line") == "LOU -7.4"


def test_an_away_favourite_reads_positive_like_the_market(panel):
    """The other direction, because a convention exercised one way is half tested: a model that
    has Clemson by 3 is "LOU +3.0", exactly as the market would quote it."""
    assert _line(panel(_row(predicted_margin=3.0)), "Model line") == "LOU +3.0"


def test_the_model_line_says_how_to_read_it(panel):
    """The help travels with the figure, on the metric, not merely on the page."""
    block = [b for k, b in panel(_row()) if k == "metric" and b.startswith("Model line ")]
    assert block and "negative means the home team is favored" in block[0]


# --- the result: a score, said once ----------------------------------------------------------

_RESULT = re.compile(r"Final score (?P<away>\d+) – (?P<home>\d+) \(away – home\)")


def _result(entries):
    found = [m for c in _captions(entries) for m in [_RESULT.search(c)] if m]
    assert len(found) == 1, f"expected the result once; captions were {_captions(entries)}"
    return found[0].group("away"), found[0].group("home")


def test_the_result_is_the_score_away_then_home(panel):
    """POSITIONAL. Clemson (away) 20, Louisville (home) 19 — distinct numbers, so a swap fails."""
    assert _result(panel(_row())) == ("20", "19")


def test_the_result_no_longer_restates_the_margin_two_ways(panel):
    """The old caption printed the actual margin twice, from both ends — R-544's inversion lived
    in exactly that kind of sentence. One statement of the result, as a score."""
    body = _text(panel(_row()))
    assert "Actual margin" not in body and "home perspective" not in body


def test_an_ungraded_game_states_no_result_at_all(panel):
    """A game that has not been played has no result. Absent, not zero: 0 – 0 would claim a
    scoreless tie that never happened."""
    entries = panel(_row(actual_margin=None, home_points=None, away_points=None))
    assert "Final score" not in _text(entries)
    assert _line(entries, "Model line") == "LOU -7.4", \
        "the forecast stopped drawing because the result was missing"


# --- null versus zero ------------------------------------------------------------------------

def test_home_win_probability_is_OMITTED_rather_than_promised_as_an_em_dash(panel):
    """🚨 R-579 REVERSES WHAT THIS TEST USED TO ASSERT, AND THE REASON IS THE MEASUREMENT.

    It used to assert an em dash, on the grounds that AC-G.32 makes a null honest. That was
    right about one game and wrong about the column: A090 established the value is null in
    ALL 111,049 rows, and why — srv_game's `latest_prediction` prefers a margin model, and the
    margin and probability models are disjoint. So the tile never showed a number in its life.

    An em dash says "we have no figure for THIS game". A tile that has never once been filled
    says something else, and the honest rendering is to omit it until R-578 populates the
    column. ⚠️ Driven by the null, not by a caption — see the note on `tiles` in `_model`.
    """
    entries = panel(_row())
    labels = [b for k, b in entries if k == "metric"]
    assert not any(b.startswith("Home win probability ") for b in labels), \
        "the panel is still promising a number the column has never carried"
    assert len(labels) == 3, f"three tiles, not four, while the column is null: {labels}"


def test_a_published_home_win_probability_WOULD_render_at_three_decimals(panel):
    """⚠️ THE TEST THAT KEEPS THE ONE ABOVE HONEST, AND R-579 MADE IT LOAD-BEARING.

    The tile is omitted while the column is null, so without this the file would assert only
    an absence — and an absence passes just as well when the metric has been deleted by
    accident. This supplies a value, proves the tile RETURNS, and pins the format: a
    probability lives in the third decimal, because .184 and .238 must not both read 0.2.
    """
    entries = panel(_row(home_win_probability=0.6182))
    assert _metric(entries, "Home win probability") == "0.618"
    assert len([b for k, b in entries if k == "metric"]) == 4, \
        "the omitted tile did not come back when the column carried a value"


def test_a_zero_cover_edge_and_a_missing_one_are_different_statements(panel):
    """AC-G.32. An edge of exactly zero is a measurement — the model agrees with the book.
    A missing edge is the absence of one. They must never render the same."""
    assert _metric(panel(_row(home_cover_edge=0.0)), "Cover edge") == "0.0"
    assert _metric(panel(_row(home_cover_edge=None)), "Cover edge") == "—"


# --- the two absences, which are different claims ---------------------------------------------

def test_a_game_before_the_training_floor_says_TOO_EARLY_not_NOTHING_KNOWN(panel):
    """The panel's own comment: collapsing these two would be the site's worst kind of lie.

    Week 2 of a season whose model floor is Week 5 is "the model does not forecast this
    week", which is a statement about the model's training cut.
    """
    body = _text(panel(_row(week=2, predicted_margin=None)))
    assert "would be here" in body, "the Empty state did not render"
    assert "Week 2" in body, "the Empty state did not name the week that was asked for"
    assert "No model has scored this game" not in body, \
        "a too-early game was described as one we have nothing for"


def test_a_game_with_no_model_at_all_says_the_OTHER_thing(panel):
    """Week 12 is past the floor, so an absent prediction is not a training-cut statement."""
    body = _text(panel(_row(predicted_margin=None)))
    assert "No model has scored this game" in body
    assert "Week 12" not in body, "a scored-era game was explained by the training floor"


def test_an_empty_forecast_draws_no_figures(panel):
    """B076's lesson: an Empty state rendering ABOVE a grid that also drew looks exactly
    like the assertion above passing."""
    entries = panel(_row(predicted_margin=None))
    assert not [b for k, b in entries if k == "metric"], \
        "an Empty model panel still drew figures"


# --- the licence boundary ---------------------------------------------------------------------

def test_the_attribution_travels_with_the_numbers(panel):
    """AC-G.41. An unattributed prediction is the one thing the licence forbids.

    The wording lives in `dim_model_version.attribution` and reaches the page as a column,
    so the page cannot render the numbers without it — provided the page actually calls for
    it, which is what this asserts.
    """
    caption = " ".join(_captions(panel(_row())))
    assert "licensed CFB Model Training Pack" in caption
    assert "Not an official CollegeFootballData.com prediction" in caption


def test_a_missing_attribution_is_reported_as_a_DEFECT_not_quietly_omitted(panel):
    """AC-G.41 again, from the other side. Silence here would be a licence breach that
    looks like a tidy page."""
    stripped = {k: v for k, v in _row().items() if k != "attribution"}
    entries = panel(stripped)
    caption = " ".join(_captions(entries))
    assert "defect" in caption.lower(), \
        "a prediction rendered with no attribution and no complaint"
    assert _line(entries, "Model line") == "LOU -7.4", \
        "the numbers stopped drawing rather than the omission being reported"


# --- the rest of the panel --------------------------------------------------------------------

def test_the_predicted_score_reads_away_then_home_and_says_which(panel):
    """20.5 – 27.9 is meaningless without the order, and the order is not guessable."""
    caption = " ".join(_captions(panel(_row())))
    assert "20.5 – 27.9" in caption, "the predicted score is missing or transposed"
    assert "(away – home)" in caption, "the score does not say which end is which"


def test_the_model_and_its_version_are_named(panel):
    """A number from an unnamed version cannot be reproduced or retired."""
    caption = " ".join(_captions(panel(_row())))
    # ⚠️ A274 (cfdb-main-R-4537) EDITED THIS LINE AND IT IS SESSION B's FILE (§3.2.2).
    # A274 added the pack model to `lib/models.DISPLAY_NAMES`, which B157's own caption
    # reads, so the key is no longer what the page prints. The MODEL IS STILL NAMED and
    # the version key is still asserted below — the test's intent is unchanged, only
    # the string it pins. Nothing else in this file was touched.
    assert "Random Forest Score Model (Training Pack)" in caption
    assert "98d34949266b" in caption, "the model version key is not on the page"


def test_the_SECTION_HEADING_as_RENDERED_carries_the_brand(panel):
    """Marc, 2026-10-01: *"can you change the header on Matchup page from 'Model' to
    'M4D Model'?"* (cfdb-wta-R-2950).

    🚨 THIS ASSERTS THE RENDERED HEADING, NOT THE LITERAL PASSED TO `fmt.title_case`, AND
    THAT IS THE WHOLE POINT. `title_case` capitalises an all-lowercase word and leaves a
    mixed-case one alone, so `"m4d model"` would ship as `M4d Model` while the source line
    still read correct to anyone grepping for the string. Measured both ways when this was
    written: `title_case("M4D Model") -> "M4D Model"`, `title_case("m4d model") -> "M4d
    Model"`. A test on the constant cannot tell those apart; this one can.
    """
    headings = [_plain(body) for kind, body in panel(_row()) if kind == "subheader"]
    assert headings, "the panel drew no section heading at all, so this would pass on nothing"
    assert "M4D Model" in headings, (
        f"the Model section no longer announces the brand; it drew {headings}")
    assert "M4d Model" not in headings, (
        "the brand was case-mangled on the way to the page — `title_case` lower-cased the D, "
        "which means the literal reached it all-lowercase")


def test_the_caption_does_not_LABEL_the_model_under_a_heading_that_already_did(panel):
    """cfdb-main-R-3666. The caption used to open `Model <name>`, which under a section
    headed "M4D Model" put the word three times in two lines.

    ⚠️ THE LABEL WAS RIGHT WHEN THE VALUE WAS A RAW KEY and is wrong now that
    `models.display_name` returns a name ending in "Model". The caption still NAMES the
    model — `test_the_model_and_its_version_are_named` is the assertion for that, and it is
    deliberately left alone — this one pins only that the redundant label is gone.
    """
    captions = _captions(panel(_row()))
    named = [c for c in captions if "Random Forest Score Model (Training Pack)" in c]
    assert len(named) == 1, f"expected one caption naming the model, drew {captions}"
    assert named[0].startswith("Random Forest Score Model (Training Pack)"), (
        f"the caption still leads with a label before the model's name: {named[0]!r}")


def test_the_out_of_sample_chip_appears_only_when_the_week_is_out_of_sample(panel):
    """AC-12.5. The chip is a claim about the training cut, and a chip that always showed
    would be no claim at all."""
    assert "Out-of-sample week" not in _text(panel(_row(is_out_of_sample_week=False)))
    assert "Out-of-sample week" in _text(panel(_row(is_out_of_sample_week=True)))
