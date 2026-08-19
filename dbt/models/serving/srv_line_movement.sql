-- Line movement: one row per (game, provider, snapshot). Additive — a time series straight
-- off the fact, which is the only shape that answers "how did this line move".
select
    l.betting_line_sk, l.game_id, l.snapshot_ts,
    l.provider_key, p.provider_name, l.provider_raw,
    l.season, l.week, l.season_type,
    l.spread, l.formatted_spread, l.spread_open,
    l.over_under, l.over_under_open, l.home_moneyline, l.away_moneyline,
    g.game_date, g.start_date, g.home_team, g.away_team, g.home_team_id, g.away_team_id,
    h.abbreviation as home_abbreviation, a.abbreviation as away_abbreviation,
    -- Movement since open, computed here so the app never subtracts.
    case when l.spread is not null and l.spread_open is not null
         then l.spread - l.spread_open end as spread_move_from_open,
    ao_src.as_of_ts
from {{ ref('fct_betting_line') }} l
left join {{ ref('dim_provider') }} p on p.provider_key = l.provider_key
left join {{ ref('fct_game') }} g on g.game_id = l.game_id
left join {{ ref('dim_team') }} h on h.season = l.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = l.season and a.team_id = g.away_team_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'market') ao_src
