"""The Matchup line-movement panel: how far the line travelled (R-459).

WHAT THIS EXISTS TO CATCH. `states.section` turns any exception inside the panel into the
Error state — plain language, no traceback, exactly as designed — so a panel that has
stopped drawing looks like a handled failure rather than a defect. That is the failure mode
`ci/check_page_queries.py` was written after: Scores asked srv_game for eight columns it did
not have and raised on every load, with nobody noticing.

That check executes the page's query, so a renamed or dropped column is already covered.
What it cannot see is whether the panel still DRAWS, and whether it draws the two caveats
that make these numbers honest. That is what these assertions are for.

THE TWO ASSERTIONS THAT MATTER MOST are the caveats, because the panel is at its most
dangerous when it looks healthiest:

  1. THE BOOK IS NAMED. Every measure is one book's by construction. A movement figure that
     does not say whose price it came from is the provenance defect the `market_implied_`
     prefix rule exists to prevent, and it renders perfectly while being wrong.

  2. A SPANNED SNAPSHOT GAP SAYS SO. Three days in 2026 hold no snapshots at all. A window
     spanning them makes the excursion a FLOOR, not a measurement, and a floor presented as
     a measurement is exactly the caveat that must travel with the row.

A single-snapshot game gets the same treatment for a different reason: 1,577 of 1,854 rows
carry one snapshot, and on those the excursion equals the net move by construction rather
than by measurement.
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

    def cache(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda fn: fn

    stub.cache_data = stub.cache_resource = cache
    stub.session_state = {}
    return stub, captured


# The modules that hold their own `import streamlit`. Reloading the view alone leaves
# lib.states emitting into the REAL streamlit, so the Empty state renders somewhere the
# capture cannot see it.
_RELOAD = ("lib.states", "lib.table", "lib.identity", "views.matchup")


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
        matchup._line_movement(pd.Series(row))
        return list(captured)

    yield run

    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    _reload_all()


def _row(**overrides):
    """One srv_game row's worth of movement columns. A game with a real history by default."""
    row = {
        "line_movement_provider_key": "draftkings",
        "line_snapshot_count": 94,
        "line_movement_spans_snapshot_gap": False,
        "line_spread_move_from_open": -3.0,
        "line_spread_largest_excursion": -4.5,
        "line_total_move_from_open": 1.5,
        "line_total_largest_excursion": 2.5,
        "line_market_implied_win_probability_move_from_open": 1.10,
        "line_market_implied_win_probability_largest_excursion": 4.57,
    }
    row.update(overrides)
    return row


def _text(entries):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)) for _, body in entries)


# --- it draws ------------------------------------------------------------------------------

def test_both_measures_are_drawn_for_every_market(panel):
    """The regression this file is named for: the panel silently stopping.

    Six figures, because there are two measurements of three markets. A panel that drew only
    the net moves would look complete and would have lost the entire point of the mart.
    """
    entries = panel(_row())
    metrics = [b for kind, b in entries if kind == "metric"]
    assert len(metrics) == 6, f"expected six figures, drew {len(metrics)}"
    body = _text(entries)
    for figure in ("-3.0", "-4.5", "+1.5", "+2.5", "+1.10", "+4.57"):
        assert figure in body, f"{figure} is missing from the panel"


def test_the_net_move_and_the_excursion_are_both_present_and_distinct(panel):
    """The mart's whole justification, restated at the page.

    A round trip — out and back — reads as no move at all and a real excursion. If the panel
    ever drew one number per market, this game would render as though nothing happened.
    """
    body = _text(panel(_row(line_spread_move_from_open=0.0,
                            line_spread_largest_excursion=-3.0)))
    assert "-3.0" in body, "the excursion vanished, and with it the round trip"
    assert "Widest spread excursion" in body


# --- the caveats, which are the point ------------------------------------------------------

def test_the_book_is_named_on_the_panel(panel):
    """Provenance. A move measured against a different book's price is not a move."""
    body = _text(panel(_row()))
    assert "draftkings" in body, "the panel does not say whose price these moves came from"


def test_a_window_spanning_the_snapshot_gap_says_the_excursion_is_a_floor(panel):
    """The caveat that has to travel with the row.

    Three days in 2026 hold no snapshots. A window spanning them was not observed throughout,
    so the excursion is a floor — the line may have gone further while nobody was looking.
    """
    body = _text(panel(_row(line_movement_spans_snapshot_gap=True)))
    assert "floor" in body.lower(), "a spanned gap rendered as though it were a measurement"
    assert "no snapshots" in body.lower()


def test_a_clean_window_does_not_cry_wolf(panel):
    """The other half of the caveat, and the reason the flag is `spans` not `predates`.

    Asking only whether the line opened before the gap flags 1,728 games where 98 is correct.
    A caveat that fires on 93% of rows indicates nothing.
    """
    body = _text(panel(_row(line_movement_spans_snapshot_gap=False)))
    assert "floor" not in body.lower(), "the gap caveat fired on a game that never spanned it"


def test_a_single_snapshot_says_the_excursion_is_the_net_move_restated(panel):
    """1,577 of 1,854 rows. Six numbers of which three are echoes, unless the panel says so."""
    body = _text(panel(_row(line_snapshot_count=1,
                            line_spread_move_from_open=-3.0,
                            line_spread_largest_excursion=-3.0)))
    assert "observed once" in body.lower()
    assert "1 snapshot" in body, "the snapshot count should read singular"


# --- the states --------------------------------------------------------------------------

def test_a_game_with_no_snapshots_is_empty_not_a_row_of_dashes(panel):
    """EMPTY, NOT DEGRADED. No history is an absence of market, not a fault in tracking it."""
    entries = panel(_row(line_snapshot_count=None))
    assert not [b for kind, b in entries if kind == "metric"], \
        "a game with no snapshots drew figures anyway"
    body = _text(entries)
    assert "would be here" in body, "the Empty state did not render"
    assert "no opening price" in body.lower() or "no line snapshots" in body.lower()


def test_a_broken_row_degrades_this_panel_and_not_the_page(panel):
    """states.section is the blast wall. The panel must not take Matchup down with it."""
    entries = panel(_row(line_snapshot_count="not a number"))
    body = _text(entries)
    assert "Something went wrong" in body or "srv_game" in body, \
        "the panel raised out of its own section instead of degrading"


def test_no_threshold_is_applied(panel):
    """Marc sets what counts as a big move. The panel shows numbers and ranks nothing."""
    body = _text(panel(_row(line_spread_move_from_open=-14.0,
                            line_spread_largest_excursion=-28.5))).lower()
    for verdict in ("big move", "significant", "sharp", "steam"):
        assert verdict not in body, f"the panel editorialised: {verdict!r}"
