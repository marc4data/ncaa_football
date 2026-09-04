-- THE game-grain serving view: one row per game. R-076.
--
-- NAMED FOR ITS GRAIN, NOT FOR A PAGE. This replaces srv_schedule and srv_scoreboard, which
-- were one row per game over fct_game apiece — the same grain over the same fact, split by
-- which page read them.
--
-- THE COST OF THAT SPLIT WAS ALREADY PAID. srv_scoreboard took team display names off
-- dim_team, which is season-scoped and does not list every Division II visitor an FBS side
-- schedules; 12,168 of 110,634 rows rendered an em dash for the team and the string "None"
-- for the winner. srv_schedule took the same name off fct_game and had zero nulls. One
-- column, two implementations, one of them shipped broken. The fix went into srv_scoreboard's
-- header rather than into the thing that made two implementations possible.
--
-- MEASURED WHILE MERGING, and it is the same shape a second time: `home_rank` had two
-- implementations too. srv_schedule read g.home_rank off fct_game; srv_scoreboard rebuilt it
-- with its own ap_rank CTE over fct_poll_rank. fct_game ALREADY joins fct_poll_rank for the
-- AP Top 25 — the CTE was re-deriving what the spine hands it. They agreed exactly (11,982
-- populated on both, zero disagreements across 110,879 games), which is precisely the state
-- the team name was in before it drifted. The CTE is dropped and the spine's column kept.
--
-- THE GRAIN RULE (Marc, ratified 2026-09-02): "Can't add game.team grain to a table that is
-- at game grain." Anything finer than one row per game arrives as its own view — see
-- srv_game_team — or as a DERIVED summary computed in dbt and named so the derivation shows.
-- The box-score columns below are the second kind: sums across both teams, not team rows.

with latest_line as (

    -- THE MARKET IS A MART NOW (fct_game_market). This was the newest-snapshot ranking
    -- inline; the weekly distribution models need the same "current line" rule and cannot
    -- reach a serving view, so it moved down a layer rather than being copied into one.
    -- Aliased so every reference below reads exactly as it did.
    select game_id, spread_current as spread, total_current as over_under,
           spread_open, over_under_open, home_moneyline, away_moneyline,
           current_provider_key as provider_key, line_snapshot_ts as snapshot_ts
    from {{ ref('fct_game_market') }}

),

latest_market as (

    -- De-vigged market probabilities, from srv_matchup. R-094.
    select game_id, market_implied_home_win_probability,
           market_implied_away_win_probability, overround, devig_method
    from (
        select *, row_number() over (partition by game_id
                                     order by snapshot_ts desc, provider_key) as recency
        from {{ ref('fct_market_probability') }}
    ) r where recency = 1

),

latest_prediction as (

    -- Prefer a model that populates predicted_margin: six of seven models are probability
    -- models, so ordering by recency alone loses the margin almost every time.
    select game_id, model_name, model_version, model_family, predicted_margin,
           predicted_total_points, predicted_home_points, predicted_away_points,
           predicted_home_win_probability, home_cover_edge, home_win_probability_edge,
           confidence_bucket, is_out_of_sample_week
    from (
        select p.*, row_number() over (
                   partition by p.game_id
                   order by case when p.predicted_margin is not null then 0 else 1 end,
                            p.prediction_ts desc, p.model_version desc) as recency
        from {{ ref('fct_prediction') }} p
    ) r where recency = 1

),

