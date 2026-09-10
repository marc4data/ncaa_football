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


def test_every_dataset_label_has_a_reader():
    """🚨 THE DEAD-COPY DIRECTION, RESTORED.

    A label in `datasets.py` that no `states.section` names is copy nobody will ever see —
    and worse, it is copy that LOOKS like coverage when someone audits the table against the
    Excel export, which is exactly what Marc said he would use these captions for.
    """
    named = _section_views()
    orphans = sorted(set(DATASETS) - set(named))
    assert not orphans, (
        "these datasets.py labels are named by no states.section under site/views/, so they "
        f"render nowhere: {orphans}. Either a page is missing the call site, or the label is "
        "dead copy — and which one it is, is Cowork's call rather than a test exemption.")


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
    for view in ("srv_game", "srv_team_week", "srv_game_team", "srv_game_team_leader",
                 "srv_game_travel", "srv_drive", "srv_game_weather"):
        assert "matchup.py" in named.get(view, set()), \
            f"matchup.py does not name {view} in any states.section"
