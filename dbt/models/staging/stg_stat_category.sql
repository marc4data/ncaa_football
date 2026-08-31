-- The controlled vocabulary of box-score stat categories. One row per category name.
--
-- /stats/categories returns a BARE ARRAY OF STRINGS — no wrapping object, no keys. It is the
-- only endpoint shaped that way, which is why it needs json_scalar_text: after exploding,
-- Postgres holds a jsonb scalar and reading it with ::text would keep JSON's quotes and give
-- `"passing"` rather than passing.
--
-- Small, and worth having: stg_game_team_stat lands ~35 category/stat pairs per team as
-- strings, and this is the authoritative list of what those category names can be. Without
-- it, validating that model's categories means hardcoding a list that goes stale the moment
-- CFBD adds one.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (order by filename desc) as recency
    from {{ source('raw', 'raw_stats_categories') }}
    where status_code = 200

),

exploded as (

    -- No params to partition on: the endpoint takes none. Newest fetch wins outright.
    select {{ json_array_elements('payload') }} as category
    from successful_fetches
    where recency = 1

)

select distinct
    {{ json_scalar_text('category') }} as stat_category
from exploded
