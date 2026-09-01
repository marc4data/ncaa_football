-- Every serving column carries a description.
--
-- AC-16.6, rewritten. The previous version asserted that every serving column APPEARS in
-- the dictionary, which the model reads out of information_schema and therefore satisfies
-- by construction — it tested nothing. The criterion worth having is the one that is
-- currently false.
--
-- RAISED TO ERROR. It was warn while the debt stood at 634 undocumented serving columns —
-- a test that fails hundreds of times on day one gets muted rather than paid down, so warn
-- kept the number countable and visible on every run instead. That threshold has now been
-- cleared: dbt/models/serving/_models.yml documents all 634, and the honest way to keep it
-- there is to make the next undocumented column fail the build rather than add one more
-- line to a warning nobody reads.
--
-- This checks the SERVING layer only. Staging and dimensional coverage are still partial
-- and are not in scope here; widening it is a separate decision with a separate backlog.
{{ config(severity='error') }}

select table_schema, table_name, column_name
from {{ ref('dim_field_metadata') }}
where layer = 'serving'
  and column_description is null
