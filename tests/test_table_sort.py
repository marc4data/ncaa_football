"""cfdb-main-R-948 — the sort headers that drew a link and sorted nothing.

Marc, three times under three different sections of his 2026-09-16 notes:

    "Column sort isn't working.  The whole page reloads and end-user has to scroll down to get
     to the same page s/he clicked from."

🚨 A PRESENCE ASSERTION CANNOT SEE THIS DEFECT, WHICH IS WHY IT SURVIVED ELEVEN VIEWS. The
header renders. The link renders. The URL changes. The page reloads. Everything is present and
nothing is sorted — `table.render` drew the links and `table.apply_sort` was a separate call the
view had to remember, and eleven of sixteen did not.

✅ SO EVERY TEST HERE ASSERTS THE ORDER OF THE ROWS, on a frame whose ARRIVAL order is not its
sorted order. A fixture already in sorted order would pass against a `render` that sorts nothing
— R-744's family, and the whole reason this defect lasted.
"""
import importlib
import re
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VIEWS = SITE / "views"

_RELOAD = ("lib.params", "lib.table")


class _Stub(types.ModuleType):
    """Streamlit, reduced to what a table needs: query params in, markup out."""

    def __init__(self):
        super().__init__("streamlit")
        self.query_params = {}
        self.markup = []
        self.session_state = {}

    def markdown(self, body, **kwargs):
        self.markup.append(body)

    def caption(self, *a, **k):
        pass

    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture
def table_module():
    """`lib.table` bound to a stub, and PUT BACK afterwards.

    ⚠️ THE RESTORE IS BY HAND AND IT IS THE POINT — leaving a stub bound into `lib.params` is a
    defect this suite has already paid for once (test_matchup_drives.py's first version).
    """
    added = str(SITE) not in sys.path
    if added:
        sys.path.insert(0, str(SITE))
    real = sys.modules.get("streamlit")
    stub = _Stub()
    sys.modules["streamlit"] = stub
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))
    table = sys.modules["lib.table"]

    yield table, stub

    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))
    if added:
        sys.path.remove(str(SITE))


def _frame():
    """A frame whose ARRIVAL order is deliberately not its sorted order.

    🚨 THIS IS THE FIXTURE DECISION THE ROUND TURNS ON. Today's tables arrive in
    `MOST_EXCITING_ORDER`, which is not alphabetical and not by any single column a reader
    clicks — so a fixture already sorted by the test's own key would pass against a `render`
    that never sorts, and prove nothing.
    """
    return pd.DataFrame([
        {"team": "Cobras", "yards": 250},
        {"team": "Aardvarks", "yards": 410},
        {"team": "Badgers", "yards": 120},
    ])


def _columns(table):
    return [table.Col("team", "Team"), table.Col("yards", "Yards", "num", dp=0)]


def _rendered_order(stub, field="team"):
    """The values of the first column, in the order the table actually emitted them."""
    html = stub.markup[-1]
    body = html[html.index("<tbody>"):]
    return re.findall(r"<td[^>]*>([A-Za-z]+)</td>", body)


# --- the defect itself --------------------------------------------------------------------

def test_a_sort_param_actually_reorders_the_rows(table_module):
    """🚨 cfdb-main-R-948. The one assertion eleven views could not have passed.

    ⚠️ BOTH DIRECTIONS ARE ASSERTED because a fix for one alone produces the other: a `render`
    that always sorts ascending would pass the first half and fail the second.
    """
    table, stub = table_module
    frame, columns = _frame(), _columns(table)

    stub.query_params = {}
    table.render(frame, columns)
    assert _rendered_order(stub) == ["Cobras", "Aardvarks", "Badgers"], (
        "with no ?sort= the frame's own order must survive — the SQL's ORDER BY is the default")

    stub.query_params = {"sort": "team", "order": "asc"}
    table.render(frame, columns)
    assert _rendered_order(stub) == ["Aardvarks", "Badgers", "Cobras"], (
        "the sort header changed the URL and the rows did not move — that is the defect")

    stub.query_params = {"sort": "team", "order": "desc"}
    table.render(frame, columns)
    assert _rendered_order(stub) == ["Cobras", "Badgers", "Aardvarks"]

    stub.query_params = {"sort": "yards", "order": "asc"}
    table.render(frame, columns)
    assert _rendered_order(stub) == ["Badgers", "Cobras", "Aardvarks"], (
        "a numeric column must sort numerically, not by its rendered string")


