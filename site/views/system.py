"""System Overview — page 18. Back of house; nothing here belongs on Today."""
import pandas as pd
import streamlit as st

from lib import chips, fmt, shell, states, table
from lib.query import query
from lib.table import Col

SEVERITY = {"ok": "y", "warn": "r", "error": "n", "unknown": "w"}

# 🚨 A291 (cfdb-main-R-5043). HOW OLD A VERDICT MAY BE BEFORE THE READER IS TOLD NOT TO
# TRUST IT. Six hours, and the number is derived rather than chosen: the shortest budget on
# this board is `scores_refresh` at FIVE HOURS, so a verdict older than that can already be
# wrong about the fastest signal it reports on.
#
# ⚠️ THIS IS THE ONLY THRESHOLD IN THIS FEATURE AND IT LIVES HERE ON PURPOSE (R-574). It is
# a RENDER-TIME judgement — `srv_system_health` is a table, so `current_timestamp` minus the
# build clock is zero on every build and a SQL branch could never fire (R-760). Putting the
# number in a dbt var as well would be one threshold in two languages, which is the drift
# R-574 forbids. `dbt/macros/health_verdict.sql` owns the stamp; this owns the judgement.
VERDICT_STALE_HOURS = 6


def _verdict_note(df, now=None):
    """Whether the board's verdict is too old to read as current, and what to say.

    Returns `(is_stale, message)`. Separated from `body()` with an injectable clock so the
    stale branch can be PROVEN to fire (R-760/R-843) — a banner nobody has seen is a claim.
    """
    if df is None or df.empty or "verdict_computed_at" not in df.columns:
        # The column is published by this round's model change. A reader on an older
        # published tree gets silence rather than a wrong reassurance (AC-G.11: an absence
        # must not read as an all-clear).
        return False, ""
    computed = df["verdict_computed_at"].max()
    if pd.isna(computed):
        return False, ""
    stamp = pd.Timestamp(computed)
    reference = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz=stamp.tz)
    hours = (reference - stamp).total_seconds() / 3600.0
    age = fmt.relative_age(stamp, reference)
    if hours <= VERDICT_STALE_HOURS:
        return False, f"Verdict computed {age}."
    return True, (
        f"This board's verdict was computed {age} and every severity on it is a snapshot "
        f"from that moment, not a live reading. `srv_system_health` is rebuilt by the "
        f"weekly cadence, so a row about a five-hour cadence can be days out of date — "
        f"read the Observed column, which is an absolute time, rather than any 'hours ago' "
        f"in Detail.")


def body(page) -> None:
    with states.section("srv_system_health"):
        df = query("""
            select signal_type, subject, severity, detail, observed_at,
                   verdict_computed_at, as_of_ts
            from srv_system_health
            order by case severity when 'error' then 0 when 'warn' then 1
                                   when 'unknown' then 2 else 3 end, signal_type, subject
            limit 500
        """)
        table.as_of_caption(df)

        # 🚨 A291: the board says its own age BEFORE it says anything about the pipeline.
        # On 2026-11-02 it published `scores_refresh · error · "PUBLISH HAS STOPPED - last
        # completed 24 hours ago"` from a build 28 hours earlier; the cadence had beaten 42
        # minutes before. The verdict was not wrong about the past — it was silent about
        # being a snapshot, which is R-3766 and R-3782's family for a third time.
        stale, note = _verdict_note(df)
        if note:
            (st.warning if stale else st.caption)(note)

        if df.empty:
            # AC-18.8: zero rows is "no results recorded", never "all clear". A green board
            # must mean every check passed, not that no checks ran.
            states.empty("Pipeline health would be here.",
                         "No results recorded — this is NOT the same as all checks passing.")
            return

        counts = df["severity"].value_counts().to_dict()
        cols = st.columns(4)
        for i, key in enumerate(("error", "warn", "unknown", "ok")):
            cols[i].metric(key.title(), counts.get(key, 0))

        for signal, rows in df.groupby("signal_type", sort=True):
            st.markdown(f"<div class='cfdb-daygroup'>{signal.replace('_', ' ').title()}</div>",
                        unsafe_allow_html=True)
            table.render(rows, [
                Col("subject", "Subject"),
                Col("severity", "Status", render=lambda r: chips.chip_html(
                    SEVERITY.get(r["severity"], "w"), r["severity"].title())),
                Col("detail", "Detail"),
                Col("observed_at", "Observed", "datetime"),
            ], caption="srv_system_health")

        # AC-18.5 is a prohibition on the other direction; this note is here so a reader
        # knows the omission is deliberate rather than an oversight.
        st.caption("Airflow run history is not captured — `fct_pipeline_run` does not "
                   "exist, so no pipeline-run section is shown rather than an empty table "
                   "implying no runs happened (AC-18.7).")


def render() -> None:
    shell.render_page("system", body)
