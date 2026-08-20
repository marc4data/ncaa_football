"""Excel Export — page 15. The take-away artifact.

The page is deliberately thin: pick a scope, see exactly what the workbook will and will
not contain, download it. The build itself lives in `lib/workbook.py`.

What the page has to get right is the honesty of the preview. A download is the one action
on this site whose result the user cannot see before committing to it, so the omissions are
shown BEFORE the button rather than discovered on the index sheet afterwards.
"""
from datetime import datetime, timezone

import streamlit as st

from lib import filters, shell, states, workbook


def body(page) -> None:
    scope = filters.game_scope()

    st.markdown(
        "A workbook of the games currently in scope — schedule, results, the odds board, "
        "model edges, standings, model provenance and the field definitions. Everything is "
        "read from the serving layer, formatted as real Excel: typed numbers, freeze panes, "
        "autofilter and conditional formatting on the columns worth scanning.")

    # The scope rule, stated where someone would otherwise go looking for the control that
    # does not exist. Saying why is better than leaving an apparent omission.
    st.caption(
        "Exports are bounded by the filters in the sidebar. There is no whole-database or "
        "raw-data download: CFBD's terms prohibit redistributing their data as data, and a "
        "workbook travels further than a page does.")

    with states.section("srv_schedule"):
        planned, missing = _preview(scope)

    if not planned:
        states.empty(
            "A workbook would be built here.",
            f"No sheet has any rows for {scope.describe()}, so there is nothing to export.",
            fix_label="Clear filters", fix=filters.clear)
        return

    st.subheader("What this workbook will contain")
    for name, view, count in planned:
        st.markdown(f"- **{name}** — {count:,} row(s) from `{view}`")
    if missing:
        st.subheader("What it will not contain")
        for name, reason in missing:
            st.markdown(f"- **{name}** — {reason}")
        st.caption(
            "Omitted rather than shipped as an empty tab (AC-15.5). The same list is "
            "written onto the workbook's index sheet, so the file explains itself if it is "
            "opened somewhere else.")

    if st.button("Build the workbook", type="primary"):
        started = datetime.now(timezone.utc)
        with st.spinner("Building…"):
            payload, index_rows, omitted = workbook.build(
                scope.season, scope.week, scope.season_type, scope.conference)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        name = workbook.filename(scope.season, scope.week, started)
        st.download_button(
            f"Download {name}", data=payload, file_name=name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        # AC-15.11 is a criterion with a number in it, so the number is shown rather than
        # asserted in a document nobody opens next to the running site.
        st.caption(
            f"{len(index_rows)} sheet(s), "
            f"{sum(count for _, _, count, _ in index_rows):,} rows, built in "
            f"{elapsed:.1f}s.")


def _preview(scope) -> tuple:
    """Row counts per sheet, run as the real queries rather than estimated.

    Counting with the actual query is the only preview that cannot be wrong: an estimate
    that disagrees with the file is worse than no preview, because the user stops checking.
    It costs one extra pass, and the whole build is bounded at ten seconds.
    """
    planned, missing = [], []
    for sheet in workbook.SHEETS:
        # Shares the builder's reader, so the preview and the file cannot disagree about
        # what is in scope — including about why something is not. A second implementation
        # of "is this sheet available" is a second answer waiting to diverge.
        df, reason = workbook.read_sheet(
            sheet, scope.season, scope.week, scope.season_type, scope.conference)
        if df is None:
            missing.append((sheet.name, reason))
        else:
            planned.append((sheet.name, sheet.view, len(df)))
    return planned, missing


def render() -> None:
    shell.render_page("export", body)
