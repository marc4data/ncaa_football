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
import os
import re
from datetime import datetime, timezone
from typing import Callable, Dict, List, NamedTuple, Optional
from urllib.parse import quote

import pandas as pd

from lib import fmt
from lib.query import query

CFBD_CREDIT = ("Data from CollegeFootballData.com. Used under their terms; attribution is "
               "optional under those terms and provided anyway.")
MODEL_DISCLAIMER = (
    "Predictions are cfdb's own, built on a commercially licensed training pack. They are "
    "NOT CollegeFootballData.com predictions and CFBD does not endorse them. Figures are "
    "held-out backtests, not realised betting results. Nothing here is betting advice.")

# THE NOTE BLOCK IS AS LONG AS IT NEEDS TO BE, THEN EXACTLY ONE BLANK ROW, THEN THE HEADER.
#
# R-181, and Marc calls it a global requirement: "there needs to be 1 empty row between
# disclaimer info and the header row of the dataset — global requirement to help play to how
# sorting works in Excel."
#
# It used to be four constants — credit 1, disclaimer 2, header 4, data 5 — which gives
# exactly one blank row on a sheet WITH the model disclaimer and TWO on a sheet without it.
# Excel treats a blank row as the end of a region, so the second blank is not cosmetic: it
# changes what Ctrl+A and a header-click select.
#
# WHAT THIS COSTS, SAID OUT LOUD. `ROW_HEADER = 4` existed so "the freeze pane, autofilter and
# header row are at the same address throughout", and a computed header gives that up. The
# replacement is stronger, which is why the trade is worth taking: with Excel Tables (R-182)
# every data range is a NAMED OBJECT that Excel resolves for itself, so nothing downstream
# needs the address at all. Anyone tempted to restore the constant should restore the Tables
# first and then discover there is nothing left for it to do.
ROW_CREDIT = 1
BLANK_ROWS_BEFORE_HEADER = 1


def header_row(note_lines: int) -> int:
    """The 1-based row the header sits on, given how many note lines precede it."""
    return note_lines + BLANK_ROWS_BEFORE_HEADER + 1


def first_data_row(note_lines: int) -> int:
    return header_row(note_lines) + 1


# Retained ONLY because `_write_index` writes a fixed two-line note block of its own and the
# rest of the module reads these for the index's own layout. Data sheets compute their rows.
ROW_DISCLAIMER = 2

# THE ROW CAP, NAMED, AND RAISED — R-196.
#
# It was `limit 400` written into three of the seven queries as a literal, which is two
# problems. Nothing named it, so nothing could report it; and 400 is below the size of the
# thing a user most obviously asks for. Measured on the serving database:
#
#     one FBS week          ~55 games   (2025 regular: avg 55.5, range 51-96)
#     one FBS season        ~900
#     one season, all divisions        3,745      <- 400 returned 11% of it
#
# 5,000 clears a full all-divisions season with room, which is the widest scope the filter
# bar can express. It is a CAP, not a target: the point is that the file cannot become
# unbounded, not that it should approach this.
ROW_CAP = 5000


def site_base_url() -> Optional[str]:
    """The public origin of the site, or None if nobody has told us what it is.

    R-183. `CFDB_SITE_HOST` is set on the droplet and in `.env`, and the tunnel's hostname
    lives in the Cloudflare dashboard — so it is reachable at build time and must never be
    guessed. **If it is unset the workbook ships with no hyperlinks and the Index says so**,
    because a file full of `http://None/...` is worse than a file with none: it is the R-151
    shape exactly, a link that resolves in dev and 404s in what the user downloaded.
    """
    host = (os.getenv("CFDB_SITE_HOST") or "").strip().rstrip("/")
    if not host:
        return None
    return host if host.startswith(("http://", "https://")) else f"https://{host}"


def _scoped_query(season, week, season_type, conference, division, **extra) -> str:
    """The query string that CARRIES THE SCOPE FORWARD, as `GameScope.link()` does.

    A link that drops the season is the defect that made choosing 2025 and clicking a team
    return a 2026 page. It is worse in a workbook, which is read weeks later.
    """
    carried = {"season": season, "week": week,
               "season_type": None if season_type == "regular" else season_type,
               "conference": conference,
               "division": None if division == "fbs" else division}
    carried.update(extra)
    pairs = [f"{k}={quote(str(v))}" for k, v in carried.items() if v is not None]
    return "&".join(pairs)


# Excel's own rules for a table's displayName, enforced rather than discovered: unique in the
# workbook, starts with a letter or underscore, no spaces, nothing Excel reads as an operator,
# and it must not look like a cell reference. A duplicate or an illegal name is a repair
# prompt, not an exception — the file writes cleanly and Excel refuses it.
CELL_REFERENCE = re.compile(r"^[A-Za-z]{1,3}[0-9]+$")


def _team_url(base, slug, **scope):
    if not base or not slug or (isinstance(slug, float) and pd.isna(slug)):
        return None
    query = _scoped_query(**scope, team=slug)
    return f"{base}/team?{query}" if query else f"{base}/team"


