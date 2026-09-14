"""The browser tab says where you are — `M4D · <Page Name>`, plus a suffix where there is one.

Marc, 2026-09-14, and A130 built it: `lib/tab.py` and the two call sites in `site/app.py`
and `site/views/today.py`.

🚨 WHAT THESE GUARDS ARE AIMED AT, BECAUSE R-843 IS THE TRAP HERE AND IT IS A SHARP ONE.
`app.py` sets a STATIC FALLBACK — `M4D` — before routing, deliberately, so a page whose title
cannot be resolved still has a real title. **That fallback is a perfectly good string.** So an
assertion of the shape *the tab is non-empty*, *the tab starts with M4D*, or *set_page_config
was called* PASSES with the entire per-page mechanism deleted. Every assertion below pins a
string the fallback CANNOT produce — one containing a page name.

⚠️ AND `test_the_routed_page_reaches_the_tab` EXECUTES `app.py` rather than reading it. A
source-text assertion would survive `st.navigation(...)` being re-wired to something that no
longer routes, which is the change most likely to break this by accident.
"""
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))


@pytest.fixture()
def tab():
    from lib import tab as module
    return module


# --- the string itself -------------------------------------------------------------------

def test_the_tab_reads_brand_page_and_suffix(tab):
    """The whole ask, pinned as one literal. Marc named every part of this string."""
    assert tab.compose("Matchup", "USM @ AUB") == "M4D · Matchup · USM @ AUB"
    assert tab.compose("Today") == "M4D · Today"


def test_the_brand_replaced_cfdb_and_the_descriptor_became_the_page_name(tab):
    """The retired title was `cfdb — college football data`. Neither half may come back.

    `cfdb` IS NOT RENAMED as a project — it is the repo, the database and the `srv_` prefix.
    This asserts about the TAB only, which is the only place the rename applies.
    """
    rendered = tab.compose("Schedule")
    assert "cfdb" not in rendered
    assert "college football data" not in rendered
    assert rendered.startswith("M4D")


def test_a_missing_part_is_dropped_rather_than_rendered_as_an_empty_segment(tab):
    """Every part is optional because every part can really be missing — see `teams_suffix`.

    The failure this stops is `M4D ·  · `, which is what a naive join produces and which at
    tab width reads as a rendering fault rather than as an absent value.
    """
    assert tab.compose(None, None) == "M4D"
    assert tab.compose("", "   ") == "M4D"
    assert tab.compose(None, "USM @ AUB") == "M4D · USM @ AUB"


# --- the Matchup suffix, from published columns ------------------------------------------

def _game_row(**overrides):
    """A row shaped like `srv_game`, which is what `matchup.py` already has in hand."""
    row = {"away_abbreviation": "USM", "away_team": "Southern Miss",
           "home_abbreviation": "AUB", "home_team": "Auburn"}
    row.update(overrides)
    return pd.Series(row)


def test_the_suffix_reads_the_published_abbreviation(tab):
    assert tab.teams_suffix(_game_row()) == "USM @ AUB"


def test_a_null_abbreviation_falls_back_to_the_published_team_name(tab):
    """⚠️ MEASURED IN SERVING, NOT ASSUMED: `away_abbreviation` is null on 12,018 of 112,675
    rows of `srv_game` (10.7%), and on 136 rows of the 2026 season. The fallback chain is the
    one `matchup.py` already uses for its own labels — abbreviation, then the full name."""
    assert tab.teams_suffix(_game_row(away_abbreviation=None)) == "Southern Miss @ AUB"
    assert tab.teams_suffix(_game_row(home_abbreviation=float("nan"))) == "USM @ Auburn"


def test_a_side_with_no_usable_name_drops_the_whole_suffix(tab):
    """🚨 NEVER `None @ AUB`. A half-built suffix is worse than none: it reads as a team."""
    assert tab.teams_suffix(_game_row(away_abbreviation=None, away_team=None)) is None
    assert tab.teams_suffix(pd.Series({"home_abbreviation": "AUB"})) is None
    assert tab.teams_suffix(None) is None


def test_the_string_none_is_not_a_team(tab):
    """A null that has already been through `str()` upstream arrives as the text `None`."""
    assert tab.teams_suffix(_game_row(away_abbreviation="None", away_team="nan")) is None


# --- the contract with Streamlit ---------------------------------------------------------

def _capture(monkeypatch, tab):
    """Record what `set_title` hands to `st.set_page_config`."""
    seen = []
    monkeypatch.setattr(tab.st, "set_page_config", lambda **kw: seen.append(kw))
    return seen


