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
-- Game-grain totals from the team-grain box score. R-006.
--
-- NOT BLOCKED, which is worth saying because it was expected to be: srv_scoreboard carries
-- no yardage, but fct_game_team does, at game x team grain — so "total yards, both teams"
-- is a sum of the two rows for a game rather than a column that has to be invented.
--
-- Box scores are `recent` scope: 3,360 of 7,662 completed 2025 team-rows carry total_yards
-- and NOTHING before 2024 does. So this is null for most of history, which is the honest
-- state and renders as an em dash rather than a zero.
with game_box as (
    select
        game_id,
        sum(total_yards)    as total_yards_both_teams,
        sum(rushing_yards)  as rushing_yards_both_teams,
        sum(passing_yards)  as passing_yards_both_teams,
        sum(turnovers)      as turnovers_both_teams,
        count(*) filter (where total_yards is not null) as teams_with_box_score
    from {{ ref('fct_game_team') }}
    group by game_id
),

-- The last line recorded BEFORE kickoff, and its provenance. R-007.
--
-- srv_scoreboard was contracted to carry `spread_at_close` and does not. Building it
-- surfaced why the name matters: our snapshot history begins 2026-08-15, when the lines DAG
-- started sampling. For a 2024 game, the only line we hold is whatever CFBD returned when
-- we fetched it in August 2026 — a real market number, but its snapshot_ts is our FETCH
-- time, not a pre-kickoff observation.
--
-- Calling both "close" would conflate a line we watched with a line we were told about, so
-- the two are distinguished by `spread_at_close_basis` and the page says which it is. An
-- unattributed line is a number with no provenance and this project does not ship those.
pre_kick as (
    select game_id, spread, provider_key, snapshot_ts, basis from (
        select
            b.game_id, b.spread, b.provider_key, b.snapshot_ts,
            case when b.snapshot_ts <= g.start_date then 'observed_before_kickoff'
                 else 'as_recorded_by_cfbd' end as basis,
            row_number() over (
                partition by b.game_id
                -- Prefer a genuine pre-kickoff observation; among those, the latest.
                order by case when b.snapshot_ts <= g.start_date then 0 else 1 end,
                         b.snapshot_ts desc, b.provider_key
            ) as recency
        from {{ ref('fct_betting_line') }} b
        join {{ ref('fct_game') }} g on g.game_id = b.game_id
    ) ranked where recency = 1
),

ap_rank as (
    select season, season_type, week, team_id, rank
    from {{ ref('fct_poll_rank') }}
    where poll_name = 'AP Top 25'
)

select
    g.game_sk, g.game_id, g.season, g.week, g.season_type, g.game_date, g.start_date,
    g.is_completed, g.is_neutral_site, g.venue,
    g.venue as venue_display,
    {{ to_local_timestamp('g.start_date') }} as start_date_et,
    -- THE NAME COMES FROM THE GAME, not from the dimension.
    --
    -- dim_team is season-scoped and built from CFBD's /teams response, which does not list
    -- every opponent an FBS or FCS side happens to schedule: a Division II visitor exists in
    -- /games and not in /teams. Taking the display name off the dimension left it NULL on
    -- 12,168 of 110,634 rows — 11% of the scoreboard — and the page rendered an em dash for
    -- the team and, worse, `None` for the winner.
    --
    -- fct_game carries the name for both sides on every row, always. srv_schedule already
    -- did it this way and has zero nulls; this view was the one that disagreed.
    --
    -- The slug falls back to a slug OF that name rather than to NULL. A null slug is a link
    -- to nowhere; a derived slug is a link to a team page that will honestly render Empty,
    -- because a team with no dim_team row genuinely has no season record to show.
    -- FBS SPINE (Marc, 2026-08-20). EITHER team, not both: a Division II visitor's trip
    -- to an FBS stadium is an FBS game, and excluding it would drop 20 of the 25 games on
    -- the opening Thursday. 934 of 3,831 games in 2025 qualify, so this is the difference
    -- between a schedule about college football and a schedule about all of college
    -- football. Carried as a COLUMN so the site filters on it with a default rather than a
    -- hardcoded WHERE nobody can widen.
    (g.home_classification = 'fbs' or g.away_classification = 'fbs') as is_fbs_game,

    g.home_team_id, g.home_team, h.abbreviation as home_abbreviation,
    {{ team_identity('h', 'g.home_team', 'home_') }},
    h.color_on_light as home_color_on_light, h.logo_source_url as home_logo_url,
    g.home_points,
    g.away_team_id, g.away_team, a.abbreviation as away_abbreviation,
    {{ team_identity('a', 'g.away_team', 'away_') }},
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
    -- NULL, not zero, for a game with no result — the same rule `total_points` below
    -- applies, and this column was the one place that broke it. `coalesce(points, 0)` gave
    -- all 1,769 unplayed games a final margin of 0, which is indistinguishable from a tie
    -- and from the three completed-but-unscored games. Zero here now means exactly one
    -- thing: the two teams finished level.
    case when g.is_completed and g.home_points is not null and g.away_points is not null
         then abs(g.home_points - g.away_points) end       as final_margin,
    hr.wins as home_wins, hr.losses as home_losses,
    ar.wins as away_wins, ar.losses as away_losses,
    ao_src.as_of_ts,
    g.away_points - g.home_points as actual_margin,   -- away minus home, per the convention
    g.excitement_index,
    g.is_upset,
    g.attendance,

    -- R-005. Computed in dbt, not summed in the app: the single-table-SELECT rule means no
    -- metric maths in Streamlit, and a sum in a page is exactly that.
    --
    -- NULL, not zero, for a game that has not been played. We have shipped the opposite
    -- once — ats_record_display reading 0-0-0 for seasons nobody had played, in the same
    -- row where wins and losses were correctly null. One table, two treatments of "hasn't
    -- happened yet" is the bug; a third instance is not going in.
    case when g.is_completed and g.home_points is not null and g.away_points is not null
         then g.home_points + g.away_points end            as total_points,

    -- R-006.
    bx.total_yards_both_teams,
    bx.rushing_yards_both_teams,
    bx.passing_yards_both_teams,
    bx.turnovers_both_teams,
    -- 2 when both box scores landed, 1 when only one did, 0 when neither. A total built
    -- from one team is not a game total, and this is what lets the page say so.
    bx.teams_with_box_score,

    -- R-007.
    pk.spread as spread_at_close,
    pk.provider_key as spread_at_close_provider,
    pk.basis as spread_at_close_basis,

    -- R-008. WHETHER THE FAVOURITE COVERED — distinct from which side covered.
    --
    -- Four states, and pending is not push. A pick'em (spread exactly 0) has no favourite
    -- at all, which is the not-applicable third state of AC-G.32 and a real case in the
    -- data rather than a hypothetical.
    --
    -- Convention, as everywhere: margin is away minus home, so a NEGATIVE spread means the
    -- home team is favoured. The favourite covers when the actual margin beats the number
    -- in the favourite's direction.
    case
        when not g.is_completed or g.home_points is null then 'pending'
        when pk.spread is null then null
        when pk.spread = 0 then 'no_favorite'
        when (g.away_points - g.home_points) = pk.spread then 'push'
        when pk.spread < 0 and (g.away_points - g.home_points) < pk.spread then 'yes'
        when pk.spread > 0 and (g.away_points - g.home_points) > pk.spread then 'yes'
        else 'no'
    end                                                    as favorite_covered
from {{ ref('fct_game') }} g
left join game_box bx on bx.game_id = g.game_id
left join pre_kick pk on pk.game_id = g.game_id
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
