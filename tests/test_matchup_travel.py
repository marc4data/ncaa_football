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
import re
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
            seen["html"] = render_harness.body_html(captured)
            return render_harness.plain(" ".join(str(t) for t in captured)), seen
    return run


def _matchup():
    import importlib
    return importlib.import_module("views.matchup")


def _cells(seen) -> list:
    """The table's DATA cells, as text — never the caption, the note or the heading.

    🚨 **THIS HELPER EXISTS BECAUSE v17's CAPTION BROKE SIX ASSERTIONS AT ONCE, AND THEY WERE
    RIGHT TO BREAK.** cfdb-wta-R-2912 gave the panel a sentence explaining that *an em dash
    means cfdb publishes no coordinates … which is a different fact from `home venue`* — so
    the strings `—` and `home venue` are now in the panel's PROSE whatever any cell says.
    **Every test below that searched the whole blob had silently stopped being able to fail**
    (R-2260: a substring is not a rule; B152's caption guard learned the same lesson one file
    over, twice in one round).

    ✅ **THE RULE THE PANEL ACTUALLY HAS IS ABOUT CELLS** — R-634: a null renders as an em dash
    and a zero does not — so the instrument reads cells.
    """
    body = re.search(r"<tbody>(.*?)</tbody>", seen["html"], re.S)
    assert body, f"the travel panel drew no table body: {seen['html'][:400]}"
    return [re.sub("<[^>]+>", "", c).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", body.group(1), re.S)]


def _rows(seen) -> int:
    body = re.search(r"<tbody>(.*?)</tbody>", seen["html"], re.S)
    return len(re.findall(r"<tr", body.group(1))) if body else 0


def _headings(seen) -> list:
    head = re.search(r"<thead>(.*?)</thead>", seen["html"], re.S)
    assert head, "the travel table draws no header row"
    return [re.sub("<[^>]+>", "", c).strip()
            for c in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1), re.S)]


# --- 🚨 R-634: the UNIT, not the column name --------------------------------------------------

def test_the_rendered_distance_is_in_MILES(travel):
    """🚨 IT ASSERTS THE RENDERED STRING, NOT WHICH COLUMN WAS READ, AND THAT IS DELIBERATE.

    "the panel reads `travel_miles`" would pass the day a model shipped miles under the old
    name, and it would also pass if the panel read the right column and printed "km" beside it.
    Marc's request was about what he SEES: "all distance measurements in miles."

    ⚠️ The fixture's two columns disagree — 8,463.6 against 5,259.0 — so only one of them can
    produce this string.
    """
    body, seen = travel([_side()])
    # ⚠️ **NO DECIMAL SINCE v17 — Marc: *"Don't need a decimal point on the distance."***
    # 📊 The published figure is unchanged at 5,259.0; **rounding for DISPLAY is rendering,
    # and nothing here recomputes or converts** (§4.2.1).
    assert "5,259 mi" in _cells(seen), f"the distance is not the miles figure: {_cells(seen)}"
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
    _body, seen = travel([HOME_SIDE])
    cells = _cells(seen)
    assert "home venue" in cells, f"a home side did not render its zero: {cells}"
    assert "\u2014" not in cells, f"a home side rendered as absent: {cells}"


def test_a_NULL_distance_is_an_em_dash_and_not_a_zero(travel):
    """The other half, and the common one: 76.6% of upcoming games have neither side's
    distance. An absent measurement must never read as "they travelled nowhere"."""
    _body, seen = travel([_side(travel_miles=None, elevation_change_ft=None)])
    cells = _cells(seen)
    assert "\u2014" in cells, f"a null distance did not render as absent: {cells}"
    assert "home venue" not in cells, "a null distance was rendered as a home game"
    assert not any("mi" in c for c in cells), f"a null distance invented a number: {cells}"


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
    _z, zero = travel([_side(travel_miles=0.0)])
    _n, null = travel([_side(travel_miles=None)])
    assert _cells(zero) != _cells(null), "zero and null rendered identically (AC-G.32)"
    assert "home venue" in _cells(zero) and "home venue" not in _cells(null)


# --- the panel must not have grown -------------------------------------------------------------

def test_the_panel_still_emits_ONE_line_per_side(travel):
    """⚠️ R-600. Marc: "Too big, not that important." B085 turned two headings and six
    st.metric tiles into two lines, and this round changes UNITS, not size.

    One `st.markdown` per side, plus the subheader and the as-of caption — the same shape
    B085 left. A panel that grew back would pass every unit assertion above.
    """
    _body, seen = travel([_side(), HOME_SIDE])
    # ⚠️ **ONE ROW PER SIDE SINCE v17, WHICH IS THE SAME CLAIM IN THE NEW SHAPE.** R-600's
    # rule was *one line per side, not a heading and three tiles*; the table keeps it — one
    # header row and two data rows, which is shorter than the two prose lines it replaced
    # because those wrapped at 1024.
    assert _rows(seen) == 2, (
        f"the travel panel draws {_rows(seen)} rows for two sides, not 2 — it has grown back "
        f"from the one-per-side shape B085 left")


def test_both_sides_are_rendered_and_named(travel):
    _body, seen = travel([_side(), HOME_SIDE])
    cells = _cells(seen)
    assert "Arizona State" in cells and "Towson" in cells
    assert "5,259 mi" in cells and "home venue" in cells


