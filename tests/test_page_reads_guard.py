"""The guard on R-623's guard.

⚠️ ci/check_page_reads.py runs in CI and not in pytest, exactly as check_layering and
check_publish_build_agreement do. This file is the part that has to run everywhere: that the
check still PASSES on this tree, and that its exemption list has not quietly become the
blanket A088 warned about — "a check that needs a blanket exemption on day one is the third
silent guard".
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ci"))

# 🚨 BOUND AT IMPORT, BEFORE ANY TEST CAN MONKEYPATCH IT — AND THIS IS NOT HYPOTHETICAL.
# test_heartbeat.py replaces `subprocess.run` with a stub returning returncode 0, and the
# patch leaks into this file in a full run: `test_the_check_can_actually_fail` passed alone
# and failed in the suite, reporting "the check passed with a column removed" when the check
# had never been invoked at all. ⚠️ THE NEGATIVE TEST WAS ITSELF DEFEATED BY A STUB — the same
# shape as A085's harness failing AS the page, one layer up, and it is the reason this line
# exists rather than a plain `subprocess.run` call below.
_REAL_RUN = subprocess.run


def test_the_check_passes_on_this_tree():
    result = _REAL_RUN([sys.executable, "ci/check_page_reads.py"],
                       cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_exemption_carries_a_reason():
    """⚠️ THE WEEKLY_BY_DESIGN PATTERN, AND A088 PROVED IT IS ENFORCED IN BOTH DIRECTIONS.

    To add a name you must be able to finish "the page reads this and no query selects it
    because…". A bare set of names is a blanket wearing a list's clothes.
    """
    import check_page_reads as check
    assert check.PROVIDED_BY_THE_PAGE, "the exemption list vanished — that is not an improvement"
    for name, reason in check.PROVIDED_BY_THE_PAGE.items():
        assert isinstance(reason, str) and len(reason) > 30, \
            f"{name!r} is exempt with no real reason: {reason!r}"


def test_the_exemption_list_is_small_enough_to_read():
    """A guard whose exemption list grows without anyone noticing has become a suppression
    list. Four today; this fails long before it becomes a blanket."""
    import check_page_reads as check
    assert len(check.PROVIDED_BY_THE_PAGE) <= 10, (
        f"{len(check.PROVIDED_BY_THE_PAGE)} exemptions — read them and ask whether the check "
        f"is still checking anything")


def test_the_check_can_actually_fail():
    """🚨 R-157, and four rounds in five have found a test that could not fail.

    Runs the check against a scratch copy of the tree with a real column removed from
    matchup's COLUMNS — B084's defect, reintroduced — and asserts it goes red and NAMES the
    column.
    """
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "repo"
        shutil.copytree(ROOT / "site", scratch / "site")
        shutil.copytree(ROOT / "ci", scratch / "ci")
        target = scratch / "site" / "views" / "matchup.py"
        source = target.read_text()
        broken = source.replace("    home_mascot, away_mascot,\n", "", 1)
        assert broken != source, "the fixture no longer matches matchup.py — update this test"
        target.write_text(broken)
        result = _REAL_RUN([sys.executable, "ci/check_page_reads.py"],
                           cwd=scratch, capture_output=True, text=True)
        assert result.returncode == 1, "the check passed with a column removed"
        assert "home_mascot" in result.stderr and "away_mascot" in result.stderr, \
            f"it failed without naming the column: {result.stderr}"


def test_the_as_of_exemption_list_is_empty_and_stays_honest():
    """R-564's other half. ⚠️ EMPTY TODAY, AND THAT IS THE STRONGEST STATE FOR IT: all sixteen
    modules calling as_of_caption select as_of_ts, so nothing needs forgiving. If an entry ever
    appears it carries a reason, the same rule as PROVIDED_BY_THE_PAGE — A088: "without an
    exemption list carrying a reason per entry, the check gets a blanket skip the first time it
    is inconvenient and becomes the third silent guard."
    """
    import check_page_reads as check
    for name, reason in check.AS_OF_EXEMPT.items():
        assert isinstance(reason, str) and len(reason) > 30, \
            f"{name!r} is exempt from the as-of check with no real reason: {reason!r}"
    assert len(check.AS_OF_EXEMPT) <= 3, (
        f"{len(check.AS_OF_EXEMPT)} pages exempt from AC-G.35 — read them and ask whether the "
        f"check is still checking anything")


def test_the_as_of_check_can_actually_fail():
    """🚨 PART 5's BREAK FOR R-564's OTHER HALF, run against a scratch copy.

    ⚠️ IT REMOVES THE COLUMN FROM EVERY QUERY IN THE MODULE, because the check is a UNION: a
    module with two queries passes if either selects it. rankings.py has two, and removing one
    correctly leaves the check green — which was worth discovering by running the break rather
    than by assuming a single edit was enough.
    """
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "repo"
        shutil.copytree(ROOT / "site", scratch / "site")
        shutil.copytree(ROOT / "ci", scratch / "ci")
        target = scratch / "site" / "views" / "rankings.py"
        source = target.read_text()
        assert source.count("as_of_ts") >= 2, "rankings.py changed — update this test"
        target.write_text(source.replace("as_of_ts", "as_of_ts_GONE"))
        result = _REAL_RUN([sys.executable, "ci/check_page_reads.py"],
                           cwd=scratch, capture_output=True, text=True)
        assert result.returncode == 1, "the check passed with as_of_ts removed"
        assert "as_of_caption with no as_of_ts" in result.stderr, \
            f"it failed without naming the cause: {result.stderr}"
