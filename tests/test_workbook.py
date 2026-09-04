"""The Excel deliverable, checked against its twelve acceptance criteria.

The workbook is the feature closest to the licence line and the only artifact that leaves
the site, so most of these assert obligations rather than behaviour: attribution present on
every sheet, the model disclaimer on every sheet carrying a prediction, and no code path
that widens scope beyond the filters.

Built against a stubbed query so the whole thing runs in CI without a database. That is not
a compromise — the properties under test are properties of the WRITER, and a fixture with
one row of each awkward type (null, NaN, a tz-aware timestamp, an empty string, a bool)
exercises them harder than real data does.
"""
import math
import sys
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from lib import workbook                                # noqa: E402
from lib.query import check_contract                    # noqa: E402


def _frame(fields):
    """Two rows per sheet: one populated, one carrying every awkward value at once.

    The second row is the point. A null, a NaN, a tz-aware timestamp and an empty string
    are the four things that turn into either an exception at write time or a repair prompt
    at open time, and all four arrive from real serving views.
    """
    populated, awkward = {}, {}
    for field in fields:
        if field.endswith("_ts") or field.endswith("_date") or field.endswith("_et"):
            populated[field] = pd.Timestamp("2026-09-05 19:30", tz="UTC")
            awkward[field] = pd.NaT
        elif field.startswith("is_"):
            populated[field] = True
            awkward[field] = False
        elif field in ("week", "season", "games", "attendance"):
            populated[field] = 7
            awkward[field] = None
        elif ("point" in field or "margin" in field or "spread" in field
              or "edge" in field or "prob" in field or "pct" in field
              or "score" in field or "total" in field or "loss" in field
              or field.endswith("_rank") or field.endswith("moneyline")
              or field in ("wins", "losses", "ties", "win_pct", "error", "n")):
            populated[field] = -3.5
            awkward[field] = float("nan")
        else:
            populated[field] = "text"
            awkward[field] = ""
    return pd.DataFrame([populated, awkward])


@pytest.fixture
def built(monkeypatch):
    """A real workbook, from stubbed reads.

    CFDB_SITE_HOST is set EXPLICITLY rather than inherited. A test that behaves one way on a
    laptop with a populated .env and another way on a CI runner is the class of test
    conftest.py exists to prevent, and the hyperlink work made this module sensitive to it.
    """
    monkeypatch.setenv("CFDB_SITE_HOST", "https://cfdb.example")

    def fake_query(sql, params=None):
        # Every stubbed query still goes through the contract, so a sheet that violates
        # G-1/G-2 fails here rather than in production.
        check_contract(sql)
        for sheet in workbook.SHEETS:
            if f"from {sheet.view}" in " ".join(sql.split()):
                # The SELECTED fields, not just the visible columns: the sheet also pulls
                # what it derives from and what it links with, and a fixture missing those
                # makes the hyperlinks look absent when they are merely unstubbed.
                df = _frame(sorted(set(sheet.fields) | set(sheet.selected_fields)))
                if "game_id" in df.columns:
                    df["game_id"] = [401752000, 401752001]
                # Realistic verdicts, so the mark rendering is actually exercised. Without
                # them every verdict cell is the no-data dash and any test about the marks
                # passes while proving nothing — which is exactly what the colour test
                # refused to do.
                # Distinct team and venue names, because the alignment rule now depends on
                # CARDINALITY: with both rows reading "text" the fixture made a team column
                # look like a two-value category and centred it, which is not what real data
                # does. A fixture that misrepresents the shape of the data cannot test a rule
                # that reads the shape of the data.
                for column, values in (("away_team_display", ["Rice", "Auburn"]),
                                       ("home_team_display", ["Louisville", "Texas"]),
                                       ("venue_display", ["Cardinal Stadium", "DKR"]),
                                       ("winner", ["Louisville", "Texas"]),
                                       ("upset_level", ["upset", "none"]),
                                       ("winner_covered_close", ["yes", "no"]),
                                       ("over_met", ["yes", "no"]),
                                       ("favorite_covered", ["yes", "no_favorite"])):
                    if column in df.columns:
                        df[column] = values
                return df
        return pd.DataFrame([{"model_version": "abc123", "model_name": "stub"}])

    monkeypatch.setattr(workbook, "query", fake_query)
    payload, index_rows, omitted = workbook.build(2026, 8, "regular", None)
    from openpyxl import load_workbook
    return payload, load_workbook(BytesIO(payload)), index_rows, omitted


# --- AC-15.6: the file opens ------------------------------------------------------------

def test_the_workbook_is_a_structurally_valid_xlsx(built):
    payload, _, _, _ = built
    archive = zipfile.ZipFile(BytesIO(payload))
    assert archive.testzip() is None
    assert "[Content_Types].xml" in archive.namelist()


def test_no_cell_holds_a_value_excel_refuses_to_open(built):
    """NaN, infinity and a tz-aware datetime each produce a repair prompt or an exception.

    The file is structurally valid XML in the NaN case and Excel still refuses it, which is
    why this checks values rather than trusting that the save succeeded.
    """
    _, book, _, _ = built
    for name in book.sheetnames:
        for row in book[name].iter_rows():
            for cell in row:
                value = cell.value
                if isinstance(value, float):
                    assert not math.isnan(value), f"{name}!{cell.coordinate}"
                    assert not math.isinf(value), f"{name}!{cell.coordinate}"
                if isinstance(value, datetime):
                    assert value.tzinfo is None, f"{name}!{cell.coordinate}"


def test_sheet_names_are_legal(built):
    """Over 31 characters, or any of []:*?/\\, and Excel rewrites or rejects the name."""
    _, book, _, _ = built
    for name in book.sheetnames:
        assert len(name) <= 31, name
        assert not set(name) & set(r"[]:*?/\\"), name
    assert len(set(book.sheetnames)) == len(book.sheetnames)


# --- AC-15.3 / AC-15.4: the obligations that travel with the file -----------------------

def test_every_sheet_carries_cfbd_attribution_in_a_fixed_cell(built):
    _, book, _, _ = built
    for name in book.sheetnames:
        assert "CollegeFootballData.com" in str(
            book[name].cell(workbook.ROW_CREDIT, 1).value), name


def test_every_sheet_that_declares_the_disclaimer_carries_it(built):
    """AC-15.4 was "every sheet with predictions writes the disclaimer". R-221 split that in
    two, and the split is the point: Schedule STILL CARRIES PREDICTIONS and no longer writes
    the sheet-level line, because attribution now travels per row instead.

    So the assertion follows `sheet_disclaimer`, and the test below is what makes removing
    the line safe rather than merely requested.
    """
    _, book, _, _ = built
    for sheet in workbook.SHEETS:
        if sheet.name not in book.sheetnames:
            continue
        tab = book[sheet.name]
        text = str(tab.cell(workbook.ROW_DISCLAIMER, 1).value)
        if sheet.sheet_disclaimer:
            assert "NOT CollegeFootballData.com predictions" in text, sheet.name
        else:
            assert "NOT CollegeFootballData.com predictions" not in text, sheet.name


def test_a_sheet_without_the_disclaimer_must_carry_attribution_per_row(built):
    """R-221, AND THIS IS THE LOAD-BEARING HALF.

    Removing a licence statement from a file that travels off the site, while the numbers it
    covered are still on the sheet, is not a formatting change. What makes it safe is that
    attribution is carried AS DATA, per row, from dim_model_version — which is strictly
    stronger than a line in row 2, because it survives filtering, sorting and copy-paste.

    So a sheet that drops the sheet-level line must have the column. If it ever has neither,
    the workbook ships unattributed predictions.
    """
    for sheet in workbook._ALL_SHEETS:
        if sheet.has_predictions and not sheet.sheet_disclaimer:
            assert "attribution" in sheet.fields, (
                f"{sheet.name} carries predictions, writes no disclaimer, and has no "
                f"attribution column — that is an unattributed prediction leaving the site")


def test_no_prediction_cell_is_populated_beside_a_blank_attribution(built):
    """The runtime half of the same guarantee, on the built file rather than the definition.

    Attribution being null where there is no model row is CORRECT — no prediction, nothing to
    attribute. The failure case is the other way round: a populated `Pred margin` beside a
    blank `Attribution`.
    """
    _, book, _, _ = built
    schedule = next(s for s in workbook.SHEETS if s.name == "Schedule")
    tab = book["Schedule"]
    header = workbook.header_row(1)
    labels = {tab.cell(header, i).value: i for i in range(1, tab.max_column + 1)}
    prediction_columns = ["Pred margin", "Home win prob", "Confidence", "Model",
                          "Model version"]
    assert "Attribution" in labels and schedule.sheet_disclaimer is False
    for row in range(header + 1, tab.max_row + 1):
        attributed = tab.cell(row, labels["Attribution"]).value
        for column in prediction_columns:
            value = tab.cell(row, labels[column]).value
            if value not in (None, ""):
                assert attributed not in (None, ""), (
                    f"row {row}: {column} is populated and Attribution is blank")


def test_the_out_of_sample_flag_is_a_column_not_a_footnote(built):
    """AC-15.4. A workbook gets sorted and filtered; a sheet-level note does not survive
    that, and the rows it applied to end up looking like ordinary predictions."""
    # Asserted on every sheet that carries predictions, not on one named sheet — the named
    # sheet stopped shipping and the test went looking for something that was not there.
    predicting = [s for s in workbook._ALL_SHEETS if s.has_predictions]
    assert predicting
    for sheet in predicting:
        assert "is_out_of_sample_week" in sheet.fields, sheet.name


# --- AC-15.1 / AC-15.2: the scope rule --------------------------------------------------

def test_every_sheet_reads_exactly_one_serving_view(built):
    """AC-15.2, enforced by the same contract the pages use rather than by reading them."""
    for sheet in workbook.SHEETS:
        assert check_contract(" ".join(sheet.sql.split())) == sheet.view


def test_scoped_sheets_filter_on_the_season(built):
    """AC-15.1. The two unscoped sheets are provenance — which models produced the
    predicted columns, and what the fields mean — not additional data."""
    # Walks _ALL_SHEETS, INCLUDING the six that do not ship yet. Their SQL is still real
    # work and still under the CI query checker; letting the property lapse while they sit
    # out of the shipping list is how they would come back broken.
    unscoped = {s.name for s in workbook._ALL_SHEETS if not s.scoped}
    assert unscoped == {"Model performance", "Data dictionary"}
    for sheet in workbook._ALL_SHEETS:
        if sheet.scoped:
            assert ":season" in sheet.sql, sheet.name


