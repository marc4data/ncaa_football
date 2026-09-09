-- Every endpoint label in mart_as_of's map must be a label the manifest has actually seen.
-- R-490.
--
-- ⚠️ THIS IS THE TEST THAT WOULD HAVE CAUGHT THE CLASS, AND IT DID NOT EXIST UNTIL NOW.
-- R-353 found srv_drive borrowing the 'game' stamp, fixed that one instance, and left the
-- class open. Five months later A077 found six more by walking lineage by hand. In between,
-- nothing in this repo could tell you a domain was built from a label that matches nothing.
--
-- THE FAILURE MODE IT CATCHES IS SILENT BY CONSTRUCTION. mart_as_of joins its literal map to
-- stg_raw_manifest on `endpoint`. A label that matches nothing does not error and does not
-- warn — it contributes no rows, and the domain is quietly built from whatever labels remain.
-- A domain whose labels ALL fail to match disappears from the table entirely, and because
-- every serving view reaches it through a `cross join` on a one-row subquery, that view then
-- returns ZERO ROWS. A typo here does not produce a wrong caption; it produces an empty page.
--
-- Three ways to get here, all silent today:
--   1. the API-path spelling. src/ingest.fetch flattens '/' to '_', so 'games/weather' matches
--      nothing while 'games_weather' matches. This exact mistake is why stg_api_usage_endpoint
--      once returned zero rows, and mart_as_of's own header warns about it in prose — prose
--      that nothing enforced.
--   2. an ordinary typo: 'ratings_srs_expaned'.
--   3. an endpoint renamed upstream, where the map keeps pointing at the old label. This one
--      is the nastiest: it works for months and then silently stops.
--
-- ⚠️ WHAT THIS TEST DELIBERATELY DOES NOT CLAIM. It proves every label is REAL. It does not
-- prove the label belongs in the domain it is mapped to, which is the actual A077 defect —
-- srv_team_rating joined a domain built entirely from real, correct, current labels that had
-- nothing to do with ratings. The stronger check is proposed in the A077 report; this is the
-- cheap half that closes the silent-failure half of the class.
with mapped as (

    -- The map, restated. ⚠️ It is restated rather than selected out of mart_as_of because
    -- mart_as_of has already DONE the join: a label that matched nothing has been dropped by
    -- the time the model produces rows, so a test reading its output cannot see the thing it
    -- is looking for. The literal has to be duplicated for the test to have anything to test.
    --
    -- ⚠️ AND THE DUPLICATION IS ITSELF A HAZARD, STATED SO NOBODY DISCOVERS IT THE HARD WAY:
    -- add a domain to mart_as_of and forget to add it here, and this test still PASSES while
    -- covering less than it appears to — the same shape as the defect it exists to catch, one
    -- level up. The clean fix is to lift the map into its own model (dim_as_of_map) that both
    -- mart_as_of and this test read, so there is one list. That is a bigger change than A077's
    -- scope and is proposed in the A077 report rather than done in passing.
    select * from (values
        ('games'), ('games_teams'), ('calendar'), ('records'), ('drives'), ('lines'),
        ('rankings'), ('stats_season'), ('teams'), ('conferences'), ('venues'),
        ('info'), ('info_usage'),
        ('ratings_sp'), ('ratings_srs'), ('ratings_elo'), ('ratings_fpi'), ('ppa_teams'),
        ('games_weather'), ('games_players'), ('plays'), ('plays_stats'),
        ('stats_player_season'), ('roster')
    ) as t(endpoint)

),

seen as (

    select distinct endpoint from {{ ref('stg_raw_manifest') }} where status_code = 200

)

select m.endpoint as label_in_mart_as_of_that_matches_no_manifest_endpoint
from mapped m
left join seen s on s.endpoint = m.endpoint
where s.endpoint is null
