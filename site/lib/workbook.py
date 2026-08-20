"""The Excel deliverable: a workbook of what the user is already looking at.

This is the feature closest to the licence line, so the scope rule is structural rather
than a promise. Every sheet is a query against one serving view, bounded by the same filter
scope the pages use, and there is no control anywhere that widens it — no "all seasons", no
full-corpus dump, no raw layer. A request that amounts to "pull the whole database into
Excel" has no code path here to say yes with.

Three properties carry most of the weight:

  Attribution is structural.   Every sheet writes the CFBD credit into A1 before anything
                               else, and a prediction sheet writes the model disclaimer into
                               A2. Neither is optional per sheet, because a workbook leaves
                               the site and travels on its own.

  Numbers are numbers.         Cells are written as floats with an Excel number format
                               derived from the same precision table the site renders with,
                               so a column reads identically in both places and can still be
                               summed. A workbook of numeric strings is a screenshot with
                               extra steps.

  A missing sheet is named.    A view that returns nothing is omitted and recorded on the
                               index with the reason. An empty tab looks like a bug in the
                               export; a line saying "Edges — no rows in this scope" is an
                               answer.
"""
import io
import re
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from lib import fmt
from lib.query import query

CFBD_CREDIT = ("Data from CollegeFootballData.com. Used under their terms; attribution is "
               "optional under those terms and provided anyway.")
MODEL_DISCLAIMER = (
    "Predictions are cfdb's own, built on a commercially licensed training pack. They are "
    "NOT CollegeFootballData.com predictions and CFBD does not endorse them. Figures are "
    "held-out backtests, not realised betting results. Nothing here is betting advice.")

# Layout is identical on every sheet so a reader learns it once and the freeze pane,
# autofilter and header row are at the same address throughout.
ROW_CREDIT = 1
ROW_DISCLAIMER = 2
ROW_HEADER = 4
ROW_FIRST_DATA = 5


class Sheet:
    """One tab: where it comes from, what it is called, and which columns it shows.

    `columns` are (field, label) pairs. The label is what the site's table renders in that
    column's header — kept as literal text rather than imported from a page, because the
    page's own column carries an HTML renderer (a logo, a chip) that has no meaning in a
    spreadsheet. `tests/test_site_foundation.py` asserts the labels still agree.
    """

    def __init__(self, name: str, view: str, sql: str, columns: List[tuple],
                 has_predictions: bool = False, note: str = "", scoped: bool = True):
        self.name, self.view, self.sql = name, view, sql
        self.columns, self.has_predictions = columns, has_predictions
        self.note, self.scoped = note, scoped

    @property
    def fields(self) -> List[str]:
        return [field for field, _ in self.columns]


