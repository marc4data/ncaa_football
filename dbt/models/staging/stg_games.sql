{{ config(materialized='table') }}

-- One row per game, across every season landed in raw.
--
-- MATERIALIZED AS A TABLE, and alone among the staging models in that. Staging is views by
-- convention because a view costs nothing to build and the work is trivial. This model
-- stopped being trivial when the game_id dedup below was added: a window function is an
-- optimization fence, and this view is referenced FOUR times — twice inside fct_game alone,
-- once for a GROUP BY and once joined to four other relations. As a view each reference is
-- re-inlined and re-sorted, and the planner, unable to push predicates through the fence,
-- chose a plan for fct_game that had not finished after eight minutes against a build that
-- previously took under thirty seconds for the whole 27-model selection.
--
-- Reading the view standalone is 216 ms. The cost was never the dedup; it was paying for it
-- once per reference and denying the planner any statistics. As a table the dedup runs once
-- per dbt run and every downstream model reads an analyzed relation.
--
-- DEDUP HAPPENS TWICE, ON TWO DIFFERENT KEYS, BECAUSE THERE ARE TWO DIFFERENT DUPLICATES.
--
-- 1. Per params, keeping the newest FILE. The backfill fetches each season twice — once for
--    `seasonType=regular`, once for `postseason` — so deduping per season would silently
--    discard the bowl games. Keying on the whole params object generalises: one surviving
--    file per distinct request, whatever dimensions that request had.
--
-- 2. Per game_id, keeping the row from the newest file. Step 1 is only sufficient while
--    requests are DISJOINT, and it has no answer for OVERLAPPING ones. cfbd_scores_refresh
--    fetches `{year, week, seasonType}`; the backfill holds `{year, seasonType}` for the
--    whole season. Different params, so different partitions, so both files survive step 1
--    — and every game the week-scoped file shares with the season-wide one is emitted
--    twice. That is 211 duplicate game_ids on the first live run of the scores DAG, and
--    nine failing tests: the unique tests on stg_games and fct_game, the schedule
--    reconciliation assertions, and srv_team_game_log parity.
--
--    It had never fired because nothing in the project fetched a single week until the
--    scores DAG did. Two latent faults that only meet on first use.
--
--    Newest file wins, matching step 1, so a refetch supersedes rather than races: the
--    2-hourly scores fetch is by construction newer than the backfill it overlaps.
--
-- Verified as a strict no-op for history: across 157 seasons of raw, 1869 to 2025, this
-- drops zero rows. Only 2026 changes, and only by the 211 it is here to remove.
--
-- JSON access goes through the dispatched macros (see macros/json.sql); the dedup uses a
-- window function rather than Postgres' `distinct on`, which Spark has no equivalent for.

