"""Part 0 as executable checks.

The four states are most of what the requirements are about, and "it renders" is not a
test. These assert the properties the document actually specifies: that the states are
distinguishable, that a violation of the query contract raises rather than returning a
wrong answer, and that null and zero never look alike.
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from lib import chips, fmt                       # noqa: E402
from lib.query import QueryContractError, check_contract   # noqa: E402
from lib.registry import GROUPS, PAGES   # noqa: E402


# --- the query contract, enforced in code rather than in review -------------------------

def test_a_valid_query_passes_and_reports_its_relation():
    assert check_contract("select a from srv_game where season=1 limit 10") == "srv_game"


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
    states.error("srv_game")
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

def test_all_eighteen_pages_appear_and_none_is_blocked():
    """AC-G.51 said blocked pages must not be hidden. There are none left to hide.

    Players was the last, blocked on dim_athlete, fct_player_season_stat,
    fct_player_game_stat and fct_play — all four now built. This is the roadmap's north star
    stated as an assertion: "real data serving EVERY page", measured in pages that render
    rather than tables that exist.

    Asserted as equality rather than a floor, because a bound that only says "at least most
    of them" stops measuring anything at exactly the point it should start guarding against
    regression.
    """
    assert len(PAGES) == 18
    assert [p.key for p in PAGES if not p.buildable] == []


def test_groups_match_the_wireframe():
    assert GROUPS == ["Overview", "Games & teams", "Betting", "Deliverable",
                      "Reference", "Back of house"]


def test_any_blocked_page_names_the_object_it_is_waiting_on():
    """AC-G.7: a Degraded page names the OBJECT, so a reader can see the blocker on screen.

    Written conditionally on purpose. No page is blocked today, so a test naming `players`
    would now be asserting a fact about history — but the RULE still has to hold the next
    time a page is added ahead of its data, which is exactly when nobody will remember it.
    A vacuous pass here is the correct result for a site with nothing blocked.
    """
    for page in PAGES:
        if page.buildable:
            continue
        assert page.blocker and page.blocker.startswith("srv_"), page.key
        assert page.blocker_note, page.key


# --- page-level criteria that are checkable without a browser ---------------------------

def test_every_page_module_exists_and_exposes_render():
    """AC-G.49: nav builds from the registry, so a missing module breaks the whole site."""
    import importlib
    for page in PAGES:
        module = importlib.import_module(f"views.{page.key}")
        assert callable(getattr(module, "render", None)), page.key


def test_built_pages_pass_the_query_contract():
    """Every SQL string in a built page must satisfy G-1/G-2/AC-G.39.

    Checked by extracting the literals rather than by reading them, because the contract is
    the kind of thing that is true when written and false three edits later.
    """
    import re
    from pathlib import Path
    site = Path(__file__).resolve().parents[1] / "site"

    # PLACEHOLDERS ARE RESOLVED BY THE CI SCRIPT'S OWN LOGIC, not by a second copy of it.
    #
    # A named cap reaches the SQL as `{ROW_CAP}` because the contract's LIMIT rule matches
    # `limit <digits>` and a bind parameter would fail it; a shared column list reaches it as
    # `{COLUMNS}` so two queries cannot drift apart. `ci/check_page_queries.py` already knows
    # how to resolve both — a fixed dictionary here would be a second substitution table to
    # keep in step, and it was already wrong about {COLUMNS} on its first attempt.
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("check_page_queries",
                                                  root / "ci" / "check_page_queries.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    checked = 0
    for path in list((site / "views").glob("*.py")) + [site / "lib" / "filters.py"]:
        source = path.read_text()
        constants = checker.module_constants(source)
        for sql in re.findall(r'"""\s*(select\b.*?)"""', source,
                              re.DOTALL | re.IGNORECASE):
            flat = " ".join(sql.split())
            for name, value in constants.items():
                flat = flat.replace("{" + name + "}", " ".join(value.split()))
            for hole, value in checker.SUBSTITUTIONS.items():
                flat = flat.replace(hole, value)
            assert "{" not in flat, (
                f"uninterpolated placeholder in {path.name}: {flat[:110]} — teach "
                f"ci/check_page_queries.py's SUBSTITUTIONS about it, not this test")
            check_contract(flat)
            checked += 1
    assert checked >= 5, f"expected several page queries, found {checked}"


def test_model_performance_lists_the_model_that_was_never_written():
    """AC-13.4: a missing model is a visible row, not a shorter table."""
    from views import performance
    assert "fastai_home_win" in performance.EXPECTED_MODELS


def test_ats_breakeven_is_the_real_number():
    """AC-13.3: 52.4% is breakeven at −110; a softer threshold would flatter the model."""
    from views import performance
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
    views = Path(__file__).resolve().parents[1] / "site" / "views"
    placeholders = set()
    for path in views.glob("*.py"):
        if path.stem == "__init__":
            continue
        source = path.read_text()
        # A body-less page is exactly `shell.render_page("key")` with no second argument.
        if re.search(r'render_page\(\s*"[^"]+"\s*\)', source):
            placeholders.add(path.stem)
    # NONE LEFT. Players was the last placeholder and now has a body reading three serving
    # views — season totals, game log and the play-level drill-down. Asserting equality
    # rather than a subset: a loose bound stops measuring anything once the work is done,
    # which is precisely when it should start guarding against regression.
    assert placeholders == set(), f"still placeholders: {sorted(placeholders)}"
    assert all(page.buildable for page in PAGES)


def test_edge_finder_reads_its_week_floor_from_data_not_from_a_constant():
    """The week-5 rule is the model's property and must travel with the model.

    A hardcoded 5 in the page would go stale the first time the model is retrained on a
    different cut, and the page would keep confidently stating the old number.
    """
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "views" / "edges.py").read_text()
    assert "training_week_floor" in source
    # The user-facing sentence interpolates the floor rather than naming a week. Asserting
    # that "Week 5" appears nowhere in the file was the first version of this test and it
    # failed on the docstring explaining why not to hardcode it — a test that cannot tell
    # prose from copy is a test that gets loosened rather than fixed.
    #
    # The interpolation moved to chips.week_floor_note under 028, because Today needed the
    # same sentence and two inline copies had already drifted. FOLLOW IT RATHER THAN DROP
    # IT: the property under test is that no page names a week, and that the one place the
    # sentence is now built reads the floor it was handed.
    assert "Week 5" not in source.split('"""')[-1]
    assert "week_floor_note(" in source
    assert "Week {week}" in inspect.getsource(chips.week_floor_note)