SHEETS = [
    Sheet("Schedule", "srv_schedule", """
        select start_date_et, week, away_team_display, away_conference, away_points,
               home_team_display, home_conference, home_points,
               spread_current, total_current, predicted_margin, home_win_probability,
               network, venue_display, is_neutral_site, is_conference_game, is_completed
        from srv_schedule
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and (:conference is null or home_conference = :conference
               or away_conference = :conference)
        order by start_date_et, game_id
        limit 400
    """, [
        ("start_date_et", "Kickoff"), ("week", "Wk"),
        ("away_team_display", "Away"), ("away_conference", "Away conf"),
        ("away_points", "Away pts"),
        ("home_team_display", "Home"), ("home_conference", "Home conf"),
        ("home_points", "Home pts"),
        ("spread_current", "Spread"), ("total_current", "Total"),
        ("predicted_margin", "Pred margin"), ("home_win_probability", "Home win prob"),
        ("network", "TV"), ("venue_display", "Venue"),
        ("is_neutral_site", "Neutral"), ("is_conference_game", "Conference"),
        ("is_completed", "Final"),
    ], has_predictions=True),

    Sheet("Scores", "srv_scoreboard", """
        select game_date, week, away_team_display, away_points,
               home_team_display, home_points, winner, actual_margin,
               excitement_index, is_upset, attendance, venue_display
        from srv_scoreboard
        where season = :season and season_type = :season_type and is_completed
          and (:week is null or week = :week)
        order by game_date desc, game_id
        limit 400
    """, [
        ("game_date", "Date"), ("week", "Wk"),
        ("away_team_display", "Away"), ("away_points", "Away pts"),
        ("home_team_display", "Home"), ("home_points", "Home pts"),
        ("winner", "Winner"), ("actual_margin", "Margin (away−home)"),
        ("excitement_index", "Excitement"), ("is_upset", "Upset"),
        ("attendance", "Attendance"), ("venue_display", "Venue"),
    ]),

    Sheet("Odds", "srv_odds_board", """
        select start_date_et, week, away_team_display, home_team_display,
               provider_display, spread, spread_open, total, total_open,
               home_moneyline, away_moneyline,
               home_implied_probability, away_implied_probability, devig_method,
               is_best_home_spread, is_best_away_spread, snapshot_ts
        from srv_odds_board
        where season = :season and is_latest_snapshot
          and (:week is null or week = :week)
        order by start_date_et, game_id, provider_display
        limit 900
    """, [
        ("start_date_et", "Kickoff"), ("week", "Wk"),
        ("away_team_display", "Away"), ("home_team_display", "Home"),
        ("provider_display", "Book"),
        ("spread", "Spread"), ("spread_open", "Open"),
        ("total", "Total"), ("total_open", "Total open"),
        ("home_moneyline", "Home ML"), ("away_moneyline", "Away ML"),
        ("home_implied_probability", "Home implied"),
        ("away_implied_probability", "Away implied"),
        ("devig_method", "De-vig method"),
        ("is_best_home_spread", "Best home"), ("is_best_away_spread", "Best away"),
        ("snapshot_ts", "Snapshot"),
    ]),

    Sheet("Edges", "srv_edge_finder", """
        select week, away_team, home_team, market, edge_unit, edge_value, edge_magnitude,
               model_name, confidence_bucket,
               spread_home_perspective, predicted_margin_home_perspective,
               market_implied_home_win_probability, predicted_home_win_probability,
               actual_home_cover, cover_correct, home_win_correct, is_out_of_sample_week
        from srv_edge_finder
        where season = :season
          and (:week is null or week = :week)
        order by edge_magnitude desc
        limit 400
    """, [
        ("week", "Wk"), ("away_team", "Away"), ("home_team", "Home"),
        ("market", "Market"), ("edge_unit", "Unit"),
        ("edge_value", "Edge"), ("edge_magnitude", "Edge size"),
        ("model_name", "Model"), ("confidence_bucket", "Confidence"),
        ("spread_home_perspective", "Market spread"),
        ("predicted_margin_home_perspective", "Model margin"),
        ("market_implied_home_win_probability", "Market win prob"),
        ("predicted_home_win_probability", "Model win prob"),
        ("actual_home_cover", "Home covered"), ("cover_correct", "Cover hit"),
        ("home_win_correct", "Winner hit"),
        # AC-15.4: the flag is per ROW, not a sheet-level footnote. A workbook gets
        # filtered and sorted, and a caption does not survive that.
        ("is_out_of_sample_week", "Out-of-sample week"),
    ], has_predictions=True),

    Sheet("Standings", "srv_standings", """
        select conference, tiebreak_rank, school, wins, losses, ties,
               conference_wins, conference_losses, win_pct,
               points_for, points_against, point_differential, tiebreak_basis
        from srv_standings
        where season = :season and classification in ('fbs','fcs')
        order by conference, tiebreak_rank
        limit 1000
    """, [
        ("conference", "Conference"), ("tiebreak_rank", "#"), ("school", "Team"),
        ("wins", "W"), ("losses", "L"), ("ties", "T"),
        ("conference_wins", "Conf W"), ("conference_losses", "Conf L"),
        ("win_pct", "Win %"),
        ("points_for", "PF"), ("points_against", "PA"),
        ("point_differential", "Diff"), ("tiebreak_basis", "Tiebreak"),
    ], note="Season-scoped: standings are a season figure, not a week one."),

    # Not week-scoped, and deliberately so. These two describe the export rather than adding
    # to it: which models produced the predicted columns, and what every field means. Both
    # are small, and shipping predictions without either would be shipping numbers with no
    # way to check what they are.
    Sheet("Model performance", "srv_model_performance", """
        select model_name, model_version, model_family, split, season,
               is_out_of_sample_week, games, mean_absolute_margin_error,
               winner_accuracy_pct, ats_accuracy_pct, brier_score, log_loss, attribution
        from srv_model_performance
        order by winner_accuracy_pct desc nulls last
        limit 200
    """, [
        ("model_name", "Model"), ("model_version", "Version"),
        ("model_family", "Family"), ("split", "Split"), ("season", "Season"),
        ("is_out_of_sample_week", "Out-of-sample week"), ("games", "n"),
        ("mean_absolute_margin_error", "Margin MAE"),
        ("winner_accuracy_pct", "SU %"), ("ats_accuracy_pct", "ATS %"),
        ("brier_score", "Brier"), ("log_loss", "Log loss"),
        ("attribution", "Attribution"),
    ], has_predictions=True, scoped=False,
        note="Model-level provenance for the predicted columns, not week-scoped."),

    Sheet("Data dictionary", "srv_data_dictionary", """
        select layer, table_name, column_name, data_type, is_nullable,
               description_status, column_description
        from srv_data_dictionary
        where layer = 'serving'
        order by table_name, ordinal_position
        limit 2000
    """, [
        ("layer", "Layer"), ("table_name", "Table"), ("column_name", "Column"),
        ("data_type", "Type"), ("is_nullable", "Nullable"),
        ("description_status", "Status"), ("column_description", "Description"),
    ], scoped=False,
        note="AC-15.8 / AC-16.7: generated from the same view the site's Data Dictionary "
             "page reads, so the workbook and the page cannot disagree."),
]

