"""The shared Streamlit render harness (R-480 / R-631). ONE implementation, for both sessions.

🚨 THIS PATTERN HAS BEEN RE-IMPLEMENTED FIVE TIMES — A087, A088, A089, B082, A093 — and each
round rebuilt a stub from scratch. A093 had to repair one that could not model nested columns.
R-480's original complaint is that nothing in this project calls a page's `render()`; the reason
nobody fixed it is that a stub is easy to write badly and the badness is invisible.

⚠️ WHERE IT LIVES, AND WHY HERE. `tests/`, because it is test infrastructure and NOT `site/lib/`
— nothing shipped in the site image should import it. `tests/` carries a conftest.py, so pytest
puts this directory on sys.path and any test in either worktree can `import render_harness`. A
script outside pytest adds `sys.path.insert(0, "tests")` and does the same. 🚨 IF SESSION B
CANNOT IMPORT IT, IT IS THE SIXTH IMPLEMENTATION RATHER THAN THE LAST ONE.

── EVERY REQUIREMENT BELOW WAS EARNED BY A SPECIFIC FAILURE ─────────────────────────────────

1. 🚨 AN UNKNOWN `st.*` RAISES, FROM BaseException. A085's stub omitted `line_chart` — the
   page's only chart call — and the resulting AttributeError was caught by `states.section` and
   rendered as an Error state. The harness gap was INDISTINGUISHABLE FROM A PAGE DEFECT: it cost
   a merged false finding, a queue-jumped round, and the whole of A086's first phase.
   `HarnessGap` derives from BaseException so `except Exception` cannot swallow it.

2. ⚠️ DUNDERS ARE EXEMPT, AND THIS ONE HID ITS OWN EVIDENCE. B082: pytest reads `__file__` on a
   module WHILE FORMATTING A FAILURE, so raising on it turned a red test into `INTERNALERROR`
   and the report of the break was replaced by a crash in the reporter.

3. ⚠️ NESTED COLUMNS ARE MODELLED, NOT RECORDED. A093's legend nests `st.columns(2)` inside a
   column. A generic recorder returns None, `zip(None, …)` raises, and the page looks broken for
   a reason that is the harness's.

4. ⚠️ `assert_captured` EXISTS BECAUSE A SILENT ABSENCE READS AS A PASS. A091 asserted
   `"cfdb-legend" in html` before printing anything, after B079's lesson that an empty capture
   looks exactly like a clean render.

5. ⚠️ `PROVIDED` IS A NAMED LIST. A gap should be legible rather than latent, and the list is
   what a session quotes in its report.
"""
import contextlib
import importlib
import json
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class HarnessGap(BaseException):
    """NOT an Exception — so no page-level `except Exception` can swallow it.

    ⚠️ That is the whole point. `states.section` catches Exception to turn a fault into an Error
    state; a harness gap must escape that, or it renders AS the page and costs a round.
    """


# Every Streamlit method this harness knowingly provides. Anything else is a GAP, loudly.
PROVIDED = (
    "subheader caption markdown write text code title header divider "
    "info warning error success toast badge "
    "dataframe table json latex image html page_link "
    "line_chart bar_chart area_chart scatter_chart altair_chart plotly_chart "
    "vega_lite_chart pyplot graphviz_chart pydeck_chart map "
    "rerun stop set_page_config navigation Page"
).split()

_FALSE_WIDGETS = ("button form_submit_button link_button download_button "
                  "checkbox toggle").split()
_CONTAINERS = "container expander spinner form empty status popover".split()


