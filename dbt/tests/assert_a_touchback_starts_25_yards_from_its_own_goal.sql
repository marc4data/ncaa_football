-- The named anchor for the coordinate: a touchback is 75 yards to go, and must read as 25
-- yards from the offense's own goal line.
--
-- AN EXISTENCE TEST, NOT A CONSISTENCY ONE. The complement test proves the arithmetic holds
-- wherever it is applied; this proves the arithmetic is applied to the right quantity, by
-- pinning one value a reader can check against a football field. A model that computed
-- `yards_from_own_goal` off `yardline` instead would pass the complement test and fail here.
--
-- It cannot pass vacuously: the touchback is the most common start in the data.
select 'no touchback drive reads as 25 yards from own goal' as failure
from (
    select count(*) as n
    from {{ ref('fct_drive') }}
    where start_yards_to_goal = 75
      and start_yards_from_own_goal = 25
) probe
where probe.n = 0
