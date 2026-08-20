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


# --- A4 page bodies ----------------------------------------------------------------------

def test_every_page_now_has_a_body_except_the_blocked_one():
    """A4's completion criterion, checked rather than claimed.

    `shell.render_page(key)` with no body renders the "not built yet" placeholder. Counting
    which modules still call it that way is the only honest measure of how much of A4 is
    done — a progress note in a document is a claim, and this is the same claim executable.
    """
    import re
    from pathlib import Path
    from lib.registry import BY_KEY
    pages = Path(__file__).resolve().parents[1] / "site" / "pages"
    placeholders = set()
    for path in pages.glob("*.py"):
        if path.stem == "__init__":
            continue
        source = path.read_text()
        # A body-less page is exactly `shell.render_page("key")` with no second argument.
        if re.search(r'render_page\(\s*"[^"]+"\s*\)', source):
            placeholders.add(path.stem)
    # Players is the only one left, and it stays: its primary view does not exist, so the
    # shell renders the blocked state and a body would have nothing to read. Asserting
    # equality rather than a subset — a loose bound stops measuring anything once the work
    # is done, which is precisely when it should start guarding against regression.
    assert placeholders == {"players"}, f"still placeholders: {sorted(placeholders)}"
    assert not BY_KEY["players"].buildable


def test_edge_finder_reads_its_week_floor_from_data_not_from_a_constant():
    """The week-5 rule is the model's property and must travel with the model.

    A hardcoded 5 in the page would go stale the first time the model is retrained on a
    different cut, and the page would keep confidently stating the old number.
    """
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "pages" / "edges.py").read_text()
    assert "training_week_floor" in source
    # The user-facing sentence interpolates the floor rather than naming a week. Asserting
    # that "Week 5" appears nowhere in the file was the first version of this test and it
    # failed on the docstring explaining why not to hardcode it — a test that cannot tell
    # prose from copy is a test that gets loosened rather than fixed.
    assert "Week {floor}" in source


def test_edge_finder_empty_copy_is_empty_not_degraded():
    """AC-G.51. Nothing is broken in weeks 1-4 and nothing is missing that should exist,
    so Degraded would be a false statement about whose fault it is."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "pages" / "edges.py").read_text()
    assert "states.empty(" in source
    assert "states.degraded(" not in source


def test_matchup_does_not_flip_the_sign_convention_itself():
    """G-3: a sign convention is a definition, and definitions live in dbt.

    The page reads actual_margin_home_perspective rather than negating actual_margin, so
    there is exactly one place the convention is expressed.
    """
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "pages" / "matchup.py").read_text()
    assert "actual_margin_home_perspective" in source
    assert "-float(" not in source and "-1 *" not in source


def test_matchup_reads_series_ties_rather_than_deriving_them():
    """A tie is its own outcome. Subtracting to find the away record credited every draw
    to the away team in 40,045 rows."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "pages" / "matchup.py").read_text()
    assert "series_ties" in source


def test_blank_confidence_bucket_renders_as_absent():
    """The pack writes an empty string where it has no bucket, and an empty cell reads as
    a value. Same defect class as the ats 0-0-0 that manufactured a record."""
    from pages import edges
    from lib import fmt
    assert edges._bucket({"confidence_bucket": ""}) == fmt.EM_DASH
    assert edges._bucket({"confidence_bucket": None}) == fmt.EM_DASH
    assert edges._bucket({"confidence_bucket": "high"}) == "high"


def test_moneylines_never_render_with_a_decimal_point():
    """A price with a decimal point reads like a spread, and those are different
    quantities. -270.0 is not a moneyline anyone has seen."""
    from pages import odds
    render = odds._moneyline("home_moneyline")
    assert render({"home_moneyline": -270}) == "-270"
    assert render({"home_moneyline": 145}) == "+145"


