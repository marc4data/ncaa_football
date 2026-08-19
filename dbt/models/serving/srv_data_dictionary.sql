-- Data Dictionary page, and the Excel export: one row per modelled column.
--
-- The only serving model with a single upstream source, deliberately — the same object
-- feeds the page and the download, so the two cannot disagree about what a column means.
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
    is_documented
from {{ ref('dim_field_metadata') }}
