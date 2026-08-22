-- No serving view carries a null team name or a null team slug. Any view, any row.
--
-- THE DIMENSION DOES NOT COVER THE FACT'S KEY SPACE. dim_team is built from CFBD's /teams
-- response; fct_game's key space is /games. /games is the authority on who played, /teams
-- on who is an FBS programme, and a Division II visitor is legitimately in the first and
-- legitimately absent from the second.
--
-- Found on srv_scoreboard at 11% of rows. Swept for rather than fixed, which turned one
-- defect into five:
--
--   srv_scoreboard      12,168 of 110,634    11.0%
--   srv_team_game_log   12,552 of 221,268     5.7%
--   srv_standings        7,482 of  30,475    24.6%
--   srv_rankings           662 of  49,798     1.3%
--   srv_today_edges            9 of     211     4.3%   <- the landing page
--
-- Four of those five were invisible until the first was generalised. This test is the
-- generalisation made permanent: it covers every view that carries an identity pair, so
-- the sixth occurrence fails the build on the commit that introduces it rather than
-- appearing as an em dash on a page nobody was looking at.
--
-- A null display renders as an em dash where a team should be. A null slug is worse: it is
-- a clickable row pointing nowhere, and a link to nowhere is worse than a row that was
-- never clickable.
with offenders as (

    {% set paired = [
        ('srv_scoreboard', ['home', 'away']),
        ('srv_schedule',   ['home', 'away']),
        ('srv_odds_board', ['home', 'away']),
        ('srv_today_edges', ['home', 'away']),
    ] %}
    {% set single = [
        'srv_rankings', 'srv_standings', 'srv_team_game_log',
        'srv_team_overview', 'srv_team_stats', 'srv_teams_index',
    ] %}

    {% for view, sides in paired %}
    select '{{ view }}' as view_name, 'display or slug' as problem, count(*) as offending_rows
    from {{ ref(view) }}
    where {% for side in sides %}
          {{ side }}_team_display is null or {{ side }}_team_slug is null
          {%- if not loop.last %} or {% endif %}
          {%- endfor %}
    having count(*) > 0
    union all
    {% endfor %}

    {% for view in single %}
    select '{{ view }}', 'display or slug', count(*)
    from {{ ref(view) }}
    where team_display is null or team_slug is null
    having count(*) > 0
    {%- if not loop.last %}
    union all
    {% endif %}
    {% endfor %}

)
select * from offenders
