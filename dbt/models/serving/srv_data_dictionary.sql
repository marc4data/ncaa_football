-- Data Dictionary page, and the Excel export: one row per modelled column.
--
-- The only serving model with a single upstream source, deliberately — the same object
-- feeds the page and the download, so the two cannot disagree about what a column means.
--
-- MUST BE BUILT LAST, and dbt cannot know that.
--
-- It catalogues the serving layer but declares no ref on any of it, so the scheduler is
-- free to build it first — and did. Measured: after widening seven views, Postgres reported
-- 1,108 dictionary rows and Databricks 1,031, and 31 of that 77-row gap was precisely the
-- columns just added. The dictionary had catalogued the layer as it stood before the run.
--
-- dim_field_metadata solved this by being a view, which is current whenever queried. This
-- model cannot: serving objects are tables because pg_dump ships rows, not definitions. So
-- the constraint moves here, and the fix is operational — build it in a second pass.
--
-- Built as a table like every serving model (pg_dump ships rows, not view definitions), and
-- because it reads a catalogue view it must be built AFTER the models it documents. That is
-- the one ordering constraint dim_field_metadata's view materialization pushed here rather
-- than removing; the production DAG builds serving last, so it holds.
select
    field_sk,
    layer,
    table_schema,
    table_name,
    column_name,
    ordinal_position,
    data_type,
    is_nullable,
    table_description,
    column_description,
    is_documented,
    description_status,
    ao_src.as_of_ts
from {{ ref('dim_field_metadata') }}
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'ops') ao_src
