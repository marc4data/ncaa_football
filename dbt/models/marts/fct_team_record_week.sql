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

    -- R-620. `venue` IS WHERE THIS TEAM PLAYED, AND A NEUTRAL GAME IS NEITHER.
    --
    -- ⚠️ THE DECISION IS CARRIED IN THE DATA RATHER THAN ONLY IN THIS COMMENT, which is why
    -- there are three splits below and not two. A neutral game is not played at the team's own
    -- venue and it is not played at the opponent's, so folding it into either would overstate
    -- that side's record — and 130 of 2025's 3,831 completed games are neutral, which is
    -- enough that the choice shows on screen. Home + away + neutral sums to the total, so the
    -- decision is auditable from the columns instead of taken on trust.
    --
    -- The FIXTURE's home_team_id still names the nominal host of a neutral game; that is how
    -- the feed models a bowl. It is deliberately not read as a home game here.
    select season, season_type, week, home_team_id as team_id,
           case when is_neutral_site then 'neutral' else 'home' end as venue,
           case when home_points > away_points then 1 else 0 end as win,
           case when home_points < away_points then 1 else 0 end as loss,
           case when home_points = away_points then 1 else 0 end as tie
    from {{ ref('fct_game') }}
    where is_completed and home_points is not null and away_points is not null
      and home_team_id is not null

    union all

    select season, season_type, week, away_team_id,
           case when is_neutral_site then 'neutral' else 'away' end,
           case when away_points > home_points then 1 else 0 end,
           case when away_points < home_points then 1 else 0 end,
           case when away_points = home_points then 1 else 0 end
    from {{ ref('fct_game') }}
    where is_completed and home_points is not null and away_points is not null
      and away_team_id is not null

),

per_week as (

    select season, season_type, week, team_id,
           sum(win) as wins, sum(loss) as losses, sum(tie) as ties,
           -- R-620. The same three counts once per venue, plus how many games each venue
           -- accounts for — the game count is what tells a NULL away record ("no away games
           -- yet") apart from a real 0-0.
           sum(case when venue = 'home' then win else 0 end)     as home_wins,
           sum(case when venue = 'home' then loss else 0 end)    as home_losses,
           sum(case when venue = 'home' then tie else 0 end)     as home_ties,
           sum(case when venue = 'home' then 1 else 0 end)       as home_games,
           sum(case when venue = 'away' then win else 0 end)     as away_wins,
           sum(case when venue = 'away' then loss else 0 end)    as away_losses,
           sum(case when venue = 'away' then tie else 0 end)     as away_ties,
           sum(case when venue = 'away' then 1 else 0 end)       as away_games,
           sum(case when venue = 'neutral' then win else 0 end)  as neutral_wins,
           sum(case when venue = 'neutral' then loss else 0 end) as neutral_losses,
           sum(case when venue = 'neutral' then tie else 0 end)  as neutral_ties,
           sum(case when venue = 'neutral' then 1 else 0 end)    as neutral_games
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
        coalesce(w.home_wins, 0) as week_home_wins,
        coalesce(w.home_losses, 0) as week_home_losses,
        coalesce(w.home_ties, 0) as week_home_ties,
        coalesce(w.home_games, 0) as week_home_games,
        coalesce(w.away_wins, 0) as week_away_wins,
        coalesce(w.away_losses, 0) as week_away_losses,
        coalesce(w.away_ties, 0) as week_away_ties,
        coalesce(w.away_games, 0) as week_away_games,
        coalesce(w.neutral_wins, 0) as week_neutral_wins,
        coalesce(w.neutral_losses, 0) as week_neutral_losses,
        coalesce(w.neutral_ties, 0) as week_neutral_ties,
        coalesce(w.neutral_games, 0) as week_neutral_games,
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
        -- R-140. THE SAME WINDOW, `current row` INSTEAD OF `1 preceding`.
        --
        -- That one word is the whole difference between "going into this week" and "after it",
        -- and it is exactly the off-by-one the negative test on current_record flips. A page
        -- showing a completed game wants the record the game produced; a page showing a
        -- scheduled one wants the record the teams carry into it. Both, from one model.
        sum(week_wins) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and current row)   as wins_after,
        sum(week_losses) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and current row)   as losses_after,
        sum(week_ties) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and current row)   as ties_after,
        -- ⚠️ R-620. THE SPLITS USE THE SAME `1 preceding` FRAME, AND THAT IS NOT OPTIONAL.
        -- A preview must not show a record containing the game being previewed — the same
        -- leakage rule Marc stated for yardage: "can only include data through Week 4 in a
        -- Week 5 game". Reusing this model rather than coining a second one is what makes the
        -- off-by-one right by construction instead of by a second author remembering it.
        {% for venue in ['home', 'away', 'neutral'] %}
        sum(week_{{ venue }}_wins) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and 1 preceding) as {{ venue }}_wins_before,
        sum(week_{{ venue }}_losses) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and 1 preceding) as {{ venue }}_losses_before,
        sum(week_{{ venue }}_ties) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and 1 preceding) as {{ venue }}_ties_before,
        -- How many games at this venue have already been played. This is the column that
        -- separates "no away games yet" (NULL) from a genuine 0-0, per AC-G.32.
        sum(week_{{ venue }}_games) over (
            partition by season, team_id order by season_type_ordinal, week
            rows between unbounded preceding and 1 preceding) as {{ venue }}_games_before,
        {% endfor %}
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

    -- Both flags are computed HERE rather than in the select list below, because Postgres
    -- cannot reference a select alias from a sibling expression in the same select.
    select r.*,
           season_games > 0                                   as has_completed_games,
           (season_games > 0
            or (coalesce(fixtures_before, 0) = 0 and is_fbs)) as record_is_known
    from running r

),