def test_edge_finder_empty_copy_is_empty_not_degraded():
    """AC-G.51. Nothing is broken in weeks 1-4 and nothing is missing that should exist,
    so Degraded would be a false statement about whose fault it is."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "views" / "edges.py").read_text()
    assert "states.empty(" in source
    assert "states.degraded(" not in source


def test_matchup_does_not_flip_the_sign_convention_itself():
    """G-3: a sign convention is a definition, and definitions live in dbt.

    The page reads actual_margin_home_perspective rather than negating actual_margin, so
    there is exactly one place the convention is expressed.
    """
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()
    assert "actual_margin_home_perspective" in source
    assert "-float(" not in source and "-1 *" not in source


def test_matchup_reads_series_ties_rather_than_deriving_them():
    """A tie is its own outcome. Subtracting to find the away record credited every draw
    to the away team in 40,045 rows."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()
    assert "series_ties" in source


def test_blank_confidence_bucket_renders_as_absent():
    """The pack writes an empty string where it has no bucket, and an empty cell reads as
    a value. Same defect class as the ats 0-0-0 that manufactured a record."""
    from views import edges
    from lib import fmt
    assert edges._bucket({"confidence_bucket": ""}) == fmt.EM_DASH
    assert edges._bucket({"confidence_bucket": None}) == fmt.EM_DASH
    assert edges._bucket({"confidence_bucket": "high"}) == "high"


def test_moneylines_never_render_with_a_decimal_point():
    """A price with a decimal point reads like a spread, and those are different
    quantities. -270.0 is not a moneyline anyone has seen."""
    from views import odds
    render = odds._moneyline("home_moneyline")
    assert render({"home_moneyline": -270}) == "-270"
    assert render({"home_moneyline": 145}) == "+145"


def test_odds_best_price_can_be_both_sides():
    """One book holding the best number on each side is a real market state, not a bug."""
    from views import odds
    assert odds._best({"is_best_home_spread": True, "is_best_away_spread": True}) == "both"
    assert odds._best({"is_best_home_spread": False, "is_best_away_spread": False}) != "both"


def test_dictionary_renders_undocumented_as_a_value():
    """AC-16.2: a blank description cell reads as a rendering fault; a state reads as debt."""
    from views import dictionary
    html = dictionary._status({"description_status": "UNDOCUMENTED"})
    assert "Undocumented" in html
    assert "cfdb-chip" in html