def test_no_sheet_offers_an_unbounded_export():
    """Every query carries a LIMIT, and none reads raw or staging."""
    for sheet in workbook.SHEETS:
        flat = " ".join(sheet.sql.split()).lower()
        assert " limit " in flat, sheet.name
        assert "raw." not in flat and "staging." not in flat, sheet.name


# --- AC-15.5: an omission is named ------------------------------------------------------

def test_an_empty_sheet_is_omitted_rather_than_shipped_blank(monkeypatch):
    def empty_query(sql, params=None):
        check_contract(sql)
        return pd.DataFrame()
    monkeypatch.setattr(workbook, "query", empty_query)
    payload, index_rows, omitted = workbook.build(2026, 1, "regular", None)
    assert index_rows == []
    assert {name for name, _ in omitted} == {s.name for s in workbook.SHEETS}
    from openpyxl import load_workbook
    book = load_workbook(BytesIO(payload))
    # The index still exists and still says what happened. A workbook with no tabs at all
    # would be indistinguishable from a failed download.
    assert book.sheetnames == ["Index"]
    text = "\n".join(str(c.value) for row in book["Index"].iter_rows() for c in row)
    for sheet in workbook.SHEETS:
        assert sheet.view in text


def test_a_real_failure_is_not_reported_as_an_omission(monkeypatch):
    """A connection or permission error is not "no rows in this scope".

    The first version of the reader caught everything and reported every sheet as omitted,
    which produced a workbook calmly stating the data was unavailable while the real
    problem was that nothing could be read at all.
    """
    def broken(sql, params=None):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(workbook, "query", broken)
    with pytest.raises(RuntimeError):
        workbook.build(2026, 1, "regular", None)


# --- AC-15.7 / AC-15.12: it is a spreadsheet, not a picture of one ----------------------

def test_numeric_cells_are_numbers_with_the_sites_precision(built):
    _, book, _, _ = built
    checked = 0
    for sheet in workbook.SHEETS:
        if sheet.name not in book.sheetnames:
            continue
        tab = book[sheet.name]
        first_data = workbook.first_data_row(2 if sheet.sheet_disclaimer else 1)
        for index, (field, _) in enumerate(sheet.columns, start=1):
            cell = tab.cell(first_data, index)
            if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                assert cell.number_format == workbook.number_format(field), field
                checked += 1
    assert checked > 10


def test_precision_comes_from_the_same_table_the_site_renders_with():
    """AC-G.31 in the workbook. A column that reads 1 dp on screen and 2 dp in Excel is
    two different claims about how precisely the number is known."""
    assert workbook.number_format("spread") == "#,##0.0"
    assert workbook.number_format("margin_mae") == "#,##0.00"
    assert workbook.number_format("home_win_probability") == "#,##0.000"
    # Counts are counts. A decimal point on an attendance makes it look measured.
    assert workbook.number_format("attendance") == "#,##0"
    assert workbook.number_format("home_moneyline") == "+#,##0;-#,##0"


def test_sheets_are_workable_not_merely_readable(built):
    """AC-15.12: freeze panes, filtering, and conditional formatting where it earns its
    place. The deliverable is meant to be worked in.

    THE FILTER NOW COMES FROM THE TABLE, NOT FROM `auto_filter` (R-182 trap 1). openpyxl
    documents that a table must not overlap the worksheet's autofilter, and an overlap is
    the "we found a problem with some content" repair prompt AC-15.6 forbids. So the
    affordance is asserted, and the thing that would collide with it is asserted ABSENT.
    """
    _, book, _, _ = built
    for sheet in workbook.SHEETS:
        if sheet.name not in book.sheetnames:
            continue
        tab = book[sheet.name]
        from openpyxl.utils import get_column_letter
        expected_row = workbook.first_data_row(2 if sheet.sheet_disclaimer else 1)
        expected_col = get_column_letter(sheet.freeze_column())
        assert tab.freeze_panes == f"{expected_col}{expected_row}", sheet.name
        assert not tab.auto_filter.ref, (
            f"{sheet.name} has a worksheet autofilter as well as a Table; overlapping them "
            f"is what produces Excel's repair prompt")
        assert len(tab.tables) == 1, f"{sheet.name} should carry exactly one Table"
    assert len(book["Schedule"].conditional_formatting._cf_rules) > 0


def test_an_empty_string_becomes_an_empty_cell(built):
    """The pack writes '' where it has no confidence bucket. An empty-string cell is not an
    empty cell: it breaks COUNTBLANK and sorts ahead of real values."""
    assert workbook._clean("") is None
    assert workbook._clean("   ") is None
    assert workbook._clean("high") == "high"


def test_null_and_zero_stay_distinguishable_in_the_workbook():
    """AC-G.32 does not stop applying because the output is a file."""
    assert workbook._clean(None) is None
    assert workbook._clean(float("nan")) is None
    assert workbook._clean(0) == 0
    assert workbook._clean(0.0) == 0.0


# --- AC-15.9 / AC-15.10: the file explains itself ---------------------------------------

def test_the_index_states_scope_timestamp_counts_and_model_version(built):
    _, book, index_rows, _ = built
    text = "\n".join(str(c.value) for row in book["Index"].iter_rows() for c in row)
    assert "Generated (UTC)" in text
    assert "season 2026" in text and "week 8" in text
    assert "Model version(s)" in text
    for entry in index_rows:
        assert entry.name in text and entry.view in text


def test_the_filename_encodes_its_own_scope():
    """AC-15.10. A folder of files called export.xlsx is a folder nobody can tell apart,
    and scope is the single most important fact about an export designed to be bounded."""
    stamp = datetime(2026, 8, 20, tzinfo=timezone.utc)
    assert workbook.filename(2026, 8, stamp) == "cfdb_week08_2026_20260820.xlsx"
    assert workbook.filename(2026, None, stamp) == "cfdb_season_2026_20260820.xlsx"


def test_no_duplicate_column_headers_on_any_sheet():
    """Two columns headed "Model" is merely cluttered on a web page and unusable in a
    spreadsheet — a filter dropdown cannot tell them apart. Found in the Edges page by
    building the export from its columns."""
    for sheet in workbook.SHEETS:
        labels = [label for _, label in sheet.columns]
        assert len(labels) == len(set(labels)), f"{sheet.name}: {labels}"


def test_export_labels_agree_with_the_site(built):
    """AC-15.8. Where a page shows the same field, it shows it under the same name.

    Compared per (VIEW, field), not per field. The first version keyed on the field name
    alone and reported a mismatch on `market`, which is a composite spread-and-model cell
    on Today and a genuine srv_edge_finder column on Edges — two different things sharing a
    name. A test that cannot tell those apart teaches you to ignore it.

    The cells themselves cannot be shared: the site renders a team as a logo plus a name in
    one cell, the workbook writes the display name. The LABEL is what a reader carries
    between the two, so the label is what is checked.
    """
    import re
    from lib.registry import PAGES
    site = Path(__file__).resolve().parents[1] / "site"

    view_labels = {}
    for page in PAGES:
        path = site / "views" / f"{page.key}.py"
        if not page.view or not path.exists():
            continue
        for field, label in re.findall(r'Col\(\s*"(\w+)"\s*,\s*"([^"]*)"', path.read_text()):
            view_labels.setdefault(page.view, {}).setdefault(field, set()).add(label)

    mismatches = []
    for sheet in workbook.SHEETS:
        shown_on_page = view_labels.get(sheet.view, {})
        for field, label in sheet.columns:
            shown = shown_on_page.get(field)
            if shown and label not in shown and field not in workbook.EXPORT_ONLY_LABELS:
                mismatches.append((sheet.name, field, label, sorted(shown)))
    assert not mismatches, mismatches


def test_every_declared_label_divergence_is_still_real():
    """A documented exception that no longer diverges is stale documentation.

    Without this, EXPORT_ONLY_LABELS becomes a list nobody prunes, and the next genuine
    mismatch gets waved through because "it is probably one of those".
    """
    import re
    from lib.registry import PAGES
    site = Path(__file__).resolve().parents[1] / "site"

    view_labels = {}
    for page in PAGES:
        path = site / "views" / f"{page.key}.py"
        if not page.view or not path.exists():
            continue
        for field, label in re.findall(r'Col\(\s*"(\w+)"\s*,\s*"([^"]*)"', path.read_text()):
            view_labels.setdefault(page.view, {}).setdefault(field, set()).add(label)

    for field in workbook.EXPORT_ONLY_LABELS:
        # TWO SHAPES OF DIVERGENCE, and the second was missed until R-101 produced one.
        #
        #   different  the site has a column for the field under another header
        #   absent     the site does not surface the field as a column at ALL
        #
        # The original version only knew the first, so when R-101 folded the neutral-site
        # glyph into the shared Game column this test read "no longer differs" and asked for
        # the exception to be dropped — when the divergence had in fact just got wider. An
        # exception is stale only when the site and the sheet AGREE on a header.
        diverges = any(
            field not in view_labels.get(sheet.view, {})
            or label not in view_labels[sheet.view][field]
            for sheet in workbook._ALL_SHEETS
            for name, label in sheet.columns if name == field)
        # _ALL_SHEETS, not SHEETS: an exception belonging to a sheet that is written but not
        # yet SHIPPED is still live documentation, and pruning it now would mean rediscovering
        # the same divergence when that sheet is converted.
        exported = any(name == field
                       for sheet in workbook._ALL_SHEETS for name, _ in sheet.columns)
        assert exported, f"{field} is not exported at all; drop the exception"
        assert diverges, f"{field} no longer differs from the site; drop the exception"


# === R-184 / R-196: the scope the user asked for, and the truth about what was written ====
#
# These are the Part 1 defect tests. Every one of them is negative-tested in
# `tests/test_workbook_scope_negatives.py`, because the failure being fixed here is
# specifically a check that agreed with a wrong answer.

GAME_SHEETS = [s for s in workbook.SHEETS if s.view == "srv_game"]


