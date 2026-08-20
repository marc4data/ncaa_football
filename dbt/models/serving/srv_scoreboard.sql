-- Scoreboard: one row per game, carrying both card states. Additive.
-- Pre-game fields and post-game fields live on the same row so the app switches on
-- is_completed rather than querying two objects.
--
-- The slug, display-name, kickoff, venue and poll-rank columns were added after the Scores
-- page was found asking for eight columns this view did not have. That page had been
-- rendering the Error state on every load since it was written, and it looked like a
-- handled failure rather than a defect — which is the cost of a graceful degradation the
-- author never sees fire. The fix belongs here rather than in the page: a link needs a
-- slug, and a serving view that cannot produce one forces the app to build URLs from
-- display names.
-- AP only, and only one poll, because the badge shows ONE number. Verified unique on
-- (season, season_type, week, team_id) across all 27,371 rows — a second poll here would
-- fan the scoreboard out silently, which is how fct_game gained 18 phantom rows once.
with ap_rank as (
    select season, season_type, week, team_id, rank
    from {{ ref('fct_poll_rank') }}
    where poll_name = 'AP Top 25'
)

select
    g.game_sk, g.game_id, g.season, g.week, g.season_type, g.game_date, g.start_date,
    g.is_completed, g.is_neutral_site, g.venue,
    g.venue as venue_display,
    {{ to_local_timestamp('g.start_date') }} as start_date_et,
    g.home_team_id, g.home_team, h.abbreviation as home_abbreviation,
    h.team_slug as home_team_slug, h.team_display as home_team_display,
    h.color_on_light as home_color_on_light, h.logo_source_url as home_logo_url,
    g.home_points,
    g.away_team_id, g.away_team, a.abbreviation as away_abbreviation,
    a.team_slug as away_team_slug, a.team_display as away_team_display,
    a.color_on_light as away_color_on_light, a.logo_source_url as away_logo_url,
    g.away_points,
    -- AC-1.5: the rank the team held going into this game, so an unranked team can show
    -- NO badge rather than an em dash inside one. Poll rank is week-scoped, which is why
    -- this cannot be read off dim_team.
    hp.rank as home_rank,
    ap.rank as away_rank,
    case
        when not g.is_completed then null
        when g.home_points > g.away_points then g.home_team
        when g.away_points > g.home_points then g.away_team
        else null
    end as winner,
    abs(coalesce(g.home_points, 0) - coalesce(g.away_points, 0)) as final_margin,
    hr.wins as home_wins, hr.losses as home_losses,
    ar.wins as away_wins, ar.losses as away_losses,
    ao_src.as_of_ts,
    g.away_points - g.home_points as actual_margin,   -- away minus home, per the convention
    g.excitement_index,
    g.is_upset,
    g.attendance
from {{ ref('fct_game') }} g
left join ap_rank hp
    on hp.season = g.season and hp.season_type = g.season_type
   and hp.week = g.week and hp.team_id = g.home_team_id
left join ap_rank ap
    on ap.season = g.season and ap.season_type = g.season_type
   and ap.week = g.week and ap.team_id = g.away_team_id
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
left join {{ ref('fct_team_record') }} hr on hr.season = g.season and hr.team_id = g.home_team_id
left join {{ ref('fct_team_record') }} ar on ar.season = g.season and ar.team_id = g.away_team_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao_src
