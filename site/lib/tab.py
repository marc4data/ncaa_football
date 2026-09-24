"""The browser tab: `M4D · <Page Name>`, and a suffix for a page that has one.

Marc, 2026-09-14: *"tab shows football icon then cfdb - college football data, replace cfdb
with M4D, college football data with `<Page Name>`, Show `<Page Name>` and team logos if on
Matchup"*. The logos are the one part a tab cannot do — a favicon is a single 16x16 slot and
two logos in it would be 8x8 each — so Matchup carries TEAM ABBREVIATIONS in the text
instead, which Marc chose when the constraint was put to him.

🚨 WHY THIS IS A MODULE AND NOT TWO LINES IN app.py — ALL FOUR FACTS WERE MEASURED IN A REAL
BROWSER AGAINST THE PINNED STREAMLIT (1.61.1), NOT READ OUT OF THE DOCS.

1. `st.Page(title=...)` NAMES THE NAV ENTRY AND NOTHING ELSE. Every page of this app has
   passed its own title to `st.Page` since the nav was built, and `document.title` read
   `cfdb — college football data` on all five pages sampled — Today, Schedule, Matchup,
   Scores and Team. The tab has only ever shown `set_page_config`'s string.
2. ✅ `set_page_config` MAY BE CALLED AGAIN, AND THE LAST CALL WINS — including from inside a
   page's own run, after `st.navigation` has routed. 1.61.1 has no "called once" guard.
   THIS IS WHY THE SITE STILL HAS NO JAVASCRIPT: a `components.v1.html` iframe reaching for
   `window.parent.document.title` was the alternative, and it would have put an iframe on
   every page of a site that has none. Measured: zero scripts before this change, zero after.
3. ✅ OMITTING `page_icon` ON THE SECOND CALL LEAVES THE FAVICON ALONE. The football is not
   re-sent and not lost — the two `<link rel="icon">` hrefs came back byte-identical.
4. 🚨 A TAB TITLE IS COSMETIC AND A PAGE IS NOT, so `set_title` cannot raise. Streamlit
   rejected a repeat `set_page_config` for years (`StreamlitAPIException`) and a future pin
   may reject it again. `app.py` sets the static fallback BEFORE routing, so there is always
   a real title in place when that happens — see the guard's own docstring for what the
   reader sees without it, which was MEASURED rather than assumed.

`cfdb` IS NOT BEING RENAMED. It is the repo, the database, the `srv_` model prefix and the
round ids. Only the tab changed.
"""
from typing import Optional

import streamlit as st

from lib import registry

# The brand as it appears in the tab, and nowhere else in the system.
BRAND = "M4D"

# Middle dot with spaces. It reads as a separator at tab size where a hyphen reads as part of
# a name, and `—` is what the retired string used between the brand and its description.
SEPARATOR = " · "


def compose(page_title: Optional[str] = None, suffix: Optional[str] = None) -> str:
    """Build the tab string. Pure — no Streamlit, so it is testable without a session.

    Every part is optional because every part can genuinely be missing: a page Streamlit
    could not resolve has no title, and a suffix is built from published columns that are
    null on some rows (see `teams_suffix`). A missing part is DROPPED rather than rendered
    as an empty segment, so the tab never reads `M4D ·  · ` at any width.
    """
    parts = [BRAND]
    for part in (page_title, suffix):
        text = str(part).strip() if part is not None else ""
        if text:
            parts.append(text)
    return SEPARATOR.join(parts)


def set_title(page_title: Optional[str] = None, suffix: Optional[str] = None) -> None:
    """Point the browser tab at where the reader actually is.

    Call it from `app.py` once routing has resolved, and again from a page that has a suffix
    worth showing — the later call wins (fact 2 above). `page_icon` is deliberately NOT
    passed: fact 3, the football survives.

    🚨 IT SWALLOWS EVERYTHING, ON PURPOSE, AND THE COST OF NOT DOING SO WAS MEASURED IN A
    BROWSER RATHER THAN REASONED ABOUT — A130 staged a Streamlit that refuses the second call
    and rendered the site both ways.

        guard in place    the tab reads `M4D`; Today drew 12,140 characters and Schedule
                          73,399; no error card anywhere
        guard removed     🚨 THE PAGE IS GONE. 823 characters — the sidebar and nothing else —
                          under a raw `RuntimeError`, a full traceback, TWO ABSOLUTE
                          FILESYSTEM PATHS and Streamlit's "Ask Google / Ask ChatGPT" links.
                          That is AC-G.9 in the most visible place on the site.

    ⚠️ AND IT IS WORSE THAN AN ERROR CARD, WHICH IS WHAT THIS DOCSTRING FIRST CLAIMED. The
    `app.py` call site is OUTSIDE any page body, so `states.section` never sees the exception
    — there is no Error card to draw, because the app dies before `page.run()` is reached.
    A handled-looking failure would have been the GOOD outcome; the real one is a dead site.
    `claude_work/renders/A130_unguarded_title_failure.png` is the picture.
    """
    try:
        st.set_page_config(page_title=compose(page_title, suffix))
    except Exception:            # noqa: BLE001 — see the docstring; cosmetic must not break a page
        pass