def _division_aware_query(recorder=None, in_scope=None):
    """A stub that HONOURS the division parameter instead of ignoring it.

    A stub that returns the same rows whatever it is asked is how this defect survived: the
    page, the preview and the file all agreed, and none of them had applied the filter. So
    this fake behaves like the database on the one axis under test — it drops the non-FBS
    row when the caller binds a division other than 'all'.
    """
    def fake_query(sql, params=None):
        check_contract(sql)
        flat = " ".join(sql.split())
        if recorder is not None:
            recorder.append((flat, dict(params or {})))
        for sheet in workbook.SHEETS:
            if f"from {sheet.view}" in flat:
                df = _frame(sorted(set(sheet.fields) | set(sheet.selected_fields)))
                if "game_id" in df.columns:
                    df["game_id"] = [401752000, 401752001]
                if sheet.view == "srv_game":
                    # Row 0 is an FBS game, row 1 is two non-FBS teams.
                    df["is_fbs_game"] = [True, False]
                    df["home_classification"] = ["fbs", "ii"]
                    df["away_classification"] = ["fbs", "iii"]
                    if (params or {}).get("division", "all") != "all":
                        df = df[df["is_fbs_game"]].reset_index(drop=True)
                if in_scope is not None:
                    df["rows_in_scope"] = in_scope
                return df
        return pd.DataFrame([{"model_version": "abc123", "model_name": "stub"}])
    return fake_query


def test_division_reaches_the_query_as_a_bound_parameter(monkeypatch):
    """THE DEFECT ITSELF. `build()` took four of GameScope's five filters, so `division` was
    dropped on the floor at `export.py:58` and again at `:86`.

    Asserted on the BINDING rather than on the SQL text, because the SQL was never the
    problem — the predicate can be perfectly written and still never receive a value.
    """
    seen = []
    monkeypatch.setattr(workbook, "query", _division_aware_query(recorder=seen))
    workbook.build(2026, 8, "regular", None, "fbs")

    bound = [params for sql, params in seen if "from srv_game" in sql]
    assert bound, "no srv_game sheet was read at all"
    for params in bound:
        assert params.get("division") == "fbs", (
            "the division filter never reached the query; this is R-184 exactly")


def test_a_workbook_scoped_to_fbs_holds_no_game_between_two_non_fbs_teams(monkeypatch):
    """AND THE SAME BUILD AT 'all' KEEPS IT. A test that only proves the row is absent
    cannot tell "the filter worked" from "the fixture had nothing to filter"."""
    monkeypatch.setattr(workbook, "query", _division_aware_query())

    def classifications(division):
        payload, _, _ = workbook.build(2026, 8, "regular", None, division)
        from openpyxl import load_workbook
        book = load_workbook(BytesIO(payload))
        rows = 0
        for sheet in GAME_SHEETS:
            if sheet.name in book.sheetnames:
                tab = book[sheet.name]
                first = workbook.first_data_row(2 if sheet.sheet_disclaimer else 1)
                rows += tab.max_row - first + 1
        return rows

    narrow, wide = classifications("fbs"), classifications("all")
    assert narrow < wide, (
        f"FBS wrote {narrow} rows and All divisions wrote {wide} — the filter changed "
        "nothing, so this test would pass against the defect it exists to catch")


def test_the_export_and_the_page_spell_the_division_rule_identically():
    """One rule, one spelling. The export must return the set the page displayed, and the
    way that breaks is not a wrong predicate — it is a SECOND predicate that starts out
    right and drifts. Compared as text, so a change to either side has to change both.

    EITHER team FBS, not both: a Division II visitor's trip to an FBS stadium is an FBS
    game, and requiring both drops 20 of the 25 games on the opening Thursday.
    """
    page = (Path(__file__).resolve().parents[1] / "site" / "views" / "schedule.py").read_text()
    predicate = "(:division = 'all' or is_fbs_game)"
    assert predicate in page, (
        "the Schedule page no longer spells the rule this way; the export must follow it, "
        "not the other way round")
    for sheet in GAME_SHEETS:
        assert predicate in " ".join(sheet.sql.split()), (
            f"{sheet.name} reads srv_game but does not apply the page's division rule")


def test_every_sheet_query_carries_the_named_cap_and_no_literal_limit():
    """The cap was four different magic numbers across seven queries — 400, 900, 1000, 2000
    — and nothing named any of them, so nothing could report one. One constant, reported."""
    import re as _re
    for sheet in workbook.SHEETS:
        limits = _re.findall(r"limit\s+(\d+)", sheet.sql, _re.IGNORECASE)
        assert limits == [str(workbook.ROW_CAP)], (
            f"{sheet.name} limits to {limits}, not the named cap {workbook.ROW_CAP}")


def test_the_cap_clears_a_full_season_at_the_widest_scope():
    """Measured, not chosen: a season at All Divisions is 3,745 games on the serving
    database. A cap below that truncates the single most obvious thing to ask for."""
    assert workbook.ROW_CAP >= 3745


def test_rows_written_and_rows_in_scope_are_two_facts(monkeypatch):
    """R-196. The preview ran the real query and so did the build, which guaranteed they
    agreed — and both were wrong by 3,345 rows.

    A count and a cap are two facts about one query, so they come back from one query.
    """
    monkeypatch.setattr(workbook, "query", _division_aware_query(in_scope=3745))
    sheet = GAME_SHEETS[0]
    read = workbook.read_sheet(sheet, 2026, None, "regular", None, "fbs")
    assert read.rows == 1, "the honest stub returns one FBS row"
    assert read.rows_in_scope == 3745
    assert read.truncated


def test_the_index_names_the_truncation_the_number_and_the_cure(monkeypatch):
    """A silently short workbook is the worst failure this file can have: a plausible number
    of rows, correctly formatted, with no way for the reader to know what is missing."""
    monkeypatch.setattr(workbook, "query", _division_aware_query(in_scope=3745))
    payload, index_rows, _ = workbook.build(2026, 8, "regular", None, "fbs")
    from openpyxl import load_workbook
    text = "\n".join(str(c.value) for row in load_workbook(BytesIO(payload))["Index"].iter_rows()
                     for c in row)
    assert "Truncated" in text
    assert "3,745" in text, "the Index must state how many rows were in scope"
    assert f"{workbook.ROW_CAP:,}" in text, "and what the cap was"
    assert "Narrow the filters" in text, "and what to do about it"
    assert any(entry.truncated for entry in index_rows)


def test_an_untruncated_workbook_says_so_rather_than_staying_silent(monkeypatch):
    """The other half of the same claim. 'No warning' is indistinguishable from 'nobody
    checked', which is the whole lesson of R-194."""
    monkeypatch.setattr(workbook, "query", _division_aware_query())
    payload, _, _ = workbook.build(2026, 8, "regular", None, "fbs")
    from openpyxl import load_workbook
    text = "\n".join(str(c.value) for row in load_workbook(BytesIO(payload))["Index"].iter_rows()
                     for c in row)
    assert "Complete" in text and "Truncated" not in text


def test_only_srv_game_sheets_can_honour_the_division_filter():
    """Verified against the serving schema, not assumed: `is_fbs_game` exists on srv_game and
    nowhere else. So a scope line reading 'FBS' would overstate what the other six sheets
    did, and the Index names it per sheet rather than quietly implying it.

    Asserted across ALL seven, because five of the six that cannot honour it are the ones
    waiting to be converted — this is the property they must come back with.
    """
    scoped = {s.name for s in workbook._ALL_SHEETS if s.division_scoped}
    assert scoped == {"Schedule", "Scores"}, scoped
    for sheet in workbook._ALL_SHEETS:
        assert sheet.division_scoped == (sheet.view == "srv_game"), sheet.name


def test_the_index_says_when_the_division_filter_could_not_reach_a_sheet(monkeypatch):
    """The note itself, built for a sheet that cannot narrow. Exercised directly because the
    only sheet shipping today CAN narrow, and a test that silently covers nothing is R-194.
    """
    monkeypatch.setattr(workbook, "query", _division_aware_query())
    standings = next(s for s in workbook._ALL_SHEETS if s.name == "Standings")
    monkeypatch.setattr(workbook, "SHEETS", [standings])
    _, index_rows, _ = workbook.build(2026, 8, "regular", None, "fbs")
    note = next(e for e in index_rows if e.name == "Standings").note
    assert "does not apply" in note and "FBS" in note

    monkeypatch.setattr(workbook, "SHEETS", workbook._ALL_SHEETS[:1])
    _, index_rows, _ = workbook.build(2026, 8, "regular", None, "fbs")
    assert "does not apply" not in next(e for e in index_rows if e.name == "Schedule").note


def test_the_scope_line_names_the_division_unless_it_excludes_nothing():
    assert "FBS" in workbook.describe_scope(2026, 8, "regular", None, "fbs")
    assert "ALL" not in workbook.describe_scope(2026, 8, "regular", None, "all").upper()[10:]


def test_no_sheet_query_contains_a_line_comment():
    """`read_sheet()` sends `" ".join(sql.split())` — the whole query on ONE line.

    So a `--` comment does not comment out its line; it comments out EVERY REMAINING CLAUSE
    of the query. This is not hypothetical: the R-184 predicate was first written with `--`
    above it, and the flattened SQL silently lost its own WHERE clause, its ORDER BY and its
    LIMIT. Postgres reported a syntax error at the next statement, which is a long way from
    the cause.

    Block comments survive flattening. Use them.
    """
    import re as _re
    for sheet in workbook.SHEETS:
        # Block comments stripped FIRST. The eighth time in this repo a source-reading check
        # has matched its own prose: the block comment explaining this rule contains the very
        # two characters it forbids, and the first version of this test failed on it.
        code = _re.sub(r"/\*.*?\*/", "", sheet.sql, flags=_re.S)
        assert "--" not in code, (
            f"{sheet.name}'s query has a `--` comment. read_sheet() flattens the SQL to one "
            f"line, so everything after it is commented out. Use /* ... */ instead.")


def test_the_flattened_sql_survives_comment_semantics_not_just_string_matching():
    """The property the test above protects — asserted the way POSTGRES would see it.

    The first version of this test was green with the defect present, which is the failure
    class this project keeps rediscovering: a true assertion about the wrong property. It
    checked that the flattened text ENDS WITH the cap, and it does — `limit 5000` is still
    the last thing in the string when a `--` has commented it out. `check_contract` agreed
    for the same reason: its LIMIT check is a regex over text, and text is not what runs.

    So apply what the server applies. Flatten, then delete from any `--` to end of line —
    which, once flattened, is end of statement — and assert what SURVIVES is still the whole
    query.
    """
    import re as _re
    for sheet in workbook.SHEETS:
        flat = " ".join(sheet.sql.split())
        as_parsed = _re.sub(r"/\*.*?\*/", " ", flat, flags=_re.S)
        as_parsed = _re.sub(r"--.*$", "", as_parsed)
        assert check_contract(as_parsed) == sheet.view, (
            f"{sheet.name}'s query does not survive its own comments")
        assert _re.search(rf"\blimit\s+{workbook.ROW_CAP}\b", as_parsed), (
            f"{sheet.name} loses its LIMIT once comments are applied — a `--` has swallowed "
            f"the tail. What the server would run: ...{as_parsed[-110:]}")
        assert "order by" in as_parsed.lower(), (
            f"{sheet.name} loses its ORDER BY once comments are applied")