class Charts:
    """The chart specs a render produced — SERIALISED ON FIRST READ, not at draw time.

    🚨 R-614's REAL COST, MEASURED, AND IT IS NOT WHAT THE PROMPT EXPECTED. B094 moved seven
    files onto this harness and the nine matchup files went 9.9s -> 16.3s. Cowork's premise was
    that reloading fifteen modules in `RELOAD` was the expense. It is not:

        a full fixture enter+exit          5.1 ms  -> ~1.2 s across all 236 harness tests
        cutting RELOAD to six modules      saves 3.8 ms an enter, so ~0.9 s at best
                                           AND BREAKS 13 TESTS: lib.query and lib.params are
                                           load-bearing, and without lib.query the stub's
                                           cache_resource is gone and the suite reaches a real
                                           database

    ⚠️ LOCALISED PER FILE, INTERLEAVED THREE TIMES, THE WHOLE REGRESSION IS ONE FILE —
    `test_matchup_yardage.py`, 8.1s -> 13.7s. Every other file moved by less than 0.3s. The
    mechanism:

        chart.to_json() + json.loads()    19.0 ms per chart
        yardage: 6 charts x 52 tests      312 charts -> 5.9 s

    🚨 AND YARDAGE NEVER READS THE JSON. It reads the altair OBJECT out of `Capture.events`,
    because its assertions are about axis domains, plotted coordinates and stroke widths. The
    harness was paying 19 ms a chart to build something nobody asked for.

    ✅ SO THE SPECS ARE BUILT ON ACCESS. A caller that reads them gets exactly what it got
    before; a caller that never touches them pays nothing. `len()` and truthiness answer from
    the object list, so even counting charts is free.
    """

    def __init__(self):
        self._objects = []
        self._specs = None

    def add(self, chart):
        self._objects.append(chart)
        self._specs = None

    def _materialise(self):
        if self._specs is None:
            specs = []
            for chart in self._objects:
                try:
                    specs.append(json.loads(chart.to_json()))
                except Exception as exc:                           # noqa: BLE001
                    specs.append({"__unreadable__": str(exc)})
            self._specs = specs
        return self._specs

    def __len__(self):
        return len(self._objects)

    def __bool__(self):
        return bool(self._objects)

    def __getitem__(self, index):
        return self._materialise()[index]

    def __iter__(self):
        return iter(self._materialise())

    def __eq__(self, other):
        return self._materialise() == other

    def __repr__(self):
        return repr(self._materialise())


class Capture(list):
    """The rendered strings, which ALSO remember which `st.*` call produced each one.

    🚨 R-613. IT IS A `list` SUBCLASS ON PURPOSE, AND THAT IS WHAT MAKES THE CONSOLIDATION
    SAFE. Every existing caller — `assert_captured`, `plain`, `"\n".join(captured)`, A's two
    files and A's `test_states_failure_modes` — sees exactly what it saw before: a list of
    strings. Nothing of A's changes, which is §3 rule 3.1 for an addition.

    ⚠️ AND WITHOUT IT THE SEVEN FILES COULD NOT MOVE. They roll their own stub because they
    capture `(kind, body)` PAIRS and assert on the kind — 28 sites across the seven, things
    like "the panel emits exactly two markdown blocks" and "this sentence is a caption, not a
    heading". The shared harness captured flat strings, so moving them would have meant
    deleting 28 real claims. `.events` keeps them.
    """

    def __init__(self):
        super().__init__()
        self.events = []

    def record(self, kind, body):
        self.events.append((kind, body))
        self.append(body)
        return body

    def record_object(self, kind, obj, text):
        """An event whose payload is an OBJECT, with a string standing in for it in the list.

        ⚠️ THE FLAT LIST MUST STAY STRINGS — `render()` does `"\n".join(captured)` and
        `plain()` runs regexes over it — so the object goes only into `.events`.

        🚨 IT EXISTS BECAUSE A CHART IS NOT ITS REPR. The bespoke stubs captured the altair
        OBJECT and the yardage tests read `chart.to_dict()` off it — axis domains, plotted
        coordinates, stroke widths, the spec Streamlit ships. `str(chart)` says nothing about
        any of that, which is the same reason B084's own stub kept the object.
        """
        self.events.append((kind, obj))
        self.append(text)
        return obj

    def clear(self):
        super().clear()
        self.events.clear()


