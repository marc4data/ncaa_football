"""R-645 / R-653 — Matchup and the Excel export must answer with the SAME number.

🚨 MARC FOUND THIS HIMSELF, ON A BETTING PAGE: *"Matchup is showing the line has shifted up 7.
Export to excel shows +6.5."* Both were true of their own book and neither said which book.

    surface          column                          book          401856679
    Matchup          line_spread_move_from_open      DraftKings    7.0
    Excel export     spread_move_from_open           Bovada        6.5

⚠️ AND THE MATCHUP ROW DID NOT EVEN RECONCILE WITH ITSELF: it drew Bovada's price of 5 beside
DraftKings' move of 7.0, when 5 − (−1.5) is 6.5.

Measured 2026-09-11 across `srv_game`: the two families disagree on **1,107 of the 1,332**
games carrying both, and name a **different book on 1,739 of 1,886**. This was not one odd game.

🚨 R-653 IS THE GENERAL FORM AND THIS FILE IS ITS FIRST INSTANCE: nothing in this project
compared a rendered value across two surfaces, which is how the site published two different
kickoff times for one game all season (R-643). ⚠️ This is one assertion about one pair of
numbers, deliberately — not a framework.
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "site"))

import render_harness as H                                      # noqa: E402
from lib import workbook                                        # noqa: E402

# 🚨 THE TWO FAMILIES ARE MADE TO DISAGREE, AND THAT IS THE WHOLE FIXTURE. B087's `_degenerate`
# break went green because a different guard refused the chart first and the test was satisfied
# by the wrong thing; a row where both families carry 6.5 would pass whichever column the card
# read. These are Marc's own numbers from 401856679.
SPREAD_UNPREFIXED, SPREAD_LINE_FAMILY = 6.5, 7.0
TOTAL_UNPREFIXED, TOTAL_LINE_FAMILY = -2.0, -3.0

ROW = {
    "spread": 5.0, "spread_open": -1.5, "over_under": 43.5, "over_under_open": 45.5,
    "spread_move_from_open": SPREAD_UNPREFIXED, "total_move_from_open": TOTAL_UNPREFIXED,
    "line_spread_move_from_open": SPREAD_LINE_FAMILY,
    "line_total_move_from_open": TOTAL_LINE_FAMILY,
    "provider_key": "bovada", "line_movement_provider_key": "draftkings",
    "line_snapshot_count": 23, "line_snapshot_ts": pd.Timestamp("2026-09-11 12:00:17+00:00"),
    "line_movement_spans_snapshot_gap": False,
    "spread_favorite_side": "away", "moneyline_favorite_side": "away",
    "favorite_definitions_disagree": False,
    "home_team": "Michigan", "away_team": "Oklahoma",
    "home_abbreviation": "MICH", "away_abbreviation": "OU",
    "home_moneyline": 175, "away_moneyline": -210,
    # ⚠️ R-605's BOARD READS PER-SIDE COLUMNS AND A GAME ID. Without these the card raised into
    # states.section and this file asserted against an Error state — which is exactly the
    # B076 shape, a defect that renders as a handled failure.
    "game_id": 401856679, "home_team_id": 130, "away_team_id": 201,
    "market_implied_home_points": 19.5, "market_implied_away_points": 24.0,
    "market_implied_home_win_probability": 0.3493,
    "market_implied_away_win_probability": 0.6507,
}

# Oklahoma away at -4.5, Michigan home at +4.5 — the mirror, from srv_game_team.
_GAME_TEAM = {201: {"team_id": 201, "spread_final": -4.5},
              130: {"team_id": 130, "spread_final": 4.5}}


def _rendered_card():
    with H.streamlit_stubbed() as (_st, captured, _charts):
        import importlib
        matchup = importlib.reload(importlib.import_module("views.matchup"))
        matchup._game_team_rows = lambda _g: {k: pd.Series(v)
                                              for k, v in _GAME_TEAM.items()}
        matchup._market_card(dict(ROW))
    # ⚠️ R-605 RENAMED THE COLUMNS: "Spread"/"Over/Under" became "Point Spread"/"Total" on the
    # board's header. The block is still the one carrying both, which is what this looks for.
    card = [block for block in captured
            if "Point Spread" in block and "Total" in block]
    assert card, f"the market card did not render; captured {len(captured)} blocks"
    return H.plain(card[0])


def _exported(label):
    """The value the Excel export puts under `label`, taken from the sheet's own declaration."""
    for sheet in workbook.SHEETS:
        for field, header in sheet.columns:
            if header == label:
                return field, ROW.get(field)
    raise AssertionError(f"no Excel column headed {label!r}")


# ⚠️ R-605 MOVED THE LABELS INTO A HEADER ROW, so "the arrow after the word Spread" now finds
# the header and then the FIRST arrow on the board, whichever cell it belongs to. The anchor is
# the value the chip sits under instead — the away row's own spread and its own O-side total —
# which is what "beside its number" always meant.
@pytest.mark.parametrize("card_label,anchor,excel_label,line_family_value", [
    ("Spread", r"-4\.5", "Δ Spread", SPREAD_LINE_FAMILY),
    ("Over/Under", r"O 43\.5", "Δ O/U", TOTAL_LINE_FAMILY),
])
def test_the_two_surfaces_report_the_same_move(card_label, anchor, excel_label,
                                               line_family_value):
    """🚨 THE ASSERTION IS THAT THEY AGREE — not that each reads its own column.

    A test that checked "Matchup reads X" and "Excel reads Y" would have passed happily
    throughout the defect. This renders one row through the real card and reads the same row
    through the export's own column declaration, then compares the numbers.
    """
    plain = _rendered_card()
    field, exported = _exported(excel_label)

    # The chip is a glyph and an UNSIGNED amount, so compare magnitudes against the export.
    match = re.search(rf"{anchor}\s*[▲▼]\s*([0-9.]+)", plain)
    assert match, (
        f"no movement chip rendered beside {card_label!r}; the card drew: {plain[:200]}")
    shown = float(match.group(1))

    assert shown == abs(float(exported)), (
        f"THE TWO SURFACES DISAGREE ABOUT ONE FACT. Matchup's {card_label} chip shows "
        f"{shown} and the Excel export's {excel_label!r} column ({field}) holds {exported}. "
        f"That is R-645: Marc saw 7 on the page and 6.5 in the workbook for game 401856679, "
        f"because the card read the one-book `line_` family while the export read the "
        f"unprefixed one. The other family's value here is {line_family_value}.")


def test_the_card_names_the_book_its_number_came_from():
    """⚠️ PROVENANCE, §4.3's rule applied to the reader.

    The card's numbers are `provider_key`'s — Bovada on this row — so Bovada is the book the
    caption must name. It used to prefer `line_movement_provider_key` whatever it displayed,
    which named DraftKings beside a Bovada price on 92% of the games carrying both.

    🚨 IT GOES THROUGH `_rendered_card()` RATHER THAN BUILDING ITS OWN. This test had a second,
    near-identical render that forgot to stub `_game_team_rows` — so once R-605 made the board
    read `srv_game_team`, it opened a REAL DATABASE CONNECTION. It passed on a laptop with a
    tunnel up and failed in CI, which is the one place that could see it.

    ⚠️ conftest.py exists to keep this suite offline and free; two copies of a render helper is
    how a test slips past it.
    """
    blob = _rendered_card()
    assert "Bovada" in blob, (
        f"the card does not name the book its numbers came from. Captured: {blob[:300]}")