# === R-181 / R-182 / R-183: the layout ====================================================

def test_exactly_one_blank_row_sits_between_the_notes_and_the_header(built):
    """R-181, Marc's global requirement. Excel treats a blank row as the end of a region, so
    a second blank changes what a header-click and Ctrl+A select — it is not cosmetic.

    Asserted by READING THE CELLS, not by recomputing the constant. A test that asks
    `header_row(n) == n + 2` restates the implementation and would pass with the sheet laid
    out any way at all.
    """
    _, book, _, _ = built
    for name in book.sheetnames:
        tab = book[name]
        column_a = [tab.cell(r, 1).value for r in range(1, 12)]
        notes = 0
        while notes < len(column_a) and column_a[notes] not in (None, ""):
            notes += 1
        assert notes >= 1, f"{name} has no note block at all — attribution is structural"
        blanks = 0
        while column_a[notes + blanks] in (None, ""):
            blanks += 1
        assert blanks == 1, (
            f"{name} has {blanks} blank row(s) between its notes and its header, not 1")


def test_the_blank_row_holds_on_a_sheet_with_the_disclaimer_and_one_without(monkeypatch):
    """THE NEGATIVE HALF, and the reason the old layout was wrong.

    Four fixed constants gave exactly one blank row on a sheet WITH the model disclaimer and
    two on a sheet without — so a test that only ever saw a prediction sheet would have
    reported the old layout as correct. Both shapes, in one test.
    """
    monkeypatch.setenv("CFDB_SITE_HOST", "https://cfdb.example")
    monkeypatch.setattr(workbook, "query", _division_aware_query())
    from openpyxl import load_workbook

    seen = {}
    for sheet in (next(s for s in workbook._ALL_SHEETS if s.sheet_disclaimer),
                  next(s for s in workbook._ALL_SHEETS if not s.sheet_disclaimer)):
        monkeypatch.setattr(workbook, "SHEETS", [sheet])
        payload, _, _ = workbook.build(2026, 8, "regular", None, "all")
        tab = load_workbook(BytesIO(payload))[sheet.name]
        column_a = [tab.cell(r, 1).value for r in range(1, 12)]
        # The CONTIGUOUS prefix. Counting non-empty cells in the first three rows instead
        # counted the header as a note the moment the block was one line long.
        notes = 0
        while column_a[notes] not in (None, ""):
            notes += 1
        seen[sheet.sheet_disclaimer] = (notes, column_a[notes])
    assert seen[True][0] == 2 and seen[False][0] == 1, seen
    for _, first_gap in seen.values():
        assert first_gap in (None, ""), seen
    assert workbook.header_row(2) != workbook.header_row(1), (
        "the header address must MOVE with the note block; a constant is what R-181 removed")


def test_every_table_name_is_legal_unique_and_has_no_space(built):
    """R-182. Excel's own constraints, enforced rather than discovered — a duplicate or an
    illegal displayName is a repair prompt, not an exception, so the file writes cleanly and
    Excel refuses it."""
    import re as _re
    _, book, _, _ = built
    names = []
    for sheet_name in book.sheetnames:
        for table in book[sheet_name].tables.values():
            names.append(table.displayName)
    assert names, "no sheet carries an Excel Table"
    for name in names:
        assert _re.fullmatch(r"tbl_[A-Za-z0-9_]+", name), name
        assert " " not in name
        assert not _re.fullmatch(r"[A-Za-z]{1,3}[0-9]+", name), f"{name} looks like a cell ref"
    assert len(names) == len(set(names)), f"duplicate table name: {names}"


def test_the_index_inventory_is_itself_a_table(built):
    _, book, _, _ = built
    assert "tbl_Index" in {t.displayName for t in book["Index"].tables.values()}


def test_a_table_never_overlaps_a_worksheet_autofilter(built):
    """R-182 trap 1, stated as the property rather than as the absence of one line. This is
    the fault class that produces "we found a problem with some content", which AC-15.6
    forbids outright."""
    _, book, _, _ = built
    for name in book.sheetnames:
        tab = book[name]
        if tab.tables:
            assert not tab.auto_filter.ref, name


def test_the_navy_header_survives_the_table_style(built):
    """R-182 trap 3. A TableStyleInfo's header band would override the manual fill and the
    file would depend on which Excel applied last. One treatment: the navy stays, stripes off.
    """
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    assert tab.cell(header, 1).fill.fgColor.rgb.endswith("2F4858")
    for table in tab.tables.values():
        assert table.tableStyleInfo.showRowStripes is False


def test_headers_are_unique_and_non_empty_on_every_sheet():
    """R-182 trap 2. A Table makes non-empty MANDATORY rather than merely tidy, and the
    67-column list has several near-collisions — TV/TV (full), the two `covered` columns —
    each of which had to be spelled distinctly."""
    for sheet in workbook._ALL_SHEETS:
        labels = [label for _, label in sheet.columns]
        assert all(label and label.strip() for label in labels), sheet.name
        duplicates = {la for la in labels if labels.count(la) > 1}
        assert not duplicates, f"{sheet.name} has duplicate headers: {duplicates}"


def test_freeze_panes_stays_on_the_sheet_not_on_the_table(built):
    """R-182 trap 4."""
    _, book, _, _ = built
    schedule = next(s for s in workbook._ALL_SHEETS if s.name == "Schedule")
    from openpyxl.utils import get_column_letter
    column = get_column_letter(schedule.freeze_column())
    assert book["Schedule"].freeze_panes == f"{column}{workbook.first_data_row(1)}"


# --- R-183, the hyperlinks --------------------------------------------------------------

def test_team_and_matchup_cells_link_back_and_carry_the_scope(built):
    """A link that drops the season is the defect that made choosing 2025 and clicking a
    team return a 2026 page. It is worse in a workbook, which is read weeks later."""
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    labels = {tab.cell(header, i).value: i for i in range(1, tab.max_column + 1)}
    away = tab.cell(header + 1, labels["Away"])
    assert away.hyperlink is not None, "the team name cell is not linked"
    target = away.hyperlink.target or away.hyperlink.location
    assert target.startswith("https://cfdb.example/team?")
    assert "season=2026" in target and "week=8" in target
    assert away.value and not str(away.value).startswith("http"), (
        "the cell's VALUE must stay the team name, so the column still sorts as a name")


def test_the_matchup_cell_reads_a_word_and_carries_the_url_behind_it(built):
    """Round 3 REVERSES round 2's decision here, and the reversal is Marc's.

    Round 2 put the raw URL in the cell so anything reading the file as DATA could see it —
    a cell hyperlink is invisible to a CSV export or a pivot. He looked at it: a 90-character
    URL in every row of a 56-column sheet costs more width and legibility than that buys, and
    `Game id` beside it already reconstructs the link.

    So the cell says "Matchup" and the URL is the hyperlink.
    """
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    labels = {tab.cell(header, i).value: i for i in range(1, tab.max_column + 1)}
    cell = tab.cell(header + 1, labels["Matchup URL"])
    assert cell.value == workbook.URL_CELL_LABEL == "Matchup"
    assert not str(cell.value).startswith("http"), "the URL is the link, not the text"
    target = cell.hyperlink.target or cell.hyperlink.location
    assert target.startswith("https://cfdb.example/matchup?")
    assert "season=2026" in target and "week=8" in target


def test_the_index_links_each_sheet_back_to_its_page_with_the_same_filters(built):
    """Round 3. A workbook read in November should land on the week it covers, not on
    whatever week the site is showing when the link is clicked — which is the same defect
    that made choosing 2025 and clicking a team return a 2026 page."""
    _, book, _, _ = built
    tab = book["Index"]
    found = {}
    for row in tab.iter_rows():
        for cell in row:
            if cell.value in ("Schedule", "srv_game") and cell.hyperlink:
                found[cell.value] = cell.hyperlink.target or cell.hyperlink.location
    assert "Schedule" in found, "the sheet name does not link back to its page"
    assert found["Schedule"].startswith("https://cfdb.example/schedule?")
    assert "season=2026" in found["Schedule"] and "week=8" in found["Schedule"]

    assert "srv_game" in found, "the serving view does not link into the data dictionary"
    # The site's own convention, not a second spelling of it: lib/table.py already writes
    # `/dictionary?table=<name>` for every dataset caption on every page.
    assert found["srv_game"] == "https://cfdb.example/dictionary?table=srv_game"


def test_the_index_links_are_absent_rather_than_broken_with_no_host(monkeypatch):
    monkeypatch.delenv("CFDB_SITE_HOST", raising=False)
    monkeypatch.setattr(workbook, "query", _division_aware_query())
    payload, _, _ = workbook.build(2026, 8, "regular", None, "fbs")
    from openpyxl import load_workbook
    tab = load_workbook(BytesIO(payload))["Index"]
    for row in tab.iter_rows():
        for cell in row:
            assert cell.hyperlink is None, cell.coordinate


def test_with_no_site_host_the_workbook_ships_no_links_rather_than_broken_ones(monkeypatch):
    """R-151's shape: a link that resolves in dev and 404s in the file the user downloaded.
    A workbook full of `http://None/...` is worse than one with none."""
    monkeypatch.delenv("CFDB_SITE_HOST", raising=False)
    monkeypatch.setattr(workbook, "query", _division_aware_query())
    assert workbook.site_base_url() is None
    payload, _, _ = workbook.build(2026, 8, "regular", None, "fbs")
    from openpyxl import load_workbook
    book = load_workbook(BytesIO(payload))
    tab = book["Schedule"]
    for row in tab.iter_rows():
        for cell in row:
            assert cell.hyperlink is None, f"{cell.coordinate} linked with no host set"
            assert "None/" not in str(cell.value), f"{cell.coordinate} = {cell.value!r}"
    index = "\n".join(str(c.value) for r in book["Index"].iter_rows() for c in r)
    assert "no hyperlinks" in index, "the Index must say the links are absent and why"


