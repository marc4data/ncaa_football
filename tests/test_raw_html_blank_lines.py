r"""A219 — no blank line reaches Streamlit's Markdown parser inside raw HTML.

> **B148 (cfdb-wta-R-1514):** *"any raw-HTML string this site passes to `st.markdown` shatters
> on a blank line."*

🚨 **WHAT THIS FILE CAN AND CANNOT OBSERVE, STATED FIRST, BECAUSE THAT IS THE ROUND'S SUBJECT.**
B148's first attempt at this guard came back GREEN under its own staged break and had to be
renamed, because it claimed a property no pure-Python test can watch: **the Markdown parse
happens in the FRONTEND**, after `st.markdown` has handed the string over.

    ❌ NOT OBSERVABLE HERE   "the browser receives well-formed HTML"
    ✅ OBSERVABLE HERE       "what this site hands to Streamlit contains no blank line
                             when it asked for raw HTML, and is byte-identical when it did not"

**The second is a real contract and it is what these tests are named for.** The first is
`ci/measure_escaped_markup.py`'s job — a Chromium script, deliberately not a test.

📊 AND THE BROWSER HALF WAS RUN, AS A POSITIVE CONTROL RATHER THAN AN ASSERTION. A blank line
injected into `views/system.py`'s `cfdb-daygroup` markup:

    guard disabled → 5 injected <p> inside div.cfdb-daygroup, 2804 elements
    guard enabled  → 0,                                       2794 elements

## What reaches the guard, measured rather than assumed

📊 `ci/enumerate_raw_html_sites.py` at this commit: **62 `unsafe_allow_html` calls across 18
files** — 61 passing `True` outright, one computing it at runtime
(`matchup.py:1296`, `unsafe_allow_html=bool(whose)`). ⚠️ Cowork's prompt said 67; that is
`git grep -c`, which counts LINES, and five of them are comments about the keyword (R-859).

📊 Rendering all 18 pages against live published serving: **827 markdown/caption calls, 581 raw
and 246 prose. Raw strings containing a blank line today: 0. Prose strings: 1** —
`views/methodology.py:18`, whose paragraphs ARE blank lines, and which the guard cannot reach
because it does not pass `unsafe_allow_html`.
"""
import re
import sys
from pathlib import Path

import pytest
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from lib import rawhtml                                           # noqa: E402

APP = (ROOT / "site" / "app.py").read_text()
INSTRUMENT = (ROOT / "ci" / "measure_escaped_markup.py").read_text()


@pytest.fixture
def guarded():
    """Install the guard and put Streamlit back exactly as it was afterwards.

    ⚠️ `install()` MUTATES A THIRD-PARTY CLASS AND A MODULE ATTRIBUTE. A test that leaves that
    in place would make every later test in the session run against a patched Streamlit, which
    is the kind of cross-contamination that makes a suite's failures unattributable.
    """
    saved = {fn: (getattr(DeltaGenerator, fn), getattr(st, fn)) for fn in rawhtml.GUARDED}
    # ⚠️ THE FIXTURE SAVES AND RESTORES; IT DOES NOT INSTALL. Installing here made a guard that
    # refuses to install — the correct behaviour when a binding cannot be covered — surface as
    # a fixture ERROR on three unrelated tests instead of a FAILURE on the one test named for
    # it. **A break has to go red against its own named test to have proved anything (R-726).**
    yield
    for fn, (cls_attr, mod_attr) in saved.items():
        setattr(DeltaGenerator, fn, cls_attr)
        setattr(st, fn, mod_attr)


# ── the collapse itself ───────────────────────────────────────────────────────────────

def test_a_blank_line_becomes_one_newline():
    """🚨 THE WHOLE DEFECT IN ONE LINE: a blank line terminates a raw HTML block in Markdown."""
    assert rawhtml.collapse("<div>\n\nx</div>") == "<div>\nx</div>"
    assert rawhtml.collapse("<a>\n\n\n\nb</a>") == "<a>\nb</a>"


