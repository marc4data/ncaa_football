"""System Overview — page 18. Back of house; nothing here belongs on Today."""
import streamlit as st

from lib import chips, shell, states, table
from lib.query import query
from lib.table import Col

SEVERITY = {"ok": "y", "warn": "r", "error": "n", "unknown": "w"}


def body(page) -> None:
    with states.section("srv_system_health"):
        df = query("""
            select signal_type, subject, severity, detail, observed_at, as_of_ts
            from srv_system_health
            order by case severity when 'error' then 0 when 'warn' then 1
                                   when 'unknown' then 2 else 3 end, signal_type, subject
            limit 500
        """)
        table.as_of_caption(df)

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
