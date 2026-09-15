-- A134 / R-887. The punter and the placekicker are ranked on what they DID, not on what it
-- was worth — and this test exists because the wrong choice is invisible to every count.
--
-- 🚨 THE BREAK THIS CATCHES LEAVES EVERY ROW PRESENT. Swap the placekicker's ranking from
-- ATTEMPTS to POINTS and the panel still has 7,816 rows, still one leader per team-game, still
-- no nulls, still the right tie rate. The only thing that changes is WHICH MAN IS ON THE CARD —
-- and it changes in 30 real team-games, measured. A presence assertion cannot see any of it.
--
-- ⚠️ SO THE ANCHORS ARE TEAM-GAMES WHERE THE TWO ANSWERS DIFFER. An anchor where both metrics
-- name the same man would pass under the break, which is R-843: a pin is only a pin if the
-- break moves it.
--
-- 🚨 AND A KICKER WHO WENT 0 FOR 2 IS STILL THE PLACEKICKER. That is the whole judgement: he is
-- the man the team sent out. Points is "made" in disguise and would hide him behind a team-mate
-- who kicked three extra points.

with leaders as (

    select game_id, team_id, panel, player_name, leader_rank,
           game_placekicks, game_kicking_points, game_punts, game_punt_yards
    from {{ ref('srv_game_team_leader_in_this_game') }}
    where panel in ('punting', 'kicking')

),

-- ⚠️ SCOPED ON THE GAME BEING IN THE VIEW AT ALL, NOT ON THE PANEL HAVING ROWS. A128 drafted
-- this guard the other way round and caught itself: keying on the panel's own rows means an
-- empty panel switches the assertion OFF, which is §6 mode 2 inside the test written to prevent
-- it. `ci/fixtures.sql` carries none of these games, so in CI this yields no rows and says so.
anchors as (

    select
        -- game 401635581, Rutgers. Derek Morris attempted three placekicks and scored two
        -- points; Ryan Coe attempted ONE and scored three. The placekicker is Morris.
        count(*) filter (where game_id = 401635581 and team_id = 25
                           and panel = 'kicking' and leader_rank = 1
                           and player_name = 'Derek Morris')                 as morris_leads,
        count(*) filter (where game_id = 401635581 and team_id = 25
                           and panel = 'kicking' and leader_rank = 1
                           and player_name = 'Ryan Coe')                     as coe_leads,
        count(*) filter (where game_id = 401635581 and team_id = 25
                           and panel = 'kicking')                            as kicking_rows,
        -- game 401628506, Oregon State. Sappington 3 kicks / 3 points against Boyle 2 / 4.
        count(*) filter (where game_id = 401628506 and team_id = 2483
                           and panel = 'kicking' and leader_rank = 1
                           and player_name = 'Atticus Sappington')           as sappington_leads,
        count(*) filter (where game_id = 401628506 and team_id = 2483
                           and panel = 'kicking')                            as kicking_rows_2
    from leaders

),

failures as (

    -- 1. THE PLACEKICKER IS THE MAN WHO KICKED, NOT THE MAN WHO SCORED.
    select 'kicking rank 1 is the attempts leader, not the points leader' as failure
    from anchors
    where kicking_rows > 0 and (morris_leads <> 1 or coe_leads <> 0)

    union all

    select 'the second kicking anchor names the attempts leader' as failure
    from anchors
    where kicking_rows_2 > 0 and sappington_leads <> 1

    union all

    -- 2. 🚨 NO PANEL MAY RANK ON AN ALL-NULL COLUMN. A128's catastrophe: rank() over a column
    -- that is null for every row makes every row jointly 1st, and the defensive panel went
    -- 13,375 -> 91,434. FG and XP carry their figures in made/attempted and their stat_value IS
    -- null, so this is the live hazard here rather than a remembered one.
    select 'a special-teams panel has a null ranking figure' as failure
    from leaders
    where (panel = 'kicking' and game_placekicks is null)
       or (panel = 'punting' and game_punts    is null)

    union all

    -- 3. THE RANKING FIGURE IS POSITIVE. A man who punted nothing did not lead the punting.
    select 'a leader qualified on a zero ranking figure' as failure
    from leaders
    where (panel = 'kicking' and game_placekicks <= 0)
       or (panel = 'punting' and game_punts      <= 0)

    union all

    -- 4. RANK 1 EXISTS WHEREVER THE PANEL DOES. A panel whose best row is rank 2 has lost its
    -- leader to a filter.
    select 'a special-teams panel has rows but no rank 1' as failure
    from (
        select game_id, team_id, panel, min(leader_rank) as best
        from leaders group by game_id, team_id, panel
    ) g
    where best <> 1

)

select * from failures
