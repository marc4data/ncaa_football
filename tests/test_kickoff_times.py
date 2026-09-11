"""R-643 — the test that should have existed, and one known game is the whole of it.

🚨 EVERY KICKOFF ON THIS SITE WAS FOUR HOURS EARLY FOR A SEASON AND 1,080 TESTS WERE GREEN.
Nothing asserted a wall-clock string against a real game, so the double conversion was
invisible: `srv_game` published `start_date_et` — Eastern wall-clock with the offset thrown
away by `AT TIME ZONE` — and `fmt._local` treated that naive value as UTC and converted it
again.

⚠️ AND THE FIXTURES SHARED THE ASSUMPTION, WHICH IS WHY NOTHING CAUGHT IT. Every
`start_date_et` fixture in `tests/` was naive, except `test_matchup_tabs.py`'s, which was
tz-aware — the suite did not agree with itself about what the column was, and both spellings
passed.

**The source of truth is written down here, in words, so this test can be checked by a human
against a schedule rather than against the code that produced it:**

    Game 401856679 — Oklahoma at Michigan, Saturday 12 September 2026.
    Kickoff: 12:00 PM Eastern  =  9:00 AM Pacific  =  16:00 UTC.

Marc, 2026-09-11: *"On the schedule both games are showing kickoff at 5AM PDT, when real
kick-off is 9AM PDT."*
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from lib import fmt                                                      # noqa: E402

# The instant `srv_game.start_date` holds for game 401856679, verified against published
# serving on 2026-09-11. ⚠️ A tz-AWARE value, because that is what serving publishes and what
# the page receives — see the module docstring for why the naive spelling was the defect.
KICKOFF_401856679 = pd.Timestamp("2026-09-12 16:00:00", tz="UTC")

# What the same moment looks like once dbt has thrown the offset away. This is NOT a value the
# warehouse can produce any more; it is kept so the regression has something to be tested with.
KICKOFF_AS_NAIVE_EASTERN = pd.Timestamp("2026-09-12 12:00:00")


def test_the_known_kickoff_renders_as_nine_in_the_morning_pacific():
    """🚨 THE ROUND. 12:00 PM Eastern is 9:00 AM Pacific, and the site must say so."""
    assert fmt.clock(KICKOFF_401856679) == "9:00 AM PDT"
    assert fmt.local_time(KICKOFF_401856679) == "Sep 12, 2026, 9:00 AM PDT"


def test_the_double_conversion_cannot_come_back_quietly():
    """Re-introducing it must FAIL, not render 5:00 AM.

    ⚠️ THE OLD BEHAVIOUR IS THE THING BEING FORBIDDEN: a naive Eastern wall clock used to be
    assumed UTC and converted again, landing on 5:00 AM PDT — four hours early, and looking
    exactly like a real time. The offset is the error: four hours under EDT, five under EST.
    """
    # ⚠️ THE FAILURE MESSAGE NAMES THE HOUR, because "DID NOT RAISE" would send the next
    # reader to look up what the right answer was. A guard is worth what its message says.
    try:
        rendered = fmt.clock(KICKOFF_AS_NAIVE_EASTERN)
    except fmt.NaiveTimestamp:
        return
    pytest.fail(
        f"a naive Eastern kickoff rendered as {rendered!r} instead of being refused. "
        f"Game 401856679 kicks off at 9:00 AM PDT; the double conversion renders it "
        f"5:00 AM PDT — four hours early under EDT and five under EST, on every game, "
        f"every page, all season. That is R-643 coming back.")


def test_a_naive_timestamp_is_refused_rather_than_guessed():
    """R-571's ninth instance: the tolerance that was added for test fixtures.

    ⚠️ It is refused for EVERY formatter that converts, not just the kickoff one, because the
    guess was in `_local` and every caller inherited it.
    """
    naive = pd.Timestamp("2026-09-12 12:00:00")
    for render in (fmt.clock, fmt.local_time, fmt.as_of):
        with pytest.raises(fmt.NaiveTimestamp):
            render(naive)


def test_an_absent_kickoff_is_still_an_absence_and_not_an_error():
    """⚠️ THE RAISE MUST NOT SWALLOW THE EMPTY CASE. AC-G.32: a missing value renders as the
    em-dash, and that is a different fact from 'someone passed the wrong type'."""
    for missing in (None, pd.NaT):
        assert fmt.clock(missing) == fmt.EM_DASH
        assert fmt.local_time(missing) == fmt.EM_DASH


def test_a_bare_date_is_never_converted():
    """`day()` handles a date before `_local` sees it, and that path must stay open.

    Converting midnight shifts a game back a calendar day — the defect that once cost this
    project 66,496 games, which is why `day()` checks for a normalized naive value first.
    """
    assert fmt.day(pd.Timestamp("2026-09-12")) == "Sep 12, 2026"


def test_the_time_and_its_zone_label_move_together(monkeypatch):
    """AC-G.34. `fmt.py`'s own header calls the abbreviation load-bearing; prove it travels.

    🚨 '7:30 PM' is not unambiguous and '7:30 PM PDT' is — so a configured zone change must
    move BOTH the number and the label, or the site states a time in a zone it no longer uses.
    """
    assert fmt.clock(KICKOFF_401856679) == "9:00 AM PDT"

    monkeypatch.setattr(fmt, "display_timezone", lambda: "America/New_York")
    assert fmt.clock(KICKOFF_401856679) == "12:00 PM EDT"

    monkeypatch.setattr(fmt, "display_timezone", lambda: "UTC")
    assert fmt.clock(KICKOFF_401856679) == "4:00 PM UTC"