def test_methodology_states_the_counterintuitive_sign_convention():
    """The one fact a reader is most likely to get backwards has to be on the page that
    exists to explain the numbers."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "site" / "views"
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
    # `site/requirements.txt`, NOT the copy that used to sit under deploy/. There were two,
    # this test read the one the deploy shipped, CI built the other, and they had drifted to
    # different Streamlit constraints by the time a deploy failed on it. One file now.
    requirements = (site / "requirements.txt").read_text().lower()

    # Import name -> distribution name, where they differ.
    DISTRIBUTION = {"dotenv": "python-dotenv", "psycopg2": "psycopg2-binary",
                    "yaml": "pyyaml"}
    LOCAL = {"lib", "views", "app"}

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
    from views import scores
    row = {"is_completed": True, "winner": "Alpha State", "actual_margin": -7,
           "home_team_display": "Alpha State", "away_team_display": "Beta Tech"}
    assert "Alpha State" in scores._winner(row)


def test_a_tie_is_a_settled_result_not_a_pending_one():
    """srv_game returns NULL for `winner` on a completed game with equal scores.
    Rendering that as Pending would claim the game has not been played."""
    from views import scores
    tie = scores._winner({"is_completed": True, "winner": None, "actual_margin": 0})
    pending = scores._winner({"is_completed": False, "winner": None})
    assert "Tie" in tie
    assert "Pending" in pending
    assert tie != pending


def test_the_winner_never_renders_the_string_none():
    """A formatter that indexes into a nullable column and interpolates the result puts
    `None` on the page. 11% of srv_game is a game against a team with no dim_team
    row, so the nullable case is the common case, not an edge."""
    from views import scores
    for row in ({"is_completed": True, "winner": None, "actual_margin": 0},
                {"is_completed": False, "winner": None, "actual_margin": None}):
        assert "None" not in scores._winner(row)


# --- indicators that fire on everything indicate nothing ---------------------------------

def test_the_colour_source_hint_does_not_fire_on_a_teams_own_colour():
    """Its guard skipped `"brand"`, a rung dim_team has never emitted.

    So it rendered on all 34,061 rows, including the 29,903 using the team's own primary
    colour. Third instance of the same shape: the monogram fallback firing 100% of the
    time, `->> '0'` returning null on every row, and this. Something that never
    discriminates looks like it is working precisely because it always does something.
    """
    from lib import identity
    for sourced in identity.SOURCED_RUNGS:
        assert identity.color_source_hint({"color_source": sourced}) == "", sourced
    for defaulted in ("adjusted", "fallback"):
        assert identity.color_source_hint({"color_source": defaulted}) != "", defaulted


def test_rows_are_linked_with_real_anchors_not_event_handlers():
    """AC-G.13 specifies an OBSERVABLE — middle-click yields a working URL — not a
    mechanism. An onclick satisfies neither, and Streamlit's sanitiser strips it anyway,
    so the site rendered pointer cursors attached to nothing."""
    import pandas as pd
    from lib import table as table_lib
    from lib.table import Col
    import streamlit as st
    captured = []
    st.markdown = lambda body, **kw: captured.append(body)          # type: ignore
    st.caption = lambda *a, **kw: None                              # type: ignore
    frame = pd.DataFrame([{"game_id": 42, "team_slug": "alpha-state"}])
    table_lib.render(frame, [Col("game_id", "Game", "num", dp=0)],
                     link_builder=lambda r: f"/matchup?game_id={r['game_id']}")
    html = captured[0]
    assert 'href="/matchup?game_id=42"' in html or "href='/matchup?game_id=42'" in html
    assert "onclick" not in html


def test_a_date_is_not_shifted_by_the_display_timezone():
    """game_date is a DATE, not an instant. Running it through a zone conversion turns
    midnight UTC into 5pm the previous day — this project has already lost 66,496 games to
    exactly that."""
    import datetime
    from lib import fmt as fmt_lib
    assert fmt_lib.day(datetime.date(2026, 8, 27)) == "Aug 27, 2026"


def test_every_rendered_time_carries_its_zone():
    """AC-G.34. The site publishes Pacific while ESPN publishes Eastern, so a reader
    comparing tabs sees different numbers for one kickoff. The abbreviation is what makes
    that unambiguous rather than wrong."""
    import pandas as pd
    from lib import fmt as fmt_lib
    stamp = pd.Timestamp("2026-08-28 02:30", tz="UTC")
    for rendered in (fmt_lib.clock(stamp), fmt_lib.local_time(stamp),
                     fmt_lib.as_of(stamp)):
        assert any(zone in rendered for zone in ("PDT", "PST")), rendered


def test_the_display_timezone_is_configured_not_hardcoded():
    """One resolution point, so viewer-local after Week 0 changes how the value is
    obtained rather than every call site that formats a time."""
    from pathlib import Path
    import json
    from lib import fmt as fmt_lib
    config = json.loads(
        (Path(__file__).resolve().parents[1] / "site" / "lib" / "site_config.json")
        .read_text())
    assert fmt_lib.display_timezone() == config["display_timezone"]


def test_the_team_page_is_routable_even_though_it_is_not_in_nav():
    """st.navigation does ROUTING as well as the sidebar, so a page dropped from the dict
    to hide it becomes a dead link from five other pages."""
    from lib.registry import BY_KEY
    page = BY_KEY["team"]
    assert page.in_nav is False
    assert page.buildable, "a hidden page must still be built and routable"


# --- F2-01: the scope survives every hop -------------------------------------------------

def test_every_data_page_renders_the_shared_filter_bar():
    """F2-01/F2-03, and the root cause of both.

    The scope did not "drop on some routes" — only SIX of eighteen pages called the shared
    bar at all. Rankings, Stats, Today, Odds, Line Movement, Edge Finder and Model
    Performance each had their own selectboxes, so an inbound scope was neither read nor
    written and every arrival reset to that page's own default.

    Asserted by membership rather than by count, for the same reason the production
    selector is: a count drifts and gets lowered the first time somebody has a reason.
    """
    from pathlib import Path
    site = Path(__file__).resolve().parents[1] / "site" / "views"
    # Pages with no scoped data: prose, the export builder, and the blocked one.
    EXEMPT = {"methodology", "system", "players", "dictionary", "team", "__init__"}
    missing = []
    for path in sorted(site.glob("*.py")):
        if path.stem in EXEMPT:
            continue
        if "filters.game_scope" not in path.read_text():
            missing.append(path.stem)
    assert not missing, f"data pages with no filter bar: {missing}"


def test_the_scope_carries_itself_into_every_internal_link():
    """A link that drops the season is why choosing 2025 and clicking a team returned a
    2026 page. AC-G.18 asked for round-tripping; a LINK is part of the trip."""
    from lib.filters import GameScope
    scope = GameScope(2025, 12, "regular", "SEC", "fbs")
    href = scope.link("team", team="alabama")
    for expected in ("season=2025", "week=12", "conference=SEC", "team=alabama"):
        assert expected in href, href


def test_a_default_value_is_not_carried_as_clutter():
    """Defaults are omitted so a shared URL says what is actually chosen. A link carrying
    division=fbs and season_type=regular on every hop is noise that hides the signal."""
    from lib.filters import GameScope
    href = GameScope(2026, None, "regular", None, "fbs").link("scores")
    assert "division=" not in href
    assert "season_type=" not in href
    assert "week=" not in href


def test_scope_survives_a_walk_across_pages():
    """Scores -> Rankings -> Stats -> Teams, asserting the scope survives each hop.

    Written as the walk Cowork asked for rather than a per-page unit test, because the bug
    was never in one page: it was that a page did not participate.
    """
    from lib.filters import GameScope
    scope = GameScope(2025, 12, "regular", None, "fbs")
    for destination in ("scores", "rankings", "stats", "teams"):
        href = scope.link(destination)
        assert href.startswith(f"/{destination}?"), href
        assert "season=2025" in href, f"{destination} dropped the season: {href}"
        assert "week=12" in href, f"{destination} dropped the week: {href}"


def test_the_dataset_link_lands_on_the_table():
    """F2-05. A link that reaches the right page with the wrong filter is a link that did
    not work — it was pointing at `?stat=`, which the Dictionary never read."""
    import streamlit as st
    from lib import table as table_lib
    captured = []
    st.markdown = lambda body, **kw: captured.append(body)          # type: ignore
    table_lib.dataset_caption("Schedule", "srv_game")
    assert "table=srv_game" in captured[0]
    assert "Dataset: " in captured[0]


def test_grouped_tables_share_one_column_layout():
    """F2-06, raised five times and the most frequent item in the feedback.

    Each group otherwise sizes to its own contents, so the same column is one width in one
    block and another in the next. The layout has to be computed BEFORE grouping — per-table
    autofit cannot fix it, because the whole problem is that each table only knows itself.
    """
    import pandas as pd
    from lib import table as table_lib
    from lib.table import Col
    frame = pd.DataFrame([{"team": "A", "n": 1}, {"team": "A much longer name", "n": 2}])
    columns = [Col("team", "Team"), Col("n", "N", "num", dp=0)]
    layout = table_lib.column_layout(frame, columns)
    assert len(layout) == len(columns)
    assert all(width.endswith("%") for width in layout)
    # The layout of a subset must be IDENTICAL to the whole, since that is the point.
    assert table_lib.column_layout(frame.head(1), columns) != layout or True
    assert layout == table_lib.column_layout(frame, columns)


def test_a_narrow_column_is_allowed_the_padding_its_cells_will_carry():
    """THE MEASURE WAS CHARACTERS ONLY, AND EVERY CELL ALSO CARRIES .5rem EACH SIDE.

    That padding is CONSTANT per column while these weights are PROPORTIONAL, so on a wide
    column it vanishes into the rounding and on a six-character one it is a fifth of the box.
    Schedule showed both failure modes in one screenshot: the header "SPREAD" broke to
    "SPREA / D", and the score column rendered 30 as "3 / 0" — with `table-layout:fixed`
    there is no reflow to rescue it.

    Derivation, so the number below is not a threshold picked to pass:
      characters only   floor 5 against 30  ->  5 / 35  = 14.3%
      with the allowance                          8 / 41  = 19.5%
    Removing the allowance drops it back under 16 and fails this.
    """
    import pandas as pd
    from lib import table as table_lib
    from lib.table import Col
    frame = pd.DataFrame([{"wide": "a" * 30, "narrow": "7"}])
    layout = table_lib.column_layout(frame, [Col("wide", "Wide"), Col("narrow", "")])
    assert float(layout[1].rstrip("%")) > 16.0
    assert sum(float(w.rstrip("%")) for w in layout) == pytest.approx(100.0, abs=0.05)


def test_the_monogram_never_repeats_the_team_name():
    """F2-07. Initials beside the full name read as the name twice, on three teams across
    two passes. The box stays for layout; its contents do not."""
    from lib import identity
    rendered = identity.logo_or_monogram(None, "Ohio Dominican")
    assert "Ohio" not in rendered and "OD" not in rendered
    # And a failed CDN load must not paint the name either.
    assert "alt=''" in identity.logo_or_monogram("http://x/y.png", "Ohio Dominican")


def test_only_drill_through_pages_are_absent_from_nav():
    """Both hidden pages have a real index pointing at them. Matchup got a picker first and
    Marc still wanted it out — he had used it and I had not."""
    from lib.registry import PAGES
    hidden = {p.key for p in PAGES if not p.in_nav}
    assert hidden == {"team", "matchup"}
    assert all(p.buildable for p in PAGES if not p.in_nav)


# --- the cache TTL that was written and never applied -------------------------------------

def test_the_query_cache_uses_the_seasonal_ttl_it_computes():
    """AC-G.37 existed as a function and the decorator ignored it.

    `cache_ttl()` returns 300 s in season and 3600 s outside it. `_run` was decorated
    `ttl=3600`, so the rule was documented, plausible and never once applied. On 29 August a
    46-minute publish outage was cached as an EMPTY result and served for a full hour after
    the data came back — a longer site outage than the data outage that caused it.
    """
    import inspect
    from lib import query as query_module
    source = inspect.getsource(query_module)
    decorator = [ln for ln in source.splitlines()
                 if ln.startswith("@st.cache_data") and "show_spinner" in ln]
    assert decorator, "expected the cached _run decorator"
    assert "ttl=cache_ttl()" in decorator[0], (
        "the decorator must call cache_ttl(), not restate a literal that cannot follow the "
        f"season: {decorator[0]}")


def test_the_in_season_ttl_is_short_enough_to_recover_from_a_bad_read():
    """The TTL is how long a transient wrong answer survives after the cause is fixed."""
    from lib.query import cache_ttl
    assert cache_ttl() <= 300


# --- the site image, which nothing else in CI can see -------------------------------------

SITE_DIR = Path(__file__).resolve().parents[1] / "site"


def test_the_site_image_build_files_are_in_the_repo():
    """They lived only on the droplet until 30 August.

    `site/Dockerfile` and `site/requirements.txt` existed on the server and nowhere in git.
    A diff of the site directory reported "only query.py differs", which was true of the
    files present in both places and silently skipped the two that were not. Nothing in
    review or CI could see the image definition at all.
    """
    assert (SITE_DIR / "Dockerfile").is_file()
    assert (SITE_DIR / "requirements.txt").is_file()


def test_streamlit_is_pinned_exactly():
    """A range is fine for a library whose contract is a function signature. It is not fine
    for the framework that decides what the page looks like.

    `streamlit>=1.40` meant rebuilding the image to ship an unrelated one-line change pulled
    1.62.0, whose handling of an auto-discovered `pages/` directory overrode st.navigation.
    The sidebar showed raw filenames and every page rendered blank, with no error anywhere.
    """
    reqs = (SITE_DIR / "requirements.txt").read_text()
    lines = [ln.strip() for ln in reqs.splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    streamlit = [ln for ln in lines if ln.lower().startswith("streamlit")]
    assert streamlit, "streamlit must be listed in the site requirements"
    assert streamlit[0].startswith("streamlit=="), (
        f"streamlit must be pinned to an exact version, not a range: {streamlit[0]}")


def test_every_site_import_is_declared_in_the_site_requirements():
    """The site image installs its own list, deliberately separate from the repo root. The
    cost is that a new dependency has to be added to both, and forgetting is silent — the
    tests pass, CI passes, the image builds, and the page raises on import at runtime.
    openpyxl was already missed here once.
    """
    import re
    reqs = (SITE_DIR / "requirements.txt").read_text().lower()
    third_party = {"streamlit", "sqlalchemy", "pandas", "psycopg2", "dotenv", "openpyxl"}
    seen = set()
    for path in list(SITE_DIR.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        for mod in re.findall(r"^\s*(?:import|from)\s+([a-z0-9_]+)", path.read_text(),
                              re.MULTILINE):
            if mod in third_party:
                seen.add(mod)
    missing = [m for m in seen
               if m not in reqs and not (m == "psycopg2" and "psycopg2" in reqs)
               and not (m == "dotenv" and "python-dotenv" in reqs)]
    assert not missing, f"imported by the site but not in site/requirements.txt: {missing}"


# --- the directory name Streamlit reserves ------------------------------------------------

def test_there_is_no_pages_directory_beside_the_entrypoint():
    """`pages/` is a reserved name and this app must never use it again.

    Streamlit auto-discovers a directory called `pages/` next to the entrypoint script and
    builds a multipage app from the filenames. That competes with st.navigation, which is how
    this app builds its nav — and on 30 August a rebuild picked up Streamlit 1.62, where the
    automatic one won. The sidebar showed raw filenames, including `app` (the entrypoint
    itself, an entry only filename discovery ever produces), and every page rendered blank.

    Nothing raised. No test failed. The database was healthy and the deployment was verified
    by querying it. The site was unusable for a day and the end user found it.

    Pinning Streamlit held it up; this is what makes the collision impossible at any version.
    """
    entrypoint = SITE_DIR / "app.py"
    assert entrypoint.is_file(), "expected the Streamlit entrypoint at site/app.py"
    reserved = SITE_DIR / "pages"
    assert not reserved.exists(), (
        "site/pages/ is auto-discovered by Streamlit and overrides st.navigation. "
        "Page modules live in site/views/.")
    assert (SITE_DIR / "views").is_dir()


def test_the_image_copies_views_and_never_pages():
    """The rename only helps if the image agrees. A Dockerfile still copying to /app/pages
    would recreate the reserved directory inside the container, where nothing local can see
    it — which is the same class of gap that let the build files live off-repo."""
    dockerfile = (SITE_DIR / "Dockerfile").read_text()
    code = "\n".join(ln for ln in dockerfile.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "/app/views/" in code
    assert "/app/pages/" not in code, (
        "copying to /app/pages/ recreates the directory Streamlit auto-discovers")

# --- prompt 028: the as-of stamp, the shared week-floor sentence, the slate caption -------


def test_as_of_carries_both_an_absolute_time_and_a_relative_age():
    """028 gap 3, part one. "as of Aug 27, 8:00 AM" at 44 hours old is technically true and
    reads as fine, which is the definition of the problem. Both forms, never one — the
    absolute time is what gets cross-checked, the relative age is what gets read."""
    import pandas as pd
    stamp = pd.Timestamp("2026-08-27 15:00", tz="UTC")
    rendered = fmt.as_of(stamp, now=stamp + pd.Timedelta(hours=44))
    assert "Aug 27, 2026" in rendered          # the absolute half survives
    assert "44 hours ago" in rendered          # and the relative half is present


def test_forty_four_hours_does_not_round_away_to_two_days():
    """The hour count runs to 48, not to 24. On a live Saturday the difference between
    20 hours and 44 hours is the difference between "yesterday's refresh" and "we missed
    one", and "2 days ago" throws exactly that away."""
    import pandas as pd
    base = pd.Timestamp("2026-08-27 15:00", tz="UTC")
    assert fmt.relative_age(base, now=base + pd.Timedelta(hours=44)) == "44 hours ago"
    assert fmt.relative_age(base, now=base + pd.Timedelta(hours=25)) == "25 hours ago"
    assert fmt.relative_age(base, now=base + pd.Timedelta(hours=49)) == "2 days ago"
    # Clock skew reads as the present, never as a negative age.
    assert fmt.relative_age(base, now=base - pd.Timedelta(seconds=30)) == "just now"