class Recorder:
    """A container that captures what is drawn into it, and can make more containers.

    🚨 R-617. IT DELEGATES TO THE MODULE-LEVEL STUB, AND THE REASON IS A ROUND THAT WAS SPENT
    ON IT. A `Recorder` is what `st.columns()` returns, and every name it did not define fell
    through `__getattr__` to a function that recorded and returned `None`. Measured on
    `bf3500c`, five methods disagreed with the stub they were standing in for:

        st.selectbox("Down", [...])   -> 'Any'        left.selectbox("Down", [...])  -> None
        st.multiselect(…, default=…)  -> ['a']        left.multiselect(…)            -> None
        st.slider("S", value=3)       -> 3            left.slider("S", value=3)      -> None
        st.expander("t")              -> Recorder     left.expander("t")             -> None
        st.button("Go")               -> False        left.button("Go")              -> None

    **`views/players.py:275` does `None if down == "Any" else int(down)`.** `int(None)` raises,
    `states.section` catches it, and the page draws an Error card. ⚠️ **A110 reported that as a
    page defect, Cowork wrote it into the register as one, and A111 spent its round disproving
    it** — the fifth time a harness gap has been read as a page fault on this project.

    ⚠️ AND THE OTHER FOUR ARE WORSE THAN THE ONE THAT WAS FOUND. `with left.expander("x"):`
    cannot work at all against `None`, and a column's `button` was merely FALSEY rather than
    `False` — so `_FALSE_WIDGETS` looked like it covered columns and did not.

    ✅ SO THERE IS ONE DEFINITION PER METHOD AND THE SPLIT CANNOT DISAGREE. `__getattr__` looks
    the name up on the stub module and calls THAT, rather than keeping a second list of what
    each widget returns. Cowork's ruling, and R-574's lesson: two statements of one rule drift,
    and the drift is invisible until it costs a round. ⚠️ There was already one here —
    `Recorder.metric` rstripped its body and `st.metric` did not.

    ⚠️ THE RECORDING IS KEPT, NOT TRADED FOR THE ANSWER. A column's `selectbox` records into
    the flat list AND `.events` (B094's `Capture` contract) *and* returns the stub's value. The
    stub's own drawing methods already record, so the wrapper records only when the delegate
    did not — no list says which ones those are, it is observed per call.
    """

    def __init__(self, captured, st=None):
        self._captured = captured
        # ⚠️ OPTIONAL, WITH THE OLD BEHAVIOUR AS THE DEFAULT — §3 rule 3.1. `Recorder([])` is a
        # live call site in `test_render_harness.py` and A's `test_export_page.py` rolls its
        # own recorder entirely; a Recorder built without a stub keeps recording and returning
        # `None`, exactly as before.
        self._st = st

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    # Requirement 3: a column can make columns.
    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [Recorder(self._captured, self._st) for _ in range(count)]

    def tabs(self, labels, **kwargs):
        return [Recorder(self._captured, self._st) for _ in labels]

    def container(self, *a, **k):
        return Recorder(self._captured, self._st)

    # ⚠️ `metric` USED TO BE DEFINED HERE TOO, AND THE TWO DEFINITIONS HAD ALREADY DRIFTED:
    # this one rstripped the body and `st.metric` did not. It is gone — the stub's `metric`
    # records through `Capture.record` exactly as this did, so a consolidated file asserting
    # "a metric labelled X was drawn" still reads it out of `.events`. That drift is the
    # measured case for delegating rather than listing.

    def _record(self, name, body):
        if isinstance(self._captured, Capture):
            self._captured.record(name, body)
        else:
            self._captured.append(body)

    def __getattr__(self, name):
        # Requirement 2: dunders are Python's business, not the page's.
        if name.startswith("__"):
            raise AttributeError(name)
        if name.startswith("_"):
            raise AttributeError(name)

        if self._st is None:
            def record(*args, **kwargs):
                self._record(name, " ".join(str(a) for a in args))
            return record

        # 🚨 THE ONE DEFINITION. `getattr` on the stub, so an unprovided name raises
        # `HarnessGap` from a column exactly as it does from `st` — requirement 1 covered
        # absence at module level only, and a column swallowed it.
        target = getattr(self._st, name)
        if not callable(target):
            # `st.sidebar`, `st.session_state`, `st.query_params`, `st.context` — the same
            # object, not a copy, so a page that writes session state through a column and
            # reads it off `st` sees its own write.
            return target

        def call(*args, **kwargs):
            before = len(self._captured)
            value = target(*args, **kwargs)
            # ⚠️ OBSERVED, NOT LISTED. The stub's drawing methods record themselves; its
            # widgets and containers do not. Asking the capture whether it grew needs no
            # second list of which is which, so nothing here can fall out of step with the
            # stub the way `metric` did.
            if len(self._captured) == before:
                self._record(name, " ".join(str(a) for a in args))
            return value
        return call


