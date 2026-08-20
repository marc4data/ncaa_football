"""Data Dictionary — page 17. Every modelled column, and whether anyone has explained it.

The page renders UNDOCUMENTED as a value rather than a blank (AC-16.2), and that is the
whole point of it. A dictionary that lists 1,130 columns and silently shows nothing in the
description cell for 838 of them reads as a finished reference with some gaps in rendering.
Showing the gap as a state makes the debt countable, and a countable debt is one somebody
eventually pays.

The descriptions themselves are written once in dbt's schema.yml, pushed into Postgres as
native column comments by `persist_docs`, and read back out of the catalogue. There is no
second document, so this page cannot disagree with the models.
"""
import pandas as pd
import streamlit as st

from lib import chips, params, shell, states, table
from lib.query import query
from lib.table import Col

LAYERS = ["All layers", "staging", "dimensional", "serving"]


@st.cache_data(ttl=3600)
def _tables(layer) -> list:
    return query("""select distinct table_name from srv_data_dictionary
                    where (:layer is null or layer = :layer)
                    order by table_name limit 400""",
                 {"layer": layer})["table_name"].tolist()


def body(page) -> None:
    with states.section("srv_data_dictionary"):
        chosen_layer = params.get("tab")
        with st.sidebar:
            layer_label = st.selectbox(
                "Layer", LAYERS,
                index=LAYERS.index(chosen_layer) if chosen_layer in LAYERS else 0)
            layer = None if layer_label == "All layers" else layer_label
            tables = ["All tables"] + _tables(layer)
            table_choice = st.selectbox("Table", tables)
            undocumented_only = st.toggle(
                "Undocumented only", value=False,
                help="The columns still waiting for a description.")
        search = st.text_input("Search columns and descriptions", "",
                               placeholder="e.g. spread, margin, devig")

        params.set_params(tab=layer_label if layer else None)
        table_name = None if table_choice == "All tables" else table_choice

        df = query("""
            select layer, table_schema, table_name, column_name, ordinal_position,
                   data_type, is_nullable, table_description, column_description,
                   is_documented, description_status, as_of_ts
            from srv_data_dictionary
            where (:layer is null or layer = :layer)
              and (:table_name is null or table_name = :table_name)
              and (:undocumented is false or is_documented is false)
              and (:search = ''
                   or lower(column_name) like :pattern
                   or lower(coalesce(column_description, '')) like :pattern)
            order by layer, table_name, ordinal_position
            limit 2000
        """, {"layer": layer, "table_name": table_name,
              "undocumented": undocumented_only,
              "search": search.strip().lower(),
              "pattern": f"%{search.strip().lower()}%"})
        table.as_of_caption(df)

        _coverage()

        states.render_or_state(
            df, "srv_data_dictionary",
            "The field definitions would be listed here.",
            "No column matches the current filters."
            + (f" Nothing contains “{search.strip()}”." if search.strip() else ""),
            renderer=_dictionary,
            fix_label="Clear the search" if search.strip() else None,
            fix=lambda: st.rerun())


def _coverage() -> None:
    """How much of the model is explained, stated up front rather than discovered.

    Counted in SQL over the one view, and rendered exactly as returned. An earlier version
    pivoted and summed the counts in pandas to show "53 of 204", which is a denominator the
    app invented — and inventing denominators is how two places on a site end up disagreeing
    about the same percentage.
    """
    counts = query("""
        select layer, description_status, count(*) as columns
        from srv_data_dictionary
        group by layer, description_status
        order by layer, description_status
        limit 40
    """)
    if counts.empty:
        return
    parts = [f"**{row.layer}** {int(row.columns):,} {row.description_status.lower()}"
             for row in counts.itertuples()]
    st.caption("Column descriptions — " + " · ".join(parts)
               + ". The serving layer is documented last on purpose: its columns are "
                 "renamed projections of mart columns, and describing them before the "
                 "marts settle would mean writing the same sentence twice.")


def _status(row) -> str:
    """AC-16.2: UNDOCUMENTED is a rendered value, not an empty cell."""
    if str(row.get("description_status")) == "authored":
        return chips.chip_html("y", "Authored", "a description was written for this column")
    return chips.chip_html("r", "Undocumented",
                           "no description has been written for this column yet")


def _description(row) -> str:
    value = row.get("column_description")
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return ("<span style='opacity:.6'>No description written yet.</span>")
    return str(value)


def _dictionary(df: pd.DataFrame) -> None:
    for (layer, table_name), rows in df.groupby(["layer", "table_name"], sort=False):
        description = rows["table_description"].dropna()
        st.markdown(f"<div class='cfdb-daygroup'>{table_name} "
                    f"<span style='opacity:.6;font-weight:400'>· {layer}</span></div>",
                    unsafe_allow_html=True)
        if not description.empty:
            st.caption(str(description.iloc[0]))
        table.render(rows, [
            Col("column_name", "Column"),
            Col("data_type", "Type"),
            Col("is_nullable", "Nullable", "bool"),
            Col("status", "Status", render=_status),
            Col("description", "Description", render=_description),
        ], caption=f"srv_data_dictionary · {table_name}", max_rows=200)


def render() -> None:
    shell.render_page("dictionary", body)
