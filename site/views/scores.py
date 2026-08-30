"""Scores — page 3. Completed results with the model's call alongside the outcome."""
import pandas as pd
import streamlit as st

from lib import chips, filters, fmt, shell, states, table
from lib.query import query
from lib.table import Col


def _rows(season, week, season_type, conference, division='fbs') -> pd.DataFrame:
    return query("""
        select game_id, season, week, game_date, start_date_et,
               home_team_slug, home_team_display, home_logo_url, home_points, home_rank,
               away_team_slug, away_team_display, away_logo_url, away_points, away_rank,
               winner, actual_margin, excitement_index, is_upset, attendance, venue_display,
               total_points, total_yards_both_teams, teams_with_box_score,
               spread_at_close, spread_at_close_provider, spread_at_close_basis,
               favorite_covered, is_completed, as_of_ts
        from srv_scoreboard
        where season = :season and season_type = :season_type and is_completed
          and (:week is null or week = :week)
          -- FBS spine: EITHER team FBS, defaulted rather than hardcoded, so
          -- 'All divisions' in the filter bar genuinely widens it.
          and (:division = 'all' or is_fbs_game)
        order by game_date desc, start_date_et desc
        limit 400
    """, {"season": season, "week": week, "season_type": season_type,
          "division": division})


def _winner(row) -> str:
    """AC-3.1. The winner is READ, not derived.

    This used to pick the winner by the sign of actual_margin and index into the display
    columns. Two problems, both found by rehearsing the post-game path against real 2025
    games rather than 2026 fixtures where every score is null:

      1. It is the app owning a definition dbt already owns. srv_scoreboard computes
         `winner` from the points, and a second derivation is a second answer waiting to
         disagree — which it did, on one game in 295.
      2. It indexed into a column that can be NULL and rendered `<strong>None</strong>`.
         The display name is fixed at the view now, but a formatter that assumes a value is
         present is the thing that broke, and reading the view's own answer removes the
         assumption rather than guarding it.

    The sign convention is still asserted — in dbt, against the data, where it belongs.
    """
    if not row.get("is_completed"):
        return chips.chip_html("w", "Pending", "this game has not been played")
    winner = row.get("winner")
    if winner is None or (isinstance(winner, float) and pd.isna(winner)):
        # The view returns NULL for a completed game with equal scores. A tie is a settled
        # result and must not render as Pending.
        return chips.chip_html("w", "Tie", "a settled result, not an unplayed game")
    return f"<strong>{winner}</strong>"


UPSET_LEGEND = ("Upset scale — **!** under 10 points · **!!** 10 to 20 · **!!!** 21 or "
                "more. Degree is the winning margin, which is the cheapest honest proxy "
                "for how surprising a result was.")


def _favorite_covered(row) -> str:
    """R-008. Four states, and none of them is another one.

    `pending` is not `push` — AC-G.20 — and a pick'em has no favourite at all, which is the
    not-applicable third state of AC-G.32 rather than a missing value. All four come from
    the view; nothing here decides which side was favoured.
    """
    value = row.get("favorite_covered")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fmt.EM_DASH
    return {
        "yes":         chips.chip_html("y", "Covered", "the market favourite covered"),
        "no":          chips.chip_html("n", "No", "the favourite did not cover"),
        "push":        chips.chip_html("w", "Push",
                                       "landed exactly on the number, a settled result"),
        "pending":     chips.chip_html("w", "Pending", "not played yet"),
        "no_favorite": chips.chip_html("w", "Pick-em",
                                       "the spread was zero, so there was no favourite"),
    }.get(str(value), fmt.EM_DASH)


def _side(row, side: str) -> str:
    """A team cell, with a caret if this side won.

    The caret is a GLYPH, not a colour, so the result survives greyscale and a colour-blind
    reader (AC-G.22). It is absent rather than dimmed on the losing side: two markers where
    one is meaningful is the monogram problem again.
    """
    cell = table.team_cell(row, f"{side}_team_slug", f"{side}_team_display",
                           f"{side}_logo_url", f"{side}_rank")
    winner = row.get("winner")
    if winner and winner == row.get(f"{side}_team_display"):
        return f"<span class='cfdb-winner' title='won'>▸</span>{cell}"
    return f"<span class='cfdb-winner-spacer'></span>{cell}"


def _upset(row) -> str:
    """Upset by DEGREE, in the width of one character.

    An upset where the loser was ranked and the winner was not is a bigger story than a
    one-score result between neighbours, and the margin is the cheapest proxy for that.
    A single glyph column also stops a boolean eating the width of a word.
    """
    if not row.get("is_upset"):
        return ""
    margin = row.get("actual_margin")
    if margin is None or pd.isna(margin):
        return "!"
    size = abs(float(margin))
    return "!!!" if size >= 21 else ("!!" if size >= 10 else "!")


