"""Scores — page 3. A stacked scoreboard at game x TEAM grain (R-267).

One row per team per game, six tabs over the export's colour bands, four frozen
columns and the rest scrolling horizontally. The query is the Excel sheet's own.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from lib import chips, filters, fmt, params, shell, states, table, workbook
from lib.query import query
from lib.table import Col

# How long after kickoff a game that is not yet final still counts as IN PROGRESS.
#
# A DELIBERATE COPY of src.scores_cadence.SETTLE_HOURS, which is the source of truth. The
# site image is built from ./site alone and cannot import src/, the same boundary that put a
# copy of the lines cadence config in lib/. Keeping the two numbers equal is what makes the
# page and the pipeline agree on what "still settling" means — the refresh gate collects
# results for exactly as long as this page claims a game is being played.
#
# The upper bound is the honesty guard, not a detail. `is_completed = false` on its own is
# true for a POSTPONED game forever, and for a game suspended on Thursday and resumed on
# Friday it is true across the whole intervening night. Claiming those are in progress is
# the false positive that is worse than the current silence, so a game that kicked off
# longer ago than this drops out of the claim rather than being asserted about.
SETTLE_HOURS = 8

# How far ahead a kickoff still counts as "coming up" for the not-started caption. A day,
# because the caption answers "is anything happening today", not "what is on this season".
UPCOMING_HOURS = 24


def _unsettled(scope, now=None) -> pd.DataFrame:
    """Games in scope that are not final, in the window either side of now.

    Not a join and not arithmetic — one serving view, a WHERE, and a projected boolean that
    says which side of now each kickoff falls on. The window bounds are computed here
    because they are clock values, not metrics.
    """
    now = now or datetime.now(timezone.utc)
    return query("""
        select game_id, start_date, (start_date <= :now) as has_kicked
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and (:division = 'all' or is_fbs_game)
          and not is_completed
          and start_date >= :window_start and start_date <= :window_end
        order by start_date
        limit 400
    """, {"season": scope.season, "week": scope.week,
          "season_type": scope.season_type, "division": scope.division,
          "now": now,
          "window_start": now - timedelta(hours=SETTLE_HOURS),
          "window_end": now + timedelta(hours=UPCOMING_HOURS)})


def _slate_caption(scope, now=None) -> None:
    """AC-3.4's second branch: the page says so, rather than being silently short a game.

    THREE SITUATIONS, NOT TWO. At 23:00 on the opening Thursday the table is empty because
    nothing has finaled yet, while twenty thousand people are watching a game — and "No
    completed games for 2026 Week 1 yet" is true, reads as broken, and is indistinguishable
    from a quiet Tuesday. "Nothing has finished yet" and "nothing is happening" are opposite
    claims and only one of them is reassuring.

      in progress now   -> games are being played; results appear as each one finals
      today, none yet   -> when the first kickoff is
      neither           -> nothing said here; the existing Empty state is already correct

    A game in progress cannot reach the table above it: `is_completed` comes straight from
    CFBD's `completed` field and is never derived from points, so a live game is absent
    rather than presented as final at whatever the score was when we asked. This caption is
    what turns that absence from a gap into a statement.
    """
    try:
        df = _unsettled(scope, now)
    except Exception:                                              # noqa: BLE001
        # A caption is not worth failing a page over. Silence is the current behaviour and
        # it is honest; a wrong claim about a live game is not.
        return
    if df.empty:
        return

    kicked = df[df["has_kicked"].fillna(False).astype(bool)]
    if not kicked.empty:
        st.caption(
            f"**{len(kicked)} game{'s' if len(kicked) != 1 else ''} in progress.** Results "
            f"appear here as each one finals — cfdb records a score only once CFBD reports "
            f"the game complete, so a game still being played is absent rather than shown "
            f"with a partial score.")
        return

    st.caption(
        f"**No games have kicked off yet.** First kickoff "
        f"{fmt.local_time(df['start_date'].min())}. Results appear here as each game "
        f"finals.")


# ==========================================================================================
# THE STACKED SCOREBOARD (R-267, R-268)
# ==========================================================================================
#
# Marc: "shift to Stacked/scoreboard format where Away and Home teams are presented on
# different lines."
#
# THE GRAIN ALREADY GIVES YOU THAT. srv_game_team is one row per team per game and the sort
# puts away above home, so the stacking is the data, not a layout. There is no pivot here and
# no pairing logic, and the moment anything on this page reshapes the frame that is the bug.
#
# ONE QUERY, SHARED WITH THE EXPORT. The sheet's SQL is imported rather than re-typed: same
# scope filters, same compound ORDER BY, same `game_no`. A page and a workbook that disagree
# about what "the Scores data" is would be the drift this project keeps paying for, and here
# they cannot — there is one statement.
SCORES_SHEET = next(s for s in workbook.SHEETS if s.name == "Scores")

# The four columns that stay put while the rest scrolls. Marc's choice, and it is a
# CONSTRUCTED set rather than a prefix — which is exactly what the site can do and Excel
# cannot, where the same decision had to become "everything up to Pts for" (R-265).
FROZEN = ("game_no", "game_date", "team", "points_for")

# Marc's six tabs, mapped onto the export's colour bands. These are TAB LABELS, not a rename
# of anything in the workbook — his ruling: "There's a single Excel sheet, Scores, with
# several different columns grouped by color, but on the same page. On the website, the data
# is split into tabs. Website presentation doesn't change the purpose of the workbook."
#
# SIX TABS, SEVEN BANDS, AND THAT IS DELIBERATE. Ancillary was split out of Game a day after
# the tabs were named and no tab was added, so its seven keys ride at the far right of Game
# Results — the same place they sit on the sheet, for the same reason. A seventh tab is one
# line here if he wants one.
#
# THE BLOCKS ARE THE SOURCE, not a copy of the field lists. A column added to a band reaches
# its tab with no second list to maintain.
TABS = (
    ("Game Results", ("Game", "Ancillary")),
    ("Against The Line", ("Market",)),
    ("Box Score", ("Box score",)),
    ("Stats", ("Team advanced",)),
    ("Offense", ("Offense",)),
    ("Defense", ("Defense",)),
)


def tab_fields(blocks) -> list:
    """The frozen four, then this tab's own columns in sheet order.

    The frozen four appear on every tab and are filtered out of the block half so they are
    not rendered twice — which is why the union test has to treat them separately.
    """
    own = [field for name, fields in workbook.SCORES_BLOCKS if name in blocks
           for field in fields if field not in FROZEN]
    return list(FROZEN) + own


def _rows(scope) -> pd.DataFrame:
    """The export's own statement, run for this scope."""
    return query(" ".join(SCORES_SHEET.sql.split()),
                 {"season": scope.season, "week": scope.week,
                  "season_type": scope.season_type, "conference": scope.conference,
                  "division": scope.division})