# --- 🚨 v17 (cfdb-wta-R-2912): labelled, aligned, and the elevation says what it is ----------

def test_EVERY_MEASURE_HAS_A_HEADING_that_names_it(travel):
    """> **MARC, v17:** *"Can you make it more tabular with headings and so that the data
    > points are labeled and aligned."*

    🚨 **THE LINE THIS REPLACED WAS POSITIONAL.** It read `Towson  Home · home venue · 7d rest
    · +0 ft`, so every figure depended on the reader knowing the order they came in — and the
    one he could not decode was the last. **A heading per measure is the whole fix.**

    ⚠️ **THE PAIRS ARE PINNED, NOT THE COUNT** (B149's R-744): swapping the field under a
    heading keeps five columns and would come back green against a count.
    """
    _body, seen = travel([_side()])
    assert _headings(seen) == ["Team", "Side", "Traveled", "Elevation change", "Rest, days"], (
        f"the travel table's headings moved: {_headings(seen)}")
    cols = _matchup()._travel_columns()
    assert [(c.label, c.field) for c in cols] == [
        ("Team", "team"), ("Side", "is_home"), ("Traveled", "travel_miles"),
        ("Elevation change", "elevation_change_ft"), ("Rest, days", "rest_days"),
    ], "a heading and the field under it no longer agree"


def test_THE_ELEVATION_SAYS_WHAT_IT_IS_A_CHANGE_FROM(travel):
    """> **MARC, v17:** *"Without the header, not sure end-users understand the elevation
    > difference listed in ft."*

    🚨 **A HEADING ALONE DOES NOT ANSWER HIM AND NEITHER DOES A HOVER.** *Elevation change*
    says it is a change; it does not say **from what**, and a `title` is invisible to a reader
    who does not know there is anything to hover. ✅ **So the sentence is in the caption, where
    it is read without being sought** — and the sign is the fact it explains: negative means
    they came down.
    """
    body, seen = travel([_side()])
    caption = re.search(r"<caption[^>]*>(.*?)</caption>", seen["html"], re.S)
    assert caption, f"the travel table draws no caption: {seen['html'][:300]}"
    text = re.sub("<[^>]+>", "", caption.group(1))
    assert "home elevation" in text and "game venue" in text, (
        f"the caption no longer says what the elevation is a change FROM: {text!r}")
    assert "negative" in text.lower() or "came down" in text.lower(), (
        f"the caption no longer says which way the sign runs: {text!r}")
    assert "-1,027 ft" in _cells(seen), f"the signed figure left the cell: {_cells(seen)}"
    assert "1,027 ft" in body and "+1,027" not in body, "the descent lost its sign"


def test_THE_DISTANCE_CARRIES_NO_DECIMAL_POINT(travel):
    """> **MARC, v17:** *"Don't need a decimal point on the distance."*

    ⚠️ **ROUNDING FOR DISPLAY IS RENDERING; CONVERTING OR DERIVING IS NOT** (§4.2.1). A097
    published `travel_miles` rounded from the same unrounded measurement as its metric twin,
    and this reads that column and prints fewer of its digits — **nothing is recomputed.**
    """
    _body, seen = travel([_side(), HOME_SIDE])
    distances = [c for c in _cells(seen) if "mi" in c]
    assert distances == ["5,259 mi"], f"the distance cells are {distances}"
    assert not any("." in c for c in distances), (
        f"a distance still carries a decimal point: {distances}")


def test_THE_TABLE_READS_AWAY_THEN_HOME_like_every_other_section(travel):
    """⚠️ **THE `order by` FLIPPED IN v17 AND THAT IS THE WHOLE CHANGE** — `is_home asc`
    rather than `desc`. B148 made the two sides symmetric away-then-home, and PART 1 and
    PART 2 of this round both stack and sit in that order; this panel was the last one
    reading home-first. **Same columns, same row count, no second read.**
    """
    _body, seen = travel([_side(), HOME_SIDE])
    assert "order by is_home asc" in seen["sql"], (
        f"the travel query no longer orders away first: {seen['sql']}")


def test_AN_ABSENT_FIGURE_IS_NAMED_rather_than_left_as_a_bare_dash(travel):
    """🚨 **THE EMPTY TABLE IS THE COMMON CASE — 1,218 of 1,590 upcoming 2026 games have
    NEITHER side's distance (76.6%).** So a table of unexplained em dashes is what three
    readers in four would see, and it would be worse than the prose it replaced.

    ⚠️ **AC-G.11: the note says WHICH absence it is**, and keeps it apart from the zero that
    is a measurement.
    """
    _body, seen = travel([_side(travel_miles=None, elevation_change_ft=None),
                          _side(team="Towson", travel_miles=None,
                                elevation_change_ft=None)])
    assert _cells(seen).count("—") == 4, (
        f"two sides with no distance and no elevation drew "
        f"{_cells(seen).count(chr(8212))} em dashes, not 4: {_cells(seen)}")
    note = " ".join(str(t) for t in seen["raw"])
    assert "no coordinates" in note, (
        "nothing on the panel says what an em dash means, and it is the state most readers "
        "will see")
    assert "home venue" in note, (
        "the note no longer separates the absence from the measured zero (R-634)")
