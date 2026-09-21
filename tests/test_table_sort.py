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
    # ⚠️ THE PROPERTY, NOT THE CALL TEXT — A189. This asserted the literal
    # `apply_sort(df, columns)` and went red when that call gained the table key
    # (cfdb-main-R-1925), which is a strengthening of the very thing it guards. A source test
    # matching an exact call signature breaks on every improvement to that call; what has to
    # hold is that `render` sorts rather than leaving it to the caller.
    assert 'sortable is True' in source and 'apply_sort(' in source, (
        "render must apply the sort itself; the separate call is what eleven views forgot")
    assert 'df = apply_sort(' in source, (
        "render must assign the sorted frame back, or it sorts a copy and draws the original")
    assert 'sortable = False' in source, (
        "render must also stop DRAWING the links whenever it will not sort")


# --- A178: which way a column OPENS (cfdb-main-R-1850 / cfdb-main-R-1851) -------------------

def _first_href(stub, label):
    """The URL the header for `label` would send a cold reader to."""
    html = stub.markup[-1]
    head = html[:html.index("<tbody>")]
    match = re.search(r"<a class='cfdb-sort' href='([^']+)'[^>]*>" + label, head)
    assert match, f"no sort link for {label!r} in\n{head}"
    return match.group(1)


def test_a_measure_opens_descending_and_a_name_still_opens_ascending(table_module):
    """🚨 cfdb-main-R-1850.

    > **MARC, v10:** *"When I choose a column header to force a sort, it shift to sort asc, but
    > end-user will generally want to see the best performers for the metric (desc). Can you
    > make desc the first sort."*

    ⚠️ AND IT IS PER COLUMN, NOT ONE CONSTANT. `table.render` is the site's only table
    producer, so a global flip reaches Schedule, Scores, Standings, Rankings, every Team tab,
    every Matchup table and every Leaderboard at once.
    """
    table, stub = table_module
    # ⚠️ `squad`, not `team`: `_header_cell` refuses a sort link on a hand-listed set of
    # synthetic field names — `team`, `rank`, `record`, `winner` and a dozen more — because
    # those columns render something the frame has no single field for. A fixture using one
    # of them tests the exclusion list, not the opening direction.
    columns = [table.Col("squad", "Squad"), table.Col("yards", "Yards", "num", dp=0)]
    frame = _frame().rename(columns={"team": "squad"})

    stub.query_params = {}
    table.render(frame, columns)

    assert "order=desc" in _first_href(stub, "Yards"), (
        "a numeric measure must open on its best performers")
    assert "order=asc" in _first_href(stub, "Squad"), (
        "a name has no best end — it reads from the top down")


def test_clicking_the_active_column_still_toggles_both_ways(table_module):
    """⚠️ MARC ASKED FOR A BETTER STARTING POINT, NOT FOR THE TOGGLE TO GO. A change that made
    a measure *always* sort descending would satisfy the sentence above and take away the
    control — and every assertion about the opening direction would still pass.
    """
    table, stub = table_module

    stub.query_params = {"sort": "yards", "order": "desc"}
    table.render(_frame(), _columns(table))
    assert "order=asc" in _first_href(stub, "Yards"), (
        "the active column must offer the other direction")

    stub.query_params = {"sort": "yards", "order": "asc"}
    table.render(_frame(), _columns(table))
    assert "order=desc" in _first_href(stub, "Yards")


def test_a_rank_column_opens_ascending_because_one_is_best(table_module):
    """🚨 cfdb-main-R-1850. THE COLUMN THAT MAKES `kind` INSUFFICIENT.

    📊 Measured across the site: of 193 `Col` call sites, FOUR ranks carry `kind="num"` —
    `ap_rank`, `coaches_rank` and `committee_rank` on Rankings, `tiebreak_rank` on Standings.
    **Defaulting every number to `desc` and stopping there would open the Rankings page on the
    136th-best team in the country**, which is the opposite of what Marc asked for.
    """
    table, stub = table_module
    # `ap_rank`, which is the real field name on the Rankings page — `rank` alone is on
    # `_header_cell`'s synthetic-field exclusion list and would draw no link at all.
    columns = [table.Col("squad", "Squad"),
               table.Col("ap_rank", "AP", "num", dp=0, opens="asc"),
               table.Col("yards", "Yards", "num", dp=0)]
    frame = _frame().rename(columns={"team": "squad"}).assign(ap_rank=[3, 1, 2])

    stub.query_params = {}
    table.render(frame, columns)
    assert "order=asc" in _first_href(stub, "AP"), "1 is the best rank"
    assert "order=desc" in _first_href(stub, "Yards"), "and the measure beside it is unchanged"


