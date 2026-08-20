-- Every game-grain serving row can name both teams and link to both.
--
-- fct_game carries a name for both sides on every row, always. dim_team does not: it is
-- built from CFBD's /teams response, which does not list every opponent an FBS or FCS side
-- schedules, so a Division II visitor exists in /games and not in /teams.
--
-- srv_scoreboard took the display name off the dimension and had it NULL on 12,168 of
-- 110,634 rows — 11% of the scoreboard. The Scores page rendered an em dash for the team
-- and `None` for the winner, and nobody saw it because every page had only ever been
-- checked against 2026 rows, where no game is completed and the whole post-game path is
-- unreachable.
--
-- The slug matters for the same reason one level down: a null slug is a link to nowhere.
-- It falls back to a slug of the game's own team name, which resolves to a team page that
-- honestly renders Empty — a team with no dim_team row genuinely has no season record.
--
-- Both views are checked. srv_schedule already took its NAME from the game and was correct;
-- it had the same null SLUG. A test covering only the view that was wrong would not have
-- found that.
with offenders as (

    select 'srv_scoreboard' as view_name, game_id,
           home_team_display, away_team_display, home_team_slug, away_team_slug
    from {{ ref('srv_scoreboard') }}
    where home_team_display is null or away_team_display is null
       or home_team_slug is null or away_team_slug is null

    union all

    select 'srv_schedule', game_id,
           home_team_display, away_team_display, home_team_slug, away_team_slug
    from {{ ref('srv_schedule') }}
    where home_team_display is null or away_team_display is null
       or home_team_slug is null or away_team_slug is null

)
select * from offenders