def _rendered(df: pd.DataFrame) -> pd.DataFrame:
    """Every column as the SHEET renders it — Yes/No, cover words, possession in minutes.

    Through `Sheet.value_for`, which is what the workbook writer calls. One renderer, two
    outputs: the page cannot disagree with the file about what a cell says.
    """
    if df.empty:
        return df
    out = pd.DataFrame(
        {field: [SCORES_SHEET.value_for(field, record) for _, record in df.iterrows()]
         for field in SCORES_SHEET.fields})
    # Carried through for the links and the banding; not displayed by any tab.
    for passenger in ("game_id", "team_slug", "rows_in_scope"):
        if passenger in df.columns:
            out[passenger] = df[passenger].values
    return out


def _kind(field: str, series) -> tuple:
    """(kind, dp) for a column, from the same rules the sheet formats with.

    Derived rather than listed: R-216's integer sets and R-259's per-sheet decimal default
    already decide this for the workbook, and a second table of column types on the page is
    a second answer waiting to disagree with the file.
    """
    if not pd.api.types.is_numeric_dtype(series):
        return "", None
    if workbook.is_plain_integer(field):
        return "num", 0
    if field in SCORES_SHEET.integer_fields:
        return "num", 0
    if field in SCORES_SHEET.site_precision:
        return "signed" if "spread" in field or "margin" in field else "num", 1
    return "num", SCORES_SHEET.decimals


def _columns(fields, frame, scope) -> list:
    """Col objects for one tab, labelled exactly as the sheet's headers are."""
    labels = dict(workbook.SCORES_COLUMNS)
    out = []
    for field in fields:
        kind, dp = _kind(field, frame[field]) if field in frame else ("", None)
        column = Col(field, labels.get(field, field), kind, dp=dp)
        if field == "team":
            column = Col(field, labels[field], kind, dp=dp,
                         link=lambda r: scope.link("team", team=r.get("team_slug")))
        out.append(column)
    return out


