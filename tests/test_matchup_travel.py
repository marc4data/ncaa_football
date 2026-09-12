"""The Matchup travel panel: miles and feet (R-634), and the states AC-G.32 separates.

🚨 THIS PANEL HAD NO TESTS AT ALL UNTIL B089, which is why its units could drift for four
rounds without anything noticing. B085 raised that it rendered kilometres, correctly refused to
convert in the page — a multiplication is metric maths and §4.2 puts it in dbt — and A097
shipped the imperial columns. ⚠️ The panel went on rendering km and m for four more rounds, and
no test could have said so.

⚠️ EVERY FIXTURE CARRIES BOTH UNITS WITH DIFFERENT NUMBERS, ON PURPOSE. A row whose
`travel_km` and `travel_miles` are the same number passes whichever column the panel reads, and
"check your fixture can distinguish what it claims to test" is a lesson this panel's neighbours
have now paid for five times. The pair below is REAL — Arizona State to Wembley Stadium, a 2026
neutral-site game, read from live serving on 2026-09-11:

    travel_km 8463.6   travel_miles 5259.0
    elevation_change_m -313.2   elevation_change_ft -1027

🚨 AND -1027 IS NOT THE CONVERSION OF -313.2. Converting the rounded metre figure gives -1028.
Both columns are rounded from the same unrounded measurement, which is what stops them
disagreeing, and it is also why a fixture must not compute one from the other.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_harness  # noqa: E402


# Arizona State at Wembley, and Kansas the other side of the same game. Measured.
def _side(**overrides):
    side = {
        "team": "Arizona State", "opponent": "Kansas",
        "is_home": False, "is_neutral_site": True,
        "game_venue": "Wembley Stadium",
        "travel_km": 8463.6, "travel_miles": 5259.0,
        "elevation_change_m": -313.2, "elevation_change_ft": -1027.0,
        "rest_days": 7, "rest_bucket": "normal week",
        "previous_game_date": pd.Timestamp("2026-08-30"),
        "as_of_ts": pd.Timestamp("2026-09-11T12:00:00Z"),
    }
    side.update(overrides)
    return side


HOME_SIDE = dict(
    team="Towson", opponent="Arizona State", is_home=True, is_neutral_site=False,
    game_venue="Johnny Unitas Stadium",
    travel_km=0.0, travel_miles=0.0,
    elevation_change_m=0.0, elevation_change_ft=0.0,
    rest_days=7, rest_bucket="normal week",
    previous_game_date=pd.Timestamp("2026-08-30"),
    as_of_ts=pd.Timestamp("2026-09-11T12:00:00Z"),
)


@pytest.fixture
def travel():
    """Call the real `_travel`, with the query replaced and streamlit captured."""
    def run(sides):
        with render_harness.streamlit_stubbed() as (_st, captured, _charts):
            # ⚠️ IMPORTED INSIDE THE STUB, NOT BEFORE IT. `views.*` is not in the harness's
            # RELOAD list — it reloads `lib.*` only — so the view has to be brought in while
            # the stub is installed or it binds to the real streamlit and the capture is
            # empty. Dropping it first makes the copy a fresh object the harness's own
            # `st is stub` teardown then puts back.
            sys.modules.pop("views.matchup", None)
            import importlib
            matchup = importlib.import_module("views.matchup")
            seen = {}

            def fake_query(sql, params=None):
                seen["sql"] = sql
                return pd.DataFrame(sides)

            matchup.query = fake_query
            matchup._travel(401856679)
            # 🚨 R-610. `streamlit_stubbed` deliberately does not enforce on exit — it is the
            # raw instrument and A's failure-state tests use it — so the panel-level fixtures
            # call the guard themselves. Strict by default; no opt-in here because a travel
            # panel has no legitimate reason to render an Error card.
            render_harness.assert_no_error_card(captured, "the travel panel")
            seen["raw"] = list(captured)
            return render_harness.plain(" ".join(str(t) for t in captured)), seen
    return run


# --- 🚨 R-634: the UNIT, not the column name --------------------------------------------------

def test_the_rendered_distance_is_in_MILES(travel):
    """🚨 IT ASSERTS THE RENDERED STRING, NOT WHICH COLUMN WAS READ, AND THAT IS DELIBERATE.

    "the panel reads `travel_miles`" would pass the day a model shipped miles under the old
    name, and it would also pass if the panel read the right column and printed "km" beside it.
    Marc's request was about what he SEES: "all distance measurements in miles."

    ⚠️ The fixture's two columns disagree — 8,463.6 against 5,259.0 — so only one of them can
    produce this string.
    """
    body, _ = travel([_side()])
    assert "5,259.0 mi" in body, f"the distance is not the miles figure: {body}"
    assert "8,463.6" not in body, "the kilometre figure reached the page"
    assert " km" not in body, f"the panel still names kilometres: {body}"


def test_the_rendered_elevation_is_in_FEET(travel):
    body, _ = travel([_side()])
    assert "-1,027 ft" in body, f"the elevation is not the feet figure: {body}"
    assert "-313" not in body, "the metre figure reached the page"


def test_the_panel_does_not_SELECT_the_metric_columns_any_more(travel):
    """⚠️ §3.3's MIGRATE step, asserted from the page's side.

    The metric columns stay in the model — dropping them is a published-column removal and
    session A's round after this one. What this round owes Cowork is proof the page no longer
    reads them, which is the thing that makes the drop safe.
    """
    _body, seen = travel([_side()])
    sql = seen["sql"]
    assert "travel_miles" in sql and "elevation_change_ft" in sql
    assert "travel_km" not in sql, "the page still selects travel_km"
    assert "elevation_change_m" not in sql, "the page still selects elevation_change_m"


# --- 🚨 the sign is the fact -------------------------------------------------------------------

def test_a_DESCENT_and_a_CLIMB_render_differently(travel):
    """🚨 abs() WOULD MAKE THESE TWO ROWS IDENTICAL AND BOTH WOULD LOOK RIGHT.

    Arizona State drop 1,027 ft going to Wembley; a side going to Laramie climbs. ⚠️ The two
    fixtures differ ONLY in the sign, so a magnitude cannot tell them apart and this test is
    the only thing that can.
    """
    down, _ = travel([_side(elevation_change_ft=-1027.0)])
    up, _ = travel([_side(elevation_change_ft=1027.0)])
    assert "-1,027 ft" in down
    assert "+1,027 ft" in up
    assert down != up, "a descent and a climb rendered identically"


def test_the_sign_is_always_shown_even_when_climbing(travel):
    """A bare "1,027 ft" reads as a magnitude. The leading + is what makes it a direction."""
    body, _ = travel([_side(elevation_change_ft=1027.0)])
    assert "+1,027 ft" in body, f"a climb lost its sign: {body}"


# --- 🚨 AC-G.32: zero and null are different facts ---------------------------------------------

def test_a_HOME_side_is_zero_and_NOT_an_em_dash(travel):
    """🚨 AC-G.32, AND THE ZERO IS REAL RATHER THAN ASSUMED. 367 of the 3,180 upcoming 2026
    sides carry `travel_miles` = 0.0 rather than null — a team playing at home travelled no
    distance, which is a measurement.

    ⚠️ THE PANEL RENDERS "home venue" FOR THAT ZERO, NOT "0.0 mi", and the distinction the rule
    cares about is that it is emphatically not the em dash a null produces. Saying what the
    zero MEANS is better copy than printing it; confusing it with absence is the failure.
    """
    body, _ = travel([HOME_SIDE])
    assert "home venue" in body, f"a home side did not render its zero: {body}"
    assert "—" not in body, f"a home side rendered as absent: {body}"


def test_a_NULL_distance_is_an_em_dash_and_not_a_zero(travel):
    """The other half, and the common one: 76.6% of upcoming games have neither side's
    distance. An absent measurement must never read as "they travelled nowhere"."""
    body, _ = travel([_side(travel_miles=None, elevation_change_ft=None)])
    assert "—" in body, f"a null distance did not render as absent: {body}"
    assert "home venue" not in body, "a null distance was rendered as a home game"
    assert "mi" not in body.split("Arizona State")[-1].split("·")[1], \
        f"a null distance invented a number: {body}"


def test_zero_and_null_never_render_the_same_string(travel):
    """The rule stated as one assertion, so neither branch can drift into the other.

    🚨 THE TWO ROWS DIFFER ONLY IN `travel_miles`, AND THE FIRST VERSION OF THIS TEST DID NOT.
    It compared HOME_SIDE against an Arizona State row, so the two bodies differed by TEAM NAME
    whatever the distance rendered as — and the staged break that folds zero into the null
    branch (`if not miles`) left it GREEN while
    `test_a_HOME_side_is_zero_and_NOT_an_em_dash` went red beside it.

    ⚠️ That is the sixth time on this page's tests that a fixture could not distinguish what it
    claimed to test. Same team, same everything, one field apart.
    """
    zero, _ = travel([_side(travel_miles=0.0)])
    null, _ = travel([_side(travel_miles=None)])
    assert zero != null, "zero and null rendered identically (AC-G.32)"
    assert "home venue" in zero and "home venue" not in null


# --- the panel must not have grown -------------------------------------------------------------

def test_the_panel_still_emits_ONE_line_per_side(travel):
    """⚠️ R-600. Marc: "Too big, not that important." B085 turned two headings and six
    st.metric tiles into two lines, and this round changes UNITS, not size.

    One `st.markdown` per side, plus the subheader and the as-of caption — the same shape
    B085 left. A panel that grew back would pass every unit assertion above.
    """
    _body, seen = travel([_side(), HOME_SIDE])
    # The panel's own per-side wrapper. Counting THAT rather than "how many strings were
    # captured" is what makes this a statement about the panel's shape instead of about the
    # harness's bookkeeping.
    lines = [t for t in seen["raw"] if "padding:.1rem 0" in str(t)]
    assert len(lines) == 2, (
        f"the travel panel emits {len(lines)} side lines for two sides, not 2 — it has grown "
        f"back from the one-line-per-side shape B085 left")


def test_both_sides_are_rendered_and_named(travel):
    body, _ = travel([_side(), HOME_SIDE])
    assert "Arizona State" in body and "Towson" in body
    assert "5,259.0 mi" in body and "home venue" in body
