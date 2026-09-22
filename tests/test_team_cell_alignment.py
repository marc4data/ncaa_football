"""A201 PART 1 — the team name sits on the same line as its logo, rank and record.

> **MARC, v13:** *"Team Name isn't vertically aligned with the Logo, Rank and Record"*

🚨 THE PROOF IS A BROWSER MEASUREMENT AND IT IS NOT IN THIS FILE. A unit test cannot see where
a glyph lands. 📊 Measured by a Range over each text node at 1440 and 1100 with the sidebar
open, the worst centre spread inside a team cell went **5.5px → 1.0px**, across 142 cells on
Schedule and 32 on Today; Matchup has no `.cfdb-table` team cells and is untouched. The
numbers live in `claude_work/cfdb_report_A201_slate_rows_and_alignment.md`.

What this file holds is the DECISION — which declaration does it, and that nothing else was
nudged to compensate.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()


def rule(selector: str) -> str:
    """The declaration block for a selector, as written."""
    start = THEME.index(selector)
    return THEME[start:THEME.index("}", start)]


def test_the_name_is_centred_with_the_rest_of_the_cell():
    """⚠️ THE CAUSE IS THIS RULE'S OWN `display:inline-block`, which takes an explicit
    alignment. `bottom` put the name's BOX bottom on the line box, so a 19px name beside a
    28px logo hung 4.5px low."""
    block = rule(".cfdb-table .cfdb-team {")
    assert "vertical-align:middle" in block
    assert "vertical-align:bottom" not in block


def test_the_ellipsis_cluster_travelled_with_it_untouched():
    """🚨 A164 TESTED THAT CLUSTER FOR A DIFFERENT BUG AND EXONERATED IT. Dropping it here to
    "clean up" the rule would reintroduce a defect somebody already measured away."""
    block = rule(".cfdb-table .cfdb-team {")
    for declaration in ("display:inline-block", "max-width:100%", "white-space:nowrap",
                        "overflow:hidden", "text-overflow:ellipsis"):
        assert declaration in block, f"{declaration} was dropped from the rule"


def test_nothing_was_nudged_to_compensate():
    """> **A201's prompt:** *"align on one baseline — vertical centring of the row, not
    per-element nudges."*

    🚨 A `position:relative; top:-2px` ON THE NAME WOULD ALSO "FIX" THE RENDER and would break
    the moment a font or a logo size changed. The fix is one alignment declaration and no
    offsets.
    """
    block = rule(".cfdb-table .cfdb-team {")
    assert "top:" not in block and "margin-top" not in block
    assert "transform" not in block
    # and the three siblings keep the baseline rule they already shared
    siblings = rule(".cfdb-team, .cfdb-rank, .cfdb-team-record {")
    assert "vertical-align:baseline" in siblings


def test_the_logo_and_record_rules_were_left_alone():
    """✅ THE CHEAPER WIN WAS DECLINED ON PURPOSE. Centring every element as well reaches a
    0.5px spread instead of 1.0px — and would have to touch `.cfdb-logo` and `.cfdb-logo-box`,
    which the game cards, the legend and Matchup all read, to buy half a pixel nobody sees.
    """
    assert "vertical-align:middle" in rule(".cfdb-logo {"), (
        "the logo's own alignment is unchanged")
    # the shared team/rank/record rule must not have grown a table-specific override
    assert not re.search(r"\.cfdb-table\s+\.cfdb-rank\s*\{[^}]*vertical-align", THEME)
    assert not re.search(r"\.cfdb-table\s+\.cfdb-team-record\s*\{[^}]*vertical-align", THEME)
