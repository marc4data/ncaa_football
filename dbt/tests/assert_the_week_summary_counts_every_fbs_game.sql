-- A214. THE WEEK SUMMARY'S POPULATION IS RECONCILED AGAINST THE VIEW IT AGGREGATES.
--
-- 🚨 A MODEL THAT AGREES WITH ITSELF HAS PROVED NOTHING. Every figure on `srv_week_summary` is
-- computed over one game set, defined once in its `games` CTE. This asserts that the set really
-- is every game with an FBS team on either side — by counting them again, in the other relation,
-- and requiring the two numbers to match.
--
-- IT CATCHES TWO DIFFERENT DEFECTS, AND THEY FAIL ON DIFFERENT SIDES OF THE JOIN:
--
--   1. 🚨 A NARROWED POPULATION. Changing `where is_fbs_game` to require BOTH sides to be FBS
--      reads as a tightening rather than a bug, and every rate stays inside [0, 1] afterwards,
--      so the rate test cannot see it. Here `fbs_games` simply stops matching and the row fires.
--   2. 🚨 A WEEK THAT PRODUCES NO ROW AT ALL. The model LEFT JOINs the record spine precisely so
--      a week nobody has played still publishes a row — *no games yet* and *no row for this
--      week* are different facts and a page cannot tell them apart from an empty result
--      (AC-G.11). A FULL join here means a week present in `srv_game` and missing from the
--      summary fails with `summary_games` null, rather than passing unnoticed.
--
-- ⚠️ BOTH SIDES ARE `ref()`ed (§3.6), so this is ordered after the two relations it compares
-- rather than free to run before either exists.
--
-- ⚠️ AND IT IS A PROPERTY, NOT A PINNED VALUE (§2.3.3), so it says the same true thing about
-- CI's fixture sample as about the production warehouse. It names no game and no week.
with from_the_game_view as (
    select season, season_type, week, count(*) as game_view_games
    from {{ ref('srv_game') }}
    where is_fbs_game
    group by season, season_type, week
),

from_the_summary as (
    select season, season_type, week, fbs_games as summary_games
    from {{ ref('srv_week_summary') }}
)

select
    coalesce(g.season, s.season)           as season,
    coalesce(g.season_type, s.season_type) as season_type,
    coalesce(g.week, s.week)               as week,
    g.game_view_games,
    s.summary_games
from from_the_game_view g
full outer join from_the_summary s
  on  s.season = g.season and s.season_type = g.season_type and s.week = g.week
where g.game_view_games is distinct from s.summary_games
