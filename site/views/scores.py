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
# Marc, 2026-09-05: "Reorder columns to Rank Before, Team, Record." The rank leads into the
# team it qualifies and the record follows, so the three read as one identity cluster — and
# all three are frozen, because splitting them would put the rank on screen and the record
# off it, which is the arrangement the reorder exists to end.
FROZEN = ("game_no", "game_date", "team_rank", "team", "record_before_display",
          "points_for", "won")

# Schedule's own winner marker, reused whole rather than redrawn. R-100's wording — "a
# relocation, not a new component" — and two pages marking a winner with two different
# characters is a worse outcome than either character. A GLYPH rather than a colour, so the
# result survives greyscale and a colour-blind reader (AC-G.22).
WIN_GLYPHS = {"Yes": "▸", "Tie": "="}

# WHICH POLL THE RANK IS. `fct_game` joins fct_poll_rank with `poll_name = 'AP Top 25'`, one
# poll on purpose — so the page has to say which, or a "#21" is a number with no authority
# behind it. Read from nowhere: this is a literal in the mart and a literal here, and the two
# would have to be kept in step by hand if the mart ever took a second poll.
RANK_POLL = "AP Top 25"

# R-279. IN THE FILE, NOT ON THE PAGE. Marc: "keep the other fields in the dataset, but don't
# present them in the web interface. They still belong in the Excel output."
#
# HIDING IS A RENDER-LIST DECISION, NEVER A SELECT DECISION — `game_id` drives the matchup
# link and `game_no` drives the banding, and both are hidden from some tabs while riding in
# every frame.
#
# Each one has to be redundant on THIS page rather than merely noisy, so each says why.
HIDDEN_ON_PAGE = {
    "game_id": "an opaque key; the row already links to the matchup",
    "season": "the filter bar says it",
    "season_type": "the filter bar says it",
    "week": "the filter bar says it",
    "opponent": "IT IS THE PAIRED ROW — the stacked format's whole premise",
    "is_home": "it is the away-above-home ORDER; the same premise said twice",
    "points_against": "the paired row's `Pts for`, one line away",
    # R-289. Written into the workbook as a value because a cell hyperlink is invisible to a
    # formula; on a page the anchor IS the link, so the URL as text is noise.
    "matchup_url": "export-only; the page has the link itself",
    # Marc, 2026-09-05: "I would suppress Postgame ELO in the web interface (keep in Excel)."
    # `Elo delta` is the number a reader wants from the pair, and it is beside the pregame
    # rating — so the postgame value is one subtraction away and costs a column to show.
    "postgame_elo": "the delta says what it did; the rating itself is in the file",
}

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
#
# (slug, label, blocks). THE SLUG IS WHAT GOES IN THE URL, and the URL is why these are
# anchors rather than `st.tabs` — see `_tab_bar`.
TABS = (
    ("results", "Game Results", ("Game", "Ancillary")),
    ("line", "Against The Line", ("Market",)),
    ("box", "Box Score", ("Box score",)),
    ("stats", "Stats", ("Team advanced",)),
    ("offense", "Offense", ("Offense",)),
    ("defense", "Defense", ("Defense",)),
)


def _active_tab() -> tuple:
    """The tab the URL asks for, or the first. An unknown slug falls back rather than
    raising — a hand-edited `?tab=` is noise, not a request (AC-G.11)."""
    wanted = params.get("tab")
    for entry in TABS:
        if entry[0] == wanted:
            return entry
    return TABS[0]


def _tab_bar(active: str) -> None:
    """R-283. THE TAB LIVES IN THE URL, WHICH IS WHY THESE ARE ANCHORS.

    Marc: "Clicking a sort while on Against The Line or Box Score resets the user to the Game
    Results tab." `st.tabs` keeps its selection client-side and never touches the URL, so
    every sort link rebuilt the page at the default tab. None of the eighteen sort anchors
    carried a tab parameter because there was no tab parameter to carry.

    Making the tab a URL parameter fixes it for EVERY control at once rather than one at a
    time: `params.link_here` preserves every known parameter, `tab` is already one, so the
    sort links and the reset link pick it up with no change to either. A helper that had to
    remember to add it is a helper someone forgets to use.

    It is also the same requirement `apply_sort` is server-side FOR — a sorted view has to
    survive a reload and be sendable to somebody. A tab in session state fails that for
    exactly the reason a client-side sorter would have.
    """
    links = []
    for slug, label, _blocks in TABS:
        css = "cfdb-tab" + (" cfdb-tab-on" if slug == active else "")
        href = params.link_here(tab=slug)
        links.append(f"<a class='{css}' href='{href}' target='_self'>{label}</a>")
    st.markdown(f"<div class='cfdb-tabbar'>{''.join(links)}</div>",
                unsafe_allow_html=True)