def test_a_bare_hostname_becomes_https_and_a_full_url_is_left_alone(monkeypatch):
    monkeypatch.setenv("CFDB_SITE_HOST", "cfdb.example.com")
    assert workbook.site_base_url() == "https://cfdb.example.com"
    monkeypatch.setenv("CFDB_SITE_HOST", "http://localhost:8501/")
    assert workbook.site_base_url() == "http://localhost:8501"


def test_the_index_warns_that_access_will_ask_for_a_sign_in(built):
    """Someone who was not expecting Cloudflare Access reads the sign-in page as a broken
    link, and concludes the workbook's links are wrong."""
    _, book, _, _ = built
    text = "\n".join(str(c.value) for r in book["Index"].iter_rows() for c in r)
    assert "Cloudflare Access" in text and "sign in" in text


# --- R-185, the Schedule sheet ------------------------------------------------------------

def test_the_schedule_sheet_carries_marcs_fifty_six_columns_in_his_order():
    """R-214/R-215. The order is `claude_work/supporting_files/cfdb_schedule_column_order.csv`
    and it is AUTHORITATIVE, so this reads the file rather than restating it. A test that
    hardcoded the list would have to be edited alongside the CSV and could disagree with it.
    """
    import csv as _csv
    source = (Path(__file__).resolve().parents[2] / "claude_work" / "supporting_files"
              / "cfdb_schedule_column_order.csv")
    if not source.exists():                      # the CSV lives outside this repo
        pytest.skip("Marc's column-order CSV is not present in this checkout")
    wanted = [row["Field"] for row in _csv.DictReader(source.open())]
    schedule = next(s for s in workbook._ALL_SHEETS if s.name == "Schedule")
    assert [label for _, label in schedule.columns] == wanted


def test_the_eleven_removed_columns_are_gone_from_the_select_as_well_as_the_headers():
    """R-214. Dropping a label but leaving the field in the SELECT would keep paying for the
    column and give a reader no way to see it — and the underlying srv_game columns are
    deliberately untouched, so nothing else notices."""
    schedule = next(s for s in workbook._ALL_SHEETS if s.name == "Schedule")
    flat = " ".join(schedule.sql.split())
    for field in ("kickoff_time_known", "network,", "spread_open", "over_under_open",
                  "spread_at_close", "spread_at_close_provider", "spread_at_close_basis",
                  "total_at_close", "total_at_close_provider", "total_at_close_basis"):
        assert field not in flat, f"{field} is still selected"
    assert "game_date" not in flat, "the Day column went, and so does what it derived from"


def test_upset_basis_is_gone_and_must_not_come_back():
    """R-193. It was dropped from srv_game the same day the column list was first written,
    and a SELECT naming it is what 500'd the Schedule page. `upset_level` alone now carries
    "judged against the closing line"."""
    for sheet in workbook._ALL_SHEETS:
        assert "upset_basis" not in sheet.sql, sheet.name
        assert "upset_basis" not in sheet.fields, sheet.name


def test_the_delta_columns_lost_their_disambiguator_and_the_index_says_so(built):
    """R-214, consequence 1, and it is a REAL LOSS rather than a tidy-up.

    `Δ Spread` is null both when the line did not move and when no opening number was ever
    recorded — two different facts, one blank cell — and `Spread open` beside it was what
    told them apart. Marc removed both opening columns, so the blank is now genuinely
    ambiguous in the file.

    No sentinel is invented; the Index carries the sentence. This test asserts the sentence
    exists, because it is the only thing standing between a reader and a wrong reading.
    """
    schedule = next(s for s in workbook._ALL_SHEETS if s.name == "Schedule")
    labels = [label for _, label in schedule.columns]
    assert "Spread open" not in labels and "O/U open" not in labels
    assert "Δ Spread" in labels
    _, book, _, _ = built
    text = "\n".join(str(c.value) for r in book["Index"].iter_rows() for c in r)
    assert "did not move" in text and "no opening line" in text


def test_marcs_order_keeps_the_market_left_of_the_result():
    """His arrangement is scope → fixture → market → result → context → model → keys, and it
    preserves the one property spec §3.2 argued for: the numbers you open the file on a
    Wednesday to read come before the columns that are blank until Saturday night."""
    schedule = next(s for s in workbook._ALL_SHEETS if s.name == "Schedule")
    labels = [label for _, label in schedule.columns]
    assert labels.index("Spread") < labels.index("Away pts")
    assert labels.index("Season") < labels.index("Away")
    assert labels.index("Attribution") == len(labels) - 1


def test_the_derived_columns_are_words_not_booleans_or_timestamps():
    """`Day` and `Status` exist because a datetime does not answer "is this a Thursday game"
    and a boolean does not answer "has it been played" without the reader translating."""
    schedule = next(s for s in workbook._ALL_SHEETS if s.name == "Schedule")
    assert schedule.value_for("status", {"is_completed": True}) == "Final"
    assert schedule.value_for("status", {"is_completed": False}) == "Scheduled"
    assert schedule.value_for("status", {"is_completed": None}) is None
    assert "weekday" not in schedule.derived, "the Day column went out with R-214"


def test_the_default_sort_is_the_order_by_and_it_is_stable():
    """A Table's sortState is metadata about a sort that WAS applied; Excel does not
    re-apply it on open. So the ORDER BY is the default sort, and it needs a tiebreak or two
    builds of the same scope differ — which a diff of two workbooks depends on."""
    schedule = next(s for s in workbook._ALL_SHEETS if s.name == "Schedule")
    flat = " ".join(schedule.sql.split())
    assert "order by start_date_et, game_id" in flat


def test_only_the_schedule_sheet_ships_and_the_other_six_are_kept_not_deleted():
    """Marc: "only 1 data sheet for now". The six are real work and are converted one at a
    time; deleting them would mean rewriting their SQL and column lists from scratch."""
    assert [s.name for s in workbook.SHEETS] == ["Schedule"]
    assert len(workbook.PENDING_SHEETS) == 6
    assert {s.name for s in workbook.PENDING_SHEETS} == {
        "Scores", "Odds", "Edges", "Standings", "Model performance", "Data dictionary"}


def test_the_index_names_the_six_that_are_not_here_rather_than_dropping_them(built):
    """A sheet a user had yesterday and does not have today is a question. An Index that
    does not mention it makes the workbook look broken instead of narrowed."""
    _, book, _, _ = built
    text = "\n".join(str(c.value) for r in book["Index"].iter_rows() for c in r)
    for sheet in workbook.PENDING_SHEETS:
        assert sheet.name in text, sheet.name
    assert "not converted to the new layout yet" in text


def test_nothing_in_the_file_is_a_fault_excel_would_refuse_to_open(built):
    """AC-15.6 IS A CLAIM ABOUT EXCEL, AND openpyxl OPENING THE FILE DOES NOT PROVE IT.

    openpyxl is forgiving where Excel is not, so this asserts the specific structures Excel
    rejects with "we found a problem with some content" — the prompt AC-15.6 forbids:

      * a table's declared tableColumns disagreeing with the header cells above them
      * a duplicate or empty column name inside a table
      * a table ref that overruns the sheet's used range
      * a table overlapping a worksheet autofilter (R-182 trap 1)
      * NaN or infinity in a cell, which is valid XML and still refused
      * a part that is not well-formed XML

    It still does not replace opening the file in Excel once, by hand. It makes the
    hand-check a confirmation rather than the only evidence.
    """
    import math
    import re
    import zipfile
    from xml.etree import ElementTree
    from openpyxl.utils import range_boundaries

    payload, book, _, _ = built

    with zipfile.ZipFile(BytesIO(payload)) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            if name.endswith((".xml", ".rels")):
                ElementTree.fromstring(archive.read(name))   # raises if malformed

    seen_tables = 0
    for name in book.sheetnames:
        tab = book[name]
        for table in tab.tables.values():
            seen_tables += 1
            min_col, min_row, max_col, max_row = range_boundaries(table.ref)
            headers = [tab.cell(min_row, c).value for c in range(min_col, max_col + 1)]
            declared = [c.name for c in table.tableColumns]
            assert headers == declared, (
                f"{table.displayName}: the table declares {declared} and the header row "
                f"says {headers}. Excel refuses the file when these disagree")
            assert len(set(declared)) == len(declared), table.displayName
            assert all(h not in (None, "") for h in headers), table.displayName
            assert max_row <= tab.max_row and max_col <= tab.max_column, (
                f"{table.displayName}: ref {table.ref} overruns {tab.dimensions}")
            assert not tab.auto_filter.ref, table.displayName
    assert seen_tables >= 2, "Index and Schedule should both carry a Table"

    # NaN IS CHECKED IN THE RAW XML, AND THE REASON IS THE WHOLE POINT OF THIS COMMENT.
    #
    # The first version of this loop walked the RE-LOADED workbook looking for a float that
    # is NaN. It could never fail. openpyxl WRITES NaN — as `<c t="n"><v /></c>`, a numeric
    # cell with no value, which is exactly what Excel objects to — and then READS THAT BACK
    # AS None. So the object model always looks clean no matter what was written, and the
    # assertion was unfalsifiable: green with `_clean`'s guards removed entirely.
    #
    # Verified by removing both guards and watching this stay green, which is how it was
    # caught. The bytes are the only place the fault is visible.
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        for name in archive.namelist():
            if not name.startswith("xl/worksheets/"):
                continue
            body = archive.read(name).decode("utf-8")
            empty_numeric = re.findall(r'<c[^>]*t="n"[^>]*>\s*<v\s*/>', body)
            assert not empty_numeric, (
                f"{name} has {len(empty_numeric)} numeric cell(s) with no value — that is "
                f"how a NaN or an infinity reaches the file, and Excel refuses it")
    assert math is not None


# === R-216 · R-217 · R-218 · R-219 · R-220: round two ====================================

def test_no_label_shaped_number_renders_with_a_decimal_or_a_comma():
    """R-216. THE RULE, not the list.

    A thousands separator is for a quantity you might total. A rank, an id, a season and a
    week are labels that happen to be numeric, and a comma in one is a bug. `#,##0` rendered
    season 2025 as "2,025" — which is how a membership tuple that had `season` in it was
    still wrong about it.

    Enumerates the REAL columns rather than re-implementing the pattern. That matters:
    `best_rank_in_game` carries "rank" in the MIDDLE of its name and the suffix rule does not
    see it, so a test written from the same pattern would have agreed with the bug.
    """
    offenders = []
    for sheet in workbook._ALL_SHEETS:
        for field, label in sheet.columns:
            looks_like_a_label = ("rank" in field or field.endswith("_id")
                                  or field in ("season", "week"))
            if not looks_like_a_label:
                continue
            rendered = workbook.number_format(field)
            if "." in rendered or "," in rendered:
                offenders.append((sheet.name, field, rendered))
    assert not offenders, offenders


