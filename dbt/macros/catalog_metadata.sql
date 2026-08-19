{#
  Reading the warehouse's own column catalogue, which is where the two engines diverge most.

  The data dictionary is generated from descriptions written once in schema.yml and pushed
  into the database by `persist_docs`. That makes the database the single source of truth at
  read time and keeps the authoring in dbt — no second document to maintain, and no drift
  between what the docs say and what the tables are.

  Postgres and Databricks expose those comments completely differently:

    Postgres    information_schema.columns has no comment column at all. Comments live in
                pg_catalog.pg_description, addressed by table OID and column ordinal, and
                have to be joined back through pg_class and pg_namespace.
    Databricks  Unity Catalog's information_schema.columns carries `comment` directly.

  This is exactly the case the dispatch pattern exists for: same question, no shared SQL.
#}

{% macro column_catalog(schemas) -%}
    {{ return(adapter.dispatch('column_catalog', 'cfdb_dbt')(schemas)) }}
{%- endmacro %}


{% macro default__column_catalog(schemas) -%}
    select
        c.table_schema                                   as table_schema,
        c.table_name                                     as table_name,
        c.column_name                                    as column_name,
        c.ordinal_position                               as ordinal_position,
        c.data_type                                      as data_type,
        c.is_nullable                                    as is_nullable,
        d.description                                    as column_description,
        td.description                                   as table_description
    from information_schema.columns c
    join pg_catalog.pg_class cls
        on cls.relname = c.table_name
    join pg_catalog.pg_namespace ns
        on ns.oid = cls.relnamespace and ns.nspname = c.table_schema
    left join pg_catalog.pg_description d
        on d.objoid = cls.oid and d.objsubid = c.ordinal_position
    left join pg_catalog.pg_description td
        on td.objoid = cls.oid and td.objsubid = 0
    where c.table_schema in ({{ schemas }})
{%- endmacro %}


{% macro databricks__column_catalog(schemas) -%}
    select
        c.table_schema                                   as table_schema,
        c.table_name                                     as table_name,
        c.column_name                                    as column_name,
        c.ordinal_position                               as ordinal_position,
        c.full_data_type                                 as data_type,
        c.is_nullable                                    as is_nullable,
        c.comment                                        as column_description,
        t.comment                                        as table_description
    from information_schema.columns c
    left join information_schema.tables t
        on t.table_schema = c.table_schema and t.table_name = c.table_name
    where c.table_schema in ({{ schemas }})
{%- endmacro %}