with successful_fetches as (

    select
        params,
        filename,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (
            partition by params
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_games') }}
    where status_code = 200

),

exploded as (

    select
        filename,
        {{ json_array_elements('payload') }} as game
    from successful_fetches
    where recency = 1

),

games as (

    select game
    from (
        select
            game,
            row_number() over (
                partition by cast({{ json_get_string('game', 'id') }} as int)
                order by filename desc
            ) as game_recency
        from exploded
    ) ranked
    where game_recency = 1

)

select
    cast({{ json_get_string('game', 'id') }} as int)              as game_id,
    cast({{ json_get_string('game', 'season') }} as int)          as season,
    cast({{ json_get_string('game', 'week') }} as int)            as week,
    {{ json_get_string('game', 'seasonType') }}                   as season_type,
    cast({{ json_get_string('game', 'startDate') }} as {{ type_timestamp_tz() }}) as start_date,
    cast({{ json_get_string('game', 'completed') }} as boolean)   as is_completed,
    cast({{ json_get_string('game', 'conferenceGame') }} as boolean) as is_conference_game,
    cast({{ json_get_string('game', 'neutralSite') }} as boolean) as is_neutral_site,
    cast({{ json_get_string('game', 'homeId') }} as int)          as home_team_id,
    {{ json_get_string('game', 'homeTeam') }}                     as home_team,
    cast({{ json_get_string('game', 'homePoints') }} as int)      as home_points,
    {{ json_get_string('game', 'homeClassification') }}           as home_classification,
    cast({{ json_get_string('game', 'awayId') }} as int)          as away_team_id,
    {{ json_get_string('game', 'awayTeam') }}                     as away_team,
    cast({{ json_get_string('game', 'awayPoints') }} as int)      as away_points,
    {{ json_get_string('game', 'awayClassification') }}           as away_classification,
    cast({{ json_get_string('game', 'venueId') }} as int)         as venue_id,
    {{ json_get_string('game', 'venue') }}                        as venue,
    cast({{ json_get_string('game', 'attendance') }} as int)      as attendance,
    {{ safe_numeric(json_get_string('game', 'excitementIndex')) }} as excitement_index,

    -- CONFERENCE, ON THE SPINE AT LAST. This model held classification but not conference,
    -- so labelling a game as a conference matchup, or grouping the schedule by league, meant
    -- joining out to stg_teams — a season-scoped join, for a fact the payload was carrying
    -- all along. `is_conference_game` above says WHETHER; these say WHICH.
    {{ json_get_string('game', 'homeConference') }}               as home_conference,
    {{ json_get_string('game', 'awayConference') }}               as away_conference,

    -- Quarter-by-quarter scores, as JSON arrays. Carried rather than exploded: a scoring
    -- progression belongs at game grain here and a mart can unnest it to quarters where a
    -- page needs that shape.
    {{ json_get_object('game', 'homeLineScores') }}               as home_line_scores,
    {{ json_get_object('game', 'awayLineScores') }}               as away_line_scores,

    -- ELO BEFORE AND AFTER, plus the postgame win probability. These are the only
    -- game-level model outputs on the spine, and the pregame/postgame pair is what makes an
    -- upset measurable rather than anecdotal.
    {{ safe_numeric(json_get_string('game', 'homePregameElo')) }}  as home_pregame_elo,
    {{ safe_numeric(json_get_string('game', 'homePostgameElo')) }} as home_postgame_elo,
    {{ safe_numeric(json_get_string('game', 'homePostgameWinProbability')) }}
                                                                   as home_postgame_win_probability,
    {{ safe_numeric(json_get_string('game', 'awayPregameElo')) }}  as away_pregame_elo,
    {{ safe_numeric(json_get_string('game', 'awayPostgameElo')) }} as away_postgame_elo,
    {{ safe_numeric(json_get_string('game', 'awayPostgameWinProbability')) }}
                                                                   as away_postgame_win_probability,

    cast({{ json_get_string('game', 'startTimeTBD') }} as boolean) as is_start_time_tbd,
    {{ json_get_string('game', 'notes') }}                         as notes,
    {{ json_get_string('game', 'highlights') }}                    as highlights,

    -- THE PLAYOFF BLOCK IS NULL FOR ALMOST EVERY GAME, and that is the normal case rather
    -- than missing data — only playoff games carry it. It duplicates what stg_cfp_matchup
    -- holds from /playoffs/cfp/games, but reaches back further: /playoffs/cfp is fetched for
    -- two seasons while the game spine runs to 1869, so a pre-2024 playoff game is described
    -- here and nowhere else.
    {{ json_get_nested_string('game', ['playoff', 'competition']) }} as playoff_competition,
    {{ json_get_nested_string('game', ['playoff', 'format']) }}      as playoff_format,
    {{ json_get_nested_string('game', ['playoff', 'round']) }}       as playoff_round,
    {{ json_get_nested_string('game', ['playoff', 'roundName']) }}   as playoff_round_name,
    {{ json_get_nested_string('game', ['playoff', 'bracketSlot']) }} as playoff_bracket_slot,
    {{ json_get_nested_string('game', ['playoff', 'bowlName']) }}    as playoff_bowl_name,
    cast({{ json_get_nested_string('game', ['playoff', 'homeSeed']) }} as int)
                                                                     as playoff_home_seed,
    cast({{ json_get_nested_string('game', ['playoff', 'awaySeed']) }} as int)
                                                                     as playoff_away_seed
from games
