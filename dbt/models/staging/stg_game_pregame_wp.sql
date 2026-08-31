-- Pre-game win probability: one row per (game, snapshot).
--
-- NOT DEDUPLICATED, AND THAT IS THE POINT — the same choice stg_lines makes, for the same
-- reason. /metrics/wp/pregame is registered `snapshot=True`: it answers differently to an
-- identical request as the week progresses, because the number moves with the market and
-- with injury news. Collapsing to the latest fetch would keep one number per game and throw
-- away the movement, which is the only thing repeated fetching buys.
--
-- snapshot_ts is raw_manifest.fetched_at — when the probability was OBSERVED, not when the
-- file was loaded. Load time would make every snapshot in a catch-up load look simultaneous,
-- which turns a movement series into a vertical line.
--
-- TEAMS BY NAME, NO IDS. The payload names home and away and carries no team id, so a join to
-- a team dimension is a string join; game_id is the reliable key here.

with responses as (

    select
        r.filename,
        m.fetched_at as snapshot_ts,
        {{ json_get_object('r.content', 'data') }} as payload
    from {{ source('raw', 'raw_metrics_wp_pregame') }} r
    join {{ source('raw', 'raw_manifest') }} m
        -- THE MANIFEST KEYS ENDPOINTS WITH UNDERSCORES, NOT SLASHES: `metrics_wp_pregame`,
        -- from src.endpoints.Endpoint.key, which is path.replace("/", "_"). stg_lines gets
        -- away with the plain name because `lines` has no slash in it.
        --
        -- Written as the path first, this join matched nothing and the model returned zero
        -- rows — and the build stayed green, because not_null passes vacuously on an empty
        -- table. Caught only by looking at the row count against real data.
        on m.endpoint = 'metrics_wp_pregame' and m.filename = r.filename
    where r.status_code = 200

),

exploded as (

    select filename, snapshot_ts, {{ json_array_elements('payload') }} as row_json
    from responses

)

select
    filename,
    snapshot_ts,
    cast({{ json_get_string('row_json', 'gameId') }} as bigint) as game_id,
    cast({{ json_get_string('row_json', 'season') }} as int)    as season,
    cast({{ json_get_string('row_json', 'week') }} as int)      as week,
    {{ json_get_string('row_json', 'seasonType') }}             as season_type,
    {{ json_get_string('row_json', 'homeTeam') }}               as home_team,
    {{ json_get_string('row_json', 'awayTeam') }}               as away_team,
    {{ safe_numeric(json_get_string('row_json', 'spread')) }}   as spread,
    -- Home team's probability of winning. The away side is 1 - this, and is NOT stored:
    -- deriving it is exact, whereas storing both invites them to disagree after an edit.
    {{ safe_numeric(json_get_string('row_json', 'homeWinProbability')) }}
        as home_win_probability
from exploded
