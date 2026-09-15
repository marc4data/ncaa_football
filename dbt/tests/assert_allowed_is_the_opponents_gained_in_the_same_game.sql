-- A135 / R-899. `*_yards_allowed` is the OPPONENT's gained in the SAME game, and this test exists
-- because the obvious way to check that cannot see the defect it is aimed at.
--
-- 🚨 THE SYMMETRIC ASSERTION IS A TRAP, AND IT IS THE ONE A CAREFUL PERSON WRITES FIRST.
-- "this row's allowed equals the other row's gained" holds BOTH WAYS ROUND. With sides A and B
-- carrying a and b:
--
--     correct   A.gained=a A.allowed=b   B.gained=b B.allowed=a   ->  A.allowed == B.gained  ✅
--     SWAPPED   A.gained=b A.allowed=a   B.gained=a B.allowed=b   ->  A.allowed == B.gained  ✅
--
-- The swap is invisible to it, every row count is identical, and no null appears. ⚠️ SO THE CHECK
-- HAS TO REACH OUTSIDE THE PAIR — to the box score each figure is supposed to have come from.
--
-- 🚨 AND THE PAIRING TRAP IS ALREADY WRITTEN DOWN IN `matchup.py`: "a team's `_for` sits beside
-- the OTHER side's `_allowed`. Pairing a team's `_for` with its own `_allowed` describes ONE TEAM
-- rather than a matchup." This is that sentence as an assertion.

with published as (

    select game_id, team_id, team, season, season_type,
           total_yards, rushing_yards, passing_yards,
           total_yards_allowed, rushing_yards_allowed, passing_yards_allowed,
           game_figures_state, is_completed
    from {{ ref('srv_game_team') }}

),

-- THE SOURCE OF TRUTH, NOT THE OTHER HALF OF THE SAME VIEW. Each side's own box score.
box as (

    select game_id, team_id, total_yards, rushing_yards, passing_yards
    from {{ ref('fct_game_team') }}

),

failures as (

    -- 1. GAINED IS THIS TEAM'S OWN BOX SCORE. Under a gained/allowed swap this fires on every
    --    game whose two sides did not gain exactly the same yards.
    select 'gained is not this team''s own box score' as failure
    from published p
    join box b on b.game_id = p.game_id and b.team_id = p.team_id
    where p.total_yards   is distinct from b.total_yards
       or p.rushing_yards is distinct from b.rushing_yards
       or p.passing_yards is distinct from b.passing_yards

    union all

    -- 2. ALLOWED IS THE OPPONENT'S BOX SCORE — the same reach outside the pair, other way round.
    select 'allowed is not the opponent''s box score' as failure
    from published p
    join box o on o.game_id = p.game_id and o.team_id <> p.team_id
    where p.total_yards_allowed   is distinct from o.total_yards
       or p.rushing_yards_allowed is distinct from o.rushing_yards
       or p.passing_yards_allowed is distinct from o.passing_yards

    union all

    -- 3. 🚨 A PINNED VALUE, ON A GAME WHERE THE TWO SIDES ARE NOTHING ALIKE (R-843: a pin is only
    --    a pin if the break MOVES it). Mercer 834 yards, VMI 155, 2025 regular season. An anchor
    --    on a close game would survive the swap within rounding; this one cannot.
    --    ⚠️ Scoped on the GAME being present, not on the figures being present — keying on the
    --    figures would switch the assertion off exactly when it is needed (§6 mode 2).
    select 'the lopsided anchor game does not read 834 gained / 155 allowed' as failure
    from (
        select
            count(*)                                                        as rows_in_game,
            max(total_yards)         filter (where team = 'Mercer')         as mercer_gained,
            max(total_yards_allowed) filter (where team = 'Mercer')         as mercer_allowed,
            max(total_yards)         filter (where team = 'VMI')            as vmi_gained,
            max(total_yards_allowed) filter (where team = 'VMI')            as vmi_allowed
        from published where game_id = 401767577
    ) a
    where rows_in_game > 0
      and (mercer_gained <> 834 or mercer_allowed <> 155
           or vmi_gained <> 155 or vmi_allowed <> 834)

    union all

    -- 4. THE STATE COLUMN AGREES WITH THE FIGURES IT DESCRIBES. AC-G.11 is only worth anything
    --    if the label is true: a row saying `played` with no figure would be a confident wrong
    --    absence, which is the R-730 defect this column exists to prevent.
    select 'game_figures_state disagrees with the figures on its own row' as failure
    from published
    where (game_figures_state = 'played'       and total_yards is null)
       or (game_figures_state = 'scheduled'    and (total_yards is not null or is_completed))
       or (game_figures_state = 'no_box_score' and (total_yards is not null or not is_completed))
       or game_figures_state not in ('played', 'scheduled', 'no_box_score')

)

select * from failures
