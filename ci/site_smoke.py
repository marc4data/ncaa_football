"""Boot the real app.py inside the built site image and check what nav it produces.

WHY THIS EXISTS. On 30 August the site rendered a sidebar of raw filenames and blank pages
for a day, and the end user found it. Nothing else could have: the repo has no test that
runs the app, CI never built this image, and the deployment was verified by querying the
database — which was entirely healthy the whole time.

The specific fault was Streamlit auto-discovering a directory named `pages/` and overriding
st.navigation. A static test now forbids that name. This is the complement: it proves the
entrypoint actually executes end to end in the real image, at the pinned version, and hands
st.navigation the pages the registry says it should.

st.navigation is stubbed rather than run. Executing a page would need a database, and this is
a build-time check — what it verifies is that app.py gets that far and builds the right nav,
which is the half that was silently wrong.
"""
import runpy
import sys

import streamlit as st

EXPECTED_PAGES = 18
EXPECTED_GROUPS = ["Overview", "Games & teams", "Betting", "Deliverable",
                   "Reference", "Back of house"]

captured = {}


class _RecordedPage:
    """What app.py asked for, rather than what Streamlit made of it.

    st.Page's own `.title` only resolves inside a script run, so reading it here raises.
    Recording the arguments is both simpler and a better test: it asserts what the app
    requested, with no Streamlit internals in the way.
    """

    def __init__(self, _fn, title=None, url_path=None, default=False, **_kw):
        self.title = title
        self.url_path = url_path
        self.default = default


class _StubNavigation:
    def run(self):
        captured["ran"] = True


def _fake_navigation(nav, **_kwargs):
    captured["nav"] = nav
    return _StubNavigation()


def main() -> int:
    st.Page = _RecordedPage
    st.navigation = _fake_navigation
    try:
        runpy.run_path("/app/app.py", run_name="__main__")
    except Exception as exc:                                       # noqa: BLE001
        print(f"FAIL: app.py raised {type(exc).__name__}: {exc}")
        return 1

    nav = captured.get("nav")
    if not nav:
        print("FAIL: app.py never called st.navigation — the nav would fall back to "
              "Streamlit's filename discovery, which is the 30 August outage exactly")
        return 1

    groups = list(nav)
    if groups != EXPECTED_GROUPS:
        print(f"FAIL: nav groups {groups} != {EXPECTED_GROUPS}")
        return 1

    total = sum(len(v) for v in nav.values())
    if total != EXPECTED_PAGES:
        print(f"FAIL: {total} pages registered, expected {EXPECTED_PAGES}")
        return 1

    # Titles, not filenames. The outage was visible precisely because the sidebar showed
    # `app`, `edges`, `today` — module names — instead of "Today", "Edge Finder".
    titles = [p.title for pages in nav.values() for p in pages]
    if any(t.islower() for t in titles):
        print(f"FAIL: nav shows module names rather than titles: {titles}")
        return 1
    if "app" in titles:
        print("FAIL: the entrypoint script appears as a page — that is Streamlit's "
              "automatic filename discovery, not st.navigation")
        return 1

    print(f"OK: app.py executed, st.navigation got {total} pages across "
          f"{len(groups)} groups; titles look like titles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
