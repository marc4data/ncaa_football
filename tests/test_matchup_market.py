"""The Matchup market panel: the book's four prices and the caveats that make them readable.

WHY THIS FILE DID NOT EXIST UNTIL R-517, AND WHAT THAT COST. B080's panel-invocation census
found that `_market` and `_model` are called by NOTHING in `tests/` — ten of the fourteen
call sites it was changing had no coverage at all. The gap had already cost something
measurable: a line re-wrap in `_model` silently dropped four words from a caption, and it
was an `ast` string census that caught it rather than review or the suite, "which does not
execute `_model`".

`states.section` turns any exception inside a panel into the Error state — plain language,
no traceback, exactly as designed — so a panel that has stopped drawing looks like a handled
failure. `ci/check_page_queries.py` executes the page's query and so covers a renamed or
dropped column; what neither it nor anything else can see is whether the panel still DRAWS.

ASSERT ON IDENTITY, NOT ON PRESENCE — B076's lesson, and it is the rule this file is built
on. B076's first assertion order passed while the panel was broken, because a neighbouring
guard rendered Empty above the grid being checked. "-1.5 appears somewhere in the body" is
the weak form and it would survive the two prices being transposed; "-1.5 is the value of
the metric labelled Spread (home)" is the assertion. Every figure here is read out of its
own metric block by label.

THE FIXTURE IS A REAL ROW. Every value below was read back from `srv_game` for game
401754591 — Clemson at Louisville, week 12 2025 — not invented. A fixture that disagrees
with the page is a fixture that is wrong.
"""
import html
import re
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))


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


# The modules that hold their own `import streamlit`. Reloading the view alone leaves
# lib.states emitting into the REAL streamlit, so the Empty state renders somewhere the
# capture cannot see it. ⚠️ lib.chips is here and is NOT in the line-movement file's list:
# `_market` ends with `chips.spread_sign_note()`, which is a caption of its own.
_RELOAD = ("lib.states", "lib.table", "lib.identity", "lib.chips", "views.matchup")


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
        matchup._market(pd.Series(row))
        return list(captured)

    yield run

    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    _reload_all()


def _row(**overrides):
    """One srv_game row's worth of market columns, read back from game 401754591."""
    row = {
        "spread": -1.5,
        "over_under": 51.0,
        "home_moneyline": -145,
        "away_moneyline": 145,
        "spread_open": -3.5,
        "over_under_open": 51.5,
        "provider_key": "bovada",
        "line_snapshot_ts": pd.Timestamp("2026-08-15 02:01:39.671339+00:00"),
        "market_implied_home_win_probability": 0.591837,
        "market_implied_away_win_probability": 0.408163,
        "overround": 1.0,
        "devig_method": "multiplicative",
    }
    row.update(overrides)
    return row


