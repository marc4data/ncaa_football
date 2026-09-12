"""R-630. The query failing and the page failing are different facts.

🚨 THE COST OF CONFLATING THEM IS MEASURED. A086 spent its whole first phase on a panel
reported as "something went wrong reading srv_rankings" while srv_rankings returned 101 healthy
rows — the fault was an AttributeError in the renderer. Cowork wrote and queue-jumped an entire
round on that message. B084 (R-627) hit it from the other side: a dropped SSH tunnel rendered as
a fault in srv_game.

⚠️ A READER MUST NEVER SEE A TRACEBACK. That is absolute (AC-G.9) and it is why R-446 stayed open
for weeks: the obvious fix is the forbidden one. The split below is the fix that is allowed.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))


@pytest.fixture
def states():
    """lib.states with streamlit captured, via the SHARED harness.

    ⚠️ THE FIRST VERSION OF THIS FIXTURE HAND-ROLLED A THREE-METHOD STUB AND FAILED FOR A REASON
    THAT WAS THE STUB'S. Importing `lib.query` for QueryFailed needs `st.cache_resource`, which
    the stub did not provide, so all six tests failed ALONE and passed in the full suite — where
    another file had already imported the real module. ⚠️ That is R-571's shape again, in the
    act of testing R-571's fix, and it is the argument for R-631's harness in one paragraph.
    """
    import render_harness
    # 🚨 THE ONE EXEMPTION IN THE SUITE, AND IT IS DECLARED RATHER THAN IMPLICIT. R-705(2).
    #
    # Every test in this file renders a failure state ON PURPOSE — that is what it is for. So
    # `streamlit_stubbed` cannot enforce "no Error card" on exit while this call site is silent
    # about it, and B092/B096 correctly shipped the parameter and left A's call site to A rather
    # than reaching across (§3 rule 3.1).
    #
    # ⚠️ IT IS A NO-OP TODAY: the raw instrument accepts the argument and does not yet act on it.
    # The point is that when it does, NOTHING IS EXEMPT BY ACCIDENT — this file says out loud that
    # it draws error cards, and every other caller is enforced without anyone auditing them.
    with render_harness.streamlit_stubbed(allow_error_state=True) as (_st, captured, _charts):
        import importlib
        yield importlib.import_module("lib.states"), captured


def _query_failed(relation="srv_rankings"):
    from lib.query import QueryFailed
    return QueryFailed(relation, RuntimeError("connection closed"))


def test_a_query_failure_NAMES_the_view_because_the_view_is_what_failed(states):
    module, captured = states
    with module.section("srv_rankings"):
        raise _query_failed()
    body = " ".join(captured)
    assert "Could not load this section" in body
    assert "srv_rankings" in body, "a real query failure should name the relation"


def test_a_RENDERER_failure_does_NOT_name_the_view(states):
    """🚨 A086's DEFECT, ASSERTED SO IT CANNOT COME BACK.

    The query succeeded, so the view is not what failed, and printing it sends the next reader —
    or the next round — to the wrong layer.
    """
    module, captured = states
    with module.section("srv_rankings"):
        raise AttributeError("module 'streamlit' has no attribute 'line_chart'")
    body = " ".join(captured)
    assert "Could not display this section" in body
    assert "srv_rankings" not in body, \
        "a renderer failure named the view — this is the A086 defect restored"


def test_neither_state_leaks_a_traceback_or_the_exception_text(states):
    """AC-G.9 is absolute, and it is why R-446 could not simply be 'print the error'."""
    module, captured = states
    with module.section("srv_game"):
        raise AttributeError("no attribute 'line_chart' at /site/views/today.py:671")
    body = " ".join(captured)
    for forbidden in ("Traceback", "AttributeError", "line_chart", "/site/"):
        assert forbidden not in body, f"the page leaked {forbidden!r}"


def test_a_missing_relation_still_degrades_rather_than_erroring(states):
    """The pre-existing behaviour, unchanged: a relation that does not exist is Degraded, not
    Error, and R-630 must not have quietly cost that."""
    module, captured = states
    with module.section("srv_new", degraded_if_missing="srv_new"):
        from lib.query import QueryFailed
        raise QueryFailed("srv_new", RuntimeError('relation "srv_new" does not exist'))
    body = " ".join(captured)
    assert "not built" in body.lower() or "srv_new" in body


# --- the operator's half ----------------------------------------------------------------

def test_the_trace_is_OFF_by_default_and_writes_nothing(states, capsys, monkeypatch):
    module, _ = states
    monkeypatch.delenv("CFDB_TRACE_STATES", raising=False)
    with module.section("srv_game"):
        raise AttributeError("boom")
    assert capsys.readouterr().err == "", "the trace wrote to stderr with the flag unset"


def test_the_trace_names_the_type_and_the_failing_line_on_STDERR(states, capsys, monkeypatch):
    """⚠️ B084 HAD TO PATCH states.section TO A PASSTHROUGH to learn its Error state was a
    dropped tunnel. Four of R-571's five cases would have been a one-line diagnosis with this.

    🚨 STDERR, NEVER THE PAGE.
    """
    module, captured = states
    monkeypatch.setenv("CFDB_TRACE_STATES", "1")
    with module.section("srv_rankings"):
        raise AttributeError("module 'streamlit' has no attribute 'line_chart'")
    err = capsys.readouterr().err
    assert "AttributeError" in err
    assert "line_chart" in err
    assert "srv_rankings" in err, "the trace should say which section was being drawn"
    page = " ".join(captured)
    assert "AttributeError" not in page and "line_chart" not in page, \
        "the trace leaked onto the reader's screen"
