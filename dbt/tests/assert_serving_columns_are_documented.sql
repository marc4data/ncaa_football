-- Every serving column carries a description.
--
-- AC-16.6, rewritten. The previous version asserted that every serving column APPEARS in
-- the dictionary, which the model reads out of information_schema and therefore satisfies
-- by construction — it tested nothing. The criterion worth having is the one that is
-- currently false.
--
-- Severity is warn, deliberately. This fails ~665 times today at 30.5% coverage, and a test
-- that fails hundreds of times on day one gets muted rather than paid down. Warn makes the
-- documentation debt countable and visible on every run; raise it to error once coverage
-- clears a threshold worth defending.
{{ config(severity='warn') }}

select table_schema, table_name, column_name
from {{ ref('dim_field_metadata') }}
where layer = 'serving'
  and column_description is null
