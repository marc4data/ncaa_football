"""`lib/datasets.py` carries no dead copy — the direction A091 had to leave unguarded (R-528).

A089 asserted `sections == set(DATASETS)` in BOTH directions, so a label nobody used failed.
A091 lifted the table out of `today.py` to `lib/datasets.py` so Matchup could consume it
rather than declare a second one, and at that moment the equality stopped being a statement
about Today: the table held six keys Today does not read, deliberately, because §3 rule 3.1
says a shared-module change ships the labels and the other session wires its own call sites.

A091 weakened its own assertion to a subset and said so rather than hiding it:

    "THE DEAD-COPY DIRECTION IS THEREFORE UNGUARDED RIGHT NOW, and pretending otherwise would
     be worse than saying so. The honest version — every key in datasets.py is named by a
     `states.section` somewhere under site/views/ — cannot pass until Matchup's call sites
     land, and a guard that ships already exempted is not a guard."

⚠️ B083'S CALL SITES ARE WHAT MAKE IT PASSABLE, so the guard lands with them rather than with
the table. It lives here rather than in `test_today_tabs.py` because it is a statement about
`site/views/` as a whole and belongs to neither page.

⚠️ ONLY ONE DIRECTION IS ASSERTABLE AND THAT IS NOT AN OVERSIGHT. `site/views/` names 25
distinct views in `states.section` calls; `DATASETS` holds 11. The other 14 are pages nobody
has done this work for yet, and asserting the reverse would fail for a reason that has nothing
to do with dead copy. `test_today_tabs.py` guards that direction where it IS true — inside
Today, per module.
"""
import ast
from pathlib import Path

import pytest

VIEWS = Path(__file__).resolve().parents[1] / "site" / "views"

import sys                                                            # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))
from lib.datasets import DATASETS                                     # noqa: E402


def _section_views():
    """Every view named by a `states.section(...)` anywhere under site/views/.

    ⚠️ THE FIRST ARGUMENT, NOT THE `dataset=` KEYWORD. A view can be guarded by a section
    without carrying a caption — the Matchup header reads srv_game_weather that way on
    purpose, because the header reads two datasets and captioning it with one would be R-574's
    defect in a new place. The question this guard asks is whether the LABEL has a reader,
    and a section names the view either way.
    """
    named = {}
    for path in sorted(VIEWS.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "section"):
                continue
            if not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                named.setdefault(first.value, set()).add(path.name)
    return named


# 🚨 R-839/B110. ONE LABEL IS ORPHANED ON PURPOSE, AND THE EXEMPTION EXPIRES BY ITSELF.
#
# §3.3 is EXPAND → MIGRATE → CONTRACT, and the order is not negotiable: **the page stops
# reading the relation FIRST, and the publish drops it on a LATER round.** B110 deleted the
# Matchup page's `Game leaders` section (Marc's v03, *"Replace Game Leaders section by adding
# player cards"*), which is the MIGRATE. The CONTRACT — `site/lib/datasets.py:49`, the
# `src/publish_marts.py` entry and the 308,232-row table itself — is **session A's round**,
# and `site/lib/` is A's file that B must not reach into (§3 rule 3).
#
# ⚠️ SO THERE IS A WINDOW WHERE THE LABEL HAS NO READER, AND IT COSTS NOTHING: an unread
# published table is disk, while a published table removed under a page that still reads it
# is a broken page. The window is in the safe direction by construction.
#
# 🚨 AND AN EXEMPTION THAT OUTLIVES ITS CAUSE IS EXACTLY THE DEAD COPY THIS GUARD EXISTS TO
# FIND. So it is asserted to still be NEEDED: the moment A's round removes the label from
# `datasets.py`, the second assertion below goes red and this block must be deleted with it.
# **It cannot rot quietly, which is the only thing that makes it different from the test
# exemption the message below refuses.**
_MIGRATING = {"srv_game_team_leader"}