def test_whitespace_only_lines_count_as_blank():
    """⚠️ MARKDOWN'S RULE IS *a line containing only whitespace*, not literally `\\n\\n`. A line
    of spaces or a tab between two newlines terminates the block exactly the same way, and a
    generated string is far more likely to carry `\\n   \\n` than a clean `\\n\\n`."""
    assert rawhtml.collapse("<div>\n   \nx</div>") == "<div>\nx</div>"
    assert rawhtml.collapse("<div>\n\t\n \nx</div>") == "<div>\nx</div>"


def test_a_single_newline_is_untouched():
    """⚠️ ONE NEWLINE IS LEGAL INSIDE A RAW HTML BLOCK and the site's markup is full of them —
    every multi-line `<style>` and every wrapped f-string. Collapsing those would be a change
    with no reason behind it."""
    markup = "<div>\n<span>a</span>\n<span>b</span>\n</div>"
    assert rawhtml.collapse(markup) == markup


def test_collapse_changes_nothing_when_there_is_nothing_to_change():
    assert rawhtml.collapse("<div>x</div>") == "<div>x</div>"
    assert rawhtml.collapse("") == ""


# ── the seam: BOTH bindings, because they are genuinely different objects ─────────────

def test_the_guard_reaches_st_markdown_and_column_markdown(guarded):  # noqa: D401
    """🚨 THE ONE THING THAT MAKES THIS DELICATE, AND IT IS MEASURED, NOT ASSUMED.
    `st.markdown` is a BOUND METHOD captured at import, so replacing `DeltaGenerator.markdown`
    reaches `column.markdown(...)` and **not** `st.markdown(...)`. 📊 10 of the 62 call sites
    go through a column, slot or sub-column object; the other 52 go through `st.`. **Guarding
    one binding leaves the other silently unprotected.**"""
    try:
        rawhtml.install()
    except RuntimeError as exc:
        pytest.fail(f"the guard could not cover every binding: {exc}")
    for fn in rawhtml.GUARDED:
        assert getattr(getattr(DeltaGenerator, fn), rawhtml._MARK, False), (
            f"DeltaGenerator.{fn} is unguarded — every `column.{fn}(...)` call is exposed")
        assert getattr(getattr(st, fn), rawhtml._MARK, False), (
            f"st.{fn} is unguarded — it is a bound method and does not follow the class")
    assert rawhtml.installed()


def test_install_is_idempotent(guarded):
    """⚠️ STREAMLIT RE-RUNS `app.py` ON EVERY INTERACTION, so this is called again on every
    click. A second wrap would nest the guard inside itself once per rerun — unbounded."""
    rawhtml.install()
    first = {fn: getattr(DeltaGenerator, fn) for fn in rawhtml.GUARDED}
    rawhtml.install()
    rawhtml.install()
    assert {fn: getattr(DeltaGenerator, fn) for fn in rawhtml.GUARDED} == first


def test_install_refuses_to_pretend_it_worked(monkeypatch, guarded):
    """🚨 A GUARD THAT SILENTLY STOPS WORKING IS THE FAILURE THIS PROJECT SPENT A FORTNIGHT
    REMOVING. `st.markdown`'s binding is an implementation detail of a pinned dependency; the
    day Streamlit changes its dispatch, this must be loud rather than quietly absent."""
    monkeypatch.setattr(rawhtml, "installed", lambda: False)
    with pytest.raises(RuntimeError, match="did not take"):
        rawhtml.install()


# ── what actually arrives, on both sides of the raw/prose line ───────────────────────

def _passed_down(fn: str, body: str, raw):
    """Call through the guard and return what the real Streamlit method received."""
    # ⚠️ THE WRAPPER IS BUILT AROUND A SPY BY THE SAME `_wrap` THE INSTALLER USES, so this
    # exercises the real code path without mutating Streamlit for the rest of the session.
    class Fake:
        pass
    spy_calls = []

    def spy(self, b="", u=False, *a, **k):
        spy_calls.append((b, u))
        return None
    wrapped = rawhtml._wrap(spy)
    wrapped(Fake(), body, raw)
    return spy_calls[0]