def tab_fields(blocks) -> list:
    """The frozen four, then this tab's own columns in sheet order.

    The frozen four appear on every tab and are filtered out of the block half so they are
    not rendered twice — which is why the union test has to treat them separately.
    """
    own = [field for name, fields in workbook.SCORES_BLOCKS if name in blocks
           for field in fields
           if field not in FROZEN and field not in HIDDEN_ON_PAGE]
    return list(FROZEN) + own


def _rows(scope) -> pd.DataFrame:
    """The export's own statement, run for this scope — with the one bound difference.

    R-278. `completed_only` is the only place the two surfaces legitimately diverge: the
    workbook is a data extract and carries `Completed` as a column, so it wants every row;
    this is a RESULTS page. A second query would be how Schedule and the export drifted in
    R-184, so it is a parameter on one statement.

    IT WAS INVISIBLE ON THE WEEK MARC WAS LOOKING AT. 2025 week 2 is entirely finished, so
    the page looked correct; the defect only shows on a live week, which is every week from
    here. The test uses a mixed scope for exactly that reason.
    """
    return query(" ".join(SCORES_SHEET.sql.split()),
                 {"season": scope.season, "week": scope.week,
                  "season_type": scope.season_type, "conference": scope.conference,
                  "division": scope.division, "completed_only": True})


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
    # CARRIED THROUGH FOR THE LINKS, THE LOGOS AND THE BANDING, and taken from the sheet's
    # own declared list rather than a second one here — which is how the logos went missing
    # after the slugs were fixed: the SELECT had them, this function did not name them, and
    # `team_cell` drew a monogram for every team without complaining.
    #
    # AND WITHOUT THE `in df.columns` GUARD THAT MADE THE ORIGINAL FAILURE SILENT. A missing
    # passenger is a broken page, not a cosmetic loss — R-287 is what four layers of
    # reasonable-looking silence produced. If the SELECT stops carrying one, say so here.
    passengers = ("game_id", "rows_in_scope") + workbook.SCORES_PASSENGERS
    missing = [name for name in passengers if name not in df.columns]
    if missing:
        raise KeyError(
            f"the Scores statement no longer selects {missing} — the page links and draws "
            f"with these, and a missing one renders as a monogram or a link to nowhere")
    for passenger in passengers:
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
    # R-280. THE WORKBOOK SPLITS THREE WAYS AND THIS SPLIT TWO, SO THE PAGE PRINTED "2,025".
    #
    # `is_plain_integer` documents itself as "a numeric label: no decimal point, no thousands
    # separator", and the format table's comment reads "a season is not '2,025' on any
    # sheet." The page rendered 2,025 and game ids as 401,752,817, because both branches
    # below returned the same ("num", 0) and `fmt.number` puts a separator on everything.
    #
    # AND THE DOCSTRING ABOVE READ AS SATISFIED WHILE THIS WAS TRUE. It says a second TABLE
    # of column types would be a second answer waiting to disagree — correct, and this was
    # not a second table, it was a second and COARSER SPLIT, which disagrees just as well.
    # "One renderer, two outputs" is true of `value_for` (Yes/No, cover words, possession
    # minutes) and was false of numbers, which take this path instead.
    if workbook.is_plain_integer(field):
        return "plain", 0          # a label that happens to be numeric: 2025, 401752817
    if field in SCORES_SHEET.integer_fields:
        return "num", 0            # a quantity you might total: 1,234
    if field in SCORES_SHEET.site_precision:
        return "signed" if "spread" in field or "margin" in field else "num", 1
    return "num", SCORES_SHEET.decimals