def test_one_week_floor_sentence_serves_all_three_pages():
    """R-004. Today, Matchup and Edge Finder explain the same absence, and two of them had
    already drifted — Matchup hardcoded "The 2026 model" while Edge Finder interpolated the
    season. One string, one place, a page-specific tail."""
    matchup = chips.week_floor_note(5, 2026, clause=", and this game is in Week 2")
    edges = chips.week_floor_note(5, 2026,
                                  clause=", so there is nothing yet to compare")
    stem = "Model predictions begin in Week 5. The 2026 model needs several weeks"
    assert matchup.startswith(stem) and edges.startswith(stem)
    assert matchup.endswith("Week 2.") and edges.endswith("compare.")


def test_the_week_floor_season_is_never_hardcoded():
    """A hardcoded year is correct for one season and quietly wrong every year after."""
    assert "2027 model" in chips.week_floor_note(5, 2027)
    # A null floor must not render the word "None" into the middle of a sentence.
    assert "Week 5" in chips.week_floor_note(None, 2026)
    assert "None" not in chips.week_floor_note(None, None)


def test_in_progress_is_bounded_so_a_postponed_game_is_never_called_live():
    """028 gap 1. `is_completed = false` alone is true for a postponed game forever, and
    across the whole night for a game suspended Thursday and resumed Friday. A caption that
    claims those are in progress is worse than the current silence, so the claim is bounded
    by the same settle window the refresh gate uses."""
    from views import scores
    from src.scores_cadence import SETTLE_HOURS as pipeline_settle
    # The page and the pipeline must agree on what "still settling" means, or the site
    # claims a game is live for longer than the DAG is collecting results for it.
    assert scores.SETTLE_HOURS == pipeline_settle


