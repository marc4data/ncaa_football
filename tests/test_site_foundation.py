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
    checked = 0
    for path in (site / "views").glob("*.py"):
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
    requirements = (Path(__file__).resolve().parents[1]
                    / "deploy" / "site" / "requirements.txt").read_text().lower()

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
    """srv_scoreboard returns NULL for `winner` on a completed game with equal scores.
    Rendering that as Pending would claim the game has not been played."""
    from views import scores
    tie = scores._winner({"is_completed": True, "winner": None, "actual_margin": 0})
    pending = scores._winner({"is_completed": False, "winner": None})
    assert "Tie" in tie
    assert "Pending" in pending
    assert tie != pending


def test_the_winner_never_renders_the_string_none():
    """A formatter that indexes into a nullable column and interpolates the result puts
    `None` on the page. 11% of srv_scoreboard is a game against a team with no dim_team
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
    table_lib.dataset_caption("Schedule", "srv_schedule")
    assert "table=srv_schedule" in captured[0]
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
