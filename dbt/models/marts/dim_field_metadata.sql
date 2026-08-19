-- One row per modelled column: the data dictionary, generated rather than maintained.
--
-- Descriptions are written once in schema.yml, pushed into the database as native comments
-- by `persist_docs`, and read back here. That ordering matters — it means the dictionary
-- cannot drift from the models, because there is no second place to update. A hand-kept
-- dictionary is wrong the first time anyone renames a column and does not tell anyone.
--
-- Why the field descriptions are ours to write: CFBD's OpenAPI spec (v5.24.0) fully
-- describes 74 endpoints and 289 parameters, but only 4 of its 1,017 FIELDS carry any
-- prose. The vendor documents the interface, not the meaning, so the meaning is authored
-- here or it does not exist.
--
-- Scope is the three modelled schemas. `raw` is deliberately excluded: it holds landed API
-- responses whose shape is CFBD's, not ours, and documenting a payload we do not control
-- would be documenting someone else's contract.
-- Materialized as a VIEW on purpose, and this is the whole design of the model.
--
-- It reads the warehouse catalogue rather than any dbt model, so it declares no `ref` and
-- dbt is free to build it whenever — in practice first. As a table that is a real defect:
-- measured, built in DAG order it reported 1.6% documented, and rebuilt immediately
-- afterwards against the same database, 41.6%. It had catalogued the *previous* run's
-- comments. A dictionary that is silently one run stale is worse than none, because it
-- reads as authoritative.
--
-- Generating `-- depends_on:` edges from `graph.nodes` looks like the fix and cannot work:
-- dbt collects ref edges during parsing, `graph` is only populated at execution, and an
-- execute-guard means the refs are never registered at all. (That guard is not written out
-- here even in a comment: Jinja is rendered before the SQL is, so a tag inside a `--` line
-- is still a live tag, and this file failed to compile until it was reworded.)
--
-- A view sidesteps the ordering question entirely — it is evaluated when queried, so it is
-- current by construction and cannot be stale. Any downstream *table* built from it still
-- has to run after the models it documents; that constraint now lives in one place instead
-- of being a property of this model's position in the DAG.
{{ config(materialized='view', tags=['dictionary']) }}

with catalog as (
    {{ column_catalog("'staging', 'marts', 'serving'") }}
)
select
    {{ surrogate_key(['table_schema', 'table_name', 'column_name']) }} as field_sk,
    table_schema,
    table_name,
    column_name,
    ordinal_position,
    data_type,
    case when is_nullable = 'YES' then true else false end as is_nullable,
    table_description,
    column_description,
    -- The layer is inferable from the schema, and the page groups by it so a reader can
    -- see the shape of the model rather than an alphabetical wall of columns.
    case table_schema
        when 'staging' then 'staging'
        when 'marts'   then 'dimensional'
        when 'serving' then 'serving'
    end as layer,
    column_description is not null as is_documented
from catalog