def test_every_dataset_label_has_a_reader():
    """🚨 THE DEAD-COPY DIRECTION, RESTORED.

    A label in `datasets.py` that no `states.section` names is copy nobody will ever see —
    and worse, it is copy that LOOKS like coverage when someone audits the table against the
    Excel export, which is exactly what Marc said he would use these captions for.
    """
    named = _section_views()
    orphans = sorted(set(DATASETS) - set(named) - _MIGRATING)
    assert not orphans, (
        "these datasets.py labels are named by no states.section under site/views/, so they "
        f"render nowhere: {orphans}. Either a page is missing the call site, or the label is "
        "dead copy — and which one it is, is Cowork's call rather than a test exemption.")


def test_the_MIGRATION_EXEMPTION_still_has_something_to_exempt():
    """🚨 THE EXEMPTION ABOVE IS TIME-BOXED BY THIS ASSERTION AND BY NOTHING ELSE (R-839).

    ⚠️ `test_every_dataset_label_has_a_reader` is an ABSENCE test, and an absence passes just
    as well when the thing doing the looking has been quietly narrowed — which is what a
    permanent exemption list is. This is the other half: **a name in `_MIGRATING` that is no
    longer in `datasets.py` means session A's contract step has LANDED**, so the window is
    closed and the exemption is now hiding a real orphan rather than a planned one.

    ✅ WHEN THIS GOES RED THE FIX IS TO DELETE `_MIGRATING` AND THIS TEST, not to edit the set.
    """
    stale = sorted(_MIGRATING - set(DATASETS))
    assert not stale, (
        f"{stale} is no longer a label in datasets.py, so the EXPAND → MIGRATE → CONTRACT "
        f"window this exemption covers has closed. Delete `_MIGRATING` and this test (R-839).")


def test_the_guard_would_notice_a_label_with_no_reader():
    """⚠️ THE GUARD IS TESTED BEFORE IT IS TRUSTED.

    Three rounds in four have found a test that could not fail. This one asserts an absence,
    and an absence passes just as well when the thing doing the looking is broken — so the
    lookup is fed a key that certainly has no call site, and must report it.
    """
    named = _section_views()
    assert "srv_a_view_that_does_not_exist" not in named
    orphans = sorted({"srv_a_view_that_does_not_exist"} - set(named))
    assert orphans == ["srv_a_view_that_does_not_exist"], \
        "the orphan calculation does not actually detect an orphan"


@pytest.mark.parametrize("view", sorted(DATASETS))
def test_each_label_is_front_of_house_copy(view):
    """AC-G.7 as amended: a reader is shown "Kickoff weather", never `srv_game_weather`."""
    label = DATASETS[view]
    assert label and not label.startswith("srv_"), \
        f"{view} label {label!r} is an identifier, not front-of-house copy"


def test_matchup_names_every_view_it_reads():
    """The Matchup half of R-528, asserted here because the file this guards is shared.

    ⚠️ srv_game_weather IS INCLUDED, and it is the one that would be missed: the header reads
    it without a `dataset=` caption, so a guard that looked for the keyword rather than the
    section would call it dead copy and be wrong.
    """
    named = _section_views()
    # ⚠️ `srv_game_team_leader` LEFT THIS LIST IN B110 (R-839) — the page's `Game leaders`
    # section was removed, so matchup.py genuinely no longer names it. The CARDS' relation,
    # `srv_game_team_leader_in_this_game`, is a DIFFERENT view and is read inside
    # `_post_game`'s own section; the two names differ only by a suffix, which is the trap
    # A128 and `_game_leaders`'s docstring both warn about.
    for view in ("srv_game", "srv_team_week", "srv_game_team",
                 "srv_game_travel", "srv_drive", "srv_game_weather"):
        assert "matchup.py" in named.get(view, set()), \
            f"matchup.py does not name {view} in any states.section"