def _plain(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def _text(entries):
    return " ".join(_plain(body) for _, body in entries)


def _metric(entries, label):
    """THE VALUE OF ONE NAMED METRIC — the whole point of this helper.

    Reading a figure out of the block that carries its label is what makes these assertions
    survive a transposition. `"-145" in body` passes when the two moneylines are swapped.
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


# --- the four prices -------------------------------------------------------------------------

def test_each_price_lands_in_its_own_metric(panel):
    """Four prices, four labels, and NONE of them interchangeable.

    ⚠️ THE MONEYLINES ARE THE PAIR THAT MATTERS. -145 and +145 are both true of this game
    and mean opposite things; a panel that swapped them would render perfectly. Asserting
    `"-145" in body` passes on the swapped version, which is why every figure here is read
    out of its own labelled block.
    """
    entries = panel(_row())
    assert _metric(entries, "Spread (home)") == "-1.5"
    assert _metric(entries, "Total") == "51.0"
    assert _metric(entries, "Home moneyline") == "-145"
    assert _metric(entries, "Away moneyline") == "+145"


def test_the_home_favourite_sign_is_explained_on_the_spread_itself(panel):
    """AC-1.4. The number a reader is most likely to invert says which way it runs.

    On the METRIC, not merely somewhere on the page: the help travels with the figure it
    disambiguates, and a note that drifted onto a neighbour would be no help at all.
    """
    spread = [b for k, b in panel(_row()) if k == "metric" and b.startswith("Spread (home) ")]
    assert spread and "Negative means the home team is favoured" in spread[0]


def test_the_book_is_named_and_its_opening_line_travels_with_it(panel):
    """Every price here is ONE book's by construction.

    A price with no book attached is the provenance defect the `market_implied_` prefix rule
    exists to prevent, and it renders perfectly while being wrong. The opening line is in the
    same sentence because an opening price from a different book is not an opening price.
    """
    caption = " ".join(_captions(panel(_row())))
    assert "bovada" in caption, "the panel does not say whose prices these are"
    assert "-3.5" in caption, "the opening spread is missing"
    assert "51.5" in caption, "the opening total is missing"


def test_an_unnamed_book_says_so_rather_than_going_quiet(panel):
    """A null provider is still a provenance statement, and it must be a visible one."""
    caption = " ".join(_captions(panel(_row(provider_key=None))))
    assert "an unnamed book" in caption


# --- the de-vigged probabilities -------------------------------------------------------------

def test_the_implied_probabilities_are_devigged_and_the_overround_is_named(panel):
    """R-544's neighbourhood: a de-vigged number presented without its method or its
    overround is a derived figure wearing the authority of a quoted one."""
    caption = " ".join(_captions(panel(_row())))
    assert "59.2%" in caption, "the home implied probability is missing or misrounded"
    assert "40.8%" in caption, "the away implied probability is missing or misrounded"
    assert "multiplicative" in caption, "the de-vig method is not stated"
    assert "1.0000" in caption, "the overround is not stated at four decimals"


def test_no_implied_probability_means_no_claim_about_one(panel):
    """The book priced no probability, so the panel says nothing about one — and still
    draws the prices it does have. An absent caption, not a zero."""
    entries = panel(_row(market_implied_home_win_probability=None,
                         market_implied_away_win_probability=None))
    caption = " ".join(_captions(entries))
    assert "Implied home win probability" not in caption
    assert _metric(entries, "Spread (home)") == "-1.5", "the rest of the panel stopped drawing"


# --- absence, and the difference between kinds of it -----------------------------------------

def test_a_game_the_books_never_priced_renders_empty_and_draws_no_prices(panel):
    """Most of 110,634 games predate betting data entirely.

    That is an absence of market, not a failure to fetch one, and the panel must not put a
    grid of em dashes where four prices go. ⚠️ THE SECOND ASSERTION IS THE ONE THAT MATTERS:
    B076's lesson is that an Empty state rendering ABOVE a grid that also drew looks exactly
    like this test passing.
    """
    entries = panel(_row(spread=None, over_under=None))
    body = _text(entries)
    assert "would be here" in body, "the Empty state did not render"
    assert "2013 onward" in body, "the Empty state did not say what cfdb actually holds"
    assert not [b for k, b in entries if k == "metric"], \
        "an Empty market still drew price metrics"


def test_one_price_present_is_not_an_empty_market(panel):
    """A total with no spread is a priced game. The Empty branch requires BOTH to be absent,
    and a panel that gave up on either alone would hide a real price."""
    entries = panel(_row(spread=None))
    assert _metric(entries, "Total") == "51.0"
    assert _metric(entries, "Spread (home)") == "—", "a null spread was not an em dash"


def test_a_null_price_and_a_zero_price_are_different_statements(panel):
    """AC-G.32, on the one number where the confusion is most expensive.

    A spread of exactly 0 is a pick'em — a real price, quoted by a real book. A null spread
    is the absence of one. Rendering either as the other is a lie about a measurement.
    """
    assert _metric(panel(_row(spread=0.0)), "Spread (home)") == "0.0"
    assert _metric(panel(_row(spread=None)), "Spread (home)") == "—"


def test_a_null_moneyline_is_an_em_dash_not_a_zero(panel):
    """The same rule on the pair that carries no decimal, so `dp=0` cannot disguise it."""
    assert _metric(panel(_row(home_moneyline=None)), "Home moneyline") == "—"
    assert _metric(panel(_row(home_moneyline=0)), "Home moneyline") == "0"


# --- the shared caveat -----------------------------------------------------------------------

def test_the_spread_sign_note_is_the_SHARED_one(panel):
    """R-009. Three pages explain this sign; one component owns the sentence.

    ⚠️ THE ASSERTION COMPARES AGAINST `chips.SPREAD_SIGN_NOTE` RATHER THAN A COPY OF ITS
    WORDS. A page that stopped calling the component and inlined its own sentence would pass
    a test that hardcoded the text, and the drift this component exists to prevent would be
    invisible to the thing meant to be watching for it.
    """
    from lib import chips
    caption = " ".join(_captions(panel(_row())))
    assert _plain(chips.SPREAD_SIGN_NOTE) in caption, \
        "the panel is not rendering the shared spread-sign note"