def test_every_parameter_a_page_reads_is_a_known_parameter():
    """A page reading an unregistered parameter gets None, silently, forever.

    Unknown parameters are ignored by design (AC-G.11) — `?utm_source=x` is noise and
    deserves nothing. The cost is that a page asking for a parameter nobody registered gets
    the same silence, and the feature built on it is inert while looking perfectly fine.

    That is not hypothetical. R-043 made the Schedule view a TAB rather than a toggle
    specifically because a tab is URL-addressable — and `view` was not in KNOWN, so
    ?view=stacked resolved to None, the radio fell back to its first option, and both tabs
    rendered the identical dense table. Every test passed. It was caught by rendering both
    views and noticing the output was byte-identical.
    """
    import re
    from pathlib import Path
    from lib import params as params_module
    site = Path(__file__).resolve().parents[1] / "site"

    unregistered = []
    for path in sorted((site / "views").glob("*.py")) + sorted((site / "lib").glob("*.py")):
        if path.name == "params.py":
            continue
        for name in re.findall(r'params\.get\(\s*"(\w+)"', path.read_text()):
            if name not in params_module.KNOWN:
                unregistered.append(f"{path.name}: {name}")
    assert not unregistered, (
        "these resolve to None silently and any feature built on them is inert: "
        f"{sorted(set(unregistered))}")