def _matchup_url(base, game_id, **scope):
    """A link is a convenience; it must never be able to fail a build.

    `int()` on a game id that is not one raises, and this runs once per row — so a single
    malformed value would take out the whole workbook to save one hyperlink. No link is the
    right answer for a row we cannot address.
    """
    if not base or game_id is None or (isinstance(game_id, float) and pd.isna(game_id)):
        return None
    try:
        identifier = int(game_id)
    except (TypeError, ValueError):
        return None
    query = _scoped_query(**scope, game_id=identifier)
    return f"{base}/matchup?{query}" if query else f"{base}/matchup"


def _weekday(record):
    """Thu / Fri / Sat — the thing a reader plans around, which a datetime does not answer
    without a formula."""
    value = record.get("game_date")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return pd.Timestamp(value).strftime("%a")
    except (ValueError, TypeError):
        return None


def _status(record):
    """Scheduled / Final. `is_completed` is a boolean the reader has to translate; a word is
    what they would have written in the cell themselves."""
    value = record.get("is_completed")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return "Final" if bool(value) else "Scheduled"


def table_name(sheet_name: str) -> str:
    """`tbl_<SheetName>`, scrubbed to something Excel will accept."""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", sheet_name.title().replace(" ", ""))
    name = f"tbl_{cleaned}"
    if CELL_REFERENCE.match(name) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError(f"{sheet_name!r} does not yield a legal Excel table name: {name!r}")
    return name


class Sheet:
    """One tab: where it comes from, what it is called, and which columns it shows.

    `columns` are (field, label) pairs. The label is what the site's table renders in that
    column's header — kept as literal text rather than imported from a page, because the
    page's own column carries an HTML renderer (a logo, a chip) that has no meaning in a
    spreadsheet. `tests/test_site_foundation.py` asserts the labels still agree.
    """

    def __init__(self, name: str, view: str, sql: str, columns: List[tuple],
                 has_predictions: bool = False, note: str = "", scoped: bool = True,
                 derived: Optional[Dict[str, Callable]] = None,
                 link_fields: Optional[Dict[str, str]] = None):
        self.name, self.view = name, view
        # Columns the sheet COMPUTES rather than selects — a weekday name, a status word, a
        # URL. They are real columns to the reader and to Excel; they simply have no
        # counterpart in the view, and putting them here keeps `fields` the single list that
        # both the writer and the width measurement walk.
        self.derived: Dict[str, Callable] = derived or {}
        # {column field -> what it links to}. Resolved at build time because the target
        # origin is an environment value, not a repo one.
        self.link_fields: Dict[str, str] = link_fields or {}
        # `{ROW_CAP}` rather than a literal, resolved once here. The contract's LIMIT check
        # (AC-G.39) matches `limit <digits>`, so a bind parameter would fail it — the cap has
        # to reach the SQL as a number. `ci/check_page_queries.py` substitutes the same hole
        # before executing, the way it already does for `{side}`.
        self.sql = sql.replace("{ROW_CAP}", str(ROW_CAP))
        self.columns, self.has_predictions = columns, has_predictions
        self.note, self.scoped = note, scoped

    @property
    def division_scoped(self) -> bool:
        """Whether this sheet's query can honour the Division filter.

        Only `srv_game` carries `is_fbs_game` — checked against the serving schema, not
        assumed. A sheet that cannot narrow says so on the Index rather than letting the
        scope line claim a filter it did not apply.
        """
        return ":division" in self.sql

    @property
    def fields(self) -> List[str]:
        return [field for field, _ in self.columns]

    @property
    def selected_fields(self) -> List[str]:
        """The bare column names this query actually selects.

        Not the same list as `fields`: the query also pulls what the sheet DERIVES from
        (`game_date`, `is_completed`), what it LINKS with (the two slugs) and the window
        count. A test fixture built from `fields` alone silently omits all of those, and the
        hyperlinks then look absent rather than unstubbed.
        """
        body = re.search(r"select\s+(.*?)\s+from\s", " ".join(self.sql.split()),
                         re.IGNORECASE | re.DOTALL)
        if not body:
            return []
        out = []
        for piece in body.group(1).split(","):
            piece = piece.strip()
            if not piece or "(" in piece:
                continue
            out.append(piece.split()[-1])
        return out

    @property
    def url_value_fields(self) -> set:
        """Columns whose VALUE is a URL, not just columns that carry a link.

        The distinction matters: a cell hyperlink is invisible to anything that reads the
        file as data, so one column shows the URL as text and survives a copy elsewhere.
        """
        return {f for f in self.link_fields if f.endswith("_url")}

    def value_for(self, field: str, record):
        """One cell's value: computed if this sheet derives it, selected otherwise."""
        builder = self.derived.get(field)
        return builder(record) if builder is not None else record.get(field)

    def hyperlinks(self, base: str, **scope) -> Dict[str, Callable]:
        """{field -> record -> url}, or {} when nothing told us the site's origin."""
        out: Dict[str, Callable] = {}
        for field, kind in self.link_fields.items():
            if kind == "team":
                slug_field = field.replace("_team_display", "_team_slug")
                out[field] = (lambda record, sf=slug_field:
                              _team_url(base, record.get(sf), **scope))
            elif kind == "matchup":
                out[field] = (lambda record:
                              _matchup_url(base, record.get("game_id"), **scope))
        return out