# Conditional formatting goes on the columns a reader is scanning for outliers. Anything
# else would be decoration, and a spreadsheet where everything is highlighted highlights
# nothing.
# AC-15.8 says the workbook's headers match the site's. Where they deliberately do not,
# the reason is recorded here rather than left as a discrepancy someone rediscovers — and
# the test enforces that any divergence is one of these and not an accident.
EXPORT_ONLY_LABELS = {
    "away_points": "the site's header is blank, because the score renders beside the team "
                   "name; a spreadsheet column cannot have a blank header",
    "home_points": "as away_points",
}

COLOUR_SCALE_FIELDS = {"edge_value", "edge_magnitude", "point_differential",
                       "actual_margin", "predicted_margin"}
FLAG_FIELDS = {"cover_correct", "home_win_correct", "is_upset", "is_out_of_sample_week",
               "is_best_home_spread", "is_best_away_spread", "actual_home_cover"}


def number_format(field: str) -> str:
    """Excel format string at the SAME precision the site renders (AC-G.31, AC-15.7).

    Derived from fmt.precision_for rather than restated, so a column cannot read 1 dp on
    screen and 2 dp in the workbook. Integer-ish columns are the explicit exception:
    attendance, a moneyline and a week number are counts, and a decimal point on any of
    them makes it look like a measurement.
    """
    if field in ("attendance", "week", "season", "games", "home_points", "away_points",
                 "wins", "losses", "ties", "conference_wins", "conference_losses",
                 "tiebreak_rank", "n"):
        return "#,##0"
    if field.endswith("moneyline"):
        return "+#,##0;-#,##0"
    return "#,##0." + "0" * fmt.precision_for(field)


def filename(season: int, week: Optional[int], generated: datetime) -> str:
    """AC-15.10: the filename states its own scope.

    A folder of files called `export.xlsx` is a folder of files nobody can tell apart, and
    the scope is the single most important thing about an export whose whole design is
    being bounded.
    """
    scope = f"week{week:02d}" if week is not None else "season"
    return f"cfdb_{scope}_{season}_{generated:%Y%m%d}.xlsx"


def describe_scope(season: int, week: Optional[int], season_type: str,
                   conference: Optional[str]) -> str:
    bits = [f"season {season}", season_type]
    bits.append(f"week {week}" if week is not None else "all weeks")
    if conference:
        bits.append(conference)
    return ", ".join(bits)