def test_set_title_never_passes_page_icon(tab, monkeypatch):
    """❌ THE FOOTBALL IS NOT IN THE ASK AND MUST NOT MOVE. `app.py` sets `page_icon` once;
    omitting it here leaves the favicon untouched — measured byte-identical across the second
    call in Chromium. Passing it from here would be the round quietly changing an icon."""
    seen = _capture(monkeypatch, tab)
    tab.set_title("Scores", "anything")
    assert seen == [{"page_title": "M4D · Scores · anything"}]
    assert "page_icon" not in seen[0]


def test_set_title_for_reads_the_page_name_from_the_registry(tab, monkeypatch):
    """No second list of page names. The tab and the sidebar cannot disagree."""
    seen = _capture(monkeypatch, tab)
    tab.set_title_for("matchup", "USM @ AUB")
    tab.set_title_for("today")
    assert [kw["page_title"] for kw in seen] == ["M4D · Matchup · USM @ AUB", "M4D · Today"]


def test_an_unknown_key_degrades_to_the_brand_rather_than_raising(tab, monkeypatch):
    seen = _capture(monkeypatch, tab)
    tab.set_title_for("no-such-page")
    assert seen == [{"page_title": "M4D"}]


def test_a_streamlit_that_refuses_the_second_call_cannot_break_a_page(tab, monkeypatch):
    """🚨 THE ACCEPTANCE CRITERION IS NOT *the title changes*. IT IS *the page still renders
    when the title does not*.

    Streamlit raised `StreamlitAPIException` on a repeat `set_page_config` for years, and a
    future pin may again. Unguarded, that exception leaves a page body and is caught by
    `states.section`, which draws the Error card naming the page's DATASET — a confident,
    false and highly visible message about a cosmetic string."""
    def refuse(**kwargs):
        raise RuntimeError("set_page_config() can only be called once per app page")

    monkeypatch.setattr(tab.st, "set_page_config", refuse)
    tab.set_title("Scores", "USM @ AUB")          # must not raise
    tab.set_title_for("matchup")                  # must not raise


# --- the wiring, INVOKED rather than read ------------------------------------------------

def test_the_routed_page_reaches_the_tab():
    """🚨 THE ONE THAT CATCHES THE WIRING BEING REMOVED, AND IT RUNS `app.py` TO DO IT.

    `st.navigation` is stubbed to route to Matchup; the assertion is that the tab ends up
    saying `Matchup`. The static fallback is `M4D`, so deleting `tab.set_title(page.title)`
    from `app.py` moves this value — which is the whole of R-843: a pin that the break cannot
    move is not a pin.

    ⚠️ `_RELOAD` IS THE MECHANISM test_today_page.py, test_matchup_drives.py AND
    test_view_columns.py ALREADY USE (R-447). Every module binds `streamlit` at ITS first
    import and never looks again, and `test_site_foundation.py` imports every view against
    the real module and sorts first — so swapping `sys.modules` without reloading is a no-op
    that leaves the test passing for the wrong reason.
    """
    import importlib

    seen = []
    routed = types.SimpleNamespace(title="Matchup", url_path="matchup", run=lambda: None)

    stub = types.ModuleType("streamlit")
    stub.set_page_config = lambda **kw: seen.append(kw.get("page_title"))
    stub.markdown = lambda *a, **k: None
    stub.Page = lambda fn, title=None, url_path=None, default=False: types.SimpleNamespace(
        title=title, url_path=url_path, run=lambda: None)
    stub.navigation = lambda nav, expanded=True: routed

    saved = sys.modules.get("streamlit")
    sys.modules["streamlit"] = stub
    try:
        for name in ("lib.tab", "lib.theme"):
            importlib.reload(importlib.import_module(name))
        assert sys.modules["lib.tab"].st is stub, "lib.tab is not talking to the stub"
        source = compile((SITE / "app.py").read_text(), str(SITE / "app.py"), "exec")
        exec(source, {"__name__": "__main__", "__file__": str(SITE / "app.py")})
    finally:
        if saved is not None:
            sys.modules["streamlit"] = saved
        else:                                        # pragma: no cover - defensive
            del sys.modules["streamlit"]
        for name in ("lib.tab", "lib.theme"):
            importlib.reload(importlib.import_module(name))

    assert seen, "app.py never called set_page_config"
    assert seen[0] == "M4D", f"the static fallback changed: {seen[0]!r}"
    assert seen[-1] == "M4D · Matchup", (
        "the routed page's name never reached the tab — app.py set "
        f"{seen[-1]!r}, which is what it would say with the per-page call deleted")