game_box as (

    -- Game-grain totals derived from the team-grain box score. A DERIVED summary, which the
    -- grain rule permits; the team rows themselves live in srv_game_team.
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

-- THE CLOSING LINE IS A MART NOW (fct_game_market), NOT TWO CTEs HERE.
--
-- It was extracted when the weekly distribution models needed the same rule and could not
-- reach a serving view — marts cannot read serving. Copying it down a layer would have made
-- three implementations of one definition. The reasoning that used to live here (why the
-- spread and the total rank separately, why `basis` travels with each number) moved with it.
--
-- Aliased to `pk` / `pkt` so every reference below reads exactly as it did.
pre_kick as (
    select game_id, spread_at_close as spread, spread_at_close_provider as provider_key,
           spread_at_close_ts as snapshot_ts, spread_at_close_basis as basis
    from {{ ref('fct_game_market') }}
    -- NO `where spread_at_close is not null`. The original ranked EVERY betting-line row and
    -- took the top one, whose spread may be null — so six games carry a provider and a basis
    -- for a spread that does not exist. Filtering them out here changed six rows, which the
    -- before/after comparison caught. That is a behaviour change, and an extraction is not
    -- the place to make one. Flagged separately: a provider for a number we do not hold is
    -- arguably noise, but removing it is a decision rather than a tidy-up.
),

pre_kick_total as (
    select game_id, total_at_close as over_under, total_at_close_provider as provider_key,
           total_at_close_ts as snapshot_ts, total_at_close_basis as basis
    from {{ ref('fct_game_market') }}
    -- The total's own ranking DID filter `over_under is not null` in the original (R-142), and
    -- that filter lives in the mart now, so nothing more is needed here.
),

-- R-079 IS A MART, NOT A CTE HERE. The first version of this view held the "latest snapshot
-- at or before kickoff" selection inline and read stg_game_pregame_wp directly.
-- ci/check_layering.py failed the build for it and was right to: serving builds on marts.
-- Choosing which snapshot represents a game is a business rule, and a business rule inside a
-- view is one a second consumer has to re-derive — which is the defect this whole prompt is
-- about. It lives in fct_game_pregame_wp and is joined below.

series as (
    -- Head-to-head, from the game spine.
    --
    -- Written as a UNION of two equality joins rather than one join with an OR across both
    -- team-pair orderings. The OR form is the obvious way to express it and is a trap:
    -- Postgres cannot hash-join a disjunction, so it degrades to a nested loop over 110,634
    -- games against itself. That built acceptably until fct_game gained four columns, then
    -- ran past 11 minutes without finishing. Same result, and it hash-joins.
    --
    -- A TIE IS ITS OWN OUTCOME and is counted as one. The first version derived the away
    -- record as `series_games - series_home_team_wins`, which is only correct in a sport
    -- without draws: every tie was silently credited to the away team. College football
    -- had no overtime before 1996 and there are 2,600 tied games on record, which
    -- overstated the away side in 40,045 of 102,985 matchup rows — a plausible-looking
    -- number, wrong, and impossible to spot on screen because a head-to-head record is
    -- exactly the figure nobody arrives already knowing.
    select
        game_id,
        count(*)                                as series_games,
        sum(home_team_won)                      as series_home_team_wins,
        sum(away_team_won)                      as series_away_team_wins,
        sum(was_tied)                           as series_ties,
        min(prior_season)                       as series_first_season,
        max(prior_season)                       as series_last_season
    from (
        select
            cur.game_id,
            prior.season as prior_season,
            case when prior.home_team_id = cur.home_team_id
                      and prior.home_points > prior.away_points then 1
                 when prior.away_team_id = cur.home_team_id
                      and prior.away_points > prior.home_points then 1
                 else 0 end as home_team_won,
            case when prior.home_team_id = cur.away_team_id
                      and prior.home_points > prior.away_points then 1
                 when prior.away_team_id = cur.away_team_id
                      and prior.away_points > prior.home_points then 1
                 else 0 end as away_team_won,
            case when prior.home_points = prior.away_points then 1 else 0 end as was_tied
        from {{ ref('fct_game') }} cur
        join {{ ref('fct_game') }} prior
          on prior.home_team_id = cur.home_team_id
         and prior.away_team_id = cur.away_team_id
         and prior.game_id <> cur.game_id
        -- A RESULT, not merely a completed flag. Two games are marked completed with
        -- no score recorded, and counting them as meetings gave a head-to-head record
        -- of 0-0-0 over one meeting — a row that reconciles to nothing and reads as a
        -- rendering fault. A meeting with no result contributes no result.
        where prior.is_completed
          and prior.home_points is not null
          and prior.away_points is not null

        union all

        select
            cur.game_id,
            prior.season,
            case when prior.home_team_id = cur.home_team_id
                      and prior.home_points > prior.away_points then 1
                 when prior.away_team_id = cur.home_team_id
                      and prior.away_points > prior.home_points then 1
                 else 0 end,
            case when prior.home_team_id = cur.away_team_id
                      and prior.home_points > prior.away_points then 1
                 when prior.away_team_id = cur.away_team_id
                      and prior.away_points > prior.home_points then 1
                 else 0 end,
            case when prior.home_points = prior.away_points then 1 else 0 end
        from {{ ref('fct_game') }} cur
        join {{ ref('fct_game') }} prior
          on prior.home_team_id = cur.away_team_id
         and prior.away_team_id = cur.home_team_id
         and prior.game_id <> cur.game_id
        -- A RESULT, not merely a completed flag. Two games are marked completed with
        -- no score recorded, and counting them as meetings gave a head-to-head record
        -- of 0-0-0 over one meeting — a row that reconciles to nothing and reads as a
        -- rendering fault. A meeting with no result contributes no result.
        where prior.is_completed
          and prior.home_points is not null
          and prior.away_points is not null
    ) meetings
    group by game_id
),

current_week as (

    -- C4. THE CURRENT-WEEK RULE IS BUSINESS LOGIC AND IT MOVES HERE, NOT INTO THE PAGE.
    --
    -- srv_today_edges filtered to it. A slate spans Thursday to Saturday, so a calendar-date
    -- filter shows an empty page on Wednesday — which is why "today" is the current CFBD week
    -- and not today's date.
    --
    -- `not is_completed` ALONE IS NOT SUFFICIENT and picking it selected 2023 week 6 on the
    -- first build: twelve historical games are permanently flagged incomplete because they
    -- were cancelled and CFBD never marks them otherwise, so the earliest incomplete game is
    -- three seasons in the past. Anchoring on KICKOFF TIME makes those rows irrelevant
    -- instead of authoritative.
    --
    -- As a column rather than a WHERE clause in Streamlit: a definition that lives in a page
    -- is a definition the next page gets wrong, and this one has already been got wrong once.
    select season, season_type, week
    from {{ ref('fct_game') }}
    where start_date >= {{ dbt.current_timestamp() }}
    group by season, season_type, week
    order by min(start_date)
    limit 1

)

select
    g.game_sk,
    g.game_id,
    g.season,
    g.week,
    g.season_type,
    g.week_sk,
    g.game_date,
    g.start_date,
    -- AC-G.34: the display zone is applied here, never in the app.
    {{ to_local_timestamp('g.start_date') }} as start_date_et,
    g.kickoff_time_known,
    g.is_completed,
    g.is_conference_game,
    g.is_neutral_site,
    g.venue,
    -- Both spellings kept: srv_schedule exposed only venue_display and srv_scoreboard both,
    -- and the rename is not the place to drop a column somebody reads.
    g.venue                       as venue_display,
    g.network,
    -- R-080: short form from dim_broadcast_outlet, so the site and the workbook agree.
    g.network_abbreviation,
    g.attendance,
    g.excitement_index,
    g.is_upset,

    -- FBS SPINE. EITHER team, not both: a Division II visitor's trip to an FBS stadium is an
    -- FBS game, and requiring both would drop 20 of the 25 games on the opening Thursday.
    (g.home_classification = 'fbs' or g.away_classification = 'fbs') as is_fbs_game,

    g.home_team_id,
    -- The name comes from the GAME. dim_team is built from /teams and does not list every
    -- opponent an FBS side schedules; the slug falls back to a slug OF that name, because a
    -- null slug is a link to nowhere while a derived one reaches a page that renders Empty.
    g.home_team,
    {{ team_identity('h', 'g.home_team', 'home_') }},
    h.abbreviation                as home_abbreviation,
    h.conference                  as home_conference,
    h.color_on_light              as home_color_on_light,
    h.color_on_dark               as home_color_on_dark,
    h.logo_source_url             as home_logo_url,
    g.home_points,
    -- From the spine, which already joins fct_poll_rank for the AP Top 25. See the header.
    g.home_rank,

    g.away_team_id,
    g.away_team,
    {{ team_identity('a', 'g.away_team', 'away_') }},
    a.abbreviation                as away_abbreviation,
    a.conference                  as away_conference,
    a.color_on_light              as away_color_on_light,
    a.color_on_dark               as away_color_on_dark,
    a.logo_source_url             as away_logo_url,
    g.away_points,
    g.away_rank,

    -- Result, computed once so no page subtracts two numbers to find a winner.
    case
        when not g.is_completed then null
        when g.home_points > g.away_points then g.home_team
        when g.away_points > g.home_points then g.away_team
        else null
    end                                                    as winner,
    -- NULL, not zero, for a game with no result — so zero here means exactly one thing: the
    -- two teams finished level.
    case when g.is_completed and g.home_points is not null and g.away_points is not null
         then abs(g.home_points - g.away_points) end       as final_margin,
    g.away_points - g.home_points as actual_margin,   -- away minus home, per the convention
    case when g.is_completed and g.home_points is not null and g.away_points is not null
         then g.home_points + g.away_points end            as total_points,

    hr.wins as home_wins, hr.losses as home_losses,
    ar.wins as away_wins, ar.losses as away_losses,

    bx.total_yards_both_teams,
    bx.rushing_yards_both_teams,
    bx.passing_yards_both_teams,
    bx.turnovers_both_teams,
    -- 2 when both box scores landed, 1 when only one did, 0 when neither. A total built from
    -- one team is not a game total, and this is what lets a page say so.
    bx.teams_with_box_score,

    l.spread                      as spread_current,
    l.over_under                  as total_current,
    pk.spread                     as spread_at_close,
    pk.provider_key               as spread_at_close_provider,
    pk.basis                      as spread_at_close_basis,
    pkt.over_under                as total_at_close,
    pkt.provider_key              as total_at_close_provider,
    pkt.basis                     as total_at_close_basis,

    -- R-200/R-204. WHAT THE MARKET'S OWN TWO NUMBERS SAY THE SCORE SHOULD BE.
    --
    -- `market_implied_`, not `line_implied_` or `expected_`: the prefix names the PROVENANCE,
    -- and this family already exists (`market_implied_home_win_probability`). These are
    -- arithmetic on published numbers, so they carry CFBD attribution and NOT the model
    -- disclaimer — which is the whole reason the prefix is a licence boundary wearing a
    -- naming convention. `points`, not `score`, to line up with `predicted_home_points` and
    -- the actual `home_points` in a column list.
    --
    -- NO BRANCHING, AND THE SIGN DOES THE WORK. The spread is home-perspective and negative
    -- favours home, so subtracting it adds to the home side. Verified on all 1,930 FBS games
    -- with a line: implied_home + implied_away = total on every row, and greatest/least of
    -- the pair equals the abs() form on every row. Marc's instinct that this needed a
    -- home/away case statement was reasonable and turns out to be unnecessary.
    --
    -- Locked with the same rule as everything else here: the closing number once it exists,
    -- the live one before that.
    (coalesce(pkt.over_under, l.over_under) - coalesce(pk.spread, l.spread)) / 2.0
                                  as market_implied_home_points,
    (coalesce(pkt.over_under, l.over_under) + coalesce(pk.spread, l.spread)) / 2.0
                                  as market_implied_away_points,
    -- greatest/least rather than a second case statement, so the favourite/underdog rule
    -- exists in exactly ONE place and the distribution model derives from these rather than
    -- re-deriving the arithmetic.
    greatest(
        (coalesce(pkt.over_under, l.over_under) - coalesce(pk.spread, l.spread)) / 2.0,
        (coalesce(pkt.over_under, l.over_under) + coalesce(pk.spread, l.spread)) / 2.0)
                                  as market_implied_favorite_points,
    least(
        (coalesce(pkt.over_under, l.over_under) - coalesce(pk.spread, l.spread)) / 2.0,
        (coalesce(pkt.over_under, l.over_under) + coalesce(pk.spread, l.spread)) / 2.0)
                                  as market_implied_underdog_points,

    -- R-181. THE LINE IS THE ONLY BASIS. Marc, settling R-173's two-basis design one round
    -- after it shipped: "Determine upset based on who the line (spread) expects to win. Upset
    -- is not determined by ranking. There are only 25-ish teams ranked. Most FBS games have
    -- lines, so lines is the better option (by far)."
    --
    -- MEASURED, BECAUSE HIS PREMISE IS ABOUT COVERAGE AND OURS IS NOT HIS:
    --     FBS 2025          934 of 934 completed games carry a closing line   100%
    --     FBS 2024+       1,840 of 1,861                                       98.9%
    --     every completed  3,201 of 109,108                                     2.9%
    -- The last figure is pre-2024 history and lower divisions, where we hold no line AND
    -- usually no rank either. So dropping the rank fallback costs 17,483 historical verdicts
    -- and nothing at all on the seasons anyone reads.
    --
    -- `upset_basis` IS GONE WITH IT. With one basis the column was always 'line' or null,
    -- which is `upset_level is not null` spelled a second way — and a column that carries no
    -- information is the "indicator that fires on everything" this project has removed before.
    --
    -- Convention, as everywhere else here: spread is the HOME number and negative means home
    -- favoured; margin is away minus home. A pick'em names no favourite, so it is not a basis.
    case
        when not g.is_completed or g.home_points is null then null
        when pk.spread is null or pk.spread = 0 then null
        -- Home was favoured and lost, or away was favoured and lost. A tie upsets nobody.
        when pk.spread < 0 and (g.away_points - g.home_points) > 0 then true
        when pk.spread > 0 and (g.away_points - g.home_points) < 0 then true
        else false
    end                                                    as is_upset_by_line,

    -- R-141, INDICATOR 1: the scale. The verdict above says whether; this says by how much.
    -- Boundaries are dbt vars because a metric definition does not belong in the app.
    --
    -- BY MARGIN OF VICTORY, NOT BY THE SIZE OF THE SWING. Marc called an 8-point favourite
    -- losing by 5 a Level 1 upset; the swing would make it 13 and Level 2.
    case
        when not g.is_completed or g.home_points is null then null
        when pk.spread is null or pk.spread = 0 then null
        when not (case when pk.spread < 0 then (g.away_points - g.home_points) > 0
                       else (g.away_points - g.home_points) < 0 end) then 'none'
        when abs(g.away_points - g.home_points) > {{ var('upset_margin_blowout') }}
            then 'blowout'
        when abs(g.away_points - g.home_points) > {{ var('upset_margin_big') }}
            then 'big'
        else 'upset'
    end                                                    as upset_level,

    -- R-141, INDICATOR 2: DID THE TEAM THAT WON ALSO COVER?
    --
    -- NOT `favorite_covered`, which is directly above and answers a different question. That
    -- one asks whether the market's pick was right; this one asks whether the winner beat the
    -- number. They disagree exactly when an underdog wins outright — the most interesting case
    -- on the page — so the two must never be conflated, hence the explicit name.
    --
    -- Convention, unchanged from favorite_covered: spread is the HOME number and margin is
    -- away minus home, so the home side covered when the margin came in below the spread.
    case
        when not g.is_completed or g.home_points is null then 'pending'
        when pk.spread is null then null
        when (g.away_points - g.home_points) = pk.spread then 'push'
        when g.home_points = g.away_points then 'push'
        when g.home_points > g.away_points
            then case when (g.away_points - g.home_points) < pk.spread then 'yes' else 'no' end
        else case when (g.away_points - g.home_points) > pk.spread then 'yes' else 'no' end
    end                                                    as winner_covered_close,

    -- R-141, INDICATOR 3: did the game go over the closing total. Push is a real state on a
    -- whole number, and pending is not the same as no line — the null-not-zero rule again.
    case
        when not g.is_completed or g.home_points is null then 'pending'
        when pkt.over_under is null then null
        when (g.home_points + g.away_points) = pkt.over_under then 'push'
        when (g.home_points + g.away_points) > pkt.over_under then 'yes'
        else 'no'
    end                                                    as over_met,

    -- WHETHER THE FAVOURITE COVERED — distinct from which side covered. Four states, and
    -- pending is not push. A pick'em has no favourite at all, which is a real case here.
    case
        when not g.is_completed or g.home_points is null then 'pending'
        when pk.spread is null then null
        when pk.spread = 0 then 'no_favorite'
        when (g.away_points - g.home_points) = pk.spread then 'push'
        when pk.spread < 0 and (g.away_points - g.home_points) < pk.spread then 'yes'
        when pk.spread > 0 and (g.away_points - g.home_points) > pk.spread then 'yes'
        else 'no'
    end                                                    as favorite_covered,

    p.predicted_margin,
    -1 * p.predicted_margin       as predicted_margin_home_perspective,
    p.predicted_home_win_probability as home_win_probability,
    p.predicted_home_win_probability,
    p.predicted_total_points,
    p.predicted_home_points,
    p.predicted_away_points,
    p.confidence_bucket,
    p.home_cover_edge,
    p.home_win_probability_edge,
    p.is_out_of_sample_week,
    -- C4-adjacent: the same rule srv_edge_finder uses, so no page re-derives it.
    case when p.is_out_of_sample_week then false else true end as is_default_actionable,
    {{ var('prediction_training_week_floor', 5) }} as training_week_floor,
    p.model_name,
    p.model_family,
    -- THE COLUMN NOW HOLDS WHAT ITS NAME SAYS. R-094, found by the C2 diff.
    --
    -- srv_game inherited `p.model_name as model_version_key` from srv_schedule; srv_matchup
    -- carried `mv.model_version`. The column is called model_version_key, so srv_matchup was
    -- right — and unlike home_rank in the 030 rename, these did not merely agree-and-risk-
    -- drifting: they disagreed on ALL 567 populated rows, one returning `random_forest_score`
    -- and the other `98d34949266b`.
    --
    -- Part 1 documented the quirk rather than renaming it, on the grounds that renaming a
    -- serving column is a breaking change. Merging the views IS that change, so this is the
    -- moment the objection stops applying. `model_name` is now its own column beside it.
    mv.model_version              as model_version_key,
    -- Licence requirement, carried as data so a page cannot render the model's numbers
    -- without it.
    mv.attribution,

    -- Market detail, from srv_matchup. R-094.
    l.spread,
    l.spread_open,
    l.over_under,
    l.over_under_open,

    -- R-104. HOW FAR THE MARKET HAS MOVED SINCE IT OPENED, computed here and not in the page.
    --
    -- spread_open and over_under_open are both already on this row, so `current - open` in
    -- Streamlit is one line away and forbidden: CLAUDE.md's rule is that a computation
    -- belongs upstream. Two columns in the view, not two subtractions in a page.
    --
    -- NAMED FOR WHAT THE SITE ALREADY CALLS IT. srv_line_movement ships
    -- `spread_move_from_open` and renders it as "Move". Coining "change" here would be the
    -- Total-versus-O/U mistake from R-087 committed a second time, three weeks after the rule
    -- about it was written.
    --
    -- SIGN CONVENTION, which is the trap on a page that shows two negative numbers. Spread is
    -- home-perspective and NEGATIVE FAVOURS THE HOME TEAM, so a move of -1.5 means the market
    -- moved TOWARD the home side. That is the same reading as the spread beside it and as
    -- predicted_margin two columns over; there is deliberately no second interpretation of a
    -- negative number on this row.
    --
    -- NULL, NOT ZERO, WHEN IT HAS NOT MOVED — and null again when there is no opening number
    -- to measure from. A column of 0.0 down an unmoved slate is noise that reads as data, and
    -- this is the null-not-zero rule the project has now applied to ats_record_display,
    -- total_points, final_margin, travel_km and line scores. The two nulls are different
    -- facts — "did not move" and "no open recorded" — and a consumer that needs to tell them
    -- apart has spread_open beside it.
    case when l.spread is not null and l.spread_open is not null
              and l.spread <> l.spread_open
         then l.spread - l.spread_open end        as spread_move_from_open,
    case when l.over_under is not null and l.over_under_open is not null
              and l.over_under <> l.over_under_open
         then l.over_under - l.over_under_open end as total_move_from_open,

    -- R-108b. The better of the two poll ranks, for the stacked view's sort.
    --
    -- least() ignores nulls in both dialects, so an unranked opponent does not erase a ranked
    -- team's number: least(4, null) is 4. Both unranked gives NULL, which is correct — the
    -- game has no rank, rather than a rank of nothing.
    --
    -- RANK 1 IS THE BEST RANK AND UNRANKED IS NULL, so a consumer sorting on this MUST put
    -- nulls last or every unranked game leads the page. The column stays honestly null rather
    -- than coalescing to 999: a sentinel would sort correctly and lie in every other context,
    -- including the Excel export.
    least(g.home_rank, g.away_rank)               as best_rank_in_game,

    l.home_moneyline,
    l.away_moneyline,
    l.provider_key,
    l.snapshot_ts                 as line_snapshot_ts,
    l.snapshot_ts,
    mk.market_implied_home_win_probability,
    mk.market_implied_away_win_probability,
    mk.overround,
    mk.devig_method,

    -- Division of each side that season, from the game spine.
    g.home_classification,
    g.away_classification,

    -- The same result read the other way round, so a page can put it beside
    -- predicted_margin_home_perspective without flipping a sign itself.
    g.home_points - g.away_points as actual_margin_home_perspective,

    -- HEAD TO HEAD AS IT STOOD BEFORE THIS GAME, from srv_matchup. Distinct from
    -- fct_team_series, which is the all-time record per unordered pair: this is per-game and
    -- excludes the fixture on its own row.
    ser.series_games,
    ser.series_home_team_wins,
    ser.series_away_team_wins,
    ser.series_ties,
    ser.series_first_season,
    ser.series_last_season,

    -- C4. Whether this game is in the week currently in play. A COLUMN, not a WHERE clause
    -- in the app: the Today page filters on a fact rather than re-deriving the definition.
    cw.season is not null          as is_current_week,

    -- R-079. Pregame win probability, with the provenance of WHEN it was taken. Read
    -- pregame_wp_basis before quoting it: `as_recorded_by_cfbd` means the figure is real but
    -- was fetched after the game, which is not the same claim as a forecast.
    wp.home_win_probability       as pregame_home_win_probability,
    wp.basis                      as pregame_wp_basis,
    wp.snapshot_ts                as pregame_wp_snapshot_ts,

    -- R-078. Weather at the venue. Landed for 2024 onward only, so null for most of history —
    -- that renders as an em dash and is the honest state, not a defect.
    --
    -- is_indoors QUALIFIES EVERY OTHER WEATHER COLUMN. CFBD reports conditions at the
    -- venue's LOCATION, not inside it, so a domed game carries ordinary outdoor readings.
    -- Rendering "Rain, 41F" for a game played under a roof states something false.
    w.is_indoors,
    w.temperature_f,
    w.wind_speed_mph,
    w.precipitation_in,
    w.weather_condition_code,
    w.weather_condition,

    -- R-083. Per-game Elo, which is a per-WEEK Elo. No API call was needed; the games spine
    -- has carried this all along. Populated on 67,306 of 110,879 rows.
    g.home_pregame_elo,
    g.home_postgame_elo,
    g.away_pregame_elo,
    g.away_postgame_elo,

    -- R-082. Quarters, typed. Four columns plus an overtime SUM, because periods reach
    -- thirteen in this data and a column per period would either invent nine or truncate a
    -- triple-OT game. `periods` says how many there were so a page can render "2OT" honestly.
    -- Present from 2001; null before that, and null for the 60% of rows CFBD sends empty.
    g.home_q1, g.home_q2, g.home_q3, g.home_q4,
    g.home_overtime_points, g.home_periods,
    g.away_q1, g.away_q2, g.away_q3, g.away_q4,
    g.away_overtime_points, g.away_periods,

    -- R-084. THE RECORD AS IT STOOD GOING INTO THIS GAME'S WEEK.
    --
    -- NOT the same thing as home_wins / home_losses above, which are the SEASON-FINAL record
    -- from fct_team_record and are kept only because the merge drops nothing. Putting the
    -- season-final record beside a Week 3 game from a finished season is the composition
    -- failure this column exists to prevent, so a page showing a record on a game row must
    -- read these two and not those.
    --
    -- Named home_team_record_display, NOT home_record_display: srv_standings already uses
    -- that name for "record in home games", which is a different statement entirely. The
    -- collision was avoided deliberately.
    rw_home.current_record        as home_team_record_display,
    rw_away.current_record        as away_team_record_display,
    -- R-140. The record the game LEFT them with. Null for a game not yet played, which is what
    -- lets the page show the leading-into figure before kickoff and this one after.
    case when g.is_completed then rw_home.record_after end as home_team_record_after_display,
    case when g.is_completed then rw_away.record_after end as away_team_record_after_display,

    ao.as_of_ts
from {{ ref('fct_game') }} g
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
left join {{ ref('fct_team_record') }} hr on hr.season = g.season and hr.team_id = g.home_team_id
left join {{ ref('fct_team_record') }} ar on ar.season = g.season and ar.team_id = g.away_team_id
left join latest_line l on l.game_id = g.game_id
left join latest_prediction p on p.game_id = g.game_id
left join game_box bx on bx.game_id = g.game_id
left join pre_kick pk on pk.game_id = g.game_id
left join latest_market mk on mk.game_id = g.game_id
left join series ser on ser.game_id = g.game_id
left join {{ ref('dim_model_version') }} mv
    on mv.model_name = p.model_name and mv.model_version = p.model_version
-- One row at most; a cross join would multiply every game by it when the week resolves.
left join current_week cw
    on  cw.season = g.season and cw.season_type = g.season_type and cw.week = g.week
left join {{ ref('fct_game_pregame_wp') }} wp on wp.game_id = g.game_id
left join {{ ref('fct_game_weather') }} w on w.game_id = g.game_id
-- Record LEADING INTO this game's week, per side. Joined on the full grain including
-- season_type, because postseason week numbers restart at 1 and joining on week alone would
-- put a bowl game's record on an October fixture.
left join pre_kick_total pkt on pkt.game_id = g.game_id
left join {{ ref('fct_team_record_week') }} rw_home
    on  rw_home.season = g.season and rw_home.season_type = g.season_type
    and rw_home.week = g.week and rw_home.team_id = g.home_team_id
left join {{ ref('fct_team_record_week') }} rw_away
    on  rw_away.season = g.season and rw_away.season_type = g.season_type
    and rw_away.week = g.week and rw_away.team_id = g.away_team_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