# ONLY THE SCHEDULE SHEET SHIPS THIS PASS. Marc: "only 1 data sheet for now (mapped to the
# Schedule page)", confirmed 2026-09-03 against the alternative of converting all seven.
#
# The other six are NOT deleted. Their SQL and column lists are real work and each gets the
# same treatment one at a time; they sit in PENDING_SHEETS, are named on the Index so the
# absence is an answer rather than a gap, and their queries stay under the CI query checker.
#
# Why not keep them shipping in the OLD layout: a workbook with one sheet whose header row is
# computed and six whose header row is 4 is a file that contradicts itself about where its
# data starts, which is exactly the thing R-181 exists to fix.
_ALL_SHEETS = [
    # ======================================================================================
    # THE SCHEDULE SHEET — sixty-seven columns in ten labelled blocks (R-185).
    #
    # Marc: "a sheet that includes all of the data points we have included on the Schedule
    # page (including filters and any fields used in the underlying logic)." That is what
    # sixty-seven means; it is not padding.
    #
    # THE ORDER IS REASONED AND THE REASONING IS THE PART THAT GETS LOST.
    #
    #   MIRROR THE PAGE, not filter-first. In an Excel Table EVERY column is filterable, so
    #   position buys reading order and adjacency, not capability. "Put the filters on the
    #   left" is a non-argument once the data is a Table.
    #
    #   EMPTY COLUMNS GO RIGHT. Blocks H and I are blank on every upcoming game. A reader
    #   opening this on a Wednesday should not scroll past a wall of nothing to reach the
    #   market numbers, which are the reason they opened it.
    #
    # Default sort is the ORDER BY: a Table's `sortState` is metadata about a sort that was
    # applied and Excel does not re-apply it on open. `start_date_et, game_id` matches AC-2.2
    # and is stable between builds, which a diff of two workbooks depends on.
    # ======================================================================================
    Sheet("Schedule", "srv_game", """
        select week, start_date_et, kickoff_time_known, game_date, is_current_week,
               away_rank, away_team_display, away_team_record_display,
               home_rank, home_team_display, home_team_record_display, best_rank_in_game,
               is_neutral_site, venue_display, is_indoors, network_abbreviation, network,
               season, season_type, away_conference, home_conference,
               away_classification, home_classification, is_conference_game, is_fbs_game,
               spread_current, spread_open, spread_move_from_open,
               total_current, over_under_open, total_move_from_open,
               provider_key, line_snapshot_ts,
               spread_at_close, spread_at_close_provider, spread_at_close_basis,
               total_at_close, total_at_close_provider, total_at_close_basis,
               predicted_margin, home_win_probability, confidence_bucket,
               model_name, model_version_key, is_out_of_sample_week,
               away_points, home_points, winner, actual_margin, final_margin, total_points,
               upset_level, is_upset_by_line, winner_covered_close, favorite_covered,
               over_met, excitement_index, attendance,
               temperature_f, weather_condition, wind_speed_mph, precipitation_in,
               game_id, as_of_ts, attribution,
               is_completed, home_team_slug, away_team_slug,
               count(*) over () as rows_in_scope
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          /* R-184. The Division filter, which this query used to ignore entirely.
             Predicate copied verbatim from `views/schedule.py` rather than re-derived: the
             export must return the set the page showed, and two spellings of one rule is
             how they drift. EITHER team FBS, not both.
             BLOCK comment, not `--`: read_sheet() flattens this SQL onto ONE line, so a
             line comment would swallow every clause after it. (And the wording here avoids
             the word j-o-i-n, because the query contract's FORBIDDEN pattern reads comments
             too — it caught this comment's first draft.) */
          and (:division = 'all' or is_fbs_game)
          and (:conference is null or home_conference = :conference
               or away_conference = :conference)
        order by start_date_et, game_id
        limit {ROW_CAP}
    """, [
        # --- BLOCK A — WHEN. The reader's first question. -------------------------------
        ("week", "Wk"),
        ("start_date_et", "Kickoff"),
        ("kickoff_time_known", "Kickoff confirmed"),
        ("weekday", "Day"),
        ("status", "Status"),
        ("is_current_week", "Current week"),
        # --- BLOCK B — THE FIXTURE ------------------------------------------------------
        ("away_rank", "Away rank"),
        ("away_team_display", "Away"),
        ("away_team_record_display", "Away record"),
        ("home_rank", "Home rank"),
        ("home_team_display", "Home"),
        ("home_team_record_display", "Home record"),
        ("best_rank_in_game", "Best rank"),
        # --- BLOCK C — WHERE AND HOW TO WATCH -------------------------------------------
        ("is_neutral_site", "Neutral site"),
        ("venue_display", "Venue"),
        ("is_indoors", "Indoors"),
        ("network_abbreviation", "TV"),
        ("network", "TV (full)"),
        # --- BLOCK D — SCOPE. The filter columns, spelled out. ---------------------------
        ("season", "Season"),
        ("season_type", "Season type"),
        ("away_conference", "Away conference"),
        ("home_conference", "Home conference"),
        ("away_classification", "Away division"),
        ("home_classification", "Home division"),
        ("is_conference_game", "Conference game"),
        ("is_fbs_game", "FBS game"),
        # --- BLOCK E — THE MARKET NOW. Why someone opens this on a Wednesday. ------------
        ("spread_current", "Spread"),
        # `Spread open` sits beside `Δ Spread` DELIBERATELY and the two must stay adjacent:
        # the delta is null when the line did not move AND when no open was ever recorded.
        # Two different facts, one blank cell; the column beside it is the disambiguation.
        ("spread_open", "Spread open"),
        ("spread_move_from_open", "Δ Spread"),
        ("total_current", "O/U"),
        ("over_under_open", "O/U open"),
        ("total_move_from_open", "Δ O/U"),
        ("provider_key", "Book"),
        ("line_snapshot_ts", "Line taken"),
        # --- BLOCK F — THE CLOSING LINE. What the result gets judged against. ------------
        ("spread_at_close", "Closing spread"),
        ("spread_at_close_provider", "Closing spread book"),
        ("spread_at_close_basis", "Closing spread basis"),
        ("total_at_close", "Closing O/U"),
        ("total_at_close_provider", "Closing O/U book"),
        ("total_at_close_basis", "Closing O/U basis"),
        # --- BLOCK G — THE MODEL --------------------------------------------------------
        ("predicted_margin", "Pred margin"),
        ("home_win_probability", "Home win prob"),
        ("confidence_bucket", "Confidence"),
        ("model_name", "Model"),
        ("model_version_key", "Model version"),
        # AC-15.4: per ROW, never a footnote. A workbook gets filtered and sorted, and a
        # caption does not survive either.
        ("is_out_of_sample_week", "Out-of-sample week"),
        # --- BLOCK H — THE RESULT. Blank on every upcoming game, hence its position. ------
        ("away_points", "Away pts"),
        ("home_points", "Home pts"),
        ("winner", "Winner"),
        ("actual_margin", "Margin (away−home)"),
        ("final_margin", "Final margin"),
        ("total_points", "Total points"),
        # R-193: judged against the CLOSING LINE, and there is no longer a second basis to
        # name. `upset_basis` was dropped the same day the column list was first written.
        ("upset_level", "Upset level"),
        ("is_upset_by_line", "Upset by line"),
        ("winner_covered_close", "Winner covered"),
        # A DIFFERENT QUESTION from the one beside it: this one can also say no_favorite.
        ("favorite_covered", "Favourite covered"),
        ("over_met", "O/U result"),
        ("excitement_index", "Excitement"),
        ("attendance", "Attendance"),
        # --- BLOCK I — CONDITIONS AT KICKOFF. Qualified by Indoors in block C. ------------
        ("temperature_f", "Temperature °F"),
        ("weather_condition", "Condition"),
        ("wind_speed_mph", "Wind mph"),
        ("precipitation_in", "Precipitation in"),
        # --- BLOCK J — KEYS AND PROVENANCE ----------------------------------------------
        ("game_id", "Game id"),
        # The one EXPLICIT url column. A cell hyperlink is invisible to anything that reads
        # the file as data, so the visible column is what survives a copy into another tool.
        # One is enough; team links stay as cell links only.
        ("matchup_url", "Matchup URL"),
        ("as_of_ts", "As of"),
        ("attribution", "Attribution"),
    ], has_predictions=True,
        derived={"weekday": _weekday, "status": _status},
        link_fields={"away_team_display": "team", "home_team_display": "team",
                     "matchup_url": "matchup"}),

    Sheet("Scores", "srv_game", """
        select game_date, week, away_team_display, away_points,
               home_team_display, home_points, winner, actual_margin,
               excitement_index, is_upset, attendance, venue_display,
               count(*) over () as rows_in_scope
        from srv_game
        where season = :season and season_type = :season_type and is_completed
          and (:week is null or week = :week)
          and (:division = 'all' or is_fbs_game)          /* R-184, as Schedule */
        order by game_date desc, game_id
        limit {ROW_CAP}
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
               is_best_home_spread, is_best_away_spread, snapshot_ts,
               count(*) over () as rows_in_scope
        from srv_odds_board
        where season = :season and is_latest_snapshot
          and (:week is null or week = :week)
        order by start_date_et, game_id, provider_display
        limit {ROW_CAP}
    """, [
        ("start_date_et", "Kickoff"), ("week", "Wk"),
        ("away_team_display", "Away"), ("home_team_display", "Home"),
        ("provider_display", "Book"),
        ("spread", "Spread"), ("spread_open", "Open"),
        ("total", "O/U"), ("total_open", "O/U open"),
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
               actual_home_cover, cover_correct, home_win_correct, is_out_of_sample_week,
               count(*) over () as rows_in_scope
        from srv_edge_finder
        where season = :season
          and (:week is null or week = :week)
        order by edge_magnitude desc
        limit {ROW_CAP}
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
               points_for, points_against, point_differential, tiebreak_basis,
               count(*) over () as rows_in_scope
        from srv_standings
        where season = :season and classification in ('fbs','fcs')
        order by conference, tiebreak_rank
        limit {ROW_CAP}
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
    # Every cut, not just the headline. The view stacks overall / week / conference /
    # confidence / probability-decile rows, and segment_type is carried so a filter in the
    # workbook separates them — which is the one thing a spreadsheet is genuinely better at
    # than a page. The headline table on the site reads `segment_type = 'overall'`; here
    # the reader gets the same data plus the breakdowns and does the filtering themselves.
    #
    # cover_scored travels beside ats_accuracy_pct on purpose. A rate without its
    # denominator is the defect AC-G.33 exists to prevent, and it is worse in a workbook,
    # where the column gets averaged.
    Sheet("Model performance", "srv_model_performance", """
        select segment_type, segment_value, model_name, model_version, model_family,
               split, season, is_out_of_sample_week, games,
               mean_absolute_margin_error, winner_accuracy_pct, winner_scored,
               ats_accuracy_pct, cover_scored,
               mean_predicted_home_win_probability, actual_home_win_rate,
               brier_score, log_loss, attribution,
               count(*) over () as rows_in_scope
        from srv_model_performance
        order by model_name, segment_type, segment_order, segment_value
        limit {ROW_CAP}
    """, [
        ("segment_type", "Segment"), ("segment_value", "Segment value"),
        ("model_name", "Model"), ("model_version", "Version"),
        ("model_family", "Family"), ("split", "Split"), ("season", "Season"),
        ("is_out_of_sample_week", "Out-of-sample week"), ("games", "n"),
        ("mean_absolute_margin_error", "Margin MAE"),
        ("winner_accuracy_pct", "SU %"), ("winner_scored", "SU graded"),
        ("ats_accuracy_pct", "ATS %"), ("cover_scored", "ATS graded"),
        ("mean_predicted_home_win_probability", "Model says"),
        ("actual_home_win_rate", "Actually happened"),
        ("brier_score", "Brier"), ("log_loss", "Log loss"),
        ("attribution", "Attribution"),
    ], has_predictions=True, scoped=False,
        note="Every segment: overall, by week, by conference, by confidence, and by "
             "predicted-probability decile. Filter on Segment. Conference rows count a "
             "game under both teams' conferences, so they exceed the overall row."),

    Sheet("Data dictionary", "srv_data_dictionary", """
        select layer, table_name, column_name, data_type, is_nullable,
               description_status, column_description,
               count(*) over () as rows_in_scope
        from srv_data_dictionary
        where layer = 'serving'
        order by table_name, ordinal_position
        limit {ROW_CAP}
    """, [
        ("layer", "Layer"), ("table_name", "Table"), ("column_name", "Column"),
        ("data_type", "Type"), ("is_nullable", "Nullable"),
        ("description_status", "Status"), ("column_description", "Description"),
    ], scoped=False,
        note="AC-15.8 / AC-16.7: generated from the same view the site's Data Dictionary "
             "page reads, so the workbook and the page cannot disagree."),
]

# What the workbook writes, and what it does not write YET. Split rather than filtered, so
# adding a converted sheet is moving one name and cannot be done by accident.
SHEETS = [s for s in _ALL_SHEETS if s.name == "Schedule"]
PENDING_SHEETS = [s for s in _ALL_SHEETS if s.name != "Schedule"]
PENDING_REASON = ("not converted to the new layout yet; it ships in a later pass rather "
                  "than mixing two header layouts in one file")
assert len(SHEETS) == 1 and len(PENDING_SHEETS) == 6

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
    "actual_margin": "the page can say 'Margin' because the column sits between the two "
                     "teams' scores and the direction is obvious in context; a workbook "
                     "travels without that context, so the header states away-minus-home",
    "segment_value": "the page labels this per tab — Week, Conference, Confidence, "
                     "Predicted band — because each tab shows one segment type. The sheet "
                     "stacks all five, so its header has to name the column rather than "
                     "the cut, and Segment sits beside it saying which cut each row is",
    # --- R-182 TRAP 2 made these mandatory to resolve rather than merely tidy. -----------
    # An Excel Table requires unique, non-empty headers, and the Schedule sheet carries both
    # halves of two pairs the page only ever shows one of at a time.
    "network": "the sheet carries BOTH `network_abbreviation` and `network`, because a "
               "spreadsheet reader filtering on 'ESPN' and one reading 'ESPN College "
               "Extra' want different columns. The page shows one of them under 'TV', so "
               "the long form has to be spelled differently — a Table forbids duplicate "
               "headers outright",
    # The next three are all the same divergence: the page can abbreviate because the column
    # sits inside a labelled block with neighbours giving it context. A workbook column
    # travels alone, gets sorted away from its neighbours, and is read a month later.
    "spread_at_close": "the page's 'Close' sits under the line block's own heading, which "
                       "says what is closing. The workbook column has no heading above it "
                       "and no guaranteed neighbour, so it names itself",
    "total_points": "the page's 'Pts' sits in the box score beside the two teams' scores. "
                    "Alone in a spreadsheet, 'Pts' does not distinguish the game total "
                    "from either team's",
    "favorite_covered": "the page's 'Fav cover' is a narrow column in a strip of marks. "
                        "The sheet spells it out because it sits beside 'Winner covered' "
                        "and the two answer DIFFERENT questions — this one can also say "
                        "no_favorite",
    "is_neutral_site": "R-026 then R-101: the Schedule page shows a neutral site as an ICON "
                       "WITH NO LABEL — a deliberate exception to the site's "
                       "glyph-plus-label rule, decided by Marc against a small known user "
                       "base — and R-101 folded that icon into the shared Game column, so "
                       "the site now has NO COLUMN OF ITS OWN for this field at all. A "
                       "spreadsheet has no icon convention and no tooltip, so the column "
                       "keeps a spelled-out header here. This is the divergence being real "
                       "rather than an oversight",
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
                   conference: Optional[str], division: str = "fbs") -> str:
    bits = [f"season {season}", season_type]
    bits.append(f"week {week}" if week is not None else "all weeks")
    if conference:
        bits.append(conference)
    # Mirrors `GameScope.describe()`, which also omits the division when it is "all" —
    # naming a filter that excludes nothing reads as a narrowing that did not happen.
    if division != "all":
        bits.append(division.upper())
    return ", ".join(bits)


class IndexRow(NamedTuple):
    """One line of the Index's sheet inventory, and what the caller shows in the preview.

    `rows` and `rows_in_scope` travel together everywhere for the reason SheetRead names.
    """
    name: str
    view: str
    rows: int
    rows_in_scope: int
    note: str = ""

    @property
    def truncated(self) -> bool:
        return self.rows_in_scope > self.rows


class SheetRead(NamedTuple):
    """What one sheet's query returned.

    `rows` and `rows_in_scope` are DELIBERATELY TWO FIELDS. They were one number for as long
    as the cap was invisible, and that is precisely how a season export could hold 400 of
    3,745 games while every number on the page and in the file agreed with every other.
    """
    frame: Optional[pd.DataFrame]
    omission: Optional[str]
    rows_in_scope: int = 0

    @property
    def rows(self) -> int:
        return 0 if self.frame is None else len(self.frame)

    @property
    def truncated(self) -> bool:
        return self.rows_in_scope > self.rows


def read_sheet(sheet, season, week, season_type, conference, division="fbs"):
    """Fetch one sheet's rows. Returns a SheetRead.

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
              "season_type": season_type, "conference": conference, "division": division}
    wanted = set(re.findall(r":(\w+)", sheet.sql))
    try:
        df = query(" ".join(sheet.sql.split()),
                   {k: v for k, v in params.items() if k in wanted})
    except Exception as exc:                                       # noqa: BLE001
        message = str(exc).lower()
        if "does not exist" in message or "undefined table" in message:
            return SheetRead(None, f"{sheet.view} has not been built yet")
        raise
    if df.empty:
        return SheetRead(None, f"{sheet.view} returned no rows in this scope")
    # ONE QUERY ANSWERS BOTH QUESTIONS. `count(*) over ()` is a window function, and Postgres
    # evaluates window functions BEFORE the LIMIT — so every returned row carries the size of
    # the full result set. A second `select count(*)` would be a second implementation of
    # "what is in scope", free to disagree with the first; this cannot.
    in_scope = int(df["rows_in_scope"].iloc[0]) if "rows_in_scope" in df.columns else len(df)
    return SheetRead(df, None, in_scope)


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
          conference: Optional[str] = None, division: str = "fbs") -> tuple:
    """Build the workbook for one scope. Returns (bytes, index_rows, omitted).

    Returns the omissions alongside the bytes rather than logging them, because the caller
    has to show the user what is NOT in the file they are about to download.

    `division` was missing from this signature until R-184, while `GameScope` had carried it
    since R-165. A user who filtered Schedule to FBS and walked to Excel Export downloaded
    every Division II fixture in the season — 313 rows for a week that held 83.
    """
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
    from openpyxl.worksheet.table import Table as ExcelTable, TableStyleInfo
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    generated = datetime.now(timezone.utc)
    site_host = site_base_url()
    link_scope = {"season": season, "week": week, "season_type": season_type,
                  "conference": conference, "division": division}
    book = Workbook()
    book.remove(book.active)              # the default sheet, before Index is written

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F4858")
    note_font = Font(italic=True, size=9, color="555555")

    index_rows, omitted = [], []

    for sheet in SHEETS:
        # AC-15.5: a sheet with nothing to say is omitted and named. The view name goes in
        # the note so the omission points at an object rather than at a mood.
        read = read_sheet(sheet, season, week, season_type, conference, division)
        df = read.frame
        if df is None:
            omitted.append((sheet.name, read.omission))
            continue

        tab = book.create_sheet(sheet.name)

        # AC-15.3 / AC-15.4, written before anything else so no sheet can exist without it.
        # The block is however many lines this sheet needs; the header address follows from
        # it (R-181) rather than being a constant every sheet has to agree with.
        notes = [CFBD_CREDIT] + ([MODEL_DISCLAIMER] if sheet.has_predictions else [])
        for offset, text in enumerate(notes):
            tab.cell(ROW_CREDIT + offset, 1, text).font = note_font
        row_header = header_row(len(notes))
        row_first_data = first_data_row(len(notes))

        for index, (_, label) in enumerate(sheet.columns, start=1):
            cell = tab.cell(row_header, index, label)
            cell.font, cell.fill = header_font, header_fill
            cell.alignment = Alignment(vertical="center", wrap_text=True)

        links = sheet.hyperlinks(site_host, **link_scope) if site_host else {}
        for offset, (_, record) in enumerate(df.iterrows()):
            for index, field in enumerate(sheet.fields, start=1):
                builder = links.get(field)
                if field in sheet.url_value_fields:
                    # The column IS the url. With no origin resolved it is simply blank,
                    # which is the honest rendering of "nobody told us where the site is".
                    value = _clean(builder(record)) if builder else None
                else:
                    value = _clean(sheet.value_for(field, record))
                cell = tab.cell(row_first_data + offset, index, value)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cell.number_format = number_format(field)
                elif isinstance(value, datetime):
                    cell.number_format = "yyyy-mm-dd hh:mm"
                # R-183. The link goes ON the cell whose text is already the label, never as
                # a HYPERLINK() formula: the value stays real text, so the column still
                # sorts, filters and copies as a name.
                if builder is not None and value is not None:
                    target = builder(record)
                    if target:
                        cell.hyperlink = target
                        cell.style = "Hyperlink"

        last_row = row_first_data + len(df) - 1
        last_column = get_column_letter(len(sheet.columns))
        # AC-15.12: native Excel affordances, so the file is workable rather than readable.
        tab.freeze_panes = f"A{row_first_data}"
        # R-182 TRAP 1: NO `tab.auto_filter.ref` HERE. A Table brings its own filter buttons,
        # and openpyxl documents that a table must not overlap the worksheet's autofilter —
        # an overlap is exactly the "we found a problem with some content" repair prompt that
        # AC-15.6 forbids. The Table below supplies the affordance the autofilter used to.
        table = ExcelTable(displayName=table_name(sheet.name),
                           ref=f"A{row_header}:{last_column}{last_row}")
        # TRAP 3: a TableStyleInfo's header band would override the manual navy fill, and the
        # file would then depend on which Excel applied last. Marc's file should look like it
        # came from cfdb, so the manual header stays and the style contributes banding only —
        # with row stripes off, because banding plus a navy header is two header treatments.
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleLight1", showFirstColumn=False, showLastColumn=False,
            showRowStripes=False, showColumnStripes=False)
        tab.add_table(table)
        # WIDTHS FROM THE DATA, not from the header.
        #
        # The previous version sized every column from its LABEL, so a "Spread" column got
        # 11 characters regardless of what was in it and numeric cells rendered as #######,
        # while a description column got the same treatment and ran off the screen.
        #
        # Measured over the actual values, then clamped. The clamp matters in both
        # directions: a floor so a two-character header is still readable, and a ceiling so
        # one 400-character description does not set the width for the sheet. The header
        # rows are written ABOVE the table and are not measured — the credit line in A1 is
        # 120 characters and would otherwise decide column A on its own, which is exactly
        # how a header blows out the first column.
        for index, (field, label) in enumerate(sheet.columns, start=1):
            letter = get_column_letter(index)
            longest = len(str(label))
            for offset in range(len(df)):
                value = tab.cell(row_first_data + offset, index).value
                if value is None:
                    continue
                if isinstance(value, datetime):
                    rendered = 17
                elif isinstance(value, float):
                    # A float renders at its FORMAT width, not its repr: 0.07894736842105
                    # occupies four characters once the number format is applied.
                    rendered = len(number_format(field).replace("#,##", "").replace(";", ""))
                    rendered = max(rendered, 8)
                else:
                    rendered = len(str(value))
                longest = max(longest, rendered)
            ceiling = 60 if field.endswith("description") or field == "attribution" else 28
            tab.column_dimensions[letter].width = min(max(longest + 3, 9), ceiling)
            span = f"{letter}{row_first_data}:{letter}{last_row}"
            if field in COLOUR_SCALE_FIELDS:
                tab.conditional_formatting.add(span, ColorScaleRule(
                    start_type="min", start_color="F8696B",
                    mid_type="percentile", mid_value=50, mid_color="FFEB84",
                    end_type="max", end_color="63BE7B"))
            elif field in FLAG_FIELDS:
                tab.conditional_formatting.add(span, CellIsRule(
                    operator="equal", formula=["TRUE"],
                    fill=PatternFill("solid", fgColor="D8EFD3")))

        # The note carries what the Index has to be able to say about THIS sheet: that its
        # rows were cut, and — separately — that the Division filter could not reach it.
        note = sheet.note
        if not sheet.division_scoped and division != "all":
            extra = (f"The Division filter ({division.upper()}) does not apply to "
                     f"{sheet.view}, which has no game classification to narrow on.")
            note = f"{note} {extra}".strip()
        index_rows.append(IndexRow(sheet.name, sheet.view, read.rows,
                                   read.rows_in_scope, note))

    _write_index(book, season, week, season_type, conference, division, generated,
                 index_rows, omitted, header_font, header_fill, note_font, site_host)

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue(), index_rows, omitted


def _write_index(book, season, week, season_type, conference, division, generated,
                 index_rows, omitted, header_font, header_fill, note_font,
                 site_host=None) -> None:
    """AC-15.9. The index is the sheet that makes the workbook auditable a month later.

    It states when the file was made, exactly what scope it covers, how many rows each tab
    holds, which model version produced any predicted column, and — the part that matters
    most — what is NOT here and why.
    """
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table as ExcelTable, TableStyleInfo

    tab = book.create_sheet("Index", 0)
    notes = [CFBD_CREDIT, MODEL_DISCLAIMER]
    for offset, text in enumerate(notes):
        tab.cell(ROW_CREDIT + offset, 1, text).font = note_font

    row = header_row(len(notes))
    tab.cell(row, 1, "cfdb export").font = header_font
    tab.cell(row, 1).fill = header_fill
    row += 2

    # The model version is read from the data rather than stated, so it cannot describe a
    # different run than the one in the file.
    try:
        versions = query("""select distinct model_version, model_name
                            from srv_model_performance
                            where segment_type = 'overall' limit 20""")
        model_version = ", ".join(
            f"{r.model_name} {r.model_version}" for r in versions.itertuples()) or "none"
    except Exception:                                              # noqa: BLE001
        model_version = "unavailable"

    for label, value in (
        ("Generated (UTC)", generated.strftime("%Y-%m-%d %H:%M:%S")),
        ("Scope", describe_scope(season, week, season_type, conference, division)),
        ("Model version(s)", model_version),
        ("Source", "cfdb serving layer; every sheet is one serving view"),
    ):
        tab.cell(row, 1, label).font = header_font
        tab.cell(row, 2, value)
        row += 1

    row += 1
    # "Rows in scope" is its own COLUMN rather than a footnote, so a reader who sorts or
    # filters this block still has the pair side by side. A truncation recorded once in prose
    # at the bottom is a truncation that survives exactly until someone sorts the table.
    for index, label in enumerate(
            ("Sheet", "Serving view", "Rows written", "Rows in scope", "Note"), start=1):
        cell = tab.cell(row, index, label)
        cell.font, cell.fill = header_font, header_fill
    row += 1
    inventory_header = row - 1
    for entry in index_rows:
        tab.cell(row, 1, entry.name)
        tab.cell(row, 2, entry.view)
        tab.cell(row, 3, entry.rows).number_format = "#,##0"
        tab.cell(row, 4, entry.rows_in_scope).number_format = "#,##0"
        tab.cell(row, 5, entry.note)
        row += 1
    # R-182. The inventory is a DATASET — sheet, view, counts, note — so it is a Table and
    # the reader can sort and filter it. The metadata block above it is label/value pairs and
    # stays plain; making that a Table would claim it is data when it is a caption.
    if index_rows:
        index_table = ExcelTable(displayName=table_name("Index"),
                                 ref=f"A{inventory_header}:E{row - 1}")
        index_table.tableStyleInfo = TableStyleInfo(
            name="TableStyleLight1", showFirstColumn=False, showLastColumn=False,
            showRowStripes=False, showColumnStripes=False)
        tab.add_table(index_table)

    # R-196. The truncation line. A silently short workbook is the worst failure this file
    # can have, because nothing about it looks wrong — it is a plausible number of rows in a
    # correctly formatted sheet, and the reader has no way to know what is not there.
    cut = [e for e in index_rows if e.truncated]
    row += 1
    if cut:
        tab.cell(row, 1, "⚠ Truncated").font = header_font
        tab.cell(row, 2, f"The row cap is {ROW_CAP:,}. These sheets hit it:")
        row += 1
        for entry in cut:
            tab.cell(row, 1, entry.name)
            tab.cell(row, 2, f"{entry.rows:,} of {entry.rows_in_scope:,} rows written; "
                             f"{entry.rows_in_scope - entry.rows:,} not in this file. "
                             f"Narrow the filters on the Excel Export page to get all of them.")
            row += 1
    else:
        tab.cell(row, 1, "Complete").font = header_font
        tab.cell(row, 2, f"No sheet hit the {ROW_CAP:,}-row cap; every sheet holds every "
                         f"row in scope.")
        row += 1

    row += 1
    tab.cell(row, 1, "Not included in this workbook").font = header_font
    row += 1
    # AC-15.5's omissions (a view with no rows in this scope) and the sheets that are simply
    # not built yet are DIFFERENT ANSWERS to the same question, and a reader who wanted the
    # Odds sheet needs to know which one they got.
    for name, reason in omitted:
        tab.cell(row, 1, name)
        tab.cell(row, 2, reason)
        row += 1
    for sheet in PENDING_SHEETS:
        tab.cell(row, 1, sheet.name)
        tab.cell(row, 2, f"{sheet.view} — {PENDING_REASON}")
        row += 1
    if not omitted and not PENDING_SHEETS:
        tab.cell(row, 1, "Nothing — every sheet had rows in this scope.")
        row += 1

    # R-183. Whether the links are there at all, and the one thing that makes a working
    # link look broken: Cloudflare Access asks the reader to sign in.
    row += 1
    tab.cell(row, 1, "Links").font = header_font
    if site_host:
        tab.cell(row, 2, f"Team and matchup cells link back to {site_host}, carrying this "
                         f"workbook's scope. The site sits behind Cloudflare Access, so a "
                         f"link will ask you to sign in — that is not a broken link.")
    else:
        tab.cell(row, 2, "This workbook has no hyperlinks: the site's address "
                         "(CFDB_SITE_HOST) was not set where it was built. Links are "
                         "omitted rather than guessed, because a wrong link is worse than "
                         "no link.")
    row += 1

    # A blank cell means cfdb HOLDS NOTHING, not zero. Said once, because the alternative is
    # writing a dash into the cell, and a dash is text: it breaks COUNTBLANK, sorts ahead of
    # every number and cannot be filtered on "Blanks".
    row += 1
    tab.cell(row, 1, "Blank cells").font = header_font
    tab.cell(row, 2, "A blank cell means cfdb holds no value for it — not zero. The site "
                     "renders the same absence as a dash; a dash in a spreadsheet is text "
                     "and would break sorting and COUNTBLANK.")
    row += 2

    tab.cell(row, 1, "Scope is bounded by the filters on the Excel Export page. cfdb does "
                     "not offer a full-corpus or raw-layer export.").font = note_font

    for index, width in enumerate((26, 34, 14, 14, 60), start=1):
        tab.column_dimensions[get_column_letter(index)].width = width
