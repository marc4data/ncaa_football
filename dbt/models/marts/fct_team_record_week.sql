{{ config(materialized='table') }}

-- Record LEADING INTO each week. One row per (season, season_type, week, team). R-084.
--
-- Specified by Marc, 2026-09-02: "walk over each week in each season and accumulate the
-- record leading into the next week. Do a running sum of wins and losses, then build a string
-- column for current_record as W-L."
--
-- WHY IT HAS TO EXIST. fct_team_record is SEASON grain. Rendering it beside a Week 3 game
-- from a finished season shows the season-final record next to a game played in September —
-- the composition failure AC-G.33 exists to prevent, and the reason srv_game carries this
-- rather than the season record.
--
-- THE OFF-BY-ONE IS THE ENTIRE POINT OF THE COLUMN. The row for week N is cumulative over
-- completed games in weeks strictly BEFORE N. The window frame below ends at `1 preceding`,
-- not `current row`, and that single word is the difference between a correct column and one
-- that looks right on every row except the ones anyone checks. A Week 5 game must not show a
-- record containing the Week 5 result.
--
-- WALK THE CALENDAR, NOT THE GAMES. The spine is every week in the season crossed with every
-- team in that season, then results are LEFT joined onto it. A team does not play every week;
-- building from its games would produce no row for a bye, and a Schedule page filtered to
-- that week would render an empty record rather than the record carried forward.
--
-- ORDER BY SEASON TYPE, THEN WEEK — never week alone. Postseason week numbers restart at 1,
-- so ordering on week would put a bowl game in the middle of October. The ordinal is derived
-- from the data's own chronology: within season 2020, regular runs Aug-Dec 2020, postseason
-- opens 2020-12-21, and the COVID spring season runs Feb-May 2021. Four season types exist in
-- this warehouse, not two.
--
-- ONLY COMPLETED GAMES ACCUMULATE. An unplayed or postponed game contributes nothing, the
-- same rule that makes total_points null rather than zero.
--
-- 0-0 IS NOT THE SAME AS UNKNOWN. Week 1 is legitimately 0-0: no games have been played yet.
-- But a team with NO completed game anywhere in the season — a Division II side in the spine
-- because it appears on a schedule, with no result in the warehouse — gets NULL. Marc's rule:
-- 0-0 there is a lie. `has_completed_games` says which case a null is.

-- THE SPINE IS SHARED, NOT REBUILT. It was inline here until fct_team_rating_week needed
-- exactly the same thing; it now lives in dim_team_week and both models build on it. A second
-- spine that drifts from the first is this project's signature defect, and prompt 030 spent
-- itself removing two instances of it — adding a third would have been an odd way to finish.
with spine as (

    select * from {{ ref('dim_team_week') }}

),

-- One row per team per completed game, from both sides of the fixture.
team_games as (

    select season, season_type, week, home_team_id as team_id,
           case when home_points > away_points then 1 else 0 end as win,
           case when home_points < away_points then 1 else 0 end as loss,
           case when home_points = away_points then 1 else 0 end as tie
    from {{ ref('fct_game') }}
    where is_completed and home_points is not null and away_points is not null
      and home_team_id is not null

    union all

    select season, season_type, week, away_team_id,
           case when away_points > home_points then 1 else 0 end,
           case when away_points < home_points then 1 else 0 end,
           case when away_points = home_points then 1 else 0 end
    from {{ ref('fct_game') }}
    where is_completed and home_points is not null and away_points is not null
      and away_team_id is not null

),

per_week as (

    select season, season_type, week, team_id,
           sum(win) as wins, sum(loss) as losses, sum(tie) as ties
    from team_games
    group by season, season_type, week, team_id

),

-- R-127. EVERY FIXTURE, COMPLETED OR NOT, because "has not played yet" and "we hold no
-- results for this team" are different facts and the old guard could not tell them apart.
team_fixtures as (

    select season, season_type, week, home_team_id as team_id
    from {{ ref('fct_game') }} where home_team_id is not null

    union all

    select season, season_type, week, away_team_id
    from {{ ref('fct_game') }} where away_team_id is not null

),

per_week_fixtures as (

    select season, season_type, week, team_id, count(*) as fixtures
    from team_fixtures
    group by season, season_type, week, team_id

),