def test_the_header_offers_only_what_the_table_will_do(table_module):
    """⚠️ THE LINKS AND THE SORT ARE SUPPRESSED ON THE SAME CONDITION, which is what makes a
    live-looking dead control impossible rather than unlikely.

    A control that answers a click, costs a full page reload and changes nothing is the class
    `params.py` already recorded on `?view=stacked`: *"the feature was inert and looked fine"*
    (R-043).
    """
    table, stub = table_module
    frame, columns = _frame(), _columns(table)

    stub.query_params = {"sort": "team", "order": "asc"}
    table.render(frame, columns, sortable=False)
    assert "cfdb-sort" not in stub.markup[-1], "sortable=False must draw no sort links"
    assert _rendered_order(stub) == ["Cobras", "Aardvarks", "Badgers"], (
        "sortable=False must not sort either — the two have to agree")

    table.render(frame, columns)
    assert "cfdb-sort" in stub.markup[-1], "a sortable table draws its links"


def test_a_table_with_one_row_offers_no_sort_at_all(table_module):
    """A sort link on a one-row table is a control that cannot change anything, and a per-view
    list of which tables are one-row is a list that goes stale. The frame answers it.
    """
    table, stub = table_module
    stub.query_params = {"sort": "team", "order": "asc"}
    table.render(_frame().head(1), _columns(table))
    assert "cfdb-sort" not in stub.markup[-1], (
        "a single row cannot be reordered, so the header must not offer to")


def test_an_unknown_sort_column_is_ignored_rather_than_raising(table_module):
    """AC-G.11 — a stale or hand-edited `?sort=` names a column this table does not have. That
    is noise, not a request, and it must not take the page down.
    """
    table, stub = table_module
    stub.query_params = {"sort": "not_a_column", "order": "asc"}
    table.render(_frame(), _columns(table))
    assert _rendered_order(stub) == ["Cobras", "Aardvarks", "Badgers"]


def test_a_sort_keeps_the_tab_it_was_clicked_from(table_module):
    """⚠️ A SORT THAT LANDED THE READER ON A DIFFERENT TAB WOULD LOOK EXACTLY LIKE "sorting
    doesn't work", which is what Marc reported. `tab` is in `params.SLUG_PARAMS` and
    `link_here` keeps every known parameter — this is a regression guard, not a suspicion.
    """
    table, stub = table_module
    stub.query_params = {"tab": "results", "season": "2026", "week": "2"}
    table.render(_frame(), _columns(table))
    links = re.findall(r"<a class='cfdb-sort' href='([^']*)'", stub.markup[-1])
    assert links, "the table drew no sort links at all"
    for href in links:
        assert "tab=results" in href, f"the sort link drops the tab: {href}"
        assert "season=2026" in href and "week=2" in href, (
            f"the sort link drops the reader's scope: {href}")


# --- the default, and the one view allowed to opt out -------------------------------------

def _view_sources():
    return {path.stem: path.read_text()
            for path in sorted(VIEWS.glob("*.py")) if not path.stem.startswith("_")}


def test_only_scores_applies_its_own_sort(table_module):
    """🚨 THIS IS WHAT MAKES A DOUBLE SORT IMPOSSIBLE RATHER THAN MERELY HARMLESS.

    `render` applies the sort now, so a view that also calls `apply_sort` would sort twice. It
    happens to be idempotent — same key, same stable mergesort — but "harmless" is not the bar
    the charter sets.

    ✅ `scores.py` IS THE ONE EXCEPTION AND IT IS NOT A PREFERENCE: `_pairs_only` computes its
    row cap from the SORTED order so the cut never falls inside a game's two rows, and the
    column widths are measured from the same frame. It declares `sortable="applied"`, which
    tells `render` to draw the links and leave the order alone.

    ⚠️ A FUTURE VIEW THAT ADDS AN `apply_sort` CALL TRIPS THIS TEST AND HAS TO JUSTIFY ITSELF,
    which is the point — the third state must not spread by imitation.
    """
    callers = {stem for stem, body in _view_sources().items() if "apply_sort(" in body}
    assert callers == {"scores"}, (
        f"views calling apply_sort: {sorted(callers)}. `table.render` applies the sort now; a "
        f"view that also calls it sorts twice. If a view genuinely needs the sorted frame "
        f"before it renders, it must pass sortable='applied' and be named here with the reason")

    scores = _view_sources()["scores"]
    assert 'sortable="applied"' in scores, (
        "scores.py sorts its own frame and must tell render not to sort it again")


def test_no_view_silently_opts_out_of_drawing_what_it_will_not_do(table_module):
    """⚠️ `sortable=False` IS ALLOWED AND IS NOT A SMELL — it is the honest state for a table
    whose order is the content. What must not exist is the third combination: a view that draws
    links and suppresses the sort.

    There is no way to express that any more — `render` derives both from the same value — so
    this asserts the shape of the parameter rather than a list of views, which cannot go stale.
    """
    table, _stub = table_module
    import inspect
    source = inspect.getsource(table.render)
    assert 'sortable is True' in source and 'apply_sort(df, columns)' in source, (
        "render must apply the sort itself; the separate call is what eleven views forgot")
    assert 'sortable = False' in source, (
        "render must also stop DRAWING the links whenever it will not sort")