def test_a_raw_html_string_is_collapsed_before_it_leaves_this_process():
    """✅ THE CONTRACT THIS FILE IS NAMED FOR, AND IT IS OBSERVABLE HERE."""
    body, raw = _passed_down("markdown", "<div>\n\nboom</div>", True)
    assert raw is True
    assert "\n\n" not in body, f"a blank line survived the guard: {body!r}"
    assert body == "<div>\nboom</div>"


def test_prose_is_handed_through_byte_for_byte():
    """🚨 THE HALF THAT MUST NOT MOVE. A call that does not ask for raw HTML is Markdown that is
    MEANT to be Markdown, and its blank lines are its paragraphs.

    📊 Measured across all 18 pages on live published serving: of 246 prose calls, exactly one
    carries a blank line — `views/methodology.py:18`, a 4,545-character document. **Collapsing
    it would run that whole page together into a single paragraph.**"""
    prose = "### Where the data comes from\n\nEvery fact on this site originates…\n\nAnd more."
    body, raw = _passed_down("markdown", prose, False)
    assert raw is False
    assert body == prose, "the guard touched prose — methodology.py would lose its paragraphs"


def test_a_non_string_body_is_not_mangled():
    """⚠️ `body` IS TYPED `SupportsStr`, NOT `str`. A caller passing a number or a frame must
    reach Streamlit unchanged rather than raising inside a guard that assumed a string."""
    body, _raw = _passed_down("markdown", 42, True)
    assert body == 42


# ── the wiring: the guard is useless if nothing installs it ──────────────────────────

def test_app_installs_the_guard_before_anything_renders():
    """🚨 ORDERING IS THE WHOLE POINT. `theme.inject()` is itself a raw-HTML call, so a guard
    installed after it leaves the stylesheet — the largest generated string on the site —
    ungoverned on first paint."""
    # 🚨 THE CALLS, ANCHORED AT A LINE START — NOT THE PROSE ABOUT THEM. The first draft of
    # this assertion used `APP.index("theme.inject()")` and failed against the comment block
    # this round added directly above the install, which explains why it is not in
    # `theme.inject()`. **A217's R-2624 in a test written the same day it was cited.**
    install = re.search(r"^rawhtml\.install\(\)$", APP, re.M)
    inject = re.search(r"^theme\.inject\(\)$", APP, re.M)
    assert install, (
        "app.py does not install the guard; every one of the 62 call sites is unguarded")
    assert inject, "app.py no longer injects the stylesheet — this test is aimed at nothing"
    assert install.start() < inject.start(), (
        "the guard must be installed before the first raw-HTML call on the page")


# ── the instrument keeps looking for both signatures ─────────────────────────────────

def test_the_browser_instrument_looks_for_both_signatures():
    """🚨 ONE SIGNATURE WAS NOT ENOUGH AND THE CALIBRATION PROVED IT. The first version looked
    only for escaped text (`&lt;tag`). 📊 Under a real staged break it reported **zero** on a
    page whose DOM had visibly changed, because the shattered remainder was a bare closing tag
    the sanitiser passes through — escaping only happens for tags refused inline, like B148's
    SVG `<circle>`. **The injected `<p>` is the signature that caught it: 5 of them inside
    `div.cfdb-daygroup`.**

    ⚠️ ANCHORED ON THE QUERY AND THE REGEX THAT DO THE WORK, not on a word in the file
    (A217's R-2624) — this module documents both signatures in prose, so a word would match
    the explanation of a check that had been deleted."""
    assert "TAGLIKE" in INSTRUMENT and "&lt;" in INSTRUMENT, (
        "the escaped-markup signature is gone")
    assert re.search(r"querySelectorAll\(\s*'\[class\^=\"cfdb-\"\] p", INSTRUMENT), (
        "the injected-<p> signature is gone — the instrument would report zero on the exact "
        "break that calibrated it")
    assert "SKIP" in INSTRUMENT and "STYLE" in INSTRUMENT, (
        "the <style>/<script> exclusion is gone — 36 CSS comments would be reported as hits")