def set_title_for(page_key: str, suffix: Optional[str] = None) -> None:
    """`set_title` for a page that knows its own key, which is every page.

    The title comes from `registry.BY_KEY` — the same object `app.py` built the nav from —
    so a page refining its tab cannot drift from the name in the sidebar. A page renamed in
    the registry is renamed in the tab, with nothing else to remember.

    An unknown key degrades to `M4D` plus the suffix rather than raising: see `set_title`.
    """
    page = registry.BY_KEY.get(page_key)
    set_title(page.title if page is not None else None, suffix)


def teams_suffix(row) -> Optional[str]:
    """`USM @ AUB` from a row of `srv_game`, or None when it cannot be said.

    ✅ ABBREVIATIONS, BECAUSE OF THE SIZE A TAB ACTUALLY IS. With several tabs open a browser
    squeezes each to ~100px, so `M4D · Matchup · Southern Miss @ Auburn` renders as
    `M4D · Matchu…` and the teams — the entire point of the suffix — are the first thing cut.

    ✅ THE ABBREVIATION IS READ, NEVER DERIVED (§4.2.1). `srv_game.home_abbreviation` and
    `away_abbreviation` are published columns; `matchup.py` already selects both. Joining two
    published strings creates no quantity, which is the composition §4.2.1 explicitly allows.

    ⚠️ AND THE COLUMN IS NOT UNIVERSAL — measured in serving, not assumed: `away_abbreviation`
    is null on 12,018 of 112,675 rows (10.7%), and on 136 rows of the 2026 season. So the
    fallback chain is the one `matchup.py` already uses at its own labels — abbreviation,
    then the full team name — and if a side yields neither, the suffix is dropped entirely
    rather than published as `None @ AUB`.
    """
    if row is None:
        return None

    def side(prefix: str) -> str:
        for column in (f"{prefix}_abbreviation", f"{prefix}_team"):
            try:
                value = row[column]
            except (KeyError, IndexError, TypeError):
                value = None
            # A null from the database arrives as None or as a pandas NA; both are falsey
            # only after str(), so test the text rather than the object.
            text = "" if value is None else str(value).strip()
            if text and text.lower() not in ("none", "nan", "<na>"):
                return text
        return ""

    away, home = side("away"), side("home")
    if not away or not home:
        return None
    return f"{away} @ {home}"


# 🚨 A223 (cfdb-main-R-2627). THE ROUTE'S OWN SUFFIX, RESOLVED IN THE SHELL.
#
# > **MARC, v16:** *"Match - tab name, can we team Abbr to the tab? Otherwise, I've got 10 M4D -
# > Matchup tabs for 10 different games, that all look the same"*
#
# 🚨 `teams_suffix` ABOVE WAS BUILT FOR EXACTLY THIS BY A130 AND NOTHING HAS EVER CALLED IT.
# 📊 `git grep teams_suffix` at `bdc41ba`: its own definition, four mentions in comments, eight
# assertions in `tests/test_tab_title.py` — and **zero call sites.** `matchup.py`'s own docstring
# says A130 *"reached the same conclusion independently"*, and `app.py`'s says a page with more
# to say refines the title *"see views/today.py, and Matchup's team abbreviations"*. **Today does.
# Matchup never did.** That is §2.5's class — a capability that exists, is tested, and is silent.
#
# ⚠️ SO THE CALL GOES IN THE SHELL, NOT IN `matchup.py`, WHICH IS SESSION B's (§3.2.2). The page
# would be the natural home and reaching into another session's file for a browser title is not
# worth the crossing. `app.py` already knows which route it resolved and the game is in the URL.
#
# 🚨 AND IT SWALLOWS EVERYTHING, FOR THE REASON `set_title` DOES — measured by A130 in a browser,
# not reasoned about. This runs OUTSIDE any page body, so `states.section` never sees an
# exception: an unguarded failure here does not draw an Error card, **it kills the site** and
# prints a traceback with absolute filesystem paths on screen (AC-G.9).
# `claude_work/renders/A130_unguarded_title_failure.png` is the picture.
def route_suffix(url_path: Optional[str]) -> Optional[str]:
    """`USM @ AUB` when the reader is on a Matchup with a game, else None.

    ⚠️ ONE SINGLE-TABLE SELECT ON A RELATION THE PAGE ALREADY READS, and §4.2.1 is not
    engaged: joining two published strings creates no quantity — `teams_suffix`'s own note.
    `query` is `@st.cache_data`-wrapped, so a reader clicking between tabs pays once.
    """
    try:
        if url_path != "matchup":
            return None
        from lib import params
        from lib.query import query
        game_id = params.get("game_id")
        if not game_id:
            return None
        df = query("""
            select away_abbreviation, home_abbreviation, away_team, home_team
            from srv_game
            where game_id = :game_id
            limit 1
        """, {"game_id": int(game_id)})
        if df is None or df.empty:
            return None
        return teams_suffix(df.iloc[0])
    except Exception:                                              # noqa: BLE001
        # ⚠️ A TAB WITHOUT ITS TEAMS IS A COSMETIC LOSS. A dead shell is not.
        return None