def body(page) -> None:
    scope = filters.game_scope()
    table.dataset_caption("Scores", "srv_scoreboard")
    chips.spread_sign_note()
    with states.section("srv_scoreboard"):
        df = _rows(scope.season, scope.week, scope.season_type, scope.conference,
                   scope.division)
        table.as_of_caption(df)
        columns = [
            # F2-23: a caret beside the team that won, so the result is readable without
            # comparing two numbers. The winner comes from the view, not from a comparison
            # here — the page re-deriving it is what disagreed on 1 game in 295.
            Col("away", "Away", render=lambda r: _side(r, "away"),
                link=lambda r: scope.link("team", team=r.get("away_team_slug"))),
            Col("away_points", "", "num", dp=0),
            Col("home", "Home", render=lambda r: _side(r, "home"),
                link=lambda r: scope.link("team", team=r.get("home_team_slug"))),
            Col("home_points", "", "num", dp=0),
            Col("winner", "Winner", render=_winner),
            # away minus home, stated so the sign is never guessed at.
            # Integers. A football margin has no decimal, and "−7.0" reads as
            # a measurement rather than a score difference.
            Col("actual_margin", "Margin", "signed", dp=0),
            # AC-3.6: a column, never an app-side rank comparison.
            # "!" by degree rather than a fixed-width chip. The chip was costing more
            # horizontal space than the information justified on a table this wide.
            # The GLYPHS are !/!!/!!!; the HEADER is a word. A column headed with a
            # punctuation mark is a puzzle rather than a label.
            Col("is_upset", "Upset", render=_upset),
            # R-005 / R-006 / R-007 / R-008.
            Col("total_points", "Pts", "num", dp=0),
            Col("total_yards_both_teams", "Yards", "num", dp=0),
            Col("spread_at_close", "Close", "signed"),
            Col("favorite_covered", "Fav cover", render=_favorite_covered),
            Col("excitement_index", "Excitement", "num", dp=1),
            Col("attendance", "Attendance", "num", dp=0),
            table.details_col(lambda r: scope.link("matchup",
                                                   game_id=r["game_id"])),
        ]
        # AC-2.8: sorted before grouping, so each day sorts within itself and the days
        # keep their own order.
        df = table.apply_sort(df, columns)
        states.render_or_state(
            df, "srv_scoreboard",
            "Completed results would be listed here.",
            f"No completed games for {scope.describe()} yet.",
            renderer=lambda d: _grouped(d, columns, scope),
            fix_label="Clear filters", fix=filters.clear)
        # F2-24: a glyph nobody can decode is decoration. The thresholds are stated on the
        # page, not left to a tooltip that a touch device never shows.
        if not df.empty:
            st.caption(UPSET_LEGEND)
            _provenance(df)


def _provenance(df) -> None:
    """Where the closing line came from, and how complete the yardage is.

    An unattributed line is a number with no provenance. And the two bases are genuinely
    different claims: a snapshot cfdb took before kickoff is an observation, while CFBD's
    recorded spread is a number we were told about afterwards. Our snapshot history starts
    2026-08-15, so almost every historical game carries the second kind.
    """
    bases = set(df["spread_at_close_basis"].dropna().unique())
    books = sorted(set(df["spread_at_close_provider"].dropna().unique()))
    if bases:
        parts = []
        if "observed_before_kickoff" in bases:
            parts.append("a snapshot cfdb took before kickoff")
        if "as_recorded_by_cfbd" in bases:
            parts.append("the line CFBD recorded for the game")
        st.caption(
            f"**Close** is {' or '.join(parts)}"
            + (f", from {', '.join(books)}. " if books else ". ")
            + "cfdb began sampling lines on 15 August 2026, so earlier games carry CFBD's "
              "recorded number rather than an observation.")
    missing = df[df["teams_with_box_score"].fillna(0) == 0]
    if not missing.empty:
        st.caption(
            f"**Yards** is blank for {len(missing):,} of {len(df):,} games shown — CFBD "
            f"publishes box scores from 2024 onward, and not for every game.")


def _grouped(df, columns, scope) -> None:
    """AC-3.5: grouped by day, most recent first."""
    # F2-06: one layout over the whole frame, reused by every group.
    layout = table.column_layout(df, columns)
    for day, rows in df.groupby(df["game_date"], sort=False):
        st.markdown(f"<div class='cfdb-daygroup'>{pd.Timestamp(day):%A %d %B %Y}</div>",
                    unsafe_allow_html=True)
        table.render(rows, columns, caption="", layout=layout,
                     link_builder=lambda r: scope.link("matchup", game_id=r["game_id"]))


def render() -> None:
    shell.render_page("scores", body)