def read_sheet(sheet, season, week, season_type, conference):
    """Fetch one sheet's rows. Returns (frame, omission_reason).

    The two failures here are NOT the same thing and the first draft of this treated them
    as one. AC-15.5 says a sheet whose SOURCE IS MISSING is omitted with a note — that is a
    view cfdb has not built. A connection failure, a permission error or a typo'd column is
    not that, and reporting it as "omitted, no rows in this scope" produces a workbook that
    calmly says the data is unavailable while the real problem is that nothing can be read
    at all. Every sheet was omitted for exactly that reason on the first run of this module,
    and the message gave no way to tell.

    So: a missing relation is an omission, and anything else is raised.
    """
    params = {"season": season, "week": week if sheet.scoped else None,
              "season_type": season_type, "conference": conference}
    wanted = set(re.findall(r":(\w+)", sheet.sql))
    try:
        df = query(" ".join(sheet.sql.split()),
                   {k: v for k, v in params.items() if k in wanted})
    except Exception as exc:                                       # noqa: BLE001
        message = str(exc).lower()
        if "does not exist" in message or "undefined table" in message:
            return None, f"{sheet.view} has not been built yet"
        raise
    if df.empty:
        return None, f"{sheet.view} returned no rows in this scope"
    return df, None


def _clean(value):
    """One cell value openpyxl will accept, preserving the null/zero distinction.

    Two things here are not cosmetic. A tz-aware datetime makes openpyxl raise outright,
    and NaN written into a cell is what produces the repair prompt AC-15.6 forbids — the
    file is structurally valid XML and Excel still refuses it. Both are converted rather
    than left to fail at write time, where the traceback would name the cell and not the
    reason.
    """
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value.strip() == "":
        # The prediction pack writes an empty string where it has no confidence bucket. An
        # empty-string cell is not an empty cell — it is text that looks like nothing, and
        # it breaks COUNTBLANK and sorts ahead of real values. Blank and absent are the
        # same claim here, exactly as they are on the page.
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime) and value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if hasattr(value, "item"):                       # numpy scalar
        value = value.item()
    from decimal import Decimal
    if isinstance(value, Decimal):
        return float(value)
    return value


def build(season: int, week: Optional[int], season_type: str = "regular",
          conference: Optional[str] = None) -> tuple:
    """Build the workbook for one scope. Returns (bytes, index_rows, omitted).

    Returns the omissions alongside the bytes rather than logging them, because the caller
    has to show the user what is NOT in the file they are about to download.
    """
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    generated = datetime.now(timezone.utc)
    book = Workbook()
    book.remove(book.active)              # the default sheet, before Index is written

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F4858")
    note_font = Font(italic=True, size=9, color="555555")

    index_rows, omitted = [], []

    for sheet in SHEETS:
        # AC-15.5: a sheet with nothing to say is omitted and named. The view name goes in
        # the note so the omission points at an object rather than at a mood.
        df, reason = read_sheet(sheet, season, week, season_type, conference)
        if df is None:
            omitted.append((sheet.name, reason))
            continue

        tab = book.create_sheet(sheet.name)

        # AC-15.3 / AC-15.4, written before anything else so no sheet can exist without it.
        tab.cell(ROW_CREDIT, 1, CFBD_CREDIT).font = note_font
        if sheet.has_predictions:
            tab.cell(ROW_DISCLAIMER, 1, MODEL_DISCLAIMER).font = note_font

        for index, (_, label) in enumerate(sheet.columns, start=1):
            cell = tab.cell(ROW_HEADER, index, label)
            cell.font, cell.fill = header_font, header_fill
            cell.alignment = Alignment(vertical="center", wrap_text=True)

        for offset, (_, record) in enumerate(df.iterrows()):
            for index, field in enumerate(sheet.fields, start=1):
                value = _clean(record.get(field))
                cell = tab.cell(ROW_FIRST_DATA + offset, index, value)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cell.number_format = number_format(field)
                elif isinstance(value, datetime):
                    cell.number_format = "yyyy-mm-dd hh:mm"

        last_row = ROW_FIRST_DATA + len(df) - 1
        last_column = get_column_letter(len(sheet.columns))
        # AC-15.12: native Excel affordances, so the file is workable rather than readable.
        tab.freeze_panes = f"A{ROW_FIRST_DATA}"
        tab.auto_filter.ref = f"A{ROW_HEADER}:{last_column}{last_row}"
        for index, (field, label) in enumerate(sheet.columns, start=1):
            letter = get_column_letter(index)
            tab.column_dimensions[letter].width = min(
                max(len(label) + 4, 11), 42 if field.endswith("description") else 24)
            span = f"{letter}{ROW_FIRST_DATA}:{letter}{last_row}"
            if field in COLOUR_SCALE_FIELDS:
                tab.conditional_formatting.add(span, ColorScaleRule(
                    start_type="min", start_color="F8696B",
                    mid_type="percentile", mid_value=50, mid_color="FFEB84",
                    end_type="max", end_color="63BE7B"))
            elif field in FLAG_FIELDS:
                tab.conditional_formatting.add(span, CellIsRule(
                    operator="equal", formula=["TRUE"],
                    fill=PatternFill("solid", fgColor="D8EFD3")))

        index_rows.append((sheet.name, sheet.view, len(df), sheet.note))

    _write_index(book, season, week, season_type, conference, generated,
                 index_rows, omitted, header_font, header_fill, note_font)

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue(), index_rows, omitted


