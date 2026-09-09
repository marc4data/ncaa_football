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
        -- R-353. Drives are their own domain and were missing entirely, so srv_drive read the
        -- 'game' stamp — the closest honest answer available and the wrong one. It is wrong in
        -- the direction that matters: /drives last landed 2026-09-03 while /games landed
        -- 2026-09-05, so borrowing the game stamp reported drive data as two days FRESHER than
        -- it was. A freshness column that flatters is worse than none.
        --
        -- 'drives' is the FLATTENED label, verified against raw.raw_manifest in the warehouse
        -- (17 loads) rather than read off the API path — see the note above; the path spelling
        -- matches nothing and fails silently.
        ('drives',       'drive'),
        ('lines',        'market'),
        ('rankings',     'rankings'),
        ('stats_season', 'stats'),
        ('teams',        'team'),
        ('conferences',  'team'),
        ('venues',       'team'),
        ('info',         'ops'),
        ('info_usage',   'ops'),
        -- ==================================================================================
        -- R-489. R-353 FIXED ONE INSTANCE OF THIS AND LEFT THE CLASS OPEN. These are the
        -- rest, found by walking every serving view's lineage against the domain it joins
        -- rather than by waiting for someone to notice a caption (A077/R-488).
        --
        -- THE RULE THAT DECIDES WHICH ENDPOINTS BELONG TO A DOMAIN: the endpoints that
        -- supply the view's SUBJECT, not the ones it joins for LOOKUPS. Every serving view
        -- reaches dim_team for identity, so 'teams' and 'conferences' are in almost every
        -- lineage; mapping them into every domain would make the whole site read 25 days old
        -- because reference data legitimately reloads rarely. `game` has never included them
        -- and that was already right.
        --
        -- ⚠️ EVERY LABEL BELOW WAS VERIFIED AGAINST raw.raw_manifest, not derived from the
        -- API path. A label that matches nothing does not error — it contributes no rows and
        -- the domain is silently built from whatever remains, which is the single most likely
        -- way to ship a fix that does nothing. See the note at the top of this list.

        -- Ratings. THE ONE MARC COULD SEE: srv_team_rating joined 'team', whose three
        -- endpoints are all reference lookups last loaded 2026-08-15, while the five
        -- endpoints that actually produce the ratings had loaded that morning. The page
        -- rendered 552 rows of current sp+/fpi/elo/ppa under a caption saying they were
        -- twenty-five days old. Wrong in the direction that makes a reader DISCOUNT
        -- something they should trust — the mirror of R-353 and just as false.
        ('ratings_sp',          'rating'),
        ('ratings_srs',         'rating'),
        ('ratings_elo',         'rating'),
        ('ratings_fpi',         'rating'),
        ('ppa_teams',           'rating'),

        -- Weather. srv_game_weather is fed by games_weather and joined 'game', which does not
        -- contain it. Both happened to sit at 2026-09-09 the day this was found, so there was
        -- no visible drift — which is exactly why it needed finding by lineage rather than by
        -- looking at numbers. The moment /games/weather stalls and /games does not, the
        -- caption flatters.
        ('games_weather',       'weather'),

        -- Player box scores, and play-level attribution. Both joined 'game' and neither is
        -- fed by it.
        ('games_players',       'player_game'),
        ('plays',               'play'),
        ('plays_stats',         'play'),

        -- Player season stats. 'stats' maps stats_season, which is the TEAM season endpoint;
        -- srv_player_stats is fed by stats_player_season and never touched it.
        ('stats_player_season', 'player_stats'),

        -- Roster. srv_team_roster joined 'team'. roster and teams both last loaded 08-15, so
        -- like weather there is no drift today and the mapping was still wrong.
        ('roster',              'roster')
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
