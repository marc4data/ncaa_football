{{ config(materialized='table') }}

-- One row per game. A promotion of stg_games — the grain was already correct — with
-- conformed keys attached.
--
-- This model owns the date-era logic. CFBD records kickoff times only from 2001; earlier
-- games are stored at midnight UTC as date-only values, and converting those to a local
-- zone shifts 66,496 games back a day. Everything downstream reads game_date and
-- kickoff_time_known from here rather than recomputing and getting it wrong differently.

with season_has_times as (

    select season, bool_or({{ utc_time_of_day('start_date') }} <> '00:00:00') as times_known
    from {{ ref('stg_games') }}
    group by season

),

games as (

    select
        g.*,
        h.times_known,
        -- TV only: /games/media returns a row per media type, so joining all of them would
        -- multiply each game — the exact fan-out a one-row-per-game grain exists to prevent.
        m.outlet as network,
    -- Short form for a table cell, from the dimension rather than trimmed in a view, so the
    -- site and the Excel workbook cannot disagree about what a channel is called.
    m.outlet_abbreviation as network_abbreviation,
        -- One poll on purpose, for the same reason.
        hr.rank as home_rank,
        ar.rank as away_rank
    from {{ ref('stg_games') }} g
-- Deduplicated to ONE TV row per game. Simulcasts are real — ABC and SEC Network carry the
-- same game, ESPN and ESPN2 likewise — and joining them all multiplied 18 games into two
-- rows each, breaking the one-row-per-game grain. Caught by the before/after row count,
-- not by an error: a fan-out is a silent correctness bug that still builds green.
-- ORDERED BY PRECEDENCE, NOT ALPHABETICALLY. R-080.
--
-- This was `order by outlet`, which is not a rule — it is the absence of one. On the 49 games
-- carrying more than one TV outlet, ABC beat ESPN because A sorts before E. dim_broadcast_outlet
-- carries an authored precedence_rank; outlet_raw remains the tiebreaker so the pick stays
-- deterministic between two channels of equal rank.
--
-- The join also NORMALISES: `ACC Network` and `ACC NETWORK` are one channel, as are BTN/BIG10
-- and The CW Network/CW. Without the dimension those are four extra distinct values in the
-- warehouse and in the Excel export, which no display-side trim could reach.
left join (
    select game_id, display_name as outlet, display_abbreviation as outlet_abbreviation
    from (
        select
            media.game_id,
            dim.display_name,
            dim.display_abbreviation,
            row_number() over (
                partition by media.game_id
                order by dim.precedence_rank, media.outlet) as outlet_rank
        from {{ ref('stg_game_media') }} media
        join {{ ref('dim_broadcast_outlet') }} dim
            on dim.outlet_raw = media.outlet and dim.media_type = media.media_type
        where media.media_type = 'tv'
    ) ranked
    where outlet_rank = 1
) m on m.game_id = g.game_id
left join {{ ref('fct_poll_rank') }} hr
    on hr.season = g.season and hr.season_type = g.season_type and hr.week = g.week
   and hr.team_id = g.home_team_id and hr.poll_name = 'AP Top 25'
left join {{ ref('fct_poll_rank') }} ar
    on ar.season = g.season and ar.season_type = g.season_type and ar.week = g.week
   and ar.team_id = g.away_team_id and ar.poll_name = 'AP Top 25'
    join season_has_times h on h.season = g.season

)

