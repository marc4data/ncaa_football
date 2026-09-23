r"""No blank line reaches Streamlit's Markdown parser inside a raw-HTML string.

🚨 **A BLANK LINE TERMINATES A RAW HTML BLOCK IN MARKDOWN, AND `unsafe_allow_html=True` DOES
NOT MEAN "SKIP MARKDOWN" — IT MEANS "DO NOT ESCAPE WHAT SURVIVES IT".** The string is parsed as
Markdown first, so a blank line closes the HTML block mid-tag, injects a `<p>`, and escapes
everything after it.

> **B148, which found this the hard way (cfdb-wta-R-1514):** *"any raw-HTML string this site
> passes to `st.markdown` shatters on a blank line."*

📊 WHAT THE BROWSER RECEIVED when a blank line sat between two lines of an SVG `<title>`:

    Yards gained 336
    <p>n=1376 over 11 weeks          ← Markdown's paragraph tag, INSIDE an SVG <title>
    &lt;/title&gt;&lt;circle …       ← and the rest of the column as escaped literal text

**Nine circles became one, and 1,934 Python tests stayed green.** The suite asserts the markup
as a Python string, which is well-formed at that moment; `st.markdown` hands the raw string to
the FRONTEND and the parse happens client-side. **No pure-Python test can watch that step.**

## WHY THIS IS A SEAM AND NOT SIXTY-TWO FIXES

📊 A219 enumerated the call sites with `ast` (`ci/enumerate_raw_html_sites.py`): **62 calls
across 18 files**, 61 passing `unsafe_allow_html=True` outright and one computing it at runtime.
**A rule per call site is sixty-two rules that drift**, and 18 of them are in `matchup.py`,
which session A does not own (§3.2.2). Guarding the two functions every one of them ends at
touches none of those files.

## 🚨 THE ONE THING THAT MAKES THIS DELICATE, MEASURED RATHER THAN ASSUMED

**`st.markdown` is a BOUND METHOD captured at import time**, so replacing
`DeltaGenerator.markdown` reaches `column.markdown(...)` and **NOT** `st.markdown(...)`:

    DeltaGenerator.markdown = spy
    st.markdown("x", unsafe_allow_html=True)      → NOT intercepted
    col.markdown("x", unsafe_allow_html=True)     → intercepted

📊 Verified on the pinned streamlit 1.61.1. **Both bindings are therefore replaced**, and
`verify()` proves it rather than trusting it — 10 of the 62 call sites go through a column,
slot or sub-column object and would otherwise be silently unguarded.

⚠️ **AND `unsafe_allow_html` IS THE SECOND POSITIONAL PARAMETER, NOT KEYWORD-ONLY**
(`markdown(self, body, unsafe_allow_html=False, *, help=…)`). A wrapper reading it only out of
`**kwargs` would miss a positional caller. It is taken positionally here so both shapes work.

## WHAT IT DELIBERATELY DOES NOT TOUCH

✅ **A call that does not pass `unsafe_allow_html` is Markdown that is MEANT to be Markdown, and
it is returned untouched.** 📊 Measured across all 18 pages on live published serving: of 827
markdown/caption calls, **246 are prose and exactly one of them contains a blank line** —
`views/methodology.py:18`, a 4,545-character document whose paragraphs are blank lines. **The
guard cannot reach it, by construction rather than by care.**

⚠️ **COLLAPSING IS SAFE HERE BECAUSE NOTHING ON THIS SITE IS WHITESPACE-SIGNIFICANT** — measured,
not assumed: zero `<pre>`, zero `<textarea>`, zero `white-space:pre` in any of the 18 view
modules or in `theme.py`. In HTML a run of whitespace between tags is already collapsed by the
renderer, so removing a blank line from raw markup cannot change what is drawn.
"""
import re

import streamlit as st

try:
    from streamlit.delta_generator import DeltaGenerator
except Exception:                                                  # pragma: no cover
    # ⚠️ NOT A REAL STREAMLIT. `tests/test_tab_title.py` executes `app.py` against a deliberately
    # minimal stub module to prove the routed page reaches the tab, and that stub models the
    # handful of Streamlit names `app.py` uses — not its internals. **A guard that cannot be
    # imported would take that test down with it**, so the class half is optional and the
    # module-level half below still applies.
    DeltaGenerator = None