def test_odds_best_price_can_be_both_sides():
    """One book holding the best number on each side is a real market state, not a bug."""
    from pages import odds
    assert odds._best({"is_best_home_spread": True, "is_best_away_spread": True}) == "both"
    assert odds._best({"is_best_home_spread": False, "is_best_away_spread": False}) != "both"


def test_dictionary_renders_undocumented_as_a_value():
    """AC-16.2: a blank description cell reads as a rendering fault; a state reads as debt."""
    from pages import dictionary
    html = dictionary._status({"description_status": "UNDOCUMENTED"})
    assert "Undocumented" in html
    assert "cfdb-chip" in html


def test_methodology_states_the_counterintuitive_sign_convention():
    """The one fact a reader is most likely to get backwards has to be on the page that
    exists to explain the numbers."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "pages"
              / "methodology.py").read_text()
    assert "away points minus home points" in source
    assert "betting advice" in source.lower()
    assert "Week 5" in source
    # The licence obligation, stated on the page and not only in a column.
    assert "not CollegeFootballData.com predictions" in source


def test_every_site_dependency_is_in_the_site_image_requirements():
    """The site image has its own requirements list, and forgetting it is silent.

    Two lists exist for a good reason — the repo root carries dbt, the Databricks driver
    and the ingestion stack, none of which belong on a 1 GiB droplet whose only job is
    rendering. The cost is that a new site dependency has to be added to both, and missing
    the second one fails in the worst possible way: the tests pass, CI passes, the image
    builds, the container starts, and the one page that needs it raises on import when
    somebody opens it.

    That is exactly what happened with openpyxl for the Excel export, so the coupling is
    now checked rather than remembered.
    """
    import ast
    import sys as _sys
    from pathlib import Path

    site = Path(__file__).resolve().parents[1] / "site"
    requirements = (Path(__file__).resolve().parents[1]
                    / "deploy" / "site" / "requirements.txt").read_text().lower()

    # Import name -> distribution name, where they differ.
    DISTRIBUTION = {"dotenv": "python-dotenv", "psycopg2": "psycopg2-binary",
                    "yaml": "pyyaml"}
    LOCAL = {"lib", "pages", "app"}

    imported = set()
    for path in site.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])

    third_party = {
        name for name in imported
        if name not in LOCAL and name not in _sys.stdlib_module_names
    }
    missing = sorted(
        name for name in third_party
        if DISTRIBUTION.get(name, name) not in requirements)
    assert not missing, (
        f"imported by site/ but absent from deploy/site/requirements.txt: {missing}")


# --- the post-game render path -----------------------------------------------------------

def test_the_winner_is_read_from_the_view_not_derived_from_a_sign():
    """The page used to pick the winner by the sign of actual_margin and index into a
    display column. Two derivations of one definition disagree eventually, and this pair
    disagreed on 1 game in 295 the first time it was run against real completed games."""
    from pages import scores
    row = {"is_completed": True, "winner": "Alpha State", "actual_margin": -7,
           "home_team_display": "Alpha State", "away_team_display": "Beta Tech"}
    assert "Alpha State" in scores._winner(row)


def test_a_tie_is_a_settled_result_not_a_pending_one():
    """srv_scoreboard returns NULL for `winner` on a completed game with equal scores.
    Rendering that as Pending would claim the game has not been played."""
    from pages import scores
    tie = scores._winner({"is_completed": True, "winner": None, "actual_margin": 0})
    pending = scores._winner({"is_completed": False, "winner": None})
    assert "Tie" in tie
    assert "Pending" in pending
    assert tie != pending


def test_the_winner_never_renders_the_string_none():
    """A formatter that indexes into a nullable column and interpolates the result puts
    `None` on the page. 11% of srv_scoreboard is a game against a team with no dim_team
    row, so the nullable case is the common case, not an edge."""
    from pages import scores
    for row in ({"is_completed": True, "winner": None, "actual_margin": 0},
                {"is_completed": False, "winner": None, "actual_margin": None}):
        assert "None" not in scores._winner(row)
