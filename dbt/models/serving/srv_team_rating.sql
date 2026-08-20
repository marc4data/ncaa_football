-- Team ratings, one row per (season, team, system). The Ratings tab and the Matchup
-- ratings block read this.
--
-- `is_projection` travels to the page and is the reason this view exists rather than the
-- page reading five columns off srv_team_overview. In weeks 1 to 4 the only ratings that
-- exist are SP+ and FPI, and both are FORECASTS — Elo, SRS and PPA are computed from
-- results and have nothing to compute from yet. Rendering a projection and a measurement in
-- the same styling would be the same defect as showing a backtest hit rate beside a
-- realised one.
--
-- `rating_scope` is 'season' on every row today. It is here so a weekly Elo backfill is
-- additive, and so a Trends chart can ask for week-scoped rows and get an honest empty
-- answer rather than a flat line drawn from a season value repeated fourteen times.
select
    r.team_rating_sk,
    r.season,
    r.rating_system,
    -- What a reader calls each system. Held here rather than in the page because the
    -- Matchup block, the Ratings tab and the Excel export would otherwise each spell them.
    case r.rating_system
        when 'sp_plus' then 'SP+'
        when 'srs'     then 'SRS'
        when 'elo'     then 'Elo'
        when 'fpi'     then 'FPI'
        when 'ppa'     then 'PPA'
        else r.rating_system
    end                              as rating_system_display,
    -- Sort order for a page that shows all five: the two that exist preseason first, so a
    -- week-1 reader sees populated rows above empty ones.
    case r.rating_system
        when 'sp_plus' then 1 when 'fpi' then 2 when 'elo' then 3
        when 'srs' then 4 when 'ppa' then 5 else 9
    end                              as display_order,
    r.team_id,
    r.school,
    {{ team_identity('t', 'r.school') }},
    t.logo_source_url                as logo_url,
    t.color_on_light,
    r.conference,
    r.classification,
    r.rating,
    r.rating_rank,
    r.rating_rank_computed,
    r.rating_percentile,
    r.rating_population,
    r.offense_rating,
    r.defense_rating,
    r.special_teams_rating,
    r.strength_of_schedule,
    r.second_order_wins,
    r.rating_scope,
    r.week,
    r.is_projection,
    r.completed_games_at_rating,
    -- The sentence a page renders beside the number. Carried as data so the caveat cannot
    -- be dropped by a page that forgets it, the same reason `attribution` is a column.
    case when r.is_projection
         then 'Preseason projection — no game has been played yet, so this is a forecast '
              || 'rather than a measurement.'
         else 'Computed from ' || cast(r.completed_games_at_rating as {{ dbt.type_string() }})
              || ' completed game(s).'
    end                              as rating_basis_note,
    ao_src.as_of_ts
from {{ ref('fct_team_rating') }} r
left join {{ ref('dim_team') }} t
    on t.season = r.season and t.team_id = r.team_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'team') ao_src
