"""Part 0 as executable checks.

The four states are most of what the requirements are about, and "it renders" is not a
test. These assert the properties the document actually specifies: that the states are
distinguishable, that a violation of the query contract raises rather than returning a
wrong answer, and that null and zero never look alike.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from lib import chips, fmt                       # noqa: E402
from lib.query import QueryContractError, check_contract   # noqa: E402
from lib.registry import BY_KEY, GROUPS, PAGES   # noqa: E402


# --- the query contract, enforced in code rather than in review -------------------------

def test_a_valid_query_passes_and_reports_its_relation():
    assert check_contract("select a from srv_schedule where season=1 limit 10") == "srv_schedule"


@pytest.mark.parametrize("sql,reason", [
    ("select * from marts.dim_team limit 1", "reads marts, not serving"),
    ("select a from srv_x join srv_y on 1=1 limit 1", "explicit join"),
    ("select a from srv_x, srv_y limit 1", "comma join, which the keyword check misses"),
    ("select a from srv_x", "no explicit LIMIT"),
    ("delete from srv_x limit 1", "a write"),
])
def test_contract_violations_raise(sql, reason):
    with pytest.raises(QueryContractError):
        check_contract(sql)


# --- Empty vs Degraded: the distinction the whole module exists for ----------------------

def test_empty_and_degraded_produce_different_output():
    """AC-G.5. If these two ever render alike the site is lying about whose fault it is."""
    from lib import states
    import streamlit as st
    captured = []
    st.markdown = lambda body, **kw: captured.append(body)     # type: ignore
    states.empty("Games would be here.", "No games match your filters.")
    states.degraded("fct_poll_rank", "The rankings table has not been built.")
    assert len(captured) == 2
    assert captured[0] != captured[1]
    assert "cfdb-empty" in captured[0] and "cfdb-degraded" in captured[1]
    # AC-G.7: the blocker is named, in code font, in the UI.
    assert "<code>fct_poll_rank</code>" in captured[1]


def test_error_state_never_leaks_internals():
    """AC-G.9: no traceback, host, connection string or credential reaches the screen."""
    from lib import states
    import streamlit as st
    captured = []
    st.markdown = lambda body, **kw: captured.append(body)     # type: ignore
    st.button = lambda *a, **kw: False                          # type: ignore
    states.error("srv_schedule")
    body = captured[0]
    for leak in ("Traceback", "psycopg2", "password", "5432", "143.110"):
        assert leak not in body


# --- numbers and nulls -------------------------------------------------------------------

def test_null_and_zero_are_never_confusable():
    """AC-G.32. A zero is a measurement; a null is the absence of one."""
    assert fmt.number(None) == fmt.EM_DASH
    assert fmt.number(float("nan")) == fmt.EM_DASH
    assert fmt.number(0, "spread") == "0.0"
    assert fmt.number(0, "spread") != fmt.EM_DASH


def test_precision_is_fixed_per_column_not_per_value():
    """AC-G.31: `7` renders `7.0` where its column is 1 dp."""
    assert fmt.number(7, "spread") == "7.0"
    assert fmt.number(7, "margin_mae") == "7.00"
    assert fmt.number(7, "epa_per_play") == "7.000"


def test_longest_keyword_wins_so_error_is_not_read_as_margin():
    assert fmt.precision_for("absolute_margin_error") == 2


def test_a_rate_always_carries_its_n():
    """AC-G.33: 17.9% on n=11 is noise wearing a big number."""
    assert "n=11" in fmt.with_n(17.9, 11, "hit_rate")


# --- chips -------------------------------------------------------------------------------

def test_push_and_pending_are_distinguishable():
    """AC-3.3. A push is a settled result; a pending game has not been played."""
    push = chips.cover_chip_html("push")
    pending = chips.cover_chip_html(None)
    assert push != pending
    assert "Push" in push and "Pending" in pending


def test_every_chip_carries_a_glyph_and_an_accessible_label():
    """AC-G.22/23: meaning survives greyscale and is never colour-only."""
    for variant, (glyph, _, _) in chips.VARIANTS.items():
        html = chips.chip_html(variant)
        assert glyph in html
        assert "aria-label=" in html


def test_out_of_sample_copy_says_week_not_prediction():
    """The flag is week-level; calling it a prediction-level claim would be wrong."""
    html = chips.out_of_sample_chip_html(True)
    assert "week" in html.lower()
    assert "out-of-sample prediction" not in html.lower()


# --- the nav contract --------------------------------------------------------------------

def test_all_eighteen_pages_appear_including_blocked_ones():
    """AC-G.51: blocked pages are not hidden."""
    assert len(PAGES) == 18
    assert not BY_KEY["players"].buildable
    assert BY_KEY["players"] in PAGES


def test_groups_match_the_wireframe():
    assert GROUPS == ["Overview", "Games & teams", "Betting", "Deliverable",
                      "Reference", "Back of house"]


def test_a_blocked_page_names_a_specific_object():
    page = BY_KEY["players"]
    assert page.blocker and page.blocker.startswith("srv_")
    assert "dim_athlete" in page.blocker_note


# --- page-level criteria that are checkable without a browser ---------------------------

def test_every_page_module_exists_and_exposes_render():
    """AC-G.49: nav builds from the registry, so a missing module breaks the whole site."""
    import importlib
    for page in PAGES:
        module = importlib.import_module(f"pages.{page.key}")
        assert callable(getattr(module, "render", None)), page.key


def test_built_pages_pass_the_query_contract():
    """Every SQL string in a built page must satisfy G-1/G-2/AC-G.39.

    Checked by extracting the literals rather than by reading them, because the contract is
    the kind of thing that is true when written and false three edits later.
    """
    import re
    from pathlib import Path
    site = Path(__file__).resolve().parents[1] / "site"
    checked = 0
    for path in (site / "pages").glob("*.py"):
        source = path.read_text()
        for sql in re.findall(r'"""\s*(select\b.*?)"""', source, re.DOTALL | re.IGNORECASE):
            check_contract(" ".join(sql.split()))
            checked += 1
    for path in [site / "lib" / "filters.py"]:
        for sql in re.findall(r'"""\s*(select\b.*?)"""', path.read_text(),
                              re.DOTALL | re.IGNORECASE):
            check_contract(" ".join(sql.split()))
            checked += 1
    assert checked >= 5, f"expected several page queries, found {checked}"


def test_model_performance_lists_the_model_that_was_never_written():
    """AC-13.4: a missing model is a visible row, not a shorter table."""
    from pages import performance
    assert "fastai_home_win" in performance.EXPECTED_MODELS


def test_ats_breakeven_is_the_real_number():
    """AC-13.3: 52.4% is breakeven at −110; a softer threshold would flatter the model."""
    from pages import performance
    assert performance.BREAKEVEN == 52.4