select
    {{ surrogate_key(['g.game_id']) }} as game_sk,
    g.game_id,
    g.season,
    g.week,
    g.season_type,
    {{ surrogate_key(['g.season', 'g.season_type', 'g.week']) }} as week_sk,
    {{ surrogate_key(['g.season', 'g.home_team_id']) }} as home_team_sk,
    {{ surrogate_key(['g.season', 'g.away_team_id']) }} as away_team_sk,
    g.home_team_id,
    g.away_team_id,
    g.home_team,
    g.away_team,
    g.home_classification,
    g.away_classification,
    g.start_date,
    case
        when g.times_known then {{ to_local_date('g.start_date') }}
        else {{ to_utc_date('g.start_date') }}
    end as game_date,
    g.times_known as kickoff_time_known,
    g.is_completed,
    g.is_conference_game,
    g.is_neutral_site,
    g.home_points,
    g.away_points,
    -- Venue name, not a key: /games carries no venue id, so a dim_venue join would be
    -- name-based and lossy. The name is what pages render anyway.
    g.venue,
    g.attendance,
    g.excitement_index,

    -- Broadcast outlet, TV only. /games/media returns a row per media type, so a game on
    -- TV and on a streaming service appears twice; taking the TV row keeps the grain at one
    -- row per game. A game with no TV row has a null network, which is the honest answer
    -- for a game nobody is carrying.
    g.network,
    g.network_abbreviation,

    -- Poll ranks at the time of the game, AP only, and IS_UPSET derived from them.
    --
    -- One poll on purpose: joining every poll would multiply each game by the number of
    -- polls ranking either team, which is precisely the fan-out a grain of "one row per
    -- game" exists to prevent.
    g.home_rank,
    g.away_rank,
    case
        when not g.is_completed then null
        -- NULL WHEN NEITHER SIDE WAS RANKED, BECAUSE THERE IS NO FAVOURITE TO BE UPSET.
        --
        -- This branch used to be part of `else false`, and that was a claim we had no basis
        -- for: 91,047 of 109,108 completed games — 83% — asserted "not an upset" with no
        -- poll rank on either team. Marc found it on Grand Valley State at Charleston (WV),
        -- a Division II game with no ranks and no line, drawn on the page as an assessed
        -- non-upset. There is nothing there to assess.
        --
        -- The definition stays RANK-BASED, which is what AC-3.6 documents and what the two
        -- branches below implement. A market favourite is a different basis and would be a
        -- different metric — `winner_covered_close` on srv_game already answers that
        -- question, and conflating the two would give one column two meanings.
        when g.home_rank is null and g.away_rank is null then null
        -- An upset is the ranked side losing to a side ranked worse or unranked. Stated as
        -- a column because AC-3.6 forbids the app comparing ranks itself.
        when g.home_points > g.away_points and g.away_rank is not null
             and (g.home_rank is null or g.home_rank > g.away_rank) then true
        when g.away_points > g.home_points and g.home_rank is not null
             and (g.away_rank is null or g.away_rank > g.home_rank) then true
        else false
    end as is_upset,

    -- PER-GAME ELO, R-083. A rating per team per GAME is a rating per team per WEEK, so this
    -- is the weekly rating series the project had recorded as needing /ratings/elo re-fetched
    -- with a week parameter. It does not: the games spine has carried it all along, unused.
    -- Populated on 67,306 of 110,879 rows; null before Elo existed, which is honest.
    g.home_pregame_elo,
    g.home_postgame_elo,
    g.away_pregame_elo,
    g.away_postgame_elo,

    -- LINE SCORES, R-082, TYPED RATHER THAN LEFT AS JSON.
    --
    -- The source is jsonb and its shape is not what "populated on every row" suggests. It is
    -- non-null on every row, but 64,254 rows hold an EMPTY array and 1,850 hold JSON null;
    -- only 44,775 carry actual quarters, and the earliest is 2001. Modern seasons are
    -- effectively complete (3,805 of 3,831 in 2025) and the gap is historical.
    --
    -- FOUR QUARTERS AS COLUMNS, OVERTIME AS A SUM. Periods run to THIRTEEN in this data —
    -- nine overtimes — so a column per period would either invent nine of them or silently
    -- truncate a triple-OT game. Four typed quarters cover the card; `overtime_points`
    -- carries everything past regulation without pretending to know how many periods that
    -- was, and `periods` says how many there were so a page can render "2OT" honestly.
    --
    -- The raw array stays on this fact and does NOT go to serving: the site does no
    -- computation, and a jsonb column would export to Excel as a JSON string.
    {{ line_score_period('g.home_line_scores', 1) }} as home_q1,
    {{ line_score_period('g.home_line_scores', 2) }} as home_q2,
    {{ line_score_period('g.home_line_scores', 3) }} as home_q3,
    {{ line_score_period('g.home_line_scores', 4) }} as home_q4,
    {{ line_score_overtime('g.home_line_scores') }}  as home_overtime_points,
    {{ line_score_periods('g.home_line_scores') }}   as home_periods,
    {{ line_score_period('g.away_line_scores', 1) }} as away_q1,
    {{ line_score_period('g.away_line_scores', 2) }} as away_q2,
    {{ line_score_period('g.away_line_scores', 3) }} as away_q3,
    {{ line_score_period('g.away_line_scores', 4) }} as away_q4,
    {{ line_score_overtime('g.away_line_scores') }}  as away_overtime_points,
    {{ line_score_periods('g.away_line_scores') }}   as away_periods,
    g.home_line_scores,
    g.away_line_scores
from games g