def build(query_params=None, theme="light"):
    """A streamlit stub. Returns (module, captured_list, charts_list)."""
    captured, charts = Capture(), Charts()
    st = types.ModuleType("streamlit")

    def recorder(_name):
        def call(*args, **kwargs):
            captured.record(_name, " ".join(str(a) for a in args))
        return call

    for name in PROVIDED:
        setattr(st, name, recorder(name))

    def altair_chart(chart, **kwargs):
        # ⚠️ NO to_json() HERE. `Charts` builds the spec on first read — see its docstring for
        # the 19 ms a chart this was costing, and the one file that paid all of it.
        charts.add(chart)
        captured.record_object("chart", chart, "[altair_chart]")
    st.altair_chart = altair_chart
    # ⚠️ THE `.rstrip()` IS THE ONE `Recorder.metric` USED TO CARRY AND THIS ONE DID NOT.
    # Collapsing the two definitions into one meant choosing, and the column's was the one
    # eight files' assertions were written against.
    st.metric = lambda label, value, help=None, **k: captured.record(
        "metric", f"{label} :: {value} {help or ''}".rstrip())
    st.columns = lambda spec, **k: [
        Recorder(captured, st) for _ in range(spec if isinstance(spec, int) else len(spec))]
    st.tabs = lambda labels, **k: [Recorder(captured, st) for _ in labels]
    for name in _CONTAINERS:
        setattr(st, name, lambda *a, **k: Recorder(captured, st))
    st.sidebar = Recorder(captured, st)
    for name in _FALSE_WIDGETS:
        setattr(st, name, lambda *a, **k: False)
    st.radio = lambda label, options, index=0, **k: (
        list(options)[index or 0] if list(options) else None)
    st.selectbox = st.radio
    st.segmented_control = st.pills = lambda label, options, **k: (
        (list(options) or [None])[0])
    st.multiselect = lambda label, options, default=None, **k: list(default or [])
    st.slider = lambda label, *a, **k: k.get("value", 0)
    st.text_input = lambda *a, **k: k.get("value", "")
    st.number_input = lambda *a, **k: k.get("value", 0)
    st.session_state = {}
    st.query_params = dict(query_params or {})
    st.context = types.SimpleNamespace(theme=types.SimpleNamespace(type=theme))

    def cache(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda fn: fn
    st.cache_data = st.cache_resource = cache

    def missing(name):
        # Requirement 2 again, at module level: pytest reads __file__ while formatting a
        # failure, and B082 watched a red test become INTERNALERROR because of it.
        if name.startswith("__"):
            raise AttributeError(name)
        raise HarnessGap(
            f"HARNESS GAP: the page called st.{name}(), which tests/render_harness.py does "
            f"not provide. ⚠️ THIS IS NOT A PAGE DEFECT — add it to PROVIDED. (A085/R-631)")
    st.__getattr__ = missing
    return st, captured, charts


RELOAD = ("lib.query", "lib.fmt", "lib.table", "lib.states", "lib.shell", "lib.identity",
          "lib.params", "lib.filters", "lib.theme", "lib.attribution", "lib.datasets",
          "lib.chips", "lib.metrics", "lib.distribution", "lib.workbook")


# 🚨 R-610. AN ERROR STATE IS A PASSING STATE, AND THAT IS WHAT THIS EXISTS TO END.
#
# `states.section` catches `Exception` and draws an Error card. That is right for a reader and
# catastrophic for a test: a panel that raises on its FIRST LINE emits one card and nothing
# else, so every "the page does not show X" assertion in this suite passes on a panel that
# died. B091 shipped `deltas or {}` — `Series.__bool__` raises — and the whole Matchup suite
# stayed green. The LIVE RENDER found it, for the second time in one round.
#
# ⚠️ THIS IS THE THIRD WRITING-DOWN OF THE SAME FACT AND THE FIRST CONTROL. Line 17 of this
# file already said a harness gap was "INDISTINGUISHABLE FROM A PAGE DEFECT"; R-627 recorded a
# dropped tunnel reading as a page fault. Both were notes. A note that describes a failure is
# not a control that prevents one.
#
# ⚠️ `degraded` IS NOT `error`, AND THEY ARE SEPARATED FROM THE FIRST LINE. A Degraded panel is
# an HONEST state a test may legitimately render — "srv_x has not been built yet" — so it is
# recorded and never enforced. Only `error` and `render_failed` mean something raised.
_FATAL_STATES = ("error", "render_failed")


class ErrorStateRendered(AssertionError):
    """A panel raised and `states.section` drew an Error card instead of propagating."""


def _watch_states(seen):
    """Wrap `lib.states` so the three failure states record themselves.

    ⚠️ WRAPPED AFTER THE RELOAD, ON THE STUB-BOUND COPY. `streamlit_stubbed` re-imports every
    module in RELOAD against the stub and puts the originals back on exit, so these wrappers go
    with it — there is nothing to unwind and no way for them to leak into a later test.
    """
    states = sys.modules.get("lib.states")
    if states is None:
        return
    for name in ("error", "render_failed", "degraded"):
        original = getattr(states, name, None)
        if original is None or getattr(original, "_cfdb_watched", False):
            continue

        def make(fn, label):
            def watched(*args, **kwargs):
                seen.append((label, args[0] if args else None))
                return fn(*args, **kwargs)
            watched._cfdb_watched = True
            return watched

        setattr(states, name, make(original, name))


ERROR_CARD = "cfdb-error"
DEGRADED_CARD = "cfdb-degraded"


def assert_no_error_card(entries, what="the panel", allow_error_state=False):
    """🚨 THE SAME GUARD FOR THE SEVEN FIXTURES THAT DO NOT USE THIS HARNESS.

    ⚠️ MEASURED IN B092 AND IT IS THE REASON THIS FUNCTION EXISTS: of the nine
    `tests/test_matchup_*.py` files, **SEVEN roll their own streamlit stub** — including
    `test_matchup_yardage.py`, which is where B091's `deltas or {}` actually hid. A guard that
    lived only in `streamlit_stubbed` would have covered two of nine and missed the very bug
    this round is named for.

    ✅ SO THIS READS WHAT WAS DRAWN, NOT HOW IT WAS STUBBED. `states.error` and
    `render_failed` both emit `class='cfdb-state cfdb-error'`; nothing else does. It works for
    any fixture that collects markup, which is all of them.

    ⚠️ `cfdb-degraded` AND `cfdb-empty` ARE NOT THIS. A Degraded panel is an honest state a
    test may legitimately render — AC-G.11 applies to the instrument too — so only the error
    card is fatal.

    `entries` may be a list of strings or of (kind, body) pairs; both shapes exist in this
    suite and the difference is not worth a second helper.
    """
    if allow_error_state:
        return
    blob = []
    for entry in entries:
        if isinstance(entry, (tuple, list)):
            blob.extend(str(part) for part in entry)
        else:
            blob.append(str(entry))
    if any(ERROR_CARD in part for part in blob):
        raise ErrorStateRendered(
            f"{what} RENDERED AN ERROR STATE. Something raised inside `states.section`, which "
            f"caught it and drew a card — so this render emitted a failure card and nothing "
            f"else, and any assertion about what the page does NOT show would pass on it. "
            f"Find the exception; do not adjust the assertion. If this test legitimately "
            f"renders a failed panel, pass allow_error_state=True and say why in the call.")


def assert_no_error_state(seen, allow_error_state=False):
    """The enforcement. Strict by default — an Error state fails the test.

    🚨 THE MESSAGE IS THE POINT (A098's rule). "No entries found" sent B091 looking at an
    assertion; "the panel rendered an Error state" sends the next round at the traceback that
    caused it.
    """
    fatal = [(label, view) for label, view in seen if label in _FATAL_STATES]
    if fatal and not allow_error_state:
        where = ", ".join(f"{label}({view})" if view else label for label, view in fatal)
        raise ErrorStateRendered(
            f"THE PANEL RENDERED AN ERROR STATE: {where}. Something raised inside "
            f"`states.section`, which caught it and drew a card — so this render emitted a "
            f"failure card and nothing else, and any assertion about what the page does NOT "
            f"show would pass on it. Find the exception; do not adjust the assertion. If this "
            f"test legitimately renders a failed panel, pass allow_error_state=True and say "
            f"why in the call.")


@contextlib.contextmanager
def streamlit_stubbed(query_params=None, theme="light", allow_error_state=False,
                      states_seen=None):
    """Swap in the stub, and PUT IT ALL BACK — two populations, two opposite methods.

    ⚠️ THE RESTORE IS BY HAND AND MUST STAY THAT WAY. monkeypatch's sys.modules undo runs after
    fixture teardown, so a module reloaded against the stub stays bound to it for the rest of
    the session — B066 failed six unrelated tests that way.

    🚨 BUT THE RESTORE USED TO BE `importlib.reload`, AND THAT FIXED B066 BY CAUSING R-665.
    **`reload` REBINDS A MODULE'S GLOBALS IN PLACE; IT DOES NOT RESTORE THEM.** Every class the
    module defines becomes a NEW object with the same name, so a file that did
    `from lib.query import QueryContractError` at collection time is left holding a class that
    nothing raises any more. A101 reproduced it on `a68893e`: a third harness caller and five
    `test_site_foundation::test_contract_violations_raise` cases go red —

        with pytest.raises(QueryContractError):
            check_contract(sql)          # raises a DIFFERENT QueryContractError

    ⚠️ AND IT IS ORDER-DEPENDENT, WHICH IS WHY THE SUITE STAYED GREEN. With pytest-randomly the
    five fire only when a harness caller happens to run BEFORE the victim; in file order the
    third caller sorted last and nothing showed. That is a coin flip, not a pass.

    ── THE TWO POPULATIONS, AND WHY THEY NEED OPPOSITE TREATMENT ────────────────────────────

    `lib.*` (RELOAD)  — other files import NAMES out of these: `query`, `Col`,
                        `QueryContractError`, `GameScope`. Measured: 24 name-imports from
                        lib.query, 18 from lib.table, 2 from lib.filters.
                        ✅ SWAPPED. The original module object is set aside untouched and put
                        back on exit, so every identity anyone holds survives. Reloading these
                        is the defect.

    `views.*`         — nothing imports a name OUT of a view. The 13 files that touch them do
                        `from views import schedule`, which binds the MODULE OBJECT.
                        ✅ RELOADED. Reload mutates in place, which is exactly what a held
                        module object needs: `views.schedule.st` goes back to real streamlit
                        without the holder's reference changing. Swapping these would leave
                        those 13 files pointing at a discarded stub-bound module.

    🚨 THE VIEWS HALF WAS NEVER RESTORED AT ALL BEFORE THIS. Measured on `a68893e`:

        before:  lib.query.st=REAL   views.performance.st=REAL
        inside:  lib.query.st=stub   views.performance.st=stub
        after:   lib.query.st=REAL   views.performance.st=stub     <-- still the stub

    ⚠️ So B066's failure mode was live the whole time for any view a test had rendered. It went
    unnoticed because a view module is normally only read through the harness again.

    ⚠️ ONE MORE THING THE SWAP BUYS, AND IT WAS NOT THE GOAL. `lib.query` carries
    `st.cache_resource` on its engine (A095 found that the hard way). The old restore re-ran
    that decorator on every exit, throwing the cached engine away each time; putting the
    original module back leaves it intact.
    """
    if str(SITE) not in sys.path:
        sys.path.insert(0, str(SITE))
    real = sys.modules.get("streamlit")
    # The originals, set aside rather than mutated. This is the whole fix.
    originals = {name: sys.modules.get(name) for name in RELOAD}
    st, captured, charts = build(query_params, theme)
    states_seen = [] if states_seen is None else states_seen
    sys.modules["streamlit"] = st
    try:
        for name in RELOAD:
            # Dropped and imported fresh, so the stub-bound copy is a NEW object and the
            # original is never touched.
            sys.modules.pop(name, None)
            try:
                importlib.import_module(name)
            except Exception:                                      # noqa: BLE001
                pass
        _watch_states(states_seen)
        yield st, captured, charts
        # ⚠️ NO ENFORCEMENT HERE, AND §3 RULE 3.1 IS WHY. `streamlit_stubbed` is the RAW
        # instrument, and A095's `tests/test_states_failure_modes.py` uses it to exercise the
        # failure states themselves — five call sites whose whole job is to render one. A
        # shared-module change "ships the parameter and the default" and leaves the other
        # session's call sites to that session; enforcing on exit here would have reached
        # across and broken A's file to make B's guard convenient.
        #
        # ✅ THE DEFAULT IS STILL STRICT WHERE IT COUNTS: `render()` below draws a real page
        # and refuses an Error card, and `assert_no_error_card` is strict for every fixture
        # that calls it. Nothing is opt-in; the enforcement simply sits where it does not
        # reach into A's tests. B092 reports the one line A needs to extend it here.
    finally:
        if real is not None:
            sys.modules["streamlit"] = real
        else:
            sys.modules.pop("streamlit", None)
        for name, module in originals.items():
            # 🚨 BOTH PLACES, AND THE SECOND ONE IS NOT OPTIONAL. `sys.modules` is not the only
            # handle on a submodule: importing `lib.states` also sets `states` as an ATTRIBUTE
            # of the `lib` package, and `from lib import states` reads that attribute rather
            # than sys.modules. A101's first draft restored sys.modules alone, and
            # `test_error_state_never_leaks_internals` went red with an empty capture — it had
            # been handed the stub-bound module by the package while sys.modules said
            # otherwise. Two failures, both new, both caused by the fix.
            parent_name, _, child = name.rpartition(".")
            parent = sys.modules.get(parent_name) if parent_name else None
            if module is not None:
                sys.modules[name] = module
                if parent is not None:
                    setattr(parent, child, module)
            else:
                sys.modules.pop(name, None)
                if parent is not None and hasattr(parent, child):
                    delattr(parent, child)
        # The views half: reload in place so the module objects other files hold rebind to the
        # real streamlit that has just been put back.
        #
        # ⚠️ ONLY THE ONES ACTUALLY BOUND TO THE STUB. Reloading every loaded view on every
        # exit cost the suite about five seconds — measured 28s before this round and 33s with
        # the blanket version — and reloading a view that was never touched is pure waste.
        # `st is stub` is exact: it is true for precisely the modules imported or reloaded
        # while the stub was installed.
        for name in [n for n in list(sys.modules) if n.startswith("views.")]:
            module = sys.modules.get(name)
            if module is not None and getattr(module, "st", None) is st:
                try:
                    importlib.reload(module)
                except Exception:                                  # noqa: BLE001
                    pass


def render(view, query_params=None, theme="light", allow_error_state=False):
    """Call a view module's real `body()`. Returns (text, charts).

    🚨 STRICT BY DEFAULT (R-610). This draws a REAL PAGE, and a real page that renders an Error
    card has a defect — there is no legitimate reason for `render()` to return one quietly.
    B091's `deltas or {}` proved the cost: `states.section` caught the raise, drew a card, and
    every assertion about what the page does NOT show passed on a panel that had died.
    """
    with streamlit_stubbed(query_params, theme) as (st, captured, charts):
        module = importlib.reload(importlib.import_module(f"views.{view}"))
        # ⚠️ THE STUB GOES IN WITH IT (R-617). Without it the page's `page` argument is a
        # Recorder that answers `None` to every control it builds, which is the whole defect.
        module.body(Recorder(captured, st))
        assert_no_error_card(captured, f"the {view} page", allow_error_state)
        return "\n".join(captured), list(charts)


def assert_captured(text, needle, what="the render"):
    """Requirement 4. ⚠️ A SILENT ABSENCE READS AS A PASS (B079), so nothing is reported until
    the capture has been shown to contain something it must contain."""
    if needle not in text:
        raise AssertionError(
            f"{what} captured {len(text)} characters and none of them are {needle!r} — "
            f"this is an EMPTY CAPTURE, not a clean render")
    return text


def plain(html):
    """Markup stripped, for quoting a page in a report."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()