#: A newline followed by one or more further newlines, ignoring horizontal whitespace
#: between them — `\n\n`, `\n   \n`, and any longer run, all become one newline.
BLANK_LINE = re.compile(r"\n[^\S\n]*(?:\n[^\S\n]*)+")

#: The methods every raw-HTML call site on this site ends at, measured with `ast`.
GUARDED = ("markdown", "caption")

_MARK = "_cfdb_blank_line_guard"


def collapse(markup: str) -> str:
    """Every run of blank lines in `markup` becomes a single newline."""
    return BLANK_LINE.sub("\n", markup)


def _wrap_plain(real):
    """The same guard for a module-level function that is NOT a bound method.

    ⚠️ ON A REAL STREAMLIT `st.markdown` IS BOUND and `_wrap` covers it. This is the branch for
    anything else — a stub, or a future Streamlit that exposes a plain function — and it exists
    so that case is GUARDED rather than silently skipped.
    """
    def guarded(body="", unsafe_allow_html=False, *args, **kwargs):
        if unsafe_allow_html and isinstance(body, str):
            body = collapse(body)
        return real(body, unsafe_allow_html, *args, **kwargs)
    setattr(guarded, _MARK, True)
    return guarded


def _wrap(real):
    def guarded(self, body="", unsafe_allow_html=False, *args, **kwargs):
        # ⚠️ ONLY WHEN THE CALLER ASKED FOR RAW HTML. Everything else is prose and is handed
        # through byte for byte — see the module docstring's measurement of methodology.py.
        if unsafe_allow_html and isinstance(body, str):
            body = collapse(body)
        return real(self, body, unsafe_allow_html, *args, **kwargs)
    setattr(guarded, _MARK, True)
    guarded.__name__ = getattr(real, "__name__", "guarded")
    guarded.__doc__ = getattr(real, "__doc__", None)
    return guarded


def _bindings(fn: str) -> list:
    """Every live binding of `fn` that a call site could reach."""
    out = []
    if DeltaGenerator is not None and hasattr(DeltaGenerator, fn):
        out.append(getattr(DeltaGenerator, fn))
    if hasattr(st, fn):
        out.append(getattr(st, fn))
    return out


def installed() -> bool:
    """Is the guard in place on EVERY live binding of every guarded method?

    ⚠️ A BINDING THAT DOES NOT EXIST CANNOT BE UNGUARDED, so it is not counted. A binding that
    exists and is unmarked is the failure this returns False for.
    """
    return all(getattr(b, _MARK, False)
               for fn in GUARDED for b in _bindings(fn))


def install() -> None:
    """Put the guard on every binding, and refuse to pretend if it did not take.

    🚨 **IT RAISES RATHER THAN RETURNING QUIETLY.** A guard that silently stops working when
    Streamlit changes its dispatch is the exact failure this project spent a fortnight
    removing — `st.markdown`'s binding is an implementation detail of a pinned dependency, and
    the day it moves this must be loud. ⚠️ It is called from `app.py`, which Streamlit re-runs
    on every interaction, so it is idempotent by design rather than by luck.
    """
    if installed():
        return
    for fn in GUARDED:
        wrapped = None
        if DeltaGenerator is not None and hasattr(DeltaGenerator, fn):
            real = getattr(DeltaGenerator, fn)
            wrapped = real if getattr(real, _MARK, False) else _wrap(real)
            setattr(DeltaGenerator, fn, wrapped)
        # 🚨 THE SECOND BINDING. `st.<fn>` is a bound method captured at import and does NOT
        # follow the class attribute — see the module docstring. Re-bind it to the wrapper on
        # the same root DeltaGenerator the module-level shortcut already carried.
        shortcut = getattr(st, fn, None)
        if shortcut is None or getattr(shortcut, _MARK, False):
            continue
        root = getattr(shortcut, "__self__", None)
        if root is not None and wrapped is not None:
            setattr(st, fn, wrapped.__get__(root, DeltaGenerator))
        else:
            setattr(st, fn, _wrap_plain(shortcut))
    if not installed():                                            # pragma: no cover
        raise RuntimeError(
            "the raw-HTML blank-line guard did not take on both bindings of "
            f"{GUARDED} — Streamlit's dispatch has moved and raw markup is unguarded")
