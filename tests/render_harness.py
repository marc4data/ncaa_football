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


class Recorder:
    """A container that captures what is drawn into it, and can make more containers."""

    def __init__(self, captured):
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    # Requirement 3: a column can make columns.
    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [Recorder(self._captured) for _ in range(count)]

    def tabs(self, labels, **kwargs):
        return [Recorder(self._captured) for _ in labels]

    def container(self, *a, **k):
        return Recorder(self._captured)

    def metric(self, label, value, help=None, **kwargs):
        self._captured.append(f"{label} :: {value}")

    def __getattr__(self, name):
        # Requirement 2: dunders are Python's business, not the page's.
        if name.startswith("__"):
            raise AttributeError(name)
        if name.startswith("_"):
            raise AttributeError(name)

        def record(*args, **kwargs):
            self._captured.append(" ".join(str(a) for a in args))
        return record


def build(query_params=None, theme="light"):
    """A streamlit stub. Returns (module, captured_list, charts_list)."""
    captured, charts = [], []
    st = types.ModuleType("streamlit")

    def recorder(_name):
        def call(*args, **kwargs):
            captured.append(" ".join(str(a) for a in args))
        return call

    for name in PROVIDED:
        setattr(st, name, recorder(name))

    def altair_chart(chart, **kwargs):
        try:
            charts.append(json.loads(chart.to_json()))
        except Exception as exc:                                   # noqa: BLE001
            charts.append({"__unreadable__": str(exc)})
        captured.append("[altair_chart]")
    st.altair_chart = altair_chart
    st.metric = lambda label, value, help=None, **k: captured.append(f"{label} :: {value}")
    st.columns = lambda spec, **k: [
        Recorder(captured) for _ in range(spec if isinstance(spec, int) else len(spec))]
    st.tabs = lambda labels, **k: [Recorder(captured) for _ in labels]
    for name in _CONTAINERS:
        setattr(st, name, lambda *a, **k: Recorder(captured))
    st.sidebar = Recorder(captured)
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


@contextlib.contextmanager
def streamlit_stubbed(query_params=None, theme="light"):
    """Swap in the stub, reload what binds streamlit, and PUT IT ALL BACK.

    ⚠️ THE RESTORE IS BY HAND AND MUST STAY THAT WAY. monkeypatch's sys.modules undo runs after
    fixture teardown, so a module reloaded against the stub stays bound to it for the rest of
    the session — B066 failed six unrelated tests that way.
    """
    if str(SITE) not in sys.path:
        sys.path.insert(0, str(SITE))
    real = sys.modules.get("streamlit")
    st, captured, charts = build(query_params, theme)
    sys.modules["streamlit"] = st
    try:
        for name in RELOAD:
            try:
                importlib.reload(importlib.import_module(name))
            except Exception:                                      # noqa: BLE001
                pass
        yield st, captured, charts
    finally:
        if real is not None:
            sys.modules["streamlit"] = real
        else:
            sys.modules.pop("streamlit", None)
        for name in RELOAD:
            try:
                importlib.reload(importlib.import_module(name))
            except Exception:                                      # noqa: BLE001
                pass


def render(view, query_params=None, theme="light"):
    """Call a view module's real `body()`. Returns (text, charts)."""
    with streamlit_stubbed(query_params, theme) as (_st, captured, charts):
        module = importlib.reload(importlib.import_module(f"views.{view}"))
        module.body(Recorder(captured))
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