def test_counts_keep_their_thousands_separator():
    """The other half of the rule. Dropping commas everywhere would make 74109 unreadable,
    and attendance is exactly the quantity a reader might total."""
    assert workbook.number_format("attendance") == "#,##0"
    assert workbook.number_format("total_points") == "#,##0"
    assert workbook.number_format("season") == "0"
    assert workbook.number_format("game_id") == "0"
    assert workbook.number_format("best_rank_in_game") == "0"


def test_column_width_is_measured_from_the_data_not_from_the_header(built):
    """R-217. The old code seeded the width with `len(label)`, so "Conference game" set a
    15-wide column over three characters of data. Marc found four of them.

    Asserted on the columns he named, with the data the fixture holds — a long header over
    short data must now be narrow, and the header wraps instead.
    """
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    labels = {tab.cell(header, i).value: i for i in range(1, tab.max_column + 1)}
    from openpyxl.utils import get_column_letter
    for label in ("Current week", "Conference game", "Home rank", "Best rank"):
        letter = get_column_letter(labels[label])
        width = tab.column_dimensions[letter].width
        assert width < len(label), (
            f"{label!r} is {width} wide for a {len(label)}-character header — the label is "
            f"still setting the width")
        assert width >= workbook.MIN_COLUMN_WIDTH, (
            f"{label!r} is {width} wide; a one-character column is unreadable")


def test_the_header_row_wraps_and_its_height_is_computed_not_hardcoded(built):
    """R-217. Marc's macro uses 38pt, which is three lines and a good default — but it is a
    default that FITS TODAY'S HEADERS, and the next long one would silently clip.

    So the height is measured from the labels at their final widths. Asserted as a
    relationship, not a number: a test pinning 38 would be the hardcode with extra steps.
    """
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    assert tab.cell(header, 1).alignment.wrap_text is True
    height = tab.row_dimensions[header].height
    assert height and height >= workbook.MIN_HEADER_HEIGHT

    from openpyxl.utils import get_column_letter
    worst = 0
    for index, (_, label) in enumerate(
            next(s for s in workbook.SHEETS if s.name == "Schedule").columns, start=1):
        width = tab.column_dimensions[get_column_letter(index)].width
        worst = max(worst, workbook._header_height([(label, width)]))
    # THE FLOOR IS A FLOOR, NOT A FIXED HEIGHT. Marc's 50pt gives the labels room above the
    # Table's filter buttons, which sit inside the header cell and overlap the last line. But
    # a longer header in some future column must still be able to push the row taller, or
    # R-217's "computing cannot clip" is given straight back.
    assert height == max(worst, workbook.MIN_HEADER_HEIGHT), (
        f"the row is {height}pt, the tallest label needs {worst}pt and the floor is "
        f"{workbook.MIN_HEADER_HEIGHT}pt")


def test_a_longer_header_makes_the_row_taller_which_a_hardcoded_38_could_not():
    """The negative half. A fixed height cannot respond to a longer label; a computed one
    must, or it is a hardcode wearing a function's clothes."""
    short = workbook._header_height([("Wk", 6)])
    long = workbook._header_height([("Margin (away−home)", 6)])
    assert long > short
    # A single word wider than the column still has to go somewhere: Excel breaks it rather
    # than clipping, so the calculation must account for that instead of assuming it fits.
    assert workbook._header_height([("Precipitation", 6)]) > short


def test_booleans_read_as_words_and_nulls_stay_null():
    """R-218. Marc marked six fields t/f = Yes/No. A null is NOT False — this project has
    been bitten three times by truthiness on a pandas null."""
    assert workbook._yes_no(True) == "Yes"
    assert workbook._yes_no(False) == "No"
    assert workbook._yes_no(None) is None
    assert workbook._yes_no(float("nan")) is None


def test_no_favorite_becomes_two_words_not_an_underscore():
    """`favorite_covered` is already a string, so this is title-casing, not a boolean
    conversion — and a naive `.title()` leaves "No_Favorite" behind."""
    assert workbook._title_case_verdict("no_favorite") == "No favorite"
    assert workbook._title_case_verdict("push") == "Push"
    assert workbook._title_case_verdict(None) is None


def test_the_flag_highlight_follows_what_the_cell_actually_holds(built):
    """R-218's TRAP, and it is the kind that passes every test written against Python.

    `CellIsRule(operator="equal", formula=["TRUE"])` matches nothing once the cell holds the
    string "Yes" — no error, no warning, the highlight just disappears. So the formula is
    derived from whether the column has a display rule, and asserted on the built file.
    """
    _, book, _, _ = built
    schedule = next(s for s in workbook.SHEETS if s.name == "Schedule")
    rules = book["Schedule"].conditional_formatting
    formulas = [f for rule_set in rules for rule in rule_set.rules
                for f in (rule.formula or [])]
    assert formulas, "the Schedule sheet has no conditional formatting at all"
    for field in workbook.FLAG_FIELDS:
        if field not in schedule.fields:
            continue
        expected = '"Yes"' if field in schedule.display else "TRUE"
        assert expected in formulas, (
            f"{field} renders as {'Yes/No' if field in schedule.display else 'TRUE/FALSE'} "
            f"but no rule compares to {expected}")


def test_the_verdict_columns_use_the_sites_marks_and_a_dash_for_nothing():
    """R-219. Geometric shapes, not emoji: R-141 and R-175 both turned on an
    emoji-presentation character having no fixed baseline or size across platforms, and a
    workbook is opened on more platforms than a page is."""
    for marks in (workbook.UPSET_MARKS, workbook.COVER_MARKS, workbook.OVER_MARKS):
        for glyph in marks.values():
            # A mark may REPEAT to carry a level (●, ●●, ●●●) but it is always repetitions
            # of ONE character — two different shapes in one cell would be a new mark rather
            # than a stronger one.
            assert 1 <= len(glyph) <= 3, glyph
            assert len(set(glyph)) == 1, f"{glyph!r} mixes shapes"
            # Emoji live above U+1F000, and the presentation selector is U+FE0F. Neither
            # may appear here.
            assert ord(glyph[0]) < 0x1F000, f"{glyph!r} is emoji-presentation"
            assert "️" not in glyph
    render = workbook._marked(workbook.COVER_MARKS)
    assert render("yes") == "■" and render("push") == "◨"
    assert render(None) == workbook.NO_DATA_MARK
    assert render(float("nan")) == workbook.NO_DATA_MARK
    assert render("something_new") == workbook.NO_DATA_MARK


def test_the_index_carries_a_legend_for_every_mark_it_uses(built):
    """R-219, and this is NOT OPTIONAL. R-026's icon-only exception on the site is
    defensible because R-102's legend explains it once. A workbook has no tooltip at all, so
    the same exception needs the same support or it is undecodable symbols."""
    _, book, _, _ = built
    text = "\n".join(str(c.value) for r in book["Index"].iter_rows() for c in r)
    used = set()
    for marks in (workbook.UPSET_MARKS, workbook.COVER_MARKS, workbook.OVER_MARKS):
        used.update(marks.values())
    used.add(workbook.NO_DATA_MARK)
    for glyph in used:
        assert glyph in text, f"{glyph!r} is rendered in the sheet and absent from the legend"
    assert 'SUM(--(range="Yes"))' in text, "the Yes/No formula cost must be stated once"


def test_the_data_bar_carries_marcs_full_rule_in_the_x14_extension(built):
    """R-220, READ FROM THE RAW XML BECAUSE openpyxl CANNOT SEE IT.

    openpyxl's DataBarRule writes the legacy `<dataBar>`, which has one colour, a min and a
    max — no negative fill, no borders, no axis position. Three of the seven things in
    Marc's screenshot cannot be said with it. Those live in `x14:dataBar`, which openpyxl
    does not model and DISCARDS ON READ, with the warning "Unknown extension is not
    supported and will be removed".

    So a test that re-loaded the workbook would find nothing and could never fail. The bytes
    are the only place this is visible — the same lesson as the NaN check above.
    """
    import re
    import zipfile as _zip
    payload, _, _ = built[0], None, None
    payload = built[0]
    with _zip.ZipFile(BytesIO(payload)) as archive:
        sheets = [n for n in archive.namelist() if n.startswith("xl/worksheets/sheet")]
        body = "".join(archive.read(n).decode("utf-8") for n in sheets)

    assert "x14:dataBar" in body, "the extension block is missing entirely"
    assert 'axisPosition="middle"' in body, "Marc's rule says axis position MIDPOINT"
    assert f'x14:negativeFillColor rgb="{workbook.DATA_BAR_NEGATIVE}"' in body, "negative RED"
    assert f'x14:borderColor rgb="{workbook.DATA_BAR_AXIS}"' in body, "solid black border"
    assert f'x14:negativeBorderColor rgb="{workbook.DATA_BAR_AXIS}"' in body
    assert f'x14:axisColor rgb="{workbook.DATA_BAR_AXIS}"' in body
    assert 'gradient="0"' in body, "Marc's rule says SOLID fill, not gradient"

    # The legacy element and the extension are tied by a GUID, and a mismatch means Excel
    # draws the plain bar and silently ignores everything Marc asked for.
    legacy = set(re.findall(r"<x14:id>([^<]+)</x14:id>", body))
    extended = set(re.findall(r'<x14:cfRule type="dataBar" id="([^"]+)"', body))
    assert legacy and legacy == extended, (legacy, extended)


def test_the_data_bar_guid_is_stable_across_builds(monkeypatch):
    """Two builds of one scope must be byte-identical, which a diff of two workbooks depends
    on. A random GUID would break that quietly."""
    assert workbook._data_bar_guid(1) == workbook._data_bar_guid(1)
    assert workbook._data_bar_guid(1) != workbook._data_bar_guid(2)


def test_every_sheet_part_is_still_well_formed_after_the_xml_injection(built):
    """Hand-written XML is the class of change that produces the repair prompt AC-15.6
    forbids, so the rewritten parts are parsed rather than trusted."""
    import zipfile as _zip
    from xml.etree import ElementTree
    payload = built[0]
    with _zip.ZipFile(BytesIO(payload)) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            if name.endswith((".xml", ".rels")):
                ElementTree.fromstring(archive.read(name))