def _write_index(book, season, week, season_type, conference, generated,
                 index_rows, omitted, header_font, header_fill, note_font) -> None:
    """AC-15.9. The index is the sheet that makes the workbook auditable a month later.

    It states when the file was made, exactly what scope it covers, how many rows each tab
    holds, which model version produced any predicted column, and — the part that matters
    most — what is NOT here and why.
    """
    from openpyxl.utils import get_column_letter

    tab = book.create_sheet("Index", 0)
    tab.cell(ROW_CREDIT, 1, CFBD_CREDIT).font = note_font
    tab.cell(ROW_DISCLAIMER, 1, MODEL_DISCLAIMER).font = note_font

    row = ROW_HEADER
    tab.cell(row, 1, "cfdb export").font = header_font
    tab.cell(row, 1).fill = header_fill
    row += 2

    # The model version is read from the data rather than stated, so it cannot describe a
    # different run than the one in the file.
    try:
        versions = query("""select distinct model_version, model_name
                            from srv_model_performance limit 20""")
        model_version = ", ".join(
            f"{r.model_name} {r.model_version}" for r in versions.itertuples()) or "none"
    except Exception:                                              # noqa: BLE001
        model_version = "unavailable"

    for label, value in (
        ("Generated (UTC)", generated.strftime("%Y-%m-%d %H:%M:%S")),
        ("Scope", describe_scope(season, week, season_type, conference)),
        ("Model version(s)", model_version),
        ("Source", "cfdb serving layer; every sheet is one serving view"),
    ):
        tab.cell(row, 1, label).font = header_font
        tab.cell(row, 2, value)
        row += 1

    row += 1
    for index, label in enumerate(("Sheet", "Serving view", "Rows", "Note"), start=1):
        cell = tab.cell(row, index, label)
        cell.font, cell.fill = header_font, header_fill
    row += 1
    for name, view, count, note in index_rows:
        tab.cell(row, 1, name)
        tab.cell(row, 2, view)
        tab.cell(row, 3, count).number_format = "#,##0"
        tab.cell(row, 4, note)
        row += 1

    row += 1
    tab.cell(row, 1, "Not included in this workbook").font = header_font
    row += 1
    if omitted:
        for name, reason in omitted:
            tab.cell(row, 1, name)
            tab.cell(row, 2, reason)
            row += 1
    else:
        tab.cell(row, 1, "Nothing — every sheet had rows in this scope.")
        row += 1

    row += 1
    tab.cell(row, 1, "Scope is bounded by the filters on the Excel Export page. cfdb does "
                     "not offer a full-corpus or raw-layer export.").font = note_font

    for index, width in enumerate((26, 34, 12, 60), start=1):
        tab.column_dimensions[get_column_letter(index)].width = width
