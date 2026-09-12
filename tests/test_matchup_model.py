"""The Matchup model panel: every model number on the site, and the sign convention twice.

WHY THIS FILE DID NOT EXIST UNTIL R-517. B080's panel-invocation census found that nothing
in `tests/` calls `_model` — the panel carrying the predicted margin, the predicted total,
the win probability, the cover edge and the actual-margin reconciliation was executed by
nothing. The gap had already cost something: a line re-wrap dropped four words from the
reconciliation caption and an `ast` string census caught it, because the suite could not.

🚨 THE RECONCILIATION CAPTION IS WHY THIS FILE MATTERS MORE THAN ITS SIZE SUGGESTS. It is
the ONE place on the site that states both margin conventions side by side:

    Actual margin -1.0 from the home perspective (+1.0 as cfdb stores it, away minus home).

R-544: A083 found the market recap treating `actual_margin` as home-perspective when it is
away-minus-home — "both branches were each other's, so the sign inverted on EVERY graded
game". Nothing checked this caption.

⚠️ AND A083'S OWN TEST PASSED AGAINST THE BUGGY CODE ON ITS FIRST DRAFT, because under the
inversion "is it negative" was true for the wrong reason. So the assertion here is
POSITIONAL, never a sign check: the value in the home-perspective slot must be the row's
`actual_margin_home_perspective`, and the value in the parenthetical must be its
`actual_margin`. A test that asked "is one of them negative" would pass on the swap, which
is precisely the failure it is supposed to catch. It is run in BOTH directions — a home loss
and a home win — because a convention that is only ever exercised one way is only half
tested.

THE FIXTURE IS A REAL ROW, read back from `srv_game` for game 401754591 (Clemson at
Louisville, week 12 2025). Louisville lost by one, so the home perspective is -1 and cfdb
stores +1. If a rendered figure disagrees with this fixture, the fixture is wrong.

⚠️ `home_win_probability` DEFAULTS TO None HERE BECAUSE THAT IS THE ONLY VALUE IT HAS EVER
HAD: R-572 measured it null in all 111,049 rows of srv_game. The em dash is not an edge case
on this column, it is the whole of its history. One test below deliberately supplies a value
anyway, so that this file keeps testing the metric rather than the outage.
"""
import html
import re
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_harness  # noqa: E402


def _stub_streamlit():
    """Capture what the panel emits instead of rendering it."""
    captured = []

    def recorder(kind):
        def call(*args, **kwargs):
            captured.append((kind, " ".join(str(a) for a in args)))
        return call

    stub = types.ModuleType("streamlit")
    for name in ("subheader", "caption", "markdown", "write", "info", "warning", "error"):
        setattr(stub, name, recorder(name))

    class _Col:
        def metric(self, label, value, help=None):
            captured.append(("metric", f"{label} {value} {help or ''}"))

    stub.columns = lambda n: [_Col() for _ in range(n if isinstance(n, int) else len(n))]
    stub.button = lambda *a, **k: False

    def cache(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda fn: fn

    stub.cache_data = stub.cache_resource = cache
    stub.session_state = {}
    return stub, captured


# The modules that hold their own `import streamlit`. ⚠️ lib.attribution and lib.chips are
# here and are NOT in the line-movement file's list: `_model` ends by calling
# `attribution.model_attribution`, and its two Empty branches are built by `lib.chips`.
# Without them the licence caption renders into the REAL streamlit, where the capture cannot
# see it — and the assertion that the attribution travels with the numbers would be testing
# nothing at all.
_RELOAD = ("lib.states", "lib.table", "lib.identity", "lib.chips", "lib.attribution",
           "views.matchup")


def _reload_all():
    import importlib
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))


@pytest.fixture
def panel():
    """The panel with streamlit captured, ready to be handed a row.

    ⚠️ IT PUTS THE MODULES BACK. Reloading lib.states against a stub binds the stub inside
    it for the REST OF THE SESSION, and test_matchup_drives learned that the hard way — six
    unrelated tests failed. `monkeypatch` cannot undo it either: its sys.modules restore
    runs after this teardown, so the swap and the restore are both done by hand here.
    """
    real = sys.modules.get("streamlit")
    stub, captured = _stub_streamlit()
    sys.modules["streamlit"] = stub
    _reload_all()
    matchup = sys.modules["views.matchup"]

    def run(row):
        captured.clear()
        matchup._model(pd.Series(row))
        # 🚨 R-610. AN ERROR STATE IS NOT A PASSING STATE. B091 shipped `deltas or {}` —
        # `Series.__bool__` raises — and `states.section` caught it and drew a card, so this
        # whole file stayed green on a panel that had died on its first line. The live render
        # found it. `assert_no_error_card` reads what was DRAWN, so it works for a fixture
        # that rolls its own stub, which seven of the nine matchup files do.
        render_harness.assert_no_error_card(captured, "the model panel")
        return list(captured)

    yield run

    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    _reload_all()


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
        "predicted_margin": -7.386955,
        "predicted_margin_home_perspective": 7.386955,
        "predicted_total_points": 48.474485,
        "predicted_home_points": 27.93072,
        "predicted_away_points": 20.543765,
        # R-572: null in all 111,049 rows of srv_game. This is the real value.
        "home_win_probability": None,
        "home_cover_edge": 5.886955,
        "is_out_of_sample_week": False,
        # Louisville were at home and lost by one.
        "actual_margin": 1,
        "actual_margin_home_perspective": -1,
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
    hits = [b for k, b in entries if k == "metric" and b.startswith(label + " ")]
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
    return hits[0][len(label):].strip().split(" ")[0]


