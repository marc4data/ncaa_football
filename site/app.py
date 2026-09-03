"""cfdb — nav entrypoint.

All eighteen pages appear, including the ones that cannot be filled yet (AC-G.51). A page
whose data is missing renders Degraded and names its blocker; it is not hidden. A site that
hides what it cannot do teaches the user nothing, and one that says "Players is waiting on
dim_athlete" is a portfolio asset.
"""
import streamlit as st

from lib import theme
from lib.registry import GROUPS, PAGES

st.set_page_config(page_title="cfdb — college football data", page_icon="🏈",
                   layout="wide", initial_sidebar_state="expanded")
theme.inject()


def _page_module(key: str):
    """Every page is a module in site/views; the registry decides what it renders.

    THE DIRECTORY IS NOT CALLED `pages/`, AND THAT IS LOAD-BEARING.

    Streamlit auto-discovers a directory named `pages/` next to the entrypoint and builds a
    multipage app from the filenames. That competes with st.navigation below, and on
    30 August a rebuild picked up Streamlit 1.62 where the automatic one won: the sidebar
    showed raw filenames — including `app`, the entrypoint itself — and every page rendered
    blank, with no error raised anywhere.

    Pinning Streamlit held the site up. Renaming the directory is what makes the collision
    impossible at any version. tests/test_site_foundation.py fails if `site/pages/` returns.
    """
    def render():
        import importlib
        module = importlib.import_module(f"views.{key}")
        module.render()
    return render


# EVERY page is registered, including the ones with no nav slot.
#
# st.navigation does the ROUTING as well as the sidebar, so a page left out of this dict is
# not merely hidden — it is unreachable by URL, which would break every team link on the
# site. So the Team page is registered here and its sidebar entry is hidden in CSS.
#
# The failure direction is deliberate: if the selector ever misses, the nav entry reappears.
# That is a cosmetic regression. Dropping the page from the dict to hide it would produce a
# dead link from five other pages, which is not.
nav = {}
for group in GROUPS:
    nav[group] = [
        st.Page(_page_module(p.key), title=p.title, url_path=p.key,
                default=(p.key == "today"))
        for p in PAGES if p.group == group
    ]

theme.hide_nav_entries([p.url_path_for_nav for p in PAGES if not p.in_nav])
# R-159. `expanded=True` IS NOT COSMETIC HERE — IT PROTECTS THE NAV FROM THE LEGEND.
#
# Streamlit's default is `expanded=False`, which collapses a long nav behind "View 8 more"
# once the sidebar runs out of room. Adding Schedule's legend below the nav pushed it over
# that threshold, so eight of eighteen pages — every Betting page, every Reference page —
# vanished behind a disclosure the moment the legend shipped. Navigation is the sidebar's
# primary job and a page-specific legend must never cost it.
st.navigation(nav, expanded=True).run()