def test_a_postgres_text_boolean_does_not_become_yes(monkeypatch):
    """'f' IS A NON-EMPTY STRING AND `bool('f')` IS TRUE.

    Postgres renders a boolean as 't'/'f' the moment anything reads it as text — a CSV
    export, a driver without type mapping, an object-dtype column. So a blanket `bool(value)`
    turns every False into "Yes", silently, on a column a reader filters on.

    Found by building a real workbook from real rows and reading row 1: a game the favourite
    won by 14 while laying 15 was showing "Upset by line: Yes". Same family as the three
    NaN-truthiness bugs this project has already had.
    """
    assert workbook._yes_no("f") == "No"
    assert workbook._yes_no("false") == "No"
    assert workbook._yes_no("t") == "Yes"
    assert workbook._yes_no(False) == "No"
    # Not a boolean at all: guessing is what caused this, so it declines to guess.
    assert workbook._yes_no("maybe") is None


def test_no_two_marks_are_visually_confusable():
    """"The favourite won" and "cfdb holds no closing line" are OPPOSITE CLAIMS.

    The first draft drew them as an em dash and an en dash, which at 11pt are the same
    picture. Every mark in use must be a distinct character, and the dash-like ones must not
    collide.
    """
    used = []
    for marks in (workbook.UPSET_MARKS, workbook.COVER_MARKS, workbook.OVER_MARKS):
        used.extend(marks.values())
    used.append(workbook.NO_DATA_MARK)

    dashes = {"-", "‐", "‑", "‒", "–", "—", "―", "−"}
    dash_marks = [m for m in used if m in dashes]
    assert len(set(dash_marks)) <= 1, (
        f"more than one dash-like mark is in use and they are indistinguishable: "
        f"{sorted(set(dash_marks))}")
    assert workbook.UPSET_MARKS["none"] not in dashes, (
        "'the favourite won' must not be a dash; the dash means cfdb holds nothing")


def test_filled_means_it_happened_and_open_means_it_did_not():
    """R-141's shape-plus-fill system, carried into the sheet. It is what makes a mark
    self-identifying without colour, which matters more in Excel than on the site."""
    assert workbook.UPSET_MARKS["upset"] == "●" and workbook.UPSET_MARKS["none"] == "○"
    assert workbook.COVER_MARKS["yes"] == "■" and workbook.COVER_MARKS["no"] == "□"


def test_the_legend_names_only_the_columns_that_actually_use_marks():
    """A legend that promises a shape in a column of words sends the reader looking for
    something that is not there. `Favourite covered` renders as Yes/No/Push per Marc's CSV,
    so it is described as a word rather than listed among the marks."""
    schedule = next(s for s in workbook.SHEETS if s.name == "Schedule")
    marked = {field for field, renderer in schedule.display.items()
              if renderer.__qualname__.startswith("_marked")}
    labels = dict(schedule.columns)
    marked_labels = {labels[f] for f in marked}
    assert marked_labels == {"Upset level", "Winner covered", "O/U result"}, marked_labels
    for column, _, _ in workbook.MARK_LEGEND:
        if column.startswith("Any"):
            continue
        assert column in marked_labels, (
            f"the legend lists {column!r} among the marks, and that column renders words")


def test_every_sheet_part_is_in_ct_worksheet_order(built):
    """THE CHECK THAT WAS MISSING, AND THE FILE SHIPPED BROKEN BECAUSE OF IT.

    `CT_Worksheet`'s children are an ORDERED SEQUENCE. Excel validates it; openpyxl does
    not, and neither does "is this well-formed XML" — the file parsed perfectly and Excel
    still refused it, replaced the whole sheet part and opened the Schedule tab EMPTY.

    The R-220 injection put its `<conditionalFormatting>` block before `<pageMargins>`,
    which on a sheet with hyperlinks lands AFTER `<hyperlinks>`. The schema puts
    conditionalFormatting first. Every prior check passed: well-formed XML, tables matching
    their headers, no NaN, no autofilter overlap. Order was the one property nothing tested.
    """
    import zipfile as _zip
    payload = built[0]
    with _zip.ZipFile(BytesIO(payload)) as archive:
        checked = 0
        for name in archive.namelist():
            if not name.startswith("xl/worksheets/sheet"):
                continue
            checked += 1
            violations = workbook.sheet_order_violations(archive.read(name))
            assert not violations, (
                f"{name}: {violations} — Excel will refuse this file and open the tab empty")
        assert checked >= 2


def test_the_order_validator_actually_detects_a_misplaced_block():
    """A validator that cannot fail is the thing that let this through in the first place.
    Fed the exact shape that broke Excel, it must object."""
    good = (b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            b'<sheetData/><conditionalFormatting sqref="A1"/><hyperlinks/><pageMargins/>'
            b'</worksheet>')
    bad = (b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           b'<sheetData/><hyperlinks/><conditionalFormatting sqref="A1"/><pageMargins/>'
           b'</worksheet>')
    assert workbook.sheet_order_violations(good) == []
    assert workbook.sheet_order_violations(bad) == [("conditionalFormatting", "hyperlinks")]


def test_the_build_refuses_to_emit_a_sheet_excel_would_reject(monkeypatch):
    """Fail at build time, not in the user's Excel. Verified by forcing the injection to the
    wrong place and asserting `build` raises rather than returning bytes."""
    monkeypatch.setenv("CFDB_SITE_HOST", "https://cfdb.example")
    monkeypatch.setattr(workbook, "query", _division_aware_query())
    # Force the fallback path AND point it at the exact wrong place — before <pageMargins>,
    # which on a sheet with hyperlinks lands after them. This is the shape that shipped.
    monkeypatch.setattr(workbook, "CF_ANCHOR", "<<no such element>>")
    monkeypatch.setattr(workbook, "SHEET_ELEMENTS_AFTER_CF", ("<pageMargins", "</worksheet>"))
    with pytest.raises(RuntimeError) as excinfo:
        workbook.build(2026, 8, "regular", None, "fbs")
    assert "CT_Worksheet order" in str(excinfo.value)


def test_the_simple_data_bar_fallback_writes_no_extension_and_stays_in_order(monkeypatch):
    """R-220's route (b), kept reachable rather than kept in a comment.

    The x14 route fought back once and cost a broken file, so the simpler rendering is one
    environment variable away and is tested — a fallback nobody exercises is a fallback that
    does not work when it is needed.
    """
    import zipfile as _zip
    monkeypatch.setenv("CFDB_SITE_HOST", "https://cfdb.example")
    monkeypatch.setattr(workbook, "DATA_BAR_SIMPLE", True)
    monkeypatch.setattr(workbook, "query", _division_aware_query())
    payload, _, _ = workbook.build(2026, 8, "regular", None, "fbs")
    with _zip.ZipFile(BytesIO(payload)) as archive:
        body = "".join(archive.read(n).decode("utf-8") for n in archive.namelist()
                       if n.startswith("xl/worksheets/sheet"))
        for name in archive.namelist():
            if name.startswith("xl/worksheets/sheet"):
                assert not workbook.sheet_order_violations(archive.read(name)), name
    assert "x14:dataBar" not in body, "the fallback must not write the extension"
    assert "dataBar" in body, "but it must still draw a bar"


# === round three: legibility ==============================================================

def test_a_column_is_never_narrower_than_the_longest_word_in_its_header(built):
    """Round 3. R-217 measured the data and went too far: at a flat floor of 6, Excel breaks
    "Favourite" into "Favouri / te", which is harder to read than the wide column it
    replaced. Marc: "shrinking is a little aggressive".

    The floor is the longest WORD now, capped. "Conference game" lands at 10 — not the 15
    that started this, and not the 6 that broke the word.
    """
    from openpyxl.utils import get_column_letter
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    for index in range(1, tab.max_column + 1):
        label = str(tab.cell(header, index).value)
        width = tab.column_dimensions[get_column_letter(index)].width
        if label in workbook.WIDTH_OVERRIDES:
            # Marc set this one by hand with the real file open, which is better information
            # than the measurement has. The override is asserted instead.
            assert width == workbook.WIDTH_OVERRIDES[label], label
            continue
        longest_word = max((len(w) for w in label.split()), default=0)
        expected_floor = max(workbook.MIN_COLUMN_WIDTH,
                             min(longest_word, workbook.HEADER_WORD_CAP))
        assert width >= expected_floor, (
            f"{label!r} is {width} wide; its longest word is {longest_word} and will break")
        # ...and the change must not have undone R-217. A column is still not as wide as its
        # whole header just because the header is long.
        if len(label) > workbook.HEADER_WORD_CAP and " " in label:
            assert width < len(label), f"{label!r} is back to fitting its entire header"


def test_the_header_is_top_aligned_and_centred(built):
    """Marc, round 3. Vertical TOP matters more than it sounds: with a wrapped header the row
    is as tall as the WORST label, so a vertically centred one-line header floats in the
    middle of a four-line row and no two headers share a baseline."""
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    for index in range(1, tab.max_column + 1):
        alignment = tab.cell(header, index).alignment
        assert alignment.vertical == "top", index
        assert alignment.horizontal == "center", index
        assert alignment.wrap_text is True, index


def test_the_mark_columns_are_centred_and_the_others_are_not(built):
    """A one-character mark left-aligned in a 6-wide column reads as a typo."""
    _, book, _, _ = built
    schedule = next(s for s in workbook.SHEETS if s.name == "Schedule")
    tab = book["Schedule"]
    header = workbook.header_row(1)
    labels = {tab.cell(header, i).value: i for i in range(1, tab.max_column + 1)}
    centred_labels = {dict(schedule.columns)[f] for f in schedule.centred}
    assert centred_labels == {"Upset level", "Winner covered", "O/U result"}
    for label in centred_labels:
        cell = tab.cell(header + 1, labels[label])
        assert cell.alignment.horizontal == "center", label
    assert tab.cell(header + 1, labels["Away"]).alignment.horizontal != "center"