final as (

    select
        season, season_type, week, team_id, season_type_ordinal,
        has_completed_games,
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
        case when record_is_known then coalesce(ties_before, 0) end   as ties,
        -- R-140. Gated on results HELD rather than on record_is_known: "after the game" is a
        -- statement about a game that was played, so unlike the leading-into figure there is
        -- no case where the answer is a definitional zero.
        case when has_completed_games then coalesce(wins_after, 0) end   as wins_after,
        case when has_completed_games then coalesce(losses_after, 0) end as losses_after,
        case when has_completed_games then coalesce(ties_after, 0) end   as ties_after,
        -- ⚠️ R-620. GATED ON GAMES AT THAT VENUE, NOT ON `record_is_known`, AND THE
        -- DIFFERENCE IS THE POINT. A team five weeks into a season that has played only at
        -- home has a KNOWN record and NO AWAY RECORD. 0-0 there would be a measurement where
        -- there is none — AC-G.32, and the same rule that makes total_points null rather than
        -- zero. B082's header omits cleanly on null, so the absence costs nothing on screen.
        {% for venue in ['home', 'away', 'neutral'] %}
        coalesce({{ venue }}_games_before, 0) as {{ venue }}_games,
        case when coalesce({{ venue }}_games_before, 0) > 0
             then {{ venue }}_wins_before end   as {{ venue }}_wins,
        case when coalesce({{ venue }}_games_before, 0) > 0
             then {{ venue }}_losses_before end as {{ venue }}_losses,
        case when coalesce({{ venue }}_games_before, 0) > 0
             then {{ venue }}_ties_before end   as {{ venue }}_ties{{ "," if not loop.last }}
        {% endfor %}
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
    wins_after,
    losses_after,
    ties_after,
    {% for venue in ['home', 'away', 'neutral'] %}
    {{ venue }}_games,
    {{ venue }}_wins,
    {{ venue }}_losses,
    {{ venue }}_ties,
    -- R-620. The same W-L / W-L-T rule as `current_record`, per venue. NULL where the team
    -- has not played at that venue yet — see the gate in `final`. Nothing should ever parse
    -- this string; the three numerics above it are what a page computes from.
    case
        when {{ venue }}_wins is null then null
        when {{ venue }}_ties > 0
            then cast({{ venue }}_wins as {{ dbt.type_string() }}) || '-'
              || cast({{ venue }}_losses as {{ dbt.type_string() }}) || '-'
              || cast({{ venue }}_ties as {{ dbt.type_string() }})
        else cast({{ venue }}_wins as {{ dbt.type_string() }}) || '-'
          || cast({{ venue }}_losses as {{ dbt.type_string() }})
    end                                                              as {{ venue }}_record,
    {% endfor %}
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
    end                                                              as current_record,
    -- R-140. The same string for the record the week LEAVES the team with. Ties extend it to
    -- three parts on the same rule, and the same null-not-zero discipline applies.
    case
        when wins_after is null then null
        when ties_after > 0 then cast(wins_after as {{ dbt.type_string() }}) || '-'
                             || cast(losses_after as {{ dbt.type_string() }}) || '-'
                             || cast(ties_after as {{ dbt.type_string() }})
        else cast(wins_after as {{ dbt.type_string() }}) || '-'
          || cast(losses_after as {{ dbt.type_string() }})
    end                                                              as record_after
from final