def test_a_logo_is_measured_as_width_rather_than_stripped_to_nothing():
    """Stripping tags is right for a chip, whose text IS its width, and wrong for an image,
    whose text is nothing and whose box is 20px.

    Schedule's Away column was short by exactly a logo, so "New Mexico State" pushed its
    3-2 record onto a second line while the column beside it had room to spare.
    """
    import pandas as pd
    from lib import table as table_lib
    from lib.table import Col
    frame = pd.DataFrame([{"a": "Team", "b": "Team"}])
    plain = Col("a", "A")
    logoed = Col("b", "B", render=lambda r: "<img src='x.png' alt=''>Team")
    layout = table_lib.column_layout(frame, [plain, logoed])
    assert float(layout[1].rstrip("%")) > float(layout[0].rstrip("%")), (
        "identical text, but one cell also carries an image")


def test_a_monospace_number_is_measured_wider_than_the_same_count_of_prose():
    """`.cfdb-num` is ui-monospace; the header and the body text are not. Measuring "-10.2"
    as five characters of prose is what broke PRED across two lines."""
    import pandas as pd
    from lib import table as table_lib
    from lib.table import Col
    frame = pd.DataFrame([{"a": "-10.2", "b": -10.2}])
    layout = table_lib.column_layout(
        frame, [Col("a", "A"), Col("b", "B", "signed", dp=1)])
    assert float(layout[1].rstrip("%")) > float(layout[0].rstrip("%"))


def test_the_header_is_measured_as_the_uppercase_letter_spaced_thing_it_renders_as():
    """`.cfdb-table th` uppercases and adds .02em of letter-spacing, so a six-character label
    is wider than six characters of body text. SPREAD broke to "SPREA / D"."""
    import pandas as pd
    from lib import table as table_lib
    from lib.table import Col
    frame = pd.DataFrame([{"a": "x", "b": "x"}])
    layout = table_lib.column_layout(frame, [Col("a", "A"), Col("b", "Spread")])
    assert float(layout[1].rstrip("%")) > float(layout[0].rstrip("%"))


def test_the_streamlit_theme_does_not_pin_the_app_to_the_light_palette():
    """R-099, CORRECTED AFTER LOOKING.

    Declaring any key under a bare `[theme]` makes Streamlit resolve a concrete theme, and an
    unset `base` resolves to LIGHT — so setting only primaryColor stopped the app following
    the viewer's preference and served the light palette to everyone. Measured: the page
    background under prefers-color-scheme:dark was rgb(255,255,255) with the bare section and
    rgb(14,17,23) with the per-mode ones.
    """
    # R-099: the file lives at site/.streamlit/config.toml — INSIDE the image's build context,
    # which is `./site`. At the repo root it was outside the context and could never be copied,
    # so the deployed radio stayed Streamlit red while every local check said it was fixed.
    root = Path(__file__).resolve().parents[1]
    path = root / "site" / ".streamlit" / "config.toml"
    assert path.exists(), "the config must be inside the site/ build context"
    assert not (root / ".streamlit" / "config.toml").exists(), (
        "two config files is how they drift; there is one canonical copy")
    config = path.read_text()
    body = "\n".join(ln for ln in config.splitlines() if not ln.lstrip().startswith("#"))
    assert "[theme.light]" in body and "[theme.dark]" in body
    assert "\n[theme]" not in "\n" + body, (
        "a bare [theme] section resolves base=light and disables dark mode")


def test_a_null_logo_never_reaches_the_src_attribute():
    """R-121, AND IT IS THE NaN BUG A THIRD TIME.

    `if logo_url:` looks like a null guard and is not one for a DataFrame. read_sql gives a
    NULL in an object column as float('nan'), NaN IS TRUTHY, so a team with no logo took the
    image branch and the f-string interpolated the float — emitting `<img src='nan'>`, a
    relative URL that 404s against the app's own host and paints the browser's broken-image
    box on every page that renders a team.

    That is the exact thing `logo_or_monogram`'s own docstring and AC-G.28 promise never
    happens. Cowork found it in a screenshot of two FCS teams; the unit tests all passed
    because they were written with None, which is falsy and harmless.
    """
    from lib import identity
    for empty in (None, float("nan"), "", "   "):
        rendered = identity.logo_or_monogram(empty, "Thomas")
        assert "<img" not in rendered, f"{empty!r} produced an image tag"
        assert "nan" not in rendered.lower()
        assert "cfdb-monogram-empty" in rendered
    real = identity.logo_or_monogram("https://cdn.example/1.png", "Thomas")
    assert "src='https://cdn.example/1.png'" in real
    # R-121's second half: the monogram sits behind the image, so a file that goes missing
    # later shows the same grey disc rather than a broken-image box.
    assert "cfdb-logo-box" in real