def _band(frame) -> callable:
    """Shade alternating RUNS of one game, in the order the rows are about to be drawn.

    R-257 REFUSED THIS IN EXCEL AND IT IS RIGHT HERE, which is worth stating because the two
    look like the same decision. In a workbook the reader re-sorts the table after we are
    gone, so a rule computed from position silently lies. On a page we render AFTER sorting:
    position is knowable, so the honest rule is the one Excel could not have.
    On the default sort this is exactly alternating games and the pair reads as a unit. Under
    any other sort it degrades to an ordinary zebra stripe, which is honest — whereas banding
    on `game_no` PARITY would put a tint on two unrelated rows whose numbers happened to share
    a parity, which is a claim that they belong together.
    """
    shade, previous, marks = False, object(), {}
    for position, value in enumerate(frame.get("game_no", pd.Series(dtype=object))):
        if value != previous:
            shade, previous = not shade, value
        marks[position] = shade
    order = {id_: i for i, id_ in enumerate(frame.index)}
    return lambda row: "cfdb-gameband" if marks.get(order.get(row.name)) else ""


def _pairs_only(frame, cap: int) -> int:
    """Round the cap DOWN so the last game on the page is not a team with no opponent.

    A cap that cuts between a game's two rows breaks the pairing silently — the reader sees
    a final row with no counterpart and no reason given, which looks like missing data.
    """
    if "game_no" not in frame or len(frame) <= cap or cap <= 0:
        return cap
    series = frame["game_no"]
    # A CAP THAT LANDS ON A BOUNDARY IS ALREADY CORRECT, and the first version trimmed anyway
    # — it always dropped the last game, so an even cap over whole games silently lost one.
    # The question is not "which game is last" but "does the cut fall INSIDE a game".
    if series.iloc[cap - 1] != series.iloc[cap]:
        return cap
    last = series.iloc[cap - 1]
    whole = int((series.head(cap) != last).sum())
    # `or cap`: if the very first game is longer than the whole cap, showing a partial game
    # beats showing nothing.
    return whole or cap


def _sorted_or_default(frame, columns):
    """The user's sort STACKED ON the default, never replacing it.

    The compound default — season, regular-before-postseason, week, date, game, away-then-home
    — is the query's own ORDER BY, so the default is "leave the frame alone" and there is no
    second ordering in Python to drift from the SQL. `apply_sort` uses a stable mergesort, so
    sorting the already-ordered frame by one column gives "Total yards descending, ties broken
    chronologically, away above home" for free.

    AND THE COST, SAID OUT LOUD: any user sort scatters the pairs. Sort by Off PPA and a
    game's two rows land hundreds of rows apart, which is the scoreboard format coming apart.
    That is correct — a sort is the reader rearranging what they were given — and `Game #`
    travelling on the row is what makes the pairing recoverable. It is also why the reset
    button exists.
    """
    return table.apply_sort(frame, columns)


def _reset_link() -> None:
    """Offered only when a non-default sort is active — a button that does nothing is the
    dead-link problem R-178 was about. Named for what it does rather than 'Reset'."""
    if not params.get("sort"):
        return
    href = params.link_here(sort=None, order=None)
    st.markdown(
        f"<a class='cfdb-resetsort' href='{href}' target='_self'>↺ Default sort</a>"
        f"<span class='cfdb-resetsort-note'>chronological, away above home</span>",
        unsafe_allow_html=True)


def body(page) -> None:
    scope = filters.game_scope()
    table.dataset_caption("Scores", SCORES_SHEET.view)
    chips.spread_sign_note()
    with states.section(SCORES_SHEET.view):
        raw = _rows(scope)
        table.as_of_caption(raw)
        _slate_caption(scope)
        frame = _rendered(raw)

        def show(df):
            _reset_link()
            labels = [label for label, _ in TABS]
            for tab, (label, blocks) in zip(st.tabs(labels), TABS):
                with tab:
                    fields = [f for f in tab_fields(blocks) if f in df.columns]
                    columns = _columns(fields, df, scope)
                    ordered = _sorted_or_default(df, columns)
                    cap = _pairs_only(ordered, 300)
                    table.render(
                        ordered, columns, caption="",
                        layout=table.column_layout(ordered, columns, unit="px"),
                        link_builder=lambda r: scope.link("matchup", game_id=r["game_id"]),
                        max_rows=cap, scroll=True, sticky=len(FROZEN),
                        row_class=_band(ordered))

        states.render_or_state(
            frame, SCORES_SHEET.view,
            "Completed results would be listed here.",
            f"No games for {scope.describe()} yet.",
            renderer=show, fix_label="Clear filters", fix=filters.clear)


def render() -> None:
    shell.render_page("scores", body)