def test_the_open_marks_are_coloured_and_the_colour_passes_contrast():
    """Marc asked for the OPEN form to carry the colour, and he is right about why: the
    filled shapes are the common case, so colouring the exception is what makes it pop.

    LITERAL BURNT SIENNA FAILS. #E97451 measures 2.97:1 against white — below WCAG AA's 4.5.
    The shipped colour is measured, because this project has already had to fix a glyph that
    was 3.6:1.
    """
    def luminance(hex_rgb):
        channels = [int(hex_rgb[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                    for c in channels]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    rgb = workbook.OPEN_MARK_COLOUR[2:]          # strip the alpha openpyxl wants
    contrast = (1.0 + 0.05) / (luminance(rgb) + 0.05)
    assert contrast >= 4.5, f"#{rgb} is {contrast:.2f}:1 against white"
    assert luminance(rgb) < luminance("E97451"), (
        "the shipped colour must be darker than literal burnt sienna, which fails")


def test_the_legend_glyphs_match_the_sheet_in_size_and_colour(built):
    """A legend whose mark is a different size or colour from the one in the column is a
    picture of a DIFFERENT mark, which is worse than no legend."""
    _, book, _, _ = built
    tab = book["Index"]
    seen = {}
    for row in tab.iter_rows():
        for cell in row:
            if cell.value in workbook.OPEN_MARKS or cell.value in ("●", "■", "▲", "▼"):
                seen[cell.value] = cell.font
    assert seen, "no legend glyphs found on the Index"
    # 12 IS MARC'S NUMBER, asserted as the requirement rather than against the constant.
    # The first version compared to MARK_FONT_SIZE, so lowering the constant moved the test
    # with it and the check stayed green — a test that restates the implementation.
    assert workbook.MARK_FONT_SIZE >= 12, workbook.MARK_FONT_SIZE
    for glyph, font in seen.items():
        assert font.size >= 12, (glyph, font.size)
        if glyph in workbook.OPEN_MARKS:
            assert font.color is not None and \
                font.color.rgb == workbook.OPEN_MARK_COLOUR, (glyph, font.color)


def test_the_open_marks_in_the_sheet_carry_the_same_colour(built):
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    labels = {tab.cell(header, i).value: i for i in range(1, tab.max_column + 1)}
    coloured = 0
    for row in range(header + 1, tab.max_row + 1):
        for label in ("Upset level", "Winner covered", "O/U result"):
            cell = tab.cell(row, labels[label])
            if cell.value in workbook.OPEN_MARKS:
                assert cell.font.color.rgb == workbook.OPEN_MARK_COLOUR, cell.coordinate
                assert cell.font.size >= 12
                coloured += 1
    assert coloured, "no open mark appeared in the fixture, so this proved nothing"


# === round four ===========================================================================

def test_low_cardinality_text_is_centred_and_prose_is_not(monkeypatch):
    """Marc: "for any text fields with cardinality <5 make them center aligned".

    A frame with ENOUGH ROWS TO JUDGE, because the rule reads the shape of the data and the
    two-row fixture cannot show it: with two rows every text column looks like a category,
    team names included.
    """
    import pandas as _pd
    rows = workbook.MIN_ROWS_TO_JUDGE_CARDINALITY + 8
    frame = _pd.DataFrame({
        "status": ["Final", "Scheduled"] * (rows // 2),                  # 2 distinct
        "season_type": ["regular"] * rows,                               # 1
        "home_team_display": [f"Team {i}" for i in range(rows)],         # all distinct
        "venue_display": [f"Stadium {i}" for i in range(rows)],          # all distinct
        "weather_condition": ["Clear", "Rain", "Cloudy", "Fog", "Snow"] * (rows // 5),
    })
    found = workbook._low_cardinality_text(frame, list(frame.columns))
    assert "status" in found and "season_type" in found
    assert "home_team_display" not in found, "a team name is prose, not a category"
    assert "venue_display" not in found
    assert "weather_condition" not in found, "five distinct values is NOT fewer than five"


def test_the_cardinality_rule_declines_to_judge_a_short_export():
    """A one-game export must not come out looking nothing like a fifty-game one. Below the
    threshold every text column is trivially low-cardinality and the rule abstains."""
    import pandas as _pd
    tiny = _pd.DataFrame({"home_team_display": ["Rice", "Auburn"]})
    assert workbook._low_cardinality_text(tiny, ["home_team_display"]) == set()


def test_nulls_do_not_count_towards_cardinality():
    """A column of Yes / No / blank is two categories. Counting the blank would push a
    three-value column over the line for no reason a reader would recognise."""
    import pandas as _pd
    rows = workbook.MIN_ROWS_TO_JUDGE_CARDINALITY + 4
    frame = _pd.DataFrame({"verdict": (["Yes", "No", None, "Push"] * rows)[:rows]})
    assert "verdict" in workbook._low_cardinality_text(frame, ["verdict"])


def test_the_header_row_clears_the_tables_filter_buttons(built):
    """Marc: the header needs "enough room to be above the drop-down filters". An Excel Table
    puts a filter button INSIDE the header cell, and it overlaps the last line of a wrapped
    label."""
    _, book, _, _ = built
    tab = book["Schedule"]
    assert tab.row_dimensions[workbook.header_row(1)].height >= 50


def test_the_fifty_point_floor_never_shortens_a_header_that_needs_more(monkeypatch):
    """The floor must not become a FIXED height — that is R-217's clipping defect returning
    by another route.

    Asserted on a BUILT FILE, not only on the computation. The first version tested
    `_header_height` alone and stayed green when the build was changed to write
    MIN_HEADER_HEIGHT unconditionally: the function was still right and the workbook was
    still wrong. Nothing in the fixture needs more than 50pt, so this makes a sheet that does.
    """
    tall = workbook._header_height([("Supercalifragilistic Expialidocious Header", 6)])
    assert tall > workbook.MIN_HEADER_HEIGHT

    monkeypatch.setenv("CFDB_SITE_HOST", "https://cfdb.example")
    monkeypatch.setattr(workbook, "query", _division_aware_query())
    schedule = next(s for s in workbook._ALL_SHEETS if s.name == "Schedule")
    stretched = workbook.Sheet(
        "Schedule", schedule.view, schedule.sql,
        [(schedule.columns[0][0], "Supercalifragilistic Expialidocious Header")]
        + list(schedule.columns[1:]),
        has_predictions=schedule.has_predictions,
        sheet_disclaimer=schedule.sheet_disclaimer,
        derived=schedule.derived, display=schedule.display,
        link_fields=schedule.link_fields, freeze_before=schedule.freeze_before)
    monkeypatch.setattr(workbook, "SHEETS", [stretched])
    payload, _, _ = workbook.build(2026, 8, "regular", None, "fbs")
    from openpyxl import load_workbook
    tab = load_workbook(BytesIO(payload))["Schedule"]
    height = tab.row_dimensions[workbook.header_row(1)].height
    assert height > workbook.MIN_HEADER_HEIGHT, (
        f"a header needing {tall}pt was written at {height}pt — the floor has become a "
        f"ceiling and long headers will clip")


def test_the_upset_mark_repeats_once_per_level():
    """Marc, round 4. The site distinguishes levels by SHADE, which a filter dropdown cannot
    carry — "show me every blowout" would mean picking a colour. Repetition keeps the
    ordering, sorts correctly (●● after ●) and gives each level its own dropdown entry."""
    assert workbook.UPSET_MARKS["upset"] == "●"
    assert workbook.UPSET_MARKS["big"] == "●●"
    assert workbook.UPSET_MARKS["blowout"] == "●●●"
    assert workbook.UPSET_MARKS["none"] == "○"
    levels = ["upset", "big", "blowout"]
    lengths = [len(workbook.UPSET_MARKS[k]) for k in levels]
    assert lengths == sorted(lengths) == [1, 2, 3], "the mark must grow WITH the level"
    assert sorted(workbook.UPSET_MARKS[k] for k in levels) == ["●", "●●", "●●●"], (
        "repetition must sort in level order, which is half the reason for it")


def test_every_repeated_mark_is_in_the_legend(built):
    """Two circles is a different value from one in the filter dropdown, so it needs its own
    line. A legend that explains ● and leaves the reader to infer ●●● is not a legend."""
    _, book, _, _ = built
    text = "\n".join(str(c.value) for r in book["Index"].iter_rows() for c in r)
    for glyph in set(workbook.UPSET_MARKS.values()):
        assert f"\n{glyph}\n" in f"\n{text}\n" or glyph in text, glyph
    legend_marks = {mark for _, mark, _ in workbook.MARK_LEGEND}
    for glyph in workbook.UPSET_MARKS.values():
        assert glyph in legend_marks, f"{glyph} is rendered and not explained"


def test_the_hand_set_widths_are_exactly_what_marc_measured(built):
    """Six columns he sized himself in Excel's width dialog with the real file open. That is
    better information than the measurement has, so it wins for these and nothing else."""
    from openpyxl.utils import get_column_letter
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    labels = {tab.cell(header, i).value: i for i in range(1, tab.max_column + 1)}
    assert workbook.WIDTH_OVERRIDES == {
        "Winner covered": 8.0, "Final margin": 5.85, "Season": 5.6,
        "Wind mph": 5.5, "Pred margin": 6.5, "Home win prob": 7.7}
    for label, expected in workbook.WIDTH_OVERRIDES.items():
        letter = get_column_letter(labels[label])
        assert tab.column_dimensions[letter].width == expected, label


def test_winner_covered_is_centred_as_well_as_widened(built):
    _, book, _, _ = built
    tab = book["Schedule"]
    header = workbook.header_row(1)
    labels = {tab.cell(header, i).value: i for i in range(1, tab.max_column + 1)}
    index = labels["Winner covered"]
    assert tab.cell(header, index).alignment.horizontal == "center"
    assert tab.cell(header + 1, index).alignment.horizontal == "center"


def test_an_away_home_pair_is_aligned_the_same_way():
    """Measured on 83 real games: `Home record` came out centred and `Away record` left,
    because that week the home side held four distinct records and the away side five.

    Two identical columns aligned differently reads as a defect, and it is a coin flip that
    lands the other way next week. A pair agrees, on prose — the safe default.
    """
    import pandas as _pd
    rows = workbook.MIN_ROWS_TO_JUDGE_CARDINALITY + 8
    frame = _pd.DataFrame({
        "away_team_record_display": [f"{i}-0" for i in range(rows)],       # many
        "home_team_record_display": ["1-0", "0-1"] * (rows // 2),          # few
    })
    fields = list(frame.columns)
    found = workbook._low_cardinality_text(frame, fields)
    assert found == set(), (
        f"the pair disagreed: {found} centred while its sibling was not")

    # And a genuinely low-cardinality pair still centres, both halves.
    both = _pd.DataFrame({
        "away_classification": ["fbs", "fcs"] * (rows // 2),
        "home_classification": ["fbs"] * rows,
    })
    assert workbook._low_cardinality_text(both, list(both.columns)) == {
        "away_classification", "home_classification"}
