"""The Excel Export page — what it promises the file will contain.

A download is the one action on this site whose result the user cannot inspect before
committing to it. That makes the preview's honesty the page's whole job, and it makes any
sentence describing the workbook a claim that has to stay true as the workbook changes.

It did not. The intro named all seven tabs — "schedule, results, the odds board, model
edges, standings, model provenance and the field definitions" — and had been wrong from the
day only Schedule shipped, through every round of Excel work, until Scores landed beside it.
Nothing caught it because nothing tested this page at all.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from lib import workbook                              # noqa: E402
from views import export                              # noqa: E402

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "export.py").read_text(
    encoding="utf-8")


def test_the_description_names_exactly_the_sheets_that_ship():
    """Derived from SHEETS, so converting a pending sheet updates the sentence by moving one
    name in workbook.py."""
    described = export._sheet_list()
    for sheet in workbook.SHEETS:
        assert sheet.name.lower() in described, sheet.name
    for sheet in workbook.PENDING_SHEETS:
        assert sheet.name.lower() not in described, (
            f"{sheet.name} is described as shipping and does not")
    assert described == "schedule and scores", described


def test_no_sheet_name_is_hardcoded_into_the_pages_prose():
    """THE GUARD THAT WOULD HAVE CAUGHT THE ORIGINAL SENTENCE.

    Asserting the current wording is a change-detector; asserting that the wording is not
    hand-written is the rule. A pending sheet's name appearing in a string literal on this
    page means somebody has described the file from memory again.

    Comments are exempt — the reason the old sentence was wrong is worth recording where the
    fix is, and quoting it there is not the same as promising it to a user.
    """
    prose = "\n".join(line for line in SOURCE.splitlines()
                      if not line.lstrip().startswith("#"))
    for sheet in workbook.PENDING_SHEETS:
        assert sheet.name.lower() not in prose.lower(), (
            f"{sheet.name!r} is written into this page's prose; build the list from "
            f"workbook.SHEETS instead")


def test_the_page_names_every_pending_sheet_before_the_download():
    """Two kinds of absence, and only one of them used to be shown.

    "No rows for your filters" comes back if you widen the scope. "This tab does not exist
    yet" does not, and a reader who remembered the Odds tab had to download the file to find
    that out. Both were already on the workbook's Index; the point of the preview is that you
    do not have to get the file first.
    """
    assert "PENDING_SHEETS" in SOURCE and "PENDING_REASON" in SOURCE
    assert workbook.PENDING_SHEETS, "nothing pending — this test now proves nothing"


def test_the_error_state_names_every_view_the_preview_reads():
    """`states.section` prints this string when a query raises. Naming srv_game on a failure
    that came from srv_game_team sends the reader to the wrong object."""
    match = re.search(r'states\.section\((.*?)\):', SOURCE, re.S)
    assert match, "the section call moved"
    expression = match.group(1)
    assert "workbook.SHEETS" in expression, (
        "the error label is hardcoded; it must be derived from the sheets actually read")
    assert "srv_game" not in expression, expression


def test_the_preview_and_the_build_read_the_same_sheets():
    """The preview counts rows by running the real queries through the builder's own reader.

    A second implementation of "what will be in the file" is a second answer waiting to
    diverge — and it would diverge silently, because the preview is checked against the file
    by nobody.
    """
    assert "workbook.read_sheet(" in SOURCE
    assert "for sheet in workbook.SHEETS" in SOURCE
    # And the build itself takes the same scope the preview did.
    assert "workbook.build(" in SOURCE


# ==========================================================================================
# ACTUALLY RUNNING THE PAGE
# ==========================================================================================

class _Recorder:
    """A stand-in for `st` that records what the page rendered.

    NOTHING IN THIS REPO EXECUTES A PAGE BODY. `ci/site_smoke.py` boots app.py and stubs
    st.navigation, which proves the entrypoint builds the right nav and deliberately stops
    short of running a page — "executing a page would need a database". So a NameError or a
    bad f-string inside `body()` reaches production, and the two outages this project has had
    on the site were both of that shape: green tests, healthy database, blank page.

    Stubbing `st` costs a few lines and closes it for the one page whose entire job is to
    describe a file the user cannot see first.
    """

    def __init__(self):
        self.text = []

    def _record(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, str):
                self.text.append(arg)
        return False

    def __getattr__(self, _name):
        return self._record

    def spinner(self, *_a, **_k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    @property
    def rendered(self):
        return "\n".join(self.text)


def test_the_page_body_runs_and_says_what_the_workbook_holds(monkeypatch):
    """Execute `body()` end to end against stubbed reads, and read what it wrote."""
    import contextlib
    from types import SimpleNamespace

    scope = SimpleNamespace(season=2025, week=2, season_type="regular",
                            conference=None, division="fbs",
                            describe=lambda: "2025 week 2")
    recorder = _Recorder()
    monkeypatch.setattr(export, "st", recorder)
    monkeypatch.setattr(export, "filters",
                        SimpleNamespace(game_scope=lambda: scope, clear=lambda: None))
    monkeypatch.setattr(export, "states", SimpleNamespace(
        section=lambda *_a, **_k: contextlib.nullcontext(),
        empty=lambda *a, **k: recorder._record(*a)))

    # Real row counts at the two real grains, so the caption about doubling is exercised
    # against numbers that actually double.
    counts = {"Schedule": 83, "Scores": 166}

    def fake_read(sheet, *_a, **_k):
        import pandas as pd
        rows = counts[sheet.name]
        return workbook.SheetRead(pd.DataFrame({"x": range(rows)}), None, rows)

    monkeypatch.setattr(workbook, "read_sheet", fake_read)
    export.body(page=None)

    out = recorder.rendered
    assert "schedule and scores" in out
    assert "83 row(s)" in out and "166 row(s)" in out
    assert "srv_game_team" in out
    # The grain caption, because 83 beside 166 reads as a defect without it.
    assert "one row per **team** per game" in out
    # And every pending sheet is named before the button, not only on the Index.
    for sheet in workbook.PENDING_SHEETS:
        assert sheet.name in out, sheet.name
