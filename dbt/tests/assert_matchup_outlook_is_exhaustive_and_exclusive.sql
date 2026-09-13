-- R-722. The three matchup outlooks must partition every classified row: each one lands in
-- exactly one bucket, and no row that HAS both figures escapes classification.
--
-- 🚨 THIS IS THE BRANCH ORDER MADE CHECKABLE, AND THE ORDER IS THE WHOLE DESIGN. `challenging`
-- is a STRICT SUBSET of `contested` — every game satisfying `(Gained - Allowed) / Gained > 0.2`
-- also satisfies `Gained > Allowed`. So a `case` that tested `contested` first would make
-- `challenging` unreachable, the column would silently lose one of its three values, and
-- nothing else in the project would notice: the row counts stay plausible, every row is still
-- classified, and the page still renders a mark on every game. It would just be the wrong mark,
-- on roughly a third of them.
--
-- ⚠️ SO "EXHAUSTIVE" ALONE WOULD PASS THE BUG. What catches it is recomputing each condition
-- INDEPENDENTLY of the case expression and asserting the stored value against them — which is
-- why this test does not simply count nulls.
--
-- ⚠️ AND A NULL IS NOT A FAILURE HERE. A row with no figure on either side — week 1, a non-FBS
-- team with no deep stats — is honestly unclassifiable, and the delta column beside it is null
-- for the same reason. Measured on 2026: 4,614 of 7,358 rows, and the outlook is null on exactly
-- the rows the delta is. What this test forbids is a row that HAS both figures and no outlook.
with expected as (

    {% for metric in ['rushing', 'passing', 'total'] %}
    select
        '{{ metric }}'                                as metric,
        game_team_sk,
        {{ metric }}_matchup_outlook                  as stored,
        -- The delta is `Gained - Allowed` for the same pair, so its SIGN decides which of the
        -- three branches a row belongs in — except that it cannot separate `contested` from
        -- `challenging`, which share a sign and differ only by the 0.2 ratio. This view does not
        -- carry `Gained` itself, so that half is asserted by
        -- assert_matchup_outlook_agrees_with_its_ratio, which reads the marts.
        -- ⚠️ THE SPLIT IS DELIBERATE AND THE OTHER TEST NAMES WHY: a break that swaps the two
        -- positive-delta branches passes THIS test completely.
        {{ metric }}_yards_for_minus_opponent_allowed_per_game as delta
    from {{ ref('srv_game_team') }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

)

select metric, game_team_sk, stored, delta,
    case
      when delta is not null and stored is null
        then 'a row with a delta must carry an outlook'
      when delta is null and stored is not null
        then 'a row with no delta cannot carry an outlook'
      when delta < 0 and stored <> 'favorable'
        then 'gained < allowed must be favorable'
      when delta = 0 and stored <> 'contested'
        then 'gained = allowed is classified contested, deliberately'
      when delta > 0 and stored not in ('contested', 'challenging')
        then 'gained > allowed must be contested or challenging'
      when stored not in ('favorable', 'contested', 'challenging')
        then 'an outlook outside the three values reached the page'
    end as rule
from expected
where (delta is not null and stored is null)
   or (delta is null and stored is not null)
   or (delta < 0 and stored <> 'favorable')
   or (delta = 0 and stored <> 'contested')
   or (delta > 0 and stored not in ('contested', 'challenging'))
   or (stored is not null and stored not in ('favorable', 'contested', 'challenging'))