joined as (

    select
        s.season, s.season_type, s.week, s.team_id, s.season_type_ordinal,
        coalesce(w.wins, 0)   as week_wins,
        coalesce(w.losses, 0) as week_losses,
        coalesce(w.ties, 0)   as week_ties,
        coalesce(f.fixtures, 0) as week_fixtures,
        -- Whether cfdb holds this team's WHOLE schedule. That is the fact separating an FBS
        -- side yet to open its season from a Division II side in the spine only because it
        -- appears on somebody else's.
        coalesce(t.is_fbs, false) as is_fbs
    from spine s
    left join per_week w
        on  w.season      = s.season
        and w.season_type = s.season_type
        and w.week        = s.week
        and w.team_id     = s.team_id
    left join per_week_fixtures f
        on  f.season      = s.season
        and f.season_type = s.season_type
        and f.week        = s.week
        and f.team_id     = s.team_id
    left join {{ ref('dim_team') }} t
        on  t.season  = s.season
        and t.team_id = s.team_id

),

running as (

    select
        j.*,
        -- `1 preceding`, NOT `current row`. See the header: this is the off-by-one the
        -- column exists to get right.
        sum(week_wins) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and 1 preceding)   as wins_before,
        sum(week_losses) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and 1 preceding)   as losses_before,
        sum(week_ties) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and 1 preceding)   as ties_before,
        -- Does this team have ANY result in the warehouse this season? Distinguishes a
        -- legitimate 0-0 at week 1 from a team we simply hold no results for.
        sum(week_wins + week_losses + week_ties) over (
            partition by season, team_id)                        as season_games,
        -- Same frame as the record itself: has this team taken the field yet this season?
        sum(week_fixtures) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and 1 preceding)    as fixtures_before
    from joined j

),

gated as (

    select r.*,
           (season_games > 0
            or (coalesce(fixtures_before, 0) = 0 and is_fbs)) as record_is_known
    from running r

),

final as (

    select
        season, season_type, week, team_id, season_type_ordinal,
        season_games > 0                     as has_completed_games,
        -- R-127. THE GUARD USED TO BE `season_games > 0`, WHICH ASKS ABOUT THE FUTURE.
        --
        -- `season_games` is a window over the WHOLE season partition, so at week 1 of a
        -- season only eight games into itself it was true only for teams that had ALREADY
        -- played. The page showed "0-0" beside Arkansas-Pine Bluff, which opened on 29
        -- August, and NOTHING beside Missouri, Oklahoma and UTEP, which had not opened yet —
        -- precisely backwards, and invisible mid-season because by then everyone qualifies.
        --
        -- Marc's rule stands; this states it properly. 0-0 is a lie for a team whose results
        -- we do not hold and the TRUTH for a team that has not played yet. Three ways to
        -- qualify, and the third is the one that was missing:
        --
        --   season_games > 0     we hold results for this team this season
        --   fixtures_before = 0  it has not taken the field yet, so 0-0 is definitional
        --   is_fbs               ...but only where we hold the whole schedule, or the
        --                        Division II stub gets 0-0 before its single fixture, which
        --                        is exactly the lie the original guard existed to prevent
        record_is_known,
        case when record_is_known then coalesce(wins_before, 0) end   as wins,
        case when record_is_known then coalesce(losses_before, 0) end as losses,
        case when record_is_known then coalesce(ties_before, 0) end   as ties
    from gated

)

select
    {{ surrogate_key(['season', 'season_type', 'week', 'team_id']) }} as team_record_week_sk,
    season,
    season_type,
    season_type_ordinal,
    week,
    team_id,
    has_completed_games,
    record_is_known,
    wins,
    losses,
    ties,
    -- W-L, extending to W-L-T only when the running tie count is non-zero. Ties existed
    -- before 1996 and a two-part string MISSTATES those seasons; a three-part string on a
    -- modern season would be equally wrong in the other direction.
    --
    -- NULL where the record is not KNOWN — R-127, and this line had the same defect as the
    -- numeric columns above it. `has_completed_games` is a true statement about results held;
    -- it is not the question "do we know this team's record leading into this week", and
    -- gating the display string on it left Missouri blank beside Arkansas-Pine Bluff's 0-0.
    --
    -- The numeric columns beside it are what a page should compute from — nothing should ever
    -- parse this string.
    case
        when not record_is_known then null
        when ties > 0 then cast(wins as {{ dbt.type_string() }}) || '-'
                        || cast(losses as {{ dbt.type_string() }}) || '-'
                        || cast(ties as {{ dbt.type_string() }})
        else cast(wins as {{ dbt.type_string() }}) || '-'
          || cast(losses as {{ dbt.type_string() }})
    end                                                              as current_record
from final
