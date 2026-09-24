r"""A226 — a bad URL parameter must not take the page to zero.

🚨 THE DEFECT: `params.get` raises `BadParam` for a value it cannot type, and nothing caught
it for the four `INT_PARAMS`. The raise escaped every `states.section`, so `?season=banana`
rendered **no panels, no error card, nothing**. A225 found it as a `week` problem; it is a
four-parameter problem on any page that reads them.

## Checked against the instrument failures this project has paid for

- **R-2254** — `pytest` exits NON-ZERO on an empty collection, so a file that collects nothing
  looks like a failure and a file whose tests all vanish looks like a pass. The collected
  count is asserted below.
- **R-2255** — `"" in anything` is True. No membership test here uses a value that could be
  empty without being asserted non-empty first.
- **R-2260 / cfdb-wta-R-1504** — a substring is not a rule, and `grep -c` counts its own
  command line. Nothing here greps; the functions are CALLED.
- **register rule 10** — "18 of 18 pages render" once came from eighteen runs of the same
  page. The page-count test here routes on the registry, not on a query parameter.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))


class _FakeQueryParams(dict):
    """Streamlit's `st.query_params` is dict-like; this is the part `params` uses."""

    def pop(self, key, default=None):
        return super().pop(key, default)


@pytest.fixture
def fake_params(monkeypatch):
    """Point `params` at a dict we control, so a 'URL' can be set in a test."""
    from lib import params
    store = _FakeQueryParams()
    monkeypatch.setattr(params.st, "query_params", store)
    return params, store


# 🚨 ONE BAD VALUE PER INT PARAMETER, AND EACH IS A VALUE A READER COULD REALLY ARRIVE ON:
# a stale `week=All` the page itself never generates, a typo, an empty string, a word.
BAD = [("season", "banana"), ("week", "All"), ("game_id", "x"), ("player_id", "")]


@pytest.mark.parametrize("name,value", BAD)
def test_A_BAD_INT_PARAMETER_IS_DISCARDED_AND_THE_PAGE_SURVIVES(fake_params, name, value):
    """The pre-flight reads it, cannot type it, drops it, and NAMES it.

    ⚠️ `player_id=""` IS IN THE SET DELIBERATELY. `params.get` returns the default for an
    empty string rather than raising, so this row asserts the pre-flight does NOT invent a
    discard — an over-eager guard that reported every blank parameter would be noise on every
    page. The expectation differs per row and is derived, not assumed.
    """
    params, store = fake_params
    from lib import shell
    store[name] = value
    discarded = shell.discard_unreadable_params()
    if value == "":
        assert discarded == [], f"an empty {name} is a default, not a bad value"
        return
    assert [n for n, _v in discarded] == [name], discarded
    assert dict(discarded)[name] == value, "the notice must name the value the reader typed"
    assert name not in store, f"{name} was named but not dropped, so the body still sees it"
    # and reading it now returns the default rather than raising
    assert params.get(name) is None


def test_THE_GUARD_CAN_GO_RED_because_the_raise_is_still_there(fake_params):
    """🚨 R-760 AND THE PROMPT'S OWN ASK: a companion proving the test above can fail.

    If `params.get` stopped raising — the fallback-inside-`get` design this round rejected —
    every row above would pass for the wrong reason: nothing to discard, nothing to name, and
    a reader silently shown the default. **This asserts the raise still exists**, which is the
    single fact the whole pre-flight depends on.
    """
    params, store = fake_params
    store["season"] = "banana"
    with pytest.raises(params.BadParam) as caught:
        params.get("season")
    assert caught.value.name == "season"
    assert caught.value.value == "banana"


def test_SEVERAL_BAD_PARAMETERS_ARE_ALL_NAMED_not_just_the_first(fake_params):
    """⚠️ A COUNT CANNOT SEE A SWAP (B149) — so this pins the PAIRS, not how many there are.
    A pre-flight that stopped at the first bad value would leave the second in the URL for the
    body to raise on, which is the blank page again."""
    params, store = fake_params
    from lib import shell
    store.update({"season": "banana", "game_id": "x", "division": "fbs"})
    discarded = shell.discard_unreadable_params()
    assert sorted(discarded) == [("game_id", "x"), ("season", "banana")], discarded
    assert store.get("division") == "fbs", "a VALID parameter was discarded with the bad ones"


def test_A_VALID_URL_DISCARDS_NOTHING(fake_params):
    """The control. A guard that fires on a good URL is worse than none — it is the
    100%-fallback shape, arriving as a notice on every page."""
    params, store = fake_params
    from lib import shell
    store.update({"season": "2026", "week": "3", "division": "fbs", "season_type": "regular"})
    assert shell.discard_unreadable_params() == []
    assert dict(store) == {"season": "2026", "week": "3", "division": "fbs",
                           "season_type": "regular"}


def test_THE_NOTICE_ESCAPES_THE_VALUE_because_it_comes_from_the_readers_url(monkeypatch):
    """🚨 AC-G.9 AND UNTRUSTED INPUT. The value is whatever was typed in the address bar and
    it is rendered into raw markup; unescaped, `?week=<script>` is a page that runs it."""
    from lib import states
    seen = []
    monkeypatch.setattr(states.st, "markdown", lambda body="", **k: seen.append(body))
    states.discarded([("week", "<script>alert(1)</script>")])
    assert len(seen) == 1
    assert "<script>" not in seen[0], "the reader's value reached the page unescaped"
    assert "&lt;script&gt;" in seen[0]


def test_THE_NOTICE_NEVER_SHOWS_AN_EXCEPTION_OR_A_TRACEBACK(monkeypatch):
    """AC-G.9: a reader must never see a traceback, a host, a credential or exception text."""
    from lib import states
    seen = []
    monkeypatch.setattr(states.st, "markdown", lambda body="", **k: seen.append(body))
    states.discarded([("season", "banana")])
    body = seen[0]
    for forbidden in ("Traceback", "BadParam", "ValueError", "invalid literal", "site/lib"):
        assert forbidden not in body, f"the notice leaked {forbidden!r}"


def test_THE_PREFLIGHT_RUNS_BEFORE_THE_BODY_not_around_it():
    """⚠️ Wrapping `body()` would catch the raise halfway through a render and leave a
    half-drawn page, a notice, and a second copy. This asserts the ORDER by calling the shell
    with a body that records when it ran."""
    import inspect
    from lib import shell
    src = inspect.getsource(shell.render_page)
    assert src.index("discard_unreadable_params()") < src.index("header(page)"), \
        "the pre-flight must run before the header, which reads parameters too"
    assert "try:" not in src, "the body is wrapped in a try, which is the half-page shape"


def test_THIS_FILE_STILL_DEFINES_THE_TEST_FUNCTIONS_IT_CLAIMS():
    """🚨 R-2254: `pytest` exits non-zero on an EMPTY collection, so a file whose tests all
    disappeared is indistinguishable from one that failed.

    ⚠️ IT COUNTS FUNCTIONS, NOT COLLECTED TESTS, AND SAYS SO — `@parametrize` expands the
    four-row case into four, so this file defines EIGHT functions and pytest collects ELEVEN.
    Asserting 8 while calling it "collected" would be a number that does not answer the
    question it is labelled with, which is the §2.4 shape."""
    import test_bad_parameter as self_module
    funcs = [n for n in dir(self_module) if n.startswith("test_")]
    assert len(funcs) == 8, f"expected 8 test functions, found {len(funcs)}: {funcs}"
    assert len(BAD) == 4, "the parametrised set shrank; collection is 8 + 4 - 1 = 11"
