-- R-722. The `challenging` branch is the one with arithmetic in it, and this is the test that
-- recomputes that arithmetic from the SOURCE figures rather than from the view's own delta.
--
-- 🚨 WITHOUT THIS, REVERSING THE TWO `Gained > Allowed` BRANCHES GOES UNDETECTED BY EVERY OTHER
-- CHECK. The sign test passes (both branches require a positive delta), the exhaustiveness test
-- passes (every row still lands somewhere), the row counts stay plausible, and the page renders
-- a mark on every game. Only recomputing the 0.2 ratio independently can tell `challenging` from
-- `contested`, because that ratio is the only thing that separates them.
--
-- ⚠️ IT READS `fct_team_yardage_week` DIRECTLY — the same two per-game figures srv_game_team
-- joins — so it is an independent recomputation rather than a restatement of the view's own
-- expression. A test that re-derives a column from that column proves nothing.
--
-- ⚠️ THE THRESHOLD IS 0.2 AND IT IS MARC'S NUMBER. Measured on 2026: it sits at the 37th
-- percentile of the rows where Gained > Allowed, so it splits that population roughly 37/63
-- rather than doing nothing or doing everything. Changing it is one literal in
-- `macros/matchup_outlook.sql` AND one here — and the fact that it appears twice is deliberate:
-- a test that reads the threshold from the macro would agree with the macro by construction.
with recomputed as (

    {% for metric in ['rushing', 'passing', 'total'] %}
    select
        '{{ metric }}'                                  as metric,
        g.game_team_sk,
        g.{{ metric }}_matchup_outlook                  as stored,
        ty.{{ metric }}_yards_for_per_game              as gained,
        oy.{{ metric }}_yards_allowed_per_game          as allowed,
        case
            when ty.{{ metric }}_yards_for_per_game is null
              or oy.{{ metric }}_yards_allowed_per_game is null then null
            when ty.{{ metric }}_yards_for_per_game
                 < oy.{{ metric }}_yards_allowed_per_game then 'favorable'
            when ty.{{ metric }}_yards_for_per_game
                 > oy.{{ metric }}_yards_allowed_per_game
             and (ty.{{ metric }}_yards_for_per_game
                  - oy.{{ metric }}_yards_allowed_per_game)
                 / ty.{{ metric }}_yards_for_per_game > 0.2 then 'challenging'
            else 'contested'
        end                                             as expected
    from {{ ref('srv_game_team') }} g
    left join {{ ref('fct_team_yardage_week') }} ty
           on ty.season = g.season and ty.season_type = g.season_type
          and ty.week = g.week and ty.team_id = g.team_id
    left join {{ ref('fct_team_yardage_week') }} oy
           on oy.season = g.season and oy.season_type = g.season_type
          and oy.week = g.week and oy.team_id = g.opponent_team_id
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

)

select metric, game_team_sk, gained, allowed, stored, expected,
       'the stored outlook must equal the outlook recomputed from the source figures' as rule
from recomputed
where stored is distinct from expected