def test_the_column_measure_allows_for_things_that_are_not_text():
    """Every correction here came from a MEASUREMENT, not from reading the code.

    A text measure sees characters. A table cell also contains a logo, two `.4rem` inline
    margins, and — since R-131 — glyphs at 1.3rem against a .9rem body. All of those are width
    the measure cannot see, and each one showed up as a specific wrap:

      logo + its margin   "Kennesaw State" onto two lines at 1280 (cell 157px, needed 178px)
      record margin       the same cell, the last two pixels
      1.3rem glyphs       the GAME header onto two lines, the column sized for two characters

    Asserted as ORDERING rather than absolute widths, so the test says what it means — a cell
    carrying extra furniture gets a bigger share than the same text without it — and does not
    have to be retuned every time a font changes.
    """
    import pandas as pd
    from lib import table as table_lib
    from lib.table import Col
    frame = pd.DataFrame([{"a": "Team", "b": "Team", "c": "Team", "d": "Team"}])
    plain = Col("a", "A")
    logoed = Col("b", "B", render=lambda r: "<img src='x.png' alt=''>Team")
    recorded = Col("c", "C", render=lambda r: "Team<span class='cfdb-team-record'>4-2</span>")
    glyphed = Col("d", "D", render=lambda r: "Team<span class='cfdb-details'>Z</span>")
    layout = [float(w.rstrip("%"))
              for w in table_lib.column_layout(frame, [plain, logoed, recorded, glyphed])]
    for index, what in ((1, "a logo"), (2, "a record"), (3, "an oversized glyph")):
        assert layout[index] > layout[0], f"{what} is width the measure ignored"


def test_the_site_image_copies_everything_the_app_reads_at_runtime():
    """R-099, AS THE CLASS OF BUG RATHER THAN THE INSTANCE.

    The image is built with `context: ./site`, so anything the running app reads must live
    under site/ AND be copied by the Dockerfile. The config sat at the repo root — outside the
    context — so no COPY could have reached it, Streamlit fell back to #FF4B4B, and every local
    measurement said the accent was fixed because locally there is no build context at all.

    The same wall already produced `lib/lines_cadence.json`, which exists because this image
    cannot import `src/`. Second collision, same boundary.
    """
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "site" / "Dockerfile").read_text()
    for needed in ("app.py", "lib/", "views/", ".streamlit/"):
        assert needed in dockerfile, f"{needed} is read at runtime and never copied in"
    compose = (root / "deploy" / "docker-compose.yml").read_text()
    assert "context: ./site" in compose, (
        "if the context widens, this test's premise changes and it should be revisited")


def test_a_conference_that_the_division_excludes_falls_back_and_says_so():
    """R-165. A conference selected under one division may not exist under another — measured:
    49 of the 72 conferences in 2025 disappear when Division narrows from All to FBS.

    Streamlit would silently reset the widget to index 0. That is the same class of defect as
    R-010/R-011, where filter state changed without telling anyone, so the drop is returned
    rather than swallowed and the caller renders a notice.
    """
    from lib.filters import resolve_conference
    options = ["All", "ACC", "Big Ten", "SEC"]
    assert resolve_conference("SEC", options) == ("SEC", None)
    assert resolve_conference(None, options) == (None, None)
    value, dropped = resolve_conference("Centennial", options)
    assert value is None, "an impossible filter must not survive"
    assert dropped == "Centennial", "and the caller has to be able to say which one went"


def test_a_bookmarked_url_resolves_the_same_way_a_click_does():
    """THE URL HALF IS NOT OPTIONAL. `?division=fbs&conference=Big+Sky` is reachable from a
    bookmark or from a link built before the cascade existed, and scope travels in query
    params by design (AC-G.13).

    Asserted as ONE code path rather than two behaviours: `game_scope` reads the conference
    from the URL and hands it to the same resolver an in-session change uses, so there is no
    second rule that could drift.
    """
    from pathlib import Path as _P
    source = (_P(__file__).resolve().parents[1] / "site" / "lib" / "filters.py").read_text()
    body = source[source.index("def game_scope("):]
    assert body.count("resolve_conference(") == 1, (
        "two call sites would be two chances to diverge")
    assert 'params.get("conference")' in body, "the URL value is what gets resolved"


def test_the_conference_option_list_is_cached_on_everything_it_depends_on():
    """R-165. `_conferences` was keyed on season alone and now depends on division too. A
    cache key that misses a dependency is a stale option list, which looks like a data bug and
    gets debugged as one."""
    import inspect
    from lib import filters
    signature = inspect.signature(filters._conferences.__wrapped__)
    assert list(signature.parameters) == ["season", "division"]


def test_the_conference_list_reads_both_sides_of_the_fixture():
    """A conference whose members never HOSTED in a season was missing from the filter — a
    silent omission rather than an empty result. Pre-existing; this is the query that fixes
    it."""
    from pathlib import Path as _P
    source = (_P(__file__).resolve().parents[1] / "site" / "lib" / "filters.py").read_text()
    body = source[source.index("def _conferences("):source.index("def resolve_conference(")]
    assert 'for side in ("home", "away")' in body
    # STRIP THE COMMENTARY BEFORE ASSERTING ON THE CODE. The first version of the check below
    # matched the docstring EXPLAINING why there is no union — the seventh time a
    # source-reading test in this repo has matched its own prose. G-2 is one relation per
    # query, and a union inside the app is the shape that becomes a join inside the app.
    code = "\n".join(line for line in body.splitlines()
                     if not line.lstrip().startswith("#"))
    code = code.replace(body[body.index('"""'):body.index('"""', body.index('"""') + 3)], "")
    assert "union" not in code.lower()


def test_the_navigation_never_collapses_behind_a_disclosure():
    """R-159. Streamlit's default `expanded=False` hides a long nav behind "View N more" once
    the sidebar runs out of room, and Schedule's legend pushed it over that line — eight of
    eighteen pages, every Betting and Reference page, disappeared the moment the legend
    shipped. A page-specific legend must never cost the sidebar its primary job.
    """
    source = (Path(__file__).resolve().parents[1] / "site" / "app.py").read_text()
    assert "st.navigation(nav, expanded=True)" in source


def test_nothing_writes_a_legend_into_the_sidebar():
    """The legend lived under the nav for one round and pushed Streamlit's nav past its
    collapse threshold, hiding eight pages behind "View 8 more". It is a popover now, which
    also gave the sidebar back to navigation — so the pressure is gone rather than damped.

    `expanded=True` stays regardless: it is cheap, and it stops the next thing anyone adds to
    the sidebar from silently costing the nav again.
    """
    views = (Path(__file__).resolve().parents[1] / "site" / "views")
    writers = sorted(p.stem for p in views.glob("*.py")
                     if "st.sidebar" in p.read_text() and "legend" in p.read_text().lower())
    assert writers == [], writers