def _columns(fields, frame, scope) -> list:
    """Col objects for one tab, labelled exactly as the sheet's headers are."""
    labels = dict(workbook.SCORES_COLUMNS)
    out = []
    for field in fields:
        kind, dp = _kind(field, frame[field]) if field in frame else ("", None)
        if field == "won":
            # Nothing at all on a loss: the marker's job is to find the winner in a stack of
            # 166 rows, and a second glyph meaning "not this one" is 83 more things to read.
            out.append(Col(field, labels[field], "center",
                           render=lambda r: (
                               f"<span class='cfdb-winner' title='won'>"
                               f"{WIN_GLYPHS[r['won']]}</span>"
                               if r.get("won") in WIN_GLYPHS else "")))
            continue
        if field == "team_rank":
            # BLANK, NOT A DASH. Marc: "NULL (empty) for Rank if it doesn't exist." Most
            # teams are unranked, so a column of em dashes is a column of noise — and an
            # em dash reads as "we hold nothing", where the truth is "this team is not in
            # the poll", which is a fact rather than a gap.
            out.append(Col(field, labels[field], "plain", dp=0,
                           render=lambda r: ("" if pd.isna(r.get("team_rank"))
                                             or r.get("team_rank") is None
                                             else f"{int(r['team_rank'])}")))
            continue
        if field == "team":
            # R-284/R-287. LOGO, RANK AND A WORKING LINK, ALL FROM MACHINERY THAT EXISTS.
            #
            # `team_cell` draws logo-or-monogram plus a rank badge and already obeys AC-1.5 —
            # an unranked team gets NO badge, not an em dash in one. `team_link` returns None
            # where the slug is missing, which is the whole point: the page used to hand-build
            # `scope.link("team", team=r.get("team_slug"))`, the slug was never in the frame,
            # `params.link` drops a None parameter, and every one of 996 team anchors pointed
            # at `/team` with no team. Four layers each did something reasonable and the
            # result looked like a working link.
            #
            # `team_rank` is the rank carried ON THIS GAME — `case when is_home then
            # home_rank else away_rank` off fct_game — so it is genuinely "rank in the week",
            # not a season-end rank borrowed backwards.
            # NO RANK BADGE HERE ANY MORE — the reorder gave rank its own column, and a
            # badge beside it would be the same number twice on one row.
            out.append(Col(field, labels[field],
                           render=lambda r: table.team_cell(
                               r, "team_slug", "team", "team_logo_url"),
                           link=table.team_link("team_slug")))
            continue
        out.append(Col(field, labels.get(field, field), kind, dp=dp))
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
    # The poll behind the Rank column, said once. A "#21" with no poll named is a number
    # with no authority behind it, and cfdb joins exactly one poll on purpose.
    st.caption(f"**Rank** is the {RANK_POLL} position going into the game — blank where the "
               f"team was unranked. **Elo delta** is postgame minus pregame; the postgame "
               f"rating itself is in the Excel export.")
    with states.section(SCORES_SHEET.view):
        raw = _rows(scope)
        table.as_of_caption(raw)
        _slate_caption(scope)
        frame = _rendered(raw)

        def show(df):
            slug, _label, blocks = _active_tab()
            _tab_bar(slug)
            _reset_link()
            fields = [f for f in tab_fields(blocks) if f in df.columns]
            columns = _columns(fields, df, scope)
            # R-288. THE MATCHUP LINK WORKS AND WAS INVISIBLE. 26,228 anchors over 83 distinct
            # hrefs — one per game, all correct — with no cue but a pointer cursor, which a
            # touch device never shows. The old page carried this glyph column and the rewrite
            # dropped it.
            #
            # AT THE RIGHT-HAND EDGE OF THE FROZEN BLOCK, not appended to the scrolling
            # columns: on Offense that would put it 8,322px from the team name it belongs to.
            # Not at the far LEFT either — that is Marc's scoreboard identity, and he asked
            # for density, not width.
            columns.insert(len(FROZEN), table.details_col(
                lambda r: scope.link("matchup", game_id=r["game_id"])))
            ordered = _sorted_or_default(df, columns)
            cap = _pairs_only(ordered, 300)
            layout = table.column_layout(ordered, columns, unit="px",
                                         seed_from_label=False)
            table.render(
                ordered, columns, caption="", layout=layout,
                link_builder=lambda r: scope.link("matchup", game_id=r["game_id"]),
                max_rows=cap, scroll=True, sticky=len(FROZEN) + 1,
                row_class=_band(ordered),
                header_height=22 + 14 * table.header_lines(columns, layout))

        states.render_or_state(
            frame, SCORES_SHEET.view,
            "Completed results would be listed here.",
            f"No games for {scope.describe()} yet.",
            renderer=show, fix_label="Clear filters", fix=filters.clear)


def render() -> None:
    shell.render_page("scores", body)
