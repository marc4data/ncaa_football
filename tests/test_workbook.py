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
    """A real workbook, from stubbed reads."""
    def fake_query(sql, params=None):
        # Every stubbed query still goes through the contract, so a sheet that violates
        # G-1/G-2 fails here rather than in production.
        check_contract(sql)
        for sheet in workbook.SHEETS:
            if f"from {sheet.view}" in " ".join(sql.split()):
                return _frame(sheet.fields)
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


def test_every_prediction_sheet_carries_the_model_disclaimer(built):
    """A workbook leaves the site. The one thing the licence forbids is presenting these
    numbers as CFBD's, and a caption on a web page does not travel with a file."""
    _, book, _, _ = built
    predicting = {s.name for s in workbook.SHEETS if s.has_predictions}
    for name in predicting & set(book.sheetnames):
        text = str(book[name].cell(workbook.ROW_DISCLAIMER, 1).value)
        assert "NOT CollegeFootballData.com predictions" in text, name
        assert "betting advice" in text.lower(), name
        assert "backtests" in text.lower(), name


def test_the_out_of_sample_flag_is_a_column_not_a_footnote(built):
    """AC-15.4. A workbook gets sorted and filtered; a sheet-level note does not survive
    that, and the rows it applied to end up looking like ordinary predictions."""
    edges = next(s for s in workbook.SHEETS if s.name == "Edges")
    assert "is_out_of_sample_week" in edges.fields


# --- AC-15.1 / AC-15.2: the scope rule --------------------------------------------------

def test_every_sheet_reads_exactly_one_serving_view(built):
    """AC-15.2, enforced by the same contract the pages use rather than by reading them."""
    for sheet in workbook.SHEETS:
        assert check_contract(" ".join(sheet.sql.split())) == sheet.view


def test_scoped_sheets_filter_on_the_season(built):
    """AC-15.1. The two unscoped sheets are provenance — which models produced the
    predicted columns, and what the fields mean — not additional data."""
    unscoped = {s.name for s in workbook.SHEETS if not s.scoped}
    assert unscoped == {"Model performance", "Data dictionary"}
    for sheet in workbook.SHEETS:
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
        for index, (field, _) in enumerate(sheet.columns, start=1):
            cell = tab.cell(workbook.ROW_FIRST_DATA, index)
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
    """AC-15.12: freeze panes, autofilter, and conditional formatting where it earns its
    place. The deliverable is meant to be worked in."""
    _, book, _, _ = built
    for sheet in workbook.SHEETS:
        if sheet.name not in book.sheetnames:
            continue
        tab = book[sheet.name]
        assert tab.freeze_panes == f"A{workbook.ROW_FIRST_DATA}", sheet.name
        assert tab.auto_filter.ref, sheet.name
    assert len(book["Edges"].conditional_formatting._cf_rules) > 0


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
            for sheet in workbook.SHEETS
            for name, label in sheet.columns if name == field)
        exported = any(name == field
                       for sheet in workbook.SHEETS for name, _ in sheet.columns)
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
                df = _frame(sheet.fields)
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
                rows += tab.max_row - workbook.ROW_FIRST_DATA + 1
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


def test_the_index_says_when_the_division_filter_could_not_reach_a_sheet(monkeypatch):
    """Only srv_game carries is_fbs_game — verified against the serving schema, not assumed.
    So a scope line reading 'FBS' overstates what five of the seven sheets did, and the
    honest fix is to name it per sheet rather than to quietly imply it."""
    monkeypatch.setattr(workbook, "query", _division_aware_query())
    _, index_rows, _ = workbook.build(2026, 8, "regular", None, "fbs")
    by_name = {entry.name: entry for entry in index_rows}
    assert "does not apply" in by_name["Standings"].note
    assert "does not apply" not in by_name["Schedule"].note


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