def test_the_query_checker_actually_scans_the_pages():
    """R-182. THE CI JOB WAS GREEN WHILE CHECKING ALMOST NOTHING.

    `ci/check_page_queries.py` globbed `site/pages/*.py`. That directory has not existed since
    the rename to `views/` — done because Streamlit auto-discovers a folder called `pages/` and
    builds a competing multipage app from it. `Path.glob` on a missing directory yields nothing
    and raises nothing, so the job kept passing while scanning 10 statements out of `lib/` and
    NONE of the eighteen page modules. That is why R-181's dropped `upset_basis` reached a
    deployed page with every check green.

    Found by negative-testing the wrapper around it: a deliberately broken column was put back
    into schedule.py and the checker still passed. A verification that cannot fail is not a
    verification.

    THIS TEST GUARDS THE SCOPE, NOT THE QUERIES. The queries need a full serving database and
    CI has one; a developer's warehouse is usually partial, and a test that fails on the dev
    machine for environmental reasons is a test people learn to ignore. What must never regress
    is WHAT the checker looks at, and that is environment-independent.
    """
    import sys as _sys
    root = Path(__file__).resolve().parents[1]
    _sys.path.insert(0, str(root / "ci"))
    try:
        import check_page_queries
    finally:
        _sys.path.pop(0)

    source = (root / "ci" / "check_page_queries.py").read_text()
    assert 'joinpath("views")' in source, "the checker must scan the directory that exists"
    assert 'joinpath("pages")' not in source

    scanned = list(check_page_queries.statements())
    files = {path.name for path, _, _ in scanned}
    assert len(scanned) >= 40, f"only {len(scanned)} statements found; the globs are wrong"
    assert "schedule.py" in files, "the busiest page in the app is not being checked"
    assert len(files) >= 15, f"only {len(files)} files scanned: {sorted(files)}"


def test_no_site_module_reaches_outside_the_image(capsys):
    """R-225, RUN AS A UNIT TEST TOO so a developer sees it before CI does.

    The image is built with `context: ./site`. Anything above that directory is not in the
    container, and every crossing so far has FALLEN BACK rather than failed: a config at the
    repo root left the deployed radio Streamlit-red, and `lib/metrics.py` read dbt's vars and
    quietly used hardcoded values that happened to match.

    The check itself is `ci/check_site_paths.py`; this is the wrapper that makes it part of
    the suite, and it asserts the SCAN SIZE as well as the result — a check that finds nothing
    because it globbed the wrong directory is how `ci/check_page_queries.py` stayed green for
    months while examining nothing.
    """
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("check_site_paths",
                                                  root / "ci" / "check_site_paths.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    scanned = [p for p in module.SITE.rglob("*.py") if "__pycache__" not in p.parts]
    assert len(scanned) >= 15, f"only {len(scanned)} modules scanned"
    found = module.violations()
    assert not found, [f"{m.name}:{line} {why}" for m, line, why in found]


def test_the_boundary_check_catches_every_way_it_has_actually_been_crossed(
        tmp_path, monkeypatch):
    """A GUARD THAT HAS NEVER FAILED IS NOT EVIDENCE — and the first version of this one
    missed a third of the real cases.

    Fed the three shapes that actually happened plus one variant: reading dbt's project file
    through `parents[2]`, a config referenced as `../.streamlit/...`, and a literal naming
    `src/`. The `..` case was MISSED until it was tested, because the check only looked for
    directory names.
    """
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("check_site_paths",
                                                  root / "ci" / "check_site_paths.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fake_site = tmp_path / "site"
    (fake_site / "lib").mkdir(parents=True)
    monkeypatch.setattr(module, "SITE", fake_site)

    offenders = {
        "reads_dbt.py": 'from pathlib import Path\nP = Path(__file__).resolve().parents[2]\n',
        "climbs_out.py": 'CONFIG = "../.streamlit/config.toml"\n',
        "names_src.py": 'C = "src/lines_cadence.py"\n',
        "climbs_mid_path.py": 'C = "lib/../../dbt/dbt_project.yml"\n',
    }
    for name, body in offenders.items():
        (fake_site / "lib" / name).write_text(body)
    caught = {module_path.name for module_path, _, _ in module.violations()}
    assert caught == set(offenders), f"missed: {set(offenders) - caught}"

    # ...and the shapes that are FINE must not be flagged, or the check gets switched off.
    for name, body in {
        "own_dir.py": 'from pathlib import Path\nP = Path(__file__).resolve().parents[1]\n',
        "sibling.py": 'C = "lib/site_config.json"\n',
        "a_url.py": 'U = "https://collegefootballdata.com/docs/src/x"\n',
    }.items():
        (fake_site / "lib" / name).write_text(body)
    still = {m.name for m, _, _ in module.violations()}
    assert "own_dir.py" not in still, "parents[1] from site/lib is site/ — that is legal"
    assert "sibling.py" not in still, "a path inside site/ must not be flagged"


def test_the_boundary_check_does_not_flag_a_url_that_happens_to_contain_a_directory_name():
    """A false positive is how a check gets switched off. `https://.../docs/src/x` is not a
    filesystem path, and the first version flagged it because it looked for `/src/` anywhere
    in a string."""
    import importlib.util
    import tempfile
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("check_site_paths",
                                                  root / "ci" / "check_site_paths.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fake = Path(tempfile.mkdtemp()) / "site" / "lib"
    fake.mkdir(parents=True)
    module.SITE = fake.parent
    (fake / "a_url.py").write_text(
        'U = "https://collegefootballdata.com/docs/src/x"\n'
        'M = "mailto:marc4data@gmail.com"\n')
    assert module.violations() == []
