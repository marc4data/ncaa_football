{{ config(materialized='table', tags=['reference']) }}
-- One row per data domain: when the data behind it was last successfully loaded.
--
-- AC-G.35 requires every page to carry an "as of" timestamp sourced from a freshness column
-- in its own serving view, explicitly NOT from now() in the app. A single global timestamp
-- would satisfy the letter of that and defeat its purpose: a page showing betting lines and
-- a page showing 1936 poll results have very different notions of fresh, and one number for
-- both tells the user nothing.
--
-- So freshness is per DOMAIN, mapped to the endpoints that actually feed it. A serving view
-- joins the domain it belongs to and exposes the result as `as_of_ts`.
with endpoint_domain as (
    select * from (values
        -- Endpoint labels are the FLATTENED form: src/ingest.fetch replaces '/' with '_' so
        -- an endpoint can be a directory name, and the manifest records what it wrote. The
        -- API-path spelling silently matches nothing — the same trap that made
        -- stg_api_usage_endpoint return zero rows.
        ('games',        'game'),
        ('games_teams',  'game'),
        ('calendar',     'game'),
        ('records',      'game'),
        ('lines',        'market'),
        ('rankings',     'rankings'),
        ('stats_season', 'stats'),
        ('teams',        'team'),
        ('conferences',  'team'),
        ('venues',       'team'),
        ('info',         'ops'),
        ('info_usage',   'ops')
    ) as t(endpoint, domain)
),
loads as (
    select
        d.domain,
        max(m.fetched_at) as as_of_ts,
        count(*)          as load_count
    from {{ ref('stg_raw_manifest') }} m
    join endpoint_domain d on d.endpoint = m.endpoint
    where m.status_code = 200
    group by d.domain
)
select domain, as_of_ts, load_count from loads

union all

-- Predictions do not come from an endpoint, so their freshness is the export's own
-- timestamp rather than an API fetch. Kept in the same table so a view joins one place.
select
    'prediction' as domain,
    max(prediction_ts) as as_of_ts,
    count(distinct model_version) as load_count
from {{ ref('fct_prediction') }}