def test_no_column_on_the_site_opens_a_rank_at_its_worst_end():
    """🚨 THE GUARD FOR THE CLASS, NOT FOR THE FOUR. A rank added tomorrow with `kind="num"`
    and no `opens=` would silently open on last place, and nothing on the page would look
    wrong — the header draws, the link works, the rows sort. This reads every `Col` on the
    site by AST and refuses that.

    ⚠️ BY AST, NOT BY GREP: this codebase's prose about `Col` outnumbers its calls, and a
    `grep -c` here has been wrong three times (2.2.1c.1).
    """
    import ast

    offenders = []
    for path in sorted(SITE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            if (getattr(node.func, "attr", None)
                    or getattr(node.func, "id", None)) != "Col":
                continue
            args = [a.value if isinstance(a, ast.Constant) else None for a in node.args]
            kw = {k.arg: (k.value.value if isinstance(k.value, ast.Constant) else None)
                  for k in node.keywords}
            field = args[0] if args else kw.get("field")
            label = args[1] if len(args) > 1 else kw.get("label")
            kind = args[2] if len(args) > 2 else kw.get("kind", "text")
            opens = kw.get("opens") or ("desc" if kind in ("num", "signed") else "asc")
            looks_like_a_rank = any(
                "rank" in str(v).lower() for v in (field, label) if v is not None)
            if looks_like_a_rank and opens == "desc":
                offenders.append(f"{path.name}:{node.lineno} {field!r} ({label!r})")

    assert not offenders, (
        "these columns read as a rank and would open on their WORST end — give them "
        "opens='asc':\n  " + "\n  ".join(offenders))


# --- A189: one table's sort must not move another (cfdb-main-R-1925) ------------------------

def _other_columns(table):
    """A DIFFERENT table that happens to share a column name — the collision in the wild."""
    return [table.Col("team", "Squad"), table.Col("yards", "Getting", "num", dp=0),
            table.Col("extra", "Extra")]


def test_a_sort_aimed_at_one_table_leaves_the_others_alone(table_module):
    """🚨 MEASURED ON THE REAL PAGE BEFORE IT WAS FIXED — A189, Today, week 3 2026.

    `?sort=` was page-wide, so any table carrying a column of that name re-sorted. **Biggest
    upsets** and **Biggest underdog covers** both have a `spread` column and sit directly above
    one another; clicking *"Getting"* on the covers table set `?sort=spread` and silently
    re-ordered the upsets panel. Texas A&M at 84.1% fell from first to below Wyoming at 47.8%
    **while the caption still said the panel was ranked by the loser's win probability** —
    a true-sounding label on a different order, which is §4.3's worst form and exactly what
    Marc reported.

    ⚠️ THE TWO TABLES SHARE AN ANCHOR, which is why the fix keys on the COLUMN SHAPE. Keying on
    the anchor would have left the only two tables that actually collided still colliding.
    """
    table, stub = table_module
    frame, mine, theirs = _frame(), _columns(table), _other_columns(table)

    # the key the OTHER table's header would put in the URL
    other_key = table.table_key(theirs)
    my_key = table.table_key(mine)
    assert other_key != my_key, "two different column shapes must not share a sort key"

    stub.query_params = {"sort": f"{other_key}.team", "order": "asc"}
    table.render(frame, mine)
    assert _rendered_order(stub) == ["Cobras", "Aardvarks", "Badgers"], (
        "a sort addressed to another table re-ordered this one — that is the defect")
    assert "cfdb-sorted" not in stub.markup[-1], (
        "and it must not light this table's arrow either")

    # ...while its OWN key still sorts it
    stub.query_params = {"sort": f"{my_key}.team", "order": "asc"}
    table.render(frame, mine)
    assert _rendered_order(stub) == ["Aardvarks", "Badgers", "Cobras"], (
        "a table must still sort when the sort is addressed to it")


def test_the_sort_link_names_its_own_table(table_module):
    """The other half: a header must WRITE the scoped form, or nothing above holds in a browser."""
    table, stub = table_module
    stub.query_params = {}
    table.render(_frame(), _columns(table))
    links = re.findall(r"<a class='cfdb-sort' href='([^']*)'", stub.markup[-1])
    assert links, "no sort links drawn"
    key = table.table_key(_columns(table))
    for href in links:
        assert f"sort={key}." in href.replace("%2E", "."), (
            f"the sort link is not scoped to this table: {href}")


def test_a_bare_sort_param_still_works_for_the_table_that_owns_it(table_module):
    """⚠️ AC-G.11 — an old bookmark or hand-edited URL carries `?sort=team` with no table key.

    Dropping it silently would make a shared link stop working with no explanation. It is
    honoured by any table that has the column, which is the pre-A189 behaviour and is the safe
    direction: no link this module DRAWS can produce the bare form any more.
    """
    table, stub = table_module
    stub.query_params = {"sort": "team", "order": "asc"}
    table.render(_frame(), _columns(table))
    assert _rendered_order(stub) == ["Aardvarks", "Badgers", "Cobras"]