def _captions(entries):
    return [_plain(body) for kind, body in entries if kind == "caption"]


_RECONCILIATION = re.compile(
    r"Actual margin (?P<home>[-+][\d.,]+) from the home perspective "
    r"\((?P<stored>[-+][\d.,]+) as cfdb stores it, away minus home\)")


def _reconciliation(entries):
    """The two margins, each read from ITS OWN named position in the sentence."""
    for caption in _captions(entries):
        found = _RECONCILIATION.search(caption)
        if found:
            return found.group("home"), found.group("stored")
    raise AssertionError(
        "the reconciliation caption did not render in its stated shape; captions were "
        f"{_captions(entries)}")


# --- the four figures ------------------------------------------------------------------------

def test_each_model_figure_lands_in_its_own_metric(panel):
    """Four figures, four labels, none interchangeable.

    The margin and the cover edge are the dangerous pair: +7.4 and +5.9 are both plausible
    as either, both positive, and a swap would render perfectly.
    """
    entries = panel(_row())
    assert _metric(entries, "Predicted margin (home)") == "+7.4"
    assert _metric(entries, "Predicted total") == "48.5"
    assert _metric(entries, "Cover edge") == "+5.9"


def test_the_predicted_margin_is_the_home_perspective_column_not_the_stored_one(panel):
    """⚠️ THE SAME INVERSION AS R-544, ONE PANEL EARLIER IN THE PAGE.

    `predicted_margin` is -7.39 and `predicted_margin_home_perspective` is +7.39 on this
    game: the model has the HOME team winning by 7.4. A panel that reached for
    `predicted_margin` because the name is shorter would render "-7.4" under a label reading
    "Predicted margin (home)" and say the away team was favoured.
    """
    assert _metric(panel(_row()), "Predicted margin (home)") == "+7.4"


def test_positive_predicted_margin_means_the_home_team_wins_and_says_so(panel):
    """AC: the help travels with the figure, on the metric, not merely on the page."""
    block = [b for k, b in panel(_row())
             if k == "metric" and b.startswith("Predicted margin (home) ")]
    assert block and "Positive means the model has the home team winning" in block[0]


# --- the reconciliation: the reason this file exists ------------------------------------------

def test_the_reconciliation_puts_each_margin_in_its_OWN_stated_position(panel):
    """🚨 R-544's defect, at the one place on the site that states both conventions.

    ⚠️ POSITIONAL, NOT A SIGN CHECK. A083's first draft of the equivalent test passed
    against the inverted code because "is it negative" was true for the wrong reason. This
    asserts that the figure introduced as "from the home perspective" IS the row's
    `actual_margin_home_perspective`, and that the one introduced as "as cfdb stores it,
    away minus home" IS its `actual_margin`. Swap the two in the panel and both assertions
    fail.
    """
    home, stored = _reconciliation(panel(_row()))
    assert home == "-1.0", \
        "the home-perspective slot is not carrying actual_margin_home_perspective"
    assert stored == "+1.0", \
        "the parenthetical is not carrying actual_margin as cfdb stores it"


def test_the_reconciliation_holds_when_the_home_team_WON(panel):
    """The other direction, because a convention exercised one way is half tested.

    Louisville lost this game by one. Here they win by ten, so the home perspective is +10
    and cfdb stores -10 — every sign in the sentence flips, and each must flip in its own
    position rather than the two trading places.
    """
    home, stored = _reconciliation(
        panel(_row(actual_margin=-10, actual_margin_home_perspective=10)))
    assert home == "+10.0"
    assert stored == "-10.0"


def test_the_two_readings_are_opposites_of_one_another(panel):
    """The property that makes the sentence true at all: same result, two ends.

    Kept SEPARATE from the positional assertions above deliberately. This one would still
    pass on a swap — it is here to catch a panel that rendered the same column twice, which
    the positional test would not notice if both slots agreed with one column.
    """
    home, stored = _reconciliation(panel(_row()))
    assert float(home) == -float(stored), \
        "the two readings are not opposites — one column was rendered into both slots"


def test_an_ungraded_game_states_no_actual_margin_at_all(panel):
    """A game that has not been played has no result to reconcile.

    Absent, not zero: a 0.0 here would claim a tie that never happened.
    """
    entries = panel(_row(actual_margin=None, actual_margin_home_perspective=None))
    body = _text(entries)
    assert "Actual margin" not in body
    assert _metric(entries, "Predicted margin (home)") == "+7.4", \
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
    assert _metric(entries, "Predicted margin (home)") == "+7.4", \
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
    assert "random_forest_score" in caption
    assert "98d34949266b" in caption, "the model version key is not on the page"


def test_the_out_of_sample_chip_appears_only_when_the_week_is_out_of_sample(panel):
    """AC-12.5. The chip is a claim about the training cut, and a chip that always showed
    would be no claim at all."""
    assert "Out-of-sample week" not in _text(panel(_row(is_out_of_sample_week=False)))
    assert "Out-of-sample week" in _text(panel(_row(is_out_of_sample_week=True)))
